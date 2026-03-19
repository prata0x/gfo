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


class TestHandleEdit:
    def test_calls_update_webhook(self, capsys):
        with patch_adapter("gfo.commands.webhook") as adapter:
            adapter.update_webhook.return_value = SAMPLE_WEBHOOK
            args = make_args(
                id=1,
                url="https://new.example.com/hook",
                event=None,
                secret=None,
                active=None,
                inactive=False,
            )
            webhook_cmd.handle_edit(args, fmt="table")
        adapter.update_webhook.assert_called_once_with(
            1,
            url="https://new.example.com/hook",
            events=None,
            secret=None,
            active=None,
        )

    def test_with_events(self):
        with patch_adapter("gfo.commands.webhook") as adapter:
            adapter.update_webhook.return_value = SAMPLE_WEBHOOK
            args = make_args(
                id=1,
                url=None,
                event=["push", "issues"],
                secret=None,
                active=None,
                inactive=False,
            )
            webhook_cmd.handle_edit(args, fmt="table")
        adapter.update_webhook.assert_called_once_with(
            1,
            url=None,
            events=["push", "issues"],
            secret=None,
            active=None,
        )

    def test_activate(self):
        with patch_adapter("gfo.commands.webhook") as adapter:
            adapter.update_webhook.return_value = SAMPLE_WEBHOOK
            args = make_args(id=1, url=None, event=None, secret=None, active=True, inactive=False)
            webhook_cmd.handle_edit(args, fmt="table")
        adapter.update_webhook.assert_called_once_with(
            1,
            url=None,
            events=None,
            secret=None,
            active=True,
        )

    def test_deactivate(self):
        with patch_adapter("gfo.commands.webhook") as adapter:
            adapter.update_webhook.return_value = SAMPLE_WEBHOOK
            args = make_args(id=1, url=None, event=None, secret=None, active=None, inactive=True)
            webhook_cmd.handle_edit(args, fmt="table")
        adapter.update_webhook.assert_called_once_with(
            1,
            url=None,
            events=None,
            secret=None,
            active=False,
        )

    def test_json_format(self, capsys):
        with patch_adapter("gfo.commands.webhook") as adapter:
            adapter.update_webhook.return_value = SAMPLE_WEBHOOK
            args = make_args(id=1, url=None, event=None, secret=None, active=None, inactive=False)
            webhook_cmd.handle_edit(args, fmt="json")
        out = capsys.readouterr().out
        import json

        data = json.loads(out)
        assert data[0]["url"] == "https://example.com/hook"

    def test_error_propagation(self):
        import pytest

        from gfo.exceptions import HttpError

        with patch_adapter("gfo.commands.webhook") as adapter:
            adapter.update_webhook.side_effect = HttpError(404, "Not found")
            args = make_args(id=999, url=None, event=None, secret=None, active=None, inactive=False)
            with pytest.raises(HttpError):
                webhook_cmd.handle_edit(args, fmt="table")
