"""gfo deploy-key サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.commands import get_adapter
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo deploy-key list のハンドラ。"""
    adapter = get_adapter()
    keys = adapter.list_deploy_keys(limit=args.limit)
    output(keys, fmt=fmt, fields=["id", "title", "read_only"])


def handle_create(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo deploy-key create --title TEXT --key TEXT のハンドラ。"""
    adapter = get_adapter()
    key = adapter.create_deploy_key(
        title=args.title,
        key=args.key,
        read_only=not args.read_write,
    )
    output(key, fmt=fmt)


def handle_delete(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo deploy-key delete <id> のハンドラ。"""
    adapter = get_adapter()
    adapter.delete_deploy_key(key_id=args.id)
