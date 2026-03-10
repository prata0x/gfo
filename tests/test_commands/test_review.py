"""gfo.commands.review のテスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gfo.adapter.base import Review
from gfo.commands import review as review_cmd
from gfo.exceptions import ConfigError
from tests.test_commands.conftest import make_args

SAMPLE_REVIEW = Review(
    id=1,
    state="approved",
    body="Looks good",
    author="reviewer",
    url="",
    submitted_at="2024-01-01T00:00:00Z",
)


def _patch(adapter):
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        with patch("gfo.commands.review.get_adapter", return_value=adapter):
            yield

    return _ctx()


class TestHandleList:
    def test_calls_list_reviews(self, capsys):
        adapter = MagicMock()
        adapter.list_reviews.return_value = [SAMPLE_REVIEW]
        args = make_args(number=1)
        with _patch(adapter):
            review_cmd.handle_list(args, fmt="table")
        adapter.list_reviews.assert_called_once_with(1)

    def test_outputs_results(self, capsys):
        adapter = MagicMock()
        adapter.list_reviews.return_value = [SAMPLE_REVIEW]
        args = make_args(number=1)
        with _patch(adapter):
            review_cmd.handle_list(args, fmt="table")
        out = capsys.readouterr().out
        assert "approved" in out


class TestHandleCreate:
    def test_approve(self):
        adapter = MagicMock()
        adapter.create_review.return_value = SAMPLE_REVIEW
        args = make_args(number=1, approve=True, request_changes=False, comment=False, body="")
        with _patch(adapter):
            review_cmd.handle_create(args, fmt="table")
        adapter.create_review.assert_called_once_with(1, state="APPROVE", body="")

    def test_request_changes(self):
        adapter = MagicMock()
        adapter.create_review.return_value = SAMPLE_REVIEW
        args = make_args(
            number=1, approve=False, request_changes=True, comment=False, body="needs work"
        )
        with _patch(adapter):
            review_cmd.handle_create(args, fmt="table")
        adapter.create_review.assert_called_once_with(1, state="REQUEST_CHANGES", body="needs work")

    def test_comment_without_body_raises(self):
        adapter = MagicMock()
        args = make_args(number=1, approve=False, request_changes=False, comment=True, body="")
        with _patch(adapter):
            with pytest.raises(ConfigError):
                review_cmd.handle_create(args, fmt="table")
