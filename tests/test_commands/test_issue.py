"""gfo.commands.issue のテスト。"""

from __future__ import annotations

import contextlib
import json
from unittest.mock import MagicMock, patch

import pytest

from gfo.adapter.base import Issue
from gfo.commands import issue as issue_cmd
from gfo.config import ProjectConfig
from gfo.exceptions import ConfigError, GfoError, HttpError
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
            state="open",
            assignee=None,
            label=None,
            limit=30,
            author=None,
            milestone=None,
            search=None,
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
            state="closed",
            assignee="alice",
            label="bug",
            limit=10,
            author=None,
            milestone=None,
            search=None,
        )

    def test_with_new_filters(self):
        args = make_args(
            state="open",
            assignee=None,
            label=None,
            limit=30,
            author="bob",
            milestone="v1.0",
            search="bug fix",
        )
        with _patch_all(self.config, self.adapter):
            issue_cmd.handle_list(args, fmt="table")

        self.adapter.list_issues.assert_called_once_with(
            state="open",
            assignee=None,
            label=None,
            limit=30,
            author="bob",
            milestone="v1.0",
            search="bug fix",
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
            milestone=None,
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
            milestone=None,
            due_date=None,
        )

    def test_create_with_milestone(self):
        config = _make_config("github")
        adapter = _make_adapter(self.issue)
        args = make_args(
            title="New Issue",
            body="",
            assignee=None,
            label=None,
            milestone="v1.0",
            type=None,
            priority=None,
        )
        with _patch_all(config, adapter):
            issue_cmd.handle_create(args, fmt="table")

        adapter.create_issue.assert_called_once_with(
            title="New Issue",
            body="",
            assignee=None,
            label=None,
            milestone="v1.0",
            due_date=None,
        )

    def test_azure_devops_work_item_type(self):
        config = _make_config("azure-devops")
        adapter = _make_adapter(self.issue)
        args = make_args(
            title="My Task",
            body="",
            assignee=None,
            label=None,
            milestone=None,
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
            milestone=None,
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
            milestone=None,
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
            milestone=None,
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
            milestone=None,
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
            milestone=None,
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
            milestone=None,
            type=None,
            priority=None,
        )
        with _patch_all(config, adapter):
            issue_cmd.handle_create(args, fmt="table")

        call_kwargs = adapter.create_issue.call_args.kwargs
        assert call_kwargs["title"] == "Bug Report"

    def test_body_file_overrides_body(self, tmp_path):
        """--body-file が指定されたらファイル内容を body として使用する。"""
        config = _make_config("github")
        adapter = _make_adapter(self.issue)
        body_path = tmp_path / "body.md"
        body_path.write_text("Body from file")
        args = make_args(
            title="New Issue",
            body="",
            assignee=None,
            label=None,
            milestone=None,
            type=None,
            priority=None,
            body_file=str(body_path),
        )
        with _patch_all(config, adapter):
            issue_cmd.handle_create(args, fmt="table")

        call_kwargs = adapter.create_issue.call_args.kwargs
        assert call_kwargs["body"] == "Body from file"

    def test_body_file_none_uses_body(self):
        """--body-file 未指定なら --body の値を使用する。"""
        config = _make_config("github")
        adapter = _make_adapter(self.issue)
        args = make_args(
            title="New Issue",
            body="Inline body",
            assignee=None,
            label=None,
            milestone=None,
            type=None,
            priority=None,
            body_file=None,
        )
        with _patch_all(config, adapter):
            issue_cmd.handle_create(args, fmt="table")

        call_kwargs = adapter.create_issue.call_args.kwargs
        assert call_kwargs["body"] == "Inline body"

    def test_body_file_not_found_raises_gfo_error(self):
        """存在しないファイルを --body-file に指定すると GfoError を送出する。"""
        config = _make_config("github")
        adapter = _make_adapter(self.issue)
        args = make_args(
            title="New Issue",
            body="",
            assignee=None,
            label=None,
            milestone=None,
            type=None,
            priority=None,
            body_file="nonexistent.txt",
        )
        with _patch_all(config, adapter):
            with pytest.raises(GfoError, match="File not found"):
                issue_cmd.handle_create(args, fmt="table")


