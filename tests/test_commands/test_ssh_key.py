"""gfo.commands.ssh_key のテスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from gfo.adapter.base import SshKey
from gfo.commands import ssh_key as ssh_key_cmd
from tests.test_commands.conftest import make_args

SAMPLE_KEY = SshKey(id=1, title="my-key", key="ssh-rsa AAAA...", created_at="2024-01-01T00:00:00Z")


def _patch(adapter):
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        with patch("gfo.commands.ssh_key.get_adapter", return_value=adapter):
            yield

    return _ctx()


class TestHandleList:
    def test_calls_list_ssh_keys(self, capsys):
        adapter = MagicMock()
        adapter.list_ssh_keys.return_value = [SAMPLE_KEY]
        args = make_args(limit=30)
        with _patch(adapter):
            ssh_key_cmd.handle_list(args, fmt="table")
        adapter.list_ssh_keys.assert_called_once_with(limit=30)
        out = capsys.readouterr().out
        assert "my-key" in out


class TestHandleCreate:
    def test_creates_ssh_key(self):
        adapter = MagicMock()
        adapter.create_ssh_key.return_value = SAMPLE_KEY
        args = make_args(title="my-key", key="ssh-rsa AAAA...")
        with _patch(adapter):
            ssh_key_cmd.handle_create(args, fmt="table")
        adapter.create_ssh_key.assert_called_once_with(title="my-key", key="ssh-rsa AAAA...")


class TestHandleDelete:
    def test_calls_delete_ssh_key(self):
        adapter = MagicMock()
        args = make_args(id=1)
        with _patch(adapter):
            ssh_key_cmd.handle_delete(args, fmt="table")
        adapter.delete_ssh_key.assert_called_once_with(key_id=1)

    def test_calls_delete_ssh_key_string_id(self):
        adapter = MagicMock()
        args = make_args(id="abc-123")
        with _patch(adapter):
            ssh_key_cmd.handle_delete(args, fmt="table")
        adapter.delete_ssh_key.assert_called_once_with(key_id="abc-123")
