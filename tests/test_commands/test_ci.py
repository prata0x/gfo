"""gfo.commands.ci のテスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from gfo.adapter.base import Pipeline
from gfo.commands import ci as ci_cmd
from tests.test_commands.conftest import make_args

SAMPLE_PIPELINE = Pipeline(
    id=123,
    status="success",
    ref="main",
    url="https://example.com/ci/123",
    created_at="2024-01-01T00:00:00Z",
)


def _patch(adapter):
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        with patch("gfo.commands.ci.get_adapter", return_value=adapter):
            yield

    return _ctx()


class TestHandleList:
    def test_calls_list_pipelines(self, capsys):
        adapter = MagicMock()
        adapter.list_pipelines.return_value = [SAMPLE_PIPELINE]
        args = make_args(ref=None, limit=30)
        with _patch(adapter):
            ci_cmd.handle_list(args, fmt="table")
        adapter.list_pipelines.assert_called_once_with(ref=None, limit=30)

    def test_outputs_results(self, capsys):
        adapter = MagicMock()
        adapter.list_pipelines.return_value = [SAMPLE_PIPELINE]
        args = make_args(ref="main", limit=10)
        with _patch(adapter):
            ci_cmd.handle_list(args, fmt="table")
        out = capsys.readouterr().out
        assert "success" in out


class TestHandleView:
    def test_calls_get_pipeline(self, capsys):
        adapter = MagicMock()
        adapter.get_pipeline.return_value = SAMPLE_PIPELINE
        args = make_args(id="123")
        with _patch(adapter):
            ci_cmd.handle_view(args, fmt="table")
        adapter.get_pipeline.assert_called_once_with("123")


class TestHandleCancel:
    def test_calls_cancel_pipeline(self):
        adapter = MagicMock()
        args = make_args(id="456")
        with _patch(adapter):
            ci_cmd.handle_cancel(args, fmt="table")
        adapter.cancel_pipeline.assert_called_once_with("456")
