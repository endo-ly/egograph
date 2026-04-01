"""LLM/Providers/OpenAI層のテスト。"""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import httpx
import pytest

from backend.infrastructure.llm import Message, OpenAIProvider, ToolCall
from backend.usecases.tools import Tool


# カスタムMockクラス：is_errorプロパティを正しく実装
class MockResponse(MagicMock):
    """httpx.Response のモック。"""

    def __init__(self, status_code: int = 200, is_error: bool = False):
        super().__init__()
        self.status_code = status_code
        self._is_error = is_error

    @property
    def is_error(self):
        return self._is_error

    def raise_for_status(self):
        if self._is_error:
            mock_request = MagicMock(spec=httpx.Request)
            raise httpx.HTTPStatusError(
                "Mock error",
                request=mock_request,
                response=self,
            )

    async def aread(self):
        return b""

    async def aiter_lines(self):
        yield  # Default implementation - should be overridden


@pytest.fixture
def mock_streaming_context():
    """ストリーミングレスポンス用のモックコンテキストを作成するfixture。

    Returns:
        mock_response, mock_iter_lines, patch_context のタプル
        mock_iter_lines はテスト内でyieldするlinesを設定できる関数
    """

    def _create(lines_generator, is_error: bool = False):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        type(mock_response).is_error = PropertyMock(return_value=is_error)
        mock_response.raise_for_status = MagicMock()
        mock_response.aread = AsyncMock(return_value=b"")
        mock_response.aiter_lines = lines_generator

        # AsyncMockContextManagerを作成
        mock_async_context = MagicMock()
        mock_async_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_async_context.__aexit__ = AsyncMock(return_value=None)

        return mock_response, mock_async_context

    return _create


