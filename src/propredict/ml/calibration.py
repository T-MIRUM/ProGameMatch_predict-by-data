"""확률 보정기와 보정 방법 선택.

처음에는 isotonic 회귀로 보정했다. 그런데 웹 시뮬레이터에서 입력을 바꿔도 확률이 그대로인 문제가 드러났다.
- isotonic은 계단 함수다. 출력이 수십 개 값뿐이라 원출력이 조금 바뀌어도 같은 계단에 머문다.
- 보정 데이터의 양 끝에 표본이 적어 0%·100%를 출력하는 구간이 생긴다. 라운드 승패에 '확실'은 없다.
그래서 보정 방법을 감으로 바꾸지 않고, 보정용 데이터 안에서 경기 단위 교차검증으로 후보를 비교해 고른다
(docs/decisions.md D22). 테스트 시즌은 선택에 쓰지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold

from propredict.ml.evaluate import evaluate

_EPS = 1e-6


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), _EPS, 1 - _EPS)
    return np.log(p / (1 - p))


@dataclass
class IdentityCalibrator:
    """보정하지 않음. 비교 기준으로 후보에 넣는다(보정이 오히려 나쁘게 만들 수도 있으므로)."""

    name: str = "none"

    def fit(self, p: np.ndarray, y: np.ndarray) -> IdentityCalibrator:
        return self

    def predict(self, p: np.ndarray) -> np.ndarray:
        return np.asarray(p, dtype=float)


@dataclass
class IsotonicCalibrator:
    """단조 증가 계단 함수. 모양 제약이 없어 유연하지만 표본이 적은 구간에서 과적합한다."""

    name: str = "isotonic"

    def fit(self, p: np.ndarray, y: np.ndarray) -> IsotonicCalibrator:
        self.model_ = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(p, y)
        return self

    def predict(self, p: np.ndarray) -> np.ndarray:
        return self.model_.predict(p)


@dataclass
class PlattCalibrator:
    """Platt 보정: logit(p)에 1차 로지스틱 회귀(기울기 a, 절편 b)를 맞춘다.

    파라미터가 2개뿐이라 수천 라운드로도 안정적으로 추정되고, 출력이 매끄럽고 단조이며 0·1에 닿지 않는다.
    LightGBM 원출력이 이미 대체로 보정돼 있어(ECE 약 1.5%) 큰 모양 변화가 필요 없다는 점도 이 방법과 맞는다.
    """

    name: str = "platt"

    def fit(self, p: np.ndarray, y: np.ndarray) -> PlattCalibrator:
        # C를 크게: 정규화 없이 a·b를 그대로 추정한다(피처가 1개라 과적합 위험이 없다)
        self.model_ = LogisticRegression(C=1e6).fit(_logit(p)[:, None], y)
        return self

    def predict(self, p: np.ndarray) -> np.ndarray:
        return self.model_.predict_proba(_logit(p)[:, None])[:, 1]

    @property
    def slope_intercept(self) -> tuple[float, float]:
        return float(self.model_.coef_[0, 0]), float(self.model_.intercept_[0])


@dataclass
class BetaCalibrator:
    """Beta 보정(Kull et al., 2017): log p와 log(1-p)에 각각 계수를 둔다. Platt보다 파라미터가 1개 많다."""

    name: str = "beta"

    @staticmethod
    def _x(p: np.ndarray) -> np.ndarray:
        p = np.clip(np.asarray(p, dtype=float), _EPS, 1 - _EPS)
        return np.c_[np.log(p), -np.log(1 - p)]

    def fit(self, p: np.ndarray, y: np.ndarray) -> BetaCalibrator:
        self.model_ = LogisticRegression(C=1e6).fit(self._x(p), y)
        return self

    def predict(self, p: np.ndarray) -> np.ndarray:
        return self.model_.predict_proba(self._x(p))[:, 1]


# 순서 = 동률일 때 우선순위(단순한 것부터). 선택은 Brier 기준이며, 차이가 tol 이하이면 앞쪽(더 단순한) 방법을 고른다.
CANDIDATES = (IdentityCalibrator, PlattCalibrator, BetaCalibrator, IsotonicCalibrator)


def select_calibrator(
    p: np.ndarray, y: np.ndarray, groups: np.ndarray, n_splits: int = 5, tol: float = 1e-5
) -> tuple[object, list[dict]]:
    """경기 단위 K-fold로 후보 보정기를 비교해 가장 좋은 것을 고르고, 전체 데이터로 다시 학습해 돌려준다.

    경기 단위로 나누는 이유: 같은 경기의 라운드가 학습 fold와 평가 fold에 섞이면 평가가 낙관적이 된다.
    반환: (전체 데이터로 학습한 보정기, 후보별 교차검증 지표 목록)
    """
    p, y, groups = np.asarray(p, dtype=float), np.asarray(y, dtype=int), np.asarray(groups)
    oof = {c.name: np.zeros(len(y)) for c in (k() for k in CANDIDATES)}
    for tr, te in GroupKFold(n_splits=n_splits).split(p, y, groups):
        for cls in CANDIDATES:
            cal = cls().fit(p[tr], y[tr])
            oof[cal.name][te] = cal.predict(p[te])

    table = []
    for cls in CANDIDATES:
        name = cls().name
        m = evaluate(y, oof[name])
        table.append({"method": name, "cv_brier": m["brier"], "cv_log_loss": m["log_loss"], "cv_ece": m["ece"]})

    best = min(r["cv_brier"] for r in table)
    chosen = next(r["method"] for r in table if r["cv_brier"] <= best + tol)
    for r in table:
        r["selected"] = r["method"] == chosen
    cls = next(c for c in CANDIDATES if c().name == chosen)
    return cls().fit(p, y), table
