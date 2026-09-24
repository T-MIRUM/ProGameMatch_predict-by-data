# API 이미지: 의존성 레이어와 소스 레이어를 분리해 소스만 바뀌면 의존성 설치를 다시 하지 않게 한다.
FROM python:3.11-slim

# LightGBM이 OpenMP 런타임(libgomp)을 필요로 한다
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv PATH="/opt/venv/bin:$PATH"

# 1) 의존성만 먼저 설치 (lockfile 기준, dev 제외)
COPY pyproject.toml uv.lock .python-version README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# 2) 소스 복사 후 프로젝트 자체 설치
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./
RUN uv sync --frozen --no-dev

EXPOSE 8000
# 시작할 때마다 마이그레이션을 적용한다: 'docker compose up' 한 번으로 스키마까지 준비되게 하려는 것.
# upgrade head는 이미 최신이면 아무것도 하지 않으므로 반복 실행해도 안전하다(멱등).
CMD ["sh", "-c", "alembic upgrade head && uvicorn propredict.api.main:app --host 0.0.0.0 --port 8000"]
