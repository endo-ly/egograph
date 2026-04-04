"""Spotify 実 API テスト（CI 除外）。"""

import os

import pytest

from pipelines.sources.spotify.collector import SpotifyCollector


@pytest.mark.live
@pytest.mark.skipif(
    not os.getenv("SPOTIFY_CLIENT_ID"),
    reason="SPOTIFY_CLIENT_ID not set",
)
def test_live_spotify_collector_gets_recently_played():
    """実 Spotify API から最近再生した曲を取得できる。"""
    # Arrange
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    refresh_token = os.getenv("SPOTIFY_REFRESH_TOKEN")

    collector = SpotifyCollector(
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
    )

    # Act
    tracks = collector.get_recently_played(limit=5)

    # Assert
    assert isinstance(tracks, list)
    # API レスポンスの構造確認
    if tracks:
        item = tracks[0]
        assert "track" in item
        assert "played_at" in item


@pytest.mark.live
@pytest.mark.skipif(
    not os.getenv("SPOTIFY_CLIENT_ID"),
    reason="SPOTIFY_CLIENT_ID not set",
)
def test_live_spotify_collector_refreshes_token():
    """トークンリフレッシュが正常に動作する。"""
    # Arrange
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    refresh_token = os.getenv("SPOTIFY_REFRESH_TOKEN")

    collector = SpotifyCollector(
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
    )

    # Act
    access_token = collector._refresh_access_token()

    # Assert
    assert access_token is not None
    assert len(access_token) > 0
