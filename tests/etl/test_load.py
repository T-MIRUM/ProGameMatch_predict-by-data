"""적재 멱등성 통합 테스트 (PostgreSQL 필요, 없으면 skip).

CI는 PostgreSQL 16 서비스에 `alembic upgrade head`를 적용한 뒤 이 테스트를 돌린다.
실데이터와 섞이지 않도록 존재하지 않는 시즌 번호(1999)를 쓰고, 끝나면 지운다.
"""

import pandas as pd
import pytest
from sqlalchemy import text

from propredict.db import get_engine
from propredict.etl.load import load_season
from propredict.etl.sources import SeasonFrames
from propredict.etl.transform import transform_season
from tests.etl import factories as f

SEASON = 1999
pytestmark = pytest.mark.db


@pytest.fixture
def engine():
    eng = get_engine()
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1 FROM rounds LIMIT 1"))
    except Exception as exc:  # DB가 없거나 마이그레이션 전이면 통합 테스트는 건너뛴다
        pytest.skip(f"PostgreSQL 사용 불가: {exc.__class__.__name__}")
    yield eng
    with eng.begin() as conn:
        conn.execute(text("DELETE FROM matches WHERE season = :s"), {"s": SEASON})


def frames(wl: pd.DataFrame, maps=("Ascent", "Bind")) -> SeasonFrames:
    return SeasonFrames(season=SEASON, scores=f.scores(), ids=f.ids(maps=maps), win_loss=wl, eco=f.eco([]))


WL = pd.concat(
    [
        f.win_loss([(1, "Alpha", "Detonated"), (2, "Bravo", "Elimination")], map_name="Ascent"),
        f.win_loss([(1, "Bravo", "Defused")], map_name="Bind"),
    ]
)


def run(engine, sf: SeasonFrames):
    with engine.begin() as conn:
        return load_season(conn, SEASON, transform_season(sf))


def ids(engine):
    with engine.connect() as conn:
        return conn.execute(
            text("""
            SELECT m.match_id, g.map_game_id, r.round_id FROM rounds r
            JOIN map_games g USING (map_game_id) JOIN matches m USING (match_id)
            WHERE m.season = :s ORDER BY r.round_id"""),
            {"s": SEASON},
        ).all()


def test_second_run_changes_nothing_and_keeps_surrogate_keys(engine):
    first = run(engine, frames(WL))
    assert (first["rounds"].inserted, first["map_games"].inserted, first["matches"].inserted) == (3, 2, 1)
    before = ids(engine)

    second = run(engine, frames(WL))
    for table, st in second.items():
        assert (st.inserted, st.updated, st.deleted) == (0, 0, 0), table
    # 대리키가 바뀌면 API URL(/api/matches/{id})이 ETL 재실행마다 깨진다
    assert ids(engine) == before


def test_changed_and_removed_source_rows_are_synced(engine):
    run(engine, frames(WL))
    # 2R 승자가 바뀌고, Bind 맵이 원본에서 사라진 상황
    changed = f.win_loss([(1, "Alpha", "Detonated"), (2, "Alpha", "Elimination")], map_name="Ascent")
    st = run(engine, frames(changed, maps=("Ascent",)))
    assert st["rounds"].updated == 1
    assert st["map_games"].deleted == 1 and st["rounds"].deleted == 1
    with engine.connect() as conn:
        winners = (
            conn.execute(
                text("""
            SELECT r.winner FROM rounds r JOIN map_games g USING (map_game_id) JOIN matches m USING (match_id)
            WHERE m.season = :s ORDER BY r.round_number"""),
                {"s": SEASON},
            )
            .scalars()
            .all()
        )
    assert winners == ["A", "A"]
