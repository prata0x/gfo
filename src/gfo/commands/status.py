"""gfo status サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.commands import get_adapter
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo status list <ref> のハンドラ。"""
    adapter = get_adapter()
    statuses = adapter.list_commit_statuses(args.ref, limit=args.limit)
    output(statuses, fmt=fmt, fields=["state", "context", "description", "created_at"])


def handle_create(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo status create <ref> --state STATE のハンドラ。"""
    adapter = get_adapter()
    status = adapter.create_commit_status(
        args.ref,
        state=args.state,
        context=args.context or "",
        description=args.description or "",
        target_url=args.url or "",
    )
    output(status, fmt=fmt)
