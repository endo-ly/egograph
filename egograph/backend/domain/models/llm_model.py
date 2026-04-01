"""LLM モデルのドメインモデル。

LLM モデルの情報を表現するエンティティと、利用可能なモデルの定義を管理します。
"""

from pydantic import BaseModel


class LLMModel(BaseModel):
    """LLM モデル情報エンティティ。

    Attributes:
        id: モデル ID（例: "openai/gpt-oss-120b:free"）
        name: モデルの表示名
        provider: プロバイダー名（例: "openrouter"）
        input_cost_per_1m: 入力 100万トークンあたりのコスト（USD）
        output_cost_per_1m: 出力 100万トークンあたりのコスト（USD）
        is_free: 無料モデルかどうか
    """

    id: str
    name: str
    provider: str
    input_cost_per_1m: float
    output_cost_per_1m: float
    is_free: bool


# 利用可能な LLM モデルの定義
MODELS_CONFIG: dict[str, LLMModel] = {
    "arcee-ai/trinity-large-preview:free": LLMModel(
        id="arcee-ai/trinity-large-preview:free",
        name="trinity-large-preview",
        provider="openrouter",
        input_cost_per_1m=0.0,
        output_cost_per_1m=0.0,
        is_free=True,
    ),
    "stepfun/step-3.5-flash:free": LLMModel(
        id="stepfun/step-3.5-flash:free",
        name="step-3.5-flash",
        provider="openrouter",
        input_cost_per_1m=0.0,
        output_cost_per_1m=0.0,
        is_free=True,
    ),
    "x-ai/grok-4.1-fast": LLMModel(
        id="x-ai/grok-4.1-fast",
        name="Grok 4.1 Fast",
        provider="openrouter",
        input_cost_per_1m=0.20,
        output_cost_per_1m=0.50,
        is_free=False,
    ),
    "deepseek/deepseek-v3.2": LLMModel(
        id="deepseek/deepseek-v3.2",
        name="DeepSeek v3.2",
        provider="openrouter",
        input_cost_per_1m=0.25,
        output_cost_per_1m=0.38,
        is_free=False,
    ),
    "glm-4.7": LLMModel(
        id="glm-4.7",
        name="GLM 4.7",
        provider="openai",
        input_cost_per_1m=0.0,
        output_cost_per_1m=0.0,
        is_free=False,
    ),
}

DEFAULT_MODEL = "deepseek/deepseek-v3.2"
