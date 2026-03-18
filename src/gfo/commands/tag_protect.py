"""gfo tag-protect サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.commands import get_adapter
from gfo.i18n import _
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo tag-protect list のハンドラ。"""
    adapter = get_adapter()
    protections = adapter.list_tag_protections(limit=args.limit)
    output(protections, fmt=fmt, fields=["id", "pattern", "create_access_level"], jq=jq)


def handle_create(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo tag-protect create <pattern> のハンドラ。"""
    adapter = get_adapter()
    protection = adapter.create_tag_protection(
        args.pattern, create_access_level=getattr(args, "access_level", None)
    )
    output(protection, fmt=fmt, jq=jq)


def handle_delete(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo tag-protect delete <id> のハンドラ。"""
    adapter = get_adapter()
    adapter.delete_tag_protection(args.id)
    print(_("Deleted tag protection '{id}'.").format(id=args.id))
