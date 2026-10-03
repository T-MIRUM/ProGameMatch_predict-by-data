"""모델 서빙 서비스.

앱 시작 시 한 번만 만들어 app.state에 보관한다(main.lifespan). 요청마다 joblib을 읽으면
디스크 I/O로 수십~수백 ms가 들어 '입력 변경 후 500ms 안에 갱신' 목표를 지키기 어렵다.

피처는 학습과 같은 함수(propredict.ml.features.state_features / sequence_features)로 만든다.
서빙 쪽에서 피처를 다시 구현하면 학습과 미묘하게 달라지는 training-serving skew가 생긴다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from propredict.api.schemas import Factor, PredictRequest, PredictResponse
from propredict.ml.features import BUY_ORDER, sequence_features, state_features
from propredict.ml.model import RoundWinModel

FEATURE_LABELS = {
    "team_a_loadout": "A 장비 가치", "team_b_loadout": "B 장비 가치", "loadout_diff": "장비 가치 차이",
    "loadout_share": "장비 가치 비율", "team_a_credits": "A 잔여 크레딧", "team_b_credits": "B 잔여 크레딧",
    "buy_a": "A 구매 유형", "buy_b": "B 구매 유형", "buy_diff": "구매 유형 격차", "buy_matchup": "구매 유형 조합",
    "round_number": "라운드 번호", "half": "전반/후반/연장", "is_pistol": "피스톨 라운드",
    "score_a": "A 스코어", "score_b": "B 스코어", "score_diff": "스코어 차이", "side_a_atk": "A 진영",
    "map_side": "맵 × 진영", "map_name": "맵",
    "prev_a_won": "직전 라운드 승패", "streak": "연승/연패", "last3_a_winrate": "최근 3라운드 승률",
    "team_a_strength": "A 팀 강도", "team_b_strength": "B 팀 강도", "strength_diff": "팀 강도 차이",
}  # fmt: skip
# 시뮬레이터 요청에는 모멘텀·팀 강도가 없다(중립값으로 채움). 사용자가 넣지 않은 값이 '예측 요인'으로
# 보이면 혼란스러우므로, 요청에서 온 피처만 상위 요인 후보로 삼는다.
NEUTRAL_FILLED = {"prev_a_won", "streak", "last3_a_winrate", "team_a_strength", "team_b_strength", "strength_diff"}
UPSET_THRESHOLD = 0.3


@dataclass
class ModelService:
    model: RoundWinModel
    lookup: pd.DataFrame
    team_strength: dict[str, float]
    match_strength: dict[int, tuple[float, float]]
    metrics: dict

    @classmethod
    def load(cls, artifacts_dir: Path) -> ModelService:
        art = joblib.load(artifacts_dir / "model.joblib")
        metrics = json.loads((artifacts_dir / "metrics.json").read_text())
        return cls(
            model=art["model"],
            lookup=art["lookup_table"],
            team_strength=art["team_strength"],
            match_strength=art.get("match_strength", {}),
            metrics=metrics,
        )

    # ------------------------------------------------------------ 룩업표 베이스라인
    def baseline(self, buy_a: str | None, buy_b: str | None) -> float | None:
        if buy_a is None or buy_b is None:
            return None
        key = (float(BUY_ORDER[buy_a]), float(BUY_ORDER[buy_b]))
        return round(float(self.lookup["win_rate"].get(key, 0.5)), 4)

    # ------------------------------------------------------------ 시뮬레이터
    def predict(self, req: PredictRequest, top_k: int = 5) -> PredictResponse:
        state = {
            **req.model_dump(),
            "prev_a_won": np.nan, "streak": 0.0, "last3_a_winrate": np.nan,
            "team_a_strength": 0.5, "team_b_strength": 0.5,
        }  # fmt: skip
        X = state_features(pd.DataFrame([state]))
        p = float(self.model.predict_proba(X)[0])
        contrib = self.model.contributions(X).iloc[0].drop(["bias", *NEUTRAL_FILLED])
        top = contrib.reindex(contrib.abs().sort_values(ascending=False).index)[:top_k]
        return PredictResponse(
            win_probability_a=round(p, 4),
            win_probability_b=round(1 - p, 4),
            baseline_probability_a=self.baseline(req.team_a_buy_type, req.team_b_buy_type),
            top_factors=[
                Factor(feature=f, label=FEATURE_LABELS.get(f, f), contribution=round(float(v), 4))
                for f, v in top.items()
            ],  # fmt: skip
        )

    # ------------------------------------------------------------ 경기 리플레이
    def strength_for(self, source_match_id: float | None) -> tuple[float, float]:
        if source_match_id is None or np.isnan(source_match_id):
            return (0.5, 0.5)
        # 학습 이후 새로 적재된 경기는 아티팩트에 없다 → 중립값 (재학습하면 채워진다)
        return self.match_strength.get(int(source_match_id), (0.5, 0.5))

    def replay(self, rounds: pd.DataFrame) -> pd.DataFrame:
        """한 경기의 라운드(dataset.QUERY 형식, 맵·라운드 순 정렬) → 라운드별 예측 확률."""
        seq = sequence_features(rounds)
        a_str, b_str = self.strength_for(rounds["source_match_id"].iloc[0])
        state_in = pd.concat([rounds.drop(columns=[c for c in seq.columns if c in rounds]), seq], axis=1)
        state_in = state_in.assign(team_a_strength=a_str, team_b_strength=b_str)
        X = state_features(state_in)
        has_eco = rounds["team_a_buy_type"].notna() & rounds["team_b_buy_type"].notna()
        p = pd.Series(np.nan, index=rounds.index)
        if has_eco.any():
            # 학습은 구매유형이 있는 라운드로만 했으므로, 없는 라운드는 외삽하지 않고 비워 둔다
            p[has_eco] = self.model.predict_proba(X[has_eco])
        out = rounds.assign(score_a=seq["score_a"], score_b=seq["score_b"], win_probability_a=p)
        out["baseline_probability_a"] = [
            self.baseline(a, b) for a, b in zip(rounds["team_a_buy_type"], rounds["team_b_buy_type"], strict=True)
        ]
        winner_p = np.where(out["winner"] == "A", out["win_probability_a"], 1 - out["win_probability_a"])
        out["upset"] = pd.Series(winner_p, index=out.index).lt(UPSET_THRESHOLD).fillna(False)
        out.attrs["strength"] = (a_str, b_str)
        return out
