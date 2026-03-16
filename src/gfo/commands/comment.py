"""gfo comment サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.commands import get_adapter
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo comment list <pr|issue> <number> のハンドラ。"""
    adapter = get_adapter()
    comments = adapter.list_comments(args.resource, args.number, limit=args.limit)
    output(comments, fmt=fmt, fields=["id", "author", "body", "created_at"], jq=jq)


def handle_create(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo comment create <pr|issue> <number> --body TEXT のハンドラ。"""
    adapter = get_adapter()
    comment = adapter.create_comment(args.resource, args.number, body=args.body)
    output(comment, fmt=fmt, jq=jq)


def handle_update(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo comment update <comment-id> --body TEXT --on <pr|issue> のハンドラ。"""
    adapter = get_adapter()
    comment = adapter.update_comment(args.on, args.comment_id, body=args.body)
    output(comment, fmt=fmt, jq=jq)


def handle_delete(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo comment delete <comment-id> --on <pr|issue> のハンドラ。"""
    adapter = get_adapter()
    adapter.delete_comment(args.on, args.comment_id)
