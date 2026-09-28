"""라운드 승리 방식으로 공격/수비 진영을 역산한다.

왜 이 방법인가 (근거: reports/data_audit.md §4):
- maps_scores.csv의 'Attacker/Defender Score'는 이름과 달리 전반/후반 점수라서 진영 정보가 없다.
- 대신 게임 규칙상 일부 승리 방식은 승리 팀의 진영을 확정한다.
    Detonated(스파이크 폭발)            → 승리 팀 = 공격
    Defused(해체)                       → 승리 팀 = 수비
    Time Expiry (No Plant)(설치 없이 종료) → 승리 팀 = 수비
  Elimination(전멸)은 양쪽 모두 가능하므로 정보가 없다.
- 진영은 1~12R 고정, 13~24R 교대, 25R부터(연장) 매 라운드 교대하며 25R은 전반과 같은 진영이다.
  (감사에서 교대 규칙 일치율 99.97~100%, 연장 규칙 일치율 100%로 확인)

그래서 맵 안의 결정적 라운드 하나하나를 "전반 공격팀은 누구였나"라는 하나의 질문으로 환산해 모으고,
답이 하나로 모이면 맵 전체 진영을 채운다. 답이 엇갈리면(데이터 오류) 추측하지 않고 NULL로 둔다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from propredict.etl.sources import MAP_KEY

SIDE_BY_WIN_METHOD = {
    "Detonated": "atk",
    "Defused": "def",
    "Time Expiry (No Plant)": "def",
}
HALF_LENGTH = 12
OVERTIME_START = 2 * HALF_LENGTH + 1


def in_first_half_side(round_number: pd.Series) -> pd.Series:
    """해당 라운드에 각 팀이 '전반과 같은 진영'인지 여부."""
    r = round_number.astype(int)
    first = r <= HALF_LENGTH
    overtime_same = (r >= OVERTIME_START) & ((r - OVERTIME_START) % 2 == 0)
    return first | overtime_same


def infer_first_half_attacker(win_loss: pd.DataFrame) -> pd.Series:
    """맵별 전반 공격팀 이름. 알 수 없거나 모순이면 <NA>.

    win_loss: 라운드마다 팀별 1행(Team, Method, Outcome)인 원본 형식.
    """
    win = win_loss.loc[win_loss["Outcome"] == "Win", MAP_KEY + ["Round Number", "Team", "Method"]].copy()
    win["side"] = win["Method"].map(SIDE_BY_WIN_METHOD)
    dec = win[win["side"].notna()]
    if dec.empty:
        return pd.Series(pd.NA, index=pd.MultiIndex.from_tuples([], names=MAP_KEY), dtype="string")

    teams = win_loss.groupby(MAP_KEY)["Team"].agg(lambda s: tuple(sorted(s.unique())))
    dec = dec.join(teams.rename("teams"), on=MAP_KEY)
    dec = dec[dec["teams"].map(len) == 2]

    def other(team: str, pair: tuple[str, str]) -> str:
        return pair[1] if pair[0] == team else pair[0]

    attacker = np.where(
        dec["side"] == "atk", dec["Team"], [other(t, p) for t, p in zip(dec["Team"], dec["teams"], strict=True)]
    )
    same = in_first_half_side(dec["Round Number"]).to_numpy()
    # 이 라운드의 공격팀 → 전반 공격팀으로 환산
    h1_attacker = np.where(
        same, attacker, [other(a, p) for a, p in zip(attacker, dec["teams"], strict=True)]
    )
    votes = pd.Series(h1_attacker, index=pd.MultiIndex.from_frame(dec[MAP_KEY])).groupby(level=MAP_KEY)
    uniq = votes.nunique()
    first = votes.first()
    # 표가 엇갈리면 어느 쪽도 믿을 근거가 없으므로 NULL (없는 값을 만들어내지 않는다)
    return first.where(uniq == 1).astype("string")


def team_a_side(round_number: pd.Series, team_a: pd.Series, h1_attacker: pd.Series) -> pd.Series:
    """라운드별 Team A 진영('atk'/'def'). 전반 공격팀을 모르면 <NA>."""
    known = h1_attacker.notna()
    a_attacks_h1 = (team_a == h1_attacker).fillna(False).to_numpy(dtype=bool)
    same = in_first_half_side(round_number).to_numpy(dtype=bool)
    atk = a_attacks_h1 == same
    out = pd.Series(np.where(atk, "atk", "def"), index=round_number.index, dtype="string")
    return out.where(known.to_numpy(), pd.NA)
