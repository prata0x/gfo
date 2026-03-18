"""gfo.commands.comment のテスト。"""

from __future__ import annotations

import pytest

from gfo.adapter.base import Comment
from gfo.commands import comment as comment_cmd
from tests.test_commands.conftest import make_args, patch_adapter

SAMPLE_COMMENT = Comment(
    id=1,
    body="Test comment",
    author="test-user",
    url="https://example.com/comment/1",
    created_at="2024-01-01T00:00:00Z",
)


class TestHandlePrComment:
    def test_list_calls_list_comments(self, capsys):
        with patch_adapter("gfo.commands.comment") as adapter:
            adapter.list_comments.return_value = [SAMPLE_COMMENT]
            args = make_args(comment_action="list", number=1, limit=30)
            comment_cmd.handle_pr_comment(args, fmt="table")
        adapter.list_comments.assert_called_once_with("pr", 1, limit=30)

    def test_list_outputs_results(self, capsys):
        with patch_adapter("gfo.commands.comment") as adapter:
            adapter.list_comments.return_value = [SAMPLE_COMMENT]
            args = make_args(comment_action="list", number=2, limit=10)
            comment_cmd.handle_pr_comment(args, fmt="table")
        out = capsys.readouterr().out
        assert "Test comment" in out

    def test_list_json(self, capsys):
        with patch_adapter("gfo.commands.comment") as adapter:
            adapter.list_comments.return_value = [SAMPLE_COMMENT]
            args = make_args(comment_action="list", number=1, limit=30)
            comment_cmd.handle_pr_comment(args, fmt="json")
        out = capsys.readouterr().out
        assert '"body": "Test comment"' in out

    def test_create_calls_create_comment(self):
        with patch_adapter("gfo.commands.comment") as adapter:
            adapter.create_comment.return_value = SAMPLE_COMMENT
            args = make_args(comment_action="create", number=1, body="Hello")
            comment_cmd.handle_pr_comment(args, fmt="table")
        adapter.create_comment.assert_called_once_with("pr", 1, body="Hello")

    def test_edit_calls_update_comment(self):
        with patch_adapter("gfo.commands.comment") as adapter:
            adapter.update_comment.return_value = SAMPLE_COMMENT
            args = make_args(comment_action="edit", comment_id=42, body="Updated")
            comment_cmd.handle_pr_comment(args, fmt="table")
        adapter.update_comment.assert_called_once_with("pr", 42, body="Updated")

    def test_delete_calls_delete_comment(self):
        with patch_adapter("gfo.commands.comment") as adapter:
            args = make_args(comment_action="delete", comment_id=42)
            comment_cmd.handle_pr_comment(args, fmt="table")
        adapter.delete_comment.assert_called_once_with("pr", 42)

    def test_no_action_raises(self):
        with patch_adapter("gfo.commands.comment"):
            args = make_args(comment_action=None)
            with pytest.raises(SystemExit):
                comment_cmd.handle_pr_comment(args, fmt="table")


class TestHandleIssueComment:
    def test_list_calls_list_comments(self, capsys):
        with patch_adapter("gfo.commands.comment") as adapter:
            adapter.list_comments.return_value = [SAMPLE_COMMENT]
            args = make_args(comment_action="list", number=5, limit=30)
            comment_cmd.handle_issue_comment(args, fmt="table")
        adapter.list_comments.assert_called_once_with("issue", 5, limit=30)

    def test_list_json(self, capsys):
        with patch_adapter("gfo.commands.comment") as adapter:
            adapter.list_comments.return_value = [SAMPLE_COMMENT]
            args = make_args(comment_action="list", number=1, limit=30)
            comment_cmd.handle_issue_comment(args, fmt="json")
        out = capsys.readouterr().out
        assert '"body": "Test comment"' in out

    def test_create_calls_create_comment(self):
        with patch_adapter("gfo.commands.comment") as adapter:
            adapter.create_comment.return_value = SAMPLE_COMMENT
            args = make_args(comment_action="create", number=3, body="Hi")
            comment_cmd.handle_issue_comment(args, fmt="table")
        adapter.create_comment.assert_called_once_with("issue", 3, body="Hi")

    def test_edit_calls_update_comment(self):
        with patch_adapter("gfo.commands.comment") as adapter:
            adapter.update_comment.return_value = SAMPLE_COMMENT
            args = make_args(comment_action="edit", comment_id=10, body="Fixed")
            comment_cmd.handle_issue_comment(args, fmt="table")
        adapter.update_comment.assert_called_once_with("issue", 10, body="Fixed")

    def test_delete_calls_delete_comment(self):
        with patch_adapter("gfo.commands.comment") as adapter:
            args = make_args(comment_action="delete", comment_id=10)
            comment_cmd.handle_issue_comment(args, fmt="table")
        adapter.delete_comment.assert_called_once_with("issue", 10)

    def test_no_action_raises(self):
        with patch_adapter("gfo.commands.comment"):
            args = make_args(comment_action=None)
            with pytest.raises(SystemExit):
                comment_cmd.handle_issue_comment(args, fmt="table")
