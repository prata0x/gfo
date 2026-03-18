"""gfo ci サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.commands import get_adapter
from gfo.exceptions import ConfigError
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


def handle_trigger(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo ci trigger --ref REF のハンドラ。"""
    adapter = get_adapter()
    inputs_dict = None
    if getattr(args, "input", None):
        inputs_dict = {}
        for item in args.input:
            if "=" not in item:
                raise ConfigError(f"Invalid input format: '{item}'. Expected KEY=VALUE.")
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
    logs = adapter.get_pipeline_logs(args.id, job_id=getattr(args, "job", None))
    print(logs)
