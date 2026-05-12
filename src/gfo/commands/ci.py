"""gfo ci サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.commands import get_adapter
from gfo.exceptions import ConfigError
from gfo.i18n import _
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo ci list のハンドラ。"""
    adapter = get_adapter()
    pipelines = adapter.list_pipelines(ref=args.ref, limit=args.limit)
    output(pipelines, fmt=fmt, fields=["id", "status", "ref", "created_at"], jq=jq)


def handle_view(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo ci view <id> のハンドラ。"""
    adapter = get_adapter()
    pipeline = adapter.get_pipeline(args.id)
    output(pipeline, fmt=fmt, jq=jq)


def handle_cancel(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo ci cancel <id> のハンドラ。"""
    adapter = get_adapter()
    adapter.cancel_pipeline(args.id)
    print(_("Canceled pipeline run '{id}'.").format(id=args.id))


def handle_delete(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo ci delete <id> のハンドラ。"""
    adapter = get_adapter()
    adapter.delete_pipeline_run(args.id)
    print(_("Deleted pipeline run '{id}'.").format(id=args.id))


def handle_trigger(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo ci trigger --ref REF のハンドラ。"""
    adapter = get_adapter()
    inputs_dict = None
    if getattr(args, "input", None):
        inputs_dict = {}
        for item in args.input:
            if "=" not in item:
                raise ConfigError(
                    _("Invalid input format: '{item}'. Expected KEY=VALUE.").format(item=item)
                )
            k, v = item.split("=", 1)
            inputs_dict[k] = v
    pipeline = adapter.trigger_pipeline(
        args.ref, workflow=getattr(args, "workflow", None), inputs=inputs_dict
    )
    output(pipeline, fmt=fmt, jq=jq)


def handle_retry(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo ci retry <id> のハンドラ。"""
    adapter = get_adapter()
    pipeline = adapter.retry_pipeline(args.id)
    output(pipeline, fmt=fmt, jq=jq)


def handle_logs(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo ci logs <id> のハンドラ。"""
    adapter = get_adapter()
    for line in adapter.get_pipeline_logs(args.id, job_id=getattr(args, "job", None)):
        print(line)


def handle_watch(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo ci watch <id> のハンドラ。"""
    import sys
    import time

    adapter = get_adapter()
    timeout = getattr(args, "timeout", 1800)
    terminal_statuses = {"success", "failure", "cancelled"}
    start = time.monotonic()
    while True:
        pipeline = adapter.get_pipeline(args.id)
        sys.stderr.write(f"\r{pipeline.status}")
        sys.stderr.flush()
        if pipeline.status in terminal_statuses:
            sys.stderr.write("\n")
            break
        if timeout > 0 and (time.monotonic() - start) >= timeout:
            sys.stderr.write("\n")
            print(_("Timed out after {timeout} seconds.").format(timeout=timeout))
            break
        time.sleep(args.interval)
    output(pipeline, fmt=fmt, jq=jq)


def handle_download(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo ci download <id> のハンドラ。"""
    adapter = get_adapter()
    output_dir = getattr(args, "dir", ".") or "."
    path = adapter.download_run_logs(
        args.id, job_id=getattr(args, "job", None), output_dir=output_dir
    )
    print(_("Downloaded: {path}").format(path=path))


def handle_workflow(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo ci workflow のハンドラ。"""
    action = getattr(args, "workflow_action", None)
    if action == "list":
        _handle_workflow_list(args, fmt=fmt, jq=jq)
    elif action == "enable":
        _handle_workflow_enable(args)
    elif action == "disable":
        _handle_workflow_disable(args)
    else:
        raise ConfigError(_("Specify a subcommand: list, enable, disable"))


def _handle_workflow_list(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    adapter = get_adapter()
    workflows = adapter.list_workflows(limit=args.limit)
    output(workflows, fmt=fmt, fields=["id", "name", "path", "state"], jq=jq)


def _handle_workflow_enable(args: argparse.Namespace) -> None:
    adapter = get_adapter()
    adapter.enable_workflow(args.id)
    print(_("Enabled workflow '{id}'.").format(id=args.id))


def _handle_workflow_disable(args: argparse.Namespace) -> None:
    adapter = get_adapter()
    adapter.disable_workflow(args.id)
    print(_("Disabled workflow '{id}'.").format(id=args.id))


def handle_artifact(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo ci artifact のハンドラ。"""
    action = getattr(args, "artifact_action", None)
    if action == "list":
        _handle_artifact_list(args, fmt=fmt, jq=jq)
    elif action == "download":
        _handle_artifact_download(args)
    else:
        raise ConfigError(_("Specify a subcommand: list, download"))


def _handle_artifact_list(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    adapter = get_adapter()
    artifacts = adapter.list_artifacts(args.run_id, limit=args.limit)
    output(artifacts, fmt=fmt, fields=["id", "name", "size", "created_at"], jq=jq)


def _handle_artifact_download(args: argparse.Namespace) -> None:
    adapter = get_adapter()
    output_dir = getattr(args, "dir", ".") or "."
    path = adapter.download_artifact(args.run_id, args.artifact_id, output_dir=output_dir)
    print(_("Downloaded: {path}").format(path=path))
