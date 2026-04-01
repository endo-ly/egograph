"""System Prompt API スキーマ。"""

from pydantic import BaseModel


class SystemPromptResponse(BaseModel):
    """System Prompt API レスポンス。"""

    name: str
    content: str


class SystemPromptUpdateRequest(BaseModel):
    """System Prompt 更新リクエスト。"""

    content: str
