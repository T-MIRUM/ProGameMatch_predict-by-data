"""GET /api/maps, GET /api/teams."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from propredict.api.schemas import MapInfo, MapsResponse, TeamInfo
from propredict.db import get_session

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/maps", response_model=MapsResponse)
def list_maps(session: Session = Depends(get_session)) -> MapsResponse:
    # 라운드 테이블(56만 행)을 조인하지 않고 ETL이 채운 map_games.total_rounds를 합산한다 (0.55초 → 수 ms)
    rows = (
        session.execute(
            text("""
        SELECT g.map_name AS name, count(*) AS map_games, coalesce(sum(g.total_rounds), 0) AS rounds,
               max(m.season) AS last_season
        FROM map_games g JOIN matches m USING (match_id)
        GROUP BY g.map_name ORDER BY map_games DESC""")
        )
        .mappings()
        .all()
    )
    seasons = session.execute(text("SELECT DISTINCT season FROM matches ORDER BY season")).scalars().all()
    return MapsResponse(maps=[MapInfo(**r) for r in rows], seasons=list(seasons))


@router.get("/teams", response_model=list[TeamInfo])
def search_teams(
    request: Request,
    season: int | None = None,
    q: str | None = Query(None, min_length=1, max_length=50, description="팀 이름 부분 검색(대소문자 무시)"),
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> list[TeamInfo]:
    rows = session.execute(text("""
        SELECT team AS name, count(*) AS matches, max(season) AS last_season FROM (
            SELECT team_a AS team, season FROM matches UNION ALL SELECT team_b, season FROM matches) t
        WHERE (CAST(:season AS SMALLINT) IS NULL OR season = :season)
          AND (CAST(:q AS TEXT) IS NULL OR team ILIKE '%' || :q || '%')
        GROUP BY team ORDER BY matches DESC, team LIMIT :limit"""),
        {"season": season, "q": q, "limit": limit}).mappings().all()  # fmt: skip
    model = getattr(request.app.state, "model", None)
    strengths = model.team_strength if model else {}
    return [TeamInfo(**r, strength=strengths.get(r["name"])) for r in rows]
