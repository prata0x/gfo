"""gfo gpg-key サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.commands import get_adapter
from gfo.i18n import _
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo gpg-key list のハンドラ。"""
    adapter = get_adapter()
    keys = adapter.list_gpg_keys(limit=args.limit)
    output(keys, fmt=fmt, fields=["id", "primary_key_id", "emails", "created_at"], jq=jq)


def handle_create(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo gpg-key create --key KEY のハンドラ。"""
    adapter = get_adapter()
    key = adapter.create_gpg_key(armored_key=args.key)
    output(key, fmt=fmt, jq=jq)


def handle_delete(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo gpg-key delete <id> のハンドラ。"""
    adapter = get_adapter()
    adapter.delete_gpg_key(key_id=args.id)
    print(_("Deleted GPG key '{id}'.").format(id=args.id))
