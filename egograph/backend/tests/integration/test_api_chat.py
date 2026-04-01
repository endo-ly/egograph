"""API/Chat統合テスト。"""

import json
from copy import deepcopy
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import backend.dependencies as deps
from backend.domain.models.llm import ChatResponse, Message, StreamChunk, ToolCall
from backend.infrastructure.database import ChatSQLiteConnection
from backend.infrastructure.repositories import ThreadRepository

JST = ZoneInfo("Asia/Tokyo")


class TestChatEndpoint:
    """Chatエンドポイントのテスト。"""

    def test_chat_requires_api_key(self, test_client):
        """API Keyが必要。"""
        # Arrange
        payload = {"messages": [{"role": "user", "content": "Hello"}]}

        # Act
        response = test_client.post("/v1/chat", json=payload)

        # Assert
        assert response.status_code == 401

    def test_chat_requires_llm_config(self, test_client, mock_backend_config):
        """LLM設定がないと501エラー。"""
        # Arrange
        config_without_llm = deepcopy(mock_backend_config)
        config_without_llm.llm = None
        test_client.app.dependency_overrides[deps.get_config] = (
            lambda: config_without_llm
        )
        payload = {"messages": [{"role": "user", "content": "Hello"}]}

        # Act
        response = test_client.post(
            "/v1/chat",
            json=payload,
            headers={"X-API-Key": "test-backend-key"},
        )

        # Assert
        assert response.status_code == 501
        assert "LLM configuration is missing" in response.json()["detail"]

    def test_chat_success(self, test_client, mock_backend_config):
        """チャットが成功する。"""
        # Arrange
        mock_response = ChatResponse(
            id="chatcmpl-test",
            message=Message(role="assistant", content="Here are your top tracks."),
            finish_reason="stop",
            usage={"prompt_tokens": 10, "completion_tokens": 20},
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

            mock_registry = MagicMock()
            mock_registry.get_all_schemas.return_value = []
            mock_registry_class.return_value = mock_registry

            payload = {"messages": [{"role": "user", "content": "Show me top tracks"}]}

            # Act
            response = test_client.post(
                "/v1/chat",
                json=payload,
                headers={"X-API-Key": "test-backend-key"},
            )

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "chatcmpl-test"
            assert data["message"]["role"] == "assistant"
            assert data["message"]["content"] == "Here are your top tracks."
            assert data["usage"] is not None

    def test_chat_with_tool_calls(self, test_client, mock_backend_config):
        """ツール呼び出しを実行して最終回答を返す。"""
        # Arrange
        tool_call_response = ChatResponse(
            id="chatcmpl-tool",
            message=Message(
                role="assistant",
                content="",
                tool_calls=[
                    ToolCall(
                        id="call_123",
                        name="get_top_tracks",
                        parameters={
                            "start_date": "2024-01-01",
                            "end_date": "2024-01-31",
                            "limit": 5,
                        },
                    )
                ],
            ),
            tool_calls=[
                ToolCall(
                    id="call_123",
                    name="get_top_tracks",
                    parameters={
                        "start_date": "2024-01-01",
                        "end_date": "2024-01-31",
                        "limit": 5,
                    },
                )
            ],
            finish_reason="tool_calls",
        )

        final_response = ChatResponse(
            id="chatcmpl-final",
            message=Message(
                role="assistant",
                content="Here are your top 5 tracks for January 2024.",
            ),
            finish_reason="stop",
            usage={"prompt_tokens": 50, "completion_tokens": 15},
        )

        with (
            patch("backend.usecases.chat.chat_usecase.LLMClient") as mock_llm_class,
            patch(
                "backend.usecases.chat.chat_usecase.ToolRegistry"
            ) as mock_registry_class,
        ):
            # クラスメソッド from_config をモック
            mock_llm_instance = MagicMock()
            mock_llm_instance.chat = AsyncMock(
                side_effect=[tool_call_response, final_response]
            )
            mock_llm_instance.chat_stream = AsyncMock()
            mock_llm_class.from_config = MagicMock(return_value=mock_llm_instance)

            mock_registry = MagicMock()
            mock_registry.get_all_schemas.return_value = []
            mock_registry.execute.return_value = {"tracks": []}
            mock_registry_class.return_value = mock_registry

            payload = {"messages": [{"role": "user", "content": "Show me top tracks"}]}

            # Act
            response = test_client.post(
                "/v1/chat",
                json=payload,
                headers={"X-API-Key": "test-backend-key"},
            )

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["tool_calls"] is None
            assert "top 5 tracks" in data["message"]["content"]
            assert mock_llm_instance.chat.call_count == 2

    def test_chat_handles_llm_error(self, test_client):
        """LLM APIエラーを502でハンドリング。"""
        # Arrange
        with (
            patch("backend.usecases.chat.chat_usecase.LLMClient") as mock_llm_class,
            patch(
                "backend.usecases.chat.chat_usecase.ToolRegistry"
            ) as mock_registry_class,
        ):
            # クラスメソッド from_config をモック
            mock_llm_instance = MagicMock()
            mock_llm_instance.chat = AsyncMock(side_effect=Exception("LLM API error"))
            mock_llm_instance.chat_stream = AsyncMock()
            mock_llm_class.from_config = MagicMock(return_value=mock_llm_instance)

            mock_registry = MagicMock()
            mock_registry.get_all_schemas.return_value = []
            mock_registry_class.return_value = mock_registry

            payload = {"messages": [{"role": "user", "content": "Hello"}]}

            # Act
            response = test_client.post(
                "/v1/chat",
                json=payload,
                headers={"X-API-Key": "test-backend-key"},
            )

            # Assert
            assert response.status_code == 502
            assert "LLM API error" in response.json()["detail"]

    def test_chat_validates_request_schema(self, test_client):
        """リクエストスキーマのバリデーション。"""
        # Arrange
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
            mock_registry = MagicMock()
            mock_registry.get_all_schemas.return_value = []
            mock_registry_class.return_value = mock_registry

            payload = {}

            # Act
            response = test_client.post(
                "/v1/chat",
                json=payload,
                headers={"X-API-Key": "test-backend-key"},
            )

            # Assert
            assert response.status_code == 422

    def test_chat_adds_system_message_with_date(self, test_client, mock_backend_config):
        """システムメッセージに現在日が追加される。"""
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

            mock_registry = MagicMock()
            mock_registry.get_all_schemas.return_value = []
            mock_registry_class.return_value = mock_registry

            payload = {"messages": [{"role": "user", "content": "Hello"}]}

            # Act
            response = test_client.post(
                "/v1/chat",
                json=payload,
                headers={"X-API-Key": "test-backend-key"},
            )

            # Assert
            assert response.status_code == 200

            mock_llm_instance.chat.assert_called_once()
            call_args = mock_llm_instance.chat.call_args
            messages = call_args.kwargs["messages"]

            assert len(messages) >= 2
            assert messages[0].role == "system"
            assert "現在日時" in messages[0].content
            assert "JST" in messages[0].content

            current_date = datetime.now(JST).strftime("%Y-%m-%d")
            assert current_date in messages[0].content

            assert messages[1].role == "user"
            assert messages[1].content == "Hello"

    def test_chat_does_not_duplicate_system_message(
        self, test_client, mock_backend_config
    ):
        """既にシステムメッセージがある場合は追加しない。"""
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

            mock_registry = MagicMock()
            mock_registry.get_all_schemas.return_value = []
            mock_registry_class.return_value = mock_registry

            payload = {
                "messages": [
                    {"role": "system", "content": "Custom system message"},
                    {"role": "user", "content": "Hello"},
                ]
            }

            # Act
            response = test_client.post(
                "/v1/chat",
                json=payload,
                headers={"X-API-Key": "test-backend-key"},
            )

            # Assert
            assert response.status_code == 200

            mock_llm_instance.chat.assert_called_once()
            call_args = mock_llm_instance.chat.call_args
            messages = call_args.kwargs["messages"]

            system_messages = [m for m in messages if m.role == "system"]
            assert len(system_messages) == 1
            assert system_messages[0].content == "Custom system message"


class TestChatStreamingEndpoint:
    """Chatストリーミングエンドポイントのテスト。"""

    def test_chat_streaming_requires_api_key(self, test_client):
        """ストリーミングもAPI Keyが必要。"""
        # Arrange
        payload = {"messages": [{"role": "user", "content": "Hello"}], "stream": True}

        # Act
        response = test_client.post("/v1/chat", json=payload)

        # Assert
        assert response.status_code == 401

    def test_chat_streaming_returns_sse_content_type(
        self,
        test_client,
        mock_backend_config,  # noqa: ARG002
    ):
        """ストリーミングレスポンスがtext/event-streamを返す。"""

        # Arrange
        async def mock_execute_loop_stream(*args, **kwargs):
            yield StreamChunk(type="done", finish_reason="stop")

        with (
            patch("backend.usecases.chat.chat_usecase.LLMClient") as mock_llm_class,
            patch(
                "backend.usecases.chat.chat_usecase.ToolRegistry"
            ) as mock_registry_class,
            patch(
                "backend.usecases.chat.chat_usecase.ToolExecutor"
            ) as mock_executor_class,
        ):
            mock_llm_instance = MagicMock()
            mock_llm_class.return_value = mock_llm_instance

            mock_registry = MagicMock()
            mock_registry.get_all_schemas.return_value = []
            mock_registry_class.return_value = mock_registry

            mock_executor_instance = MagicMock()
            mock_executor_instance.execute_loop_stream = mock_execute_loop_stream
            mock_executor_class.return_value = mock_executor_instance

            payload = {
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            }

            # Act
            response = test_client.post(
                "/v1/chat",
                json=payload,
                headers={"X-API-Key": "test-backend-key"},
            )

            # Assert
            assert response.status_code == 200
            assert (
                response.headers["content-type"] == "text/event-stream; charset=utf-8"
            )

    def test_chat_streaming_requires_llm_config(self, test_client, mock_backend_config):
        """LLM設定がない場合はストリーミングも501エラー。"""
        # Arrange
        config_without_llm = deepcopy(mock_backend_config)
        config_without_llm.llm = None
        test_client.app.dependency_overrides[deps.get_config] = (
            lambda: config_without_llm
        )
        payload = {"messages": [{"role": "user", "content": "Hello"}], "stream": True}

        # Act
        response = test_client.post(
            "/v1/chat",
            json=payload,
            headers={"X-API-Key": "test-backend-key"},
        )

        # Assert
        assert response.status_code == 501

    def test_chat_streaming_validates_model_name(
        self, test_client, mock_backend_config
    ):
        """ストリーミングでもモデル名のバリデーションが機能する。"""
        # Arrange
        payload = {
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
            "model_name": "invalid-model-name",
        }

        # Act
        response = test_client.post(
            "/v1/chat",
            json=payload,
            headers={"X-API-Key": "test-backend-key"},
        )

        # Assert
        assert response.status_code == 400

    def test_chat_streaming_saves_messages_to_db(
        self, test_client, mock_backend_config
    ):
        """ストリーミングモードでユーザー・アシスタント両方のメッセージがDBに保存される。"""

        # Arrange
        async def mock_execute_loop_stream(*args, **kwargs):
            yield StreamChunk(type="delta", delta="Hello, ")
            yield StreamChunk(type="delta", delta="how can I ")
            yield StreamChunk(type="delta", delta="help you?")
            yield StreamChunk(type="done", finish_reason="stop")

        with (
            patch("backend.usecases.chat.chat_usecase.LLMClient") as mock_llm_class,
            patch(
                "backend.usecases.chat.chat_usecase.ToolRegistry"
            ) as mock_registry_class,
            patch(
                "backend.usecases.chat.chat_usecase.ToolExecutor"
            ) as mock_executor_class,
        ):
            mock_llm_instance = MagicMock()
            mock_llm_class.return_value = mock_llm_instance

            mock_registry = MagicMock()
            mock_registry.get_all_schemas.return_value = []
            mock_registry_class.return_value = mock_registry

            mock_executor_instance = MagicMock()
            mock_executor_instance.execute_loop_stream = mock_execute_loop_stream
            mock_executor_class.return_value = mock_executor_instance

            payload = {
                "messages": [{"role": "user", "content": "Test question"}],
                "stream": True,
            }

            # Act
            response = test_client.post(
                "/v1/chat",
                json=payload,
                headers={"X-API-Key": "test-backend-key"},
            )

            # Assert
            assert response.status_code == 200

            thread_id = None
            response_text = response.text
            for line in response_text.split("\n"):
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    if data.get("thread_id"):
                        thread_id = data["thread_id"]

            assert thread_id is not None

            with ChatSQLiteConnection() as conn:
                messages = conn.execute(
                    """
                    SELECT role, content, model_name
                    FROM messages
                    WHERE thread_id = ?
                    ORDER BY created_at
                    """,
                    (thread_id,),
                ).fetchall()

                assert len(messages) == 2

                assert messages[0][0] == "user"
                assert messages[0][1] == "Test question"
                assert messages[0][2] is None

                assert messages[1][0] == "assistant"
                assert messages[1][1] == "Hello, how can I help you?"
                assert messages[1][2] == mock_backend_config.llm.default_model

    def test_chat_streaming_creates_new_thread(self, test_client, mock_backend_config):
        """ストリーミングモードで新規スレッドが作成される。"""

        # Arrange
        async def mock_execute_loop_stream(*args, **kwargs):
            yield StreamChunk(type="delta", delta="Response text")
            yield StreamChunk(type="done", finish_reason="stop")

        with (
            patch("backend.usecases.chat.chat_usecase.LLMClient") as mock_llm_class,
            patch(
                "backend.usecases.chat.chat_usecase.ToolRegistry"
            ) as mock_registry_class,
            patch(
                "backend.usecases.chat.chat_usecase.ToolExecutor"
            ) as mock_executor_class,
        ):
            mock_llm_instance = MagicMock()
            mock_llm_class.return_value = mock_llm_instance

            mock_registry = MagicMock()
            mock_registry.get_all_schemas.return_value = []
            mock_registry_class.return_value = mock_registry

            mock_executor_instance = MagicMock()
            mock_executor_instance.execute_loop_stream = mock_execute_loop_stream
            mock_executor_class.return_value = mock_executor_instance

            payload = {
                "messages": [{"role": "user", "content": "New thread message"}],
                "stream": True,
            }

            # Act
            response = test_client.post(
                "/v1/chat",
                json=payload,
                headers={"X-API-Key": "test-backend-key"},
            )

            # Assert
            assert response.status_code == 200

            thread_id = None
            response_text = response.text
            for line in response_text.split("\n"):
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    if data.get("thread_id"):
                        thread_id = data["thread_id"]

            assert thread_id is not None

            with ChatSQLiteConnection() as conn:
                thread = conn.execute(
                    "SELECT thread_id, title, user_id FROM threads WHERE thread_id = ?",
                    (thread_id,),
                ).fetchone()

                assert thread is not None
                assert thread[0] == thread_id
                assert thread[1] == "New thread message"
                assert thread[2] == "default_user"

    def test_chat_streaming_appends_to_existing_thread(
        self, test_client, mock_backend_config
    ):
        """ストリーミングモードで既存スレッドにメッセージが追加される。"""
        # Arrange
        with ChatSQLiteConnection() as conn:
            repo = ThreadRepository(conn)
            thread = repo.create_thread("default_user", "Existing thread")
            existing_thread_id = thread.thread_id

        async def mock_execute_loop_stream(*args, **kwargs):
            yield StreamChunk(type="delta", delta="Follow-up response")
            yield StreamChunk(type="done", finish_reason="stop")

        with (
            patch("backend.usecases.chat.chat_usecase.LLMClient") as mock_llm_class,
            patch(
                "backend.usecases.chat.chat_usecase.ToolRegistry"
            ) as mock_registry_class,
            patch(
                "backend.usecases.chat.chat_usecase.ToolExecutor"
            ) as mock_executor_class,
        ):
            mock_llm_instance = MagicMock()
            mock_llm_class.return_value = mock_llm_instance

            mock_registry = MagicMock()
            mock_registry.get_all_schemas.return_value = []
            mock_registry_class.return_value = mock_registry

            mock_executor_instance = MagicMock()
            mock_executor_instance.execute_loop_stream = mock_execute_loop_stream
            mock_executor_class.return_value = mock_executor_instance

            payload = {
                "messages": [{"role": "user", "content": "Follow-up question"}],
                "stream": True,
                "thread_id": existing_thread_id,
            }

            # Act
            response = test_client.post(
                "/v1/chat",
                json=payload,
                headers={"X-API-Key": "test-backend-key"},
            )

            # Assert
            assert response.status_code == 200

            with ChatSQLiteConnection() as conn:
                messages = conn.execute(
                    """
                    SELECT role, content
                    FROM messages
                    WHERE thread_id = ?
                    ORDER BY created_at
                    """,
                    (existing_thread_id,),
                ).fetchall()

                assert len(messages) == 2
                assert messages[0][0] == "user"
                assert messages[0][1] == "Follow-up question"
                assert messages[1][0] == "assistant"
                assert messages[1][1] == "Follow-up response"

    def test_chat_streaming_handles_empty_response(
        self, test_client, mock_backend_config
    ):
        """ストリーミングで空のアシスタント応答の場合、メッセージを保存しない。"""

        # Arrange
        async def mock_execute_loop_stream(*args, **kwargs):
            yield StreamChunk(type="done", finish_reason="stop")

        with (
            patch("backend.usecases.chat.chat_usecase.LLMClient") as mock_llm_class,
            patch(
                "backend.usecases.chat.chat_usecase.ToolRegistry"
            ) as mock_registry_class,
            patch(
                "backend.usecases.chat.chat_usecase.ToolExecutor"
            ) as mock_executor_class,
        ):
            mock_llm_instance = MagicMock()
            mock_llm_class.return_value = mock_llm_instance

            mock_registry = MagicMock()
            mock_registry.get_all_schemas.return_value = []
            mock_registry_class.return_value = mock_registry

            mock_executor_instance = MagicMock()
            mock_executor_instance.execute_loop_stream = mock_execute_loop_stream
            mock_executor_class.return_value = mock_executor_instance

            payload = {
                "messages": [{"role": "user", "content": "Test"}],
                "stream": True,
            }

            # Act
            response = test_client.post(
                "/v1/chat",
                json=payload,
                headers={"X-API-Key": "test-backend-key"},
            )

            # Assert
            assert response.status_code == 200

            thread_id = None
            response_text = response.text
            for line in response_text.split("\n"):
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    if data.get("thread_id"):
                        thread_id = data["thread_id"]

            with ChatSQLiteConnection() as conn:
                messages = conn.execute(
                    "SELECT role, content FROM messages WHERE thread_id = ?",
                    (thread_id,),
                ).fetchall()

                assert len(messages) == 1
                assert messages[0][0] == "user"
                assert messages[0][1] == "Test"
