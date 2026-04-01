"""R2上のYouTube視聴履歴データを検証・確認するスクリプト。

総レコード数の確認と、最新50件の視聴履歴を表示します。
DuckDBの httpfs 拡張を使用して、R2上のファイルを直接クエリします。

Usage:
    uv run python backend/scripts/verify_youtube_parquet.py
"""

import logging
import os
import sys

import duckdb
from tabulate import tabulate

# プロジェクトルートをパスに追加
sys.path.append(os.getcwd())

from backend.config import BackendConfig

# ロギング設定
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def verify_r2_data():
    """R2上のParquetデータを検証し、最新の履歴を表示する。"""
    logger.info("🦆 Verifying YouTube Watch History from R2...")

    try:
        config = BackendConfig.from_env()
    except Exception:
        logger.exception("Failed to load config")
        return

    if not config.r2:
        logger.error("R2 configuration is missing.")
        return

    r2_conf = config.r2
    conn = duckdb.connect(":memory:")

    try:
        # S3(R2) 設定の適用
        conn.execute("INSTALL httpfs; LOAD httpfs;")
        conn.execute(
            """
            CREATE SECRET (
                TYPE S3,
                KEY_ID ?,
                SECRET ?,
                REGION 'auto',
                ENDPOINT ?,
                URL_STYLE 'path'
            );
            """,
            [
                r2_conf.access_key_id,
                r2_conf.secret_access_key.get_secret_value(),
                r2_conf.endpoint_url.replace("https://", ""),
            ],
        )

        # Parquetファイルのパスパターン
        parquet_url = f"s3://{r2_conf.bucket_name}/{r2_conf.events_path}youtube/watch_history/**/*.parquet"

        logger.info(f"📂 Path: {parquet_url}")

        # 1. 総件数の確認
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM read_parquet(?)", [parquet_url]
            ).fetchone()[0]
            logger.info("✅ Connection successful. Total records in R2: %s", count)

            if count == 0:
                logger.info("ℹ️ R2 watch_history is empty. Run ingestion first.")
                return

            # 2. スキーマ確認
            logger.info("\n📋 Schema:")
            schema_query = "DESCRIBE SELECT * FROM read_parquet(?) LIMIT 1"
            df_schema = conn.execute(schema_query, [parquet_url]).df()
            print(tabulate(df_schema, headers="keys", tablefmt="simple"))

            # 3. 最新50件の動画リスト表示 (シンプル表示)
            logger.info("\n📊 Latest 50 Videos:")
            query_simple = """
                SELECT video_title, channel_name, watched_at_utc
                FROM read_parquet(?)
                ORDER BY watched_at_utc DESC
                LIMIT 50
            """
            df_simple = conn.execute(query_simple, [parquet_url]).df()

            # インデックスを1から振る
            df_simple.index = df_simple.index + 1
            print(
                tabulate(
                    df_simple[["video_title", "channel_name"]],
                    headers=["#", "Video Title", "Channel"],
                    tablefmt="simple",
                )
            )

            # 4. 直近5件の詳細表示 (デバッグ用)
            logger.info("\n🔍 Detailed View (Latest 5):")
            query_detail = """
                SELECT watched_at_utc, video_id, video_title, channel_name,
                    channel_id, video_url
                FROM read_parquet(?)
                ORDER BY watched_at_utc DESC
                LIMIT 5
            """
            df_detail = conn.execute(query_detail, [parquet_url]).df()
            print(tabulate(df_detail, headers="keys", tablefmt="simple_grid"))

        except duckdb.IOException as e:
            if "No files found" in str(e):
                logger.warning("⚠️ No Parquet files found for YouTube watch_history.")
            else:
                logger.error("❌ DuckDB IO Error: %s", e)

    except duckdb.IOException as e:
        if "No files found" in str(e):
            logger.warning("⚠️ No Parquet files found in the specified path.")
        else:
            logger.error("❌ DuckDB IO Error: %s", e)
    except Exception as e:
        logger.error("❌ Unexpected Error: %s", e)
    finally:
        conn.close()


if __name__ == "__main__":
    verify_r2_data()
