"""FastAPI 진입점.

- 모델은 lifespan에서 '앱 시작 시 1회' 로드해 app.state.model에 둔다(요청마다 로드하지 않는다).
- 모델 파일이 없어도 앱은 뜬다: DB 기반 통계는 제공하고 예측 엔드포인트만 503을 돌려준다.
- DB 연결 실패는 500 스택트레이스 대신 503 + 이유로 알린다(프론트가 '데이터 없음' 상태를 보여줄 수 있게).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from propredict import __version__
from propredict.api.routers import matches, meta, model, predict, stats
from propredict.api.schemas import HealthResponse
from propredict.api.service import ModelService
from propredict.config import get_settings
from propredict.db import get_engine

log = logging.getLogger("propredict.api")


def check_database() -> bool:
    """DB 연결 확인. 테스트에서 dependency_overrides로 교체할 수 있게 함수로 분리한다."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    artifacts = get_settings().artifacts_dir
    try:
        app.state.model = ModelService.load(artifacts)
        log.info("model loaded from %s", artifacts)
    except FileNotFoundError:
        app.state.model = None
        log.warning("model artifact not found in %s — predictions disabled", artifacts)
    yield


app = FastAPI(
    title="Propredict — VCT Round Win Probability API",
    version=__version__,
    description="발로란트 VCT 라운드 시작 시점 상태로 라운드 승리 확률을 예측합니다. "
    "교육·포트폴리오 목적의 서비스이며 Riot Games와 무관합니다.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
for r in (meta.router, predict.router, stats.router, matches.router, model.router):
    app.include_router(r)


@app.exception_handler(OperationalError)
async def db_unavailable(_: Request, exc: OperationalError) -> JSONResponse:
    log.warning("database unavailable: %s", exc.__class__.__name__)
    return JSONResponse(status_code=503, content={"detail": "데이터베이스에 연결할 수 없습니다"})


@app.get("/api/health", response_model=HealthResponse, tags=["meta"])
def health(request: Request, db_ok: bool = Depends(check_database)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=__version__,
        database="ok" if db_ok else "unavailable",
        model_loaded=getattr(request.app.state, "model", None) is not None,
    )
