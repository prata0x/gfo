"""gfo.commands.issue のテスト。"""

from __future__ import annotations

import contextlib
import json
from unittest.mock import MagicMock, patch

from gfo.adapter.base import Issue
from gfo.commands import issue as issue_cmd
from gfo.config import ProjectConfig
from tests.test_commands.conftest import make_args


def _make_config(service_type: str = "github") -> ProjectConfig:
    return ProjectConfig(
        service_type=service_type,
        host="github.com",
        api_url="https://api.github.com",
        owner="test-owner",
        repo="test-repo",
    )


def _make_issue() -> Issue:
    return Issue(
        number=1,
        title="Test Issue",
        body="Test body",
        state="open",
        author="test-user",
        assignees=[],
        labels=[],
        url="https://github.com/test-owner/test-repo/issues/1",
        created_at="2024-01-01T00:00:00Z",
    )


def _make_adapter(sample_issue: Issue) -> MagicMock:
    adapter = MagicMock()
    adapter.list_issues.return_value = [sample_issue]
    adapter.create_issue.return_value = sample_issue
    adapter.get_issue.return_value = sample_issue
    return adapter


@contextlib.contextmanager
def _patch_all(config: ProjectConfig, adapter: MagicMock):
    with patch("gfo.commands.issue.resolve_project_config", return_value=config), \
         patch("gfo.commands.issue.create_adapter", return_value=adapter):
        yield


class TestHandleList:
    def setup_method(self):
        self.config = _make_config()
        self.issue = _make_issue()
        self.adapter = _make_adapter(self.issue)

    def test_calls_list_issues(self):
        args = make_args(state="open", assignee=None, label=None, limit=30)
        with _patch_all(self.config, self.adapter):
            issue_cmd.handle_list(args, fmt="table")

        self.adapter.list_issues.assert_called_once_with(
            state="open", assignee=None, label=None, limit=30
        )

    def test_outputs_results(self, capsys):
        args = make_args(state="open", assignee=None, label=None, limit=30)
        with _patch_all(self.config, self.adapter):
            issue_cmd.handle_list(args, fmt="table")

        out = capsys.readouterr().out
        assert "Test Issue" in out
        assert "open" in out

    def test_with_filters(self):
        args = make_args(state="closed", assignee="alice", label="bug", limit=10)
        with _patch_all(self.config, self.adapter):
            issue_cmd.handle_list(args, fmt="table")

        self.adapter.list_issues.assert_called_once_with(
            state="closed", assignee="alice", label="bug", limit=10
        )

    def test_json_format(self, capsys):
        args = make_args(state="open", assignee=None, label=None, limit=10)
        with _patch_all(self.config, self.adapter):
            issue_cmd.handle_list(args, fmt="json")

        out = capsys.readouterr().out
        data = json.loads(out)
        if isinstance(data, list):
            assert data[0]["title"] == "Test Issue"
        else:
            assert data["title"] == "Test Issue"


class TestHandleCreate:
    def setup_method(self):
        self.issue = _make_issue()

    def test_basic_create(self):
        config = _make_config("github")
        adapter = _make_adapter(self.issue)
        args = make_args(
            title="New Issue",
            body="Description",
            assignee=None,
            label=None,
            type=None,
            priority=None,
        )
        with _patch_all(config, adapter):
            issue_cmd.handle_create(args, fmt="table")

        adapter.create_issue.assert_called_once_with(
            title="New Issue",
            body="Description",
            assignee=None,
            label=None,
        )

    def test_azure_devops_work_item_type(self):
        config = _make_config("azure-devops")
        adapter = _make_adapter(self.issue)
        args = make_args(
            title="My Task",
            body="",
            assignee=None,
            label=None,
            type="Bug",
            priority=None,
        )
        with _patch_all(config, adapter):
            issue_cmd.handle_create(args, fmt="table")

        call_kwargs = adapter.create_issue.call_args.kwargs
        assert call_kwargs["work_item_type"] == "Bug"
        assert "issue_type" not in call_kwargs

    def test_backlog_issue_type_and_priority(self):
        config = _make_config("backlog")
        adapter = _make_adapter(self.issue)
        args = make_args(
            title="Backlog Issue",
            body="",
            assignee=None,
            label=None,
            type=42,
            priority=2,
        )
        with _patch_all(config, adapter):
            issue_cmd.handle_create(args, fmt="table")

        call_kwargs = adapter.create_issue.call_args.kwargs
        assert call_kwargs["issue_type"] == 42
        assert call_kwargs["priority"] == 2
        assert "work_item_type" not in call_kwargs

    def test_backlog_no_priority_when_none(self):
        config = _make_config("backlog")
        adapter = _make_adapter(self.issue)
        args = make_args(
            title="Backlog Issue",
            body="",
            assignee=None,
            label=None,
            type=42,
            priority=None,
        )
        with _patch_all(config, adapter):
            issue_cmd.handle_create(args, fmt="table")

        call_kwargs = adapter.create_issue.call_args.kwargs
        assert "priority" not in call_kwargs

    def test_github_ignores_type(self):
        config = _make_config("github")
        adapter = _make_adapter(self.issue)
        args = make_args(
            title="GH Issue",
            body="",
            assignee=None,
            label=None,
            type="enhancement",
            priority=None,
        )
        with _patch_all(config, adapter):
            issue_cmd.handle_create(args, fmt="table")

        call_kwargs = adapter.create_issue.call_args.kwargs
        assert "work_item_type" not in call_kwargs
        assert "issue_type" not in call_kwargs

    def test_body_defaults_to_empty_string(self):
        config = _make_config("github")
        adapter = _make_adapter(self.issue)
        args = make_args(
            title="No Body",
            body=None,
            assignee=None,
            label=None,
            type=None,
            priority=None,
        )
        with _patch_all(config, adapter):
            issue_cmd.handle_create(args, fmt="table")

        call_kwargs = adapter.create_issue.call_args.kwargs
        assert call_kwargs["body"] == ""


class TestHandleView:
    def setup_method(self):
        self.config = _make_config()
        self.issue = _make_issue()
        self.adapter = _make_adapter(self.issue)

    def test_calls_get_issue(self):
        args = make_args(number=1)
        with _patch_all(self.config, self.adapter):
            issue_cmd.handle_view(args, fmt="table")

        self.adapter.get_issue.assert_called_once_with(1)

    def test_outputs_issue(self, capsys):
        args = make_args(number=1)
        with _patch_all(self.config, self.adapter):
            issue_cmd.handle_view(args, fmt="table")

        out = capsys.readouterr().out
        assert "Test Issue" in out


class TestHandleClose:
    def setup_method(self):
        self.config = _make_config()
        self.issue = _make_issue()
        self.adapter = _make_adapter(self.issue)

    def test_calls_close_issue(self):
        args = make_args(number=1)
        with _patch_all(self.config, self.adapter):
            issue_cmd.handle_close(args, fmt="table")

        self.adapter.close_issue.assert_called_once_with(1)

    def test_different_number(self):
        args = make_args(number=42)
        with _patch_all(self.config, self.adapter):
            issue_cmd.handle_close(args, fmt="table")

        self.adapter.close_issue.assert_called_once_with(42)
