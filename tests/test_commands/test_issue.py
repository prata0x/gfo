"""gfo.commands.issue のテスト。"""

from __future__ import annotations

import contextlib
import json
from unittest.mock import MagicMock, patch

import pytest

from gfo.adapter.base import Issue
from gfo.commands import issue as issue_cmd
from gfo.config import ProjectConfig
from gfo.exceptions import ConfigError, HttpError
from tests.test_commands.conftest import make_args, patch_adapter


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
    with (
        patch("gfo.commands.issue.get_adapter", return_value=adapter),
        patch("gfo.commands.issue.get_adapter_with_config", return_value=(adapter, config)),
    ):
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
        assert isinstance(data, list)
        assert data[0]["title"] == "Test Issue"

    def test_plain_format(self, capsys):
        args = make_args(state="open", assignee=None, label=None, limit=30)
        with _patch_all(self.config, self.adapter):
            issue_cmd.handle_list(args, fmt="plain")

        out = capsys.readouterr().out
        assert "\t" in out
        assert "NUMBER" not in out
        assert "Test Issue" in out


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
            type="42",  # CLI からは常に文字列で渡される
            priority=2,
        )
        with _patch_all(config, adapter):
            issue_cmd.handle_create(args, fmt="table")

        call_kwargs = adapter.create_issue.call_args.kwargs
        assert call_kwargs["issue_type"] == 42  # int に変換されていること
        assert call_kwargs["priority"] == 2
        assert "work_item_type" not in call_kwargs

    def test_backlog_issue_type_non_numeric_raises(self):
        """Backlog で --type に非数値を渡した場合 ConfigError になる。"""
        config = _make_config("backlog")
        adapter = _make_adapter(self.issue)
        args = make_args(
            title="Backlog Issue",
            body="",
            assignee=None,
            label=None,
            type="Bug",  # 非数値
            priority=None,
        )
        with _patch_all(config, adapter):
            with pytest.raises(ConfigError, match="numeric issue type ID"):
                issue_cmd.handle_create(args, fmt="table")

    def test_backlog_no_priority_when_none(self):
        config = _make_config("backlog")
        adapter = _make_adapter(self.issue)
        args = make_args(
            title="Backlog Issue",
            body="",
            assignee=None,
            label=None,
            type="42",  # CLI からは常に文字列で渡される
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

    def test_title_with_surrounding_whitespace_is_stripped(self):
        """前後に空白を持つ title は strip されてアダプターに渡される。"""
        config = _make_config("github")
        adapter = _make_adapter(self.issue)
        args = make_args(
            title="  Bug Report  ",
            body="",
            assignee=None,
            label=None,
            type=None,
            priority=None,
        )
        with _patch_all(config, adapter):
            issue_cmd.handle_create(args, fmt="table")

        call_kwargs = adapter.create_issue.call_args.kwargs
        assert call_kwargs["title"] == "Bug Report"


class TestHandleCreateTitleValidation:
    def test_none_title_raises_config_error(self):
        """title=None は ConfigError を送出する。"""
        config = _make_config("github")
        adapter = _make_adapter(_make_issue())
        args = make_args(title=None, body=None, assignee=None, label=None, type=None, priority=None)
        with (
            _patch_all(config, adapter),
            pytest.raises(ConfigError, match="--title must not be empty"),
        ):
            issue_cmd.handle_create(args, fmt="table")

    def test_empty_title_raises_config_error(self):
        """title="" は ConfigError を送出する。"""
        config = _make_config("github")
        adapter = _make_adapter(_make_issue())
        args = make_args(title="", body=None, assignee=None, label=None, type=None, priority=None)
        with (
            _patch_all(config, adapter),
            pytest.raises(ConfigError, match="--title must not be empty"),
        ):
            issue_cmd.handle_create(args, fmt="table")

    def test_whitespace_title_raises_config_error(self):
        """title="   " は ConfigError を送出する。"""
        config = _make_config("github")
        adapter = _make_adapter(_make_issue())
        args = make_args(
            title="   ", body=None, assignee=None, label=None, type=None, priority=None
        )
        with (
            _patch_all(config, adapter),
            pytest.raises(ConfigError, match="--title must not be empty"),
        ):
            issue_cmd.handle_create(args, fmt="table")


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


class TestHandleReopen:
    def setup_method(self):
        self.config = _make_config()
        self.issue = _make_issue()
        self.adapter = _make_adapter(self.issue)

    def test_calls_reopen_issue(self):
        args = make_args(number=1)
        with _patch_all(self.config, self.adapter):
            issue_cmd.handle_reopen(args, fmt="table")

        self.adapter.reopen_issue.assert_called_once_with(1)

    def test_different_number(self):
        args = make_args(number=42)
        with _patch_all(self.config, self.adapter):
            issue_cmd.handle_reopen(args, fmt="table")

        self.adapter.reopen_issue.assert_called_once_with(42)


class TestHandleDelete:
    def setup_method(self):
        self.config = _make_config()
        self.issue = _make_issue()
        self.adapter = _make_adapter(self.issue)

    def test_calls_delete_issue(self):
        args = make_args(number=5)
        with _patch_all(self.config, self.adapter):
            issue_cmd.handle_delete(args, fmt="table")

        self.adapter.delete_issue.assert_called_once_with(5)

    def test_prints_confirmation(self, capsys):
        args = make_args(number=5)
        with _patch_all(self.config, self.adapter):
            issue_cmd.handle_delete(args, fmt="table")

        out = capsys.readouterr().out
        assert "5" in out
        assert "Deleted" in out


class TestErrorPropagation:
    """アダプターのエラーがハンドラを通じて伝搬する。"""

    def setup_method(self):
        self.config = _make_config()
        self.issue = _make_issue()
        self.adapter = _make_adapter(self.issue)

    def test_list_http_error(self):
        self.adapter.list_issues.side_effect = HttpError(500, "Server error")
        args = make_args(state="open", assignee=None, label=None, limit=30)
        with _patch_all(self.config, self.adapter):
            with pytest.raises(HttpError):
                issue_cmd.handle_list(args, fmt="table")

    def test_view_http_error(self):
        self.adapter.get_issue.side_effect = HttpError(404, "Not found")
        args = make_args(number=999)
        with _patch_all(self.config, self.adapter):
            with pytest.raises(HttpError):
                issue_cmd.handle_view(args, fmt="table")

    def test_close_http_error(self):
        self.adapter.close_issue.side_effect = HttpError(404, "Not found")
        args = make_args(number=999)
        with _patch_all(self.config, self.adapter):
            with pytest.raises(HttpError):
                issue_cmd.handle_close(args, fmt="table")


# --- Phase 5: Reaction / Depends / Timeline / Pin / Time ---


class TestHandleReaction:
    def test_list_reactions(self, capsys):
        from gfo.adapter.base import Reaction

        with patch_adapter("gfo.commands.issue") as adapter:
            adapter.list_issue_reactions.return_value = [
                Reaction(
                    id=1,
                    content="+1",
                    user="alice",
                    created_at="2024-01-01T00:00:00Z",
                )
            ]
            args = make_args(reaction_action="list", number=1)
            issue_cmd.handle_reaction(args, fmt="table")
        adapter.list_issue_reactions.assert_called_once_with(1)

    def test_add_reaction(self):
        from gfo.adapter.base import Reaction

        with patch_adapter("gfo.commands.issue") as adapter:
            adapter.add_issue_reaction.return_value = Reaction(
                id=1,
                content="+1",
                user="alice",
                created_at="2024-01-01T00:00:00Z",
            )
            args = make_args(reaction_action="add", number=1, reaction="+1")
            issue_cmd.handle_reaction(args, fmt="table")
        adapter.add_issue_reaction.assert_called_once_with(1, "+1")

    def test_remove_reaction(self):
        with patch_adapter("gfo.commands.issue") as adapter:
            args = make_args(reaction_action="remove", number=1, reaction="+1")
            issue_cmd.handle_reaction(args, fmt="table")
        adapter.remove_issue_reaction.assert_called_once_with(1, "+1")

    def test_no_action_raises(self):
        with patch_adapter("gfo.commands.issue"):
            args = make_args(reaction_action=None, number=1)
            with pytest.raises(ConfigError):
                issue_cmd.handle_reaction(args, fmt="table")


class TestHandleDepends:
    def test_list_dependencies(self, capsys):
        with patch_adapter("gfo.commands.issue") as adapter:
            adapter.list_issue_dependencies.return_value = [_make_issue()]
            args = make_args(depends_action="list", number=1)
            issue_cmd.handle_depends(args, fmt="table")
        adapter.list_issue_dependencies.assert_called_once_with(1)

    def test_add_dependency(self):
        with patch_adapter("gfo.commands.issue") as adapter:
            args = make_args(depends_action="add", number=1, depends_on=2)
            issue_cmd.handle_depends(args, fmt="table")
        adapter.add_issue_dependency.assert_called_once_with(1, 2)

    def test_remove_dependency(self):
        with patch_adapter("gfo.commands.issue") as adapter:
            args = make_args(depends_action="remove", number=1, depends_on=2)
            issue_cmd.handle_depends(args, fmt="table")
        adapter.remove_issue_dependency.assert_called_once_with(1, 2)


class TestHandleTimeline:
    def test_get_timeline(self, capsys):
        from gfo.adapter.base import TimelineEvent

        with patch_adapter("gfo.commands.issue") as adapter:
            adapter.get_issue_timeline.return_value = [
                TimelineEvent(
                    id=1,
                    event="labeled",
                    actor="alice",
                    created_at="2024-01-01T00:00:00Z",
                    detail="bug",
                )
            ]
            args = make_args(number=1, limit=30)
            issue_cmd.handle_timeline(args, fmt="table")
        adapter.get_issue_timeline.assert_called_once_with(1, limit=30)


class TestHandlePin:
    def test_pin_issue(self, capsys):
        with patch_adapter("gfo.commands.issue") as adapter:
            args = make_args(number=1)
            issue_cmd.handle_pin(args, fmt="table")
        adapter.pin_issue.assert_called_once_with(1)

    def test_unpin_issue(self, capsys):
        with patch_adapter("gfo.commands.issue") as adapter:
            args = make_args(number=1)
            issue_cmd.handle_unpin(args, fmt="table")
        adapter.unpin_issue.assert_called_once_with(1)


class TestHandleTime:
    def test_list_time_entries(self, capsys):
        from gfo.adapter.base import TimeEntry

        with patch_adapter("gfo.commands.issue") as adapter:
            adapter.list_time_entries.return_value = [
                TimeEntry(id=1, user="alice", duration=3600, created_at="2024-01-01T00:00:00Z")
            ]
            args = make_args(time_action="list", number=1)
            issue_cmd.handle_time(args, fmt="table")
        adapter.list_time_entries.assert_called_once_with(1)

    def test_add_time_entry(self):
        from gfo.adapter.base import TimeEntry

        with patch_adapter("gfo.commands.issue") as adapter:
            adapter.add_time_entry.return_value = TimeEntry(
                id=1, user="alice", duration=5400, created_at="2024-01-01T00:00:00Z"
            )
            args = make_args(time_action="add", number=1, duration="1h30m")
            issue_cmd.handle_time(args, fmt="table")
        adapter.add_time_entry.assert_called_once_with(1, 5400)

    def test_delete_time_entry(self, capsys):
        with patch_adapter("gfo.commands.issue") as adapter:
            args = make_args(time_action="delete", number=1, entry_id="42")
            issue_cmd.handle_time(args, fmt="table")
        adapter.delete_time_entry.assert_called_once_with(1, "42")


class TestParseDuration:
    def test_hours_and_minutes(self):
        assert issue_cmd._parse_duration("1h30m") == 5400

    def test_hours_only(self):
        assert issue_cmd._parse_duration("2h") == 7200

    def test_minutes_only(self):
        assert issue_cmd._parse_duration("45m") == 2700

    def test_seconds_only(self):
        assert issue_cmd._parse_duration("120s") == 120

    def test_plain_integer(self):
        assert issue_cmd._parse_duration("3600") == 3600

    def test_invalid_format_raises(self):
        with pytest.raises(ConfigError):
            issue_cmd._parse_duration("invalid")
