"""gfo.commands.notification のテスト。"""

from __future__ import annotations

import json

import pytest

from gfo.adapter.base import Notification
from gfo.commands import notification as notif_cmd
from gfo.exceptions import GfoError, HttpError
from tests.test_commands.conftest import make_args, patch_adapter

SAMPLE_NOTIF = Notification(
    id="1",
    title="Fix bug",
    reason="mention",
    unread=True,
    repository="owner/repo",
    url="https://github.com/owner/repo/issues/1",
    updated_at="2024-01-01T00:00:00Z",
)


class TestHandleList:
    def test_calls_list_notifications(self, capsys):
        with patch_adapter("gfo.commands.notification") as adapter:
            adapter.list_notifications.return_value = [SAMPLE_NOTIF]
            args = make_args(unread_only=False, limit=30)
            notif_cmd.handle_list(args, fmt="table")
        adapter.list_notifications.assert_called_once_with(unread_only=False, limit=30)
        out = capsys.readouterr().out
        assert "Fix bug" in out

    def test_unread_only(self, capsys):
        with patch_adapter("gfo.commands.notification") as adapter:
            adapter.list_notifications.return_value = []
            args = make_args(unread_only=True, limit=30)
            notif_cmd.handle_list(args, fmt="table")
        adapter.list_notifications.assert_called_once_with(unread_only=True, limit=30)

    def test_json_format(self, capsys):
        with patch_adapter("gfo.commands.notification") as adapter:
            adapter.list_notifications.return_value = [SAMPLE_NOTIF]
            args = make_args(unread_only=False, limit=30)
            notif_cmd.handle_list(args, fmt="json")
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert isinstance(parsed, list)
        assert parsed[0]["title"] == "Fix bug"

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.notification") as adapter:
            adapter.list_notifications.side_effect = HttpError(500, "Server error")
            args = make_args(unread_only=False, limit=30)
            with pytest.raises(HttpError):
                notif_cmd.handle_list(args, fmt="table")


class TestHandleRead:
    def test_read_single(self):
        with patch_adapter("gfo.commands.notification") as adapter:
            args = make_args(id="1", mark_all=False)
            notif_cmd.handle_read(args, fmt="table")
        adapter.mark_notification_read.assert_called_once_with("1")

    def test_read_all(self):
        with patch_adapter("gfo.commands.notification") as adapter:
            args = make_args(id=None, mark_all=True)
            notif_cmd.handle_read(args, fmt="table")
        adapter.mark_all_notifications_read.assert_called_once()

    def test_error_both_id_and_all(self):
        with patch_adapter("gfo.commands.notification"):
            args = make_args(id="1", mark_all=True)
            with pytest.raises(GfoError, match="Cannot specify both"):
                notif_cmd.handle_read(args, fmt="table")

    def test_error_neither_id_nor_all(self):
        with patch_adapter("gfo.commands.notification"):
            args = make_args(id=None, mark_all=False)
            with pytest.raises(GfoError, match="Specify a notification"):
                notif_cmd.handle_read(args, fmt="table")

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.notification") as adapter:
            adapter.mark_notification_read.side_effect = HttpError(404, "Not found")
            args = make_args(id="999", mark_all=False)
            with pytest.raises(HttpError):
                notif_cmd.handle_read(args, fmt="table")
