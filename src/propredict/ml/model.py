"""서빙용 모델 래퍼: LightGBM + 확률 보정기 + 범주 인코딩을 한 객체로 묶는다.

한 객체로 묶는 이유: API가 '학습 때와 똑같은' 범주 목록·보정기를 쓰도록 강제하기 위해서다.
범주 순서가 학습 때와 다르면 LightGBM은 조용히 엉뚱한 분기를 탄다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import lightgbm as lgb
import numpy as np
import pandas as pd

from propredict.ml.features import CATEGORICAL_FEATURES, FEATURES


def fit_categories(X: pd.DataFrame) -> dict[str, list[str]]:
    return {c: sorted(X[c].astype(str).unique().tolist()) for c in CATEGORICAL_FEATURES}


def to_model_frame(X: pd.DataFrame, categories: dict[str, list[str]]) -> pd.DataFrame:
    F = X[FEATURES].copy()
    for c in CATEGORICAL_FEATURES:
        # 학습 때 없던 값(새 맵 등)은 NaN 범주로 → LightGBM이 결측 경로로 처리한다
        F[c] = pd.Categorical(F[c].astype(str), categories=categories[c])
    return F


class Calibrator(Protocol):
    """보정기 인터페이스: 원출력 확률 배열 → 보정된 확률 배열 (구현은 ml/calibration.py)."""

    name: str

    def predict(self, p: np.ndarray) -> np.ndarray: ...


@dataclass
class RoundWinModel:
    classifier: lgb.LGBMClassifier
    categories: dict[str, list[str]]
    calibrator: Calibrator | None = None
    meta: dict = field(default_factory=dict)

    def predict_raw(self, X: pd.DataFrame) -> np.ndarray:
        return self.classifier.predict_proba(to_model_frame(X, self.categories))[:, 1]

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        raw = self.predict_raw(X)
        return self.calibrator.predict(raw) if self.calibrator is not None else raw

    def contributions(self, X: pd.DataFrame) -> pd.DataFrame:
        """피처별 TreeSHAP 기여도(로그 오즈 단위, 보정 전 모델 기준). 마지막 열 bias = 기준값."""
        contrib = self.classifier.booster_.predict(to_model_frame(X, self.categories), pred_contrib=True)
        return pd.DataFrame(contrib, columns=[*FEATURES, "bias"], index=X.index)
