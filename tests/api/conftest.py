import pytest
from fastapi.testclient import TestClient

from propredict.api.main import app


@pytest.fixture(scope="module")
def client():
    # with 블록이어야 lifespan이 실행되어 모델이 로드된다 (실제 서비스와 같은 경로)
    with TestClient(app) as c:
        yield c
