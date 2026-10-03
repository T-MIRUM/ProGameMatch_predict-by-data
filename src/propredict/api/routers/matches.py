"""GET /api/matches (경기 선택용 목록), GET /api/matches/{match_id}/rounds (리플레이).

목록 엔드포인트는 명세 §6에 없지만, 화면 3 '실제 경기 하나를 골라'를 구현하려면 고를 목록이 필요해서 추가했다.
"""

from __future__ import annotations

import math

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from propredict.api.deps import get_model
from propredict.api.schemas import MatchRoundsResponse, MatchSummary, ReplayMap, ReplayRound
from propredict.api.service import ModelService
from propredict.db import get_session
from propredict.ml.dataset import CHRONO_ORDER

router = APIRouter(prefix="/api/matches", tags=["matches"])

_SUMMARY_SQL = """
    SELECT m.match_id, m.season, m.tournament, m.stage, m.match_type, m.team_a, m.team_b, m.score_a, m.score_b,
           count(DISTINCT g.map_game_id) AS maps, count(r.team_a_buy_type) AS economy_rounds
    FROM matches m JOIN map_games g USING (match_id) LEFT JOIN rounds r USING (map_game_id)
"""


@router.get("", response_model=list[MatchSummary])
def list_matches(
    season: int | None = None,
    team: str | None = Query(None, min_length=1, max_length=50),
    limit: int = Query(30, ge=1, le=200),
    session: Session = Depends(get_session),
) -> list[MatchSummary]:
    rows = (
        session.execute(
            text(
                _SUMMARY_SQL
                + """
        WHERE (CAST(:season AS SMALLINT) IS NULL OR m.season = :season)
          AND (CAST(:team AS TEXT) IS NULL OR m.team_a ILIKE '%' || :team || '%' OR m.team_b ILIKE '%' || :team || '%')
        GROUP BY m.match_id
        -- 리플레이에 의미 있는(이코노미가 있는) 최신 경기를 먼저 보여 준다
        ORDER BY (count(r.team_a_buy_type) > 0) DESC, m.season DESC, m.source_match_id DESC NULLS LAST
        LIMIT :limit"""
            ),
            {"season": season, "team": team, "limit": limit},
        )
        .mappings()
        .all()
    )
    return [MatchSummary(**r) for r in rows]


def _none(v):
    """pandas 결측(NaN/NA)을 JSON null로."""
    return None if v is None or (isinstance(v, float) and math.isnan(v)) or v is pd.NA else v


@router.get("/{match_id}/rounds", response_model=MatchRoundsResponse)
def match_rounds(match_id: int, session: Session = Depends(get_session),
                 model: ModelService = Depends(get_model)) -> MatchRoundsResponse:  # fmt: skip
    summary = session.execute(text(_SUMMARY_SQL + " WHERE m.match_id = :id GROUP BY m.match_id"),
                              {"id": match_id}).mappings().first()  # fmt: skip
    if summary is None:
        raise HTTPException(status_code=404, detail=f"경기 {match_id}를 찾을 수 없습니다")
    rounds = pd.read_sql(
        text("""
        SELECT m.match_id, m.season, m.source_match_id, m.team_a, m.team_b,
               g.map_game_id, g.map_name, g.map_order, g.score_a AS map_score_a, g.score_b AS map_score_b,
               r.round_number, r.team_a_side, r.team_a_loadout, r.team_b_loadout, r.team_a_credits, r.team_b_credits,
               r.team_a_buy_type, r.team_b_buy_type, r.winner
        FROM rounds r JOIN map_games g USING (map_game_id) JOIN matches m USING (match_id)
        WHERE m.match_id = :id"""),
        session.connection(),
        params={"id": match_id},
    )
    num = ["team_a_loadout", "team_b_loadout", "team_a_credits", "team_b_credits", "source_match_id", "map_order"]
    rounds[num] = rounds[num].astype("Float64").astype(float)
    rounds = rounds.sort_values(CHRONO_ORDER, kind="stable", na_position="last").reset_index(drop=True)
    scored = model.replay(rounds)
    a_str, b_str = scored.attrs["strength"]

    maps = []
    for (mg_id, name), g in scored.groupby(["map_game_id", "map_name"], sort=False):
        first = g.iloc[0]
        maps.append(ReplayMap(
            map_game_id=int(mg_id), map_name=name,
            map_order=None if pd.isna(first["map_order"]) else int(first["map_order"]),
            score_a=_none(first["map_score_a"]), score_b=_none(first["map_score_b"]),
            rounds=[ReplayRound(
                round_number=int(r.round_number), score_a=int(r.score_a), score_b=int(r.score_b),
                team_a_side=_none(r.team_a_side), team_a_buy_type=_none(r.team_a_buy_type),
                team_b_buy_type=_none(r.team_b_buy_type),
                team_a_loadout=None if pd.isna(r.team_a_loadout) else int(r.team_a_loadout),
                team_b_loadout=None if pd.isna(r.team_b_loadout) else int(r.team_b_loadout),
                winner=r.winner,
                win_probability_a=None if pd.isna(r.win_probability_a) else round(float(r.win_probability_a), 4),
                baseline_probability_a=_none(r.baseline_probability_a), upset=bool(r.upset),
            ) for r in g.itertuples()],
        ))  # fmt: skip
    return MatchRoundsResponse(match=MatchSummary(**summary), team_a_strength=round(a_str, 4),
                               team_b_strength=round(b_str, 4), maps=maps)  # fmt: skip
