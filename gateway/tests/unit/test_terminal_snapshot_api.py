"""Terminal snapshot API の単体テスト。"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.exceptions import HTTPException

from gateway.api.terminal import get_session_snapshot


@pytest.fixture
def mock_request():
    """テスト用リクエスト。"""
    request = MagicMock()
    request.headers = {"X-API-Key": "valid_api_key_32_bytes_or_more"}
    request.path_params = {}
    return request


class TestGetSessionSnapshot:
    """get_session_snapshot エンドポイントのテスト。"""

    @pytest.mark.asyncio
    async def test_missing_session_id_returns_400(self, mock_request):
        """session_id が欠落している場合に 400 を返すことを確認する。"""
        with patch("gateway.api.terminal.verify_gateway_token"):
            with pytest.raises(HTTPException) as exc_info:
                await get_session_snapshot(mock_request)

        assert exc_info.value.status_code == 400
        assert "Invalid session_id format" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_session_not_found_returns_404(self, mock_request):
        """存在しないセッションの場合に 404 を返すことを確認する。"""
        mock_request.path_params = {"session_id": "agent-0001"}

        with (
            patch("gateway.api.terminal.verify_gateway_token"),
            patch("gateway.api.terminal.anyio.to_thread.run_sync") as mock_run_sync,
        ):
            mock_run_sync.return_value = False

            with pytest.raises(HTTPException) as exc_info:
                await get_session_snapshot(mock_request)

        assert exc_info.value.status_code == 404
        assert "Session not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_capture_failure_returns_500(self, mock_request):
        """snapshot 取得失敗時に 500 を返すことを確認する。"""
        mock_request.path_params = {"session_id": "agent-0001"}

        with (
            patch("gateway.api.terminal.verify_gateway_token"),
            patch("gateway.api.terminal.anyio.to_thread.run_sync") as mock_run_sync,
            patch("gateway.api.terminal.TmuxAttachManager") as mock_manager_class,
        ):
            mock_run_sync.return_value = True
            mock_manager = MagicMock()
            mock_manager.capture_snapshot = AsyncMock(
                side_effect=RuntimeError("capture failed")
            )
            mock_manager_class.return_value = mock_manager

            with pytest.raises(HTTPException) as exc_info:
                await get_session_snapshot(mock_request)

        assert exc_info.value.status_code == 500
        assert "Failed to capture snapshot" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_success_returns_snapshot_json(self, mock_request):
        """正常系で snapshot JSON を返すことを確認する。"""
        mock_request.path_params = {"session_id": "agent-0001"}

        with (
            patch("gateway.api.terminal.verify_gateway_token"),
            patch("gateway.api.terminal.anyio.to_thread.run_sync") as mock_run_sync,
            patch("gateway.api.terminal.TmuxAttachManager") as mock_manager_class,
        ):
            mock_run_sync.return_value = True
            mock_manager = MagicMock()
            mock_manager.capture_snapshot = AsyncMock(return_value=b"line 1\nline 2")
            mock_manager_class.return_value = mock_manager

            response = await get_session_snapshot(mock_request)

        assert response.status_code == 200
        body = json.loads(response.body.decode())
        assert body == {
            "session_id": "agent-0001",
            "content": "line 1\nline 2",
        }
        assert response.headers["Cache-Control"] == "no-store"
        assert response.headers["Pragma"] == "no-cache"
        mock_manager.capture_snapshot.assert_awaited_once_with(
            include_escape_sequences=False
        )
