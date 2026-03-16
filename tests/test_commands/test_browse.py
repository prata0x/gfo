"""gfo.commands.browse のテスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from gfo.commands import browse as browse_cmd
from tests.test_commands.conftest import make_args


def _patch(adapter):
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        with patch("gfo.commands.browse.get_adapter", return_value=adapter):
            yield

    return _ctx()


class TestHandleBrowse:
    def test_opens_repo_url(self):
        adapter = MagicMock()
        adapter.get_web_url.return_value = "https://github.com/owner/repo"
        args = make_args(pr=None, issue=None, settings=False, **{"print": False})
        with _patch(adapter), patch("webbrowser.open") as mock_open:
            browse_cmd.handle_browse(args, fmt="table")
        adapter.get_web_url.assert_called_once_with("repo", None)
        mock_open.assert_called_once_with("https://github.com/owner/repo")

    def test_opens_pr_url(self):
        adapter = MagicMock()
        adapter.get_web_url.return_value = "https://github.com/owner/repo/pull/42"
        args = make_args(pr=42, issue=None, settings=False, **{"print": False})
        with _patch(adapter), patch("webbrowser.open") as mock_open:
            browse_cmd.handle_browse(args, fmt="table")
        adapter.get_web_url.assert_called_once_with("pr", 42)
        mock_open.assert_called_once_with("https://github.com/owner/repo/pull/42")

    def test_opens_issue_url(self):
        adapter = MagicMock()
        adapter.get_web_url.return_value = "https://github.com/owner/repo/issues/7"
        args = make_args(pr=None, issue=7, settings=False, **{"print": False})
        with _patch(adapter), patch("webbrowser.open") as mock_open:
            browse_cmd.handle_browse(args, fmt="table")
        adapter.get_web_url.assert_called_once_with("issue", 7)
        mock_open.assert_called_once_with("https://github.com/owner/repo/issues/7")

    def test_opens_settings_url(self):
        adapter = MagicMock()
        adapter.get_web_url.return_value = "https://github.com/owner/repo/settings"
        args = make_args(pr=None, issue=None, settings=True, **{"print": False})
        with _patch(adapter), patch("webbrowser.open") as mock_open:
            browse_cmd.handle_browse(args, fmt="table")
        adapter.get_web_url.assert_called_once_with("settings", None)
        mock_open.assert_called_once_with("https://github.com/owner/repo/settings")

    def test_print_flag(self, capsys):
        adapter = MagicMock()
        adapter.get_web_url.return_value = "https://github.com/owner/repo"
        args = make_args(pr=None, issue=None, settings=False, **{"print": True})
        with _patch(adapter), patch("webbrowser.open") as mock_open:
            browse_cmd.handle_browse(args, fmt="table")
        mock_open.assert_not_called()
        assert capsys.readouterr().out.strip() == "https://github.com/owner/repo"

    def test_pr_print(self, capsys):
        adapter = MagicMock()
        adapter.get_web_url.return_value = "https://github.com/owner/repo/pull/42"
        args = make_args(pr=42, issue=None, settings=False, **{"print": True})
        with _patch(adapter):
            browse_cmd.handle_browse(args, fmt="table")
        assert capsys.readouterr().out.strip() == "https://github.com/owner/repo/pull/42"
