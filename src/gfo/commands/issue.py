"""gfo issue サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

from gfo.commands import (
    create_adapter_from_spec,
    get_adapter,
    get_adapter_with_config,
    open_in_browser,
    parse_service_spec,
    read_file_arg,
)
from gfo.exceptions import ConfigError, GfoError, NotSupportedError

if TYPE_CHECKING:
    from gfo.adapter.base import GitServiceAdapter
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
    if getattr(args, "web", False):
        open_in_browser(get_adapter(), "issue")
        return
    adapter = get_adapter()
    issues = adapter.list_issues(
        state=args.state,
        assignee=args.assignee,
        label=args.label,
        limit=args.limit,
        author=getattr(args, "author", None),
        milestone=getattr(args, "milestone", None),
        search=getattr(args, "search", None),
    )
    output(issues, fmt=fmt, fields=["number", "title", "state", "author"], jq=jq)


def handle_create(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo issue create のハンドラ。"""
    if getattr(args, "body_file", None):
        args.body = read_file_arg(args.body_file)
    title = (args.title or "").strip()
    adapter, config = get_adapter_with_config()

    # --template: テンプレート名が指定された場合、本文に反映
    template_name = getattr(args, "template", None)
    if template_name and not args.body:
        templates = adapter.list_issue_templates()
        matched = next((t for t in templates if t.name == template_name), None)
        if matched is None:
            names = ", ".join(t.name for t in templates) if templates else _("(none)")
            raise ConfigError(
                _("Template '{name}' not found. Available: {available}").format(
                    name=template_name, available=names
                )
            )
        args.body = matched.body
        if matched.title and not title:
            title = matched.title

    if not title:
        raise ConfigError(_("--title must not be empty."))

    kwargs: dict = {}
    if args.type:
        if config.service_type == "azure-devops":
            kwargs["work_item_type"] = args.type
        elif config.service_type == "backlog":
            try:
                kwargs["issue_type"] = int(args.type)
            except (ValueError, TypeError) as e:
                raise ConfigError(
                    _("--type must be a numeric issue type ID for Backlog, got {type}.").format(
                        type=repr(args.type)
                    )
                ) from e
    if args.priority is not None and config.service_type == "backlog":
        kwargs["priority"] = args.priority
    milestone = getattr(args, "milestone", None)
    due_date = getattr(args, "due_date", None)
    issue = adapter.create_issue(
        title=title,
        body=args.body or "",
        assignee=args.assignee,
        label=args.label,
        milestone=milestone,
        due_date=due_date,
        **kwargs,
    )
    output(issue, fmt=fmt, jq=jq)
    if getattr(args, "web", False):
        import webbrowser

        webbrowser.open(issue.url)


