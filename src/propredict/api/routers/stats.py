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
# 성능: 처음엔 SQL에서 UNION ALL로 행을 두 배로 복제한 뒤 집계했는데(42만 → 84만 행) 4.0초가 걸렸다.
# (A구매, B구매)로 한 번만 집계하면 최대 16행이 되고, 대칭 처리는 Python에서 해도 같은 결과다 → 0.2초.
_BUY_MATRIX_SQL = text("""
    SELECT r.team_a_buy_type AS a, r.team_b_buy_type AS b, count(*) AS n, sum((r.winner = 'A')::int) AS a_wins
    FROM rounds r JOIN map_games g USING (map_game_id) JOIN matches m USING (match_id)
    WHERE r.team_a_buy_type IS NOT NULL AND r.team_b_buy_type IS NOT NULL
      AND (CAST(:map AS TEXT) IS NULL OR g.map_name = :map)
      AND (CAST(:season AS SMALLINT) IS NULL OR m.season = :season)
    GROUP BY 1, 2
""")


def mirror_counts(rows) -> dict[tuple[str, str], tuple[int, int]]:
    """(A구매, B구매, 라운드 수, A 승수) → (내 구매, 상대 구매)별 (라운드 수, 내 승수). 두 관점을 합친다."""
    cells: dict[tuple[str, str], tuple[int, int]] = {}
    for a, b, n, a_wins in rows:
        for key, wins in (((a, b), a_wins), ((b, a), n - a_wins)):
            prev_n, prev_w = cells.get(key, (0, 0))
            cells[key] = (prev_n + int(n), prev_w + int(wins))
    return cells


@router.get("/buy-matrix", response_model=BuyMatrixResponse)
def buy_matrix(map: str | None = None, season: int | None = None,
               session: Session = Depends(get_session)) -> BuyMatrixResponse:  # fmt: skip
    counts = mirror_counts(session.execute(_BUY_MATRIX_SQL, {"map": map, "season": season}).all())
    cells = []
    for team in BUY_TYPES:
        for opp in BUY_TYPES:
            n, wins = counts.get((team, opp), (0, 0))
            cells.append(BuyCell(team_buy=team, opponent_buy=opp, count=n,
                                 win_rate=round(wins / n, 4) if n else None))  # fmt: skip
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
