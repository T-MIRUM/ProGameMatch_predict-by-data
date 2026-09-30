"""학습/검증/테스트 분할 (docs/decisions.md D1).

- 시즌 단위로 나눈다: train 2021–2023 / valid 2024 / test 2025, 2026(각각 보고).
  시즌이 다르면 경기가 겹칠 수 없으므로 'match_id 단위 분할' 요구도 자동으로 만족한다.
- 라운드 단위 무작위 분할은 하지 않는다: 같은 경기의 라운드가 train/test에 섞이면
  팀·맵·흐름을 외워서 성능이 부풀려진다.
- valid(2024)는 경기 단위로 반으로 나눠 한쪽은 조기 종료, 다른 쪽은 확률 보정에 쓴다.
  같은 데이터로 둘 다 하면 보정기가 조기 종료에 맞춰진 예측을 다시 학습해 과적합된다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SPLITS: dict[str, tuple[int, ...]] = {
    "train": (2021, 2022, 2023),
    "valid": (2024,),
    "test_2025": (2025,),
    "test_2026": (2026,),
}


def split_by_season(F: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {name: F[F["season"].isin(seasons)].copy() for name, seasons in SPLITS.items()}


def split_matches(df: pd.DataFrame, frac: float = 0.5, seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame]:
    """경기(match_id) 단위로 두 그룹으로 나눈다. 같은 경기의 라운드는 항상 같은 쪽에 간다."""
    ids = np.sort(df["match_id"].unique())
    rng = np.random.default_rng(seed)
    first = set(rng.choice(ids, size=int(len(ids) * frac), replace=False).tolist())
    mask = df["match_id"].isin(first)
    return df[mask].copy(), df[~mask].copy()
