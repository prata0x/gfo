"""gfo.commands.file のテスト。"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from gfo.commands import file as file_cmd
from gfo.exceptions import HttpError, NetworkError, NotFoundError
from tests.test_commands.conftest import make_args, patch_adapter


class TestHandleGet:
    def test_calls_get_file_content(self, capsys):
        with patch_adapter("gfo.commands.file") as adapter:
            adapter.get_file_content.return_value = ("file content", "abc123sha")
            args = make_args(path="README.md", ref=None)
            file_cmd.handle_get(args, fmt="table")
        adapter.get_file_content.assert_called_once_with("README.md", ref=None)
        out = capsys.readouterr().out
        assert "file content" in out

    def test_json_format(self, capsys):
        with patch_adapter("gfo.commands.file") as adapter:
            adapter.get_file_content.return_value = ("content", "sha123")
            args = make_args(path="file.txt", ref="main")
            file_cmd.handle_get(args, fmt="json")
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["content"] == "content"
        assert data["sha"] == "sha123"

    def test_get_plain_format(self, capsys):
        """table 形式でコンテンツのみが出力される。"""
        with patch_adapter("gfo.commands.file") as adapter:
            adapter.get_file_content.return_value = ("hello world", "sha456")
            args = make_args(path="test.txt", ref=None)
            file_cmd.handle_get(args, fmt="table")
        out = capsys.readouterr().out
        assert out.strip() == "hello world"

    def test_get_jq_filter(self, capsys):
        """--jq '.sha' が適用される。"""
        with patch_adapter("gfo.commands.file") as adapter:
            adapter.get_file_content.return_value = ("content", "sha789")
            args = make_args(path="file.txt", ref=None)
            file_cmd.handle_get(args, fmt="json", jq=".sha")
        out = capsys.readouterr().out
        assert "sha789" in out

    def test_get_with_ref(self):
        """args.ref がアダプターに渡される。"""
        with patch_adapter("gfo.commands.file") as adapter:
            adapter.get_file_content.return_value = ("content", "sha123")
            args = make_args(path="file.txt", ref="develop")
            file_cmd.handle_get(args, fmt="table")
        adapter.get_file_content.assert_called_once_with("file.txt", ref="develop")


class TestHandlePut:
    def test_creates_new_file(self):
        with patch_adapter("gfo.commands.file") as adapter:
            # get_file_content が失敗する場合（新規ファイル）→ sha=None
            adapter.get_file_content.side_effect = NotFoundError()
            args = make_args(path="new.txt", message="Add file", branch=None)
            with patch("gfo.commands.file.sys.stdin") as mock_stdin:
                mock_stdin.read.return_value = "hello"
                file_cmd.handle_put(args, fmt="table")
        adapter.create_or_update_file.assert_called_once_with(
            "new.txt", content="hello", message="Add file", sha=None, branch=None
        )

    def test_updates_existing_file_with_sha(self):
        """既存ファイル更新時に get_file_content で取得した SHA が渡される。"""
        with patch_adapter("gfo.commands.file") as adapter:
            adapter.get_file_content.return_value = ("old content", "abc123")
            args = make_args(path="existing.txt", message="Update file", branch=None)
            with patch("gfo.commands.file.sys.stdin") as mock_stdin:
                mock_stdin.read.return_value = "new content"
                file_cmd.handle_put(args, fmt="table")
        adapter.create_or_update_file.assert_called_once_with(
            "existing.txt", content="new content", message="Update file", sha="abc123", branch=None
        )

    def test_non_not_found_error_propagates(self):
        """NotFoundError 以外の例外（ネットワークエラー等）はそのまま伝播する。"""
        with patch_adapter("gfo.commands.file") as adapter:
            adapter.get_file_content.side_effect = NetworkError("connection failed")
            args = make_args(path="secret.txt", message="Update", branch=None)
            with patch("gfo.commands.file.sys.stdin") as mock_stdin:
                mock_stdin.read.return_value = "data"
                with pytest.raises(NetworkError):
                    file_cmd.handle_put(args, fmt="table")

    def test_put_stdin_empty(self):
        """空コンテンツでのファイル作成。"""
        with patch_adapter("gfo.commands.file") as adapter:
            adapter.get_file_content.side_effect = NotFoundError()
            args = make_args(path="empty.txt", message="Add empty file", branch=None)
            with patch("gfo.commands.file.sys.stdin") as mock_stdin:
                mock_stdin.read.return_value = ""
                file_cmd.handle_put(args, fmt="table")
        adapter.create_or_update_file.assert_called_once_with(
            "empty.txt", content="", message="Add empty file", sha=None, branch=None
        )

    def test_put_with_branch(self):
        """args.branch が get_file_content と create_or_update_file 両方に渡される。"""
        with patch_adapter("gfo.commands.file") as adapter:
            adapter.get_file_content.return_value = ("old", "sha_old")
            args = make_args(path="file.txt", message="Update", branch="feature")
            with patch("gfo.commands.file.sys.stdin") as mock_stdin:
                mock_stdin.read.return_value = "new"
                file_cmd.handle_put(args, fmt="table")
        adapter.get_file_content.assert_called_once_with("file.txt", ref="feature")
        adapter.create_or_update_file.assert_called_once_with(
            "file.txt", content="new", message="Update", sha="sha_old", branch="feature"
        )


class TestHandleDelete:
    def test_calls_delete_file(self):
        with patch_adapter("gfo.commands.file") as adapter:
            adapter.get_file_content.return_value = ("content", "deadbeef")
            args = make_args(path="old.txt", message="Remove file", branch=None)
            file_cmd.handle_delete(args, fmt="table")
        adapter.delete_file.assert_called_once_with(
            "old.txt", sha="deadbeef", message="Remove file", branch=None
        )

    def test_delete_not_found_propagates(self):
        """handle_delete で NotFoundError が伝搬する。"""
        with patch_adapter("gfo.commands.file") as adapter:
            adapter.get_file_content.side_effect = NotFoundError()
            args = make_args(path="missing.txt", message="Delete", branch=None)
            with pytest.raises(NotFoundError):
                file_cmd.handle_delete(args, fmt="table")

    def test_delete_error_propagation(self):
        """HttpError(403) がそのまま伝搬する。"""
        with patch_adapter("gfo.commands.file") as adapter:
            adapter.get_file_content.return_value = ("content", "sha123")
            adapter.delete_file.side_effect = HttpError(403, "Forbidden")
            args = make_args(path="protected.txt", message="Delete", branch=None)
            with pytest.raises(HttpError) as exc_info:
                file_cmd.handle_delete(args, fmt="table")
            assert exc_info.value.status_code == 403
