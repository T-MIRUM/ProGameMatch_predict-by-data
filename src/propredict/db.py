"""DB 엔진과 세션.

엔진은 커넥션 풀을 들고 있으므로 프로세스당 하나만 만든다(lru_cache).
요청마다 엔진을 새로 만들면 커넥션이 누적되어 Postgres max_connections에 걸린다.
"""
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from propredict.config import get_settings


@lru_cache
def get_engine() -> Engine:
    # pool_pre_ping: 컨테이너 재시작 등으로 끊긴 커넥션을 쓰기 전에 걸러낸다
    return create_engine(get_settings().database_url, pool_pre_ping=True)


def get_session() -> Iterator[Session]:
    """FastAPI 의존성 주입용. 요청이 끝나면 세션을 반드시 닫는다."""
    factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    with factory() as session:
        yield session
