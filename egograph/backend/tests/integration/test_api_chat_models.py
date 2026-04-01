"""Chat API LLMモデル選択機能の統合テスト。"""

from unittest.mock import AsyncMock, MagicMock, patch

from backend.api.schemas import DEFAULT_MODEL
from backend.infrastructure.llm import ChatResponse, Message


class TestChatModelsEndpoint:
    """/v1/chat/models エンドポイントのテスト。"""

    def test_get_models_requires_api_key(self, test_client):
        """API Keyが必要。"""
        # Act
        response = test_client.get("/v1/chat/models")

        # Assert
        assert response.status_code == 401

    def test_get_models_returns_model_list(self, test_client):
        """モデル一覧が正しく返される。"""
        # Act
        response = test_client.get(
            "/v1/chat/models",
            headers={"X-API-Key": "test-backend-key"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        assert isinstance(data["models"], list)
        assert len(data["models"]) > 0

        # 各モデルが必要なフィールドを持つことを確認
        for model in data["models"]:
            assert "id" in model
            assert "name" in model
            assert "provider" in model
            assert "input_cost_per_1m" in model
            assert "output_cost_per_1m" in model
            assert "is_free" in model

    def test_get_models_includes_default_model(self, test_client):
        """デフォルトモデルが含まれる。"""
        # Act
        response = test_client.get(
            "/v1/chat/models",
            headers={"X-API-Key": "test-backend-key"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        model_ids = [model["id"] for model in data["models"]]
        assert DEFAULT_MODEL in model_ids


class TestChatEndpointModelSelection:
    """/v1/chat エンドポイントのモデル選択機能のテスト。"""

    def test_chat_uses_specified_model(self, test_client, mock_backend_config):
        """model_nameパラメータが指定された場合、そのモデルが使用される。"""
        # Arrange
        specified_model = "deepseek/deepseek-v3.2"
        mock_response = ChatResponse(
            id="chatcmpl-test",
            message=Message(role="assistant", content="Test response"),
            finish_reason="stop",
        )

        with (
            patch("backend.usecases.chat.chat_usecase.LLMClient") as mock_llm_class,
            patch(
                "backend.usecases.chat.chat_usecase.ToolRegistry"
            ) as mock_registry_class,
        ):
            # クラスメソッド from_config をモック
            mock_llm_instance = MagicMock()
            mock_llm_instance.chat = AsyncMock(return_value=mock_response)
            mock_llm_instance.chat_stream = AsyncMock()
            mock_llm_class.from_config = MagicMock(return_value=mock_llm_instance)

            # ToolRegistryのモック
            mock_registry = MagicMock()
            mock_registry.get_all_schemas.return_value = []
            mock_registry_class.return_value = mock_registry

            # Act
            response = test_client.post(
                "/v1/chat",
                json={
                    "messages": [{"role": "user", "content": "Hello"}],
                    "model_name": specified_model,
                },
                headers={"X-API-Key": "test-backend-key"},
            )

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["model_name"] == specified_model

            # LLMClient.from_config が呼ばれたことを確認
            mock_llm_class.from_config.assert_called_once()

    def test_chat_uses_default_model_when_not_specified(
        self, test_client, mock_backend_config
    ):
        """model_nameパラメータが指定されない場合、デフォルトモデルが使用される。"""
        # Arrange
        mock_response = ChatResponse(
            id="chatcmpl-test",
            message=Message(role="assistant", content="Test response"),
            finish_reason="stop",
        )

        with (
            patch("backend.usecases.chat.chat_usecase.LLMClient") as mock_llm_class,
            patch(
                "backend.usecases.chat.chat_usecase.ToolRegistry"
            ) as mock_registry_class,
        ):
            # クラスメソッド from_config をモック
            mock_llm_instance = MagicMock()
            mock_llm_instance.chat = AsyncMock(return_value=mock_response)
            mock_llm_instance.chat_stream = AsyncMock()
            mock_llm_class.from_config = MagicMock(return_value=mock_llm_instance)

            # ToolRegistryのモック
            mock_registry = MagicMock()
            mock_registry.get_all_schemas.return_value = []
            mock_registry_class.return_value = mock_registry

            # Act
            response = test_client.post(
                "/v1/chat",
                json={"messages": [{"role": "user", "content": "Hello"}]},
                headers={"X-API-Key": "test-backend-key"},
            )

            # Assert
            assert response.status_code == 200
            data = response.json()

            # デフォルトモデル（設定値）が使用されることを確認
            expected_model = mock_backend_config.llm.default_model
            assert data["model_name"] == expected_model

            # LLMClient.from_config が呼ばれたことを確認
            mock_llm_class.from_config.assert_called_once()

    def test_chat_returns_error_for_invalid_model(self, test_client):
        """無効なmodel_nameでエラーが返される。"""
        # Arrange
        invalid_model = "nonexistent-model"

        with (
            patch("backend.usecases.chat.chat_usecase.LLMClient") as mock_llm_class,
            patch(
                "backend.usecases.chat.chat_usecase.ToolRegistry"
            ) as mock_registry_class,
        ):
            # クラスメソッド from_config をモック
            mock_llm_instance = MagicMock()
            mock_llm_instance.chat = AsyncMock()
            mock_llm_instance.chat_stream = AsyncMock()
            mock_llm_class.from_config = MagicMock(return_value=mock_llm_instance)

            # ToolRegistryのモック
            mock_registry = MagicMock()
            mock_registry.get_all_schemas.return_value = []
            mock_registry_class.return_value = mock_registry

            # Act
            response = test_client.post(
                "/v1/chat",
                json={
                    "messages": [{"role": "user", "content": "Hello"}],
                    "model_name": invalid_model,
                },
                headers={"X-API-Key": "test-backend-key"},
            )

            # Assert
            assert response.status_code == 400
            assert "invalid_model_name" in response.json()["detail"]

    def test_chat_response_includes_model_name(self, test_client, mock_backend_config):
        """レスポンスにmodel_nameが含まれる。"""
        # Arrange
        mock_response = ChatResponse(
            id="chatcmpl-test",
            message=Message(role="assistant", content="Test response"),
            finish_reason="stop",
        )

        with (
            patch("backend.usecases.chat.chat_usecase.LLMClient") as mock_llm_class,
            patch(
                "backend.usecases.chat.chat_usecase.ToolRegistry"
            ) as mock_registry_class,
        ):
            # クラスメソッド from_config をモック
            mock_llm_instance = MagicMock()
            mock_llm_instance.chat = AsyncMock(return_value=mock_response)
            mock_llm_instance.chat_stream = AsyncMock()
            mock_llm_class.from_config = MagicMock(return_value=mock_llm_instance)

            # ToolRegistryのモック
            mock_registry = MagicMock()
            mock_registry.get_all_schemas.return_value = []
            mock_registry_class.return_value = mock_registry

            # Act
            response = test_client.post(
                "/v1/chat",
                json={"messages": [{"role": "user", "content": "Hello"}]},
                headers={"X-API-Key": "test-backend-key"},
            )

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert "model_name" in data
            assert data["model_name"] == mock_backend_config.llm.default_model

    def test_chat_saves_model_name_to_database(self, test_client, mock_backend_config):
        """使用したモデル名がDBに保存される。"""
        # Arrange
        specified_model = "deepseek/deepseek-v3.2"
        mock_response = ChatResponse(
            id="chatcmpl-test",
            message=Message(role="assistant", content="Test response"),
            finish_reason="stop",
        )

        with (
            patch("backend.usecases.chat.chat_usecase.LLMClient") as mock_llm_class,
            patch(
                "backend.usecases.chat.chat_usecase.ToolRegistry"
            ) as mock_registry_class,
            patch("backend.api.chat.ThreadRepository") as mock_thread_service_class,
        ):
            # クラスメソッド from_config をモック
            mock_llm_instance = MagicMock()
            mock_llm_instance.chat = AsyncMock(return_value=mock_response)
            mock_llm_instance.chat_stream = AsyncMock()
            mock_llm_class.from_config = MagicMock(return_value=mock_llm_instance)

            # ToolRegistryのモック
            mock_registry = MagicMock()
            mock_registry.get_all_schemas.return_value = []
            mock_registry_class.return_value = mock_registry

            # ThreadServiceのモック
            mock_thread_service = MagicMock()
            mock_thread = MagicMock()
            mock_thread.thread_id = "test-thread-id"
            mock_thread_service.create_thread.return_value = mock_thread
            mock_thread_service_class.return_value = mock_thread_service

            # Act
            response = test_client.post(
                "/v1/chat",
                json={
                    "messages": [{"role": "user", "content": "Hello"}],
                    "model_name": specified_model,
                },
                headers={"X-API-Key": "test-backend-key"},
            )

            # Assert
            assert response.status_code == 200

            # add_messageが2回呼ばれる（user, assistant）
            assert mock_thread_service.add_message.call_count == 2

            # 2回目（assistantメッセージ）の呼び出しでmodel_nameが渡されていることを確認
            assistant_call = mock_thread_service.add_message.call_args_list[1]
            assert assistant_call.args[0].model_name == specified_model
            assert assistant_call.args[0].role == "assistant"
