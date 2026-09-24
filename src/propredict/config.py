"""환경 변수 기반 설정.

설정을 코드 곳곳에서 os.environ으로 직접 읽으면 기본값과 타입이 흩어진다.
pydantic-settings로 한 곳에 모아 두면 잘못된 값이 시작 시점에 바로 드러난다.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://propredict:propredict@localhost:5432/propredict"
    raw_data_dir: Path = Path("data/raw")
    artifacts_dir: Path = Path("artifacts")
    # 브라우저에서 API를 직접 호출하므로 CORS 허용 출처가 필요하다
    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    # 프로세스당 1회만 파싱한다. 테스트에서는 get_settings.cache_clear()로 초기화한다.
    return Settings()
