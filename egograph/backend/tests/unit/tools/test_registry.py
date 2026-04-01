"""Tools/Registry層のテスト。"""

import pytest

from backend.usecases.tools import Tool, ToolBase, ToolRegistry


class MockToolA(ToolBase):
    """テスト用ツールA。"""

    @property
    def name(self) -> str:
        return "tool_a"

    @property
    def description(self) -> str:
        return "Tool A description"

    @property
    def input_schema(self) -> dict:
        return {"type": "object", "properties": {"value": {"type": "integer"}}}

    def execute(self, **params):
        return {"result": params.get("value", 0) * 2}


class MockToolB(ToolBase):
    """テスト用ツールB。"""

    @property
    def name(self) -> str:
        return "tool_b"

    @property
    def description(self) -> str:
        return "Tool B description"

    @property
    def input_schema(self) -> dict:
        return {"type": "object", "properties": {"text": {"type": "string"}}}

    def execute(self, **params):
        return {"result": params.get("text", "").upper()}


class TestToolRegistry:
    """ToolRegistryのテスト。"""

    def test_register_tool(self):
        """ツールを登録できる。"""
        # Arrange: レジストリとツールを準備
        registry = ToolRegistry()
        tool_a = MockToolA()

        # Act: ツールを登録
        registry.register(tool_a)

        # Assert: ツールが登録されていることを検証
        assert "tool_a" in registry.list_tool_names()

    def test_register_multiple_tools(self):
        """複数のツールを登録できる。"""
        # Arrange: レジストリと複数のツールを準備
        registry = ToolRegistry()
        tool_a = MockToolA()
        tool_b = MockToolB()

        # Act: 複数のツールを登録
        registry.register(tool_a)
        registry.register(tool_b)

        # Assert: 全てのツールが登録されていることを検証
        assert len(registry.list_tool_names()) == 2
        assert "tool_a" in registry.list_tool_names()
        assert "tool_b" in registry.list_tool_names()

    def test_get_tool(self):
        """登録済みツールを名前で取得できる。"""
        # Arrange: レジストリにツールを登録
        registry = ToolRegistry()
        tool_a = MockToolA()
        registry.register(tool_a)

        # Act: 名前でツールを取得
        retrieved_tool = registry.get_tool("tool_a")

        # Assert: 取得したツールが正しいことを検証
        assert retrieved_tool is tool_a

    def test_get_tool_not_found_raises_error(self):
        """未登録ツールの取得でエラー。"""
        # Arrange: 空のレジストリを準備
        registry = ToolRegistry()

        # Act & Assert: 存在しないツールの取得でKeyErrorが発生することを検証
        with pytest.raises(KeyError, match="Tool not found"):
            registry.get_tool("nonexistent_tool")

    def test_get_all_schemas(self):
        """全ツールのスキーマを取得できる。"""
        # Arrange: レジストリに複数のツールを登録
        registry = ToolRegistry()
        tool_a = MockToolA()
        tool_b = MockToolB()

        registry.register(tool_a)
        registry.register(tool_b)

        # Act: 全ツールのスキーマを取得
        schemas = registry.get_all_schemas()

        # Assert: 全スキーマが正しく取得されることを検証
        assert len(schemas) == 2
        assert all(isinstance(s, Tool) for s in schemas)

        # スキーマ名を確認
        schema_names = [s.name for s in schemas]
        assert "tool_a" in schema_names
        assert "tool_b" in schema_names

    def test_execute_tool(self):
        """ツールを実行できる。"""
        # Arrange: レジストリにツールを登録
        registry = ToolRegistry()
        tool_a = MockToolA()
        registry.register(tool_a)

        # Act: ツールを実行
        result = registry.execute("tool_a", value=10)

        # Assert: 実行結果を検証
        assert result == {"result": 20}

    def test_execute_tool_not_found_raises_error(self):
        """未登録ツールの実行でエラー。"""
        # Arrange: 空のレジストリを準備
        registry = ToolRegistry()

        # Act & Assert: 存在しないツールの実行でKeyErrorが発生することを検証
        with pytest.raises(KeyError, match="Tool not found"):
            registry.execute("nonexistent_tool", param="value")

    def test_execute_multiple_tools(self):
        """複数のツールをそれぞれ実行できる。"""
        # Arrange: レジストリに複数のツールを登録
        registry = ToolRegistry()
        tool_a = MockToolA()
        tool_b = MockToolB()

        registry.register(tool_a)
        registry.register(tool_b)

        # Act: 各ツールを実行
        result_a = registry.execute("tool_a", value=5)
        result_b = registry.execute("tool_b", text="hello")

        # Assert: それぞれの実行結果を検証
        assert result_a == {"result": 10}
        assert result_b == {"result": "HELLO"}

    def test_list_tool_names(self):
        """ツール名一覧を取得できる。"""
        # Arrange: レジストリに複数のツールを登録
        registry = ToolRegistry()
        tool_a = MockToolA()
        tool_b = MockToolB()

        registry.register(tool_a)
        registry.register(tool_b)

        # Act: ツール名一覧を取得
        names = registry.list_tool_names()

        # Assert: 全ツール名が取得されることを検証
        assert len(names) == 2
        assert "tool_a" in names
        assert "tool_b" in names
