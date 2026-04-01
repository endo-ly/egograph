"""統一LLMクライアント。

設定に基づいて適切なプロバイダーにリクエストをルーティングします。
"""

import logging
from typing import AsyncGenerator

from backend.config import LLMConfig
from backend.domain.models.llm import ChatResponse, Message, StreamChunk
from backend.domain.models.llm_model import MODELS_CONFIG
from backend.domain.models.tool import Tool
from backend.infrastructure.llm.providers import (
    AnthropicProvider,
    BaseLLMProvider,
    OpenAIProvider,
)

logger = logging.getLogger(__name__)


class LLMClient:
    """統一LLMクライアント。

    モデルIDに基づいてプロバイダーを判定し、
    統一されたインターフェースでLLM APIにアクセスします。

    Example:
        >>> config = LLMConfig()
        >>> client = LLMClient.from_config(config, "xiaomi/mimo-v2-flash:free")
        >>> response = await client.chat(messages, tools)
    """

    def __init__(self, provider_name: str, api_key: str, model_name: str, **kwargs):
        """LLMClientを初期化します。

        Args:
            provider_name: プロバイダー名（"openai", "openrouter", "anthropic"）
            api_key: API認証キー
            model_name: モデル名
            **kwargs: プロバイダー固有のパラメータ

        Raises:
            ValueError: 未対応のプロバイダー名の場合
        """
        self.provider = self._create_provider(
            provider_name, api_key, model_name, **kwargs
        )
        self.provider_name = provider_name
        self.model_name = model_name
        logger.info(
            "Initialized LLM client with provider: %s, model: %s",
            provider_name,
            model_name,
        )

    @classmethod
    def from_config(cls, config: LLMConfig, model_id: str, **kwargs) -> "LLMClient":
        """設定とモデルIDからLLMClientを作成します。

        Args:
            config: LLM設定
            model_id: モデルエイリアス（例: "xiaomi/mimo-v2-flash:free"）
            **kwargs: プロバイダー固有のパラメータ

        Returns:
            設定済みのLLMClientインスタンス

        Raises:
            ValueError: MODELS_CONFIGに存在しないモデルIDが指定された場合
            ValueError: 対応プロバイダーのAPIキーが未設定の場合

        Example:
            >>> config = LLMConfig.model_construct(
            ...     openrouter_api_key=SecretStr("sk-or")
            ... )
            >>> client = LLMClient.from_config(
            ...     config, "xiaomi/mimo-v2-flash:free"
            ... )
            >>> client.provider_name
            'openrouter'
        """
        # モデルIDからプロバイダー情報を取得
        if model_id not in MODELS_CONFIG:
            raise ValueError(
                f"invalid_model_name: Unknown model '{model_id}'. "
                f"Available models: {list(MODELS_CONFIG.keys())}"
            )

        model_config = MODELS_CONFIG[model_id]
        provider_name = model_config.provider

        # プロバイダーに対応するAPIキーを取得
        api_key = config.get_api_key(provider_name)

        # OpenRouterの場合はWeb検索設定を追加
        if provider_name == "openrouter":
            kwargs["enable_web_search"] = config.enable_web_search

        return cls(
            provider_name=provider_name,
            api_key=api_key,
            model_name=model_config.id,
            **kwargs,
        )

    def _create_provider(
        self, provider_name: str, api_key: str, model_name: str, **kwargs
    ) -> BaseLLMProvider:
        """プロバイダーファクトリ。

        Args:
            provider_name: プロバイダー名
            api_key: API認証キー
            model_name: モデル名
            **kwargs: プロバイダー固有のパラメータ

        Returns:
            プロバイダーインスタンス

        Raises:
            ValueError: 未対応のプロバイダー名の場合
        """
        provider_name_lower = provider_name.lower()

        if provider_name_lower == "openai":
            return OpenAIProvider(api_key, model_name)

        elif provider_name_lower == "openrouter":
            enable_web_search = kwargs.get("enable_web_search", False)
            return OpenAIProvider(
                api_key,
                model_name,
                base_url="https://openrouter.ai/api/v1",
                enable_web_search=enable_web_search,
            )

        elif provider_name_lower == "anthropic":
            return AnthropicProvider(api_key, model_name)

        else:
            raise ValueError(
                f"Unsupported provider: {provider_name}. "
                f"Supported: openai, openrouter, anthropic"
            )

    async def chat(
        self,
        messages: list[Message],
        tools: list[Tool] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> ChatResponse:
        """チャット補完リクエストを送信します。

        Args:
            messages: チャットメッセージ履歴
            tools: 利用可能なツール
            temperature: 生成の多様性
            max_tokens: 最大トークン数

        Returns:
            ChatResponse

        Raises:
            httpx.HTTPError: API呼び出しに失敗した場合
        """
        logger.debug("Sending chat request with %s messages", len(messages))
        if tools:
            logger.debug("Available tools: %s", [t.name for t in tools])

        return await self.provider.chat_completion(
            messages=messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[Tool] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[StreamChunk, None]:
        """チャット補完リクエストをストリーミングで送信します。

        Args:
            messages: チャットメッセージ履歴
            tools: 利用可能なツール
            temperature: 生成の多様性
            max_tokens: 最大トークン数

        Yields:
            StreamChunk: 各ストリーミングチャンク

        Raises:
            httpx.HTTPError: API呼び出しに失敗した場合
        """
        logger.debug("Sending chat stream request with %s messages", len(messages))
        if tools:
            logger.debug("Available tools: %s", [t.name for t in tools])

        async for chunk in self.provider.chat_completion_stream(
            messages=messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield chunk
