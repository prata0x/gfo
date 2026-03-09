"""gfo issue サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.adapter.registry import create_adapter
from gfo.config import resolve_project_config
from gfo.exceptions import ConfigError
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo issue list のハンドラ。"""
    config = resolve_project_config()
    adapter = create_adapter(config)
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
    config = resolve_project_config()
    adapter = create_adapter(config)
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
    config = resolve_project_config()
    adapter = create_adapter(config)
    issue = adapter.get_issue(args.number)
    output(issue, fmt=fmt)


def handle_close(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo issue close <number> のハンドラ。"""
    config = resolve_project_config()
    adapter = create_adapter(config)
    adapter.close_issue(args.number)
