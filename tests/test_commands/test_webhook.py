"""gfo.commands.webhook のテスト。"""

from __future__ import annotations

from gfo.adapter.base import Webhook
from gfo.commands import webhook as webhook_cmd
from tests.test_commands.conftest import make_args, patch_adapter

SAMPLE_WEBHOOK = Webhook(id=1, url="https://example.com/hook", events=("push",), active=True)


class TestHandleList:
    def test_calls_list_webhooks(self, capsys):
        with patch_adapter("gfo.commands.webhook") as adapter:
            adapter.list_webhooks.return_value = [SAMPLE_WEBHOOK]
            args = make_args(limit=30)
            webhook_cmd.handle_list(args, fmt="table")
        adapter.list_webhooks.assert_called_once_with(limit=30)


class TestHandleCreate:
    def test_calls_create_webhook(self):
        with patch_adapter("gfo.commands.webhook") as adapter:
            adapter.create_webhook.return_value = SAMPLE_WEBHOOK
            args = make_args(
                url="https://example.com/hook", event=["push", "pull_request"], secret=None
            )
            webhook_cmd.handle_create(args, fmt="table")
        adapter.create_webhook.assert_called_once_with(
            url="https://example.com/hook",
            events=["push", "pull_request"],
            secret=None,
        )


class TestHandleDelete:
    def test_calls_delete_webhook(self):
        with patch_adapter("gfo.commands.webhook") as adapter:
            args = make_args(id=1)
            webhook_cmd.handle_delete(args, fmt="table")
        adapter.delete_webhook.assert_called_once_with(hook_id=1)


class TestHandleTest:
    def test_calls_test_webhook(self):
        with patch_adapter("gfo.commands.webhook") as adapter:
            args = make_args(id=1)
            webhook_cmd.handle_test(args, fmt="table")
        adapter.test_webhook.assert_called_once_with(hook_id=1)

    def test_different_id(self):
        with patch_adapter("gfo.commands.webhook") as adapter:
            args = make_args(id=42)
            webhook_cmd.handle_test(args, fmt="table")
        adapter.test_webhook.assert_called_once_with(hook_id=42)
