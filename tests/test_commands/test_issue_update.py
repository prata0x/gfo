"""gfo.commands.issue handle_edit のテスト。"""

from __future__ import annotations

import pytest

from gfo.adapter.base import Issue
from gfo.commands import issue as issue_cmd
from tests.test_commands.conftest import make_args, patch_adapter

SAMPLE_ISSUE = Issue(
    number=1,
    title="Test Issue",
    body="Body",
    state="open",
    author="author",
    assignees=[],
    labels=[],
    url="",
    created_at="2024-01-01T00:00:00Z",
)


class TestHandleEdit:
    def test_calls_update_issue(self):
        with patch_adapter("gfo.commands.issue") as adapter:
            adapter.update_issue.return_value = SAMPLE_ISSUE
            args = make_args(
                number=1, title="Updated", body="New body", assignee="dev", label="bug"
            )
            issue_cmd.handle_edit(args, fmt="table")
        adapter.update_issue.assert_called_once_with(
            1,
            title="Updated",
            body="New body",
            assignee="dev",
            label="bug",
            add_labels=None,
            remove_labels=None,
            add_assignees=None,
            remove_assignees=None,
            milestone=None,
        )

    def test_calls_update_with_none_fields(self):
        with patch_adapter("gfo.commands.issue") as adapter:
            adapter.update_issue.return_value = SAMPLE_ISSUE
            args = make_args(number=2, title=None, body=None, assignee=None, label=None)
            issue_cmd.handle_edit(args, fmt="table")
        adapter.update_issue.assert_called_once_with(
            2,
            title=None,
            body=None,
            assignee=None,
            label=None,
            add_labels=None,
            remove_labels=None,
            add_assignees=None,
            remove_assignees=None,
            milestone=None,
        )

    def test_passes_add_labels(self):
        with patch_adapter("gfo.commands.issue") as adapter:
            adapter.update_issue.return_value = SAMPLE_ISSUE
            args = make_args(
                number=1,
                title=None,
                body=None,
                assignee=None,
                label=None,
                add_label=["bug", "urgent"],
                remove_label=None,
                add_assignee=None,
                remove_assignee=None,
                milestone=None,
            )
            issue_cmd.handle_edit(args, fmt="table")
        call_kwargs = adapter.update_issue.call_args.kwargs
        assert call_kwargs["add_labels"] == ["bug", "urgent"]

    def test_passes_remove_labels(self):
        with patch_adapter("gfo.commands.issue") as adapter:
            adapter.update_issue.return_value = SAMPLE_ISSUE
            args = make_args(
                number=1,
                title=None,
                body=None,
                assignee=None,
                label=None,
                add_label=None,
                remove_label=["wontfix"],
                add_assignee=None,
                remove_assignee=None,
                milestone=None,
            )
            issue_cmd.handle_edit(args, fmt="table")
        call_kwargs = adapter.update_issue.call_args.kwargs
        assert call_kwargs["remove_labels"] == ["wontfix"]

    def test_passes_add_assignees(self):
        with patch_adapter("gfo.commands.issue") as adapter:
            adapter.update_issue.return_value = SAMPLE_ISSUE
            args = make_args(
                number=1,
                title=None,
                body=None,
                assignee=None,
                label=None,
                add_label=None,
                remove_label=None,
                add_assignee=["alice"],
                remove_assignee=None,
                milestone=None,
            )
            issue_cmd.handle_edit(args, fmt="table")
        call_kwargs = adapter.update_issue.call_args.kwargs
        assert call_kwargs["add_assignees"] == ["alice"]

    def test_passes_remove_assignees(self):
        with patch_adapter("gfo.commands.issue") as adapter:
            adapter.update_issue.return_value = SAMPLE_ISSUE
            args = make_args(
                number=1,
                title=None,
                body=None,
                assignee=None,
                label=None,
                add_label=None,
                remove_label=None,
                add_assignee=None,
                remove_assignee=["bob"],
                milestone=None,
            )
            issue_cmd.handle_edit(args, fmt="table")
        call_kwargs = adapter.update_issue.call_args.kwargs
        assert call_kwargs["remove_assignees"] == ["bob"]

    def test_passes_milestone(self):
        with patch_adapter("gfo.commands.issue") as adapter:
            adapter.update_issue.return_value = SAMPLE_ISSUE
            args = make_args(
                number=1,
                title=None,
                body=None,
                assignee=None,
                label=None,
                add_label=None,
                remove_label=None,
                add_assignee=None,
                remove_assignee=None,
                milestone="v1.0",
            )
            issue_cmd.handle_edit(args, fmt="table")
        call_kwargs = adapter.update_issue.call_args.kwargs
        assert call_kwargs["milestone"] == "v1.0"


class TestIssueEditArgParsing:
    """issue edit の CLI 引数パースのテスト。"""

    @pytest.fixture
    def parser(self):
        from gfo.cli import create_parser

        p, _ = create_parser()
        return p

    def test_add_label(self, parser):
        ns = parser.parse_args(
            ["issue", "edit", "1", "--add-label", "bug", "--add-label", "urgent"]
        )
        assert ns.add_label == ["bug", "urgent"]

    def test_remove_label(self, parser):
        ns = parser.parse_args(["issue", "edit", "1", "--remove-label", "wontfix"])
        assert ns.remove_label == ["wontfix"]

    def test_add_assignee(self, parser):
        ns = parser.parse_args(["issue", "edit", "1", "--add-assignee", "alice"])
        assert ns.add_assignee == ["alice"]

    def test_remove_assignee(self, parser):
        ns = parser.parse_args(["issue", "edit", "1", "--remove-assignee", "bob"])
        assert ns.remove_assignee == ["bob"]

    def test_milestone(self, parser):
        ns = parser.parse_args(["issue", "edit", "1", "--milestone", "v1.0"])
        assert ns.milestone == "v1.0"

    def test_defaults_are_none(self, parser):
        ns = parser.parse_args(["issue", "edit", "1"])
        assert ns.add_label is None
        assert ns.remove_label is None
        assert ns.add_assignee is None
        assert ns.remove_assignee is None
        assert ns.milestone is None
