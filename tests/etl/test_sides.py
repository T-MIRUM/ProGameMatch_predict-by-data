import pandas as pd

from propredict.etl.sides import in_first_half_side, infer_first_half_attacker, team_a_side
from tests.etl.factories import win_loss

KEY = ("T", "S", "MT", "A vs B", "Ascent")


def test_half_and_overtime_rule():
    r = pd.Series([1, 12, 13, 24, 25, 26, 27])
    # 전반=같음, 후반=교대, 연장은 25R이 전반과 같고 이후 매 라운드 교대
    assert in_first_half_side(r).tolist() == [True, True, False, False, True, False, True]


def test_detonation_in_first_half_identifies_attacker():
    wl = win_loss([(1, "Alpha", "Detonated"), (2, "Bravo", "Elimination")])
    assert infer_first_half_attacker(wl).loc[KEY] == "Alpha"


def test_defuse_in_second_half_is_converted_back_to_first_half():
    # 14R에 Alpha가 해체로 이김 → 후반 Alpha 수비 → 후반 공격 Bravo → 전반 공격은 Alpha
    wl = win_loss([(1, "Bravo", "Elimination"), (14, "Alpha", "Defused")])
    assert infer_first_half_attacker(wl).loc[KEY] == "Alpha"


def test_overtime_round_votes_with_parity():
    # 26R(교대된 쪽)에서 Bravo가 설치 없이 시간 종료로 이김 → Bravo 수비 → Alpha 공격 → 전반 공격은 Bravo
    wl = win_loss([(26, "Bravo", "Time Expiry (No Plant)")])
    assert infer_first_half_attacker(wl).loc[KEY] == "Alpha"


def test_elimination_only_map_is_unknown():
    wl = win_loss([(1, "Alpha", "Elimination"), (13, "Bravo", "Elimination")])
    assert KEY not in infer_first_half_attacker(wl).index


def test_conflicting_votes_yield_null_not_a_guess():
    # 1R 폭발(Alpha 공격)과 2R 해체(Alpha 수비)는 같은 하프에서 동시에 성립할 수 없다
    wl = win_loss([(1, "Alpha", "Detonated"), (2, "Alpha", "Defused")])
    assert pd.isna(infer_first_half_attacker(wl).loc[KEY])


def test_team_a_side_per_round():
    r = pd.Series([1, 13, 25, 26])
    side = team_a_side(r, pd.Series(["Alpha"] * 4), pd.Series(["Alpha"] * 4, dtype="string"))
    assert side.tolist() == ["atk", "def", "atk", "def"]
    unknown = team_a_side(r, pd.Series(["Alpha"] * 4), pd.Series([pd.NA] * 4, dtype="string"))
    assert unknown.isna().all()
