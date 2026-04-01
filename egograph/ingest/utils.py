"""EgoGraph Ingestユーティリティ関数。

shared.utilsから移行 - Ingestサービス用のヘルパー関数を定義します。
"""

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from functools import wraps

logger = logging.getLogger(__name__)


def log_execution_time[T: Callable](func: T) -> T:
    """関数の実行時間をログ出力するデコレータ。

    Args:
        func: ラップする関数

    Returns:
        ラップされた関数
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = datetime.now(timezone.utc)
        logger.info("Starting %s", func.__name__)

        try:
            result = func(*args, **kwargs)
        except Exception:
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.exception("Failed %s after %.2fs", func.__name__, elapsed)
            raise

        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        logger.info("Completed %s in %.2fs", func.__name__, elapsed)
        return result

    return wrapper


def iso8601_to_unix_ms(iso_timestamp) -> int:
    """ISO 8601タイムスタンプまたはdatetimeオブジェクトをUnixミリ秒に変換します。

    Args:
        iso_timestamp: ISO 8601形式のタイムスタンプ文字列、またはdatetimeオブジェクト
                      (例: "2025-12-14T02:30:00.000Z"
                       または datetime(2025, 12, 14, 2, 30))

    Returns:
        Unixエポックからのミリ秒(整数)

    Raises:
        ValueError: タイムスタンプのパースに失敗した場合

    Examples:
        >>> iso8601_to_unix_ms("2025-12-14T02:30:00.000Z")
        1765679400000
        >>> iso8601_to_unix_ms(datetime(2025, 12, 14, 2, 30, tzinfo=timezone.utc))
        1765679400000
    """
    try:
        # datetimeオブジェクトの場合は直接変換
        if isinstance(iso_timestamp, datetime):
            if iso_timestamp.tzinfo is None:
                raise ValueError(
                    "Naive datetime (timezone-unaware) is not supported. "
                    "Please provide a timezone-aware datetime object "
                    "(e.g., with tzinfo=timezone.utc)."
                )
            return int(iso_timestamp.timestamp() * 1000)

        # 文字列の場合はISO 8601としてパース
        # ISO 8601の'Z'をUTC timezone指定に変換
        normalized = iso_timestamp.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        return int(dt.timestamp() * 1000)
    except (ValueError, AttributeError, TypeError) as e:
        raise ValueError(f"Failed to parse timestamp '{iso_timestamp}': {e}") from e


__all__ = [
    "log_execution_time",
    "iso8601_to_unix_ms",
]
