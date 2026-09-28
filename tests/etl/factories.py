"""ETL 테스트용 가짜 원본 데이터 생성기.

실제 CSV와 같은 컬럼 형식을 만들어, 수십 MB 원본 없이도 변환 규칙을 검증한다.
"""
from __future__ import annotations

import pandas as pd

LOSER_METHOD = {
    "Elimination": "Eliminated",
    "Detonated": "Failed Defused",
    "Defused": "Detonated Denied",
    "Time Expiry (No Plant)": "Time Expiry (Failed to Plant)",
}


def match_key(name: str = "A vs B") -> dict[str, str]:
    return {"Tournament": "T", "Stage": "S", "Match Type": "MT", "Match Name": name}


def win_loss(rounds: list[tuple[int, str, str]], teams=("Alpha", "Bravo"), map_name="Ascent", name="A vs B"):
    """rounds: [(라운드 번호, 승리 팀, 승리 방식), ...]"""
    rows = []
    for r, winner, method in rounds:
        loser = teams[1] if winner == teams[0] else teams[0]
        base = {**match_key(name), "Map": map_name, "Round Number": r}
        rows.append({**base, "Team": winner, "Method": method, "Outcome": "Win"})
        rows.append({**base, "Team": loser, "Method": LOSER_METHOD[method], "Outcome": "Loss"})
    return pd.DataFrame(rows)


def eco(rounds: list[tuple[int, str, str, str, str, str]], map_name="Ascent", name="A vs B"):
    """rounds: [(라운드, 팀, 장비가치, 잔여크레딧, 구매유형, 'Win'|'Loss'), ...] — 라운드마다 팀별 1행."""
    rows = [
        {**match_key(name), "Map": map_name, "Round Number": r, "Team": team,
         "Loadout Value": lo, "Remaining Credits": cr, "Type": typ, "Outcome": out}
        for r, team, lo, cr, typ, out in rounds
    ]
    return pd.DataFrame(rows).astype({"Loadout Value": "string", "Remaining Credits": "string"})


def scores(name="A vs B", teams=("Alpha", "Bravo"), score=(1, 0)):
    return pd.DataFrame([{**match_key(name), "Team A": teams[0], "Team B": teams[1],
                          "Team A Score": score[0], "Team B Score": score[1], "Match Result": f"{teams[0]} won"}])


def ids(name="A vs B", maps=("Ascent",), match_id=100, first_game_id=1000):
    return pd.DataFrame([{**match_key(name), "Map": m, "Match ID": match_id, "Game ID": first_game_id + i}
                         for i, m in enumerate(maps)])
