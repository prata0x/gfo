"""gfo.commands.auth_cmd のテスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gfo.commands import auth_cmd, get_adapter, get_adapter_with_config
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
        args = make_args(host="github.com", token="my-token", account="default")

        with patch("gfo.commands.auth_cmd.gfo.auth.save_token") as mock_save:
            auth_cmd.handle_login(args, fmt="table")

        mock_save.assert_called_once_with("github.com", "my-token", account="default")
        captured = capsys.readouterr()
        assert "Token saved for github.com" in captured.out
        assert "account: default" in captured.out
        assert "Warning" in captured.err

    def test_host_specified_token_from_getpass(self, capsys):
        """--host 指定、--token なし → getpass 呼び出し + save_token。"""
        args = make_args(host="gitlab.com", token=None, account="default")

        with (
            patch("gfo.commands.auth_cmd.gfo.auth.save_token") as mock_save,
            patch("gfo.commands.auth_cmd.getpass.getpass", return_value="secret") as mock_gp,
        ):
            auth_cmd.handle_login(args, fmt="table")

        mock_gp.assert_called_once_with("Token: ")
        mock_save.assert_called_once_with("gitlab.com", "secret", account="default")
        captured = capsys.readouterr()
        assert "Token saved for gitlab.com" in captured.out
        assert captured.err == ""

    def test_no_host_uses_detect_service(self, capsys):
        """--host なし → detect_service().host を使用。"""
        args = make_args(host=None, token="tok", account="default")

        with (
            patch(
                "gfo.commands.auth_cmd.gfo.detect.detect_service",
                return_value=_make_detect_result("github.com"),
            ),
            patch("gfo.commands.auth_cmd.gfo.auth.save_token") as mock_save,
        ):
            auth_cmd.handle_login(args, fmt="table")

        mock_save.assert_called_once_with("github.com", "tok", account="default")

    def test_no_host_detect_service_raises(self):
        """--host なし + detect_service が DetectionError → ConfigError に変換して raise。"""
        args = make_args(host=None, token="tok", account="default")

        with patch(
            "gfo.commands.auth_cmd.gfo.detect.detect_service",
            side_effect=DetectionError("no remote"),
        ):
            with pytest.raises(ConfigError, match="--host"):
                auth_cmd.handle_login(args, fmt="table")

    def test_login_with_custom_account(self, capsys):
        """--account 指定でアカウント名がモック呼び出しに渡る。"""
        args = make_args(host="github.com", token="tok", account="work")

        with patch("gfo.commands.auth_cmd.gfo.auth.save_token") as mock_save:
            auth_cmd.handle_login(args, fmt="table")

        mock_save.assert_called_once_with("github.com", "tok", account="work")
        captured = capsys.readouterr()
        assert "account: work" in captured.out


class TestHandleLogin_ErrorCases:
    """handle_login のエラー・境界ケースのテスト。"""

    def test_token_warning_message_content(self, capsys):
        """--token 指定時の警告メッセージが stderr に出力される。"""
        args = make_args(host="github.com", token="secret", account="default")

        with patch("gfo.commands.auth_cmd.gfo.auth.save_token"):
            auth_cmd.handle_login(args, fmt="table")

        captured = capsys.readouterr()
        # stderr に何らかの警告が出力されること
        assert captured.err.strip() != ""

    def test_no_token_option_no_warning(self, capsys):
        """--token なし（getpass 経由）では stderr への警告が出ない。"""
        args = make_args(host="github.com", token=None, account="default")

        with (
            patch("gfo.commands.auth_cmd.gfo.auth.save_token"),
            patch("gfo.commands.auth_cmd.getpass.getpass", return_value="tok"),
        ):
            auth_cmd.handle_login(args, fmt="table")

        captured = capsys.readouterr()
        assert captured.err == ""

    def test_empty_token_delegates_to_save_token(self):
        """handle_login はトークン検証を save_token に委譲する（空文字チェックは save_token 側）。"""
        args = make_args(host="github.com", token=None, account="default")

        with (
            patch("gfo.commands.auth_cmd.gfo.auth.save_token") as mock_save,
            patch("gfo.commands.auth_cmd.getpass.getpass", return_value=""),
        ):
            auth_cmd.handle_login(args, fmt="table")

        mock_save.assert_called_once_with("github.com", "", account="default")

    def test_save_token_propagates_exception(self):
        """save_token が例外を送出した場合、そのまま再 raise される。"""
        args = make_args(host="invalid-host", token="tok", account="default")

        with patch(
            "gfo.commands.auth_cmd.gfo.auth.save_token", side_effect=OSError("permission denied")
        ):
            with pytest.raises(OSError, match="permission denied"):
                auth_cmd.handle_login(args, fmt="table")

    def test_no_host_getpass_called(self):
        """--host なし・--token なし → getpass が呼ばれる。"""
        args = make_args(host=None, token=None, account="default")

        with (
            patch(
                "gfo.commands.auth_cmd.gfo.detect.detect_service",
                return_value=_make_detect_result("github.com"),
            ),
            patch("gfo.commands.auth_cmd.gfo.auth.save_token"),
            patch("gfo.commands.auth_cmd.getpass.getpass", return_value="tok") as mock_gp,
        ):
            auth_cmd.handle_login(args, fmt="table")

        mock_gp.assert_called_once_with("Token: ")


class TestHandleSwitch:
    """handle_switch のテスト。"""

    def test_switch_with_host(self, capsys):
        """--host 指定あり → switch_account 呼び出し。"""
        args = make_args(host="github.com", account="work")

        with patch("gfo.commands.auth_cmd.gfo.auth.switch_account") as mock_switch:
            auth_cmd.handle_switch(args, fmt="table")

        mock_switch.assert_called_once_with("github.com", "work")
        captured = capsys.readouterr()
        assert "work" in captured.out
        assert "github.com" in captured.out

    def test_switch_without_host_uses_detect(self, capsys):
        """--host なし → detect_service().host を使用。"""
        args = make_args(host=None, account="ci")

        with (
            patch(
                "gfo.commands.auth_cmd.gfo.detect.detect_service",
                return_value=_make_detect_result("github.com"),
            ),
            patch("gfo.commands.auth_cmd.gfo.auth.switch_account") as mock_switch,
        ):
            auth_cmd.handle_switch(args, fmt="table")

        mock_switch.assert_called_once_with("github.com", "ci")

    def test_switch_detect_failure(self):
        """--host なし + detect 失敗 → ConfigError。"""
        args = make_args(host=None, account="work")

        with patch(
            "gfo.commands.auth_cmd.gfo.detect.detect_service",
            side_effect=DetectionError("no remote"),
        ):
            with pytest.raises(ConfigError, match="--host"):
                auth_cmd.handle_switch(args, fmt="table")


class TestHandleStatus:
    """handle_status のテスト。"""

    def test_tokens_configured_shows_table(self, capsys):
        """トークンあり → テーブル表示。"""
        entries = [
            {
                "host": "github.com",
                "status": "configured",
                "source": "credentials.toml",
                "account": "default",
                "active": "*",
            },
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
            {
                "host": "github.com",
                "status": "configured",
                "source": "credentials.toml",
                "account": "default",
                "active": "*",
            },
            {
                "host": "gitlab.com",
                "status": "configured",
                "source": "credentials.toml",
                "account": "default",
                "active": "*",
            },
            {
                "host": "gitea",
                "status": "configured",
                "source": "env:GITEA_TOKEN",
                "account": "",
                "active": "",
            },
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
            {
                "host": "github",
                "status": "configured",
                "source": "env:GITHUB_TOKEN",
                "account": "",
                "active": "",
            },
        ]
        args = make_args()

        with patch("gfo.commands.auth_cmd.gfo.auth.get_auth_status", return_value=entries):
            auth_cmd.handle_status(args, fmt="table")

        captured = capsys.readouterr()
        assert "env:GITHUB_TOKEN" in captured.out

    def test_table_has_header_columns(self, capsys):
        """テーブルヘッダーに HOST / ACCOUNT / STATUS / SOURCE の列が含まれる。"""
        entries = [
            {
                "host": "github.com",
                "status": "configured",
                "source": "credentials.toml",
                "account": "default",
                "active": "*",
            },
        ]
        args = make_args()

        with patch("gfo.commands.auth_cmd.gfo.auth.get_auth_status", return_value=entries):
            auth_cmd.handle_status(args, fmt="table")

        captured = capsys.readouterr()
        assert "HOST" in captured.out
        assert "ACCOUNT" in captured.out
        assert "STATUS" in captured.out
        assert "SOURCE" in captured.out

    def test_active_account_shown_with_asterisk(self, capsys):
        """アクティブアカウントは * 付きで表示される。"""
        entries = [
            {
                "host": "github.com",
                "status": "configured",
                "source": "credentials.toml",
                "account": "default",
                "active": "*",
            },
            {
                "host": "github.com",
                "status": "configured",
                "source": "credentials.toml",
                "account": "work",
                "active": "",
            },
        ]
        args = make_args()

        with patch("gfo.commands.auth_cmd.gfo.auth.get_auth_status", return_value=entries):
            auth_cmd.handle_status(args, fmt="table")

        captured = capsys.readouterr()
        assert "default *" in captured.out


class TestHandleLogout:
    """handle_logout のテスト。"""

    def test_logout_with_host(self, capsys):
        """--host 指定 → remove_token(host, account=None) + 成功メッセージ。"""
        args = make_args(host="github.com", account=None)

        with patch("gfo.commands.auth_cmd.gfo.auth.remove_token") as mock_remove:
            auth_cmd.handle_logout(args, fmt="table")

        mock_remove.assert_called_once_with("github.com", account=None)
        captured = capsys.readouterr()
        assert "Logged out from github.com" in captured.out

    def test_logout_without_host_uses_detect(self, capsys):
        """--host なし → detect_service().host を使用。"""
        args = make_args(host=None, account=None)

        with (
            patch(
                "gfo.commands.auth_cmd.gfo.detect.detect_service",
                return_value=_make_detect_result("github.com"),
            ),
            patch("gfo.commands.auth_cmd.gfo.auth.remove_token") as mock_remove,
        ):
            auth_cmd.handle_logout(args, fmt="table")

        mock_remove.assert_called_once_with("github.com", account=None)

    def test_logout_detect_failure(self):
        """--host なし + detect 失敗 → ConfigError。"""
        args = make_args(host=None, account=None)

        with patch(
            "gfo.commands.auth_cmd.gfo.detect.detect_service",
            side_effect=DetectionError("no remote"),
        ):
            with pytest.raises(ConfigError, match="--host"):
                auth_cmd.handle_logout(args, fmt="table")

    def test_logout_with_account(self, capsys):
        """--account 指定 → remove_token(host, account="work") + アカウント名含むメッセージ。"""
        args = make_args(host="github.com", account="work")

        with patch("gfo.commands.auth_cmd.gfo.auth.remove_token") as mock_remove:
            auth_cmd.handle_logout(args, fmt="table")

        mock_remove.assert_called_once_with("github.com", account="work")
        captured = capsys.readouterr()
        assert "work" in captured.out
        assert "github.com" in captured.out

    def test_logout_propagates_config_error(self):
        """ホスト未登録 → ConfigError 伝搬。"""
        args = make_args(host="unknown.host", account=None)

        with patch(
            "gfo.commands.auth_cmd.gfo.auth.remove_token",
            side_effect=ConfigError("Host 'unknown.host' not found"),
        ):
            with pytest.raises(ConfigError, match="unknown.host"):
                auth_cmd.handle_logout(args, fmt="table")

    def test_logout_unknown_account(self):
        """アカウント未登録 → ConfigError 伝搬。"""
        args = make_args(host="github.com", account="nonexistent")

        with patch(
            "gfo.commands.auth_cmd.gfo.auth.remove_token",
            side_effect=ConfigError("Account 'nonexistent' not found"),
        ):
            with pytest.raises(ConfigError, match="nonexistent"):
                auth_cmd.handle_logout(args, fmt="table")


# ── get_adapter / get_adapter_with_config ──


def test_get_adapter_returns_adapter():
    """get_adapter() は resolve_project_config と create_adapter を呼ぶ。"""
    mock_config = MagicMock()
    mock_adapter = MagicMock()
    with (
        patch("gfo.commands.resolve_project_config", return_value=mock_config),
        patch("gfo.commands.create_adapter", return_value=mock_adapter),
    ):
        result = get_adapter()
    assert result is mock_adapter


def test_get_adapter_with_config_returns_tuple():
    """get_adapter_with_config() はアダプターと設定のタプルを返す。"""
    mock_config = MagicMock()
    mock_adapter = MagicMock()
    with (
        patch("gfo.commands.resolve_project_config", return_value=mock_config),
        patch("gfo.commands.create_adapter", return_value=mock_adapter),
    ):
        adapter, config = get_adapter_with_config()
    assert adapter is mock_adapter
    assert config is mock_config
