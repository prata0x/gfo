"""gfo wiki サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.commands import get_adapter
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo wiki list のハンドラ。"""
    adapter = get_adapter()
    pages = adapter.list_wiki_pages(limit=args.limit)
    output(pages, fmt=fmt, fields=["id", "title", "updated_at"], jq=jq)


def handle_view(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo wiki view <id> のハンドラ。"""
    adapter = get_adapter()
    page = adapter.get_wiki_page(args.id)
    output(page, fmt=fmt, jq=jq)


def handle_create(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo wiki create --title TEXT --content TEXT のハンドラ。"""
    adapter = get_adapter()
    page = adapter.create_wiki_page(title=args.title, content=args.content)
    output(page, fmt=fmt, jq=jq)


def handle_update(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo wiki update <id> のハンドラ。"""
    adapter = get_adapter()
    page = adapter.update_wiki_page(args.id, title=args.title, content=args.content)
    output(page, fmt=fmt, jq=jq)


def handle_delete(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo wiki delete <id> のハンドラ。"""
    adapter = get_adapter()
    adapter.delete_wiki_page(args.id)
