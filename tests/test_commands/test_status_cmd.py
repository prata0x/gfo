"""gfo.commands.status のテスト。"""

from __future__ import annotations

from gfo.adapter.base import CommitStatus
from gfo.commands import status as status_cmd
from tests.test_commands.conftest import make_args, patch_adapter

SAMPLE_STATUS = CommitStatus(
    state="success",
    context="ci/build",
    description="Build passed",
    target_url="https://ci.example.com/1",
    created_at="2024-01-01T00:00:00Z",
)


class TestHandleList:
    def test_calls_list_commit_statuses(self, capsys):
        with patch_adapter("gfo.commands.status") as adapter:
            adapter.list_commit_statuses.return_value = [SAMPLE_STATUS]
            args = make_args(ref="abc123", limit=30)
            status_cmd.handle_list(args, fmt="table")
        adapter.list_commit_statuses.assert_called_once_with("abc123", limit=30)


class TestHandleCreate:
    def test_calls_create_commit_status(self):
        with patch_adapter("gfo.commands.status") as adapter:
            adapter.create_commit_status.return_value = SAMPLE_STATUS
            args = make_args(
                ref="abc123",
                state="success",
                context="ci/build",
                description="passed",
                url="https://ci.example.com",
            )
            status_cmd.handle_create(args, fmt="table")
        adapter.create_commit_status.assert_called_once_with(
            "abc123",
            state="success",
            context="ci/build",
            description="passed",
            target_url="https://ci.example.com",
        )
