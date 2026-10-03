"""DB 기반 엔드포인트 통합 테스트 (PostgreSQL 필요, 없으면 skip).

ETL의 transform/load로 가짜 시즌(1999) 한 경기를 실제와 같은 경로로 적재한 뒤 API를 호출한다.
"""

import pytest
from sqlalchemy import text

from propredict.db import get_engine
from propredict.etl.load import load_season
from propredict.etl.sources import SeasonFrames
from propredict.etl.transform import transform_season
from tests.etl import factories as f

SEASON = 1999
pytestmark = pytest.mark.db

FULL, ECO = "Full buy: 20k+", "Eco: 0-5k"


@pytest.fixture(scope="module")
def seeded():
    eng = get_engine()
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1 FROM rounds LIMIT 1"))
    except Exception as exc:
        pytest.skip(f"PostgreSQL 사용 불가: {exc.__class__.__name__}")
    wl = f.win_loss([(1, "Alpha", "Detonated"), (2, "Alpha", "Elimination"), (3, "Bravo", "Defused")])
    eco = f.eco(
        [
            (1, "Alpha", "3.9k", "0.4k", ECO, "Win"),
            (1, "Bravo", "3.4k", "0.2k", ECO, "Loss"),
            (2, "Alpha", "24.0k", "1.0k", FULL, "Win"),
            (2, "Bravo", "4.0k", "6.0k", ECO, "Loss"),
        ]
    )  # 3R은 이코노미 없음 → 리플레이 확률 null이어야 함
    sf = SeasonFrames(season=SEASON, scores=f.scores(name="Alpha vs Bravo"), ids=f.ids(name="Alpha vs Bravo"),
                      win_loss=wl.assign(**{"Match Name": "Alpha vs Bravo"}),
                      eco=eco.assign(**{"Match Name": "Alpha vs Bravo"}))  # fmt: skip
    with eng.begin() as conn:
        load_season(conn, SEASON, transform_season(sf))
    yield
    with eng.begin() as conn:
        conn.execute(text("DELETE FROM matches WHERE season = :s"), {"s": SEASON})


def test_maps_and_seasons(client, seeded):
    body = client.get("/api/maps").json()
    assert SEASON in body["seasons"]
    assert any(m["name"] == "Ascent" for m in body["maps"])


def test_team_search_is_case_insensitive_and_season_filtered(client, seeded):
    teams = client.get("/api/teams", params={"q": "alp", "season": SEASON}).json()
    assert [t["name"] for t in teams] == ["Alpha"]
    assert teams[0]["matches"] == 1


def test_buy_matrix_counts_both_perspectives(client, seeded):
    body = client.get("/api/stats/buy-matrix", params={"season": SEASON}).json()
    cells = {(c["team_buy"], c["opponent_buy"]): c for c in body["cells"]}
    assert body["rounds"] == 2 and len(body["cells"]) == 16
    assert cells[(ECO, ECO)]["win_rate"] == 0.5 and cells[(ECO, ECO)]["count"] == 2  # 대각선은 정확히 50%
    assert cells[(FULL, ECO)]["win_rate"] == 1.0 and cells[(ECO, FULL)]["win_rate"] == 0.0
    assert cells[("Semi-buy: 10-20k", ECO)]["win_rate"] is None  # 표본 없는 칸


def test_map_balance(client, seeded):
    rows = client.get("/api/stats/map-balance", params={"season": SEASON}).json()
    assert rows[0]["map_name"] == "Ascent" and rows[0]["rounds"] == 3
    assert rows[0]["side_known_rounds"] == 3  # 1R 폭발로 전반 공격팀이 확정됨


def test_match_list_and_replay(client, seeded):
    matches = client.get("/api/matches", params={"season": SEASON}).json()
    assert len(matches) == 1 and matches[0]["economy_rounds"] == 2
    body = client.get(f"/api/matches/{matches[0]['match_id']}/rounds").json()
    rounds = body["maps"][0]["rounds"]
    assert [r["round_number"] for r in rounds] == [1, 2, 3]
    assert [(r["score_a"], r["score_b"]) for r in rounds] == [(0, 0), (1, 0), (2, 0)]  # 라운드 시작 시점 스코어
    assert rounds[0]["win_probability_a"] is not None and rounds[2]["win_probability_a"] is None
    assert rounds[1]["win_probability_a"] > 0.7  # 풀바이 vs 에코


def test_unknown_match_is_404(client, seeded):
    assert client.get("/api/matches/987654321/rounds").status_code == 404
