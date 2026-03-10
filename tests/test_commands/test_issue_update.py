"""gfo.commands.issue handle_update のテスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from gfo.adapter.base import Issue
from gfo.commands import issue as issue_cmd
from tests.test_commands.conftest import make_args

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


def _patch(adapter):
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        with patch("gfo.commands.issue.get_adapter", return_value=adapter):
            yield

    return _ctx()


class TestHandleUpdate:
    def test_calls_update_issue(self):
        adapter = MagicMock()
        adapter.update_issue.return_value = SAMPLE_ISSUE
        args = make_args(number=1, title="Updated", body="New body", assignee="dev", label="bug")
        with _patch(adapter):
            issue_cmd.handle_update(args, fmt="table")
        adapter.update_issue.assert_called_once_with(
            1, title="Updated", body="New body", assignee="dev", label="bug"
        )

    def test_calls_update_with_none_fields(self):
        adapter = MagicMock()
        adapter.update_issue.return_value = SAMPLE_ISSUE
        args = make_args(number=2, title=None, body=None, assignee=None, label=None)
        with _patch(adapter):
            issue_cmd.handle_update(args, fmt="table")
        adapter.update_issue.assert_called_once_with(
            2, title=None, body=None, assignee=None, label=None
        )
