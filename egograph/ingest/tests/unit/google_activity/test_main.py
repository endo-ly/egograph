"""main.py の環境変数ロード機能のテスト。"""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from ingest.google_activity.main import _load_cookies, _load_google_accounts


class TestLoadCookies:
    """_load_cookies 関数のテスト。"""

    def test_load_cookies_from_file(self, tmp_path: Path):
        """ファイルパスからCookieを読み込めること。"""
        # Arrange
        cookies_data = [
            {"name": "SID", "value": "test_sid_value"},
            {"name": "HSID", "value": "test_hsid_value"},
        ]
        cookie_file = tmp_path / "cookies.json"
        cookie_file.write_text(json.dumps(cookies_data))

        # Act
        with patch.dict(os.environ, {"TEST_COOKIE": str(cookie_file)}):
            result = _load_cookies("TEST_COOKIE")

        # Assert
        assert len(result) == 2
        assert result[0]["name"] == "SID"
        assert result[0]["value"] == "test_sid_value"

    def test_load_cookies_from_json_string(self):
        """JSON文字列からCookieを読み込めること(配列形式)。"""
        # Arrange
        cookies_json = json.dumps(
            [
                {"name": "SID", "value": "test_sid_value"},
                {"name": "HSID", "value": "test_hsid_value"},
            ]
        )

        # Act
        with patch.dict(os.environ, {"TEST_COOKIE": cookies_json}):
            result = _load_cookies("TEST_COOKIE")

        # Assert
        assert len(result) == 2
        assert result[0]["name"] == "SID"

    def test_load_cookies_from_json_dict(self):
        """JSON文字列からCookieを読み込めること(辞書形式)。"""
        # Arrange
        cookies_json = json.dumps(
            {
                "SID": "test_sid_value",
                "HSID": "test_hsid_value",
            }
        )

        # Act
        with patch.dict(os.environ, {"TEST_COOKIE": cookies_json}):
            result = _load_cookies("TEST_COOKIE")

        # Assert
        assert len(result) == 2
        assert result[0]["name"] == "SID"
        assert result[0]["value"] == "test_sid_value"

    def test_load_cookies_from_key_value_format(self):
        """key=value,key=value形式からCookieを読み込めること。"""
        # Arrange
        cookies_str = "SID=test_sid_value,HSID=test_hsid_value"

        # Act
        with patch.dict(os.environ, {"TEST_COOKIE": cookies_str}):
            result = _load_cookies("TEST_COOKIE")

        # Assert
        assert len(result) == 2
        assert result[0]["name"] == "SID"
        assert result[0]["value"] == "test_sid_value"

    def test_load_cookies_not_set_returns_none(self):
        """環境変数が未設定の場合はNoneを返すこと。"""
        # Arrange
        env = {k: v for k, v in os.environ.items() if k != "TEST_COOKIE"}

        # Act
        with patch.dict(os.environ, env, clear=True):
            result = _load_cookies("TEST_COOKIE")

        # Assert
        assert result is None

    def test_load_cookies_file_not_found(self, tmp_path: Path):
        """ファイルが存在しない場合はエラーになること。"""
        # Arrange
        nonexistent_file = tmp_path / "nonexistent.json"

        # Act & Assert
        with patch.dict(os.environ, {"TEST_COOKIE": str(nonexistent_file)}):
            with pytest.raises(ValueError) as exc_info:
                _load_cookies("TEST_COOKIE")

        assert "Cookie file not found" in str(exc_info.value)

    def test_load_cookies_invalid_json(self, tmp_path: Path):
        """ファイルのJSONが無効な場合はエラーになること。"""
        # Arrange
        cookie_file = tmp_path / "invalid.json"
        cookie_file.write_text("{invalid json")

        # Act & Assert
        with patch.dict(os.environ, {"TEST_COOKIE": str(cookie_file)}):
            with pytest.raises(ValueError) as exc_info:
                _load_cookies("TEST_COOKIE")

        assert "Invalid JSON" in str(exc_info.value)

    def test_load_cookies_empty_key_value_format(self):
        """空のkey=value形式の場合はエラーになること。"""
        # Arrange
        cookies_str = ""

        # Act & Assert
        with patch.dict(os.environ, {"TEST_COOKIE": cookies_str}):
            with pytest.raises(ValueError) as exc_info:
                _load_cookies("TEST_COOKIE")

        assert "invalid_cookies" in str(exc_info.value)
        assert "no valid key=value pairs" in str(exc_info.value)

    def test_load_cookies_no_valid_pairs(self):
        """有効なkey=valueペアがない場合はエラーになること。"""
        # Arrange
        cookies_str = "invalid,noequals,here"

        # Act & Assert
        with patch.dict(os.environ, {"TEST_COOKIE": cookies_str}):
            with pytest.raises(ValueError) as exc_info:
                _load_cookies("TEST_COOKIE")

        assert "invalid_cookies" in str(exc_info.value)
        assert "no valid key=value pairs" in str(exc_info.value)


