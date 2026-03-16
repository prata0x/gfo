"""gfo.commands.notification のテスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gfo.adapter.base import Notification
from gfo.commands import notification as notif_cmd
from gfo.exceptions import GfoError
from tests.test_commands.conftest import make_args

SAMPLE_NOTIF = Notification(
    id="1",
    title="Fix bug",
    reason="mention",
    unread=True,
    repository="owner/repo",
    url="https://github.com/owner/repo/issues/1",
    updated_at="2024-01-01T00:00:00Z",
)


def _patch(adapter):
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        with patch("gfo.commands.notification.get_adapter", return_value=adapter):
            yield

    return _ctx()


class TestHandleList:
    def test_calls_list_notifications(self, capsys):
        adapter = MagicMock()
        adapter.list_notifications.return_value = [SAMPLE_NOTIF]
        args = make_args(unread_only=False, limit=30)
        with _patch(adapter):
            notif_cmd.handle_list(args, fmt="table")
        adapter.list_notifications.assert_called_once_with(unread_only=False, limit=30)
        out = capsys.readouterr().out
        assert "Fix bug" in out

    def test_unread_only(self, capsys):
        adapter = MagicMock()
        adapter.list_notifications.return_value = []
        args = make_args(unread_only=True, limit=30)
        with _patch(adapter):
            notif_cmd.handle_list(args, fmt="table")
        adapter.list_notifications.assert_called_once_with(unread_only=True, limit=30)


class TestHandleRead:
    def test_read_single(self):
        adapter = MagicMock()
        args = make_args(id="1", **{"all": False})
        with _patch(adapter):
            notif_cmd.handle_read(args, fmt="table")
        adapter.mark_notification_read.assert_called_once_with("1")

    def test_read_all(self):
        adapter = MagicMock()
        args = make_args(id=None, **{"all": True})
        with _patch(adapter):
            notif_cmd.handle_read(args, fmt="table")
        adapter.mark_all_notifications_read.assert_called_once()

    def test_error_both_id_and_all(self):
        adapter = MagicMock()
        args = make_args(id="1", **{"all": True})
        with _patch(adapter), pytest.raises(GfoError, match="Cannot specify both"):
            notif_cmd.handle_read(args, fmt="table")

    def test_error_neither_id_nor_all(self):
        adapter = MagicMock()
        args = make_args(id=None, **{"all": False})
        with _patch(adapter), pytest.raises(GfoError, match="Specify a notification"):
            notif_cmd.handle_read(args, fmt="table")
