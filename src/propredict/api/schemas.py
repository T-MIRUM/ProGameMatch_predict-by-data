"""API 요청·응답 스키마 (Pydantic v2).

모든 응답을 명시적 모델로 두는 이유: OpenAPI 문서가 자동으로 정확해지고, 프론트엔드 타입과
백엔드 응답이 어긋나면 서버에서 먼저 검증 오류가 난다(조용히 깨진 화면 대신).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from propredict.etl.normalize import BUY_TYPES

BuyType = Literal["Eco: 0-5k", "Semi-eco: 5-10k", "Semi-buy: 10-20k", "Full buy: 20k+"]
assert set(BuyType.__args__) == set(BUY_TYPES)  # ETL 검증과 같은 값 집합을 쓰는지 import 시점에 확인

# 5인 × 최대 9,000 크레딧. 장비가치도 같은 범위 안에 있다(감사 기준 최대 약 4.5만).
MAX_CREDITS = 50_000


# ---------------------------------------------------------------- meta
class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    database: Literal["ok", "unavailable"]
    model_loaded: bool


class MapInfo(BaseModel):
    name: str
    map_games: int
    rounds: int
    last_season: int


class MapsResponse(BaseModel):
    maps: list[MapInfo]
    seasons: list[int]


class TeamInfo(BaseModel):
    name: str
    matches: int
    last_season: int
    strength: float | None = Field(None, description="전체 경기 기준 라운드 승률(베이지안 수축). 학습에 없던 팀은 null")


# ---------------------------------------------------------------- predict
class PredictRequest(BaseModel):
    map_name: str = Field(examples=["Ascent"])
    round_number: int = Field(ge=1, le=60)
    score_a: int = Field(ge=0, le=59, description="이 라운드 시작 전 Team A가 딴 라운드 수")
    score_b: int = Field(ge=0, le=59)
    team_a_buy_type: BuyType
    team_b_buy_type: BuyType
    team_a_loadout: int | None = Field(
        None, ge=0, le=MAX_CREDITS, description="장비 가치. 모르면 생략(2026 데이터처럼)"
    )
    team_b_loadout: int | None = Field(None, ge=0, le=MAX_CREDITS)
    team_a_credits: int | None = Field(None, ge=0, le=MAX_CREDITS)
    team_b_credits: int | None = Field(None, ge=0, le=MAX_CREDITS)
    team_a_side: Literal["atk", "def"] | None = Field(
        None, description="Team A 진영 (명세 대비 추가 필드, decisions D3)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "map_name": "Ascent",
                    "round_number": 14,
                    "score_a": 7,
                    "score_b": 6,
                    "team_a_buy_type": "Full buy: 20k+",
                    "team_b_buy_type": "Eco: 0-5k",
                    "team_a_loadout": 24500,
                    "team_b_loadout": 3900,
                    "team_a_credits": 2100,
                    "team_b_credits": 400,
                    "team_a_side": "atk",
                }
            ]  # fmt: skip
        }
    }

    @model_validator(mode="after")
    def score_matches_round(self) -> PredictRequest:
        # 라운드 N이 시작될 때 두 팀 스코어 합은 항상 N-1이다. 불가능한 상태로 예측하면 의미 없는 숫자가 나온다.
        if self.score_a + self.score_b != self.round_number - 1:
            raise ValueError("score_a + score_b 는 round_number - 1 과 같아야 합니다")
        return self


class Factor(BaseModel):
    feature: str
    label: str
    contribution: float = Field(description="TreeSHAP 기여도(로그오즈). 양수 = Team A 승리 쪽으로 밀어줌")


class PredictResponse(BaseModel):
    win_probability_a: float
    win_probability_b: float
    baseline_probability_a: float = Field(description="구매유형 조합 룩업표의 승률")
    top_factors: list[Factor]


# ---------------------------------------------------------------- stats
class BuyCell(BaseModel):
    team_buy: BuyType
    opponent_buy: BuyType
    win_rate: float | None
    count: int


class BuyMatrixResponse(BaseModel):
    buy_types: list[BuyType]
    cells: list[BuyCell]
    rounds: int
    map: str | None
    season: int | None


class MapBalance(BaseModel):
    map_name: str
    map_games: int
    rounds: int
    side_known_rounds: int
    attacker_win_rate: float | None
    avg_rounds_per_map: float


# ---------------------------------------------------------------- matches
class MatchSummary(BaseModel):
    match_id: int
    season: int
    tournament: str
    stage: str
    match_type: str
    team_a: str
    team_b: str
    score_a: int | None
    score_b: int | None
    maps: int
    economy_rounds: int


class ReplayRound(BaseModel):
    round_number: int
    score_a: int
    score_b: int
    team_a_side: Literal["atk", "def"] | None
    team_a_buy_type: BuyType | None
    team_b_buy_type: BuyType | None
    team_a_loadout: int | None
    team_b_loadout: int | None
    winner: Literal["A", "B"]
    win_probability_a: float | None = Field(description="이코노미 정보가 없는 라운드는 예측하지 않는다(null)")
    baseline_probability_a: float | None
    upset: bool = Field(description="모델이 30% 미만으로 본 쪽이 이긴 라운드")


class ReplayMap(BaseModel):
    map_game_id: int
    map_name: str
    map_order: int | None
    score_a: int | None
    score_b: int | None
    rounds: list[ReplayRound]


class MatchRoundsResponse(BaseModel):
    match: MatchSummary
    team_a_strength: float
    team_b_strength: float
    maps: list[ReplayMap]


# ---------------------------------------------------------------- model
class MetricSet(BaseModel):
    n: int
    brier: float
    log_loss: float
    auc: float | None
    ece: float


class CalibrationBin(BaseModel):
    bin_lower: float
    bin_upper: float
    mean_predicted: float
    observed_rate: float
    count: int


class CalibrationCurves(BaseModel):
    raw: list[CalibrationBin]
    calibrated: list[CalibrationBin]


class Significance(BaseModel):
    diff: float
    ci_low: float
    ci_high: float
    n_groups: int


class FeatureImportance(BaseModel):
    feature: str
    label: str
    mean_abs_shap: float


class ModelMetricsResponse(BaseModel):
    trained_at: str
    best_iteration: int
    splits: dict[str, list[int]]
    rows: dict[str, int]
    serving_model: str
    models: dict[str, dict[str, MetricSet]]
    calibration: dict[str, CalibrationCurves]
    significance: dict[str, dict[str, Significance]]
    feature_importance: list[FeatureImportance]
