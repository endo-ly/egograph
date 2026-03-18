"""Sync compacted parquet files from R2 to local storage."""

import argparse
import logging
from pathlib import Path

import boto3

from backend.config import BackendConfig

logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=None)
    return parser.parse_args()


def main() -> None:
    """Download compacted parquet files to the local mirror directory."""
    args = _parse_args()
    config = BackendConfig.from_env()
    if config.r2 is None:
        raise ValueError("R2 configuration is required")

    local_root = Path(args.root or config.r2.local_parquet_root or "data/parquet")
    compacted_path = config.r2.compacted_path.rstrip("/") + "/"
    local_root.mkdir(parents=True, exist_ok=True)

    s3 = boto3.client(
        "s3",
        endpoint_url=config.r2.endpoint_url,
        aws_access_key_id=config.r2.access_key_id,
        aws_secret_access_key=config.r2.secret_access_key.get_secret_value(),
        region_name="auto",
    )
    paginator = s3.get_paginator("list_objects_v2")

    downloaded = 0
    for page in paginator.paginate(Bucket=config.r2.bucket_name, Prefix=compacted_path):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            relative_path = Path(key)
            destination = local_root / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            s3.download_file(config.r2.bucket_name, key, str(destination))
            downloaded += 1

    logger.info("Downloaded %d compacted parquet files into %s", downloaded, local_root)


if __name__ == "__main__":
    main()
