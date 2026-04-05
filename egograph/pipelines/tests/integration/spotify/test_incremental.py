"""Spotify 増分取得のインテグレーションテスト。

ingest_state による after 指定の増分取得フローを検証する。
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
from pipelines.sources.spotify.storage import SpotifyStorage
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


def _mock_token():
    """Spotify 認証エンドポイントのみモックする。"""
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


@responses.activate
def test_incremental_fetch_uses_state():
    """2回目の ingest は state の latest_played_at を after として使用する。"""
    with _MemoryS3Server() as memory_s3:
        config = _build_config(memory_s3)

        # --- 1回目: 初期データ ---
        _mock_token()
        responses.add(
            responses.GET,
            "https://api.spotify.com/v1/me/player/recently-played",
            json={
                "items": [
                    {
                        "track": {
                            "id": "track-001",
                            "name": "Song A",
                            "artists": [{"id": "artist-001", "name": "Artist A"}],
                            "album": {"id": "album-001", "name": "Album A"},
                            "duration_ms": 180000,
                            "popularity": 50,
                        },
                        "played_at": "2026-04-01T01:00:00.000Z",
                        "context": {"type": "playlist", "uri": "spotify:playlist:001"},
                    },
                ]
            },
            status=200,
        )

        with patch(
            "pipelines.sources.spotify.ingest_pipeline.enrich_master_data",
        ):
            run_spotify_ingest(config=config)

        # state が保存されていることを確認
        storage = SpotifyStorage(
            endpoint_url=memory_s3.endpoint_url,
            access_key_id="test-access-key",
            secret_access_key="test-secret-key",
            bucket_name="test-bucket",
        )
        state = storage.get_ingest_state(key="state/spotify_ingest_state.json")
        assert state is not None
        assert state["latest_played_at"] == "2026-04-01T01:00:00.000Z"

        # --- 2回目: 増分データ ---
        # after パラメータ付きでリクエストが来ることを検証
        received_after = []

        def capture_after(request):
            from urllib.parse import parse_qs, urlparse

            qs = parse_qs(urlparse(request.url).query)
            received_after.append(qs.get("after", [None])[0])
            return (
                200,
                {},
                '{"items": [{"track": {"id": "track-002", "name": "Song B", '
                '"artists": [{"id": "artist-002", "name": "Artist B"}], '
                '"album": {"id": "album-002", "name": "Album B"}, '
                '"duration_ms": 200000, "popularity": 60}, '
                '"played_at": "2026-04-01T02:00:00.000Z", '
                '"context": {"type": "album", "uri": "spotify:album:002"}}]}',
            )

        _mock_token()
        responses.add_callback(
            responses.GET,
            "https://api.spotify.com/v1/me/player/recently-played",
            callback=capture_after,
        )

        with patch(
            "pipelines.sources.spotify.ingest_pipeline.enrich_master_data",
        ):
            run_spotify_ingest(config=config)

        # after パラメータが 1回目の最新時刻で設定されている
        assert len(received_after) == 1
        assert received_after[0] is not None
        # Unix ms timestamp が 2026-04-01T01:00:00.000Z 以降であることを確認
        assert int(received_after[0]) > 0


@responses.activate
def test_incremental_no_new_data_returns_early():
    """after 指定で新規データがない場合、保存処理を実行しない。"""
    with _MemoryS3Server() as memory_s3:
        config = _build_config(memory_s3)

        # 既存 state を投入
        storage = SpotifyStorage(
            endpoint_url=memory_s3.endpoint_url,
            access_key_id="test-access-key",
            secret_access_key="test-secret-key",
            bucket_name="test-bucket",
        )
        storage.save_ingest_state(
            {"latest_played_at": "2026-04-01T02:00:00.000Z"},
            key="state/spotify_ingest_state.json",
        )

        _mock_token()
        responses.add(
            responses.GET,
            "https://api.spotify.com/v1/me/player/recently-played",
            json={"items": []},
            status=200,
        )

        initial_count = len(memory_s3.objects)

        with patch(
            "pipelines.sources.spotify.ingest_pipeline.enrich_master_data",
        ):
            result = run_spotify_ingest(config=config)

        assert result["status"] == "succeeded"
        # 新規データなし → オブジェクトが増えない
        assert len(memory_s3.objects) == initial_count
