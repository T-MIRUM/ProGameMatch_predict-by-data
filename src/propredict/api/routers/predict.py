"""POST /api/predict — 라운드 시작 상태 → Team A 승리 확률."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from propredict.api.deps import get_model
from propredict.api.schemas import PredictRequest, PredictResponse
from propredict.api.service import ModelService

router = APIRouter(prefix="/api", tags=["predict"])


@router.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest, model: ModelService = Depends(get_model)) -> PredictResponse:
    if req.map_name not in model.model.categories["map_name"]:
        # 학습에 없던 맵이라도 예측은 가능하지만(맵 피처가 결측 경로로 감), 오타일 가능성이 커서 명확히 알린다
        known = ", ".join(model.model.categories["map_name"])
        raise HTTPException(status_code=422, detail=f"알 수 없는 맵: {req.map_name}. 가능한 값: {known}")
    return model.predict(req)
