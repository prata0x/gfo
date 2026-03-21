"""gfo.commands.browse のテスト。"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from gfo.commands import browse as browse_cmd
from gfo.exceptions import HttpError
from tests.test_commands.conftest import make_args, patch_adapter


class TestHandleBrowse:
    def test_opens_repo_url(self):
        with patch_adapter("gfo.commands.browse") as adapter:
            adapter.get_web_url.return_value = "https://github.com/owner/repo"
            args = make_args(pr=None, issue=None, settings=False, **{"print": False})
            with patch("webbrowser.open") as mock_open:
                browse_cmd.handle_browse(args, fmt="table")
        adapter.get_web_url.assert_called_once_with("repo", None)
        mock_open.assert_called_once_with("https://github.com/owner/repo")

    def test_opens_pr_url(self):
        with patch_adapter("gfo.commands.browse") as adapter:
            adapter.get_web_url.return_value = "https://github.com/owner/repo/pull/42"
            args = make_args(pr=42, issue=None, settings=False, **{"print": False})
            with patch("webbrowser.open") as mock_open:
                browse_cmd.handle_browse(args, fmt="table")
        adapter.get_web_url.assert_called_once_with("pr", 42)
        mock_open.assert_called_once_with("https://github.com/owner/repo/pull/42")

    def test_opens_issue_url(self):
        with patch_adapter("gfo.commands.browse") as adapter:
            adapter.get_web_url.return_value = "https://github.com/owner/repo/issues/7"
            args = make_args(pr=None, issue=7, settings=False, **{"print": False})
            with patch("webbrowser.open") as mock_open:
                browse_cmd.handle_browse(args, fmt="table")
        adapter.get_web_url.assert_called_once_with("issue", 7)
        mock_open.assert_called_once_with("https://github.com/owner/repo/issues/7")

    def test_opens_settings_url(self):
        with patch_adapter("gfo.commands.browse") as adapter:
            adapter.get_web_url.return_value = "https://github.com/owner/repo/settings"
            args = make_args(pr=None, issue=None, settings=True, **{"print": False})
            with patch("webbrowser.open") as mock_open:
                browse_cmd.handle_browse(args, fmt="table")
        adapter.get_web_url.assert_called_once_with("settings", None)
        mock_open.assert_called_once_with("https://github.com/owner/repo/settings")

    def test_print_flag(self, capsys):
        with patch_adapter("gfo.commands.browse") as adapter:
            adapter.get_web_url.return_value = "https://github.com/owner/repo"
            args = make_args(pr=None, issue=None, settings=False, **{"print": True})
            with patch("webbrowser.open") as mock_open:
                browse_cmd.handle_browse(args, fmt="table")
        mock_open.assert_not_called()
        assert capsys.readouterr().out.strip() == "https://github.com/owner/repo"

    def test_pr_print(self, capsys):
        """--print 時にブラウザが起動しないことを確認。"""
        with patch_adapter("gfo.commands.browse") as adapter:
            adapter.get_web_url.return_value = "https://github.com/owner/repo/pull/42"
            args = make_args(pr=42, issue=None, settings=False, **{"print": True})
            with patch("webbrowser.open") as mock_open:
                browse_cmd.handle_browse(args, fmt="table")
        mock_open.assert_not_called()
        assert capsys.readouterr().out.strip() == "https://github.com/owner/repo/pull/42"

    def test_default_resource_is_repo(self):
        """pr/issue/settings いずれも未指定の場合 resource="repo" になる。"""
        with patch_adapter("gfo.commands.browse") as adapter:
            adapter.get_web_url.return_value = "https://github.com/owner/repo"
            args = make_args(pr=None, issue=None, settings=False, **{"print": False})
            with patch("webbrowser.open"):
                browse_cmd.handle_browse(args, fmt="table")
        adapter.get_web_url.assert_called_once_with("repo", None)

    def test_error_propagation(self):
        """アダプターのエラーがそのまま伝搬する。"""
        with patch_adapter("gfo.commands.browse") as adapter:
            adapter.get_web_url.side_effect = HttpError(500, "Server error")
            args = make_args(pr=None, issue=None, settings=False, **{"print": False})
            with pytest.raises(HttpError):
                with patch("webbrowser.open"):
                    browse_cmd.handle_browse(args, fmt="table")

    def test_print_outputs_url_to_stdout(self, capsys):
        """--print で URL 文字列が stdout に出力される内容を検証。"""
        with patch_adapter("gfo.commands.browse") as adapter:
            adapter.get_web_url.return_value = "https://github.com/owner/repo/pull/99"
            args = make_args(pr=99, issue=None, settings=False, **{"print": True})
            with patch("webbrowser.open") as mock_open:
                browse_cmd.handle_browse(args, fmt="table")
        mock_open.assert_not_called()
        out = capsys.readouterr().out.strip()
        assert out == "https://github.com/owner/repo/pull/99"
        assert "github.com" in out
        assert "/pull/99" in out

    def test_webbrowser_failure(self):
        """webbrowser.open が例外を投げた場合に伝搬する。"""
        with patch_adapter("gfo.commands.browse") as adapter:
            adapter.get_web_url.return_value = "https://github.com/owner/repo"
            args = make_args(pr=None, issue=None, settings=False, **{"print": False})
            with patch("webbrowser.open", side_effect=RuntimeError("Browser error")):
                with pytest.raises(RuntimeError, match="Browser error"):
                    browse_cmd.handle_browse(args, fmt="table")

    def test_issue_number_zero(self):
        """issue=0 でも resource="issue" として扱われる。"""
        with patch_adapter("gfo.commands.browse") as adapter:
            adapter.get_web_url.return_value = "https://github.com/owner/repo/issues/0"
            args = make_args(pr=None, issue=0, settings=False, **{"print": True})
            with patch("webbrowser.open") as mock_open:
                browse_cmd.handle_browse(args, fmt="table")
        # issue=0 は None ではないので issue として扱われる
        adapter.get_web_url.assert_called_once_with("issue", 0)
        mock_open.assert_not_called()
