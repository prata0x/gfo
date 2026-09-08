"""gfo.commands.read_file_arg のテスト。"""

from __future__ import annotations

import io

import pytest

from gfo.commands import read_file_arg
from gfo.exceptions import ConfigError


class TestReadFileArg:
    def test_reads_file(self, tmp_path):
        """正常にファイルを読み込める。"""
        f = tmp_path / "input.txt"
        f.write_text("hello world")
        assert read_file_arg(str(f)) == "hello world"

    def test_file_not_found_raises_config_error(self):
        """存在しないファイルで ConfigError を送出する。"""
        with pytest.raises(ConfigError, match="File not found"):
            read_file_arg("nonexistent.txt")

    def test_permission_denied_raises_config_error(self, tmp_path):
        """読み取り権限のないファイルで ConfigError を送出する。"""
        f = tmp_path / "noaccess.txt"
        f.write_text("secret")
        f.chmod(0o000)
        try:
            with pytest.raises(ConfigError, match="Permission denied"):
                read_file_arg(str(f))
        finally:
            f.chmod(0o644)

    def test_stdin_read(self, monkeypatch):
        """'-' を渡すと stdin から読み込む。"""
        monkeypatch.setattr("sys.stdin", io.StringIO("stdin content"))
        assert read_file_arg("-") == "stdin content"
