"""Tools/Base層のテスト。"""

import pytest
from pydantic import ValidationError

from backend.usecases.tools import Tool, ToolBase


class TestTool:
    """Toolモデルのテスト。"""

    def test_create_tool_schema(self):
        """ツールスキーマの作成。"""
        # Arrange & Act: ツールスキーマを作成
        tool = Tool(
            name="test_tool",
            description="A test tool",
            inputSchema={
                "type": "object",
                "properties": {"param1": {"type": "string"}},
            },
        )

        # Assert: スキーマが正しく設定されることを検証
        assert tool.name == "test_tool"
        assert tool.description == "A test tool"
        assert tool.inputSchema["type"] == "object"

    def test_missing_required_fields_raises_error(self):
        """必須フィールド欠落でエラー。"""
        # Arrange & Act & Assert: 必須フィールドが欠落している場合に
        # ValidationErrorが発生することを検証
        with pytest.raises(ValidationError):
            Tool(name="test_tool")


class MockTool(ToolBase):
    """テスト用のモックツール。"""

    def __init__(self, return_value="mock result"):
        self.return_value = return_value

    @property
    def name(self) -> str:
        return "mock_tool"

    @property
    def description(self) -> str:
        return "A mock tool for testing"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "param1": {"type": "string", "description": "Test parameter"}
            },
            "required": ["param1"],
        }

    def execute(self, **params):
        return self.return_value


class TestToolBase:
    """ToolBaseのテスト。"""

    def test_to_schema_generates_tool(self):
        """to_schema()がToolスキーマを生成。"""
        # Arrange: モックツールを準備
        mock_tool = MockTool()

        # Act: to_schema()でToolスキーマを生成
        schema = mock_tool.to_schema()

        # Assert: 生成されたスキーマを検証
        assert isinstance(schema, Tool)
        assert schema.name == "mock_tool"
        assert schema.description == "A mock tool for testing"
        assert schema.inputSchema == mock_tool.input_schema

    def test_execute_returns_result(self):
        """execute()が結果を返す。"""
        # Arrange: モックツールを準備
        mock_tool = MockTool(return_value="test output")

        # Act: ツールを実行
        result = mock_tool.execute(param1="value")

        # Assert: 実行結果を検証
        assert result == "test output"
