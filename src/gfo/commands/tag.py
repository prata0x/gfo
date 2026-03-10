"""gfo tag サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.commands import get_adapter
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo tag list のハンドラ。"""
    adapter = get_adapter()
    tags = adapter.list_tags(limit=args.limit)
    output(tags, fmt=fmt, fields=["name", "sha", "message"])


def handle_create(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo tag create <name> --ref <sha-or-branch> のハンドラ。"""
    adapter = get_adapter()
    tag = adapter.create_tag(name=args.name, ref=args.ref, message=args.message or "")
    output(tag, fmt=fmt)


def handle_delete(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo tag delete <name> のハンドラ。"""
    adapter = get_adapter()
    adapter.delete_tag(name=args.name)
