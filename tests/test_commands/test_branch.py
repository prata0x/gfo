"""gfo.commands.branch のテスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from gfo.adapter.base import Branch
from gfo.commands import branch as branch_cmd
from tests.test_commands.conftest import make_args

SAMPLE_BRANCH = Branch(name="feature/test", sha="abc123", protected=False, url="")


def _patch(adapter):
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        with patch("gfo.commands.branch.get_adapter", return_value=adapter):
            yield

    return _ctx()


class TestHandleList:
    def test_calls_list_branches(self, capsys):
        adapter = MagicMock()
        adapter.list_branches.return_value = [SAMPLE_BRANCH]
        args = make_args(limit=30)
        with _patch(adapter):
            branch_cmd.handle_list(args, fmt="table")
        adapter.list_branches.assert_called_once_with(limit=30)

    def test_outputs_results(self, capsys):
        adapter = MagicMock()
        adapter.list_branches.return_value = [SAMPLE_BRANCH]
        args = make_args(limit=30)
        with _patch(adapter):
            branch_cmd.handle_list(args, fmt="table")
        out = capsys.readouterr().out
        assert "feature/test" in out


class TestHandleCreate:
    def test_calls_create_branch(self):
        adapter = MagicMock()
        adapter.create_branch.return_value = SAMPLE_BRANCH
        args = make_args(name="feature/new", ref="main")
        with _patch(adapter):
            branch_cmd.handle_create(args, fmt="table")
        adapter.create_branch.assert_called_once_with(name="feature/new", ref="main")


class TestHandleDelete:
    def test_calls_delete_branch(self):
        adapter = MagicMock()
        args = make_args(name="feature/old")
        with _patch(adapter):
            branch_cmd.handle_delete(args, fmt="table")
        adapter.delete_branch.assert_called_once_with(name="feature/old")
