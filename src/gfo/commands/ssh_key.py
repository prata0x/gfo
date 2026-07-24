"""gfo ssh-key サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.commands import confirm_action, get_adapter
from gfo.i18n import _
from gfo.output import output, output_result


def handle_view(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo ssh-key view <id> のハンドラ。"""
    adapter = get_adapter(require_repo=False)
    key = adapter.get_ssh_key(args.id)
    output(key, fmt=fmt, jq=jq)


def handle_list(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo ssh-key list のハンドラ。"""
    adapter = get_adapter(require_repo=False)
    keys = adapter.list_ssh_keys(limit=args.limit)
    output(keys, fmt=fmt, fields=["id", "title", "created_at"], jq=jq)


def handle_create(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo ssh-key create --title TITLE --key KEY のハンドラ。"""
    adapter = get_adapter(require_repo=False)
    key = adapter.create_ssh_key(title=args.title, key=args.key)
    output(key, fmt=fmt, jq=jq)


def handle_delete(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo ssh-key delete <id> のハンドラ。"""
    adapter = get_adapter(require_repo=False)
    if not confirm_action(
        args,
        _("Are you sure you want to delete SSH key '{id}'? [y/N]: ").format(id=args.id),
        fmt=fmt,
        jq=jq,
    ):
        return
    adapter.delete_ssh_key(key_id=args.id)
    output_result(
        _("Deleted SSH key '{id}'.").format(id=args.id),
        result="deleted",
        fmt=fmt,
        jq=jq,
        id=args.id,
    )
