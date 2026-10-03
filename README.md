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
| 2 | ETL (CSV → PostgreSQL) → [`reports/etl_summary.md`](reports/etl_summary.md) | ✅ |
| 3 | 모델 (피처 · 학습 · 보정 · 누수 방지 테스트) → [`reports/model_comparison.md`](reports/model_comparison.md) | ✅ |
| 4 | API (FastAPI · OpenAPI 문서 · 테스트) | ✅ |
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

### 3. 데이터 적재 (ETL)

```bash
docker compose up -d db              # DB만 띄우기
uv run alembic upgrade head          # 스키마 적용
uv run python -m propredict.etl      # 전 시즌 적재 (약 2분). --seasons 2025 2026 으로 일부만 가능
```
몇 번을 다시 실행해도 결과는 같다(멱등). 두 번째 실행부터는 모든 테이블이 `+0 ~0 -0`으로 표시된다.
적재 결과는 matches 12,652 · map_games 27,336 · rounds 555,999다.

### 4. 모델 학습 (선택)

학습된 모델(`artifacts/model.joblib`)이 저장소에 포함돼 있으므로 이 단계 없이도 API가 동작한다. 다시 학습하려면:

```bash
uv run python -m propredict.ml.train   # 약 1분. artifacts/와 reports/model_comparison.md를 갱신
```

| 테스트 시즌 | 항상 0.5 | 구매유형 룩업표 | LightGBM + 보정 | 룩업 대비 (95% CI) |
|---|---:|---:|---:|---|
| 2025 | 0.2500 | 0.2223 | **0.2201** | −0.0022 [−0.0032, −0.0011] |
| 2026 (장비가치 결측) | 0.2500 | 0.2222 | **0.2210** | −0.0012 [−0.0021, −0.0003] |

지표는 Brier score(낮을수록 좋음)다. 신뢰구간은 경기 단위 부트스트랩으로 구했다. 2025 ECE는 0.007이다.

### 5. API

`docker compose up` 후 http://localhost:8000/docs 에서 모든 엔드포인트를 직접 호출해 볼 수 있다(OpenAPI 자동 문서).

| 메서드 | 경로 | 설명 | 실데이터 응답 시간 |
|---|---|---|---:|
| GET | `/api/health` | API·DB·모델 상태 | – |
| GET | `/api/maps` | 맵 목록 + 시즌 목록 | 16ms |
| GET | `/api/teams?season=&q=` | 팀 검색 + 팀 강도 | 19ms |
| POST | `/api/predict` | 라운드 승률 + 룩업표 값 + SHAP 상위 요인 | 33ms |
| GET | `/api/stats/buy-matrix?map=&season=` | 구매유형 4×4 승률 (양 팀 관점 대칭) | 130ms |
| GET | `/api/stats/map-balance?season=` | 맵별 공격 승률 등 | 0.6s |
| GET | `/api/matches?season=&team=` | 리플레이할 경기 목록 *(명세 외 추가)* | 10ms |
| GET | `/api/matches/{id}/rounds` | 경기의 라운드별 예측 확률·실제 승패·업셋 | 66ms |
| GET | `/api/model/metrics` | Brier·LogLoss·AUC·ECE, calibration curve, SHAP 중요도 | 3ms |

```bash
curl -X POST localhost:8000/api/predict -H 'content-type: application/json' -d '{
  "map_name": "Ascent", "round_number": 14, "score_a": 7, "score_b": 6,
  "team_a_buy_type": "Full buy: 20k+", "team_b_buy_type": "Eco: 0-5k",
  "team_a_loadout": 24500, "team_b_loadout": 3900, "team_a_credits": 2100, "team_b_credits": 400,
  "team_a_side": "atk"}'
# → {"win_probability_a": 0.8792, "win_probability_b": 0.1208, "baseline_probability_a": 0.8997, "top_factors": [...]}
```

### 6. 로컬 개발

```bash
uv sync                          # 의존성 설치 (.venv)
docker compose up -d db          # DB만 띄우기
uv run alembic upgrade head      # 스키마 적용
uv run pytest                    # 테스트
uv run ruff check . && uv run ruff format --check .
uv run uvicorn propredict.api.main:app --reload   # API 개발 서버 (DB는 docker compose up -d db)
uv run python scripts/audit_data.py   # 데이터 감사 재실행 → reports/data_audit_stats.json

cd web && npm ci && npm run dev  # 웹 개발 서버
```

## 디렉터리 구조

```
├── src/propredict/      # 단일 Python 패키지: config, db, models(ORM), etl/, ml/, api/
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
- **공격/수비 진영은 원본에 직접 없다.** `maps_scores`의 Attacker/Defender 컬럼은 실제로 전·후반 점수다. 진영은 라운드 승리 방식과 하프·연장 교대 규칙으로 역산하며, 라운드의 99.27%에서 확정된다. 나머지는 NULL이다.
- **날짜가 없다.** 시즌(폴더) 단위 순서만 확실하다.
- **이코노미 데이터가 불완전하다.** `eco_rounds`는 맵의 46–100%만 담고 있고, 2026년은 `Loadout Value`가 전부 결측이다.
- **밴픽 커버리지가 낮다.** 2021년 12%, 2022년 33%다.
- **리그 수준이 섞여 있다.** 2023년부터는 1부 리그만 포함하므로 시즌 간 분포가 다르다.

## 설계 결정

주요 결정과 근거는 [`docs/decisions.md`](docs/decisions.md)에 정리한다(분할 전략, A/B 대칭 증강, 진영 피처, 스키마 변경 등).
