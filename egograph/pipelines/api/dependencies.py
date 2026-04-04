"""FastAPI dependencies."""

import secrets

from fastapi import Depends, Header, HTTPException, Request

from pipelines.service import PipelineService


def get_service(request: Request) -> PipelineService:
    """app.state.service から PipelineService を取得する。"""
    return request.app.state.service


def verify_api_key(
    x_api_key: str | None = Header(None),
    service: PipelineService = Depends(get_service),
) -> None:
    """PIPELINES_API_KEY が設定されている場合だけ X-API-Key を検証する。"""
    if service.config.api_key is None:
        return

    if not x_api_key or not secrets.compare_digest(
        x_api_key,
        service.config.api_key.get_secret_value(),
    ):
        raise HTTPException(status_code=401, detail="Invalid API key")
