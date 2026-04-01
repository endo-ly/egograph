"""LLM関連のドメインモデル。

LLMプロバイダー間で統一されたメッセージ構造を定義します。
"""

from typing import Any, Literal

from pydantic import BaseModel


class Message(BaseModel):
    """チャットメッセージ(ドメインエンティティ)。

    ビジネスドメインとしての「会話内のメッセージ」を表現します。
    LLMプロバイダーに関わらず共通で使用する概念です。

    Attributes:
        role: メッセージの送信者(user, assistant, system, tool)
        content: メッセージ本文(文字列またはAnthropicのtool_result形式のリスト)
        tool_call_id: ツール結果メッセージ用のID(OpenAI形式)
        name: ツール名(OpenAI形式のtool結果メッセージ用)
        tool_calls: assistantメッセージに含まれるツール呼び出し
            (ToolCallオブジェクトのリスト)
    """

    role: Literal["user", "assistant", "system", "tool"]
    # tool callsのみの場合はNoneを許可
    content: str | list[dict[str, Any]] | None = None
    tool_call_id: str | None = None  # OpenAI tool result用
    name: str | None = None  # OpenAI tool result用のツール名
    # assistant messageのtool_calls(ToolCallオブジェクトのリスト)
    tool_calls: list["ToolCall"] | None = None


class ToolCall(BaseModel):
    """LLMからのツール呼び出しリクエスト(ドメインエンティティ)。"""

    id: str
    name: str
    parameters: dict[str, Any]


class ChatResponse(BaseModel):
    """統一されたチャットレスポンス(ドメインエンティティ)。

    各プロバイダーのレスポンスをこの形式に変換します。
    """

    id: str
    message: Message
    tool_calls: list[ToolCall] | None = None
    # tokens情報(プロバイダーによって構造が異なる)
    usage: dict[str, Any] | None = None
    finish_reason: str


class StreamChunk(BaseModel):
    """ストリーミングチャンク(ドメインエンティティ)。

    LLMレスポンスの各チャンクを表現します。
    ツール呼び出しと最終テキスト生成の両方をサポートします。
    """

    type: Literal["delta", "tool_call", "tool_result", "done", "error"]
    delta: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_name: str | None = None
    tool_result: dict[str, Any] | None = None
    finish_reason: str | None = None
    usage: dict[str, Any] | None = None
    error: str | None = None
    thread_id: str | None = None
