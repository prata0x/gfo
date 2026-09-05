"""gfo.commands.user のテスト。"""

from __future__ import annotations

import json

import pytest

from gfo.commands import user as user_cmd
from gfo.exceptions import HttpError
from tests.test_commands.conftest import make_args, patch_adapter


class TestHandleWhoami:
    def test_calls_get_current_user(self, capsys):
        with patch_adapter("gfo.commands.user") as adapter:
            adapter.get_current_user.return_value = {
                "login": "testuser",
                "email": "test@example.com",
            }
            args = make_args()
            user_cmd.handle_whoami(args, fmt="table")
        adapter.get_current_user.assert_called_once()

    def test_outputs_json(self, capsys):
        with patch_adapter("gfo.commands.user") as adapter:
            adapter.get_current_user.return_value = {"login": "testuser"}
            args = make_args()
            user_cmd.handle_whoami(args, fmt="json")
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["login"] == "testuser"

    def test_whoami_table_format(self, capsys):
        """fmt='table' で 'key: value' 形式が出力される。"""
        with patch_adapter("gfo.commands.user") as adapter:
            adapter.get_current_user.return_value = {
                "login": "testuser",
                "email": "test@example.com",
            }
            args = make_args()
            user_cmd.handle_whoami(args, fmt="table")
        out = capsys.readouterr().out
        assert "login: testuser" in out
        assert "email: test@example.com" in out

    def test_whoami_plain_format(self, capsys):
        """fmt='plain' ではラベルなしで値だけが出力される。"""
        with patch_adapter("gfo.commands.user") as adapter:
            adapter.get_current_user.return_value = {
                "login": "testuser",
                "email": "test@example.com",
            }
            args = make_args()
            user_cmd.handle_whoami(args, fmt="plain")
        assert capsys.readouterr().out == "testuser\ntest@example.com\n"

    def test_whoami_plain_format_sanitizes_control_characters(self, capsys):
        """fmt='plain' では値中の改行・CR・タブがエスケープされる。"""
        with patch_adapter("gfo.commands.user") as adapter:
            adapter.get_current_user.return_value = {
                "bio": "line1\nline2\rline3\tline4",
            }
            args = make_args()
            user_cmd.handle_whoami(args, fmt="plain")
        assert capsys.readouterr().out == "line1\\nline2\\rline3\\tline4\n"

    def test_whoami_jq_filter(self, capsys):
        """--jq '.login' が適用される。"""
        with patch_adapter("gfo.commands.user") as adapter:
            adapter.get_current_user.return_value = {"login": "testuser"}
            args = make_args()
            user_cmd.handle_whoami(args, fmt="json", jq=".login")
        out = capsys.readouterr().out
        assert "testuser" in out

    def test_whoami_empty_dict(self, capsys):
        """空の dict でも例外なく処理される。"""
        with patch_adapter("gfo.commands.user") as adapter:
            adapter.get_current_user.return_value = {}
            args = make_args()
            user_cmd.handle_whoami(args, fmt="table")
        # 例外が発生しないことを確認
        out = capsys.readouterr().out
        assert out == ""

    def test_whoami_value_with_special_chars(self, capsys):
        """value に ':' や改行を含む場合も正しく出力される。"""
        with patch_adapter("gfo.commands.user") as adapter:
            adapter.get_current_user.return_value = {
                "bio": "dev:ops\nline2",
            }
            args = make_args()
            user_cmd.handle_whoami(args, fmt="table")
        out = capsys.readouterr().out
        assert "bio: dev:ops\\nline2" in out

    def test_whoami_table_format_sanitizes_control_characters(self, capsys):
        """fmt='table' では値中の改行・CR・タブがエスケープされる。"""
        with patch_adapter("gfo.commands.user") as adapter:
            adapter.get_current_user.return_value = {
                "bio": "line1\nline2\rline3\tline4",
            }
            args = make_args()
            user_cmd.handle_whoami(args, fmt="table")
        assert capsys.readouterr().out == "bio: line1\\nline2\\rline3 line4\n"

    def test_whoami_error_propagation(self):
        """HttpError(401) がそのまま伝搬する。"""
        with patch_adapter("gfo.commands.user") as adapter:
            adapter.get_current_user.side_effect = HttpError(401, "Unauthorized")
            args = make_args()
            with pytest.raises(HttpError) as exc_info:
                user_cmd.handle_whoami(args, fmt="table")
            assert exc_info.value.status_code == 401

    def test_works_without_resolvable_repo(self, capsys):
        """user はアカウント単位の操作のため owner/repo 未解決でも動く（require_repo=False）。"""
        from unittest.mock import MagicMock, patch

        adapter = MagicMock()
        adapter.get_current_user.return_value = {"login": "testuser"}
        with patch("gfo.commands.user.get_adapter", return_value=adapter) as mock_get_adapter:
            args = make_args()
            user_cmd.handle_whoami(args, fmt="table")
        mock_get_adapter.assert_called_once_with(require_repo=False)
