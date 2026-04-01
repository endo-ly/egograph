"""GitHub → R2 (Parquet Data Lake) 作業ログ取り込みパイプライン。"""

import logging
import sys

from ingest.github.pipeline import run_pipeline
from ingest.settings import IngestSettings
from ingest.utils import log_execution_time

logger = logging.getLogger(__name__)


@log_execution_time
def main():
    """メイン Ingestion パイプライン実行処理。"""
    logger.info("=" * 60)
    logger.info("EgoGraph GitHub Worklog Ingestion Pipeline (Parquet)")
    logger.info("=" * 60)

    try:
        config = IngestSettings.load()
        run_pipeline(config)

    except Exception:
        logger.exception("Pipeline failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
