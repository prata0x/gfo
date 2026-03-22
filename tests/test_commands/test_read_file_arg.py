"""gfo.commands.read_file_arg のテスト。"""

from __future__ import annotations

import io

import pytest

from gfo.commands import read_file_arg
from gfo.exceptions import GfoError


class TestReadFileArg:
    def test_reads_file(self, tmp_path):
        """正常にファイルを読み込める。"""
        f = tmp_path / "input.txt"
        f.write_text("hello world")
        assert read_file_arg(str(f)) == "hello world"

    def test_file_not_found_raises_gfo_error(self):
        """存在しないファイルで GfoError を送出する。"""
        with pytest.raises(GfoError, match="File not found"):
            read_file_arg("nonexistent.txt")

    def test_stdin_read(self, monkeypatch):
        """'-' を渡すと stdin から読み込む。"""
        monkeypatch.setattr("sys.stdin", io.StringIO("stdin content"))
        assert read_file_arg("-") == "stdin content"
