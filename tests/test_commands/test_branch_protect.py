"""gfo.commands.branch_protect のテスト。"""

from __future__ import annotations

import json

import pytest

from gfo.adapter.base import BranchProtection
from gfo.commands import branch_protect as bp_cmd
from gfo.exceptions import HttpError
from tests.test_commands.conftest import make_args, patch_adapter

SAMPLE_BP = BranchProtection(
    branch="main",
    require_reviews=2,
    require_status_checks=("ci/test",),
    enforce_admins=True,
    allow_force_push=False,
    allow_deletions=False,
)


class TestHandleList:
    def test_calls_list(self, capsys):
        with patch_adapter("gfo.commands.branch_protect") as adapter:
            adapter.list_branch_protections.return_value = [SAMPLE_BP]
            args = make_args(limit=30)
            bp_cmd.handle_list(args, fmt="table")
        adapter.list_branch_protections.assert_called_once_with(limit=30)
        out = capsys.readouterr().out
        assert "main" in out

    def test_json_format(self, capsys):
        with patch_adapter("gfo.commands.branch_protect") as adapter:
            adapter.list_branch_protections.return_value = [SAMPLE_BP]
            args = make_args(limit=30)
            bp_cmd.handle_list(args, fmt="json")
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert isinstance(parsed, list)
        assert parsed[0]["branch"] == "main"

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.branch_protect") as adapter:
            adapter.list_branch_protections.side_effect = HttpError(500, "Server error")
            args = make_args(limit=30)
            with pytest.raises(HttpError):
                bp_cmd.handle_list(args, fmt="table")


class TestHandleView:
    def test_calls_get(self, capsys):
        with patch_adapter("gfo.commands.branch_protect") as adapter:
            adapter.get_branch_protection.return_value = SAMPLE_BP
            args = make_args(branch="main")
            bp_cmd.handle_view(args, fmt="table")
        adapter.get_branch_protection.assert_called_once_with("main")

    def test_json_format(self, capsys):
        with patch_adapter("gfo.commands.branch_protect") as adapter:
            adapter.get_branch_protection.return_value = SAMPLE_BP
            args = make_args(branch="main")
            bp_cmd.handle_view(args, fmt="json")
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed[0]["branch"] == "main"

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.branch_protect") as adapter:
            adapter.get_branch_protection.side_effect = HttpError(404, "Not found")
            args = make_args(branch="main")
            with pytest.raises(HttpError):
                bp_cmd.handle_view(args, fmt="table")


class TestHandleSet:
    def test_calls_set(self, capsys):
        with patch_adapter("gfo.commands.branch_protect") as adapter:
            adapter.set_branch_protection.return_value = SAMPLE_BP
            args = make_args(
                branch="main",
                require_reviews=2,
                require_status_checks=None,
                enforce_admins=True,
                allow_force_push=None,
                allow_deletions=None,
            )
            bp_cmd.handle_set(args, fmt="table")
        adapter.set_branch_protection.assert_called_once_with(
            "main",
            require_reviews=2,
            require_status_checks=None,
            enforce_admins=True,
            allow_force_push=None,
            allow_deletions=None,
        )

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.branch_protect") as adapter:
            adapter.set_branch_protection.side_effect = HttpError(403, "Forbidden")
            args = make_args(
                branch="main",
                require_reviews=2,
                require_status_checks=None,
                enforce_admins=True,
                allow_force_push=None,
                allow_deletions=None,
            )
            with pytest.raises(HttpError):
                bp_cmd.handle_set(args, fmt="table")


class TestHandleRemove:
    def test_calls_remove(self, capsys):
        with patch_adapter("gfo.commands.branch_protect") as adapter:
            args = make_args(branch="main")
            bp_cmd.handle_remove(args, fmt="table")
        adapter.remove_branch_protection.assert_called_once_with("main")
        out = capsys.readouterr().out
        assert "Removed" in out
        assert "main" in out

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.branch_protect") as adapter:
            adapter.remove_branch_protection.side_effect = HttpError(404, "Not found")
            args = make_args(branch="main")
            with pytest.raises(HttpError):
                bp_cmd.handle_remove(args, fmt="table")
