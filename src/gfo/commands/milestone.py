"""gfo milestone サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.adapter.registry import create_adapter
from gfo.config import resolve_project_config
from gfo.exceptions import ConfigError
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo milestone list のハンドラ。"""
    config = resolve_project_config()
    adapter = create_adapter(config)
    milestones = adapter.list_milestones()
    output(milestones, fmt=fmt, fields=["number", "title", "state", "due_date"])


def handle_create(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo milestone create のハンドラ。"""
    if not args.title.strip():
        raise ConfigError("title must not be empty.")
    config = resolve_project_config()
    adapter = create_adapter(config)
    milestone = adapter.create_milestone(
        title=args.title,
        description=args.description,
        due_date=args.due,
    )
    output(milestone, fmt=fmt)
