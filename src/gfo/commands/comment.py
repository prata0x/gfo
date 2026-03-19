"""gfo pr comment / gfo issue comment サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.commands import get_adapter
from gfo.exceptions import ConfigError
from gfo.i18n import _
from gfo.output import output


def _dispatch(args: argparse.Namespace, resource: str, *, fmt: str, jq: str | None = None) -> None:
    """comment サブコマンドの共通ディスパッチ。"""
    action = getattr(args, "comment_action", None)
    if action is None:
        raise ConfigError(_("comment action required: list, create, edit, delete"))
    adapter = get_adapter()
    if action == "list":
        comments = adapter.list_comments(resource, args.number, limit=args.limit)
        output(comments, fmt=fmt, fields=["id", "author", "body", "created_at"], jq=jq)
    elif action == "create":
        comment = adapter.create_comment(resource, args.number, body=args.body)
        output(comment, fmt=fmt, jq=jq)
    elif action == "edit":
        comment = adapter.update_comment(resource, args.comment_id, body=args.body)
        output(comment, fmt=fmt, jq=jq)
    elif action == "delete":
        adapter.delete_comment(resource, args.comment_id)
        print(_("Deleted comment '{comment_id}'.").format(comment_id=args.comment_id))


def handle_pr_comment(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr comment のハンドラ。"""
    _dispatch(args, "pr", fmt=fmt, jq=jq)


def handle_issue_comment(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo issue comment のハンドラ。"""
    _dispatch(args, "issue", fmt=fmt, jq=jq)
