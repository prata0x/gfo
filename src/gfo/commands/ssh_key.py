"""gfo ssh-key サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.commands import get_adapter
from gfo.i18n import _
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo ssh-key list のハンドラ。"""
    adapter = get_adapter()
    keys = adapter.list_ssh_keys(limit=args.limit)
    output(keys, fmt=fmt, fields=["id", "title", "created_at"], jq=jq)


def handle_create(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo ssh-key create --title TITLE --key KEY のハンドラ。"""
    adapter = get_adapter()
    key = adapter.create_ssh_key(title=args.title, key=args.key)
    output(key, fmt=fmt, jq=jq)


def handle_delete(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo ssh-key delete <id> のハンドラ。"""
    adapter = get_adapter()
    adapter.delete_ssh_key(key_id=args.id)
    print(_("Deleted SSH key '{id}'.").format(id=args.id))
