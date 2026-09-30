"""데이터 누수 방지 테스트 (명세 §5.3).

'미래 정보를 바꿔도 현재 피처는 변하지 않아야 한다'는 교란(perturbation) 방식으로 검증한다.
구현 세부가 바뀌어도 이 성질만 지키면 통과하므로, 리팩터링에 강한 테스트다.

이 테스트가 실제로 누수를 잡는지 뮤테이션으로 확인했다 (2026-09-30):
- 팀 강도 누적합에 현재 경기 포함          → 2개 실패
- 팀 강도를 시즌 전체 승률(미래 포함)로 변경 → 3개 실패
- 라운드 스코어에 현재 라운드 포함         → 3개 실패
"""

import numpy as np
import pandas as pd
import pytest

from propredict.ml.features import FEATURES, build_features, team_strength
from propredict.ml.split import split_by_season, split_matches
from tests.ml.factories import rounds

SEQ = ["score_a", "score_b", "prev_a_won", "streak", "last3_a_winrate"]


def three_matches(last_winners="AAAAA"):
    return rounds(
        [
            {"match_id": 1, "team_a": "Alpha", "team_b": "Bravo", "winners": "ABABA"},
            {"match_id": 2, "team_a": "Alpha", "team_b": "Charlie", "winners": "AAB"},
            {"match_id": 3, "team_a": "Bravo", "team_b": "Alpha", "winners": last_winners},
        ]
    )


# ---------------------------------------------------------------- 분할
def test_season_split_never_shares_a_match():
    df = pd.concat([
        rounds([{"match_id": i, "season": s, "team_a": "A", "team_b": "B", "winners": "AB"}])
        for i, s in enumerate([2021, 2022, 2023, 2024, 2025, 2026], start=1)
    ])  # fmt: skip
    parts = split_by_season(build_features(df))
    ids = {k: set(v["match_id"]) for k, v in parts.items()}
    names = list(ids)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            assert not ids[a] & ids[b], f"{a}와 {b}가 같은 경기를 공유"
    assert sum(len(v) for v in ids.values()) == 6


def test_valid_halves_are_split_by_match_not_by_round():
    df = rounds([{"match_id": i, "team_a": "A", "team_b": "B", "winners": "ABABAB"} for i in range(40)])
    es, cal = split_matches(df)
    assert set(es["match_id"]).isdisjoint(cal["match_id"])
    assert len(es) + len(cal) == len(df)


# ---------------------------------------------------------------- 팀 강도 (expanding window)
def test_team_strength_ignores_future_matches():
    base = team_strength(three_matches("AAAAA")).set_index("match_id")
    changed = team_strength(three_matches("BBBBB")).set_index("match_id")
    # 3번 경기 결과를 뒤집어도 그 이전 경기(1, 2)의 강도는 그대로여야 한다
    pd.testing.assert_frame_equal(base.loc[[1, 2]], changed.loc[[1, 2]])


def test_team_strength_excludes_the_current_match_itself():
    base = team_strength(three_matches("AAAAA")).set_index("match_id")
    changed = team_strength(three_matches("BBBBB")).set_index("match_id")
    # 3번 경기의 강도는 3번 경기 자신의 결과와 무관해야 한다 (시즌 전체 승률 같은 값이면 여기서 실패)
    pd.testing.assert_frame_equal(base.loc[[3]], changed.loc[[3]])


def test_first_appearance_gets_neutral_prior():
    s = team_strength(three_matches()).set_index("match_id")
    assert s.loc[1, "team_a_strength"] == pytest.approx(0.5)
    assert s.loc[2, "team_b_strength"] == pytest.approx(0.5)  # Charlie의 첫 경기


def test_team_strength_uses_chronological_order_not_row_order():
    df = three_matches()
    shuffled = df.sample(frac=1.0, random_state=0)
    a = team_strength(df).set_index("match_id").sort_index()
    b = team_strength(shuffled).set_index("match_id").sort_index()
    pd.testing.assert_frame_equal(a, b)


# ---------------------------------------------------------------- 라운드 시퀀스
@pytest.mark.parametrize("k", [1, 3, 5])
def test_round_features_do_not_see_current_or_future_rounds(k):
    base = rounds([{"match_id": 1, "team_a": "A", "team_b": "B", "winners": "ABAAB"}])
    changed = base.copy()
    flip = {"A": "B", "B": "A"}
    changed.loc[changed["round_number"] >= k, "winner"] = changed["winner"].map(flip)
    fa, fb = build_features(base), build_features(changed)
    upto = fa["round_number_key"] <= k
    # k번째 라운드부터 결과를 바꿔도 1..k 라운드의 피처는 같아야 한다 (라벨 y만 달라진다)
    pd.testing.assert_frame_equal(fa.loc[upto, SEQ], fb.loc[upto, SEQ])


def test_result_derived_columns_are_not_features():
    # win_method(승리 방식)와 winner는 라운드 '결과'라서 피처가 되면 누수다
    for banned in ["win_method", "winner", "y", "team_a_side_known"]:
        assert banned not in FEATURES


def test_no_feature_is_perfectly_correlated_with_label():
    df = rounds(
        [
            {
                "match_id": i,
                "team_a": "A",
                "team_b": "B",
                "winners": "".join(np.random.default_rng(i).choice(["A", "B"], 13)),
            }
            for i in range(30)
        ]
    )
    F = build_features(df)
    num = F[FEATURES].select_dtypes("number")
    num = num.loc[:, num.std() > 0]  # 상수 컬럼은 상관계수가 정의되지 않는다
    corr = num.corrwith(F["y"]).abs().dropna()
    assert (corr < 0.95).all(), corr[corr >= 0.95]
