"""gfo.commands.ci のテスト。"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from gfo.adapter.base import Artifact, Pipeline, Workflow
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

SAMPLE_WORKFLOW = Workflow(
    id=1,
    name="CI",
    path=".github/workflows/ci.yml",
    state="active",
)

SAMPLE_ARTIFACT = Artifact(
    id=11,
    name="build-output",
    size=1024,
    url="https://example.com/artifacts/11",
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

    def test_cancel_prints_success_message(self, capsys):
        """handle_cancel が成功メッセージに id を含む。"""
        with patch_adapter("gfo.commands.ci"):
            args = make_args(id="456")
            ci_cmd.handle_cancel(args, fmt="table")
        out = capsys.readouterr().out
        assert "456" in out


class TestHandleDelete:
    def test_calls_delete_pipeline_run(self):
        with patch_adapter("gfo.commands.ci") as adapter:
            args = make_args(id="456")
            ci_cmd.handle_delete(args, fmt="table")
        adapter.delete_pipeline_run.assert_called_once_with("456")

    def test_prints_message(self, capsys):
        with patch_adapter("gfo.commands.ci"):
            args = make_args(id="789")
            ci_cmd.handle_delete(args, fmt="table")
        out = capsys.readouterr().out
        assert "789" in out

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.ci") as adapter:
            adapter.delete_pipeline_run.side_effect = GfoError("delete failed")
            args = make_args(id="123")
            with pytest.raises(GfoError, match="delete failed"):
                ci_cmd.handle_delete(args, fmt="table")


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


class TestHandleWatch:
    def test_watch_immediate_success(self, capsys):
        with patch_adapter("gfo.commands.ci") as adapter:
            adapter.get_pipeline.return_value = SAMPLE_PIPELINE
            args = make_args(id="123", interval=1)
            ci_cmd.handle_watch(args, fmt="json")
        adapter.get_pipeline.assert_called_once_with("123")
        out = capsys.readouterr().out
        assert '"status"' in out

    def test_watch_polls_until_done(self, capsys):
        running_pipeline = Pipeline(
            id=123,
            status="running",
            ref="main",
            url="https://example.com/ci/123",
            created_at="2024-01-01T00:00:00Z",
        )
        with patch_adapter("gfo.commands.ci") as adapter:
            adapter.get_pipeline.side_effect = [running_pipeline, SAMPLE_PIPELINE]
            args = make_args(id="123", interval=0)
            with patch("time.sleep") as mock_sleep:
                ci_cmd.handle_watch(args, fmt="table")
        mock_sleep.assert_called()
        assert adapter.get_pipeline.call_count == 2

    def test_watch_failure(self, capsys):
        failed_pipeline = Pipeline(
            id=123,
            status="failure",
            ref="main",
            url="https://example.com/ci/123",
            created_at="2024-01-01T00:00:00Z",
        )
        with patch_adapter("gfo.commands.ci") as adapter:
            adapter.get_pipeline.return_value = failed_pipeline
            args = make_args(id="123", interval=1)
            ci_cmd.handle_watch(args, fmt="json")
        out = capsys.readouterr().out
        assert '"failure"' in out

    def test_watch_timeout(self, capsys):
        running_pipeline = Pipeline(
            id=123,
            status="running",
            ref="main",
            url="https://example.com/ci/123",
            created_at="2024-01-01T00:00:00Z",
        )
        with patch_adapter("gfo.commands.ci") as adapter:
            adapter.get_pipeline.return_value = running_pipeline
            args = make_args(id="123", interval=0, timeout=1)
            with patch("time.sleep"), patch("time.monotonic", side_effect=[0, 0, 2]):
                ci_cmd.handle_watch(args, fmt="table")
        out = capsys.readouterr().out
        assert "Timed out" in out

    def test_watch_error_propagation(self):
        with patch_adapter("gfo.commands.ci") as adapter:
            adapter.get_pipeline.side_effect = GfoError("watch failed")
            args = make_args(id="123", interval=1)
            with pytest.raises(GfoError, match="watch failed"):
                ci_cmd.handle_watch(args, fmt="table")


class TestHandleDownload:
    def test_calls_download_run_logs(self, capsys):
        with patch_adapter("gfo.commands.ci") as adapter:
            adapter.download_run_logs.return_value = "/tmp/logs-123.zip"
            args = make_args(id="123", job=None, dir=".")
            ci_cmd.handle_download(args, fmt="table")
        adapter.download_run_logs.assert_called_once_with("123", job_id=None, output_dir=".")
        out = capsys.readouterr().out
        assert "logs-123.zip" in out

    def test_with_job_id(self, capsys):
        with patch_adapter("gfo.commands.ci") as adapter:
            adapter.download_run_logs.return_value = "/tmp/logs-123-job-42.txt"
            args = make_args(id="123", job="42", dir="/tmp")
            ci_cmd.handle_download(args, fmt="table")
        adapter.download_run_logs.assert_called_once_with("123", job_id="42", output_dir="/tmp")

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.ci") as adapter:
            adapter.download_run_logs.side_effect = GfoError("download failed")
            args = make_args(id="123", job=None, dir=".")
            with pytest.raises(GfoError, match="download failed"):
                ci_cmd.handle_download(args, fmt="table")


class TestHandleWorkflow:
    def test_list(self, capsys):
        with patch_adapter("gfo.commands.ci") as adapter:
            adapter.list_workflows.return_value = [SAMPLE_WORKFLOW]
            args = make_args(workflow_action="list", limit=30)
            ci_cmd.handle_workflow(args, fmt="table")
        adapter.list_workflows.assert_called_once_with(limit=30)
        out = capsys.readouterr().out
        assert "CI" in out

    def test_list_json(self, capsys):
        with patch_adapter("gfo.commands.ci") as adapter:
            adapter.list_workflows.return_value = [SAMPLE_WORKFLOW]
            args = make_args(workflow_action="list", limit=30)
            ci_cmd.handle_workflow(args, fmt="json")
        out = capsys.readouterr().out
        assert '"name"' in out

    def test_enable(self):
        with patch_adapter("gfo.commands.ci") as adapter:
            args = make_args(workflow_action="enable", id="1")
            ci_cmd.handle_workflow(args, fmt="table")
        adapter.enable_workflow.assert_called_once_with("1")

    def test_disable(self):
        with patch_adapter("gfo.commands.ci") as adapter:
            args = make_args(workflow_action="disable", id="1")
            ci_cmd.handle_workflow(args, fmt="table")
        adapter.disable_workflow.assert_called_once_with("1")

    def test_enable_prints_message(self, capsys):
        with patch_adapter("gfo.commands.ci"):
            args = make_args(workflow_action="enable", id="42")
            ci_cmd.handle_workflow(args, fmt="table")
        out = capsys.readouterr().out
        assert "42" in out

    def test_disable_prints_message(self, capsys):
        with patch_adapter("gfo.commands.ci"):
            args = make_args(workflow_action="disable", id="42")
            ci_cmd.handle_workflow(args, fmt="table")
        out = capsys.readouterr().out
        assert "42" in out

    def test_no_action(self):
        with patch_adapter("gfo.commands.ci"):
            args = make_args(workflow_action=None)
            with pytest.raises(ConfigError):
                ci_cmd.handle_workflow(args, fmt="table")

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.ci") as adapter:
            adapter.list_workflows.side_effect = GfoError("workflow failed")
            args = make_args(workflow_action="list", limit=30)
            with pytest.raises(GfoError, match="workflow failed"):
                ci_cmd.handle_workflow(args, fmt="table")


class TestHandleArtifact:
    def test_list(self, capsys):
        with patch_adapter("gfo.commands.ci") as adapter:
            adapter.list_artifacts.return_value = [SAMPLE_ARTIFACT]
            args = make_args(artifact_action="list", run_id="300", limit=30)
            ci_cmd.handle_artifact(args, fmt="table")
        adapter.list_artifacts.assert_called_once_with("300", limit=30)
        out = capsys.readouterr().out
        assert "build-output" in out

    def test_list_json(self, capsys):
        with patch_adapter("gfo.commands.ci") as adapter:
            adapter.list_artifacts.return_value = [SAMPLE_ARTIFACT]
            args = make_args(artifact_action="list", run_id="300", limit=30)
            ci_cmd.handle_artifact(args, fmt="json")
        out = capsys.readouterr().out
        assert '"name"' in out

    def test_download(self, capsys):
        with patch_adapter("gfo.commands.ci") as adapter:
            adapter.download_artifact.return_value = "/tmp/build-output.zip"
            args = make_args(artifact_action="download", run_id="300", artifact_id="11", dir=".")
            ci_cmd.handle_artifact(args, fmt="table")
        adapter.download_artifact.assert_called_once_with("300", "11", output_dir=".")
        out = capsys.readouterr().out
        assert "build-output.zip" in out

    def test_no_action(self):
        with patch_adapter("gfo.commands.ci"):
            args = make_args(artifact_action=None)
            with pytest.raises(ConfigError):
                ci_cmd.handle_artifact(args, fmt="table")

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.ci") as adapter:
            adapter.list_artifacts.side_effect = GfoError("artifact failed")
            args = make_args(artifact_action="list", run_id="300", limit=30)
            with pytest.raises(GfoError, match="artifact failed"):
                ci_cmd.handle_artifact(args, fmt="table")