class TestLoadGoogleAccounts:
    """_load_google_accounts 関数のテスト。"""

    def test_load_single_account(self):
        """単一アカウントを読み込めること。"""
        # Arrange
        cookies = [{"name": "SID", "value": "test_value"}]
        expected_cookies = [
            {
                "name": "SID",
                "value": "test_value",
                "domain": ".google.com",
                "path": "/",
                "sameSite": "Lax",
            }
        ]
        env = {
            "YOUTUBE_API_KEY": "test_api_key",
            "GOOGLE_COOKIE_ACCOUNT1": json.dumps(cookies),
        }

        # Act
        with patch.dict(os.environ, env, clear=True):
            accounts = _load_google_accounts()

        # Assert
        assert len(accounts) == 1
        assert accounts[0].account_id == "account1"
        assert accounts[0].youtube_api_key == "test_api_key"
        assert accounts[0].cookies == expected_cookies

    def test_load_two_accounts(self):
        """2つのアカウントを読み込めること。"""
        # Arrange
        cookies_1 = [{"name": "SID", "value": "account1_value"}]
        cookies_2 = [{"name": "SID", "value": "account2_value"}]
        env = {
            "YOUTUBE_API_KEY": "test_api_key",
            "GOOGLE_COOKIE_ACCOUNT1": json.dumps(cookies_1),
            "GOOGLE_COOKIE_ACCOUNT2": json.dumps(cookies_2),
        }

        # Act
        with patch.dict(os.environ, env, clear=True):
            accounts = _load_google_accounts()

        # Assert
        assert len(accounts) == 2
        assert accounts[0].account_id == "account1"
        assert accounts[1].account_id == "account2"

    def test_load_accounts_missing_api_key(self):
        """APIキーが未設定の場合はエラーになること。"""
        # Arrange
        env = {
            "GOOGLE_COOKIE_ACCOUNT1": json.dumps([{"name": "SID", "value": "test"}]),
        }

        # Act & Assert
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError) as exc_info:
                _load_google_accounts()

        assert "YOUTUBE_API_KEY is required" in str(exc_info.value)

    def test_load_accounts_missing_account1(self):
        """アカウント1が未設定の場合はエラーになること。"""
        # Arrange
        env = {
            "YOUTUBE_API_KEY": "test_api_key",
        }

        # Act & Assert
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError) as exc_info:
                _load_google_accounts()

        assert "At least one account" in str(exc_info.value)

    def test_load_accounts_from_file_path(self, tmp_path: Path):
        """ファイルパスからCookieを読み込めること。"""
        # Arrange
        cookies_data = [{"name": "SID", "value": "test_value"}]
        expected_cookies = [
            {
                "name": "SID",
                "value": "test_value",
                "domain": ".google.com",
                "path": "/",
                "sameSite": "Lax",
            }
        ]
        cookie_file = tmp_path / "cookies.json"
        cookie_file.write_text(json.dumps(cookies_data))

        env = {
            "YOUTUBE_API_KEY": "test_api_key",
            "GOOGLE_COOKIE_ACCOUNT1": f"./{cookie_file.name}",
        }

        # Act
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            with patch.dict(os.environ, env, clear=True):
                accounts = _load_google_accounts()
        finally:
            os.chdir(original_cwd)

        # Assert
        assert len(accounts) == 1
        assert accounts[0].cookies == expected_cookies
