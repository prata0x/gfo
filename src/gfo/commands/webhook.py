"""gfo webhook サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.commands import get_adapter
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo webhook list のハンドラ。"""
    adapter = get_adapter()
    webhooks = adapter.list_webhooks(limit=args.limit)
    output(webhooks, fmt=fmt, fields=["id", "url", "events", "active"])


def handle_create(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo webhook create --url URL --event EVENT のハンドラ。"""
    adapter = get_adapter()
    webhook = adapter.create_webhook(url=args.url, events=args.event, secret=args.secret)
    output(webhook, fmt=fmt)


def handle_delete(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo webhook delete <id> のハンドラ。"""
    adapter = get_adapter()
    adapter.delete_webhook(hook_id=args.id)
