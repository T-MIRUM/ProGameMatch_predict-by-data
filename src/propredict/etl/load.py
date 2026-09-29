"""PostgreSQL 멱등 적재.

설계 (docs/decisions.md D10):
- 시즌 단위 '동기화'. 한 트랜잭션 안에서 스테이징 테이블에 COPY → 본 테이블에 upsert → 원본에서 사라진 행 삭제.
  중간에 실패하면 시즌 전체가 롤백되어 반쯤 적재된 상태가 남지 않는다.
- DELETE 후 전부 다시 INSERT하지 않고 upsert하는 이유: 대리키(match_id 등)를 재실행 후에도 그대로 유지하기 위해서다.
  API의 /api/matches/{match_id} 같은 URL이 ETL을 다시 돌릴 때마다 바뀌면 안 된다.
- ON CONFLICT DO UPDATE ... WHERE (값) IS DISTINCT FROM (새 값): 바뀐 게 없으면 갱신하지 않는다.
  그래서 같은 데이터로 두 번째 실행하면 inserted=0, updated=0, deleted=0이 되고, 이것이 곧 멱등성의 증거가 된다.
- 행 단위 INSERT 대신 COPY: 2021 시즌만 라운드 29만 행이라 executemany보다 한 자릿수 이상 빠르다.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sqlalchemy import Connection, text

from propredict.etl.transform import MAP_NK, MATCH_NK, ROUND_NK, TransformResult

MATCH_COLS = MATCH_NK + ["team_a", "team_b", "score_a", "score_b", "source_match_id"]
MAP_COLS = MAP_NK + ["source_game_id", "map_order", "total_rounds", "score_a", "score_b", "team_a_first_half_side"]
ROUND_COLS = ROUND_NK + [
    "team_a_side", "team_a_loadout", "team_b_loadout", "team_a_credits", "team_b_credits",
    "team_a_buy_type", "team_b_buy_type", "winner", "win_method",
]  # fmt: skip


@dataclass
class TableStats:
    inserted: int = 0
    updated: int = 0
    deleted: int = 0


def _copy(conn: Connection, table: str, df: pd.DataFrame, cols: list[str]) -> None:
    """DataFrame을 COPY로 스테이징 테이블에 밀어 넣는다. pandas 결측(<NA>, NaN)은 SQL NULL로 바꾼다."""
    raw = conn.connection.driver_connection  # psycopg 3 Connection
    frame = df[cols].astype(object).where(df[cols].notna(), None)
    with raw.cursor() as cur, cur.copy(f"COPY {table} ({', '.join(cols)}) FROM STDIN") as cp:
        for row in frame.itertuples(index=False, name=None):
            cp.write_row(row)


def _upsert_sql(target: str, cols: list[str], conflict: list[str], select_from: str) -> str:
    """스테이징 → 본 테이블 upsert. 값이 실제로 달라진 행만 UPDATE한다.

    RETURNING (xmax = 0): PostgreSQL에서 새로 INSERT된 행은 xmax가 0이다. 이것으로 insert/update를 구분해 센다.
    """
    upd = [c for c in cols if c not in conflict]
    set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in upd)
    changed = (
        f"({', '.join(f'{target}.{c}' for c in upd)}) IS DISTINCT FROM ({', '.join(f'EXCLUDED.{c}' for c in upd)})"
    )
    return (
        f"INSERT INTO {target} ({', '.join(cols)}) {select_from} "
        f"ON CONFLICT ({', '.join(conflict)}) DO UPDATE SET {set_clause} WHERE {changed} "
        f"RETURNING (xmax = 0) AS inserted"
    )


def _count(rows) -> TableStats:
    flags = [r.inserted for r in rows]
    return TableStats(inserted=sum(flags), updated=len(flags) - sum(flags))


def load_season(conn: Connection, season: int, res: TransformResult) -> dict[str, TableStats]:
    """한 시즌을 동기화한다. 호출자가 연 트랜잭션(conn) 안에서 실행된다."""
    stats: dict[str, TableStats] = {}

    # 스테이징: 세션 임시 테이블. ON COMMIT DROP이라 정리 코드가 필요 없다.
    conn.execute(
        text(f"""
        CREATE TEMP TABLE stg_matches ON COMMIT DROP AS
            SELECT {", ".join(MATCH_COLS)} FROM matches WITH NO DATA;
        CREATE TEMP TABLE stg_map_games (
            season SMALLINT, tournament TEXT, stage TEXT, match_type TEXT, match_name TEXT, map_name TEXT,
            source_game_id INT, map_order SMALLINT, total_rounds SMALLINT, score_a SMALLINT, score_b SMALLINT,
            team_a_first_half_side VARCHAR(3)) ON COMMIT DROP;
        CREATE TEMP TABLE stg_rounds (
            season SMALLINT, tournament TEXT, stage TEXT, match_type TEXT, match_name TEXT, map_name TEXT,
            round_number SMALLINT, team_a_side VARCHAR(3), team_a_loadout INT, team_b_loadout INT,
            team_a_credits INT, team_b_credits INT, team_a_buy_type TEXT, team_b_buy_type TEXT,
            winner VARCHAR(1), win_method TEXT) ON COMMIT DROP;
    """)
    )
    _copy(conn, "stg_matches", res.matches, MATCH_COLS)
    _copy(conn, "stg_map_games", res.map_games, MAP_COLS)
    _copy(conn, "stg_rounds", res.rounds, ROUND_COLS)

    mk = " AND ".join(f"m.{c} = s.{c}" for c in MATCH_NK)

    # 1) matches
    rows = conn.execute(
        text(_upsert_sql("matches", MATCH_COLS, MATCH_NK, f"SELECT {', '.join(MATCH_COLS)} FROM stg_matches"))
    )
    stats["matches"] = _count(rows)

    # 2) map_games: 자연키로 match_id를 찾아 붙인다
    map_cols = [
        "match_id",
        "map_name",
        "source_game_id",
        "map_order",
        "total_rounds",
        "score_a",
        "score_b",
        "team_a_first_half_side",
    ]
    rows = conn.execute(
        text(
            _upsert_sql(
                "map_games",
                map_cols,
                ["match_id", "map_name"],
                f"SELECT m.match_id, {', '.join('s.' + c for c in map_cols[1:])} "
                f"FROM stg_map_games s JOIN matches m ON {mk}",
            )
        )
    )
    stats["map_games"] = _count(rows)

    # 3) rounds
    round_cols = ["map_game_id"] + ROUND_COLS[len(MAP_NK) :]
    rows = conn.execute(
        text(
            _upsert_sql(
                "rounds",
                round_cols,
                ["map_game_id", "round_number"],
                f"SELECT g.map_game_id, {', '.join('s.' + c for c in round_cols[1:])} "
                f"FROM stg_rounds s JOIN matches m ON {mk} JOIN map_games g ON g.match_id = m.match_id "
                f"AND g.map_name = s.map_name",
            )
        )
    )
    stats["rounds"] = _count(rows)

    # 4) 원본에서 사라진 행 삭제 (이 시즌 범위에서만). 하위 테이블부터 지워 삭제 건수를 테이블별로 센다.
    stats["rounds"].deleted = conn.execute(
        text(f"""
        DELETE FROM rounds r USING map_games g, matches m
        WHERE r.map_game_id = g.map_game_id AND g.match_id = m.match_id AND m.season = :season
          AND NOT EXISTS (SELECT 1 FROM stg_rounds s WHERE {mk} AND s.map_name = g.map_name
                          AND s.round_number = r.round_number)"""),
        {"season": season},
    ).rowcount
    stats["map_games"].deleted = conn.execute(
        text(f"""
        DELETE FROM map_games g USING matches m
        WHERE g.match_id = m.match_id AND m.season = :season
          AND NOT EXISTS (SELECT 1 FROM stg_map_games s WHERE {mk} AND s.map_name = g.map_name)"""),
        {"season": season},
    ).rowcount
    stats["matches"].deleted = conn.execute(
        text(f"""
        DELETE FROM matches m WHERE m.season = :season
          AND NOT EXISTS (SELECT 1 FROM stg_matches s WHERE {mk})"""),
        {"season": season},
    ).rowcount
    return stats
