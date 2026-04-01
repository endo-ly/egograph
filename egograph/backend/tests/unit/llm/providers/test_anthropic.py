"""LLM/Providers/Anthropic層のテスト。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.infrastructure.llm import AnthropicProvider, Message, ToolCall
from backend.usecases.tools import Tool


class TestAnthropicProvider:
    """AnthropicProviderのテスト。"""

    def test_initialization(self):
        """初期化のテスト。"""
        # Arrange & Act: プロバイダーを初期化
        provider = AnthropicProvider("test-key", "claude-3-5-sonnet-20241022")

        # Assert: 設定値が正しく保存されることを検証
        assert provider.api_key == "test-key"
        assert provider.model_name == "claude-3-5-sonnet-20241022"
        assert provider.base_url == "https://api.anthropic.com/v1"
        assert provider.api_version == "2023-06-01"

    def test_convert_tools_to_provider_format(self):
        """ツールをAnthropic形式に変換。"""
        # Arrange: プロバイダーとツールスキーマを準備
        provider = AnthropicProvider("test-key", "claude-3-5-sonnet-20241022")

        tools = [
            Tool(
                name="get_stats",
                description="Get listening stats",
                inputSchema={
                    "type": "object",
                    "properties": {"limit": {"type": "integer"}},
                },
            )
        ]

        # Act: Anthropic形式に変換
        result = provider._convert_tools_to_provider_format(tools)

        # Assert: 変換結果を検証
        assert len(result) == 1
        assert result[0]["name"] == "get_stats"
        assert result[0]["description"] == "Get listening stats"
        assert result[0]["input_schema"] == tools[0].inputSchema

    def test_parse_response_simple(self):
        """シンプルなレスポンスのパース。"""
        # Arrange: プロバイダーとシンプルなレスポンスデータを準備
        provider = AnthropicProvider("test-key", "claude-3-5-sonnet-20241022")

        raw_response = {
            "id": "msg_123",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Hello!"}],
            "model": "claude-3-5-sonnet-20241022",
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }

        # Act: レスポンスをパース
        response = provider._parse_response(raw_response)

        # Assert: パース結果を検証
        assert response.id == "msg_123"
        assert response.message.role == "assistant"
        assert response.message.content == "Hello!"
        assert response.finish_reason == "end_turn"
        assert response.usage == {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        }
        assert response.tool_calls is None

    def test_parse_response_with_tool_use(self):
        """ツール呼び出しを含むレスポンスのパース。"""
        # Arrange: プロバイダーとツール使用を含むレスポンスデータを準備
        provider = AnthropicProvider("test-key", "claude-3-5-sonnet-20241022")

        raw_response = {
            "id": "msg_456",
            "type": "message",
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Let me check your stats."},
                {
                    "type": "tool_use",
                    "id": "toolu_123",
                    "name": "get_stats",
                    "input": {"limit": 10},
                },
            ],
            "model": "claude-3-5-sonnet-20241022",
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 20, "output_tokens": 30},
        }

        # Act: レスポンスをパース
        response = provider._parse_response(raw_response)

        # Assert: ツール呼び出し情報が正しく抽出されることを検証
        assert response.id == "msg_456"
        assert response.message.content == "Let me check your stats."
        assert response.tool_calls is not None
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].id == "toolu_123"
        assert response.tool_calls[0].name == "get_stats"
        assert response.tool_calls[0].parameters == {"limit": 10}
        assert response.finish_reason == "tool_use"

    def test_parse_response_multiple_text_blocks(self):
        """複数のテキストブロックを結合してパース。"""
        # Arrange: プロバイダーと複数のテキストブロックを含むレスポンスを準備
        provider = AnthropicProvider("test-key", "claude-3-5-sonnet-20241022")

        raw_response = {
            "id": "msg_789",
            "type": "message",
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Part 1. "},
                {"type": "text", "text": "Part 2."},
            ],
            "model": "claude-3-5-sonnet-20241022",
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 15, "output_tokens": 10},
        }

        # Act: レスポンスをパース
        response = provider._parse_response(raw_response)

        # Assert: 複数のテキストブロックが結合されることを検証
        assert response.message.content == "Part 1. Part 2."

    @pytest.mark.asyncio
    async def test_chat_completion_separates_system_message(self):
        """systemメッセージを正しく分離する。"""
        # Arrange: プロバイダーとsystemメッセージを含むメッセージリストを準備
        provider = AnthropicProvider("test-key", "claude-3-5-sonnet-20241022")

        messages = [
            Message(role="system", content="You are a helpful assistant."),
            Message(role="user", content="Hello"),
        ]

        # httpx.AsyncClientをモック
        with patch(
            "backend.infrastructure.llm.providers.anthropic.httpx.AsyncClient"
        ) as mock_client_class:
            # レスポンスモック
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(
                return_value={
                    "id": "msg_test",
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Hi!"}],
                    "model": "claude-3-5-sonnet-20241022",
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                }
            )
            mock_response.raise_for_status = MagicMock()
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client_instance

            # Act: チャット補完を実行
            response = await provider.chat_completion(messages)

            # Assert: systemメッセージが分離され、正しく送信されることを検証
            assert response.message.content == "Hi!"

            # POST呼び出しのペイロードを確認
            call_args = mock_client_instance.post.call_args
            payload = call_args.kwargs["json"]

            # systemメッセージは別フィールドに分離されている
            assert "system" in payload
            assert payload["system"] == "You are a helpful assistant."
            # messagesにはuser/assistantのみ
            assert len(payload["messages"]) == 1
            assert payload["messages"][0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_chat_completion_success(self):
        """チャット補完が成功する。"""
        # Arrange: プロバイダー、メッセージ、HTTPクライアントのモックを準備
        provider = AnthropicProvider("test-key", "claude-3-5-sonnet-20241022")

        messages = [Message(role="user", content="Hello")]

        # httpx.AsyncClientをモック
        with patch(
            "backend.infrastructure.llm.providers.anthropic.httpx.AsyncClient"
        ) as mock_client_class:
            # レスポンスモック
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(
                return_value={
                    "id": "msg_test",
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Hi there!"}],
                    "model": "claude-3-5-sonnet-20241022",
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 10, "output_tokens": 20},
                }
            )
            mock_response.raise_for_status = MagicMock()
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client_instance

            # Act: チャット補完を実行
            response = await provider.chat_completion(messages)

            # Assert: レスポンスとAPI呼び出しが正しいことを検証
            assert response.message.content == "Hi there!"
            mock_client_instance.post.assert_called_once()

            # ヘッダー確認
            call_args = mock_client_instance.post.call_args
            headers = call_args.kwargs["headers"]
            assert "x-api-key" in headers
            assert "anthropic-version" in headers

    def test_convert_message_to_anthropic_basic(self):
        """基本メッセージの変換をテスト。"""
        # Arrange: プロバイダーと基本メッセージを準備
        provider = AnthropicProvider("test-key", "claude-3-5-sonnet-20241022")
        msg = Message(role="user", content="Hello")

        # Act: Anthropic形式に変換
        result = provider._convert_message_to_anthropic(msg)

        # Assert: 基本メッセージが正しく変換されることを検証
        assert result == {"role": "user", "content": "Hello"}

    def test_convert_message_with_tool_use(self):
        """assistant + tool_calls の変換をテスト。"""
        # Arrange: プロバイダーとツール呼び出しを含むassistantメッセージを準備
        provider = AnthropicProvider("test-key", "claude-3-5-sonnet-20241022")
        msg = Message(
            role="assistant",
            content="Let me check that for you.",
            tool_calls=[
                ToolCall(
                    id="toolu_123",
                    name="get_stats",
                    parameters={"limit": 10},
                )
            ],
        )

        # Act: Anthropic形式に変換
        result = provider._convert_message_to_anthropic(msg)

        # Assert: tool_callsがtool_useブロックに変換されることを検証
        assert result["role"] == "assistant"
        assert isinstance(result["content"], list)
        assert len(result["content"]) == 2

        # テキストブロック
        assert result["content"][0] == {
            "type": "text",
            "text": "Let me check that for you.",
        }

        # tool_useブロック
        assert result["content"][1] == {
            "type": "tool_use",
            "id": "toolu_123",
            "name": "get_stats",
            "input": {"limit": 10},
        }

    def test_convert_message_with_tool_use_no_text(self):
        """テキストなしでtool_callsのみのメッセージを変換。"""
        # Arrange: プロバイダーとツール呼び出しのみのメッセージを準備
        provider = AnthropicProvider("test-key", "claude-3-5-sonnet-20241022")
        msg = Message(
            role="assistant",
            content=None,
            tool_calls=[
                ToolCall(
                    id="toolu_456",
                    name="search",
                    parameters={"query": "test"},
                )
            ],
        )

        # Act: Anthropic形式に変換
        result = provider._convert_message_to_anthropic(msg)

        # Assert: tool_useブロックのみが含まれることを検証
        assert result["role"] == "assistant"
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "tool_use"

    def test_convert_tool_result_to_anthropic(self):
        """role="tool" メッセージの変換をテスト。"""
        # Arrange: プロバイダーとツール結果メッセージを準備
        provider = AnthropicProvider("test-key", "claude-3-5-sonnet-20241022")
        msg = Message(
            role="tool",
            content="Result data",
            tool_call_id="toolu_123",
        )

        # Act: Anthropic形式に変換
        result = provider._convert_tool_result_to_anthropic(msg)

        # Assert: role="user"でtool_resultブロックに変換されることを検証
        assert result["role"] == "user"
        assert isinstance(result["content"], list)
        assert len(result["content"]) == 1
        assert result["content"][0] == {
            "type": "tool_result",
            "tool_use_id": "toolu_123",
            "content": "Result data",
        }

    def test_convert_tool_result_requires_tool_call_id(self):
        """tool_call_id が必須であることをテスト。"""
        # Arrange: プロバイダーとtool_call_idなしのツール結果メッセージを準備
        provider = AnthropicProvider("test-key", "claude-3-5-sonnet-20241022")
        msg = Message(
            role="tool",
            content="Result data",
            # tool_call_id が None
        )

        # Act & Assert: tool_call_idなしでValueErrorが発生することを検証
        with pytest.raises(ValueError) as exc_info:
            provider._convert_tool_result_to_anthropic(msg)

        assert "invalid_tool_result" in str(exc_info.value)
        assert "tool_call_id is required" in str(exc_info.value)

    def test_parse_response_preserves_tool_calls(self):
        """_parse_response が tool_calls を保存することをテスト。"""
        # Arrange: プロバイダーとツール使用を含むレスポンスデータを準備
        provider = AnthropicProvider("test-key", "claude-3-5-sonnet-20241022")

        raw_response = {
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_abc",
                    "name": "get_weather",
                    "input": {"location": "Tokyo"},
                }
            ],
            "model": "claude-3-5-sonnet-20241022",
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 50, "output_tokens": 30},
        }

        # Act: レスポンスをパース
        response = provider._parse_response(raw_response)

        # Assert: messageにtool_callsが保存されることを検証（ToolCallオブジェクト）
        assert response.message.tool_calls is not None
        assert len(response.message.tool_calls) == 1
        assert response.message.tool_calls[0].id == "toolu_abc"
        assert response.message.tool_calls[0].name == "get_weather"
        assert response.message.tool_calls[0].parameters == {"location": "Tokyo"}

        # ChatResponse.tool_callsにも保存されることを確認
        assert response.tool_calls is not None
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].id == "toolu_abc"

    def test_parse_response_empty_content_with_tool_calls(self):
        """contentが空でtool_callsのみのレスポンスをパース。"""
        # Arrange: プロバイダーとテキストなしツール使用レスポンスを準備
        provider = AnthropicProvider("test-key", "claude-3-5-sonnet-20241022")

        raw_response = {
            "id": "msg_test2",
            "type": "message",
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_xyz",
                    "name": "calculator",
                    "input": {"expression": "2+2"},
                }
            ],
            "model": "claude-3-5-sonnet-20241022",
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 20, "output_tokens": 15},
        }

        # Act: レスポンスをパース
        response = provider._parse_response(raw_response)

        # Assert: contentがNoneでtool_callsが保存されることを検証
        assert response.message.content is None
        assert response.message.tool_calls is not None
        assert len(response.message.tool_calls) == 1
        assert response.message.tool_calls[0].id == "toolu_xyz"

    @pytest.mark.asyncio
    async def test_chat_completion_stream_success(self):
        """ストリーミングチャット補完が成功する。"""
        # Arrange: プロバイダーとメッセージを準備
        provider = AnthropicProvider("test-key", "claude-3-5-sonnet-20241022")
        messages = [Message(role="user", content="Tell me a story")]

        # ストリーミングレスポンスをモック
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        # Anthropicストリーミングイベントをモック
        async def mock_iter_lines():
            lines = [
                # テキストチャンク（event: + data: の2行形式）
                "event: content_block_delta",
                'data: {"type": "content_block_delta", "index": 0, "content_block": {"type": "text"}, "delta": {"type": "text_delta", "text": "Once"}}',  # noqa: E501
                "",
                "event: content_block_delta",
                'data: {"type": "content_block_delta", "index": 0, "content_block": {"type": "text"}, "delta": {"type": "text_delta", "text": " upon"}}',  # noqa: E501
                "",
                "event: content_block_delta",
                'data: {"type": "content_block_delta", "index": 0, "content_block": {"type": "text"}, "delta": {"type": "text_delta", "text": " a time"}}',  # noqa: E501
                "",
                # 完了イベント
                "event: message_delta",
                'data: {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"input_tokens": 10, "output_tokens": 15}}',  # noqa: E501
                "",
                "event: message_stop",
                'data: {"type": "message_stop", "stop_reason": "end_turn"}',
                "",
            ]
            for line in lines:
                yield line

        mock_response.aiter_lines = mock_iter_lines

        # AsyncMockContextManagerを使ってストリーミングレスポンスをモック
        mock_async_context = MagicMock()
        mock_async_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_async_context.__aexit__ = AsyncMock(return_value=None)

        # httpx.AsyncClientをモック
        with patch(
            "backend.infrastructure.llm.providers.anthropic.httpx.AsyncClient"
        ) as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_instance.stream = MagicMock(return_value=mock_async_context)
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client_instance

            # Act: ストリーミングチャット補完を実行
            chunks = []
            async for chunk in provider.chat_completion_stream(messages):
                chunks.append(chunk)

            # Assert: 正しいチャンクが返されることを検証
            assert len(chunks) == 4  # 3つのdelta + 1つのdone

            # deltaチャンクの確認
            assert chunks[0].type == "delta"
            assert chunks[0].delta == "Once"
            assert chunks[1].delta == " upon"
            assert chunks[2].delta == " a time"

            # doneチャンクの確認
            assert chunks[3].type == "done"
            assert chunks[3].finish_reason == "end_turn"
            assert chunks[3].usage["prompt_tokens"] == 10
            assert chunks[3].usage["completion_tokens"] == 15

    @pytest.mark.asyncio
    async def test_chat_completion_stream_with_tool_calls(self):
        """ストリーミングでツール呼び出しを含む応答をテスト。"""
        # Arrange: プロバイダーとメッセージを準備
        provider = AnthropicProvider("test-key", "claude-3-5-sonnet-20241022")
        messages = [Message(role="user", content="Get my stats")]

        # ストリーミングレスポンスをモック
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        async def mock_iter_lines():
            lines = [
                # ツール呼び出し開始
                "event: content_block_start",
                'data: {"type": "content_block_start", "index": 0, "content_block": {"type": "tool_use", "id": "toolu_123", "name": "get_stats"}}',  # noqa: E501
                "",
                # ツール呼び出しパラメータ（複数のデルタに分割）
                "event: content_block_delta",
                'data: {"type": "content_block_delta", "index": 0, "delta": {"type": "input_json_delta", "partial_json": "{\\"limit\\": "}}',  # noqa: E501
                "",
                "event: content_block_delta",
                'data: {"type": "content_block_delta", "index": 0, "delta": {"type": "input_json_delta", "partial_json": "10}"}}',  # noqa: E501
                "",
                # ツール呼び出し完了
                "event: content_block_stop",
                'data: {"type": "content_block_stop", "index": 0}',
                "",
                # 完了イベント（ツール使用の場合、stop_reasonがtool_useになる）
                "event: message_delta",
                'data: {"type": "message_delta", "delta": {"stop_reason": "tool_use"}, "usage": {"input_tokens": 10, "output_tokens": 20}}',  # noqa: E501
                "",
                "event: message_stop",
                'data: {"type": "message_stop", "stop_reason": "tool_use"}',
                "",
            ]
            for line in lines:
                yield line

        mock_response.aiter_lines = mock_iter_lines

        mock_async_context = MagicMock()
        mock_async_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_async_context.__aexit__ = AsyncMock(return_value=None)

        # httpx.AsyncClientをモック
        with patch(
            "backend.infrastructure.llm.providers.anthropic.httpx.AsyncClient"
        ) as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_instance.stream = MagicMock(return_value=mock_async_context)
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client_instance

            # Act: ストリーミングチャット補完を実行
            chunks = []
            async for chunk in provider.chat_completion_stream(messages):
                chunks.append(chunk)

            # Assert: tool_callチャンクとdoneチャンクが返されることを確認
            assert len(chunks) == 2

            # tool_callチャンクの確認
            assert chunks[0].type == "tool_call"
            assert chunks[0].tool_calls is not None
            assert len(chunks[0].tool_calls) == 1
            assert chunks[0].tool_calls[0].id == "toolu_123"
            assert chunks[0].tool_calls[0].name == "get_stats"
            assert chunks[0].tool_calls[0].parameters == {"limit": 10}

            # doneチャンクの確認
            assert chunks[1].type == "done"
            assert chunks[1].finish_reason == "tool_use"

    @pytest.mark.asyncio
    async def test_chat_completion_stream_empty_response(self):
        """ストリーミングで空の応答をテスト。"""
        # Arrange: プロバイダーとメッセージを準備
        provider = AnthropicProvider("test-key", "claude-3-5-sonnet-20241022")
        messages = [Message(role="user", content="OK")]

        # 空のストリーミングレスポンスをモック
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        async def mock_iter_lines():
            # 空の完了イベントのみ
            lines = [
                "event: message_delta",
                'data: {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"input_tokens": 5, "output_tokens": 0}}',  # noqa: E501
                "",
                "event: message_stop",
                'data: {"type": "message_stop", "stop_reason": "end_turn"}',
                "",
            ]
            for line in lines:
                yield line

        mock_response.aiter_lines = mock_iter_lines

        mock_async_context = MagicMock()
        mock_async_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_async_context.__aexit__ = AsyncMock(return_value=None)

        # httpx.AsyncClientをモック
        with patch(
            "backend.infrastructure.llm.providers.anthropic.httpx.AsyncClient"
        ) as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_instance.stream = MagicMock(return_value=mock_async_context)
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client_instance

            # Act: ストリーミングチャット補完を実行
            chunks = []
            async for chunk in provider.chat_completion_stream(messages):
                chunks.append(chunk)

            # Assert: doneチャンクのみが返されることを確認
            assert len(chunks) == 1
            assert chunks[0].type == "done"
            assert chunks[0].delta is None
            assert chunks[0].usage["completion_tokens"] == 0

    @pytest.mark.asyncio
    async def test_chat_completion_stream_error_event(self):
        """ストリーミングでエラーイベントをテスト。"""
        # Arrange: プロバイダーとメッセージを準備
        provider = AnthropicProvider("test-key", "claude-3-5-sonnet-20241022")
        messages = [Message(role="user", content="Hello")]

        # エラーイベントを含むストリーミングレスポンスをモック
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        async def mock_iter_lines():
            lines = [
                "event: error",
                'data: {"type": "error", "error": {"type": "invalid_request", "message": "Invalid API key"}}',  # noqa: E501
                "",
            ]
            for line in lines:
                yield line

        mock_response.aiter_lines = mock_iter_lines

        mock_async_context = MagicMock()
        mock_async_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_async_context.__aexit__ = AsyncMock(return_value=None)

        # httpx.AsyncClientをモック
        with patch(
            "backend.infrastructure.llm.providers.anthropic.httpx.AsyncClient"
        ) as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_instance.stream = MagicMock(return_value=mock_async_context)
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client_instance

            # Act: ストリーミングチャット補完を実行
            chunks = []
            async for chunk in provider.chat_completion_stream(messages):
                chunks.append(chunk)

            # Assert: エラーチャンクが返されることを確認
            assert len(chunks) == 1
            assert chunks[0].type == "error"
            assert "Invalid API key" in chunks[0].error
