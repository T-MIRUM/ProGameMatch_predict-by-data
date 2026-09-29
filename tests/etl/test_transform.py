import pandas as pd

from propredict.etl.sources import SeasonFrames
from propredict.etl.transform import transform_season
from tests.etl import factories as f


def season(scores=None, ids=None, wl=None, eco=None, year=2021) -> SeasonFrames:
    return SeasonFrames(
        season=year,
        scores=scores if scores is not None else f.scores(),
        ids=ids if ids is not None else f.ids(),
        win_loss=wl if wl is not None else f.win_loss([(1, "Alpha", "Detonated"), (2, "Bravo", "Elimination")]),
        eco=eco if eco is not None else f.eco([]),
    )


ECO_R1 = [
    (1, "Alpha", "3.9k", "0.4k", "Eco: 0-5k", "Win"),
    (1, "Bravo", "24.5k", "2.1k", "Full buy: 20k+", "Loss"),
]


def test_team_rows_are_pivoted_to_one_row_per_round():
    res = transform_season(season(eco=f.eco(ECO_R1)))
    r1 = res.rounds.set_index("round_number").loc[1]
    assert (r1.team_a_loadout, r1.team_b_loadout) == (3900, 24500)
    assert (r1.team_a_credits, r1.team_b_credits) == (400, 2100)
    assert (r1.team_a_buy_type, r1.team_b_buy_type) == ("Eco: 0-5k", "Full buy: 20k+")
    assert r1.winner == "A"


def test_round_skeleton_comes_from_win_loss_even_without_economy():
    # 2R은 eco에 없지만 스코어·연승 계산을 위해 라운드 자체는 남아야 한다
    res = transform_season(season(eco=f.eco(ECO_R1)))
    assert res.rounds["round_number"].tolist() == [1, 2]
    r2 = res.rounds.set_index("round_number").loc[2]
    assert pd.isna(r2.team_a_buy_type) and r2.winner == "B"


def test_sides_are_filled_from_decisive_round():
    res = transform_season(season())
    # 1R Alpha 폭발 승 → Alpha(=Team A) 전반 공격
    assert res.rounds["team_a_side"].tolist() == ["atk", "atk"]
    assert res.map_games.loc[0, "team_a_first_half_side"] == "atk"


def test_ambiguous_match_key_is_excluded_entirely():
    two_matches = pd.concat([f.ids(match_id=1), f.ids(match_id=2, first_game_id=2000)])
    res = transform_season(season(ids=two_matches))
    assert res.rounds.empty and res.matches.empty
    assert res.report["match_keys_excluded_ambiguous"] == 1


def test_exact_duplicate_rows_are_dropped():
    wl = f.win_loss([(1, "Alpha", "Detonated")])
    res = transform_season(season(wl=pd.concat([wl, wl]), eco=f.eco(ECO_R1 + ECO_R1)))
    assert len(res.rounds) == 1
    assert res.rounds.loc[0, "team_a_loadout"] == 3900


def test_map_games_aggregate_scores_and_order_by_game_id():
    wl = pd.concat(
        [
            f.win_loss([(1, "Alpha", "Elimination"), (2, "Alpha", "Elimination")], map_name="Bind"),
            f.win_loss([(1, "Bravo", "Elimination")], map_name="Ascent"),
        ]
    )
    ids = f.ids(maps=("Bind", "Ascent"))  # Bind의 Game ID가 더 작다 → 1번째 맵
    mg = transform_season(season(wl=wl, ids=ids)).map_games.set_index("map_name")
    assert (mg.loc["Bind", "score_a"], mg.loc["Bind", "score_b"], mg.loc["Bind", "total_rounds"]) == (2, 0, 2)
    assert (mg.loc["Bind", "map_order"], mg.loc["Ascent", "map_order"]) == (1, 2)


def test_2025_eco_tournament_alias_is_joined():
    key = {"Tournament": "VCT 2025: EMEA Kickoff"}
    sc, ids, wl = f.scores(), f.ids(), f.win_loss([(1, "Alpha", "Detonated")])
    for df in (sc, ids, wl):
        df["Tournament"] = key["Tournament"]
    eco = f.eco(ECO_R1)
    eco["Tournament"] = "Champions Tour 2025: EMEA Kickoff"
    res = transform_season(season(scores=sc, ids=ids, wl=wl, eco=eco, year=2025))
    assert res.rounds.loc[0, "team_a_buy_type"] == "Eco: 0-5k"


def test_integer_columns_stay_integer_after_joins():
    # 결측이 섞이면 pandas가 float로 바꿔 COPY가 "52936.0"을 INTEGER로 못 넣는다 (실데이터 적재 중 발견)
    ids = f.ids(maps=("Bind",))  # Ascent의 Game ID가 없어 source_game_id 결측이 생긴다
    res = transform_season(season(ids=ids, eco=f.eco(ECO_R1)))
    assert str(res.map_games["source_game_id"].dtype) == "Int64"
    assert str(res.matches["source_match_id"].dtype) == "Int64"
    for col in ("round_number", "team_a_loadout", "team_b_credits"):
        assert str(res.rounds[col].dtype) == "Int64"
