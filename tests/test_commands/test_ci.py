"""gfo.commands.ci のテスト。"""

from __future__ import annotations

from gfo.adapter.base import Pipeline
from gfo.commands import ci as ci_cmd
from tests.test_commands.conftest import make_args, patch_adapter

SAMPLE_PIPELINE = Pipeline(
    id=123,
    status="success",
    ref="main",
    url="https://example.com/ci/123",
    created_at="2024-01-01T00:00:00Z",
)


class TestHandleList:
    def test_calls_list_pipelines(self, capsys):
        with patch_adapter("gfo.commands.ci") as adapter:
            adapter.list_pipelines.return_value = [SAMPLE_PIPELINE]
            args = make_args(ref=None, limit=30)
            ci_cmd.handle_list(args, fmt="table")
        adapter.list_pipelines.assert_called_once_with(ref=None, limit=30)

    def test_outputs_results(self, capsys):
        with patch_adapter("gfo.commands.ci") as adapter:
            adapter.list_pipelines.return_value = [SAMPLE_PIPELINE]
            args = make_args(ref="main", limit=10)
            ci_cmd.handle_list(args, fmt="table")
        out = capsys.readouterr().out
        assert "success" in out


class TestHandleView:
    def test_calls_get_pipeline(self, capsys):
        with patch_adapter("gfo.commands.ci") as adapter:
            adapter.get_pipeline.return_value = SAMPLE_PIPELINE
            args = make_args(id="123")
            ci_cmd.handle_view(args, fmt="table")
        adapter.get_pipeline.assert_called_once_with("123")


class TestHandleCancel:
    def test_calls_cancel_pipeline(self):
        with patch_adapter("gfo.commands.ci") as adapter:
            args = make_args(id="456")
            ci_cmd.handle_cancel(args, fmt="table")
        adapter.cancel_pipeline.assert_called_once_with("456")