class TestHandleCreateTitleValidation:
    def test_none_title_raises_config_error(self):
        """title=None は ConfigError を送出する。"""
        config = _make_config("github")
        adapter = _make_adapter(_make_issue())
        args = make_args(
            title=None,
            body=None,
            assignee=None,
            label=None,
            milestone=None,
            type=None,
            priority=None,
        )
        with (
            _patch_all(config, adapter),
            pytest.raises(ConfigError, match="--title must not be empty"),
        ):
            issue_cmd.handle_create(args, fmt="table")

    def test_empty_title_raises_config_error(self):
        """title="" は ConfigError を送出する。"""
        config = _make_config("github")
        adapter = _make_adapter(_make_issue())
        args = make_args(
            title="", body=None, assignee=None, label=None, milestone=None, type=None, priority=None
        )
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
            title="   ",
            body=None,
            assignee=None,
            label=None,
            milestone=None,
            type=None,
            priority=None,
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
        args = make_args(
            state="open",
            assignee=None,
            label=None,
            limit=30,
            author=None,
            milestone=None,
            search=None,
        )
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


class TestHandleLock:
    def test_lock_issue(self, capsys):
        with patch_adapter("gfo.commands.issue") as adapter:
            args = make_args(number=1, reason=None)
            issue_cmd.handle_lock(args, fmt="table")
        adapter.lock_issue.assert_called_once_with(1, reason=None)

    def test_lock_issue_with_reason(self, capsys):
        with patch_adapter("gfo.commands.issue") as adapter:
            args = make_args(number=1, reason="spam")
            issue_cmd.handle_lock(args, fmt="table")
        adapter.lock_issue.assert_called_once_with(1, reason="spam")

    def test_unlock_issue(self, capsys):
        with patch_adapter("gfo.commands.issue") as adapter:
            args = make_args(number=1)
            issue_cmd.handle_unlock(args, fmt="table")
        adapter.unlock_issue.assert_called_once_with(1)


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


# --- C-09: Issue migrate が closed issue の状態を保持する ---


class TestMigrateOneIssue:
    def test_closed_issue_is_closed_on_target(self):
        """closed 状態の Issue を移行すると、ターゲット側でも close_issue が呼ばれる。"""

        closed_issue = Issue(
            number=10,
            title="Closed Issue",
            body="body",
            state="closed",
            author="alice",
            assignees=[],
            labels=[],
            url="https://example.com/issues/10",
            created_at="2024-01-01T00:00:00Z",
        )
        created_issue = Issue(
            number=20,
            title="Closed Issue",
            body="migrated body",
            state="open",
            author="bot",
            assignees=[],
            labels=[],
            url="https://example.com/issues/20",
            created_at="2024-01-01T00:00:00Z",
        )
        src = MagicMock()
        dst = MagicMock()
        src.get_issue.return_value = closed_issue
        src.list_comments.return_value = []
        dst.create_issue.return_value = created_issue

        result = issue_cmd._migrate_one_issue(src, dst, 10, set(), "github:owner/repo")
        assert result.success is True
        assert result.target_number == 20
        dst.close_issue.assert_called_once_with(20)

    def test_open_issue_not_closed_on_target(self):
        """open 状態の Issue を移行すると、close_issue は呼ばれない。"""
        open_issue = Issue(
            number=10,
            title="Open Issue",
            body="body",
            state="open",
            author="alice",
            assignees=[],
            labels=[],
            url="https://example.com/issues/10",
            created_at="2024-01-01T00:00:00Z",
        )
        created_issue = Issue(
            number=20,
            title="Open Issue",
            body="migrated body",
            state="open",
            author="bot",
            assignees=[],
            labels=[],
            url="https://example.com/issues/20",
            created_at="2024-01-01T00:00:00Z",
        )
        src = MagicMock()
        dst = MagicMock()
        src.get_issue.return_value = open_issue
        src.list_comments.return_value = []
        dst.create_issue.return_value = created_issue

        result = issue_cmd._migrate_one_issue(src, dst, 10, set(), "github:owner/repo")
        assert result.success is True
        dst.close_issue.assert_not_called()

    def test_comments_fetched_with_limit_zero(self):
        """コメント取得時に limit=0 で全件取得されることを検証する。"""
        open_issue = _make_issue()
        src = MagicMock()
        dst = MagicMock()
        src.get_issue.return_value = open_issue
        src.list_comments.return_value = []
        dst.create_issue.return_value = open_issue

        issue_cmd._migrate_one_issue(src, dst, 1, set(), "github:owner/repo")
        src.list_comments.assert_called_once_with("issue", 1, limit=0)


