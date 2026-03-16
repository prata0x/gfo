"""gfo.commands.branch のテスト。"""

from __future__ import annotations

from gfo.adapter.base import Branch
from gfo.commands import branch as branch_cmd
from tests.test_commands.conftest import make_args, patch_adapter

SAMPLE_BRANCH = Branch(name="feature/test", sha="abc123", protected=False, url="")


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
