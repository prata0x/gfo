"""gfo milestone サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.commands import get_adapter
from gfo.exceptions import ConfigError
from gfo.i18n import _
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo milestone list のハンドラ。"""
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
    print(_("Deleted milestone '{number}'.").format(number=args.number))


def handle_view(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo milestone view のハンドラ。"""
    adapter = get_adapter()
    milestone = adapter.get_milestone(args.number)
    output(milestone, fmt=fmt, jq=jq)


def handle_update(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo milestone update のハンドラ。"""
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


def handle_reopen(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo milestone reopen のハンドラ。"""
    adapter = get_adapter()
    adapter.update_milestone(args.number, state="open")
