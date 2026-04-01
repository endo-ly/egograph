"""Conversational chat endpoint with LLM.

LLMとの会話を通じてデータを分析・取得できるエンドポイントです。
LLMが必要に応じてツールを呼び出し、データにアクセスします。
"""

import asyncio
import json
import logging
import re
import sqlite3
from typing import Any, AsyncGenerator

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from backend.api.schemas import (
    DEFAULT_MODEL,
    ChatRequest,
    ChatResponse,
    ModelsResponse,
    ToolInfo,
    ToolsResponse,
    get_all_models,
    get_model,
)
from backend.config import BackendConfig
from backend.dependencies import get_chat_db, get_config, verify_api_key
from backend.infrastructure.repositories import (
    ThreadRepository,
)
from backend.usecases.chat import (
    ChatUseCase,
    ChatUseCaseRequest,
    MaxIterationsExceeded,
    NoUserMessageError,
    ThreadNotFoundError,
)
from backend.usecases.tools import build_tool_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/chat", tags=["chat"])

# MVP: ユーザーIDは固定値
DEFAULT_USER_ID = "default_user"

_SENSITIVE_KEYS = {
    "api_key",
    "authorization",
    "token",
    "credentials",
    "access_token",
    "refresh_token",
}


def _redact_string(value: str) -> str:
    value = re.sub(
        r"(?i)\bbearer\s+[a-z0-9\-._~+/]+=*",
        "Bearer <redacted>",
        value,
    )
    return re.sub(
        r"(?i)\b(api_key|authorization|token|credentials|access_token|refresh_token)\b\s*[:=]\s*([^\s,;]+)",
        r"\1: <redacted>",
        value,
    )


def _sanitize_error_detail(detail: Any) -> Any:
    if isinstance(detail, dict):
        sanitized: dict[str, Any] = {}
        for key, value in detail.items():
            if key.lower() in _SENSITIVE_KEYS:
                continue
            sanitized[key] = _sanitize_error_detail(value)
        return sanitized
    if isinstance(detail, list):
        return [_sanitize_error_detail(item) for item in detail]
    if isinstance(detail, str):
        try:
            parsed = json.loads(detail)
        except (TypeError, ValueError):
            return _redact_string(detail)
        return _sanitize_error_detail(parsed)
    return detail


def _coerce_safe_detail(detail: Any, status_code: int) -> Any:
    if detail in (None, "", {}, []):
        return f"LLM API error (status={status_code})"
    return detail


@router.get("/models", response_model=ModelsResponse)
async def get_models_endpoint(_: None = Depends(verify_api_key)):
    """利用可能なモデル一覧を取得する。

    Returns:
        モデル情報のリストを含む辞書
    """

    return {
        "models": get_all_models(),
        "default_model": DEFAULT_MODEL,
    }


@router.get("/tools", response_model=ToolsResponse)
async def get_tools_endpoint(
    config: BackendConfig = Depends(get_config),
    _: None = Depends(verify_api_key),
):
    """利用可能なツール一覧を取得する。

    R2設定が有効な場合、Spotifyツール群を返します。
    ※ YouTubeツールは一時非推奨 (2025-02-04)

    Returns:
        ツール情報のリストを含む辞書
    """
    tool_registry = build_tool_registry(config.r2)
    tools = [
        ToolInfo(name=tool.name, description=tool.description)
        for tool in tool_registry.get_all_schemas()
    ]

    return ToolsResponse(tools=tools)


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    chat_db: sqlite3.Connection = Depends(get_chat_db),
    config: BackendConfig = Depends(get_config),
    _: None = Depends(verify_api_key),
):
    """LLMエージェント向けチャットエンドポイント。

    ユーザーのメッセージを受け取り、LLMがツールを使用して
    データにアクセスしながら応答を生成します。

    ストリーミングモード (stream=True) の場合は Server-Sent Events (SSE) で
    テキストチャンクを逐次返します。

    Args:
        request: チャットリクエスト
        chat_db: チャットDB接続
        config: バックエンド設定
        _: API Key検証結果(未使用)

    Returns:
        ChatResponse: チャット応答 (stream=Falseの場合)
        StreamingResponse: ストリーミングレスポンス (stream=Trueの場合)

    Raises:
        HTTPException: LLM設定が不足している場合(501)
        HTTPException: モデル名が無効な場合(400)
        HTTPException: スレッドが見つからない場合(404)
        HTTPException: 最大イテレーション到達(500)
        HTTPException: タイムアウト(504)
        HTTPException: LLM APIエラー(502)

    Example:
        POST /v1/chat
        {
            "messages": [
                {"role": "user", "content": "先月の再生回数トップ5は？"}
            ]
        }
    """
    # 1. LLM設定検証
    if not config.llm:
        raise HTTPException(
            status_code=501,
            detail="LLM configuration is missing. Chat endpoint is unavailable.",
        )

    logger.info(
        "Received chat request with %s messages (stream=%s)",
        len(request.messages),
        request.stream,
    )

    # 2. モデル名検証
    model_name = request.model_name or config.llm.default_model
    try:
        get_model(model_name)
    except ValueError as e:
        logger.exception("Invalid model name: %s", model_name)
        raise HTTPException(status_code=400, detail=str(e)) from e

    # 3. ストリーミングモードか非ストリーミングモードか
    if request.stream:
        # ストリーミングレスポンス
        return StreamingResponse(
            _stream_chat(request, chat_db, config),
            media_type="text/event-stream",
        )
    else:
        # 非ストリーミングモード（既存のロジック）
        return await _chat_non_streaming(request, chat_db, config, model_name)


