"""gfo.commands.secret のテスト。"""

from __future__ import annotations

import json

import pytest

from gfo.adapter.base import Secret
from gfo.commands import secret as secret_cmd
from gfo.exceptions import GfoError, HttpError
from tests.test_commands.conftest import make_args, patch_adapter

SAMPLE_SECRET = Secret(name="MY_SECRET", created_at="2024-01-01", updated_at="2024-01-02")


class TestHandleList:
    def test_calls_list_secrets(self, capsys):
        with patch_adapter("gfo.commands.secret") as adapter:
            adapter.list_secrets.return_value = [SAMPLE_SECRET]
            args = make_args(limit=30)
            secret_cmd.handle_list(args, fmt="table")
        adapter.list_secrets.assert_called_once_with(limit=30)
        out = capsys.readouterr().out
        assert "MY_SECRET" in out

    def test_json_format(self, capsys):
        with patch_adapter("gfo.commands.secret") as adapter:
            adapter.list_secrets.return_value = [SAMPLE_SECRET]
            args = make_args(limit=30)
            secret_cmd.handle_list(args, fmt="json")
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert isinstance(parsed, list)
        assert parsed[0]["name"] == "MY_SECRET"

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.secret") as adapter:
            adapter.list_secrets.side_effect = HttpError(500, "Server error")
            args = make_args(limit=30)
            with pytest.raises(HttpError):
                secret_cmd.handle_list(args, fmt="table")


class TestHandleSet:
    def test_set_with_value(self):
        with patch_adapter("gfo.commands.secret") as adapter:
            adapter.set_secret.return_value = SAMPLE_SECRET
            args = make_args(name="MY_SECRET", value="secret", env_var=None, file=None)
            secret_cmd.handle_set(args, fmt="table")
        adapter.set_secret.assert_called_once_with("MY_SECRET", "secret")

    def test_set_from_env_var(self, monkeypatch):
        monkeypatch.setenv("MY_ENV", "envvalue")
        with patch_adapter("gfo.commands.secret") as adapter:
            adapter.set_secret.return_value = SAMPLE_SECRET
            args = make_args(name="MY_SECRET", value=None, env_var="MY_ENV", file=None)
            secret_cmd.handle_set(args, fmt="table")
        adapter.set_secret.assert_called_once_with("MY_SECRET", "envvalue")

    def test_set_from_env_var_missing(self, monkeypatch):
        monkeypatch.delenv("NONEXISTENT_VAR", raising=False)
        with patch_adapter("gfo.commands.secret"):
            args = make_args(name="MY_SECRET", value=None, env_var="NONEXISTENT_VAR", file=None)
            with pytest.raises(GfoError, match="not set"):
                secret_cmd.handle_set(args, fmt="table")

    def test_set_from_file(self, tmp_path):
        f = tmp_path / "secret.txt"
        f.write_text("filevalue")
        with patch_adapter("gfo.commands.secret") as adapter:
            adapter.set_secret.return_value = SAMPLE_SECRET
            args = make_args(name="MY_SECRET", value=None, env_var=None, file=str(f))
            secret_cmd.handle_set(args, fmt="table")
        adapter.set_secret.assert_called_once_with("MY_SECRET", "filevalue")

    def test_set_from_file_strips_trailing_newline(self, tmp_path):
        """ファイル内容の末尾改行が strip される。"""
        f = tmp_path / "secret.txt"
        f.write_text("filevalue\n")
        with patch_adapter("gfo.commands.secret") as adapter:
            adapter.set_secret.return_value = SAMPLE_SECRET
            args = make_args(name="MY_SECRET", value=None, env_var=None, file=str(f))
            secret_cmd.handle_set(args, fmt="table")
        adapter.set_secret.assert_called_once_with("MY_SECRET", "filevalue")

    def test_set_from_file_not_found(self):
        """存在しないファイルを指定した場合 GfoError。"""
        with patch_adapter("gfo.commands.secret"):
            args = make_args(
                name="MY_SECRET", value=None, env_var=None, file="/nonexistent/path/secret.txt"
            )
            with pytest.raises(GfoError, match="File not found"):
                secret_cmd.handle_set(args, fmt="table")

    def test_set_no_source_raises_gfo_error(self):
        """value/env_var/file いずれも None の場合 GfoError。"""
        with patch_adapter("gfo.commands.secret"):
            args = make_args(name="MY_SECRET", value=None, env_var=None, file=None)
            with pytest.raises(GfoError, match="Specify --value, --env-var, or --file"):
                secret_cmd.handle_set(args, fmt="table")

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.secret") as adapter:
            adapter.set_secret.side_effect = HttpError(403, "Forbidden")
            args = make_args(name="MY_SECRET", value="secret", env_var=None, file=None)
            with pytest.raises(HttpError):
                secret_cmd.handle_set(args, fmt="table")


class TestHandleDelete:
    def test_calls_delete(self):
        with patch_adapter("gfo.commands.secret") as adapter:
            args = make_args(name="MY_SECRET")
            secret_cmd.handle_delete(args, fmt="table")
        adapter.delete_secret.assert_called_once_with("MY_SECRET")

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.secret") as adapter:
            adapter.delete_secret.side_effect = HttpError(404, "Not found")
            args = make_args(name="MY_SECRET")
            with pytest.raises(HttpError):
                secret_cmd.handle_delete(args, fmt="table")
