"""モックLLMレスポンス。"""

import json
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from backend.domain.models.llm import ChatResponse, Message

if TYPE_CHECKING:
    from backend.domain.models.llm import StreamChunk


def get_mock_openai_response(
    content: str = "Test response", tool_calls: Optional[List[Dict[str, Any]]] = None
):
    """モックOpenAI APIレスポンス。

    Args:
        content: レスポンスのコンテンツ
        tool_calls: ツール呼び出しのリスト

    Returns:
        OpenAI API形式のレスポンス辞書
    """
    # tool_callsがある場合はfinish_reasonを"tool_calls"にする
    finish_reason = "tool_calls" if tool_calls else "stop"

    return {
        "id": "chatcmpl-test-123",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "gpt-4o-mini",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": tool_calls,
                },
                "finish_reason": finish_reason,
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
        },
    }


def get_mock_openai_tool_call_response(tool_name: str, tool_arguments: Dict[str, Any]):
    """ツール呼び出しを含むモックOpenAI APIレスポンス。

    Args:
        tool_name: ツール名
        tool_arguments: ツール引数

    Returns:
        ツール呼び出しを含むOpenAI API形式のレスポンス辞書
    """

    tool_calls = [
        {
            "id": "call_test_123",
            "type": "function",
            "function": {"name": tool_name, "arguments": json.dumps(tool_arguments)},
        }
    ]

    return get_mock_openai_response(content="", tool_calls=tool_calls)


def get_mock_anthropic_response(content: str = "Test response"):
    """モックAnthropic APIレスポンス。

    Args:
        content: レスポンスのコンテンツ

    Returns:
        Anthropic API形式のレスポンス辞書
    """
    return {
        "id": "msg_test_123",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": content}],
        "model": "claude-3-5-sonnet-20241022",
        "usage": {"input_tokens": 10, "output_tokens": 20},
    }


def get_mock_anthropic_tool_use_response(
    tool_name: str, tool_input: Dict[str, Any], text_content: str = ""
):
    """ツール使用を含むモックAnthropic APIレスポンス。

    Args:
        tool_name: ツール名
        tool_input: ツール入力
        text_content: テキストコンテンツ（オプション）

    Returns:
        ツール使用を含むAnthropic API形式のレスポンス辞書
    """
    content = []
    if text_content:
        content.append({"type": "text", "text": text_content})

    content.append(
        {
            "type": "tool_use",
            "id": "toolu_test_123",
            "name": tool_name,
            "input": tool_input,
        }
    )

    return {
        "id": "msg_test_123",
        "type": "message",
        "role": "assistant",
        "content": content,
        "model": "claude-3-5-sonnet-20241022",
        "usage": {"input_tokens": 10, "output_tokens": 20},
    }


def mock_chat_response(content: str, tool_calls=None) -> ChatResponse:
    """モックChatResponseオブジェクトを生成します。

    Args:
        content: レスポンスのコンテンツ
        tool_calls: ツール呼び出しのリスト（オプション）

    Returns:
        ChatResponseオブジェクト
    """
    return ChatResponse(
        id="test-response-123",
        message=Message(role="assistant", content=content, tool_calls=tool_calls),
        tool_calls=tool_calls,
        usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        finish_reason="stop" if tool_calls is None else "tool_calls",
    )


def get_mock_openai_stream_response(text_chunks: list[str], done: bool = True):
    """モックOpenAIストリーミングレスポンス（SSE形式）を生成します。

    Args:
        text_chunks: テキストチャンクのリスト
        done: 完了フラグ

    Returns:
        SSE形式の各行を返すジェネレータ
    """
    for chunk in text_chunks:
        json_data = {
            "id": "chatcmpl-stream",
            "object": "chat.completion.chunk",
            "created": 1234567890,
            "model": "gpt-4o-mini",
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": chunk},
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(json_data)}\n"

    if done:
        yield "data: [DONE]\n"


def get_mock_anthropic_stream_events(events: list[dict]) -> list[dict]:
    """モックAnthropicストリーミングイベントを生成します。

    Args:
        events: イベントのリスト（各イベントは辞書）

    Returns:
        イベント辞書のリスト
    """
    return events


def mock_stream_chunk(
    type: str,
    delta: str | None = None,
    tool_calls=None,
    finish_reason: str | None = None,
    usage: dict | None = None,
    error: str | None = None,
) -> "StreamChunk":
    """モックStreamChunkオブジェクトを生成します。

    Args:
        type: チャンクタイプ ("delta", "tool_call", "tool_result", "done", "error")
        delta: テキスト增量
        tool_calls: ツール呼び出しリスト
        finish_reason: 完了理由
        usage: トークン使用量
        error: エラーメッセージ

    Returns:
        StreamChunkオブジェクト
    """
    # モジュール内で循環インポートを避けるため、関数内でインポート
    from backend.domain.models.llm import StreamChunk  # noqa: PLC0415

    return StreamChunk(
        type=type,
        delta=delta,
        tool_calls=tool_calls,
        finish_reason=finish_reason,
        usage=usage,
        error=error,
    )


def get_mock_anthropic_stream_lines(text_chunks: list[str]) -> list[str]:
    """モックAnthropicストリーミングレスポンスの行を生成します。

    AnthropicはSSE形式（event: <type>\ndata: <json>\n\n）を返します。

    Args:
        text_chunks: テキストチャンクのリスト

    Returns:
        Anthropic SSE形式の行リスト
    """
    lines = []
    for chunk in text_chunks:
        event = {
            "type": "content_block_delta",
            "index": 0,
            "content_block": {"type": "text"},
            "delta": {"type": "text_delta", "text": chunk},
        }
        # SSE形式: event行、data行、空行
        lines.append(f"event: {event['type']}")
        lines.append(f"data: {json.dumps(event)}")
        lines.append("")

    # 完了イベント
    done_event = {
        "type": "message_stop",
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 10, "output_tokens": len(" ".join(text_chunks))},
    }
    lines.append(f"event: {done_event['type']}")
    lines.append(f"data: {json.dumps(done_event)}")
    lines.append("")

    return lines
