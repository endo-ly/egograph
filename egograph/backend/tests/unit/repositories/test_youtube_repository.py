"""YouTube Repository層のテスト（REDフェーズ）。"""

from datetime import date
from unittest.mock import MagicMock, patch

from pydantic import SecretStr

from backend.infrastructure.repositories.youtube_repository import YouTubeRepository
from backend.config import R2Config


class TestYouTubeRepository:
    """YouTubeRepositoryのテスト。"""

    def test_get_watch_history(self, youtube_with_sample_data):
        """視聴履歴を取得。"""
        # Arrange
        watches_parquet_path = youtube_with_sample_data.test_watches_parquet_path
        videos_parquet_path = youtube_with_sample_data.test_videos_parquet_path

        with patch(
            "backend.infrastructure.database.DuckDBConnection"
        ) as mock_conn_class:
            mock_conn = MagicMock()
            mock_conn.__enter__ = MagicMock(return_value=youtube_with_sample_data)
            mock_conn.__exit__ = MagicMock(return_value=False)
            mock_conn_class.return_value = mock_conn

            with patch(
                "backend.infrastructure.database.youtube_queries._generate_partition_paths",
                return_value=[watches_parquet_path],
            ):
                with patch(
                    "backend.infrastructure.database.youtube_queries.get_videos_parquet_path",
                    return_value=videos_parquet_path,
                ):
                    # Act
                    repo = YouTubeRepository(mock_r2_config())
                    result = repo.get_watch_history(date(2024, 1, 1), date(2024, 1, 3))

        # Assert
        assert len(result) > 0
        assert "watch_id" in result[0]
        assert "video_title" in result[0]

    def test_get_watching_stats(self, youtube_with_sample_data):
        """視聴統計を取得。"""
        # Arrange
        watches_parquet_path = youtube_with_sample_data.test_watches_parquet_path
        videos_parquet_path = youtube_with_sample_data.test_videos_parquet_path

        with patch(
            "backend.infrastructure.database.DuckDBConnection"
        ) as mock_conn_class:
            mock_conn = MagicMock()
            mock_conn.__enter__ = MagicMock(return_value=youtube_with_sample_data)
            mock_conn.__exit__ = MagicMock(return_value=False)
            mock_conn_class.return_value = mock_conn

            with patch(
                "backend.infrastructure.database.youtube_queries._generate_partition_paths",
                return_value=[watches_parquet_path],
            ):
                with patch(
                    "backend.infrastructure.database.youtube_queries.get_videos_parquet_path",
                    return_value=videos_parquet_path,
                ):
                    # Act
                    repo = YouTubeRepository(mock_r2_config())
                    result = repo.get_watching_stats(
                        date(2024, 1, 1), date(2024, 1, 3), granularity="day"
                    )

        # Assert
        assert len(result) > 0
        assert "period" in result[0]
        assert "total_seconds" in result[0]
        assert "video_count" in result[0]

    def test_get_top_channels(self, youtube_with_sample_data):
        """トップチャンネルを取得。"""
        # Arrange
        watches_parquet_path = youtube_with_sample_data.test_watches_parquet_path
        videos_parquet_path = youtube_with_sample_data.test_videos_parquet_path

        with patch(
            "backend.infrastructure.database.DuckDBConnection"
        ) as mock_conn_class:
            mock_conn = MagicMock()
            mock_conn.__enter__ = MagicMock(return_value=youtube_with_sample_data)
            mock_conn.__exit__ = MagicMock(return_value=False)
            mock_conn_class.return_value = mock_conn

            with patch(
                "backend.infrastructure.database.youtube_queries._generate_partition_paths",
                return_value=[watches_parquet_path],
            ):
                with patch(
                    "backend.infrastructure.database.youtube_queries.get_videos_parquet_path",
                    return_value=videos_parquet_path,
                ):
                    # Act
                    repo = YouTubeRepository(mock_r2_config())
                    result = repo.get_top_channels(date(2024, 1, 1), date(2024, 1, 3))

        # Assert
        assert len(result) > 0
        assert "channel_id" in result[0]
        assert "channel_name" in result[0]
        assert "total_seconds" in result[0]
        assert "video_count" in result[0]


def mock_r2_config():
    """モックR2設定。"""
    return R2Config.model_construct(
        endpoint_url="https://test.r2.cloudflarestorage.com",
        access_key_id="test_key",
        secret_access_key=SecretStr("test_secret"),
        bucket_name="test-bucket",
        raw_path="raw/",
        events_path="events/",
        master_path="master/",
    )
