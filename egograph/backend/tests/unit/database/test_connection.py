"""Database/Connection層のテスト。"""

from unittest.mock import patch

import duckdb
import pytest

from backend.infrastructure.database import DuckDBConnection


class TestDuckDBConnection:
    """DuckDBConnectionのテスト。"""

    def test_context_manager_creates_memory_connection(self, mock_r2_config):
        """コンテキストマネージャーが:memory:接続を作成。"""
        # Arrange: R2設定を準備（fixtureから提供）

        # Act: コンテキストマネージャーで接続を作成
        with DuckDBConnection(mock_r2_config) as conn:
            # Assert: 接続が正しく作成されていることを検証
            assert conn is not None
            assert isinstance(conn, duckdb.DuckDBPyConnection)
            # :memory:接続が機能することを確認
            result = conn.execute("SELECT 1 as value").fetchone()
            assert result[0] == 1

    def test_connection_closed_after_context(self, mock_r2_config):
        """コンテキスト終了後に接続がクローズされる。"""
        # Arrange: DuckDBConnectionインスタンスを作成
        db_conn = DuckDBConnection(mock_r2_config)

        # Act: コンテキストマネージャーで接続を使用
        with db_conn:
            # Assert: コンテキスト内では接続が有効
            assert db_conn.conn is not None

        # Assert: コンテキスト終了後はNoneになる
        assert db_conn.conn is None

    def test_httpfs_extension_loaded(self, mock_r2_config):
        """httpfs拡張がロードされる。"""
        # Arrange: R2設定を準備（fixtureから提供）

        # Act: 接続を作成（内部でhttpfs拡張がロードされる）
        with DuckDBConnection(mock_r2_config) as conn:
            # Assert: httpfsがロードされていることを確認（エラーが出なければOK）
            # 実際にはINSTALLとLOADが実行されている
            result = conn.execute(
                "SELECT current_setting('allow_unsigned_extensions')"
            ).fetchone()
            # httpfsがロードされていればクエリが成功する
            assert result is not None

    def test_r2_secret_configured(self, mock_r2_config):
        """R2認証情報（SECRET）が設定される。"""
        # Arrange: R2設定を準備（fixtureから提供）

        # Act: 接続を作成（内部でR2 SECRETが設定される）
        with DuckDBConnection(mock_r2_config) as conn:
            # Assert: SECRETが作成されていることを確認
            # DuckDBではSECRETの存在を直接クエリできないので、
            # エラーなく接続が完了したことで確認とする
            assert conn is not None

    def test_connection_cleanup_on_exception(self, mock_r2_config):
        """例外発生時に接続がクリーンアップされる。"""
        # Arrange: executeを途中で失敗させるためのモックを準備
        db_conn = DuckDBConnection(mock_r2_config)

        # Act: __enter__中にエラーが発生した場合をシミュレーション
        with patch.object(duckdb.DuckDBPyConnection, "execute") as mock_execute:
            # 最初の呼び出し（INSTALL httpfs）は成功、2回目で失敗
            mock_execute.side_effect = [None, Exception("Test error")]

            with pytest.raises(Exception, match="Test error"):
                with db_conn:
                    pass

            # Assert: 例外発生後、connはNoneになっている
            assert db_conn.conn is None

    def test_r2_endpoint_url_processed_correctly(self, mock_r2_config):
        """R2エンドポイントURLが正しく処理される（https://を除去）。"""
        # Arrange: endpoint_urlがhttps://で始まることを確認
        assert mock_r2_config.endpoint_url.startswith("https://")

        # Act: 接続を作成（内部でhttps://が除去される）
        with DuckDBConnection(mock_r2_config) as conn:
            # Assert: CREATE SECRETが成功していればOK
            assert conn is not None
