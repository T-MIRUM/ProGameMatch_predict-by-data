"""비교 기준선.

모델의 가치는 '얼마나 정확한가'가 아니라 '단순한 방법보다 얼마나 나은가'로 증명해야 한다.
- ConstantBaseline: 항상 0.5. Brier 0.25가 '아무것도 모를 때'의 기준.
- LookupTableBaseline: 구매유형 조합(4×4)별 과거 승률. 명세 §5.6의 표 그 자체이며,
  모델이 이 표를 못 이기면 피처 설계를 다시 해야 한다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class ConstantBaseline:
    name = "constant_0.5"

    def fit(self, X: pd.DataFrame, y: pd.Series) -> ConstantBaseline:
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        return np.full(len(X), 0.5)


class LookupTableBaseline:
    name = "lookup_buy_matchup"

    def __init__(self, min_count: int = 30):
        # 표본이 너무 적은 칸은 우연에 흔들리므로 0.5로 둔다
        self.min_count = min_count
        self.table: pd.DataFrame | None = None

    def fit(self, X: pd.DataFrame, y: pd.Series) -> LookupTableBaseline:
        g = pd.DataFrame({"buy_a": X["buy_a"], "buy_b": X["buy_b"], "y": y}).dropna().groupby(["buy_a", "buy_b"])
        t = g["y"].agg(["mean", "size"]).rename(columns={"mean": "win_rate", "size": "count"})
        t.loc[t["count"] < self.min_count, "win_rate"] = 0.5
        self.table = t
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        assert self.table is not None, "fit 먼저"
        idx = pd.MultiIndex.from_arrays([X["buy_a"], X["buy_b"]])
        return self.table["win_rate"].reindex(idx).fillna(0.5).to_numpy()