class TestHandleListWeb:
    def setup_method(self):
        self.config = _make_config()
        self.issue = _make_issue()
        self.adapter = _make_adapter(self.issue)

    def test_opens_browser(self):
        args = make_args(state="open", assignee=None, label=None, limit=30, web=True)
        with (
            _patch_all(self.config, self.adapter),
            patch("webbrowser.open") as mock_open,
        ):
            issue_cmd.handle_list(args, fmt="table")
        self.adapter.get_web_url.assert_called_once_with("issue")
        mock_open.assert_called_once_with(self.adapter.get_web_url.return_value)

    def test_does_not_call_api(self):
        args = make_args(state="open", assignee=None, label=None, limit=30, web=True)
        with (
            _patch_all(self.config, self.adapter),
            patch("webbrowser.open"),
        ):
            issue_cmd.handle_list(args, fmt="table")
        self.adapter.list_issues.assert_not_called()


class TestHandleViewWeb:
    def setup_method(self):
        self.config = _make_config()
        self.issue = _make_issue()
        self.adapter = _make_adapter(self.issue)

    def test_opens_browser(self):
        args = make_args(number=7, web=True)
        with (
            _patch_all(self.config, self.adapter),
            patch("webbrowser.open") as mock_open,
        ):
            issue_cmd.handle_view(args, fmt="table")
        self.adapter.get_web_url.assert_called_once_with("issue", 7)
        mock_open.assert_called_once_with(self.adapter.get_web_url.return_value)

    def test_does_not_call_api(self):
        args = make_args(number=7, web=True)
        with (
            _patch_all(self.config, self.adapter),
            patch("webbrowser.open"),
        ):
            issue_cmd.handle_view(args, fmt="table")
        self.adapter.get_issue.assert_not_called()


class TestHandleCreateWeb:
    def setup_method(self):
        self.config = _make_config()
        self.issue = _make_issue()
        self.adapter = _make_adapter(self.issue)

    def test_opens_browser_after_create(self):
        args = make_args(
            title="Test Issue",
            body="",
            assignee=None,
            label=None,
            milestone=None,
            type=None,
            priority=None,
            web=True,
        )
        with (
            _patch_all(self.config, self.adapter),
            patch("webbrowser.open") as mock_open,
        ):
            issue_cmd.handle_create(args, fmt="table")
        self.adapter.create_issue.assert_called_once()
        mock_open.assert_called_once_with("https://github.com/test-owner/test-repo/issues/1")

    def test_does_not_open_browser_without_flag(self):
        args = make_args(
            title="Test Issue",
            body="",
            assignee=None,
            label=None,
            milestone=None,
            type=None,
            priority=None,
        )
        with (
            _patch_all(self.config, self.adapter),
            patch("webbrowser.open") as mock_open,
        ):
            issue_cmd.handle_create(args, fmt="table")
        mock_open.assert_not_called()


