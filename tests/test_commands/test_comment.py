"""gfo.commands.comment のテスト。"""

from __future__ import annotations

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


class TestHandleList:
    def test_calls_list_comments(self, capsys):
        with patch_adapter("gfo.commands.comment") as adapter:
            adapter.list_comments.return_value = [SAMPLE_COMMENT]
            args = make_args(resource="issue", number=1, limit=30)
            comment_cmd.handle_list(args, fmt="table")
        adapter.list_comments.assert_called_once_with("issue", 1, limit=30)

    def test_outputs_results(self, capsys):
        with patch_adapter("gfo.commands.comment") as adapter:
            adapter.list_comments.return_value = [SAMPLE_COMMENT]
            args = make_args(resource="pr", number=2, limit=10)
            comment_cmd.handle_list(args, fmt="table")
        out = capsys.readouterr().out
        assert "Test comment" in out


class TestHandleCreate:
    def test_calls_create_comment(self):
        with patch_adapter("gfo.commands.comment") as adapter:
            adapter.create_comment.return_value = SAMPLE_COMMENT
            args = make_args(resource="issue", number=1, body="Hello")
            comment_cmd.handle_create(args, fmt="table")
        adapter.create_comment.assert_called_once_with("issue", 1, body="Hello")


class TestHandleUpdate:
    def test_calls_update_comment(self):
        with patch_adapter("gfo.commands.comment") as adapter:
            adapter.update_comment.return_value = SAMPLE_COMMENT
            args = make_args(comment_id=42, body="Updated", on="pr")
            comment_cmd.handle_update(args, fmt="table")
        adapter.update_comment.assert_called_once_with("pr", 42, body="Updated")


class TestHandleDelete:
    def test_calls_delete_comment(self):
        with patch_adapter("gfo.commands.comment") as adapter:
            args = make_args(comment_id=42, on="issue")
            comment_cmd.handle_delete(args, fmt="table")
        adapter.delete_comment.assert_called_once_with("issue", 42)
