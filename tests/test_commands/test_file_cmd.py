"""gfo.commands.file のテスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gfo.commands import file as file_cmd
from gfo.exceptions import NetworkError, NotFoundError
from tests.test_commands.conftest import make_args


def _patch(adapter):
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        with patch("gfo.commands.file.get_adapter", return_value=adapter):
            yield

    return _ctx()


class TestHandleGet:
    def test_calls_get_file_content(self, capsys):
        adapter = MagicMock()
        adapter.get_file_content.return_value = ("file content", "abc123sha")
        args = make_args(path="README.md", ref=None)
        with _patch(adapter):
            file_cmd.handle_get(args, fmt="table")
        adapter.get_file_content.assert_called_once_with("README.md", ref=None)
        out = capsys.readouterr().out
        assert "file content" in out

    def test_json_format(self, capsys):
        adapter = MagicMock()
        adapter.get_file_content.return_value = ("content", "sha123")
        args = make_args(path="file.txt", ref="main")
        with _patch(adapter):
            file_cmd.handle_get(args, fmt="json")
        import json

        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["content"] == "content"
        assert data["sha"] == "sha123"


class TestHandlePut:
    def test_creates_new_file(self):
        adapter = MagicMock()
        # get_file_content が失敗する場合（新規ファイル）→ sha=None
        adapter.get_file_content.side_effect = NotFoundError()
        args = make_args(path="new.txt", message="Add file", branch=None)
        with _patch(adapter):
            with patch("gfo.commands.file.sys.stdin") as mock_stdin:
                mock_stdin.read.return_value = "hello"
                file_cmd.handle_put(args, fmt="table")
        adapter.create_or_update_file.assert_called_once_with(
            "new.txt", content="hello", message="Add file", sha=None, branch=None
        )

    def test_non_not_found_error_propagates(self):
        """NotFoundError 以外の例外（ネットワークエラー等）はそのまま伝播する。"""
        adapter = MagicMock()
        adapter.get_file_content.side_effect = NetworkError("connection failed")
        args = make_args(path="secret.txt", message="Update", branch=None)
        with _patch(adapter):
            with patch("gfo.commands.file.sys.stdin") as mock_stdin:
                mock_stdin.read.return_value = "data"
                with pytest.raises(NetworkError):
                    file_cmd.handle_put(args, fmt="table")


class TestHandleDelete:
    def test_calls_delete_file(self):
        adapter = MagicMock()
        adapter.get_file_content.return_value = ("content", "deadbeef")
        args = make_args(path="old.txt", message="Remove file", branch=None)
        with _patch(adapter):
            file_cmd.handle_delete(args, fmt="table")
        adapter.delete_file.assert_called_once_with(
            "old.txt", sha="deadbeef", message="Remove file", branch=None
        )
