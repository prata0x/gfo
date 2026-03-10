"""gfo.commands.pr handle_update のテスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from gfo.commands import pr as pr_cmd
from tests.test_commands.conftest import make_args


def _patch(adapter):
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        with patch("gfo.commands.pr.get_adapter", return_value=adapter):
            yield

    return _ctx()


class TestHandleUpdate:
    def test_calls_update_with_all_fields(self, sample_pr):
        adapter = MagicMock()
        adapter.update_pull_request.return_value = sample_pr
        args = make_args(number=1, title="New title", body="New body", base="develop")
        with _patch(adapter):
            pr_cmd.handle_update(args, fmt="table")
        adapter.update_pull_request.assert_called_once_with(
            1, title="New title", body="New body", base="develop"
        )

    def test_calls_update_with_none_fields(self, sample_pr):
        adapter = MagicMock()
        adapter.update_pull_request.return_value = sample_pr
        args = make_args(number=2, title=None, body=None, base=None)
        with _patch(adapter):
            pr_cmd.handle_update(args, fmt="table")
        adapter.update_pull_request.assert_called_once_with(2, title=None, body=None, base=None)
