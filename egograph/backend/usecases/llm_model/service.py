"""LLM モデル取得サービス。

LLM モデル情報の取得ロジックを提供します。
"""

from backend.domain.models.llm_model import MODELS_CONFIG, LLMModel


def get_model(model_id: str) -> LLMModel:
    """モデル ID からモデル情報を取得する。

    Args:
        model_id: モデル ID（例: "openai/gpt-oss-120b:free"）

    Returns:
        LLMModel: モデル情報

    Raises:
        ValueError: モデル ID が登録されていない場合
    """
    if model_id not in MODELS_CONFIG:
        raise ValueError(f"invalid_model_name: unknown model '{model_id}'")
    return MODELS_CONFIG[model_id]


def get_all_models() -> list[LLMModel]:
    """全モデルを取得する。

    Returns:
        モデル情報のリスト
    """
    return list(MODELS_CONFIG.values())
