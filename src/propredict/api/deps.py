"""FastAPI 의존성. 테스트에서 dependency_overrides로 갈아끼울 수 있게 함수로 분리한다."""

from __future__ import annotations

from fastapi import HTTPException, Request

from propredict.api.service import ModelService


def get_model(request: Request) -> ModelService:
    model: ModelService | None = getattr(request.app.state, "model", None)
    if model is None:
        # 모델 파일이 없어도 앱은 떠서 DB 기반 통계는 제공한다. 예측만 503으로 알린다.
        raise HTTPException(status_code=503, detail="모델이 로드되지 않았습니다. artifacts/model.joblib을 확인하세요.")
    return model
