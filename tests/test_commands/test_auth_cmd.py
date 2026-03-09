"""gfo.commands.auth_cmd のテスト。"""

from __future__ import annotations

import pytest
from unittest.mock import patch, call

from gfo.commands import auth_cmd
from gfo.detect import DetectResult
from gfo.exceptions import ConfigError, DetectionError
from tests.test_commands.conftest import make_args


def _make_detect_result(host: str = "github.com") -> DetectResult:
    return DetectResult(
        service_type="github",
        host=host,
        owner="test-owner",
        repo="test-repo",
    )


class TestHandleLogin:
    """handle_login のテスト。"""

    def test_host_and_token_specified(self, capsys):
        """--host と --token 両方指定 → 警告表示 + save_token 呼び出し。"""
        args = make_args(host="github.com", token="my-token")

        with patch("gfo.commands.auth_cmd.gfo.auth.save_token") as mock_save:
            auth_cmd.handle_login(args, fmt="table")

        mock_save.assert_called_once_with("github.com", "my-token")
        captured = capsys.readouterr()
        assert "Token saved for github.com" in captured.out
        assert "Warning" in captured.err

    def test_host_specified_token_from_getpass(self, capsys):
        """--host 指定、--token なし → getpass 呼び出し + save_token。"""
        args = make_args(host="gitlab.com", token=None)

        with patch("gfo.commands.auth_cmd.gfo.auth.save_token") as mock_save, \
             patch("gfo.commands.auth_cmd.getpass.getpass", return_value="secret") as mock_gp:
            auth_cmd.handle_login(args, fmt="table")

        mock_gp.assert_called_once_with("Token: ")
        mock_save.assert_called_once_with("gitlab.com", "secret")
        captured = capsys.readouterr()
        assert "Token saved for gitlab.com" in captured.out
        assert captured.err == ""

    def test_no_host_uses_detect_service(self, capsys):
        """--host なし → detect_service().host を使用。"""
        args = make_args(host=None, token="tok")

        with patch("gfo.commands.auth_cmd.gfo.detect.detect_service",
                   return_value=_make_detect_result("github.com")), \
             patch("gfo.commands.auth_cmd.gfo.auth.save_token") as mock_save:
            auth_cmd.handle_login(args, fmt="table")

        mock_save.assert_called_once_with("github.com", "tok")

    def test_no_host_detect_service_raises(self):
        """--host なし + detect_service が DetectionError → ConfigError に変換して raise。"""
        args = make_args(host=None, token="tok")

        with patch("gfo.commands.auth_cmd.gfo.detect.detect_service",
                   side_effect=DetectionError("no remote")):
            with pytest.raises(ConfigError, match="--host"):
                auth_cmd.handle_login(args, fmt="table")


class TestHandleLogin_ErrorCases:
    """handle_login のエラー・境界ケースのテスト。"""

    def test_token_warning_message_content(self, capsys):
        """--token 指定時の警告メッセージが stderr に出力される。"""
        args = make_args(host="github.com", token="secret")

        with patch("gfo.commands.auth_cmd.gfo.auth.save_token"):
            auth_cmd.handle_login(args, fmt="table")

        captured = capsys.readouterr()
        assert captured.err.strip() != ""
        # stderr に何らかの警告が出力されること
        assert len(captured.err) > 0

    def test_no_token_option_no_warning(self, capsys):
        """--token なし（getpass 経由）では stderr への警告が出ない。"""
        args = make_args(host="github.com", token=None)

        with patch("gfo.commands.auth_cmd.gfo.auth.save_token"), \
             patch("gfo.commands.auth_cmd.getpass.getpass", return_value="tok"):
            auth_cmd.handle_login(args, fmt="table")

        captured = capsys.readouterr()
        assert captured.err == ""

    def test_empty_token_from_getpass_saved(self):
        """getpass が空文字を返した場合、空トークンで save_token が呼ばれる。"""
        args = make_args(host="github.com", token=None)

        with patch("gfo.commands.auth_cmd.gfo.auth.save_token") as mock_save, \
             patch("gfo.commands.auth_cmd.getpass.getpass", return_value=""):
            auth_cmd.handle_login(args, fmt="table")

        mock_save.assert_called_once_with("github.com", "")

    def test_save_token_propagates_exception(self):
        """save_token が例外を送出した場合、そのまま再 raise される。"""
        args = make_args(host="invalid-host", token="tok")

        with patch("gfo.commands.auth_cmd.gfo.auth.save_token",
                   side_effect=OSError("permission denied")):
            with pytest.raises(OSError, match="permission denied"):
                auth_cmd.handle_login(args, fmt="table")

    def test_no_host_getpass_called(self):
        """--host なし・--token なし → getpass が呼ばれる。"""
        args = make_args(host=None, token=None)

        with patch("gfo.commands.auth_cmd.gfo.detect.detect_service",
                   return_value=_make_detect_result("github.com")), \
             patch("gfo.commands.auth_cmd.gfo.auth.save_token"), \
             patch("gfo.commands.auth_cmd.getpass.getpass", return_value="tok") as mock_gp:
            auth_cmd.handle_login(args, fmt="table")

        mock_gp.assert_called_once_with("Token: ")


