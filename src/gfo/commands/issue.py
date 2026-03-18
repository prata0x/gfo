"""gfo issue サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

from gfo.commands import (
    create_adapter_from_spec,
    get_adapter,
    get_adapter_with_config,
    parse_service_spec,
)
from gfo.exceptions import ConfigError, NotSupportedError
from gfo.i18n import _
from gfo.output import output


@dataclass(frozen=True, slots=True)
class MigrateResult:
    source_number: int
    target_number: int | None
    success: bool
    error: str | None = None


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


def _sync_labels(src, dst) -> set[str]:
    """ソース側のラベルをターゲット側に同期し、利用可能なラベル名セットを返す。"""
    try:
        src_labels = src.list_labels()
    except NotSupportedError:
        return set()
    try:
        dst_labels = dst.list_labels()
    except NotSupportedError:
        print(_("Warning: target service does not support labels."), file=sys.stderr)
        return set()
    dst_label_names = {lb.name for lb in dst_labels}
    for lb in src_labels:
        if lb.name not in dst_label_names:
            try:
                dst.create_label(name=lb.name, color=lb.color or "")
                dst_label_names.add(lb.name)
            except NotSupportedError:
                print(
                    _("Warning: could not create label '{name}' on target.").format(name=lb.name),
                    file=sys.stderr,
                )
    return dst_label_names


def _migrate_one_issue(src, dst, number, available_labels, src_spec_str) -> MigrateResult:
    """単一の Issue を移行する。"""
    try:
        issue = src.get_issue(number)

        # body の先頭に移行元メタデータを埋め込み
        if issue.url:
            header = f"> *Migrated from [{src_spec_str}#{number}]({issue.url})*"
        else:
            header = f"> *Migrated from {src_spec_str}#{number}*"
        header += f"\n> *Original author: @{issue.author} | Created: {issue.created_at}*"
        original_body = issue.body or ""
        new_body = f"{header}\n---\n{original_body}"

        # label: available_labels に含まれるもの → 最初の1つ
        label = None
        for lb_name in issue.labels:
            if lb_name in available_labels:
                label = lb_name
                break

        # assignee: 最初の1名
        assignee = issue.assignees[0] if issue.assignees else None

        created = dst.create_issue(
            title=issue.title,
            body=new_body,
            assignee=assignee,
            label=label,
        )

        # コメント移行
        comments = src.list_comments("issue", number)
        for comment in comments:
            new_comment_body = (
                f"> *Comment by @{comment.author} on {comment.created_at}*\n\n{comment.body}"
            )
            dst.create_comment("issue", created.number, body=new_comment_body)

        return MigrateResult(
            source_number=number,
            target_number=created.number,
            success=True,
        )
    except Exception as e:
        return MigrateResult(
            source_number=number,
            target_number=None,
            success=False,
            error=str(e),
        )


def handle_migrate(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo issue migrate のハンドラ。"""
    src_spec = parse_service_spec(args.from_spec)
    dst_spec = parse_service_spec(args.to_spec)
    src_adapter = create_adapter_from_spec(src_spec)
    dst_adapter = create_adapter_from_spec(dst_spec)

    # 移行対象 Issue 番号を決定
    if getattr(args, "number", None) is not None:
        numbers = [args.number]
    elif getattr(args, "numbers", None) is not None:
        numbers = [int(n) for n in args.numbers.split(",")]
    elif getattr(args, "migrate_all", False):
        numbers = [i.number for i in src_adapter.list_issues(state="all", limit=0)]
    else:
        raise ConfigError(_("Specify --number, --numbers, or --all."))

    # ラベル同期
    available_labels = _sync_labels(src_adapter, dst_adapter)

    # 移行元メタデータ文字列
    src_spec_str = f"{src_spec.service_type}:{src_spec.owner}/{src_spec.repo}"

    # 各 Issue を移行
    results = []
    for num in numbers:
        result = _migrate_one_issue(src_adapter, dst_adapter, num, available_labels, src_spec_str)
        results.append(result)

    output(results, fmt=fmt, fields=["source_number", "target_number", "success", "error"], jq=jq)
