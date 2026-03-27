"""Browser history compaction helpers."""

from collections.abc import Iterable
from datetime import datetime

from ingest.browser_history.storage import BrowserHistoryStorage

CompactionTarget = tuple[int, int]


def collect_compaction_targets(
    rows: Iterable[dict[str, object]],
) -> tuple[CompactionTarget, ...]:
    """保存対象 rows から compaction 対象月を抽出する。"""
    targets = {
        (started_at.year, started_at.month)
        for row in rows
        if isinstance(started_at := row.get("started_at_utc"), datetime)
    }
    return tuple(sorted(targets))


def compact_browser_history_targets(
    storage: BrowserHistoryStorage,
    targets: Iterable[CompactionTarget],
) -> None:
    """指定月の browser history compact を実行する。"""
    for year, month in sorted(set(targets)):
        try:
            storage.compact_month(year=year, month=month)
        except Exception as exc:
            raise RuntimeError(
                f"Browser history compaction failed for {year}-{month:02d}"
            ) from exc
