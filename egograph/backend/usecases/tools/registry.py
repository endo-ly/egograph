"""ツールレジストリと実行エンジン。

利用可能なツールを管理し、名前で実行します。
"""

import logging
from typing import Any

from backend.domain.models.tool import Tool, ToolBase

logger = logging.getLogger(__name__)


class ToolRegistry:
    """ツールレジストリ。

    ツールを登録・管理し、名前でアクセス・実行できるようにします。

    Example:
        >>> registry = ToolRegistry()
        >>> registry.register(GetTopTracksTool(r2_config))
        >>> result = registry.execute(
        ...     "get_top_tracks",
        ...     start_date="2024-01-01",
        ...     end_date="2024-01-31"
        ... )
    """

    def __init__(self):
        """ToolRegistryを初期化します。"""
        self._tools: dict[str, ToolBase] = {}

    def register(self, tool: ToolBase) -> None:
        """ツールを登録します。

        Args:
            tool: 登録するツール
        """
        self._tools[tool.name] = tool
        logger.debug("Registered tool: %s", tool.name)

    def get_tool(self, name: str) -> ToolBase:
        """名前でツールを取得します。

        Args:
            name: ツール名

        Returns:
            ツールインスタンス

        Raises:
            KeyError: ツールが見つからない場合
        """
        if name not in self._tools:
            raise KeyError(f"Tool not found: {name}")
        return self._tools[name]

    def get_all_schemas(self) -> list[Tool]:
        """全ツールのスキーマを取得します。

        LLMプロバイダーに渡すためのツールスキーマリストを返します。

        Returns:
            ツールスキーマのリスト
        """
        return [tool.to_schema() for tool in self._tools.values()]

    def execute(self, tool_name: str, **params) -> Any:
        """ツールを実行します。

        Args:
            tool_name: ツール名
            **params: ツールパラメータ

        Returns:
            ツールの実行結果

        Raises:
            KeyError: ツールが見つからない場合
            ValueError: パラメータが不正な場合
        """
        tool = self.get_tool(tool_name)
        # 機密情報をログに含めないようにパラメータキーのみをログ出力
        param_keys = list(params.keys())
        logger.info("Executing tool: %s with params: %s", tool_name, param_keys)

        try:
            result = tool.execute(**params)
            logger.debug("Tool %s executed successfully", tool_name)
            return result
        except Exception as e:
            logger.error(
                "Tool %s execution failed: %s", tool_name, f"{type(e).__name__}: {e}"
            )
            raise

    def list_tool_names(self) -> list[str]:
        """登録されているツール名の一覧を取得します。

        Returns:
            ツール名のリスト
        """
        return list(self._tools.keys())
