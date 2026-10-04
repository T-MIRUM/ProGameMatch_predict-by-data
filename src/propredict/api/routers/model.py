"""GET /api/model/metrics — 모델 성능 지표, calibration curve, SHAP 중요도."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from propredict.api.deps import get_model
from propredict.api.schemas import FeatureImportance, ModelMetricsResponse
from propredict.api.service import FEATURE_LABELS, ModelService

router = APIRouter(prefix="/api/model", tags=["model"])


@router.get("/metrics", response_model=ModelMetricsResponse)
def model_metrics(model: ModelService = Depends(get_model)) -> ModelMetricsResponse:
    # 학습 때 저장한 metrics.json을 그대로 돌려준다: 화면의 숫자와 reports/model_comparison.md가 항상 같다
    m = model.metrics
    # 보정 방법 선택 기록이 없는 예전 아티팩트(isotonic 고정 시절)도 읽을 수 있게 기본값을 둔다
    sel = m.get("calibration_selection", {"method": "isotonic", "cv": []})
    return ModelMetricsResponse(
        trained_at=m["trained_at"], best_iteration=m["best_iteration"], splits=m["splits"], rows=m["rows"],
        serving_model="lightgbm_calibrated", models=m["models"], calibration=m["calibration"],
        significance=m["significance"],
        feature_importance=[FeatureImportance(**f, label=FEATURE_LABELS.get(f["feature"], f["feature"]))
                            for f in m["feature_importance"]],
        calibration_method=sel["method"], calibration_cv=sel["cv"],
    )  # fmt: skip