class TestIssueCreateWebArgParsing:
    def test_web_flag_parsed(self):
        from gfo.cli import create_parser

        parser, _ = create_parser()
        ns = parser.parse_args(["issue", "create", "--title", "Test", "--web"])
        assert ns.web is True

    def test_web_short_flag_parsed(self):
        from gfo.cli import create_parser

        parser, _ = create_parser()
        ns = parser.parse_args(["issue", "create", "--title", "Test", "-w"])
        assert ns.web is True

    def test_web_default_is_false(self):
        from gfo.cli import create_parser

        parser, _ = create_parser()
        ns = parser.parse_args(["issue", "create", "--title", "Test"])
        assert ns.web is False


class TestHandleSubscribe:
    def test_subscribe_issue(self, capsys):
        with patch_adapter("gfo.commands.issue") as adapter:
            args = make_args(number=1)
            issue_cmd.handle_subscribe(args, fmt="table")
        adapter.subscribe_issue.assert_called_once_with(1)
        out = capsys.readouterr().out
        assert "#1" in out

    def test_unsubscribe_issue(self, capsys):
        with patch_adapter("gfo.commands.issue") as adapter:
            args = make_args(number=1)
            issue_cmd.handle_unsubscribe(args, fmt="table")
        adapter.unsubscribe_issue.assert_called_once_with(1)


# --- 4a: --due-date ---


class TestHandleCreateDueDate:
    def setup_method(self):
        self.issue = _make_issue()

    def test_create_with_due_date(self):
        config = _make_config("github")
        adapter = _make_adapter(self.issue)
        args = make_args(
            title="Issue with due date",
            body="",
            assignee=None,
            label=None,
            milestone=None,
            type=None,
            priority=None,
            due_date="2026-04-01",
        )
        with _patch_all(config, adapter):
            issue_cmd.handle_create(args, fmt="table")

        call_kwargs = adapter.create_issue.call_args.kwargs
        assert call_kwargs["due_date"] == "2026-04-01"

    def test_create_without_due_date(self):
        config = _make_config("github")
        adapter = _make_adapter(self.issue)
        args = make_args(
            title="Issue no due date",
            body="",
            assignee=None,
            label=None,
            milestone=None,
            type=None,
            priority=None,
        )
        with _patch_all(config, adapter):
            issue_cmd.handle_create(args, fmt="table")

        call_kwargs = adapter.create_issue.call_args.kwargs
        assert call_kwargs["due_date"] is None


class TestHandleEditDueDate:
    def setup_method(self):
        self.config = _make_config()
        self.issue = _make_issue()
        self.adapter = _make_adapter(self.issue)
        self.adapter.update_issue.return_value = self.issue

    def test_edit_with_due_date(self):
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
            milestone=None,
            due_date="2026-05-01",
        )
        with _patch_all(self.config, self.adapter):
            issue_cmd.handle_edit(args, fmt="table")

        call_kwargs = self.adapter.update_issue.call_args.kwargs
        assert call_kwargs["due_date"] == "2026-05-01"

    def test_edit_without_due_date(self):
        args = make_args(
            number=1,
            title="New Title",
            body=None,
            assignee=None,
            label=None,
            add_label=None,
            remove_label=None,
            add_assignee=None,
            remove_assignee=None,
            milestone=None,
        )
        with _patch_all(self.config, self.adapter):
            issue_cmd.handle_edit(args, fmt="table")

        call_kwargs = self.adapter.update_issue.call_args.kwargs
        assert call_kwargs["due_date"] is None


# --- 4b: --template ---


