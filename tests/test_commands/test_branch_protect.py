"""gfo.commands.branch_protect のテスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from gfo.adapter.base import BranchProtection
from gfo.commands import branch_protect as bp_cmd
from tests.test_commands.conftest import make_args

SAMPLE_BP = BranchProtection(
    branch="main",
    require_reviews=2,
    require_status_checks=("ci/test",),
    enforce_admins=True,
    allow_force_push=False,
    allow_deletions=False,
)


def _patch(adapter):
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        with patch("gfo.commands.branch_protect.get_adapter", return_value=adapter):
            yield

    return _ctx()


class TestHandleList:
    def test_calls_list(self, capsys):
        adapter = MagicMock()
        adapter.list_branch_protections.return_value = [SAMPLE_BP]
        args = make_args(limit=30)
        with _patch(adapter):
            bp_cmd.handle_list(args, fmt="table")
        adapter.list_branch_protections.assert_called_once_with(limit=30)
        out = capsys.readouterr().out
        assert "main" in out


class TestHandleView:
    def test_calls_get(self, capsys):
        adapter = MagicMock()
        adapter.get_branch_protection.return_value = SAMPLE_BP
        args = make_args(branch="main")
        with _patch(adapter):
            bp_cmd.handle_view(args, fmt="table")
        adapter.get_branch_protection.assert_called_once_with("main")


class TestHandleSet:
    def test_calls_set(self, capsys):
        adapter = MagicMock()
        adapter.set_branch_protection.return_value = SAMPLE_BP
        args = make_args(
            branch="main",
            require_reviews=2,
            require_status_checks=None,
            enforce_admins=True,
            allow_force_push=None,
            allow_deletions=None,
        )
        with _patch(adapter):
            bp_cmd.handle_set(args, fmt="table")
        adapter.set_branch_protection.assert_called_once_with(
            "main",
            require_reviews=2,
            require_status_checks=None,
            enforce_admins=True,
            allow_force_push=None,
            allow_deletions=None,
        )


class TestHandleRemove:
    def test_calls_remove(self):
        adapter = MagicMock()
        args = make_args(branch="main")
        with _patch(adapter):
            bp_cmd.handle_remove(args, fmt="table")
        adapter.remove_branch_protection.assert_called_once_with("main")
