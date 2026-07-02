"""gfo deploy-key サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.commands import confirm_action, get_adapter
from gfo.i18n import _
from gfo.output import output, output_result


def handle_view(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo deploy-key view <id> のハンドラ。"""
    adapter = get_adapter()
    key = adapter.get_deploy_key(args.id)
    output(key, fmt=fmt, jq=jq)


def handle_list(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo deploy-key list のハンドラ。"""
    adapter = get_adapter()
    keys = adapter.list_deploy_keys(limit=args.limit)
    output(keys, fmt=fmt, fields=["id", "title", "read_only"], jq=jq)


def handle_create(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo deploy-key create --title TEXT --key TEXT のハンドラ。"""
    adapter = get_adapter()
    key = adapter.create_deploy_key(
        title=args.title,
        key=args.key,
        read_only=not args.read_write,
    )
    output(key, fmt=fmt, jq=jq)


def handle_delete(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo deploy-key delete <id> のハンドラ。"""
    adapter = get_adapter()
    if not confirm_action(
        args,
        _("Are you sure you want to delete deploy key '{id}'? [y/N]: ").format(id=args.id),
        fmt=fmt,
        jq=jq,
    ):
        return
    adapter.delete_deploy_key(key_id=args.id)
    output_result(
        _("Deleted deploy key '{id}'.").format(id=args.id),
        result="deleted",
        fmt=fmt,
        jq=jq,
        id=args.id,
    )
