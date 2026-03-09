"""gfo issue サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.commands import get_adapter, get_adapter_with_config
from gfo.exceptions import ConfigError
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo issue list のハンドラ。"""
    adapter = get_adapter()
    issues = adapter.list_issues(
        state=args.state,
        assignee=args.assignee,
        label=args.label,
        limit=args.limit,
    )
    output(issues, fmt=fmt, fields=["number", "title", "state", "author"])


def handle_create(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo issue create のハンドラ。"""
    if not args.title or not args.title.strip():
        raise ConfigError("--title must not be empty.")
    adapter, config = get_adapter_with_config()
    kwargs: dict = {}
    if args.type:
        if config.service_type == "azure-devops":
            kwargs["work_item_type"] = args.type
        elif config.service_type == "backlog":
            kwargs["issue_type"] = args.type
    if args.priority is not None and config.service_type == "backlog":
        kwargs["priority"] = args.priority
    issue = adapter.create_issue(
        title=args.title,
        body=args.body or "",
        assignee=args.assignee,
        label=args.label,
        **kwargs,
    )
    output(issue, fmt=fmt)


def handle_view(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo issue view <number> のハンドラ。"""
    adapter = get_adapter()
    issue = adapter.get_issue(args.number)
    output(issue, fmt=fmt)


def handle_close(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo issue close <number> のハンドラ。"""
    adapter = get_adapter()
    adapter.close_issue(args.number)
