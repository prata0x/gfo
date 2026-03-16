"""gfo.commands.secret のテスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gfo.adapter.base import Secret
from gfo.commands import secret as secret_cmd
from gfo.exceptions import GfoError
from tests.test_commands.conftest import make_args

SAMPLE_SECRET = Secret(name="MY_SECRET", created_at="2024-01-01", updated_at="2024-01-02")


def _patch(adapter):
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        with patch("gfo.commands.secret.get_adapter", return_value=adapter):
            yield

    return _ctx()


class TestHandleList:
    def test_calls_list_secrets(self, capsys):
        adapter = MagicMock()
        adapter.list_secrets.return_value = [SAMPLE_SECRET]
        args = make_args(limit=30)
        with _patch(adapter):
            secret_cmd.handle_list(args, fmt="table")
        adapter.list_secrets.assert_called_once_with(limit=30)
        out = capsys.readouterr().out
        assert "MY_SECRET" in out


class TestHandleSet:
    def test_set_with_value(self):
        adapter = MagicMock()
        adapter.set_secret.return_value = SAMPLE_SECRET
        args = make_args(name="MY_SECRET", value="secret", env_var=None, file=None)
        with _patch(adapter):
            secret_cmd.handle_set(args, fmt="table")
        adapter.set_secret.assert_called_once_with("MY_SECRET", "secret")

    def test_set_from_env_var(self, monkeypatch):
        monkeypatch.setenv("MY_ENV", "envvalue")
        adapter = MagicMock()
        adapter.set_secret.return_value = SAMPLE_SECRET
        args = make_args(name="MY_SECRET", value=None, env_var="MY_ENV", file=None)
        with _patch(adapter):
            secret_cmd.handle_set(args, fmt="table")
        adapter.set_secret.assert_called_once_with("MY_SECRET", "envvalue")

    def test_set_from_env_var_missing(self, monkeypatch):
        monkeypatch.delenv("NONEXISTENT_VAR", raising=False)
        adapter = MagicMock()
        args = make_args(name="MY_SECRET", value=None, env_var="NONEXISTENT_VAR", file=None)
        with _patch(adapter), pytest.raises(GfoError, match="not set"):
            secret_cmd.handle_set(args, fmt="table")

    def test_set_from_file(self, tmp_path):
        f = tmp_path / "secret.txt"
        f.write_text("filevalue")
        adapter = MagicMock()
        adapter.set_secret.return_value = SAMPLE_SECRET
        args = make_args(name="MY_SECRET", value=None, env_var=None, file=str(f))
        with _patch(adapter):
            secret_cmd.handle_set(args, fmt="table")
        adapter.set_secret.assert_called_once_with("MY_SECRET", "filevalue")


class TestHandleDelete:
    def test_calls_delete(self):
        adapter = MagicMock()
        args = make_args(name="MY_SECRET")
        with _patch(adapter):
            secret_cmd.handle_delete(args, fmt="table")
        adapter.delete_secret.assert_called_once_with("MY_SECRET")
