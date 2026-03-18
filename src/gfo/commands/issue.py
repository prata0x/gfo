"""gfo issue サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.commands import get_adapter, get_adapter_with_config
from gfo.exceptions import ConfigError
from gfo.i18n import _
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo issue list のハンドラ。"""
    adapter = get_adapter()
    issues = adapter.list_issues(
        state=args.state,
        assignee=args.assignee,
        label=args.label,
        limit=args.limit,
    )
    output(issues, fmt=fmt, fields=["number", "title", "state", "author"], jq=jq)


def handle_create(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo issue create のハンドラ。"""
    title = (args.title or "").strip()
    if not title:
        raise ConfigError(_("--title must not be empty."))
    adapter, config = get_adapter_with_config()
    kwargs: dict = {}
    if args.type:
        if config.service_type == "azure-devops":
            kwargs["work_item_type"] = args.type
        elif config.service_type == "backlog":
            try:
                kwargs["issue_type"] = int(args.type)
            except (ValueError, TypeError):
                raise ConfigError(
                    _("--type must be a numeric issue type ID for Backlog, got {type}.").format(
                        type=repr(args.type)
                    )
                )
    if args.priority is not None and config.service_type == "backlog":
        kwargs["priority"] = args.priority
    issue = adapter.create_issue(
        title=title,
        body=args.body or "",
        assignee=args.assignee,
        label=args.label,
        **kwargs,
    )
    output(issue, fmt=fmt, jq=jq)


def handle_view(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo issue view <number> のハンドラ。"""
    adapter = get_adapter()
    issue = adapter.get_issue(args.number)
    output(issue, fmt=fmt, jq=jq)


def handle_close(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo issue close <number> のハンドラ。"""
    adapter = get_adapter()
    adapter.close_issue(args.number)


def handle_reopen(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo issue reopen <number> のハンドラ。"""
    adapter = get_adapter()
    adapter.reopen_issue(args.number)


def handle_delete(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo issue delete <number> のハンドラ。"""
    adapter = get_adapter()
    adapter.delete_issue(args.number)
    print(_("Deleted issue '{number}'.").format(number=args.number))


def handle_update(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo issue update <number> のハンドラ。"""
    adapter = get_adapter()
    issue = adapter.update_issue(
        args.number,
        title=args.title,
        body=args.body,
        assignee=args.assignee,
        label=args.label,
    )
    output(issue, fmt=fmt, jq=jq)


def handle_reaction(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo issue reaction list/add/remove のハンドラ。"""
    adapter = get_adapter()
    action = getattr(args, "reaction_action", None)
    if action is None:
        raise ConfigError(_("Specify a subcommand: list, add, remove"))
    if action == "list":
        reactions = adapter.list_issue_reactions(args.number)
        output(reactions, fmt=fmt, fields=["content", "user", "created_at"], jq=jq)
    elif action == "add":
        reaction = adapter.add_issue_reaction(args.number, args.reaction)
        output(reaction, fmt=fmt, jq=jq)
    elif action == "remove":
        adapter.remove_issue_reaction(args.number, args.reaction)


def handle_depends(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo issue depends list/add/remove のハンドラ。"""
    adapter = get_adapter()
    action = getattr(args, "depends_action", None)
    if action is None:
        raise ConfigError(_("Specify a subcommand: list, add, remove"))
    if action == "list":
        deps = adapter.list_issue_dependencies(args.number)
        output(deps, fmt=fmt, fields=["number", "title", "state"], jq=jq)
    elif action == "add":
        adapter.add_issue_dependency(args.number, args.depends_on)
    elif action == "remove":
        adapter.remove_issue_dependency(args.number, args.depends_on)


def handle_timeline(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo issue timeline <number> のハンドラ。"""
    adapter = get_adapter()
    events = adapter.get_issue_timeline(args.number, limit=getattr(args, "limit", 30))
    output(events, fmt=fmt, fields=["event", "actor", "detail", "created_at"], jq=jq)


def handle_pin(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo issue pin <number> のハンドラ。"""
    adapter = get_adapter()
    adapter.pin_issue(args.number)
    print(_("Pinned issue '{number}'.").format(number=args.number))


def handle_unpin(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo issue unpin <number> のハンドラ。"""
    adapter = get_adapter()
    adapter.unpin_issue(args.number)
    print(_("Unpinned issue '{number}'.").format(number=args.number))


def _parse_duration(s: str) -> int:
    """Duration 文字列を秒に変換する。例: '1h30m' -> 5400, '45m' -> 2700, '2h' -> 7200"""
    import re

    total = 0
    pattern = re.compile(r"(\d+)\s*([hHmMsS])")
    for match in pattern.finditer(s):
        value = int(match.group(1))
        unit = match.group(2).lower()
        if unit == "h":
            total += value * 3600
        elif unit == "m":
            total += value * 60
        elif unit == "s":
            total += value
    if total == 0:
        # Try plain integer as seconds
        try:
            total = int(s)
        except ValueError:
            raise ConfigError(
                _(
                    "Invalid duration format: '{s}'. Use format like '1h30m', '45m', or '3600'."
                ).format(s=s)
            )
    return total


def handle_time(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo issue time list/add/delete のハンドラ。"""
    adapter = get_adapter()
    action = getattr(args, "time_action", None)
    if action is None:
        raise ConfigError(_("Specify a subcommand: list, add, delete"))
    if action == "list":
        entries = adapter.list_time_entries(args.number)
        output(entries, fmt=fmt, fields=["id", "user", "duration", "created_at"], jq=jq)
    elif action == "add":
        duration = _parse_duration(args.duration)
        entry = adapter.add_time_entry(args.number, duration)
        output(entry, fmt=fmt, jq=jq)
    elif action == "delete":
        adapter.delete_time_entry(args.number, args.entry_id)
        print(_("Deleted time entry '{entry_id}'.").format(entry_id=args.entry_id))
