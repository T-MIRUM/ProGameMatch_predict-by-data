"""원본 DataFrame → matches / map_games / rounds 테이블 모양으로 변환 (DB 접근 없음).

핵심 결정 (docs/decisions.md D4, D6):
- 라운드 뼈대는 win_loss(모든 맵·모든 라운드)로 만든다. eco_rounds는 맵의 일부만 있으므로
  뼈대로 쓰면 스코어·연승 같은 맥락 피처가 틀어진다. eco 값은 뼈대에 '붙인다'(없으면 NULL).
- 모호한 데이터는 고치지 않고 제외하며, 무엇을 몇 건 제외했는지 report에 남긴다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from propredict.etl.normalize import normalize_tournament, parse_money, validate_buy_type
from propredict.etl.sides import infer_first_half_attacker, team_a_side
from propredict.etl.sources import MAP_KEY, MATCH_KEY, ROUND_KEY, SeasonFrames

# 원본 컬럼명 → DB 컬럼명
_KEY_RENAME = {
    "Tournament": "tournament",
    "Stage": "stage",
    "Match Type": "match_type",
    "Match Name": "match_name",
    "Map": "map_name",
    "Round Number": "round_number",
}
MATCH_NK = ["season", "tournament", "stage", "match_type", "match_name"]  # DB 자연키
MAP_NK = MATCH_NK + ["map_name"]
ROUND_NK = MAP_NK + ["round_number"]
INT_ROUND_COLS = ["round_number", "team_a_loadout", "team_b_loadout", "team_a_credits", "team_b_credits"]


@dataclass
class TransformResult:
    matches: pd.DataFrame
    map_games: pd.DataFrame
    rounds: pd.DataFrame
    report: dict[str, int] = field(default_factory=dict)


def _ambiguous_match_keys(scores: pd.DataFrame, ids: pd.DataFrame) -> pd.MultiIndex:
    """한 복합키에 서로 다른 경기가 둘 이상 대응하는 키.

    예: 2021 'No Country vs Sengoku Gaming'은 같은 대회·스테이지·조에서 두 번 열렸다(Match ID 2개).
    eco/win_loss에는 Match ID가 없어서 두 경기의 라운드를 가를 수 없으므로 키 전체를 제외한다.
    """
    by_ids = ids.groupby(MATCH_KEY)["Match ID"].nunique()
    by_scores = scores.drop_duplicates().groupby(MATCH_KEY).size()
    bad = set(by_ids[by_ids > 1].index) | set(by_scores[by_scores > 1].index)
    return pd.MultiIndex.from_tuples(sorted(bad), names=MATCH_KEY)


def _drop_keys(df: pd.DataFrame, keys: pd.MultiIndex) -> pd.DataFrame:
    if len(keys) == 0:
        return df
    return df[~pd.MultiIndex.from_frame(df[MATCH_KEY]).isin(keys)]


def _well_formed_maps(df: pd.DataFrame, has_winner: bool = True) -> pd.Index:
    """라운드마다 정확히 2행(팀별)이고 승자가 정확히 1명인 맵만 통과."""
    g = df.groupby(ROUND_KEY)
    ok = g.size() == 2
    if has_winner:
        ok &= g["Outcome"].agg(lambda s: (s == "Win").sum()) == 1
    per_map = ok.groupby(level=MAP_KEY).all()
    return per_map[per_map].index


def _restrict(df: pd.DataFrame, maps: pd.Index) -> pd.DataFrame:
    return df[pd.MultiIndex.from_frame(df[MAP_KEY]).isin(maps)]


def transform_season(f: SeasonFrames) -> TransformResult:
    rep: dict[str, int] = {}

    # ---------- matches ----------
    ambiguous = _ambiguous_match_keys(f.scores, f.ids)
    rep["match_keys_excluded_ambiguous"] = len(ambiguous)
    scores = _drop_keys(f.scores.drop_duplicates(), ambiguous)
    source_ids = f.ids.groupby(MATCH_KEY)["Match ID"].first()
    matches = scores.join(source_ids.rename("source_match_id"), on=MATCH_KEY)
    matches = matches.rename(
        columns={
            **_KEY_RENAME,
            "Team A": "team_a",
            "Team B": "team_b",
            "Team A Score": "score_a",
            "Team B Score": "score_b",
        }
    ).assign(season=f.season)
    matches = matches[MATCH_NK + ["team_a", "team_b", "score_a", "score_b", "source_match_id"]]
    teams = scores.set_index(MATCH_KEY)[["Team A", "Team B"]]

    # ---------- rounds 뼈대: win_loss ----------
    wl = _drop_keys(f.win_loss.drop_duplicates(), ambiguous)
    wl = wl[pd.MultiIndex.from_frame(wl[MATCH_KEY]).isin(teams.index)]
    good_maps = _well_formed_maps(wl)
    rep["maps_excluded_malformed"] = wl.groupby(MAP_KEY).ngroups - len(good_maps)
    wl = _restrict(wl, good_maps)

    # 팀 이름이 scores의 Team A/B와 일치하지 않으면 A/B를 정할 수 없으므로 제외 (감사 기준 0건)
    wl = wl.join(teams, on=MATCH_KEY)
    team_ok = (wl["Team"] == wl["Team A"]) | (wl["Team"] == wl["Team B"])
    bad_maps = wl.loc[~team_ok, MAP_KEY].drop_duplicates()
    rep["maps_excluded_team_mismatch"] = len(bad_maps)
    if len(bad_maps):
        wl = _restrict(
            wl, pd.MultiIndex.from_frame(wl[MAP_KEY]).drop_duplicates().difference(pd.MultiIndex.from_frame(bad_maps))
        )

    win = wl[wl["Outcome"] == "Win"]
    rounds = win[ROUND_KEY + ["Team A"]].copy()
    rounds["winner"] = (win["Team"] == win["Team A"]).map({True: "A", False: "B"})
    rounds["win_method"] = win["Method"]

    # ---------- 진영 ----------
    h1 = infer_first_half_attacker(wl)
    rounds = rounds.join(h1.rename("h1_attacker"), on=MAP_KEY)
    rounds["team_a_side"] = team_a_side(rounds["Round Number"], rounds["Team A"], rounds["h1_attacker"])
    rep["maps_side_known"] = int(h1.notna().sum())

    # ---------- 이코노미 붙이기 ----------
    eco = f.eco.assign(Tournament=normalize_tournament(f.eco["Tournament"])).drop_duplicates()
    eco = _drop_keys(eco, ambiguous)
    eco = _restrict(eco, _well_formed_maps(eco))
    eco = eco.join(teams, on=MATCH_KEY, how="inner")
    eco["loadout"] = parse_money(eco["Loadout Value"])
    eco["credits"] = parse_money(eco["Remaining Credits"])
    eco["buy_type"] = validate_buy_type(eco["Type"])
    side_ab = pd.Series(pd.NA, index=eco.index, dtype="string")
    side_ab[eco["Team"] == eco["Team A"]] = "a"
    side_ab[eco["Team"] == eco["Team B"]] = "b"
    eco = eco.assign(ab=side_ab).dropna(subset=["ab"])
    # pivot_table(dropna=False)는 인덱스 레벨의 데카르트 곱을 만들어 메모리가 폭증하므로,
    # 팀별로 잘라 라운드 키로 조인하는 방식으로 '팀별 2행 → 라운드 1행' 피벗을 한다.
    cols = ["loadout", "credits", "buy_type"]
    a = eco[eco["ab"] == "a"].set_index(ROUND_KEY)[cols].add_prefix("team_a_")
    b = eco[eco["ab"] == "b"].set_index(ROUND_KEY)[cols].add_prefix("team_b_")
    # 두 팀 모두 있어야 비교 피처가 의미 있으므로 inner join (한쪽만 있는 라운드는 이코노미 NULL)
    wide = a.join(b, how="inner")
    rounds = rounds.join(wide, on=ROUND_KEY)
    rep["rounds_with_economy"] = int(rounds["team_a_buy_type"].notna().sum())

    # eco의 승패와 win_loss의 승패가 다른 라운드 수 (라벨은 win_loss를 신뢰)
    eco_win = eco[eco["Outcome"] == "Win"].set_index(ROUND_KEY)["ab"].str.upper()
    cmp = rounds.set_index(ROUND_KEY)["winner"].to_frame().join(eco_win.rename("eco_winner"), how="inner")
    rep["rounds_outcome_disagree_eco"] = int((cmp["winner"] != cmp["eco_winner"]).sum())

    rounds = rounds.rename(columns=_KEY_RENAME).assign(season=f.season)
    rounds = (
        rounds[
            ROUND_NK
            + [
                "team_a_side",
                "team_a_loadout",
                "team_b_loadout",
                "team_a_credits",
                "team_b_credits",
                "team_a_buy_type",
                "team_b_buy_type",
                "winner",
                "win_method",
            ]
        ]
        .sort_values(ROUND_NK, kind="stable")
        .reset_index(drop=True)
    )

    # ---------- map_games ----------
    agg = rounds.groupby(MAP_NK).agg(
        total_rounds=("round_number", "size"),
        score_a=("winner", lambda s: int((s == "A").sum())),
        score_b=("winner", lambda s: int((s == "B").sum())),
    )
    # 경기 내 맵 순서: 원본에 명시 컬럼이 없어 Game ID 오름차순을 쓴다. 같은 맵이 Game ID 2개로
    # 중복 수집된 경우(2021 19건 등)는 작은 ID를 대표로 쓴다.
    game = f.ids.groupby(MAP_KEY)["Game ID"].min()
    game.index = game.index.set_names([_KEY_RENAME[k] for k in MAP_KEY])
    game = game.to_frame("source_game_id").assign(season=f.season).set_index("season", append=True)
    game = game.reorder_levels(MAP_NK)
    map_games = agg.join(game, how="left").reset_index()
    map_games["map_order"] = map_games.groupby(MATCH_NK)["source_game_id"].rank(method="first").astype("Int64")
    first_side = rounds[rounds["round_number"] == 1].set_index(MAP_NK)["team_a_side"].rename("team_a_first_half_side")
    map_games = map_games.join(first_side, on=MAP_NK)

    # 라운드가 하나도 남지 않은 경기는 matches에서도 뺀다 (예측·리플레이 대상이 아님)
    used = map_games[MATCH_NK].drop_duplicates()
    rep["matches_without_rounds"] = len(matches) - len(used)
    matches = matches.merge(used, on=MATCH_NK, how="inner")

    # 조인·집계를 거치며 결측이 섞인 정수 컬럼은 pandas가 float로 바꾼다(52936 → 52936.0).
    # DB의 INTEGER 컬럼에 그대로 넣으면 실패하므로, nullable 정수형(Int64)으로 명시해 되돌린다.
    matches = matches.astype({c: "Int64" for c in ["score_a", "score_b", "source_match_id"]})
    map_games = map_games.astype(
        {c: "Int64" for c in ["source_game_id", "map_order", "total_rounds", "score_a", "score_b"]}
    )
    rounds = rounds.astype({c: "Int64" for c in INT_ROUND_COLS})

    rep.update(matches=len(matches), map_games=len(map_games), rounds=len(rounds))
    return TransformResult(matches=matches, map_games=map_games, rounds=rounds, report=rep)
