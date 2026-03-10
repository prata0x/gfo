"""gfo.commands.webhook のテスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from gfo.adapter.base import Webhook
from gfo.commands import webhook as webhook_cmd
from tests.test_commands.conftest import make_args

SAMPLE_WEBHOOK = Webhook(id=1, url="https://example.com/hook", events=("push",), active=True)


def _patch(adapter):
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        with patch("gfo.commands.webhook.get_adapter", return_value=adapter):
            yield

    return _ctx()


class TestHandleList:
    def test_calls_list_webhooks(self, capsys):
        adapter = MagicMock()
        adapter.list_webhooks.return_value = [SAMPLE_WEBHOOK]
        args = make_args(limit=30)
        with _patch(adapter):
            webhook_cmd.handle_list(args, fmt="table")
        adapter.list_webhooks.assert_called_once_with(limit=30)


class TestHandleCreate:
    def test_calls_create_webhook(self):
        adapter = MagicMock()
        adapter.create_webhook.return_value = SAMPLE_WEBHOOK
        args = make_args(
            url="https://example.com/hook", event=["push", "pull_request"], secret=None
        )
        with _patch(adapter):
            webhook_cmd.handle_create(args, fmt="table")
        adapter.create_webhook.assert_called_once_with(
            url="https://example.com/hook",
            events=["push", "pull_request"],
            secret=None,
        )


class TestHandleDelete:
    def test_calls_delete_webhook(self):
        adapter = MagicMock()
        args = make_args(id=1)
        with _patch(adapter):
            webhook_cmd.handle_delete(args, fmt="table")
        adapter.delete_webhook.assert_called_once_with(hook_id=1)
