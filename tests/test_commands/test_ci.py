"""gfo.commands.ci のテスト。"""

from __future__ import annotations

import pytest

from gfo.adapter.base import Pipeline
from gfo.commands import ci as ci_cmd
from gfo.exceptions import ConfigError, GfoError
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


class TestHandleTrigger:
    def test_calls_trigger_pipeline(self, capsys):
        with patch_adapter("gfo.commands.ci") as adapter:
            adapter.trigger_pipeline.return_value = SAMPLE_PIPELINE
            args = make_args(ref="main", workflow="ci.yml", input=None)
            ci_cmd.handle_trigger(args, fmt="table")
        adapter.trigger_pipeline.assert_called_once_with("main", workflow="ci.yml", inputs=None)

    def test_json_output(self, capsys):
        with patch_adapter("gfo.commands.ci") as adapter:
            adapter.trigger_pipeline.return_value = SAMPLE_PIPELINE
            args = make_args(ref="main", workflow="ci.yml", input=None)
            ci_cmd.handle_trigger(args, fmt="json")
        out = capsys.readouterr().out
        assert '"status"' in out

    def test_parses_inputs(self, capsys):
        with patch_adapter("gfo.commands.ci") as adapter:
            adapter.trigger_pipeline.return_value = SAMPLE_PIPELINE
            args = make_args(ref="main", workflow="ci.yml", input=["FOO=bar", "BAZ=qux=1"])
            ci_cmd.handle_trigger(args, fmt="table")
        adapter.trigger_pipeline.assert_called_once_with(
            "main", workflow="ci.yml", inputs={"FOO": "bar", "BAZ": "qux=1"}
        )

    def test_invalid_input_format(self):
        with patch_adapter("gfo.commands.ci"):
            args = make_args(ref="main", workflow="ci.yml", input=["INVALID"])
            with pytest.raises(ConfigError, match="Invalid input format"):
                ci_cmd.handle_trigger(args, fmt="table")

    def test_no_workflow(self, capsys):
        with patch_adapter("gfo.commands.ci") as adapter:
            adapter.trigger_pipeline.return_value = SAMPLE_PIPELINE
            args = make_args(ref="main", workflow=None, input=None)
            ci_cmd.handle_trigger(args, fmt="table")
        adapter.trigger_pipeline.assert_called_once_with("main", workflow=None, inputs=None)

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.ci") as adapter:
            adapter.trigger_pipeline.side_effect = GfoError("trigger failed")
            args = make_args(ref="main", workflow="ci.yml", input=None)
            with pytest.raises(GfoError, match="trigger failed"):
                ci_cmd.handle_trigger(args, fmt="table")


class TestHandleRetry:
    def test_calls_retry_pipeline(self, capsys):
        with patch_adapter("gfo.commands.ci") as adapter:
            adapter.retry_pipeline.return_value = SAMPLE_PIPELINE
            args = make_args(id="123")
            ci_cmd.handle_retry(args, fmt="table")
        adapter.retry_pipeline.assert_called_once_with("123")

    def test_json_output(self, capsys):
        with patch_adapter("gfo.commands.ci") as adapter:
            adapter.retry_pipeline.return_value = SAMPLE_PIPELINE
            args = make_args(id="123")
            ci_cmd.handle_retry(args, fmt="json")
        out = capsys.readouterr().out
        assert '"status"' in out

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.ci") as adapter:
            adapter.retry_pipeline.side_effect = GfoError("retry failed")
            args = make_args(id="123")
            with pytest.raises(GfoError, match="retry failed"):
                ci_cmd.handle_retry(args, fmt="table")


class TestHandleLogs:
    def test_calls_get_pipeline_logs(self, capsys):
        with patch_adapter("gfo.commands.ci") as adapter:
            adapter.get_pipeline_logs.return_value = "log output here"
            args = make_args(id="123", job=None)
            ci_cmd.handle_logs(args, fmt="table")
        adapter.get_pipeline_logs.assert_called_once_with("123", job_id=None)
        out = capsys.readouterr().out
        assert "log output here" in out

    def test_with_job_id(self, capsys):
        with patch_adapter("gfo.commands.ci") as adapter:
            adapter.get_pipeline_logs.return_value = "job log output"
            args = make_args(id="123", job="456")
            ci_cmd.handle_logs(args, fmt="table")
        adapter.get_pipeline_logs.assert_called_once_with("123", job_id="456")
        out = capsys.readouterr().out
        assert "job log output" in out

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.ci") as adapter:
            adapter.get_pipeline_logs.side_effect = GfoError("logs failed")
            args = make_args(id="123", job=None)
            with pytest.raises(GfoError, match="logs failed"):
                ci_cmd.handle_logs(args, fmt="table")
