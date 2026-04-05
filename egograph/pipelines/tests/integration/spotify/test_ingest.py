"""Spotify ingest パイプラインのインテグレーションテスト。

MemoryS3 + responses モックを使用し、Collector → Transform → S3 Storage の
全データフローを検証する。
"""

from unittest.mock import patch

import responses
from pydantic import SecretStr

from pipelines.sources.common.config import (
    Config,
    DuckDBConfig,
    R2Config,
    SpotifyConfig,
)
from pipelines.sources.spotify.pipeline import (
    run_spotify_ingest,
)
from pipelines.tests.e2e.test_browser_history_ingest import (
    _MemoryS3Server,
)


def _build_config(memory_s3) -> Config:
    """Spotify pipeline 用の設定を構築する。"""
    r2 = R2Config(
        endpoint_url=memory_s3.endpoint_url,
        access_key_id="test-access-key",
        secret_access_key=SecretStr("test-secret-key"),
        bucket_name="test-bucket",
    )
    return Config(
        spotify=SpotifyConfig(
            client_id="test-client-id",
            client_secret=SecretStr("test-client-secret"),
            refresh_token=SecretStr("test-refresh-token"),
        ),
        duckdb=DuckDBConfig(r2=r2),
    )


def _mock_spotify_api(items: list[dict] | None = None):
    """Spotify API の必要エンドポイントをモックする。"""
    default_items = [
        {
            "track": {
                "id": "3n3Ppam7vgaVa1iaRUc9Lp",
                "name": "Mr. Brightside",
                "artists": [{"id": "0C0XlULifJtAgn6ZNCW2eu", "name": "The Killers"}],
                "album": {"id": "4OHNH3sDzIxnmUADXzv2kT", "name": "Hot Fuss"},
                "duration_ms": 222973,
                "popularity": 85,
            },
            "played_at": "2026-04-01T02:30:00.000Z",
            "context": {
                "type": "playlist",
                "uri": "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M",
            },
        },
        {
            "track": {
                "id": "0VjIjW4GlUZAMYd2vXMi3b",
                "name": "Blinding Lights",
                "artists": [{"id": "1Xyo4u8uXC1ZmMpatF05PJ", "name": "The Weeknd"}],
                "album": {"id": "4yP0hdKOZPNshxUOjY0cZj", "name": "After Hours"},
                "duration_ms": 200040,
                "popularity": 92,
            },
            "played_at": "2026-04-01T02:26:00.000Z",
            "context": {
                "type": "album",
                "uri": "spotify:album:4yP0hdKOZPNshxUOjY0cZj",
            },
        },
    ]
    recently_played_items = items if items is not None else default_items

    responses.add(
        responses.POST,
        "https://accounts.spotify.com/api/token",
        json={
            "access_token": "mock-access-token",
            "expires_in": 3600,
            "token_type": "Bearer",
        },
        status=200,
    )
    responses.add(
        responses.GET,
        "https://api.spotify.com/v1/me/player/recently-played",
        json={"items": recently_played_items},
        status=200,
    )


@responses.activate
def test_ingest_saves_raw_events_and_state():
    """Ingest が raw JSON, events Parquet, ingest state を S3 に保存する。"""
    with _MemoryS3Server() as memory_s3:
        config = _build_config(memory_s3)
        _mock_spotify_api()

        with patch(
            "pipelines.sources.spotify.ingest_pipeline.enrich_master_data",
        ):
            result = run_spotify_ingest(config=config)

        assert result["status"] == "succeeded"
        object_keys = {key for _, key in memory_s3.objects}

        assert any(k.startswith("raw/spotify/recently_played/") for k in object_keys), (
            "raw data not found"
        )

        assert any(k.startswith("events/spotify/plays/year=") for k in object_keys), (
            "events parquet not found"
        )

        assert any("state/spotify_ingest_state.json" in k for k in object_keys), (
            "ingest state not found"
        )


@responses.activate
def test_ingest_no_data_returns_early():
    """新規データなしの場合、保存処理を実行せずに早期リターンする。"""
    with _MemoryS3Server() as memory_s3:
        config = _build_config(memory_s3)
        _mock_spotify_api(items=[])

        with patch(
            "pipelines.sources.spotify.ingest_pipeline.enrich_master_data",
        ):
            result = run_spotify_ingest(config=config)

        assert result["status"] == "succeeded"
        # 新規データなし → 保存処理が実行されない
        assert len(memory_s3.objects) == 0
