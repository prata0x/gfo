"""gfo tag サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.commands import confirm_action, get_adapter
from gfo.i18n import _
from gfo.output import output, output_result


def handle_view(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo tag view <name> のハンドラ。"""
    adapter = get_adapter()
    tag = adapter.get_tag(args.name)
    output(tag, fmt=fmt, jq=jq)


def handle_list(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo tag list のハンドラ。"""
    adapter = get_adapter()
    tags = adapter.list_tags(limit=args.limit)
    output(tags, fmt=fmt, fields=["name", "sha", "message"], jq=jq)


def handle_create(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo tag create <name> --ref <sha-or-branch> のハンドラ。"""
    adapter = get_adapter()
    tag = adapter.create_tag(name=args.name, ref=args.ref, message=args.message or "")
    output(tag, fmt=fmt, jq=jq)


def handle_delete(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo tag delete <name> のハンドラ。"""
    adapter = get_adapter()
    if not confirm_action(
        args,
        _("Are you sure you want to delete tag '{name}'? [y/N]: ").format(name=args.name),
        fmt=fmt,
        jq=jq,
    ):
        return
    adapter.delete_tag(name=args.name)
    output_result(
        _("Deleted tag '{name}'.").format(name=args.name),
        result="deleted",
        fmt=fmt,
        jq=jq,
        tag=args.name,
    )
