"""gfo notification サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.commands import get_adapter
from gfo.exceptions import GfoError
from gfo.i18n import _
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo notification list のハンドラ。"""
    adapter = get_adapter()
    notifications = adapter.list_notifications(
        unread_only=args.unread_only,
        limit=args.limit,
    )
    output(
        notifications,
        fmt=fmt,
        fields=["id", "title", "reason", "unread", "repository", "updated_at"],
        jq=jq,
    )


def handle_read(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo notification read のハンドラ。"""
    adapter = get_adapter()
    if args.mark_all and args.id is not None:
        raise GfoError(_("Cannot specify both ID and --all."))
    if not args.mark_all and args.id is None:
        raise GfoError(_("Specify a notification ID or --all."))
    if args.mark_all:
        adapter.mark_all_notifications_read()
        print(_("Marked all notifications as read."))
    else:
        adapter.mark_notification_read(args.id)
        print(_("Marked notification '{id}' as read.").format(id=args.id))
