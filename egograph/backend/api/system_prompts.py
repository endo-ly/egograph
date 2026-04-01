"""System Prompt 管理API。"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from backend.api.schemas import SystemPromptResponse, SystemPromptUpdateRequest
from backend.dependencies import verify_api_key
from backend.infrastructure.context_files import (
    ensure_context_file,
    read_context_file,
    resolve_context_file,
    write_context_file,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/system-prompts", tags=["system-prompts"])


@router.get("/{name}", response_model=SystemPromptResponse)
def get_system_prompt(
    name: str,
    _: None = Depends(verify_api_key),
):
    """System Prompt ファイルを取得します。"""

    try:
        entry = resolve_context_file(name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    content = read_context_file(entry.key)
    if content is None:
        content = ensure_context_file(entry.key)
    logger.info("Loaded system prompt file: %s", entry.filename)

    return SystemPromptResponse(name=entry.key, content=content)


@router.put("/{name}", response_model=SystemPromptResponse)
def update_system_prompt(
    name: str,
    request: SystemPromptUpdateRequest,
    _: None = Depends(verify_api_key),
):
    """System Prompt ファイルを更新します。"""

    try:
        entry = resolve_context_file(name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        write_context_file(entry.key, request.content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.info("Updated system prompt file: %s", entry.filename)

    return SystemPromptResponse(name=entry.key, content=request.content)