class TestHandleCreateTemplate:
    def setup_method(self):
        self.issue = _make_issue()

    def test_template_sets_body(self):
        from gfo.adapter.base import IssueTemplate

        config = _make_config("github")
        adapter = _make_adapter(self.issue)
        adapter.list_issue_templates.return_value = [
            IssueTemplate(
                name="bug_report",
                title="Bug: ",
                body="## Steps to reproduce\n\n## Expected\n\n## Actual\n",
                about="Report a bug",
                labels=("bug",),
            ),
        ]
        args = make_args(
            title="My bug",
            body="",
            assignee=None,
            label=None,
            milestone=None,
            type=None,
            priority=None,
            template="bug_report",
        )
        with _patch_all(config, adapter):
            issue_cmd.handle_create(args, fmt="table")

        call_kwargs = adapter.create_issue.call_args.kwargs
        assert "Steps to reproduce" in call_kwargs["body"]

    def test_template_not_found_raises(self):
        from gfo.adapter.base import IssueTemplate

        config = _make_config("github")
        adapter = _make_adapter(self.issue)
        adapter.list_issue_templates.return_value = [
            IssueTemplate(
                name="bug_report",
                title="",
                body="template body",
                about="",
                labels=(),
            ),
        ]
        args = make_args(
            title="My issue",
            body="",
            assignee=None,
            label=None,
            milestone=None,
            type=None,
            priority=None,
            template="nonexistent",
        )
        with _patch_all(config, adapter):
            with pytest.raises(ConfigError, match="nonexistent"):
                issue_cmd.handle_create(args, fmt="table")

    def test_template_skipped_when_body_provided(self):
        config = _make_config("github")
        adapter = _make_adapter(self.issue)
        args = make_args(
            title="My issue",
            body="My custom body",
            assignee=None,
            label=None,
            milestone=None,
            type=None,
            priority=None,
            template="bug_report",
        )
        with _patch_all(config, adapter):
            issue_cmd.handle_create(args, fmt="table")

        # body が既に指定されている場合、テンプレートは無視される
        call_kwargs = adapter.create_issue.call_args.kwargs
        assert call_kwargs["body"] == "My custom body"
        adapter.list_issue_templates.assert_not_called()

    def test_template_title_used_when_no_title_given(self):
        """--title 未指定でもテンプレートの title が使われれば ConfigError にならない。"""
        from gfo.adapter.base import IssueTemplate

        config = _make_config("github")
        adapter = _make_adapter(self.issue)
        adapter.list_issue_templates.return_value = [
            IssueTemplate(
                name="bug_report",
                title="Bug Report",
                body="## Description\n",
                about="Report a bug",
                labels=("bug",),
            ),
        ]
        args = make_args(
            title="",
            body="",
            assignee=None,
            label=None,
            milestone=None,
            type=None,
            priority=None,
            template="bug_report",
        )
        with _patch_all(config, adapter):
            issue_cmd.handle_create(args, fmt="table")

        call_kwargs = adapter.create_issue.call_args.kwargs
        assert call_kwargs["title"] == "Bug Report"
        assert "Description" in call_kwargs["body"]


# --- 4c: issue status ---


class TestHandleStatus:
    def setup_method(self):
        self.config = _make_config()
        self.issue = _make_issue()
        self.adapter = _make_adapter(self.issue)
        self.adapter.get_current_username.return_value = "test-user"

    def test_calls_list_issues_for_created_and_assigned(self):
        args = make_args()
        with _patch_all(self.config, self.adapter):
            issue_cmd.handle_status(args, fmt="table")

        calls = self.adapter.list_issues.call_args_list
        assert len(calls) == 2
        assert calls[0].kwargs == {"state": "open", "author": "test-user"}
        assert calls[1].kwargs == {"state": "open", "assignee": "test-user"}

    def test_outputs_sections(self, capsys):
        args = make_args()
        with _patch_all(self.config, self.adapter):
            issue_cmd.handle_status(args, fmt="table")

        out = capsys.readouterr().out
        assert "Created by you" in out
        assert "Assigned to you" in out
        assert "Test Issue" in out

    def test_empty_results(self, capsys):
        self.adapter.list_issues.return_value = []
        args = make_args()
        with _patch_all(self.config, self.adapter):
            issue_cmd.handle_status(args, fmt="table")

        out = capsys.readouterr().out
        assert "No issues found" in out

    def test_json_format(self, capsys):
        args = make_args()
        with _patch_all(self.config, self.adapter):
            issue_cmd.handle_status(args, fmt="json")

        out = capsys.readouterr().out
        data = json.loads(out)
        assert "created" in data
        assert "assigned" in data
        assert len(data["created"]) == 1
        assert data["created"][0]["title"] == "Test Issue"


