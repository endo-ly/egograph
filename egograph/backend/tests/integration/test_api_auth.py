"""API Key / Tailscale app capability 認証の統合テスト。

認証を通過したリクエストは未登録パスで 404、拒否されたリクエストは 401 になる。
この差で認証ミドルウェアの判定だけを検証する。
"""

import json

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app

CAPABILITY = "example.com/cap/egograph-read"
UNROUTED_PATH = "/v1/data/__auth_probe__"
CAPABILITY_HEADER = "Tailscale-App-Capabilities"


@pytest.fixture
def capability_client(mock_backend_config):
    """Tailscale app capability 認証を有効化した TestClient。"""
    mock_backend_config.tailscale_app_capability = CAPABILITY
    app = create_app(config=mock_backend_config)
    with TestClient(app) as client:
        yield client


def _capability_header(capabilities: dict) -> dict[str, str]:
    """tailscale serve が付与する形式の app capability ヘッダーを作る。"""
    return {CAPABILITY_HEADER: json.dumps(capabilities)}


class TestApiKeyAuth:
    """API Key 認証のテスト。"""

    def test_request_with_valid_api_key_passes(self, capability_client):
        """正しい API Key があれば認証を通過する。"""
        # Arrange
        headers = {"X-API-Key": "test-backend-key"}

        # Act
        response = capability_client.get(UNROUTED_PATH, headers=headers)

        # Assert
        assert response.status_code == 404

    def test_request_without_credentials_returns_401(self, capability_client):
        """API Key も app capability もなければ 401 を返す。"""
        # Act
        response = capability_client.get(UNROUTED_PATH)

        # Assert
        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid API key"}


class TestTailscaleAppCapabilityAuth:
    """Tailscale app capability 認証のテスト。"""

    @pytest.mark.parametrize(
        "capabilities",
        [
            {CAPABILITY: [{}]},
            {CAPABILITY: []},
            {"example.com/cap/other": [{}], CAPABILITY: [{"access": "read"}]},
        ],
    )
    def test_request_with_granted_capability_passes(
        self, capability_client, capabilities
    ):
        """設定した capability が付与されていれば API Key なしで認証を通過する。"""
        # Arrange
        headers = _capability_header(capabilities)

        # Act
        response = capability_client.get(UNROUTED_PATH, headers=headers)

        # Assert
        assert response.status_code == 404

    @pytest.mark.parametrize(
        "header_value",
        [
            json.dumps({}),
            json.dumps({"example.com/cap/other": [{}]}),
            json.dumps([CAPABILITY]),
            json.dumps(CAPABILITY),
            "not-json",
            "=?utf-8?q?=7B=22example.com/cap/egograph-read=22:[]=7D?=",
        ],
    )
    def test_request_without_granted_capability_returns_401(
        self, capability_client, header_value
    ):
        """capability が無い・解析できないヘッダーは拒否する。"""
        # Arrange
        headers = {CAPABILITY_HEADER: header_value}

        # Act
        response = capability_client.get(UNROUTED_PATH, headers=headers)

        # Assert
        assert response.status_code == 401

    def test_capability_header_is_ignored_when_not_configured(
        self, mock_backend_config
    ):
        """capability 未設定時はヘッダーがあっても API Key を要求する。"""
        # Arrange
        mock_backend_config.tailscale_app_capability = None
        app = create_app(config=mock_backend_config)
        headers = _capability_header({CAPABILITY: [{}]})

        # Act
        with TestClient(app) as client:
            response = client.get(UNROUTED_PATH, headers=headers)

        # Assert
        assert response.status_code == 401

    def test_capability_grants_mcp_access(self, capability_client):
        """capability 認証は REST と同じく MCP にも適用される。"""
        # Arrange
        headers = {
            **_capability_header({CAPABILITY: [{}]}),
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        payload = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "id": 1,
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0.1"},
            },
        }

        # Act
        response = capability_client.post("/mcp", json=payload, headers=headers)

        # Assert
        assert response.status_code == 200
