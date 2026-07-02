"""gfo milestone サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.commands import get_adapter, open_in_browser
from gfo.exceptions import ConfigError
from gfo.i18n import _
from gfo.output import output, output_result


def handle_list(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo milestone list のハンドラ。"""
    if getattr(args, "web", False):
        open_in_browser(get_adapter(), "milestone")
        return
    adapter = get_adapter()
    milestones = adapter.list_milestones()
    output(milestones, fmt=fmt, fields=["number", "title", "state", "due_date"], jq=jq)


def handle_create(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo milestone create のハンドラ。"""
    title = args.title.strip()
    if not title:
        raise ConfigError(_("title must not be empty."))
    adapter = get_adapter()
    milestone = adapter.create_milestone(
        title=title,
        description=args.description,
        due_date=args.due,
    )
    output(milestone, fmt=fmt, jq=jq)


def handle_delete(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo milestone delete のハンドラ。"""
    adapter = get_adapter()
    adapter.delete_milestone(number=args.number)
    output_result(
        _("Deleted milestone '{number}'.").format(number=args.number),
        result="deleted",
        number=args.number,
        fmt=fmt,
        jq=jq,
    )


def handle_view(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo milestone view のハンドラ。"""
    if getattr(args, "web", False):
        open_in_browser(get_adapter(), "milestone", args.number)
        return
    adapter = get_adapter()
    milestone = adapter.get_milestone(args.number)
    output(milestone, fmt=fmt, jq=jq)


def handle_edit(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo milestone edit のハンドラ。"""
    adapter = get_adapter()
    milestone = adapter.update_milestone(
        args.number,
        title=args.title,
        description=args.description,
        due_date=args.due,
        state=args.state,
    )
    output(milestone, fmt=fmt, jq=jq)


def handle_close(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo milestone close のハンドラ。"""
    adapter = get_adapter()
    adapter.update_milestone(args.number, state="closed")
    output_result(
        _("Closed milestone '{number}'.").format(number=args.number),
        result="closed",
        number=args.number,
        fmt=fmt,
        jq=jq,
    )


def handle_reopen(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo milestone reopen のハンドラ。"""
    adapter = get_adapter()
    adapter.update_milestone(args.number, state="open")
    output_result(
        _("Reopened milestone '{number}'.").format(number=args.number),
        result="reopened",
        number=args.number,
        fmt=fmt,
        jq=jq,
    )
