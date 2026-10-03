"""GET /api/stats/buy-matrix, GET /api/stats/map-balance — DB 집계 통계."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from propredict.api.schemas import BuyCell, BuyMatrixResponse, MapBalance
from propredict.db import get_session
from propredict.etl.normalize import BUY_TYPES

router = APIRouter(prefix="/api/stats", tags=["stats"])

# 각 라운드를 두 팀 관점에서 한 번씩 센다. 그래서 매트릭스가 대칭이 되고(대각선 = 정확히 50%),
# 'A/B 중 누가 A였나'라는 데이터 수집 순서에 결과가 좌우되지 않는다.
_BUY_MATRIX_SQL = text("""
    WITH r AS (
        SELECT r.team_a_buy_type, r.team_b_buy_type, r.winner
        FROM rounds r JOIN map_games g USING (map_game_id) JOIN matches m USING (match_id)
        WHERE r.team_a_buy_type IS NOT NULL AND r.team_b_buy_type IS NOT NULL
          AND (CAST(:map AS TEXT) IS NULL OR g.map_name = :map)
          AND (CAST(:season AS SMALLINT) IS NULL OR m.season = :season)
    ), both_sides AS (
        SELECT team_a_buy_type AS team_buy, team_b_buy_type AS opp_buy, (winner = 'A')::int AS won FROM r
        UNION ALL
        SELECT team_b_buy_type, team_a_buy_type, (winner = 'B')::int FROM r
    )
    SELECT team_buy, opp_buy, avg(won) AS win_rate, count(*) AS n FROM both_sides GROUP BY 1, 2
""")


@router.get("/buy-matrix", response_model=BuyMatrixResponse)
def buy_matrix(map: str | None = None, season: int | None = None,
               session: Session = Depends(get_session)) -> BuyMatrixResponse:  # fmt: skip
    rows = {(r.team_buy, r.opp_buy): r for r in session.execute(_BUY_MATRIX_SQL, {"map": map, "season": season})}
    cells = []
    for team in BUY_TYPES:
        for opp in BUY_TYPES:
            r = rows.get((team, opp))
            cells.append(BuyCell(team_buy=team, opponent_buy=opp, count=int(r.n) if r else 0,
                                 win_rate=round(float(r.win_rate), 4) if r else None))  # fmt: skip
    # 두 관점으로 셌으므로 실제 라운드 수는 합의 절반
    return BuyMatrixResponse(buy_types=list(BUY_TYPES), cells=cells, rounds=sum(c.count for c in cells) // 2,
                             map=map, season=season)  # fmt: skip


@router.get("/map-balance", response_model=list[MapBalance])
def map_balance(season: int | None = None, session: Session = Depends(get_session)) -> list[MapBalance]:
    rows = (
        session.execute(
            text("""
        SELECT g.map_name,
               count(DISTINCT g.map_game_id) AS map_games,
               count(*) AS rounds,
               count(r.team_a_side) AS side_known_rounds,
               avg(((r.winner = 'A') = (r.team_a_side = 'atk'))::int) FILTER (WHERE r.team_a_side IS NOT NULL)
                   AS attacker_win_rate,
               count(*)::float / count(DISTINCT g.map_game_id) AS avg_rounds_per_map
        FROM rounds r JOIN map_games g USING (map_game_id) JOIN matches m USING (match_id)
        WHERE CAST(:season AS SMALLINT) IS NULL OR m.season = :season
        GROUP BY g.map_name ORDER BY map_games DESC"""),
            {"season": season},
        )
        .mappings()
        .all()
    )
    return [MapBalance(**{**r, "attacker_win_rate": None if r["attacker_win_rate"] is None
                          else round(float(r["attacker_win_rate"]), 4),
                          "avg_rounds_per_map": round(float(r["avg_rounds_per_map"]), 2)}) for r in rows]  # fmt: skip
