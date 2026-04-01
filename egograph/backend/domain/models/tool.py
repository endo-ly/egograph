"""ツールのドメインモデル。

LLMに提供するツールのスキーマ定義と基底クラスを提供します。
Model Context Protocol (MCP)のツール設計を参考にしつつ、
シンプルなPython関数として実装します。
"""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class Tool(BaseModel):
    """ツールスキーマ(ドメインエンティティ)。

    LLMプロバイダーに渡すためのツール定義です。
    プロバイダーに依存しない抽象的なツールの概念を表現します。

    Attributes:
        name: ツール名
        description: ツールの説明(LLMが読む)
        inputSchema: 入力パラメータのJSON Schema
    """

    name: str
    description: str
    inputSchema: dict[str, Any]  # JSON Schema


class ToolBase(ABC):
    """ツール実装の基底クラス。

    各ツールはこのクラスを継承し、name、description、input_schema、
    executeメソッドを実装する必要があります。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """ツール名。

        例: "get_top_tracks", "query_spotify_plays"
        """
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """ツールの説明（LLMが読む）。

        何ができるか、どういう時に使うべきかを明確に記述します。
        """
        pass

    @property
    @abstractmethod
    def input_schema(self) -> dict[str, Any]:
        """入力パラメータのJSON Schema。

        Example:
            {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "..."},
                    "limit": {"type": "integer", "default": 10}
                },
                "required": ["start_date"]
            }
        """
        pass

    @abstractmethod
    def execute(self, **params) -> Any:
        """ツールを実行します。

        Args:
            **params: input_schemaで定義されたパラメータ

        Returns:
            ツールの実行結果（JSON serializable）

        Raises:
            ValueError: パラメータが不正な場合
            Exception: 実行に失敗した場合
        """
        pass

    def to_schema(self) -> Tool:
        """ツールスキーマを生成します。

        Returns:
            LLMプロバイダーに渡すためのToolスキーマ
        """
        return Tool(
            name=self.name, description=self.description, inputSchema=self.input_schema
        )
