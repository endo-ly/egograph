"""DuckDB接続管理。

ステートレス設計：:memory:モードで毎回新規接続を作成し、
R2のParquetファイルを直接クエリします。
"""

import hashlib
import logging
from urllib.parse import urlparse

import duckdb

from backend.config import R2Config

logger = logging.getLogger(__name__)


class DuckDBConnection:
    """ステートレスDuckDB接続マネージャー。

    コンテキストマネージャーとして使用し、:memory:接続を作成して
    R2のParquetデータに直接アクセスします。

    Example:
        >>> r2_config = R2Config(
        ...     endpoint_url="https://example.r2.cloudflarestorage.com",
        ...     access_key_id="test",
        ...     secret_access_key=SecretStr("secret"),
        ... )
        >>> with DuckDBConnection(r2_config) as conn:
        ...     sql = "SELECT COUNT(*) FROM read_parquet(?)"
        ...     result = conn.execute(sql, [parquet_url])
        ...     count = result.fetchone()[0]
    """

    def __init__(self, r2_config: R2Config):
        """DuckDBConnectionを初期化します。

        Args:
            r2_config: R2設定（認証情報とバケット情報）
        """
        self.r2_config = r2_config
        self.conn: duckdb.DuckDBPyConnection | None = None

    def _build_secret_name(self, endpoint: str) -> str:
        """R2用のSECRET名を生成する。

        同一エンドポイント/アクセスキー/シークレットキーでも衝突しないようにハッシュ化する。
        """
        seed = (
            f"{endpoint}|{self.r2_config.access_key_id}"
            f"|{self.r2_config.secret_access_key.get_secret_value()}"
        )
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
        return f"r2_{digest}"

    def __enter__(self) -> duckdb.DuckDBPyConnection:
        """コンテキストマネージャーのエントリー。

        :memory:接続を作成し、R2アクセス用の設定を行います。

        Returns:
            設定済みのDuckDBコネクション

        Raises:
            duckdb.Error: DuckDB接続またはR2設定に失敗した場合
        """
        logger.debug("Creating DuckDB :memory: connection")
        self.conn = duckdb.connect(":memory:")

        try:
            # httpfs拡張のインストールとロード（最適化版）
            # 既にインストール済みならLOADのみ実行して高速化
            try:
                self.conn.execute("LOAD httpfs;")
                logger.debug("Loaded httpfs extension (already installed)")
            except (duckdb.CatalogException, duckdb.IOException):
                # 未インストールまたはバイナリ破損ならINSTALL → LOAD
                self.conn.execute("INSTALL httpfs;")
                self.conn.execute("LOAD httpfs;")
                logger.debug("Installed and loaded httpfs extension")

            # R2認証情報の設定（CREATE SECRET）
            parsed = urlparse(self.r2_config.endpoint_url)
            endpoint = parsed.netloc or parsed.path
            if not endpoint:
                raise ValueError(
                    f"Invalid R2 endpoint URL: '{self.r2_config.endpoint_url}'. "
                    "Could not extract hostname or path."
                )
            secret_name = self._build_secret_name(endpoint)
            # SECRET名はidentifierなのでプレースホルダではなくquotingで保護
            # secret_nameはハッシュ値なので英数字のみだが、安全のためquoteする
            try:
                self.conn.execute(f'DROP SECRET IF NOT EXISTS "{secret_name}";')
            except duckdb.Error:
                pass

            # CREATE SECRETではSECRET名はidentifierなので直接埋め込み（quote済み）
            # 認証情報はプレースホルダを使用
            self.conn.execute(
                f"""
                CREATE SECRET "{secret_name}" (
                    TYPE S3,
                    KEY_ID ?,
                    SECRET ?,
                    REGION 'auto',
                    ENDPOINT ?,
                    URL_STYLE 'path'
                );
                """,
                [
                    self.r2_config.access_key_id,
                    self.r2_config.secret_access_key.get_secret_value(),
                    endpoint,
                ],
            )
            logger.debug("Configured R2 secret for endpoint: %s", endpoint)

        except Exception:
            logger.exception("Failed to configure DuckDB connection")
            if self.conn:
                self.conn.close()
                self.conn = None
            raise

        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        """コンテキストマネージャーの終了。

        接続をクローズします。
        """
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.debug("Closed DuckDB connection")
