"""YouTube 視聴統計ツール。

指定期間の視聴履歴、視聴統計、トップチャンネルを取得するツールを提供します。
"""

import logging
from typing import Any

from backend.constants import MAX_LIMIT
from backend.domain.models.tool import ToolBase
from backend.infrastructure.repositories import YouTubeRepository
from backend.validators import (
    validate_date_range,
    validate_granularity,
    validate_limit,
)

logger = logging.getLogger(__name__)


class GetWatchHistoryTool(ToolBase):
    """指定期間の視聴履歴を取得するツール。"""

    def __init__(self, repository: YouTubeRepository):
        """GetWatchHistoryTool を初期化します。

        Args:
            repository: YouTube データリポジトリ
        """
        self.repository = repository

    @property
    def name(self) -> str:
        return "get_watch_history"

    @property
    def description(self) -> str:
        return (
            "YouTubeの指定した期間（start_date から end_date）の視聴履歴を取得します。"
            "視聴時刻の降順で返されます。"
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "開始日（ISO形式: YYYY-MM-DD）",
                },
                "end_date": {
                    "type": "string",
                    "description": "終了日（ISO形式: YYYY-MM-DD）",
                },
                "limit": {
                    "type": "integer",
                    "description": "取得する履歴数（指定しない場合は全件）",
                },
            },
            "required": ["start_date", "end_date"],
        }

    def execute(
        self,
        start_date: str,
        end_date: str,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """視聴履歴を取得します。

        Args:
            start_date: 開始日（ISO形式: YYYY-MM-DD）
            end_date: 終了日（ISO形式: YYYY-MM-DD）
            limit: 取得する履歴数（省略時は全件）

        Returns:
            視聴履歴のリスト（視聴時刻の降順）

        Raises:
            ValueError: 日付形式が不正な場合
        """
        # バリデーション（ビジネスロジック）
        start, end = validate_date_range(start_date, end_date)
        validated_limit = (
            validate_limit(limit, max_value=MAX_LIMIT) if limit is not None else None
        )

        logger.info(
            "Executing get_watch_history: %s to %s, limit=%s",
            start,
            end,
            validated_limit,
        )

        # データ取得は repository に委譲
        return self.repository.get_watch_history(start, end, validated_limit)


class GetWatchingStatsTool(ToolBase):
    """期間別の視聴統計を取得するツール。"""

    def __init__(self, repository: YouTubeRepository):
        """GetWatchingStatsTool を初期化します。

        Args:
            repository: YouTube データリポジトリ
        """
        self.repository = repository

    @property
    def name(self) -> str:
        return "get_watching_stats"

    @property
    def description(self) -> str:
        return (
            "YouTubeの指定した期間の視聴統計を取得します。"
            "日別、週別、月別で集計できます。"
            "総視聴時間、視聴動画数、ユニーク動画数を返します。"
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "開始日（ISO形式: YYYY-MM-DD）",
                },
                "end_date": {
                    "type": "string",
                    "description": "終了日（ISO形式: YYYY-MM-DD）",
                },
                "granularity": {
                    "type": "string",
                    "description": "集計単位",
                    "enum": ["day", "week", "month"],
                    "default": "day",
                },
            },
            "required": ["start_date", "end_date"],
        }

    def execute(
        self, start_date: str, end_date: str, granularity: str = "day"
    ) -> list[dict[str, Any]]:
        """視聴統計を取得します。

        Args:
            start_date: 開始日（ISO形式: YYYY-MM-DD）
            end_date: 終了日（ISO形式: YYYY-MM-DD）
            granularity: 集計単位（"day", "week", "month"）

        Returns:
            期間別統計のリスト

        Raises:
            ValueError: 日付形式または granularity が不正な場合
        """
        # バリデーション（ビジネスロジック）
        start, end = validate_date_range(start_date, end_date)
        validated_granularity = validate_granularity(granularity)

        logger.info(
            "Executing get_watching_stats: %s to %s, granularity=%s",
            start,
            end,
            granularity,
        )

        # データ取得は repository に委譲
        return self.repository.get_watching_stats(start, end, validated_granularity)


class GetTopChannelsTool(ToolBase):
    """指定期間で最も視聴されたチャンネルを取得するツール。"""

    def __init__(self, repository: YouTubeRepository):
        """GetTopChannelsTool を初期化します。

        Args:
            repository: YouTube データリポジトリ
        """
        self.repository = repository

    @property
    def name(self) -> str:
        return "get_top_channels"

    @property
    def description(self) -> str:
        return (
            "YouTubeの指定した期間（start_date から end_date）で最も視聴された"
            "チャンネルを取得します。視聴時間の多い順にソートされます。"
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "開始日（ISO形式: YYYY-MM-DD）",
                },
                "end_date": {
                    "type": "string",
                    "description": "終了日（ISO形式: YYYY-MM-DD）",
                },
                "limit": {
                    "type": "integer",
                    "description": "取得するチャンネル数",
                    "default": 10,
                },
            },
            "required": ["start_date", "end_date"],
        }

    def execute(
        self, start_date: str, end_date: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """トップチャンネルを取得します。

        Args:
            start_date: 開始日（ISO形式: YYYY-MM-DD）
            end_date: 終了日（ISO形式: YYYY-MM-DD）
            limit: 取得するチャンネル数

        Returns:
            トップチャンネルのリスト（視聴時間降順）

        Raises:
            ValueError: 日付形式または limit が不正な場合
        """
        # バリデーション（ビジネスロジック）
        start, end = validate_date_range(start_date, end_date)
        validated_limit = validate_limit(limit, max_value=MAX_LIMIT)

        logger.info(
            "Executing get_top_channels: %s to %s, limit=%s",
            start,
            end,
            validated_limit,
        )

        # データ取得は repository に委譲
        return self.repository.get_top_channels(start, end, validated_limit)
