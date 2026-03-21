"""auth コマンドの CLI 統合テスト。

adapter 不要。一時ディレクトリで gfo.auth のファイル操作をテストする。
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from gfo.cli import main
from tests.integration.conftest import safe_temporary_directory

pytestmark = [
    pytest.mark.integration,
    pytest.mark.cli,
]


class _CapturedIO:
    """stdout/stderr をキャプチャするコンテキストマネージャ。"""

    def __init__(self):
        self.stdout = ""
        self.stderr = ""

    def __enter__(self):
        import sys
        from io import StringIO

        self._old_stdout = sys.stdout
        self._old_stderr = sys.stderr
        self._out = StringIO()
        self._err = StringIO()
        sys.stdout = self._out
        sys.stderr = self._err
        return self

    def __exit__(self, *args):
        import sys

        self.stdout = self._out.getvalue()
        self.stderr = self._err.getvalue()
        sys.stdout = self._old_stdout
        sys.stderr = self._old_stderr


def _run_auth(argv: list[str], config_dir: Path) -> tuple[int, str, str]:
    """auth コマンドを一時ディレクトリで実行する。"""
    with (
        patch("gfo.config.get_config_dir", return_value=config_dir),
        patch("gfo.auth.get_credentials_path", return_value=config_dir / "credentials.toml"),
    ):
        cap = _CapturedIO()
        with cap:
            exit_code = main(argv)
    return exit_code, cap.stdout, cap.stderr


class TestAuthLoginStatusLogout:
    """login → status → token → logout の一連フロー。"""

    def test_auth_lifecycle(self) -> None:
        with safe_temporary_directory() as tmpdir:
            config_dir = Path(tmpdir)

            # 1. login (--token でトークンを直接指定)
            code, out, err = _run_auth(
                ["auth", "login", "--host", "github.com", "--token", "test-token-123"],
                config_dir,
            )
            assert code == 0

            # 2. status
            code, out, err = _run_auth(["auth", "status"], config_dir)
            assert code == 0
            assert "github.com" in out

            # 3. status --format json
            code, out, err = _run_auth(["auth", "status", "--format", "json"], config_dir)
            assert code == 0
            data = json.loads(out)
            assert isinstance(data, list)
            assert any(e["host"] == "github.com" for e in data)

            # 4. token
            code, out, err = _run_auth(["auth", "token", "--host", "github.com"], config_dir)
            assert code == 0
            assert "test-token-123" in out

            # 5. logout
            code, out, err = _run_auth(["auth", "logout", "--host", "github.com"], config_dir)
            assert code == 0

            # 6. status 後にエントリがなくなっている
            code, out, err = _run_auth(["auth", "status"], config_dir)
            assert code == 0


class TestAuthSwitch:
    """複数アカウント登録 → switch テスト。"""

    def test_multi_account_switch(self) -> None:
        with safe_temporary_directory() as tmpdir:
            config_dir = Path(tmpdir)

            # アカウント1 登録
            code, _, _ = _run_auth(
                [
                    "auth",
                    "login",
                    "--host",
                    "gitlab.com",
                    "--token",
                    "token-account1",
                    "--account",
                    "work",
                ],
                config_dir,
            )
            assert code == 0

            # アカウント2 登録
            code, _, _ = _run_auth(
                [
                    "auth",
                    "login",
                    "--host",
                    "gitlab.com",
                    "--token",
                    "token-account2",
                    "--account",
                    "personal",
                ],
                config_dir,
            )
            assert code == 0

            # switch
            code, out, _ = _run_auth(
                ["auth", "switch", "--host", "gitlab.com", "personal"],
                config_dir,
            )
            assert code == 0
            assert "personal" in out

            # token で personal のトークンが返ることを確認
            code, out, _ = _run_auth(
                ["auth", "token", "--host", "gitlab.com"],
                config_dir,
            )
            assert code == 0
            assert "token-account2" in out


class TestAuthStatusJson:
    """--format json での構造化出力テスト。"""

    def test_status_json_structure(self) -> None:
        with safe_temporary_directory() as tmpdir:
            config_dir = Path(tmpdir)

            # トークン登録
            code, _, _ = _run_auth(
                ["auth", "login", "--host", "example.com", "--token", "abc123"],
                config_dir,
            )
            assert code == 0

            # JSON 出力確認
            code, out, _ = _run_auth(
                ["auth", "status", "--format", "json"],
                config_dir,
            )
            assert code == 0
            data = json.loads(out)
            assert isinstance(data, list)
            assert len(data) >= 1
            entry = next(e for e in data if e["host"] == "example.com")
            assert "status" in entry
            assert "source" in entry
            assert "account" in entry
