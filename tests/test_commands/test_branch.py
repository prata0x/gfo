"""gfo.commands.branch のテスト。"""

from __future__ import annotations

import json

import pytest

from gfo.adapter.base import Branch
from gfo.commands import branch as branch_cmd
from gfo.exceptions import HttpError
from tests.test_commands.conftest import make_args, patch_adapter

SAMPLE_BRANCH = Branch(name="feature/test", sha="abc123", protected=False, url="")


class TestHandleView:
    def test_calls_get_branch(self):
        with patch_adapter("gfo.commands.branch") as adapter:
            adapter.get_branch.return_value = SAMPLE_BRANCH
            args = make_args(name="feature/test")
            branch_cmd.handle_view(args, fmt="table")
        adapter.get_branch.assert_called_once_with("feature/test")

    def test_outputs_result(self, capsys):
        with patch_adapter("gfo.commands.branch") as adapter:
            adapter.get_branch.return_value = SAMPLE_BRANCH
            args = make_args(name="feature/test")
            branch_cmd.handle_view(args, fmt="table")
        out = capsys.readouterr().out
        assert "feature/test" in out
        assert "abc123" in out

    def test_json_format(self, capsys):
        with patch_adapter("gfo.commands.branch") as adapter:
            adapter.get_branch.return_value = SAMPLE_BRANCH
            args = make_args(name="feature/test")
            branch_cmd.handle_view(args, fmt="json")
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert isinstance(parsed, list)
        assert parsed[0]["name"] == "feature/test"

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.branch") as adapter:
            adapter.get_branch.side_effect = HttpError(404, "Not found")
            args = make_args(name="nonexistent")
            with pytest.raises(HttpError):
                branch_cmd.handle_view(args, fmt="table")


class TestHandleList:
    def test_calls_list_branches(self, capsys):
        with patch_adapter("gfo.commands.branch") as adapter:
            adapter.list_branches.return_value = [SAMPLE_BRANCH]
            args = make_args(limit=30)
            branch_cmd.handle_list(args, fmt="table")
        adapter.list_branches.assert_called_once_with(limit=30)

    def test_outputs_results(self, capsys):
        with patch_adapter("gfo.commands.branch") as adapter:
            adapter.list_branches.return_value = [SAMPLE_BRANCH]
            args = make_args(limit=30)
            branch_cmd.handle_list(args, fmt="table")
        out = capsys.readouterr().out
        assert "feature/test" in out


class TestHandleCreate:
    def test_calls_create_branch(self):
        with patch_adapter("gfo.commands.branch") as adapter:
            adapter.create_branch.return_value = SAMPLE_BRANCH
            args = make_args(name="feature/new", ref="main")
            branch_cmd.handle_create(args, fmt="table")
        adapter.create_branch.assert_called_once_with(name="feature/new", ref="main")


class TestHandleDelete:
    def test_calls_delete_branch(self):
        with patch_adapter("gfo.commands.branch") as adapter:
            args = make_args(name="feature/old")
            branch_cmd.handle_delete(args, fmt="table")
        adapter.delete_branch.assert_called_once_with(name="feature/old")

    def test_delete_error_not_found(self):
        """404 エラーが伝搬する。"""
        with patch_adapter("gfo.commands.branch") as adapter:
            adapter.delete_branch.side_effect = HttpError(404, "Not found")
            args = make_args(name="nonexistent")
            with pytest.raises(HttpError) as exc_info:
                branch_cmd.handle_delete(args, fmt="table")
            assert exc_info.value.status_code == 404

    def test_delete_protected(self):
        """403 保護されたブランチの削除が伝搬する。"""
        with patch_adapter("gfo.commands.branch") as adapter:
            adapter.delete_branch.side_effect = HttpError(403, "Protected branch")
            args = make_args(name="main")
            with pytest.raises(HttpError) as exc_info:
                branch_cmd.handle_delete(args, fmt="table")
            assert exc_info.value.status_code == 403


class TestHandleListEdgeCases:
    """handle_list の追加エッジケーステスト。"""

    def test_list_empty(self, capsys):
        """空リスト: テーブル出力でエラーなし。"""
        with patch_adapter("gfo.commands.branch") as adapter:
            adapter.list_branches.return_value = []
            args = make_args(limit=30)
            branch_cmd.handle_list(args, fmt="table")
        adapter.list_branches.assert_called_once_with(limit=30)

    def test_list_json_format(self, capsys):
        """JSON 出力形式テスト。"""
        with patch_adapter("gfo.commands.branch") as adapter:
            adapter.list_branches.return_value = [SAMPLE_BRANCH]
            args = make_args(limit=30)
            branch_cmd.handle_list(args, fmt="json")
        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "feature/test"
        assert data[0]["sha"] == "abc123"
        assert data[0]["protected"] is False


class TestHandleCreateEdgeCases:
    """handle_create の追加エッジケーステスト。"""

    def test_create_json_format(self, capsys):
        """JSON 出力形式テスト。"""
        created_branch = Branch(name="feature/new", sha="def456", protected=False, url="")
        with patch_adapter("gfo.commands.branch") as adapter:
            adapter.create_branch.return_value = created_branch
            args = make_args(name="feature/new", ref="main")
            branch_cmd.handle_create(args, fmt="json")
        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, list)
        assert data[0]["name"] == "feature/new"

    def test_create_error_conflict(self):
        """409/422 コンフリクトエラーが伝搬する。"""
        with patch_adapter("gfo.commands.branch") as adapter:
            adapter.create_branch.side_effect = HttpError(422, "Branch already exists")
            args = make_args(name="feature/test", ref="main")
            with pytest.raises(HttpError) as exc_info:
                branch_cmd.handle_create(args, fmt="table")
            assert exc_info.value.status_code == 422


class TestHandleViewEdgeCases:
    """handle_view の追加エッジケーステスト。"""

    def test_view_with_jq(self, capsys):
        """jq フィルター付き出力。"""
        from unittest.mock import patch as _patch

        with patch_adapter("gfo.commands.branch") as adapter:
            adapter.get_branch.return_value = SAMPLE_BRANCH
            args = make_args(name="feature/test")
            with _patch("gfo.output.apply_jq_filter", return_value='"feature/test"') as mock_jq:
                branch_cmd.handle_view(args, fmt="json", jq=".[0].name")
                mock_jq.assert_called_once()
