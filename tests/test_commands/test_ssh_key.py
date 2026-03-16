"""gfo.commands.ssh_key のテスト。"""

from __future__ import annotations

import json

import pytest

from gfo.adapter.base import SshKey
from gfo.commands import ssh_key as ssh_key_cmd
from gfo.exceptions import HttpError
from tests.test_commands.conftest import make_args, patch_adapter

SAMPLE_KEY = SshKey(id=1, title="my-key", key="ssh-rsa AAAA...", created_at="2024-01-01T00:00:00Z")


class TestHandleList:
    def test_calls_list_ssh_keys(self, capsys):
        with patch_adapter("gfo.commands.ssh_key") as adapter:
            adapter.list_ssh_keys.return_value = [SAMPLE_KEY]
            args = make_args(limit=30)
            ssh_key_cmd.handle_list(args, fmt="table")
        adapter.list_ssh_keys.assert_called_once_with(limit=30)
        out = capsys.readouterr().out
        assert "my-key" in out

    def test_json_format(self, capsys):
        with patch_adapter("gfo.commands.ssh_key") as adapter:
            adapter.list_ssh_keys.return_value = [SAMPLE_KEY]
            args = make_args(limit=30)
            ssh_key_cmd.handle_list(args, fmt="json")
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert isinstance(parsed, list)
        assert parsed[0]["title"] == "my-key"

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.ssh_key") as adapter:
            adapter.list_ssh_keys.side_effect = HttpError(500, "Server error")
            args = make_args(limit=30)
            with pytest.raises(HttpError):
                ssh_key_cmd.handle_list(args, fmt="table")


class TestHandleCreate:
    def test_creates_ssh_key(self):
        with patch_adapter("gfo.commands.ssh_key") as adapter:
            adapter.create_ssh_key.return_value = SAMPLE_KEY
            args = make_args(title="my-key", key="ssh-rsa AAAA...")
            ssh_key_cmd.handle_create(args, fmt="table")
        adapter.create_ssh_key.assert_called_once_with(title="my-key", key="ssh-rsa AAAA...")

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.ssh_key") as adapter:
            adapter.create_ssh_key.side_effect = HttpError(422, "Unprocessable")
            args = make_args(title="my-key", key="ssh-rsa AAAA...")
            with pytest.raises(HttpError):
                ssh_key_cmd.handle_create(args, fmt="table")


class TestHandleDelete:
    def test_calls_delete_ssh_key(self, capsys):
        with patch_adapter("gfo.commands.ssh_key") as adapter:
            args = make_args(id=1)
            ssh_key_cmd.handle_delete(args, fmt="table")
        adapter.delete_ssh_key.assert_called_once_with(key_id=1)
        out = capsys.readouterr().out
        assert "Deleted" in out
        assert "1" in out

    def test_calls_delete_ssh_key_string_id(self):
        with patch_adapter("gfo.commands.ssh_key") as adapter:
            args = make_args(id="abc-123")
            ssh_key_cmd.handle_delete(args, fmt="table")
        adapter.delete_ssh_key.assert_called_once_with(key_id="abc-123")

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.ssh_key") as adapter:
            adapter.delete_ssh_key.side_effect = HttpError(404, "Not found")
            args = make_args(id=1)
            with pytest.raises(HttpError):
                ssh_key_cmd.handle_delete(args, fmt="table")
