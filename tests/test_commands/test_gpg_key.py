"""gfo.commands.gpg_key のテスト。"""

from __future__ import annotations

import json

import pytest

from gfo.adapter.base import GpgKey
from gfo.commands import gpg_key as gpg_key_cmd
from gfo.exceptions import HttpError
from tests.test_commands.conftest import make_args, patch_adapter

SAMPLE_GPG_KEY = GpgKey(
    id=1,
    primary_key_id="ABC123",
    public_key="-----BEGIN PGP PUBLIC KEY BLOCK-----...",
    emails=("user@example.com",),
    created_at="2024-01-01T00:00:00Z",
)


class TestHandleList:
    def test_calls_list_gpg_keys(self, capsys):
        with patch_adapter("gfo.commands.gpg_key") as adapter:
            adapter.list_gpg_keys.return_value = [SAMPLE_GPG_KEY]
            args = make_args(limit=30)
            gpg_key_cmd.handle_list(args, fmt="table")
        adapter.list_gpg_keys.assert_called_once_with(limit=30)
        out = capsys.readouterr().out
        assert "ABC123" in out

    def test_json_format(self, capsys):
        with patch_adapter("gfo.commands.gpg_key") as adapter:
            adapter.list_gpg_keys.return_value = [SAMPLE_GPG_KEY]
            args = make_args(limit=30)
            gpg_key_cmd.handle_list(args, fmt="json")
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert isinstance(parsed, list)
        assert parsed[0]["primary_key_id"] == "ABC123"

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.gpg_key") as adapter:
            adapter.list_gpg_keys.side_effect = HttpError(500, "Server error")
            args = make_args(limit=30)
            with pytest.raises(HttpError):
                gpg_key_cmd.handle_list(args, fmt="table")


class TestHandleCreate:
    def test_creates_gpg_key(self):
        with patch_adapter("gfo.commands.gpg_key") as adapter:
            adapter.create_gpg_key.return_value = SAMPLE_GPG_KEY
            args = make_args(key="-----BEGIN PGP PUBLIC KEY BLOCK-----...")
            gpg_key_cmd.handle_create(args, fmt="table")
        adapter.create_gpg_key.assert_called_once_with(
            armored_key="-----BEGIN PGP PUBLIC KEY BLOCK-----..."
        )

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.gpg_key") as adapter:
            adapter.create_gpg_key.side_effect = HttpError(422, "Unprocessable")
            args = make_args(key="-----BEGIN PGP PUBLIC KEY BLOCK-----...")
            with pytest.raises(HttpError):
                gpg_key_cmd.handle_create(args, fmt="table")


class TestHandleDelete:
    def test_calls_delete_gpg_key(self, capsys):
        with patch_adapter("gfo.commands.gpg_key") as adapter:
            args = make_args(id=1)
            gpg_key_cmd.handle_delete(args, fmt="table")
        adapter.delete_gpg_key.assert_called_once_with(key_id=1)
        out = capsys.readouterr().out
        assert "Deleted" in out
        assert "1" in out

    def test_calls_delete_gpg_key_string_id(self):
        with patch_adapter("gfo.commands.gpg_key") as adapter:
            args = make_args(id="abc-123")
            gpg_key_cmd.handle_delete(args, fmt="table")
        adapter.delete_gpg_key.assert_called_once_with(key_id="abc-123")

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.gpg_key") as adapter:
            adapter.delete_gpg_key.side_effect = HttpError(404, "Not found")
            args = make_args(id=1)
            with pytest.raises(HttpError):
                gpg_key_cmd.handle_delete(args, fmt="table")
