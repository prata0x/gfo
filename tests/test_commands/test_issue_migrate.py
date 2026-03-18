"""gfo issue migrate のテスト。"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from gfo.adapter.base import Comment, Issue, Label
from gfo.commands import issue as issue_cmd
from gfo.commands.issue import _migrate_one_issue, _sync_labels
from gfo.exceptions import HttpError, NotSupportedError
from tests.test_commands.conftest import make_args


def _make_issue(
    number=1,
    title="Test Issue",
    body="Issue body",
    state="open",
    author="alice",
    assignees=None,
    labels=None,
    url="https://github.com/src-owner/src-repo/issues/1",
    created_at="2024-01-01T00:00:00Z",
):
    return Issue(
        number=number,
        title=title,
        body=body,
        state=state,
        author=author,
        assignees=assignees or [],
        labels=labels or [],
        url=url,
        created_at=created_at,
    )


def _make_comment(id=1, body="comment body", author="bob", created_at="2024-01-15T10:30:00Z"):
    return Comment(
        id=id,
        body=body,
        author=author,
        url="https://github.com/src-owner/src-repo/issues/1#comment-1",
        created_at=created_at,
    )


def _make_src_spec():
    spec = MagicMock()
    spec.service_type = "github"
    spec.owner = "src-owner"
    spec.repo = "src-repo"
    return spec


def _make_dst_spec():
    spec = MagicMock()
    spec.service_type = "gitlab"
    spec.owner = "dst-owner"
    spec.repo = "dst-repo"
    return spec


class TestHandleMigrateSingleIssue:
    """単一 Issue 移行成功（--number）"""

    @patch("gfo.commands.issue.create_adapter_from_spec")
    @patch("gfo.commands.issue.parse_service_spec")
    def test_single_issue_migration(self, mock_parse, mock_create_adapter, capsys):
        src_spec = _make_src_spec()
        dst_spec = _make_dst_spec()
        mock_parse.side_effect = [src_spec, dst_spec]

        src_adapter = MagicMock()
        dst_adapter = MagicMock()
        mock_create_adapter.side_effect = [src_adapter, dst_adapter]

        src_issue = _make_issue(number=1, labels=["bug"], assignees=["alice"])
        created_issue = _make_issue(number=10)
        src_adapter.get_issue.return_value = src_issue
        dst_adapter.create_issue.return_value = created_issue
        src_adapter.list_comments.return_value = [_make_comment()]
        src_adapter.list_labels.return_value = [Label(name="bug", color="ff0000", description=None)]
        dst_adapter.list_labels.return_value = [Label(name="bug", color="ff0000", description=None)]

        args = make_args(
            from_spec="github:src-owner/src-repo",
            to_spec="gitlab:dst-owner/dst-repo",
            number=1,
            numbers=None,
            migrate_all=False,
        )
        issue_cmd.handle_migrate(args, fmt="table")

        dst_adapter.create_issue.assert_called_once()
        dst_adapter.create_comment.assert_called_once()


class TestHandleMigrateMultipleIssues:
    """複数 Issue 移行（--numbers "1,2,3"）"""

    @patch("gfo.commands.issue.create_adapter_from_spec")
    @patch("gfo.commands.issue.parse_service_spec")
    def test_multiple_issues_migration(self, mock_parse, mock_create_adapter, capsys):
        src_spec = _make_src_spec()
        dst_spec = _make_dst_spec()
        mock_parse.side_effect = [src_spec, dst_spec]

        src_adapter = MagicMock()
        dst_adapter = MagicMock()
        mock_create_adapter.side_effect = [src_adapter, dst_adapter]

        src_adapter.get_issue.side_effect = [
            _make_issue(number=1),
            _make_issue(number=2),
            _make_issue(number=3),
        ]
        dst_adapter.create_issue.side_effect = [
            _make_issue(number=10),
            _make_issue(number=11),
            _make_issue(number=12),
        ]
        src_adapter.list_comments.return_value = []
        src_adapter.list_labels.return_value = []
        dst_adapter.list_labels.return_value = []

        args = make_args(
            from_spec="github:src-owner/src-repo",
            to_spec="gitlab:dst-owner/dst-repo",
            number=None,
            numbers="1,2,3",
            migrate_all=False,
        )
        issue_cmd.handle_migrate(args, fmt="table")

        assert src_adapter.get_issue.call_count == 3
        assert dst_adapter.create_issue.call_count == 3


class TestHandleMigrateAllIssues:
    """全 Issue 移行（--all）"""

    @patch("gfo.commands.issue.create_adapter_from_spec")
    @patch("gfo.commands.issue.parse_service_spec")
    def test_all_issues_migration(self, mock_parse, mock_create_adapter, capsys):
        src_spec = _make_src_spec()
        dst_spec = _make_dst_spec()
        mock_parse.side_effect = [src_spec, dst_spec]

        src_adapter = MagicMock()
        dst_adapter = MagicMock()
        mock_create_adapter.side_effect = [src_adapter, dst_adapter]

        src_adapter.list_issues.return_value = [
            _make_issue(number=1),
            _make_issue(number=2),
        ]
        src_adapter.get_issue.side_effect = [
            _make_issue(number=1),
            _make_issue(number=2),
        ]
        dst_adapter.create_issue.side_effect = [
            _make_issue(number=10),
            _make_issue(number=11),
        ]
        src_adapter.list_comments.return_value = []
        src_adapter.list_labels.return_value = []
        dst_adapter.list_labels.return_value = []

        args = make_args(
            from_spec="github:src-owner/src-repo",
            to_spec="gitlab:dst-owner/dst-repo",
            number=None,
            numbers=None,
            migrate_all=True,
        )
        issue_cmd.handle_migrate(args, fmt="table")

        src_adapter.list_issues.assert_called_once_with(state="all", limit=0)
        assert src_adapter.get_issue.call_count == 2
        assert dst_adapter.create_issue.call_count == 2


class TestMigrateBodyMetadata:
    """移行先 body に元URL/author/created_at が埋め込まれる"""

    def test_body_contains_metadata_with_url(self):
        src_adapter = MagicMock()
        dst_adapter = MagicMock()

        src_issue = _make_issue(
            number=42,
            body="Original body text",
            author="alice",
            url="https://github.com/src-owner/src-repo/issues/42",
            created_at="2024-01-01T00:00:00Z",
        )
        created_issue = _make_issue(number=10)
        src_adapter.get_issue.return_value = src_issue
        dst_adapter.create_issue.return_value = created_issue
        src_adapter.list_comments.return_value = []

        _migrate_one_issue(src_adapter, dst_adapter, 42, set(), "github:src-owner/src-repo")

        call_kwargs = dst_adapter.create_issue.call_args
        body = call_kwargs.kwargs.get("body") or call_kwargs[1].get("body")
        assert "[github:src-owner/src-repo#42]" in body
        assert "(https://github.com/src-owner/src-repo/issues/42)" in body
        assert "@alice" in body
        assert "2024-01-01T00:00:00Z" in body
        assert "Original body text" in body

    def test_body_without_url(self):
        src_adapter = MagicMock()
        dst_adapter = MagicMock()

        src_issue = _make_issue(
            number=42,
            body="Body text",
            author="alice",
            url="",
            created_at="2024-01-01T00:00:00Z",
        )
        created_issue = _make_issue(number=10)
        src_adapter.get_issue.return_value = src_issue
        dst_adapter.create_issue.return_value = created_issue
        src_adapter.list_comments.return_value = []

        _migrate_one_issue(src_adapter, dst_adapter, 42, set(), "github:src-owner/src-repo")

        call_kwargs = dst_adapter.create_issue.call_args
        body = call_kwargs.kwargs.get("body") or call_kwargs[1].get("body")
        assert "> *Migrated from github:src-owner/src-repo#42*" in body
        assert "[" not in body.split("\n")[0]  # リンク形式ではない


class TestMigrateCommentMetadata:
    """コメント本文に元 author/created_at が埋め込まれる"""

    def test_comment_body_contains_metadata(self):
        src_adapter = MagicMock()
        dst_adapter = MagicMock()

        src_issue = _make_issue(number=1)
        created_issue = _make_issue(number=10)
        src_adapter.get_issue.return_value = src_issue
        dst_adapter.create_issue.return_value = created_issue
        src_adapter.list_comments.return_value = [
            _make_comment(
                id=1,
                body="This is a comment",
                author="bob",
                created_at="2024-01-15T10:30:00Z",
            )
        ]

        _migrate_one_issue(src_adapter, dst_adapter, 1, set(), "github:src-owner/src-repo")

        call_kwargs = dst_adapter.create_comment.call_args
        comment_body = call_kwargs.kwargs.get("body") or call_kwargs[1].get("body")
        assert "@bob" in comment_body
        assert "2024-01-15T10:30:00Z" in comment_body
        assert "This is a comment" in comment_body


class TestSyncLabels:
    """ラベル同期テスト"""

    def test_creates_missing_labels(self):
        src_adapter = MagicMock()
        dst_adapter = MagicMock()

        src_adapter.list_labels.return_value = [
            Label(name="bug", color="ff0000", description=None),
            Label(name="feature", color="00ff00", description=None),
        ]
        dst_adapter.list_labels.return_value = [
            Label(name="bug", color="ff0000", description=None),
        ]

        result = _sync_labels(src_adapter, dst_adapter)

        dst_adapter.create_label.assert_called_once_with(name="feature", color="00ff00")
        assert "bug" in result
        assert "feature" in result

    def test_create_label_not_supported_skips(self, capsys):
        src_adapter = MagicMock()
        dst_adapter = MagicMock()

        src_adapter.list_labels.return_value = [
            Label(name="feature", color="00ff00", description=None),
        ]
        dst_adapter.list_labels.return_value = []
        dst_adapter.create_label.side_effect = NotSupportedError("test", "create_label")

        result = _sync_labels(src_adapter, dst_adapter)

        captured = capsys.readouterr()
        assert "feature" in captured.err
        assert "feature" not in result


class TestMigratePartialFailure:
    """一部 Issue 移行失敗 → 残りは続行"""

    @patch("gfo.commands.issue.create_adapter_from_spec")
    @patch("gfo.commands.issue.parse_service_spec")
    def test_partial_failure_continues(self, mock_parse, mock_create_adapter, capsys):
        src_spec = _make_src_spec()
        dst_spec = _make_dst_spec()
        mock_parse.side_effect = [src_spec, dst_spec]

        src_adapter = MagicMock()
        dst_adapter = MagicMock()
        mock_create_adapter.side_effect = [src_adapter, dst_adapter]

        src_adapter.get_issue.side_effect = [
            HttpError(500, "Server Error"),
            _make_issue(number=2),
        ]
        dst_adapter.create_issue.return_value = _make_issue(number=20)
        src_adapter.list_comments.return_value = []
        src_adapter.list_labels.return_value = []
        dst_adapter.list_labels.return_value = []

        args = make_args(
            from_spec="github:src-owner/src-repo",
            to_spec="gitlab:dst-owner/dst-repo",
            number=None,
            numbers="1,2",
            migrate_all=False,
        )
        issue_cmd.handle_migrate(args, fmt="json")

        captured = capsys.readouterr()
        results = json.loads(captured.out)
        assert len(results) == 2
        # Issue 1 failed
        assert results[0]["success"] is False
        assert results[0]["error"] is not None
        # Issue 2 succeeded
        assert results[1]["success"] is True
        assert results[1]["target_number"] == 20


class TestMigrateJsonOutput:
    """JSON 出力形式テスト"""

    @patch("gfo.commands.issue.create_adapter_from_spec")
    @patch("gfo.commands.issue.parse_service_spec")
    def test_json_output(self, mock_parse, mock_create_adapter, capsys):
        src_spec = _make_src_spec()
        dst_spec = _make_dst_spec()
        mock_parse.side_effect = [src_spec, dst_spec]

        src_adapter = MagicMock()
        dst_adapter = MagicMock()
        mock_create_adapter.side_effect = [src_adapter, dst_adapter]

        src_adapter.get_issue.return_value = _make_issue(number=1)
        dst_adapter.create_issue.return_value = _make_issue(number=10)
        src_adapter.list_comments.return_value = []
        src_adapter.list_labels.return_value = []
        dst_adapter.list_labels.return_value = []

        args = make_args(
            from_spec="github:src-owner/src-repo",
            to_spec="gitlab:dst-owner/dst-repo",
            number=1,
            numbers=None,
            migrate_all=False,
        )
        issue_cmd.handle_migrate(args, fmt="json")

        captured = capsys.readouterr()
        results = json.loads(captured.out)
        assert len(results) == 1
        assert results[0]["source_number"] == 1
        assert results[0]["target_number"] == 10
        assert results[0]["success"] is True
        assert results[0]["error"] is None


class TestMigrateAssignee:
    """assignee が移行される"""

    def test_assignee_is_passed(self):
        src_adapter = MagicMock()
        dst_adapter = MagicMock()

        src_issue = _make_issue(number=1, assignees=["alice", "bob"])
        created_issue = _make_issue(number=10)
        src_adapter.get_issue.return_value = src_issue
        dst_adapter.create_issue.return_value = created_issue
        src_adapter.list_comments.return_value = []

        _migrate_one_issue(src_adapter, dst_adapter, 1, set(), "github:src-owner/src-repo")

        call_kwargs = dst_adapter.create_issue.call_args
        assert call_kwargs.kwargs.get("assignee") == "alice"

    def test_no_assignee_when_empty(self):
        src_adapter = MagicMock()
        dst_adapter = MagicMock()

        src_issue = _make_issue(number=1, assignees=[])
        created_issue = _make_issue(number=10)
        src_adapter.get_issue.return_value = src_issue
        dst_adapter.create_issue.return_value = created_issue
        src_adapter.list_comments.return_value = []

        _migrate_one_issue(src_adapter, dst_adapter, 1, set(), "github:src-owner/src-repo")

        call_kwargs = dst_adapter.create_issue.call_args
        assert call_kwargs.kwargs.get("assignee") is None


class TestMigrateLabels:
    """label が available_labels に含まれる場合のみ渡される"""

    def test_label_passed_when_available(self):
        src_adapter = MagicMock()
        dst_adapter = MagicMock()

        src_issue = _make_issue(number=1, labels=["bug", "feature"])
        created_issue = _make_issue(number=10)
        src_adapter.get_issue.return_value = src_issue
        dst_adapter.create_issue.return_value = created_issue
        src_adapter.list_comments.return_value = []

        available = {"bug", "enhancement"}
        _migrate_one_issue(src_adapter, dst_adapter, 1, available, "github:src-owner/src-repo")

        call_kwargs = dst_adapter.create_issue.call_args
        assert call_kwargs.kwargs.get("label") == "bug"

    def test_label_none_when_not_available(self):
        src_adapter = MagicMock()
        dst_adapter = MagicMock()

        src_issue = _make_issue(number=1, labels=["wontfix"])
        created_issue = _make_issue(number=10)
        src_adapter.get_issue.return_value = src_issue
        dst_adapter.create_issue.return_value = created_issue
        src_adapter.list_comments.return_value = []

        available = {"bug", "feature"}
        _migrate_one_issue(src_adapter, dst_adapter, 1, available, "github:src-owner/src-repo")

        call_kwargs = dst_adapter.create_issue.call_args
        assert call_kwargs.kwargs.get("label") is None
