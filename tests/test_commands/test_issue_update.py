"""gfo.commands.issue handle_update のテスト。"""

from __future__ import annotations

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


class TestHandleUpdate:
    def test_calls_update_issue(self):
        with patch_adapter("gfo.commands.issue") as adapter:
            adapter.update_issue.return_value = SAMPLE_ISSUE
            args = make_args(
                number=1, title="Updated", body="New body", assignee="dev", label="bug"
            )
            issue_cmd.handle_update(args, fmt="table")
        adapter.update_issue.assert_called_once_with(
            1, title="Updated", body="New body", assignee="dev", label="bug"
        )

    def test_calls_update_with_none_fields(self):
        with patch_adapter("gfo.commands.issue") as adapter:
            adapter.update_issue.return_value = SAMPLE_ISSUE
            args = make_args(number=2, title=None, body=None, assignee=None, label=None)
            issue_cmd.handle_update(args, fmt="table")
        adapter.update_issue.assert_called_once_with(
            2, title=None, body=None, assignee=None, label=None
        )