async def _chat_non_streaming(
    request: ChatRequest,
    chat_db: sqlite3.Connection,
    config: BackendConfig,
    model_name: str,
) -> ChatResponse:
    """非ストリーミングモードでチャットを実行します。

    Args:
        request: チャットリクエスト
        chat_db: チャットDB接続
        config: バックエンド設定
        model_name: 使用するモデル名

    Returns:
        ChatResponse: チャット応答

    Raises:
        HTTPException: 各種エラー
    """
    thread_repository = ThreadRepository(chat_db)
    use_case = ChatUseCase(thread_repository, config.llm, config.r2)

    try:
        result = await use_case.execute(
            ChatUseCaseRequest(
                messages=request.messages,
                thread_id=request.thread_id,
                model_name=model_name,
                user_id=DEFAULT_USER_ID,
            )
        )
        return ChatResponse(
            id=result.response_id,
            message=result.message,
            tool_calls=None,
            usage=result.usage,
            thread_id=result.thread_id,
            model_name=result.model_name,
        )
    except NoUserMessageError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ThreadNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except MaxIterationsExceeded as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    except asyncio.TimeoutError:
        logger.exception("Request timed out")
        raise HTTPException(status_code=504, detail="Request timed out") from None
    except httpx.HTTPStatusError as e:
        logger.exception(
            "LLM API error: status=%s response=%s",
            e.response.status_code,
            e.response.text,
        )
        try:
            error_body = e.response.json()
        except ValueError:
            error_body = e.response.text
        safe_detail = _sanitize_error_detail(error_body)
        safe_detail = _coerce_safe_detail(safe_detail, e.response.status_code)
        raise HTTPException(status_code=502, detail=safe_detail) from e
    except Exception as e:
        logger.exception("Chat request failed")
        raise HTTPException(status_code=502, detail=f"LLM API error: {str(e)}") from e


async def _stream_chat(
    request: ChatRequest,
    chat_db: sqlite3.Connection,
    config: BackendConfig,
) -> AsyncGenerator[str, None]:
    """ストリーミングモードでチャットを実行します。

    SSE 形式でチャンクを yield します。

    Args:
        request: チャットリクエスト
        chat_db: チャットDB接続
        config: バックエンド設定

    Yields:
        str: SSE 形式のチャンク

    Raises:
        HTTPException: 各種エラー
    """
    thread_repository = ThreadRepository(chat_db)
    use_case = ChatUseCase(thread_repository, config.llm, config.r2)

    try:
        async for chunk in use_case.execute_stream(
            ChatUseCaseRequest(
                messages=request.messages,
                thread_id=request.thread_id,
                model_name=request.model_name or config.llm.default_model,
                user_id=DEFAULT_USER_ID,
            )
        ):
            # SSE 形式で yield
            yield f"event: {chunk.type}\n"
            yield f"data: {chunk.model_dump_json()}\n\n"
    except NoUserMessageError as e:
        yield "event: error\n"
        yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
    except ThreadNotFoundError as e:
        yield "event: error\n"
        yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
    except MaxIterationsExceeded as e:
        yield "event: error\n"
        yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
    except asyncio.TimeoutError:
        logger.exception("Request timed out")
        yield "event: error\n"
        yield f"data: {json.dumps({'type': 'error', 'error': 'Request timed out'})}\n\n"
    except httpx.HTTPStatusError as e:
        logger.exception(
            "LLM API error: status=%s response=%s",
            e.response.status_code,
            e.response.text,
        )
        try:
            error_body = e.response.json()
        except ValueError:
            error_body = e.response.text
        safe_detail = _sanitize_error_detail(error_body)
        safe_detail = _coerce_safe_detail(safe_detail, e.response.status_code)
        yield "event: error\n"
        yield f"data: {json.dumps({'type': 'error', 'error': safe_detail})}\n\n"
    except Exception as e:
        logger.exception("Chat request failed")
        yield "event: error\n"
        error_payload = json.dumps(
            {"type": "error", "error": f"LLM API error: {str(e)}"}
        )
        yield f"data: {error_payload}\n\n"
