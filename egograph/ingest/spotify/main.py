"""Spotify → R2 (Parquet Data Lake) データ取り込みパイプライン。"""

import logging
import sys
from datetime import datetime, timezone

from ingest.settings import IngestSettings
from ingest.spotify.pipeline import run_pipeline
from ingest.utils import log_execution_time

logger = logging.getLogger(__name__)


@log_execution_time
def main():
    """メイン Ingestion パイプライン実行処理。"""
    logger.info("=" * 60)
    logger.info("EgoGraph Spotify Ingestion Pipeline (Parquet)")
    logger.info(f"Started at: {datetime.now(timezone.utc).isoformat()}")
    logger.info("=" * 60)

    try:
        config = IngestSettings.load()
        run_pipeline(config)

    except Exception:
        logger.exception("Pipeline failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
