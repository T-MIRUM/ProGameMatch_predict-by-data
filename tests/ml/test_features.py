import numpy as np
import pandas as pd
import pytest

from propredict.ml.features import FEATURES, NUMERIC_FEATURES, build_features, flip_ab, state_features
from tests.ml.factories import rounds


def sample():
    return build_features(rounds([{"match_id": 1, "team_a": "A", "team_b": "B", "winners": "ABBAAAB"}]))


def test_flip_twice_is_identity():
    X = sample()[FEATURES]
    X2 = flip_ab(flip_ab(X))
    pd.testing.assert_frame_equal(X[NUMERIC_FEATURES], X2[NUMERIC_FEATURES], check_exact=False, atol=1e-12)
    assert (X[["buy_matchup", "map_side"]] == X2[["buy_matchup", "map_side"]]).all().all()


def test_flip_swaps_perspective():
    F = sample()
    X, y = F[FEATURES], F["y"]
    Xf, yf = flip_ab(X, y)
    assert (yf == 1 - y).all()
    assert (Xf["team_a_loadout"] == X["team_b_loadout"]).all()
    assert (Xf["score_diff"] == -X["score_diff"]).all()
    assert (Xf["buy_matchup"] == "0v3").all() and (X["buy_matchup"] == "3v0").all()
    assert (Xf["map_side"].str.endswith("|def") == X["map_side"].str.endswith("|atk")).all()


def api_state(**over):
    base = {
        "map_name": "Ascent", "round_number": 14, "score_a": 7, "score_b": 6, "team_a_side": "atk",
        "team_a_loadout": 24500, "team_b_loadout": 3900, "team_a_credits": 2100, "team_b_credits": 400,
        "team_a_buy_type": "Full buy: 20k+", "team_b_buy_type": "Eco: 0-5k",
        "prev_a_won": np.nan, "streak": 0.0, "last3_a_winrate": np.nan,
        "team_a_strength": 0.5, "team_b_strength": 0.5,
    }  # fmt: skip
    return pd.DataFrame([{**base, **over}])


def test_state_features_work_for_a_single_api_request():
    # 명세 §6 예시 요청과 같은 값 — 학습과 서빙이 같은 함수를 쓴다
    X = state_features(api_state())
    assert list(X.columns) == FEATURES
    row = X.iloc[0]
    assert row["loadout_diff"] == 20600 and row["loadout_share"] == pytest.approx(24500 / 28400)
    assert (row["half"], row["is_pistol"], row["score_diff"], row["side_a_atk"]) == (2, 0, 1, 1)
    assert (row["buy_matchup"], row["map_side"]) == ("3v0", "Ascent|atk")


def test_missing_loadout_and_side_become_nan_not_zero():
    # 2026년처럼 장비가치가 없을 때 0으로 채우면 '장비 0원'이라는 거짓 정보가 된다
    row = state_features(api_state(team_a_loadout=None, team_b_loadout=None, team_a_side=None)).iloc[0]
    assert np.isnan(row["loadout_diff"]) and np.isnan(row["loadout_share"]) and np.isnan(row["side_a_atk"])
    assert row["map_side"] == "Ascent|unk"


def test_overtime_half_code():
    assert state_features(api_state(round_number=25)).iloc[0]["half"] == 3
    assert state_features(api_state(round_number=13)).iloc[0]["is_pistol"] == 1
