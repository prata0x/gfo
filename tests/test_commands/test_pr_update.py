"""gfo.commands.pr handle_edit のテスト。"""

from __future__ import annotations

import pytest

from gfo.commands import pr as pr_cmd
from tests.test_commands.conftest import make_args, patch_adapter


class TestHandleEdit:
    def test_calls_update_with_all_fields(self, sample_pr):
        with patch_adapter("gfo.commands.pr") as adapter:
            adapter.update_pull_request.return_value = sample_pr
            args = make_args(number=1, title="New title", body="New body", base="develop")
            pr_cmd.handle_edit(args, fmt="table")
        adapter.update_pull_request.assert_called_once_with(
            1,
            title="New title",
            body="New body",
            base="develop",
            add_labels=None,
            remove_labels=None,
            add_assignees=None,
            remove_assignees=None,
            milestone=None,
        )

    def test_calls_update_with_none_fields(self, sample_pr):
        with patch_adapter("gfo.commands.pr") as adapter:
            adapter.update_pull_request.return_value = sample_pr
            args = make_args(number=2, title=None, body=None, base=None)
            pr_cmd.handle_edit(args, fmt="table")
        adapter.update_pull_request.assert_called_once_with(
            2,
            title=None,
            body=None,
            base=None,
            add_labels=None,
            remove_labels=None,
            add_assignees=None,
            remove_assignees=None,
            milestone=None,
        )

    def test_passes_add_labels(self, sample_pr):
        with patch_adapter("gfo.commands.pr") as adapter:
            adapter.update_pull_request.return_value = sample_pr
            args = make_args(
                number=1,
                title=None,
                body=None,
                base=None,
                add_label=["bug", "urgent"],
                remove_label=None,
                add_assignee=None,
                remove_assignee=None,
                milestone=None,
            )
            pr_cmd.handle_edit(args, fmt="table")
        call_kwargs = adapter.update_pull_request.call_args.kwargs
        assert call_kwargs["add_labels"] == ["bug", "urgent"]

    def test_passes_remove_labels(self, sample_pr):
        with patch_adapter("gfo.commands.pr") as adapter:
            adapter.update_pull_request.return_value = sample_pr
            args = make_args(
                number=1,
                title=None,
                body=None,
                base=None,
                add_label=None,
                remove_label=["wontfix"],
                add_assignee=None,
                remove_assignee=None,
                milestone=None,
            )
            pr_cmd.handle_edit(args, fmt="table")
        call_kwargs = adapter.update_pull_request.call_args.kwargs
        assert call_kwargs["remove_labels"] == ["wontfix"]

    def test_passes_add_assignees(self, sample_pr):
        with patch_adapter("gfo.commands.pr") as adapter:
            adapter.update_pull_request.return_value = sample_pr
            args = make_args(
                number=1,
                title=None,
                body=None,
                base=None,
                add_label=None,
                remove_label=None,
                add_assignee=["alice"],
                remove_assignee=None,
                milestone=None,
            )
            pr_cmd.handle_edit(args, fmt="table")
        call_kwargs = adapter.update_pull_request.call_args.kwargs
        assert call_kwargs["add_assignees"] == ["alice"]

    def test_passes_remove_assignees(self, sample_pr):
        with patch_adapter("gfo.commands.pr") as adapter:
            adapter.update_pull_request.return_value = sample_pr
            args = make_args(
                number=1,
                title=None,
                body=None,
                base=None,
                add_label=None,
                remove_label=None,
                add_assignee=None,
                remove_assignee=["bob"],
                milestone=None,
            )
            pr_cmd.handle_edit(args, fmt="table")
        call_kwargs = adapter.update_pull_request.call_args.kwargs
        assert call_kwargs["remove_assignees"] == ["bob"]

    def test_passes_milestone(self, sample_pr):
        with patch_adapter("gfo.commands.pr") as adapter:
            adapter.update_pull_request.return_value = sample_pr
            args = make_args(
                number=1,
                title=None,
                body=None,
                base=None,
                add_label=None,
                remove_label=None,
                add_assignee=None,
                remove_assignee=None,
                milestone="v1.0",
            )
            pr_cmd.handle_edit(args, fmt="table")
        call_kwargs = adapter.update_pull_request.call_args.kwargs
        assert call_kwargs["milestone"] == "v1.0"


class TestPrEditArgParsing:
    """pr edit の CLI 引数パースのテスト。"""

    @pytest.fixture
    def parser(self):
        from gfo.cli import create_parser

        p, _ = create_parser()
        return p

    def test_add_label(self, parser):
        ns = parser.parse_args(["pr", "edit", "1", "--add-label", "bug", "--add-label", "urgent"])
        assert ns.add_label == ["bug", "urgent"]

    def test_remove_label(self, parser):
        ns = parser.parse_args(["pr", "edit", "1", "--remove-label", "wontfix"])
        assert ns.remove_label == ["wontfix"]

    def test_add_assignee(self, parser):
        ns = parser.parse_args(["pr", "edit", "1", "--add-assignee", "alice"])
        assert ns.add_assignee == ["alice"]

    def test_remove_assignee(self, parser):
        ns = parser.parse_args(["pr", "edit", "1", "--remove-assignee", "bob"])
        assert ns.remove_assignee == ["bob"]

    def test_milestone(self, parser):
        ns = parser.parse_args(["pr", "edit", "1", "--milestone", "v1.0"])
        assert ns.milestone == "v1.0"

    def test_defaults_are_none(self, parser):
        ns = parser.parse_args(["pr", "edit", "1"])
        assert ns.add_label is None
        assert ns.remove_label is None
        assert ns.add_assignee is None
        assert ns.remove_assignee is None
        assert ns.milestone is None
