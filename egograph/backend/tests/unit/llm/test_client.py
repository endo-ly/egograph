"""LLM/Client層のテスト。"""

from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr

from backend.config import LLMConfig
from backend.domain.models.llm_model import MODELS_CONFIG, LLMModel
from backend.infrastructure.llm import (
    AnthropicProvider,
    ChatResponse,
    LLMClient,
    Message,
    OpenAIProvider,
)


class TestLLMClient:
    """LLMClientのテスト。"""

    def test_creates_openai_provider(self):
        """OpenAIプロバイダーを作成。"""
        # Arrange: プロバイダー名とモデル名を準備
        provider_name = "openai"
        model_name = "gpt-4o-mini"

        # Act: LLMClientを作成
        client = LLMClient(provider_name, "test-key", model_name)

        # Assert: OpenAIプロバイダーが作成されることを検証
        assert isinstance(client.provider, OpenAIProvider)
        assert client.provider.model_name == "gpt-4o-mini"

    def test_creates_openrouter_provider(self):
        """OpenRouterプロバイダーを作成。"""
        # Arrange: OpenRouterのプロバイダー名とモデル名を準備
        provider_name = "openrouter"
        model_name = "meta-llama/llama-3.1-70b-instruct"

        # Act: LLMClientを作成
        client = LLMClient(provider_name, "test-key", model_name)

        # Assert: OpenRouterプロバイダー（OpenAI互換）が作成されることを検証
        assert isinstance(client.provider, OpenAIProvider)
        assert "openrouter.ai" in client.provider.base_url

    def test_creates_anthropic_provider(self):
        """Anthropicプロバイダーを作成。"""
        # Arrange: Anthropicのプロバイダー名とモデル名を準備
        provider_name = "anthropic"
        model_name = "anthropic/test-model"

        # Act: LLMClientを作成
        client = LLMClient(provider_name, "test-key", model_name)

        # Assert: Anthropicプロバイダーが作成されることを検証
        assert isinstance(client.provider, AnthropicProvider)
        assert client.provider.model_name == "anthropic/test-model"

    def test_raises_error_for_unsupported_provider(self):
        """未対応プロバイダーでエラー。"""
        # Arrange: 未対応のプロバイダー名を準備
        invalid_provider = "invalid_provider"

        # Act & Assert: ValueErrorが発生することを検証
        with pytest.raises(ValueError, match="Unsupported provider"):
            LLMClient(invalid_provider, "test-key", "model-name")

    def test_provider_name_is_case_insensitive(self):
        """プロバイダー名は大文字小文字を区別しない。"""
        # Arrange: 大文字と小文字のプロバイダー名を準備
        provider_upper = "OPENAI"
        provider_lower = "openai"

        # Act: 両方のプロバイダー名でLLMClientを作成
        client_upper = LLMClient(provider_upper, "test-key", "gpt-4o-mini")
        client_lower = LLMClient(provider_lower, "test-key", "gpt-4o-mini")

        # Assert: どちらもOpenAIプロバイダーが作成されることを検証
        assert isinstance(client_upper.provider, OpenAIProvider)
        assert isinstance(client_lower.provider, OpenAIProvider)

    @pytest.mark.asyncio
    async def test_chat_delegates_to_provider(self, monkeypatch):
        """chatメソッドがプロバイダーに委譲される。"""
        # Arrange: プロバイダーのchat_completionをモック
        mock_response = ChatResponse(
            id="test-123",
            message=Message(role="assistant", content="Test response"),
            finish_reason="stop",
        )

        mock_chat_completion = AsyncMock(return_value=mock_response)
        monkeypatch.setattr(
            "backend.infrastructure.llm.providers.openai.OpenAIProvider.chat_completion",
            mock_chat_completion,
        )

        client = LLMClient("openai", "test-key", "gpt-4o-mini")
        messages = [Message(role="user", content="Hello")]

        # Act: chatメソッドを実行
        response = await client.chat(messages, temperature=0.5, max_tokens=1024)

        # Assert: プロバイダーに正しく委譲されることを検証
        assert response == mock_response
        mock_chat_completion.assert_called_once()
        call_kwargs = mock_chat_completion.call_args.kwargs
        assert call_kwargs["messages"] == messages
        assert call_kwargs["temperature"] == 0.5
        assert call_kwargs["max_tokens"] == 1024


class TestLLMClientFromConfig:
    """LLMClient.from_configメソッドのテスト。"""

    def test_from_config_openai_model(self):
        """OpenAIモデルでLLMClientを作成。"""
        # Arrange: OpenAIプロバイダーのAPIキーを設定
        config = LLMConfig.model_construct(
            openai_api_key=SecretStr("sk-test-openai"),
        )
        # MODELS_CONFIG に存在する glm-4.7 を使用（openai プロバイダー）
        model_id = "glm-4.7"

        # Act: from_configでLLMClientを作成
        client = LLMClient.from_config(config, model_id)

        # Assert: OpenAIプロバイダーが作成されることを検証
        assert isinstance(client.provider, OpenAIProvider)
        assert client.provider_name == "openai"
        assert client.model_name == model_id

    def test_from_config_openrouter_model(self):
        """OpenRouterモデルでLLMClientを作成。"""
        # Arrange: OpenRouterプロバイダーのAPIキーを設定
        config = LLMConfig.model_construct(
            openrouter_api_key=SecretStr("sk-or-test"),
            enable_web_search=True,
        )
        model_id = "deepseek/deepseek-v3.2"

        # Act: from_configでLLMClientを作成
        client = LLMClient.from_config(config, model_id)

        # Assert: OpenRouterプロバイダーが作成されることを検証
        assert isinstance(client.provider, OpenAIProvider)
        assert client.provider_name == "openrouter"
        assert client.provider.enable_web_search is True

    def test_from_config_anthropic_model(self, monkeypatch):
        """AnthropicプロバイダーでLLMClientを作成。"""
        # Arrange: AnthropicプロバイダーのAPIキーを設定
        config = LLMConfig.model_construct(
            anthropic_api_key=SecretStr("sk-ant-test"),
        )
        model_id = "anthropic/test-model"
        test_models = {
            **MODELS_CONFIG,
            model_id: LLMModel(
                id=model_id,
                name="Anthropic Test Model",
                provider="anthropic",
                input_cost_per_1m=0.0,
                output_cost_per_1m=0.0,
                is_free=True,
            ),
        }
        monkeypatch.setattr(
            "backend.infrastructure.llm.client.MODELS_CONFIG", test_models
        )

        # Act: from_configでLLMClientを作成
        client = LLMClient.from_config(config, model_id)
        assert isinstance(client.provider, AnthropicProvider)
        assert client.provider_name == "anthropic"

    def test_from_config_invalid_model_raises_error(self):
        """無効なモデルIDでエラーが発生する。"""
        # Arrange
        config = LLMConfig.model_construct(
            openai_api_key=SecretStr("sk-test"),
        )
        invalid_model_id = "invalid/model"

        # Act & Assert: ValueErrorが発生することを検証
        with pytest.raises(ValueError, match="invalid_model_name"):
            LLMClient.from_config(config, invalid_model_id)

    def test_from_config_missing_api_key_raises_error(self):
        """APIキーが未設定の場合にエラーが発生する。"""
        # Arrange: APIキー未設定の設定
        config = LLMConfig.model_construct()
        # MODELS_CONFIG に存在する glm-4.7 を使用（openai プロバイダー）
        model_id = "glm-4.7"

        # Act & Assert: ValueErrorが発生することを検証
        with pytest.raises(ValueError, match="OPENAI_API_KEY is not set"):
            LLMClient.from_config(config, model_id)