class TestHandleStatus:
    """handle_status のテスト。"""

    def test_tokens_configured_shows_table(self, capsys):
        """トークンあり → テーブル表示。"""
        entries = [
            {"host": "github.com", "status": "configured", "source": "credentials.toml"},
        ]
        args = make_args()

        with patch("gfo.commands.auth_cmd.gfo.auth.get_auth_status", return_value=entries):
            auth_cmd.handle_status(args, fmt="table")

        captured = capsys.readouterr()
        assert "github.com" in captured.out
        assert "configured" in captured.out
        assert "credentials.toml" in captured.out

    def test_no_tokens_shows_message(self, capsys):
        """トークンなし → "No tokens configured." 表示。"""
        args = make_args()

        with patch("gfo.commands.auth_cmd.gfo.auth.get_auth_status", return_value=[]):
            auth_cmd.handle_status(args, fmt="table")

        captured = capsys.readouterr()
        assert "No tokens configured." in captured.out

    def test_multiple_entries_all_shown(self, capsys):
        """複数エントリ → すべてのホストが表示される。"""
        entries = [
            {"host": "github.com", "status": "configured", "source": "credentials.toml"},
            {"host": "gitlab.com", "status": "configured", "source": "credentials.toml"},
            {"host": "gitea", "status": "configured", "source": "env:GITEA_TOKEN"},
        ]
        args = make_args()

        with patch("gfo.commands.auth_cmd.gfo.auth.get_auth_status", return_value=entries):
            auth_cmd.handle_status(args, fmt="table")

        captured = capsys.readouterr()
        assert "github.com" in captured.out
        assert "gitlab.com" in captured.out
        assert "gitea" in captured.out
        assert "env:GITEA_TOKEN" in captured.out

    def test_env_source_shown(self, capsys):
        """環境変数経由トークン → source が "env:..." 形式で表示される。"""
        entries = [
            {"host": "github", "status": "configured", "source": "env:GITHUB_TOKEN"},
        ]
        args = make_args()

        with patch("gfo.commands.auth_cmd.gfo.auth.get_auth_status", return_value=entries):
            auth_cmd.handle_status(args, fmt="table")

        captured = capsys.readouterr()
        assert "env:GITHUB_TOKEN" in captured.out

    def test_table_has_header_columns(self, capsys):
        """テーブルヘッダーに HOST / STATUS / SOURCE の列が含まれる。"""
        entries = [
            {"host": "github.com", "status": "configured", "source": "credentials.toml"},
        ]
        args = make_args()

        with patch("gfo.commands.auth_cmd.gfo.auth.get_auth_status", return_value=entries):
            auth_cmd.handle_status(args, fmt="table")

        captured = capsys.readouterr()
        assert "HOST" in captured.out
        assert "STATUS" in captured.out
        assert "SOURCE" in captured.out
