"""gfo ci サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.commands import get_adapter
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
