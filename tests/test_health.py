"""헬스 엔드포인트 테스트 — DB 없이도 돌도록 DB 확인을 의존성 오버라이드로 대체한다."""

import pytest
from fastapi.testclient import TestClient

from propredict.api.main import app, check_database


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.parametrize(("db_ok", "expected"), [(True, "ok"), (False, "unavailable")])
def test_health_reports_database_state(client, db_ok, expected):
    app.dependency_overrides[check_database] = lambda: db_ok
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert res.json()["database"] == expected


def test_openapi_is_generated(client):
    # 명세: OpenAPI 문서 자동 생성
    assert client.get("/openapi.json").status_code == 200