# --- 4d: issue develop ---


class TestHandleDevelop:
    def setup_method(self):
        self.config = _make_config()
        self.issue = _make_issue()
        self.adapter = _make_adapter(self.issue)

    def _make_branch(self, name="issue-1-test-issue"):
        from gfo.adapter.base import Branch

        return Branch(name=name, sha="abc123", protected=False, url="https://example.com")

    def _make_repo(self, default_branch="main"):
        from gfo.adapter.base import Repository

        return Repository(
            name="test-repo",
            full_name="test-owner/test-repo",
            description=None,
            visibility="public",
            default_branch=default_branch,
            clone_url="https://github.com/test-owner/test-repo.git",
            url="https://github.com/test-owner/test-repo",
        )

    def test_creates_branch_with_auto_name(self):
        branch = self._make_branch()
        self.adapter.create_branch.return_value = branch
        self.adapter.get_repository.return_value = self._make_repo()
        args = make_args(number=1)
        with _patch_all(self.config, self.adapter):
            issue_cmd.handle_develop(args, fmt="table")

        call_kwargs = self.adapter.create_branch.call_args.kwargs
        assert call_kwargs["name"] == "issue-1-test-issue"
        assert call_kwargs["ref"] == "main"

    def test_creates_branch_with_custom_name(self):
        branch = self._make_branch(name="my-branch")
        self.adapter.create_branch.return_value = branch
        args = make_args(number=1, name="my-branch")
        with _patch_all(self.config, self.adapter):
            issue_cmd.handle_develop(args, fmt="table")

        call_kwargs = self.adapter.create_branch.call_args.kwargs
        assert call_kwargs["name"] == "my-branch"

    def test_creates_branch_with_custom_base(self):
        branch = self._make_branch()
        self.adapter.create_branch.return_value = branch
        args = make_args(number=1, base="develop")
        with _patch_all(self.config, self.adapter):
            issue_cmd.handle_develop(args, fmt="table")

        call_kwargs = self.adapter.create_branch.call_args.kwargs
        assert call_kwargs["ref"] == "develop"

    def test_uses_default_branch_from_repo(self):
        branch = self._make_branch()
        self.adapter.create_branch.return_value = branch
        self.adapter.get_repository.return_value = self._make_repo(default_branch="master")
        args = make_args(number=1)
        with _patch_all(self.config, self.adapter):
            issue_cmd.handle_develop(args, fmt="table")

        call_kwargs = self.adapter.create_branch.call_args.kwargs
        assert call_kwargs["ref"] == "master"

    def test_json_format(self, capsys):
        branch = self._make_branch()
        self.adapter.create_branch.return_value = branch
        self.adapter.get_repository.return_value = self._make_repo()
        args = make_args(number=1)
        with _patch_all(self.config, self.adapter):
            issue_cmd.handle_develop(args, fmt="json")

        out = capsys.readouterr().out
        data = json.loads(out)
        # output() は単一オブジェクトもリストとしてシリアライズする
        if isinstance(data, list):
            assert data[0]["name"] == "issue-1-test-issue"
        else:
            assert data["name"] == "issue-1-test-issue"


# --- _slugify ---


class TestSlugify:
    def test_simple_title(self):
        assert issue_cmd._slugify("Fix login bug") == "fix-login-bug"

    def test_special_characters(self):
        assert issue_cmd._slugify("Add feature: user-auth!") == "add-feature-user-auth"

    def test_unicode_title(self):
        result = issue_cmd._slugify("ログインバグ修正")
        assert result == "issue"  # 日本語は ASCII 変換で消えるのでフォールバック

    def test_max_length(self):
        result = issue_cmd._slugify("A" * 100, max_len=10)
        assert len(result) <= 10

    def test_empty_string(self):
        assert issue_cmd._slugify("") == "issue"

    def test_trailing_hyphens_stripped(self):
        result = issue_cmd._slugify("test---", max_len=4)
        assert not result.endswith("-")
