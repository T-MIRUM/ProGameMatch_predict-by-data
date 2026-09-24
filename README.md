# ProGameMatch_predict-by-data

> **Propredict** — 발로란트 VCT 프로 경기에서 **라운드가 시작되는 시점의 상태**만으로 그 라운드의 승리 확률을 예측하고, 웹에서 탐색하는 서비스.
>
> 본 서비스는 교육·포트폴리오 목적이며 Riot Games와 무관합니다.

## 무엇을 보여 주나

- **확률의 신뢰성(calibration)**: "모델이 70%라고 한 라운드는 실제로 70% 이겼다"를 calibration curve로 증명한다.
- **이코노미의 영향 정량화**: 구매 유형 조합(Eco / Semi-eco / Semi-buy / Full buy)이 라운드 승패에 주는 영향.
- 성능 기준선은 "항상 0.5"와 "구매유형 조합 룩업 테이블" 두 가지다. 모델은 둘 다 이겨야 한다.

## 진행 상황

| Phase | 내용 | 상태 |
|---|---|---|
| 0 | 데이터 감사 → [`reports/data_audit.md`](reports/data_audit.md) | ✅ |
| 1 | 프로젝트 골격 (Docker Compose, DB 마이그레이션, CI) | ✅ |
| 2 | ETL (CSV → PostgreSQL) | ⏳ |
| 3 | 모델 (피처 · 학습 · 보정 · 누수 방지 테스트) | ⏳ |
| 4 | API | ⏳ |
| 5 | 프론트엔드 (시뮬레이터 · 이코노미 매트릭스 · 경기 리플레이 · 모델 성능) | ⏳ |
| 6 | 마무리 (아키텍처 다이어그램 · 결과 정리) | ⏳ |

## 아키텍처 (초안)

```
data/raw/*.csv ──(ETL, Phase 2)──▶ PostgreSQL 16 ──(학습, Phase 3)──▶ artifacts/model
                                        │                                  │ (시작 시 1회 로드)
                                        └──────────▶ FastAPI (:8000) ◀─────┘
                                                        ▲
                                              Next.js (:3000, 브라우저)
```

| 영역 | 기술 |
|---|---|
| 언어 / 패키지 | Python 3.11, uv |
| DB / 마이그레이션 | PostgreSQL 16, SQLAlchemy 2, Alembic |
| 모델 | scikit-learn, LightGBM, SHAP |
| API | FastAPI, Pydantic v2 |
| 웹 | Next.js 16 (App Router), TypeScript, Tailwind v4, Recharts |
| 인프라 | Docker Compose, GitHub Actions |

## 빠른 시작

### 준비물
- Docker Desktop
- [uv](https://docs.astral.sh/uv/) (Python 3.11은 uv가 자동으로 받는다)
- Node.js 22 (웹을 로컬에서 개발할 때만)

### 1. 데이터 받기

```bash
./scripts/download_data.sh      # kaggle CLI 필요. 방법은 스크립트 상단 주석 참고
```
CLI 없이 [Kaggle 데이터셋 페이지](https://www.kaggle.com/datasets/ryanluong1/valorant-champion-tour-2021-2023-data)에서 zip을 받아 `data/raw/`에 풀어도 된다. 원본 CSV(1.3 GB)는 git에 커밋하지 않는다.

### 2. 전체 스택 실행

```bash
cp .env.example .env            # 선택: 기본값으로도 동작
docker compose up --build
```
- 웹: http://localhost:3000 — API·DB 연결 상태가 표시된다
- API 문서(OpenAPI): http://localhost:8000/docs
- DB 스키마는 API 컨테이너가 시작할 때 `alembic upgrade head`로 자동 적용된다.

### 3. 로컬 개발

```bash
uv sync                          # 의존성 설치 (.venv)
docker compose up -d db          # DB만 띄우기
uv run alembic upgrade head      # 스키마 적용
uv run pytest                    # 테스트
uv run ruff check . && uv run ruff format --check .
uv run python scripts/audit_data.py   # 데이터 감사 재실행 → reports/data_audit_stats.json

cd web && npm ci && npm run dev  # 웹 개발 서버
```

## 디렉터리 구조

```
├── src/propredict/      # 단일 Python 패키지: config, db, models(ORM), api/ (ETL·ML은 Phase 2–3에서 추가)
├── migrations/          # Alembic 마이그레이션
├── tests/
├── scripts/             # download_data.sh, audit_data.py
├── web/                 # Next.js 프론트엔드
├── docker/              # api / web Dockerfile
├── data/raw/            # 원본 CSV (git 제외)
├── artifacts/           # 학습된 모델 (API에 읽기 전용 마운트)
├── reports/             # 데이터 감사 · 모델 비교 리포트
└── docs/decisions.md    # 설계 결정 기록
```

## 데이터 한계 (요약)

자세한 수치와 근거는 [`reports/data_audit.md`](reports/data_audit.md)에 있다.

- **라운드 진행 중 실시간 승률은 만들 수 없다.** `rounds_kills.csv`는 멀티킬·클러치만 기록하고 타임스탬프가 없다. 선수 단위 집계로만 쓴다.
- **공격/수비 진영은 원본에 직접 없다.** `maps_scores`의 Attacker/Defender 컬럼은 실제로 전·후반 점수다. 진영은 라운드 승리 방식으로 역산하며, 하프의 88–95%에서 확정된다. 나머지는 NULL이다.
- **날짜가 없다.** 시즌(폴더) 단위 순서만 확실하다.
- **이코노미 데이터가 불완전하다.** `eco_rounds`는 맵의 46–100%만 담고 있고, 2026년은 `Loadout Value`가 전부 결측이다.
- **밴픽 커버리지가 낮다.** 2021년 12%, 2022년 33%다.
- **리그 수준이 섞여 있다.** 2023년부터는 1부 리그만 포함하므로 시즌 간 분포가 다르다.

## 설계 결정

주요 결정과 근거는 [`docs/decisions.md`](docs/decisions.md)에 정리한다(분할 전략, A/B 대칭 증강, 진영 피처, 스키마 변경 등).
