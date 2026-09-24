"""FastAPI 진입점.

Phase 1에서는 스택이 뜨는지 확인할 /api/health만 제공한다.
모델 로드는 lifespan에서 '앱 시작 시 1회' 수행하도록 자리를 잡아 두고, Phase 4에서 채운다
(요청마다 모델을 읽으면 디스크 I/O 때문에 500ms 응답 목표를 지킬 수 없다).
"""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text

from propredict import __version__
from propredict.config import get_settings
from propredict.db import get_engine


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    database: Literal["ok", "unavailable"]


def check_database() -> bool:
    """DB 연결 확인. 테스트에서 dependency_overrides로 교체할 수 있게 함수로 분리한다."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        # 헬스체크는 예외로 500을 내기보다 '무엇이 안 되는지'를 알려 주는 편이 운영에 유용하다
        return False


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Phase 4: 여기서 artifacts/의 모델을 1회 로드해 app.state에 보관한다
    yield


app = FastAPI(
    title="Propredict — VCT Round Win Probability API",
    version=__version__,
    description="교육·포트폴리오 목적의 서비스이며 Riot Games와 무관합니다.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse, tags=["meta"])
def health(db_ok: bool = Depends(check_database)) -> HealthResponse:
    # 프로세스가 응답하면 status는 ok. DB 상태는 별도 필드로 알려 컨테이너 재시작 루프를 피한다.
    return HealthResponse(status="ok", version=__version__, database="ok" if db_ok else "unavailable")