def handle_view(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo issue view <number> のハンドラ。"""
    if getattr(args, "web", False):
        open_in_browser(get_adapter(), "issue", args.number)
        return
    adapter = get_adapter()
    issue = adapter.get_issue(args.number)
    output(issue, fmt=fmt, jq=jq)


def handle_close(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo issue close <number> のハンドラ。"""
    adapter = get_adapter()
    adapter.close_issue(args.number)
    print(_("Closed issue #{number}.").format(number=args.number))


def handle_reopen(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo issue reopen <number> のハンドラ。"""
    adapter = get_adapter()
    adapter.reopen_issue(args.number)
    print(_("Reopened issue #{number}.").format(number=args.number))


def handle_delete(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo issue delete <number> のハンドラ。"""
    adapter = get_adapter()
    adapter.delete_issue(args.number)
    print(_("Deleted issue '{number}'.").format(number=args.number))


def handle_edit(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo issue edit <number> のハンドラ。"""
    adapter = get_adapter()
    issue = adapter.update_issue(
        args.number,
        title=args.title,
        body=args.body,
        assignee=args.assignee,
        label=args.label,
        add_labels=getattr(args, "add_label", None),
        remove_labels=getattr(args, "remove_label", None),
        add_assignees=getattr(args, "add_assignee", None),
        remove_assignees=getattr(args, "remove_assignee", None),
        milestone=getattr(args, "milestone", None),
        due_date=getattr(args, "due_date", None),
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
        print(
            _("Removed reaction '{reaction}' from issue #{number}.").format(
                reaction=args.reaction, number=args.number
            )
        )


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
        print(
            _("Added dependency #{depends_on} to issue #{number}.").format(
                depends_on=args.depends_on, number=args.number
            )
        )
    elif action == "remove":
        adapter.remove_issue_dependency(args.number, args.depends_on)
        print(
            _("Removed dependency #{depends_on} from issue #{number}.").format(
                depends_on=args.depends_on, number=args.number
            )
        )


def handle_timeline(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo issue timeline <number> のハンドラ。"""
    adapter = get_adapter()
    events = adapter.get_issue_timeline(args.number, limit=getattr(args, "limit", 30))
    output(events, fmt=fmt, fields=["event", "actor", "detail", "created_at"], jq=jq)


def handle_lock(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo issue lock <number> のハンドラ。"""
    adapter = get_adapter()
    adapter.lock_issue(args.number, reason=getattr(args, "reason", None))
    print(_("Locked issue #{number}.").format(number=args.number))


def handle_unlock(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo issue unlock <number> のハンドラ。"""
    adapter = get_adapter()
    adapter.unlock_issue(args.number)
    print(_("Unlocked issue #{number}.").format(number=args.number))


def handle_subscribe(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo issue subscribe <number> のハンドラ。"""
    adapter = get_adapter()
    adapter.subscribe_issue(args.number)
    print(_("Subscribed to issue #{number}.").format(number=args.number))


def handle_unsubscribe(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo issue unsubscribe <number> のハンドラ。"""
    adapter = get_adapter()
    adapter.unsubscribe_issue(args.number)
    print(_("Unsubscribed from issue #{number}.").format(number=args.number))


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
        except ValueError as e:
            raise ConfigError(
                _(
                    "Invalid duration format: '{s}'. Use format like '1h30m', '45m', or '3600'."
                ).format(s=s)
            ) from e
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


def handle_status(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo issue status のハンドラ。"""
    from gfo.output import output_grouped

    adapter = get_adapter()
    username = adapter.get_current_username()

    created = adapter.list_issues(state="open", author=username)
    assigned = adapter.list_issues(state="open", assignee=username)

    output_grouped(
        {"created": created, "assigned": assigned},
        fields=["number", "title", "state", "author"],
        fmt=fmt,
        jq=jq,
        labels={"created": _("Created by you"), "assigned": _("Assigned to you")},
        empty_message=_("  No issues found."),
    )


def _slugify(text: str, max_len: int = 40) -> str:
    """タイトル文字列をブランチ名用のスラッグに変換する。"""
    import re
    import unicodedata

    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:max_len].rstrip("-") if text else "issue"


def handle_develop(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo issue develop <number> のハンドラ。"""
    adapter = get_adapter()
    issue = adapter.get_issue(args.number)

    # ブランチ名の決定
    branch_name = getattr(args, "name", None)
    if not branch_name:
        slug = _slugify(issue.title)
        branch_name = f"issue-{args.number}-{slug}"

    # ベースブランチの決定
    base = getattr(args, "base", None)
    if not base:
        repo = adapter.get_repository()
        base = repo.default_branch or "main"

    branch = adapter.create_branch(name=branch_name, ref=base)
    output(branch, fmt=fmt, jq=jq)


def _sync_labels(src: GitServiceAdapter, dst: GitServiceAdapter) -> set[str]:
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


def _migrate_one_issue(
    src: GitServiceAdapter,
    dst: GitServiceAdapter,
    number: int,
    available_labels: set[str],
    src_spec_str: str,
) -> MigrateResult:
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

        # 元 Issue が closed の場合はターゲット側もクローズ
        if issue.state == "closed":
            dst.close_issue(created.number)

        # コメント移行
        comments = src.list_comments("issue", number, limit=0)
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
    except GfoError as e:
        # AttributeError / TypeError / KeyError などのプログラミングエラーは握りつぶさず
        # 上位に再 raise する（batch.py と同じ方針。実装バグを移行失敗として隠さない）
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
