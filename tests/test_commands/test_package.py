"""gfo.commands.package のテスト。"""

from __future__ import annotations

import json

import pytest

from gfo.adapter.base import Package
from gfo.commands import package as package_cmd
from gfo.exceptions import HttpError
from tests.test_commands.conftest import make_args, patch_adapter

SAMPLE_PACKAGE = Package(
    name="test-pkg",
    type="npm",
    version="1.0.0",
    owner="test-owner",
    url="https://example.com/packages/test-pkg",
    created_at="2024-01-01T00:00:00Z",
)


class TestHandleList:
    def test_calls_list_packages(self, capsys):
        with patch_adapter("gfo.commands.package") as adapter:
            adapter.list_packages.return_value = [SAMPLE_PACKAGE]
            args = make_args(type=None, limit=30)
            package_cmd.handle_list(args, fmt="table")
        adapter.list_packages.assert_called_once_with(package_type=None, limit=30)

    def test_json_output(self, capsys):
        with patch_adapter("gfo.commands.package") as adapter:
            adapter.list_packages.return_value = [SAMPLE_PACKAGE]
            args = make_args(type=None, limit=30)
            package_cmd.handle_list(args, fmt="json")
        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, list)
        assert data[0]["name"] == "test-pkg"

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.package") as adapter:
            adapter.list_packages.side_effect = HttpError(500, "Server error")
            args = make_args(type=None, limit=30)
            with pytest.raises(HttpError):
                package_cmd.handle_list(args, fmt="table")


class TestHandleView:
    def test_calls_get_package(self, capsys):
        with patch_adapter("gfo.commands.package") as adapter:
            adapter.get_package.return_value = SAMPLE_PACKAGE
            args = make_args(package_type="npm", name="test-pkg", version=None)
            package_cmd.handle_view(args, fmt="table")
        adapter.get_package.assert_called_once_with("npm", "test-pkg", version=None)

    def test_json_output(self, capsys):
        with patch_adapter("gfo.commands.package") as adapter:
            adapter.get_package.return_value = SAMPLE_PACKAGE
            args = make_args(package_type="npm", name="test-pkg", version=None)
            package_cmd.handle_view(args, fmt="json")
        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, list)
        assert data[0]["name"] == "test-pkg"
        assert data[0]["type"] == "npm"

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.package") as adapter:
            adapter.get_package.side_effect = HttpError(404, "Not found")
            args = make_args(package_type="npm", name="test-pkg", version=None)
            with pytest.raises(HttpError):
                package_cmd.handle_view(args, fmt="table")


class TestHandleDelete:
    def test_calls_delete_package_with_yes(self, capsys):
        with patch_adapter("gfo.commands.package") as adapter:
            args = make_args(package_type="npm", name="test-pkg", version="1.0.0", yes=True)
            package_cmd.handle_delete(args, fmt="table")
        adapter.delete_package.assert_called_once_with("npm", "test-pkg", "1.0.0")

    def test_delete_confirm_yes(self, capsys):
        """builtins.input を "y" にパッチ → delete_package() が呼び出される。"""
        from unittest.mock import patch

        with patch_adapter("gfo.commands.package") as adapter:
            args = make_args(package_type="npm", name="test-pkg", version="1.0.0", yes=False)
            with patch("builtins.input", return_value="y"):
                package_cmd.handle_delete(args, fmt="table")
        adapter.delete_package.assert_called_once_with("npm", "test-pkg", "1.0.0")
        out = capsys.readouterr().out
        assert "Deleted" in out

    def test_delete_confirm_no(self, capsys):
        """builtins.input を "n" にパッチ → "Aborted." 出力、delete_package 未呼び出し。"""
        from unittest.mock import patch

        with patch_adapter("gfo.commands.package") as adapter:
            args = make_args(package_type="npm", name="test-pkg", version="1.0.0", yes=False)
            with patch("builtins.input", return_value="n"):
                package_cmd.handle_delete(args, fmt="table")
        adapter.delete_package.assert_not_called()
        out = capsys.readouterr().out
        assert "Aborted" in out

    def test_delete_confirm_empty(self, capsys):
        """builtins.input を "" にパッチ → Aborted (y/yes 以外は拒否)。"""
        from unittest.mock import patch

        with patch_adapter("gfo.commands.package") as adapter:
            args = make_args(package_type="npm", name="test-pkg", version="1.0.0", yes=False)
            with patch("builtins.input", return_value=""):
                package_cmd.handle_delete(args, fmt="table")
        adapter.delete_package.assert_not_called()
        out = capsys.readouterr().out
        assert "Aborted" in out

    def test_delete_success_message(self, capsys):
        """削除成功メッセージの出力内容検証。"""
        with patch_adapter("gfo.commands.package"):
            args = make_args(package_type="npm", name="test-pkg", version="1.0.0", yes=True)
            package_cmd.handle_delete(args, fmt="table")
        out = capsys.readouterr().out
        assert "Deleted" in out
        assert "npm/test-pkg@1.0.0" in out

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.package") as adapter:
            adapter.delete_package.side_effect = HttpError(403, "Forbidden")
            args = make_args(package_type="npm", name="test-pkg", version="1.0.0", yes=True)
            with pytest.raises(HttpError):
                package_cmd.handle_delete(args, fmt="table")


class TestHandleListEdgeCases:
    """handle_list の追加エッジケーステスト。"""

    def test_list_empty(self, capsys):
        """空リスト: テーブル出力でエラーなし。"""
        with patch_adapter("gfo.commands.package") as adapter:
            adapter.list_packages.return_value = []
            args = make_args(type=None, limit=30)
            package_cmd.handle_list(args, fmt="table")
        adapter.list_packages.assert_called_once_with(package_type=None, limit=30)

    def test_list_with_type_filter(self):
        """package_type 引数が伝搬される。"""
        with patch_adapter("gfo.commands.package") as adapter:
            adapter.list_packages.return_value = [SAMPLE_PACKAGE]
            args = make_args(type="npm", limit=10)
            package_cmd.handle_list(args, fmt="table")
        adapter.list_packages.assert_called_once_with(package_type="npm", limit=10)


class TestHandleViewEdgeCases:
    """handle_view の追加エッジケーステスト。"""

    def test_view_with_version(self):
        """version 引数が伝搬される。"""
        with patch_adapter("gfo.commands.package") as adapter:
            adapter.get_package.return_value = SAMPLE_PACKAGE
            args = make_args(package_type="npm", name="test-pkg", version="2.0.0")
            package_cmd.handle_view(args, fmt="table")
        adapter.get_package.assert_called_once_with("npm", "test-pkg", version="2.0.0")