class TestOpenAIProvider:
    """OpenAIProviderのテスト。"""

    def test_initialization(self):
        """初期化のテスト。"""
        # Arrange & Act: プロバイダーを初期化
        provider = OpenAIProvider("test-key", "gpt-4o-mini")

        # Assert: 設定値が正しく保存されることを検証
        assert provider.api_key == "test-key"
        assert provider.model_name == "gpt-4o-mini"
        # デフォルト base_url が変更されたのでそれに合わせる
        assert provider.base_url == "https://api.z.ai/api/coding/paas/v4"

    def test_custom_base_url(self):
        """カスタムbase_urlの設定。"""
        # Arrange & Act: カスタムbase_urlを指定してプロバイダーを初期化
        provider = OpenAIProvider(
            "test-key", "model-name", base_url="https://openrouter.ai/api/v1"
        )

        # Assert: カスタムbase_urlが設定されることを検証
        assert provider.base_url == "https://openrouter.ai/api/v1"

    def test_base_url_strips_trailing_slash(self):
        """base_urlの末尾スラッシュを除去。"""
        # Arrange & Act: 末尾にスラッシュを含むbase_urlで初期化
        provider = OpenAIProvider(
            "test-key", "model-name", base_url="https://api.z.ai/api/paas/v4/"
        )

        # Assert: 末尾のスラッシュが除去されることを検証
        assert provider.base_url == "https://api.z.ai/api/paas/v4"

    def test_convert_tools_to_provider_format(self):
        """ツールをOpenAI形式に変換。"""
        # Arrange: プロバイダーとツールスキーマを準備
        provider = OpenAIProvider("test-key", "gpt-4o-mini")

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

        # Act: OpenAI形式に変換
        result = provider._convert_tools_to_provider_format(tools)

        # Assert: 変換結果を検証
        assert len(result) == 1
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "get_stats"
        assert result[0]["function"]["description"] == "Get listening stats"
        assert result[0]["function"]["parameters"] == tools[0].inputSchema

    def test_parse_response_simple(self):
        """シンプルなレスポンスのパース。"""
        # Arrange: プロバイダーとシンプルなレスポンスデータを準備
        provider = OpenAIProvider("test-key", "gpt-4o-mini")

        raw_response = {
            "id": "chatcmpl-123",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Hello!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }

        # Act: レスポンスをパース
        response = provider._parse_response(raw_response)

        # Assert: パース結果を検証
        assert response.id == "chatcmpl-123"
        assert response.message.role == "assistant"
        assert response.message.content == "Hello!"
        assert response.finish_reason == "stop"
        assert response.usage == {"prompt_tokens": 10, "completion_tokens": 5}
        assert response.tool_calls is None

    def test_parse_response_with_tool_calls(self):
        """ツール呼び出しを含むレスポンスのパース。"""
        # Arrange: プロバイダーとツール呼び出しを含むレスポンスデータを準備
        provider = OpenAIProvider("test-key", "gpt-4o-mini")

        raw_response = {
            "id": "chatcmpl-456",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_123",
                                "function": {
                                    "name": "get_stats",
                                    "arguments": '{"limit": 10}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
        }

        # Act: レスポンスをパース
        response = provider._parse_response(raw_response)

        # Assert: ツール呼び出し情報が正しく抽出されることを検証
        assert response.id == "chatcmpl-456"
        assert response.tool_calls is not None
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].id == "call_123"
        assert response.tool_calls[0].name == "get_stats"
        assert response.tool_calls[0].parameters == {"limit": 10}
        assert response.finish_reason == "tool_calls"

    @pytest.mark.asyncio
    async def test_chat_completion_success(self):
        """チャット補完が成功する。"""
        # Arrange: プロバイダー、メッセージ、HTTPクライアントのモックを準備
        provider = OpenAIProvider("test-key", "gpt-4o-mini")

        messages = [Message(role="user", content="Hello")]

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = (
                mock_client_instance
            )

            # レスポンスモック
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "id": "chatcmpl-test",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "Hi there!"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            }
            mock_client_instance.post.return_value = mock_response

            # Act: チャット補完を実行
            response = await provider.chat_completion(messages)

            # Assert: レスポンスとAPI呼び出しが正しいことを検証
            assert response.message.content == "Hi there!"
            mock_client_instance.post.assert_called_once()

    def test_convert_messages_to_provider_format_basic(self):
        """基本的なメッセージ変換のテスト。"""
        # Arrange: プロバイダーと基本的なメッセージを準備
        provider = OpenAIProvider("test-key", "gpt-4o-mini")
        messages = [
            Message(role="system", content="You are a helpful assistant"),
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi there!"),
        ]

        # Act: OpenAI形式に変換
        result = provider._convert_messages_to_provider_format(messages)

        # Assert: 基本的なメッセージが正しく変換されることを検証
        assert len(result) == 3
        assert result[0] == {"role": "system", "content": "You are a helpful assistant"}
        assert result[1] == {"role": "user", "content": "Hello"}
        assert result[2] == {"role": "assistant", "content": "Hi there!"}

    def test_convert_messages_with_tool_results(self):
        """role="tool"メッセージの変換テスト。"""
        # Arrange: プロバイダーとtool resultメッセージを準備
        provider = OpenAIProvider("test-key", "gpt-4o-mini")
        messages = [
            Message(role="user", content="Get my stats"),
            Message(
                role="tool",
                content='{"plays": 100}',
                tool_call_id="call_123",
                name="get_stats",
            ),
        ]

        # Act: OpenAI形式に変換
        result = provider._convert_messages_to_provider_format(messages)

        # Assert: tool resultメッセージが正しく変換されることを検証
        assert len(result) == 2
        assert result[0] == {"role": "user", "content": "Get my stats"}
        assert result[1] == {
            "role": "tool",
            "content": '{"plays": 100}',
            "tool_call_id": "call_123",
            "name": "get_stats",
        }

    def test_convert_messages_with_assistant_tool_calls(self):
        """assistant + tool_calls の変換テスト。"""
        # Arrange: プロバイダーとtool callsを含むassistantメッセージを準備
        provider = OpenAIProvider("test-key", "gpt-4o-mini")
        tool_calls_data = [
            ToolCall(
                id="call_456",
                name="get_stats",
                parameters={"limit": 10},
            )
        ]
        messages = [
            Message(role="user", content="Get my top 10 stats"),
            Message(role="assistant", content="", tool_calls=tool_calls_data),
        ]

        # Act: OpenAI形式に変換
        result = provider._convert_messages_to_provider_format(messages)

        # Assert: tool_callsを含むassistantメッセージが正しく変換されることを検証
        assert len(result) == 2
        assert result[0] == {"role": "user", "content": "Get my top 10 stats"}
        # ToolCallオブジェクトがOpenAI形式に変換されている
        assert result[1]["role"] == "assistant"
        assert result[1]["content"] == ""
        assert len(result[1]["tool_calls"]) == 1
        assert result[1]["tool_calls"][0]["id"] == "call_456"
        assert result[1]["tool_calls"][0]["type"] == "function"
        assert result[1]["tool_calls"][0]["function"]["name"] == "get_stats"
        assert result[1]["tool_calls"][0]["function"]["arguments"] == '{"limit": 10}'

    def test_convert_tool_message_requires_tool_call_id(self):
        """tool_call_id必須チェックのテスト。"""
        # Arrange: プロバイダーとtool_call_idのないtoolメッセージを準備
        provider = OpenAIProvider("test-key", "gpt-4o-mini")
        messages = [Message(role="tool", content='{"result": "ok"}', name="get_stats")]

        # Act & Assert: tool_call_idが必須であることを検証
        with pytest.raises(ValueError, match=r"invalid_tool_message.*tool_call_id"):
            provider._convert_messages_to_provider_format(messages)

    def test_convert_tool_message_requires_name(self):
        """name必須チェックのテスト。"""
        # Arrange: プロバイダーとnameのないtoolメッセージを準備
        provider = OpenAIProvider("test-key", "gpt-4o-mini")
        messages = [
            Message(role="tool", content='{"result": "ok"}', tool_call_id="call_789")
        ]

        # Act & Assert: nameが必須であることを検証
        with pytest.raises(ValueError, match=r"invalid_tool_message.*name"):
            provider._convert_messages_to_provider_format(messages)

    @pytest.mark.asyncio
    async def test_chat_completion_stream_success(self, mock_streaming_context):
        """ストリーミングチャット補完が成功する。"""
        # Arrange: プロバイダーとメッセージを準備
        provider = OpenAIProvider("test-key", "gpt-4o-mini")
        messages = [Message(role="user", content="Tell me a story")]

        # ストリーミング-linesをモック
        async def mock_iter_lines():
            lines = [
                (
                    'data: {"id":"chatcmpl-stream","object":"chat.completion.chunk",'
                    '"created":1234567890,"model":"gpt-4o-mini","choices":[{'
                    '"index":0,"delta":{"content":"Once"},"finish_reason":null}]}'
                ),
                (
                    'data: {"id":"chatcmpl-stream","object":"chat.completion.chunk",'
                    '"created":1234567891,"model":"gpt-4o-mini","choices":[{'
                    '"index":0,"delta":{"content":" upon"},"finish_reason":null}]}'
                ),
                (
                    'data: {"id":"chatcmpl-stream","object":"chat.completion.chunk",'
                    '"created":1234567892,"model":"gpt-4o-mini","choices":[{'
                    '"index":0,"delta":{"content":" a time"},"finish_reason":null}]}'
                ),
                "data: [DONE]",
            ]
            for line in lines:
                yield line

        _, mock_stream_ctx = mock_streaming_context(mock_iter_lines)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_instance = MagicMock()
            mock_client_class.return_value.__aenter__.return_value = (
                mock_client_instance
            )
            mock_client_instance.stream = MagicMock(return_value=mock_stream_ctx)

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

    @pytest.mark.asyncio
    async def test_chat_completion_stream_with_tool_calls(self, mock_streaming_context):
        """ストリーミングでツール呼び出しを含む応答をテスト。"""
        # Arrange: プロバイダーとメッセージを準備
        provider = OpenAIProvider("test-key", "gpt-4o-mini")
        messages = [Message(role="user", content="Get my stats")]

        # ストリーミング-linesをモック（ツール呼び出しを含む）
        async def mock_iter_lines():
            lines = [
                (
                    'data: {"id":"chatcmpl-stream","object":"chat.completion.chunk",'
                    '"created":1234567890,"model":"gpt-4o-mini","choices":[{'
                    '"index":0,"delta":{"tool_calls":[{"id":"call_001",'
                    '"type":"function","function":{"name":"get_stats",'
                    '"arguments":"{\\"limit\\":10}"},"index":0}]},'
                    '"finish_reason":null}]}'
                ),
                "data: [DONE]",
            ]
            for line in lines:
                yield line

        _, mock_stream_ctx = mock_streaming_context(mock_iter_lines)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_instance = MagicMock()
            mock_client_class.return_value.__aenter__.return_value = (
                mock_client_instance
            )
            mock_client_instance.stream = MagicMock(return_value=mock_stream_ctx)

            # Act: ストリーミングチャット補完を実行
            chunks = []
            async for chunk in provider.chat_completion_stream(messages):
                chunks.append(chunk)

            # Assert: ツール呼び出しチャンクが含まれることを確認
            assert len(chunks) == 2

            # ツール呼び出しチャンクの確認
            tool_call_chunk = chunks[0]
            assert tool_call_chunk.type == "tool_call"
            assert tool_call_chunk.tool_calls is not None
            assert len(tool_call_chunk.tool_calls) == 1
            assert tool_call_chunk.tool_calls[0].name == "get_stats"
            assert tool_call_chunk.tool_calls[0].parameters == {"limit": 10}

    @pytest.mark.asyncio
    async def test_chat_completion_stream_handles_done_marker(
        self,
        mock_streaming_context,
    ):
        """ストリーミングで[DONE]マーカーを正しく処理する。"""
        # Arrange: プロバイダーとメッセージを準備
        provider = OpenAIProvider("test-key", "gpt-4o-mini")
        messages = [Message(role="user", content="Hello")]

        async def mock_iter_lines():
            lines = ["data: [DONE]"]
            for line in lines:
                yield line

        _, mock_stream_ctx = mock_streaming_context(mock_iter_lines)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_instance = MagicMock()
            mock_client_class.return_value.__aenter__.return_value = (
                mock_client_instance
            )
            mock_client_instance.stream = MagicMock(return_value=mock_stream_ctx)

            # Act: ストリーミングチャット補完を実行
            chunks = []
            async for chunk in provider.chat_completion_stream(messages):
                chunks.append(chunk)

            # Assert: doneチャンクのみが返されることを確認
            assert len(chunks) == 1
            assert chunks[0].type == "done"

    @pytest.mark.asyncio
    async def test_chat_completion_stream_with_usage(self, mock_streaming_context):
        """ストリーミングでusage情報が返される。"""
        # Arrange: プロバイダーとメッセージを準備
        provider = OpenAIProvider("test-key", "gpt-4o-mini")
        messages = [Message(role="user", content="Hello")]

        async def mock_iter_lines():
            lines = [
                (
                    'data: {"id":"chatcmpl-stream","object":"chat.completion.chunk",'
                    '"created":1234567890,"model":"gpt-4o-mini","choices":[{'
                    '"index":0,"delta":{"content":"Hi"},"finish_reason":null}]}'
                ),
                (
                    'data: {"id":"chatcmpl-stream","object":"chat.completion.chunk",'
                    '"created":1234567891,"model":"gpt-4o-mini","choices":[{'
                    '"index":0,"delta":{},"finish_reason":"stop"}],"usage":{'
                    '"prompt_tokens":10,"completion_tokens":5}}'
                ),
                "data: [DONE]",
            ]
            for line in lines:
                yield line

        _, mock_stream_ctx = mock_streaming_context(mock_iter_lines)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_instance = MagicMock()
            mock_client_class.return_value.__aenter__.return_value = (
                mock_client_instance
            )
            mock_client_instance.stream = MagicMock(return_value=mock_stream_ctx)

            # Act: ストリーミングチャット補完を実行
            chunks = []
            async for chunk in provider.chat_completion_stream(messages):
                chunks.append(chunk)

            # Assert: deltaチャンクとdoneチャンクが返されることを確認
            assert len(chunks) == 2

            # deltaチャンクの確認
            assert chunks[0].type == "delta"
            assert chunks[0].delta == "Hi"

            # doneチャンクの確認
            done_chunk = chunks[1]
            assert done_chunk.type == "done"
            assert done_chunk.usage == {"prompt_tokens": 10, "completion_tokens": 5}
            assert done_chunk.finish_reason == "stop"
