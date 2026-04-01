"""LLM/Models層のテスト。"""

import pytest
from pydantic import ValidationError

from backend.infrastructure.llm import ChatResponse, Message, ToolCall


class TestMessage:
    """Messageモデルのテスト。"""

    def test_create_user_message(self):
        """ユーザーメッセージの作成。"""
        # Arrange: ユーザーメッセージのデータを準備

        # Act: ユーザーメッセージを作成
        msg = Message(role="user", content="Hello")

        # Assert: メッセージが正しく作成されることを検証
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_create_assistant_message(self):
        """アシスタントメッセージの作成。"""
        # Arrange: アシスタントメッセージのデータを準備

        # Act: アシスタントメッセージを作成
        msg = Message(role="assistant", content="Hi there")

        # Assert: メッセージが正しく作成されることを検証
        assert msg.role == "assistant"
        assert msg.content == "Hi there"

    def test_create_system_message(self):
        """システムメッセージの作成。"""
        # Arrange: システムメッセージのデータを準備

        # Act: システムメッセージを作成
        msg = Message(role="system", content="You are a helpful assistant")

        # Assert: メッセージが正しく作成されることを検証
        assert msg.role == "system"
        assert msg.content == "You are a helpful assistant"

    def test_invalid_role_raises_error(self):
        """無効なroleでエラー発生。"""
        # Arrange: 無効なroleを準備
        invalid_role = "invalid"

        # Act & Assert: ValidationErrorが発生することを検証
        with pytest.raises(ValidationError):
            Message(role=invalid_role, content="Test")

    def test_missing_content_is_allowed(self):
        """contentがNoneでも許可されることを確認(tool callsのみの場合)。"""
        # Arrange & Act: contentなしのメッセージを作成
        message = Message(role="assistant", content=None)

        # Assert: contentがNoneであることを確認
        assert message.role == "assistant"
        assert message.content is None

    def test_create_tool_message(self):
        """ツール結果メッセージの作成。"""
        # Arrange: ツール結果メッセージのデータを準備
        tool_call_id = "call_123"
        tool_name = "get_top_tracks"
        tool_result = "Top 5 tracks retrieved"

        # Act: ツール結果メッセージを作成
        msg = Message(
            role="tool",
            content=tool_result,
            tool_call_id=tool_call_id,
            name=tool_name,
        )

        # Assert: メッセージが正しく作成されることを検証
        assert msg.role == "tool"
        assert msg.content == "Top 5 tracks retrieved"
        assert msg.tool_call_id == "call_123"
        assert msg.name == "get_top_tracks"

    def test_tool_call_id_field(self):
        """tool_call_idフィールドのテスト。"""
        # Arrange & Act: tool_call_idを持つメッセージを作成
        msg = Message(role="tool", content="result", tool_call_id="call_abc")

        # Assert: tool_call_idが正しく設定されることを検証
        assert msg.tool_call_id == "call_abc"

    def test_name_field(self):
        """nameフィールドのテスト。"""
        # Arrange & Act: nameを持つメッセージを作成
        msg = Message(role="tool", content="result", name="search_tool")

        # Assert: nameが正しく設定されることを検証
        assert msg.name == "search_tool"

    def test_content_as_list(self):
        """contentがlist型の場合のテスト（Anthropic tool_result形式）。"""
        # Arrange: list形式のcontentを準備
        content_blocks = [
            {"type": "tool_result", "tool_use_id": "toolu_123", "content": "Result 1"},
            {"type": "text", "text": "Additional context"},
        ]

        # Act: list形式のcontentを持つメッセージを作成
        msg = Message(role="user", content=content_blocks)

        # Assert: list形式のcontentが正しく設定されることを検証
        assert msg.role == "user"
        assert isinstance(msg.content, list)
        assert len(msg.content) == 2
        assert msg.content[0]["type"] == "tool_result"
        assert msg.content[1]["type"] == "text"

    def test_content_as_string_backward_compatibility(self):
        """contentが文字列の場合の後方互換性テスト。"""
        # Arrange & Act: 従来通りの文字列contentでメッセージを作成
        msg = Message(role="user", content="Hello, world!")

        # Assert: 文字列contentが正しく設定されることを検証
        assert msg.role == "user"
        assert msg.content == "Hello, world!"
        assert isinstance(msg.content, str)

    def test_tool_calls_field(self):
        """tool_callsフィールドのテスト（ToolCallオブジェクト形式）。"""
        # Arrange: tool_calls データを準備
        tool_calls = [
            ToolCall(
                id="call_1",
                name="get_weather",
                parameters={"location": "Tokyo"},
            ),
            ToolCall(
                id="call_2",
                name="get_time",
                parameters={},
            ),
        ]

        # Act: tool_callsを持つassistantメッセージを作成
        msg = Message(role="assistant", content="", tool_calls=tool_calls)

        # Assert: tool_callsが正しく設定されることを検証
        assert msg.role == "assistant"
        assert msg.tool_calls is not None
        assert len(msg.tool_calls) == 2
        assert msg.tool_calls[0].id == "call_1"
        assert msg.tool_calls[0].name == "get_weather"
        assert msg.tool_calls[1].id == "call_2"

    def test_all_new_fields_are_optional(self):
        """新フィールドが全てOptionalであることを確認。"""
        # Arrange & Act: 新フィールドなしでメッセージを作成
        msg = Message(role="user", content="Test message")

        # Assert: 新フィールドがNoneであることを検証
        assert msg.tool_call_id is None
        assert msg.name is None
        assert msg.tool_calls is None

    def test_complex_tool_message_with_list_content(self):
        """複雑なツールメッセージ（list content + tool_call_id）のテスト。"""
        # Arrange: Anthropic形式の複雑なツール結果を準備
        content_blocks = [
            {
                "type": "tool_result",
                "tool_use_id": "toolu_abc123",
                "content": [
                    {"type": "text", "text": "Here are the results:"},
                    {"type": "json", "json": {"items": [1, 2, 3]}},
                ],
            }
        ]

        # Act: 複雑なツール結果メッセージを作成
        msg = Message(role="user", content=content_blocks, tool_call_id="toolu_abc123")

        # Assert: 全てのフィールドが正しく設定されることを検証
        assert msg.role == "user"
        assert isinstance(msg.content, list)
        assert msg.content[0]["type"] == "tool_result"
        assert msg.tool_call_id == "toolu_abc123"


