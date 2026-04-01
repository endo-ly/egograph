"""LLM モデル API スキーマ。

LLM モデル情報 API のレスポンスモデルを定義します。
"""

from pydantic import BaseModel

from backend.domain.models.llm_model import LLMModel


class ModelsResponse(BaseModel):
    """モデル一覧 API レスポンス。

    Attributes:
        models: モデル情報のリスト
        default_model: デフォルトモデル ID
    """

    models: list[LLMModel]
    default_model: str
