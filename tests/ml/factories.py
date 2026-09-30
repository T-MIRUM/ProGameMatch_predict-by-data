"""모델 테스트용 가짜 라운드 시퀀스 (dataset.load_rounds()와 같은 컬럼)."""

from __future__ import annotations

import pandas as pd


def rounds(matches: list[dict]) -> pd.DataFrame:
    """matches: [{"match_id", "season", "team_a", "team_b", "winners": "AABAB"...}, ...] (한 경기 = 한 맵)."""
    rows = []
    for m in matches:
        for i, w in enumerate(m["winners"], start=1):
            rows.append({
                "match_id": m["match_id"], "season": m.get("season", 2021),
                "source_match_id": float(m.get("source_match_id", m["match_id"])),
                "tournament": "T", "team_a": m["team_a"], "team_b": m["team_b"],
                "map_game_id": m["match_id"] * 10, "map_name": m.get("map_name", "Ascent"), "map_order": 1.0,
                "round_number": i, "team_a_side": m.get("side", "atk") if i <= 12 else "def",
                "team_a_loadout": 20000.0, "team_b_loadout": 4000.0,
                "team_a_credits": 1000.0, "team_b_credits": 3000.0,
                "team_a_buy_type": "Full buy: 20k+", "team_b_buy_type": "Eco: 0-5k",
                "winner": w,
            })  # fmt: skip
    return pd.DataFrame(rows)
