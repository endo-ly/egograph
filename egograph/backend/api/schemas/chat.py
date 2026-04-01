"""チャット API スキーマ。

チャット API のリクエスト・レスポンスモデルを定義します。
"""

from pydantic import BaseModel

from backend.domain.models.llm import Message


class ChatRequest(BaseModel):
    """チャット API リクエスト。

    Attributes:
        messages: メッセージリスト
        stream: ストリーミング有効化フラグ
        thread_id: スレッド ID（既存スレッドの場合）
        model_name: 使用するモデル名
    """

    messages: list[Message]
    stream: bool = False
    thread_id: str | None = None
    model_name: str | None = None


class ChatResponse(BaseModel):
    """チャット API レスポンス。

    Attributes:
        id: レスポンス ID
        message: アシスタントメッセージ
        tool_calls: ツール呼び出し情報
        usage: トークン使用量情報
        thread_id: スレッド ID
        model_name: 使用したモデル名
    """

    id: str
    message: Message
    tool_calls: list[dict] | None = None
    usage: dict | None = None
    thread_id: str
    model_name: str | None = None


class ToolInfo(BaseModel):
    """ツール情報。

    Attributes:
        name: ツール名
        description: ツール説明
    """

    name: str
    description: str


class ToolsResponse(BaseModel):
    """ツール一覧レスポンス。

    Attributes:
        tools: ツール情報のリスト
    """

    tools: list[ToolInfo]
