"""gfo milestone サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.commands import get_adapter
from gfo.exceptions import ConfigError
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo milestone list のハンドラ。"""
    adapter = get_adapter()
    milestones = adapter.list_milestones()
    output(milestones, fmt=fmt, fields=["number", "title", "state", "due_date"])


def handle_create(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo milestone create のハンドラ。"""
    title = args.title.strip()
    if not title:
        raise ConfigError("title must not be empty.")
    adapter = get_adapter()
    milestone = adapter.create_milestone(
        title=title,
        description=args.description,
        due_date=args.due,
    )
    output(milestone, fmt=fmt)


def handle_delete(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo milestone delete のハンドラ。"""
    adapter = get_adapter()
    adapter.delete_milestone(number=args.number)
    print(f"Deleted milestone '{args.number}'.")