class TestToolCall:
    """ToolCallモデルのテスト。"""

    def test_create_tool_call(self):
        """ツール呼び出しの作成。"""
        # Arrange: ツール呼び出しのデータを準備
        tool_id = "call_123"
        tool_name = "get_top_tracks"
        parameters = {"limit": 10}

        # Act: ツール呼び出しを作成
        tc = ToolCall(id=tool_id, name=tool_name, parameters=parameters)

        # Assert: ツール呼び出しが正しく作成されることを検証
        assert tc.id == "call_123"
        assert tc.name == "get_top_tracks"
        assert tc.parameters == {"limit": 10}

    def test_empty_parameters(self):
        """パラメータなしのツール呼び出し。"""
        # Arrange: パラメータなしのツール呼び出しデータを準備
        tool_id = "call_456"
        tool_name = "get_stats"

        # Act: ツール呼び出しを作成
        tc = ToolCall(id=tool_id, name=tool_name, parameters={})

        # Assert: 空のパラメータが正しく設定されることを検証
        assert tc.parameters == {}

    def test_complex_parameters(self):
        """複雑なパラメータのツール呼び出し。"""
        # Arrange: 複雑なパラメータを持つツール呼び出しデータを準備
        parameters = {
            "query": "test",
            "limit": 20,
            "filters": {"genre": "rock"},
        }

        # Act: ツール呼び出しを作成
        tc = ToolCall(
            id="call_789",
            name="search",
            parameters=parameters,
        )

        # Assert: 複雑なパラメータが正しく設定されることを検証
        assert tc.parameters["query"] == "test"
        assert tc.parameters["filters"]["genre"] == "rock"

    def test_missing_required_fields_raises_error(self):
        """必須フィールド欠落でエラー。"""
        # Arrange: 必須フィールドが欠けたデータを準備

        # Act & Assert: ValidationErrorが発生することを検証
        with pytest.raises(ValidationError):
            ToolCall(id="call_123")


class TestChatResponse:
    """ChatResponseモデルのテスト。"""

    def test_create_simple_response(self):
        """シンプルなレスポンスの作成。"""
        # Arrange: シンプルなレスポンスデータを準備
        response_id = "resp_123"
        message = Message(role="assistant", content="Test")
        usage = {"prompt_tokens": 10, "completion_tokens": 20}

        # Act: レスポンスを作成
        response = ChatResponse(
            id=response_id,
            message=message,
            tool_calls=None,
            usage=usage,
            finish_reason="stop",
        )

        # Assert: レスポンスが正しく作成されることを検証
        assert response.id == "resp_123"
        assert response.message.content == "Test"
        assert response.tool_calls is None
        assert response.finish_reason == "stop"

    def test_response_with_tool_calls(self):
        """ツール呼び出しを含むレスポンス。"""
        # Arrange: ツール呼び出しを含むレスポンスデータを準備
        tool_calls = [
            ToolCall(id="call_1", name="get_top_tracks", parameters={"limit": 5})
        ]

        # Act: レスポンスを作成
        response = ChatResponse(
            id="resp_456",
            message=Message(role="assistant", content=""),
            tool_calls=tool_calls,
            usage={"prompt_tokens": 10, "completion_tokens": 5},
            finish_reason="tool_calls",
        )

        # Assert: ツール呼び出しが正しく含まれることを検証
        assert response.tool_calls is not None
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].name == "get_top_tracks"
        assert response.finish_reason == "tool_calls"

    def test_response_with_usage_stats(self):
        """使用統計を含むレスポンス。"""
        # Arrange: 使用統計を含むレスポンスデータを準備
        usage = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}

        # Act: レスポンスを作成
        response = ChatResponse(
            id="resp_789",
            message=Message(role="assistant", content="Done"),
            usage=usage,
            finish_reason="stop",
        )

        # Assert: 使用統計が正しく含まれることを検証
        assert response.usage["prompt_tokens"] == 100
        assert response.usage["completion_tokens"] == 50
        assert response.usage["total_tokens"] == 150

    def test_response_without_optional_fields(self):
        """オプショナルフィールドなしのレスポンス。"""
        # Arrange: 最小限のレスポンスデータを準備
        message = Message(role="assistant", content="Minimal response")

        # Act: レスポンスを作成
        response = ChatResponse(
            id="resp_minimal",
            message=message,
            finish_reason="stop",
        )

        # Assert: オプショナルフィールドがNoneであることを検証
        assert response.tool_calls is None
        assert response.usage is None

    def test_missing_required_fields_raises_error(self):
        """必須フィールド欠落でエラー。"""
        # Arrange: 必須フィールドが欠けたデータを準備

        # Act & Assert: ValidationErrorが発生することを検証
        with pytest.raises(ValidationError):
            ChatResponse(
                id="resp_bad", message=Message(role="assistant", content="Test")
            )
