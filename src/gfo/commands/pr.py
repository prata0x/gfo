"""gfo pr サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse
import json

import gfo.git_util
from gfo._context import cli_remote
from gfo.commands import get_adapter, open_in_browser, read_file_arg
from gfo.exceptions import ConfigError
from gfo.i18n import _
from gfo.output import _sanitize_for_plain, apply_jq_filter, output, output_result


def handle_list(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr list のハンドラ。"""
    if getattr(args, "web", False):
        open_in_browser(get_adapter(), "pr")
        return
    adapter = get_adapter()
    prs = adapter.list_pull_requests(
        state=args.state,
        limit=args.limit,
        author=getattr(args, "author", None),
        label=getattr(args, "label", None),
        assignee=getattr(args, "assignee", None),
        search=getattr(args, "search", None),
        base=getattr(args, "base", None),
        head=getattr(args, "head", None),
        draft=getattr(args, "draft", None),
        milestone=getattr(args, "milestone", None),
    )
    output(prs, fmt=fmt, fields=["number", "title", "state", "author"], jq=jq)


def handle_create(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr create のハンドラ。"""
    if getattr(args, "body_file", None):
        args.body = read_file_arg(args.body_file)
    adapter = get_adapter()
    head = args.head or gfo.git_util.get_current_branch()
    # --remote 指定時はそのリモートの HEAD から base を推定する
    base = args.base or gfo.git_util.get_default_branch(remote=cli_remote.get())
    title = (args.title or gfo.git_util.get_last_commit_subject() or "").strip()
    if not title:
        raise ConfigError(_("Could not determine PR title. Use --title option."))
    if getattr(args, "fill", False):
        body = args.body or gfo.git_util.get_last_commit_body() or ""
    else:
        body = args.body or ""
    if getattr(args, "dry_run", False):
        if fmt == "json":
            output_result(
                _("Title: {title}").format(title=title),
                result="dry_run",
                fmt=fmt,
                jq=jq,
                title=title,
                head=head,
                base=base,
                draft=bool(args.draft),
                body=body,
            )
        else:
            print(_("Title: {title}").format(title=title))
            print(_("Head:  {head} -> Base: {base}").format(head=head, base=base))
            if args.draft:
                print(_("Draft: yes"))
            if body:
                print(_("Body:"))
                print(body)
        return
    pr = adapter.create_pull_request(
        title=title,
        body=body,
        base=base,
        head=head,
        draft=args.draft,
        reviewers=getattr(args, "reviewer", None),
        assignees=getattr(args, "assignee", None),
        labels=getattr(args, "label", None),
        milestone=getattr(args, "milestone", None),
    )
    output(pr, fmt=fmt, jq=jq)
    if getattr(args, "web", False):
        import webbrowser

        webbrowser.open(pr.url)


def handle_view(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr view <number> のハンドラ。"""
    if getattr(args, "web", False):
        open_in_browser(get_adapter(), "pr", args.number)
        return
    adapter = get_adapter()
    pr = adapter.get_pull_request(args.number)
    output(pr, fmt=fmt, jq=jq)


def handle_merge(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr merge <number> のハンドラ。"""
    import warnings

    adapter = get_adapter()
    # --delete-branch は実際のマージ完了後にのみブランチを削除する。
    # --auto は「予約」のみで即時マージしないため、併用するとマージ前に
    # ソースブランチが消える。--disable-auto も同様にマージしない。
    # 即時削除の意味論を満たせない組み合わせは明示的に拒否する。
    if getattr(args, "delete_branch", False) and (
        getattr(args, "auto", False) or getattr(args, "disable_auto", False)
    ):
        raise ConfigError(
            _(
                "--delete-branch cannot be combined with --auto/--disable-auto "
                "(the branch would be deleted before the merge completes)."
            )
        )
    if getattr(args, "squash", False):
        method = "squash"
    elif getattr(args, "rebase", False):
        method = "rebase"
    else:
        method = "merge"
    # --delete-branch 指定時はマージ前にブランチ名を取得
    source_branch = None
    if getattr(args, "delete_branch", False):
        pr_info = adapter.get_pull_request(args.number)
        source_branch = pr_info.source_branch
    if getattr(args, "disable_auto", False):
        adapter.disable_auto_merge(args.number)
        result = "auto_merge_disabled"
        message = _("Disabled auto-merge for PR #{number}.").format(number=args.number)
    elif getattr(args, "auto", False):
        if getattr(args, "subject", None) or getattr(args, "body", None):
            warnings.warn(_("--subject/--body are ignored when --auto is used."), stacklevel=1)
        adapter.enable_auto_merge(args.number, merge_method=method)
        result = "auto_merge_enabled"
        message = _("Enabled auto-merge for PR #{number}.").format(number=args.number)
    else:
        adapter.merge_pull_request(
            args.number,
            method=method,
            title=getattr(args, "subject", None),
            message=getattr(args, "body", None),
        )
        result = "merged"
        message = _("Merged PR #{number}.").format(number=args.number)
    deleted_branch = None
    if source_branch:
        adapter.delete_branch(name=source_branch)
        deleted_branch = source_branch
    fields: dict[str, object] = {"number": args.number}
    if deleted_branch:
        fields["deleted_branch"] = deleted_branch
    output_result(message, result=result, fmt=fmt, jq=jq, **fields)
    if deleted_branch and fmt != "json":
        print(_("Deleted branch '{branch}'.").format(branch=deleted_branch))


def handle_close(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr close <number> のハンドラ。"""
    adapter = get_adapter()
    adapter.close_pull_request(args.number)
    output_result(
        _("Closed PR #{number}.").format(number=args.number),
        result="closed",
        fmt=fmt,
        jq=jq,
        number=args.number,
    )


def handle_reopen(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr reopen <number> のハンドラ。"""
    adapter = get_adapter()
    adapter.reopen_pull_request(args.number)
    output_result(
        _("Reopened PR #{number}.").format(number=args.number),
        result="reopened",
        fmt=fmt,
        jq=jq,
        number=args.number,
    )


def handle_lock(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr lock <number> のハンドラ。"""
    adapter = get_adapter()
    adapter.lock_pull_request(args.number, reason=getattr(args, "reason", None))
    output_result(
        _("Locked PR #{number}.").format(number=args.number),
        result="locked",
        fmt=fmt,
        jq=jq,
        number=args.number,
    )


def handle_unlock(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr unlock <number> のハンドラ。"""
    adapter = get_adapter()
    adapter.unlock_pull_request(args.number)
    output_result(
        _("Unlocked PR #{number}.").format(number=args.number),
        result="unlocked",
        fmt=fmt,
        jq=jq,
        number=args.number,
    )


def handle_checkout(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr checkout <number> のハンドラ。"""
    adapter = get_adapter()
    pr = adapter.get_pull_request(args.number)
    refspec = adapter.get_pr_checkout_refspec(args.number, pr=pr)
    # --remote 指定時はそのリモートから fetch する（アダプターの参照先と揃える）
    gfo.git_util.git_fetch(cli_remote.get() or "origin", refspec)
    gfo.git_util.git_checkout_branch(pr.source_branch)


def handle_edit(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr edit <number> のハンドラ。"""
    adapter = get_adapter()
    pr = adapter.update_pull_request(
        args.number,
        title=args.title,
        body=args.body,
        base=args.base,
        add_labels=getattr(args, "add_label", None),
        remove_labels=getattr(args, "remove_label", None),
        add_assignees=getattr(args, "add_assignee", None),
        remove_assignees=getattr(args, "remove_assignee", None),
        milestone=getattr(args, "milestone", None),
        draft=getattr(args, "draft", None),
    )
    output(pr, fmt=fmt, jq=jq)


def handle_diff(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr diff <number> のハンドラ。"""
    import sys

    adapter = get_adapter()
    out = sys.stdout.buffer
    for chunk in adapter.get_pull_request_diff(args.number):
        out.write(chunk)
    out.flush()


def handle_checks(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr checks <number> のハンドラ。"""
    adapter = get_adapter()
    checks = adapter.list_pull_request_checks(args.number)
    output(checks, fmt=fmt, fields=["name", "status", "conclusion", "url"], jq=jq)


def handle_files(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr files <number> のハンドラ。"""
    adapter = get_adapter()
    files = adapter.list_pull_request_files(args.number)
    output(files, fmt=fmt, fields=["filename", "status", "additions", "deletions"], jq=jq)


def handle_commits(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr commits <number> のハンドラ。"""
    adapter = get_adapter()
    commits = adapter.list_pull_request_commits(args.number)
    output(commits, fmt=fmt, fields=["sha", "message", "author", "created_at"], jq=jq)


def handle_reviewers(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr reviewers list|add|remove のハンドラ。"""
    adapter = get_adapter()
    action = getattr(args, "reviewer_action", None)
    if action == "add":
        adapter.request_reviewers(args.number, args.users)
        output_result(
            _("Added reviewers to PR #{number}.").format(number=args.number),
            result="reviewers_added",
            fmt=fmt,
            jq=jq,
            number=args.number,
        )
    elif action == "remove":
        adapter.remove_reviewers(args.number, args.users)
        output_result(
            _("Removed reviewers from PR #{number}.").format(number=args.number),
            result="reviewers_removed",
            fmt=fmt,
            jq=jq,
            number=args.number,
        )
    else:
        # list_requested_reviewers は list[str] を返すため output() は使えない
        # (dataclass を前提に fields/asdict を呼びクラッシュする)。
        # collaborator / org members 同様、apply_jq_filter を直接適用する。
        reviewers = adapter.list_requested_reviewers(args.number)
        if fmt == "json":
            json_str = json.dumps(reviewers, ensure_ascii=False)
            if jq is not None:
                print(apply_jq_filter(json_str, jq))
            else:
                print(json_str)
        else:
            for reviewer in reviewers:
                print(_sanitize_for_plain(reviewer))


def handle_update_branch(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr update-branch <number> のハンドラ。"""
    adapter = get_adapter()
    adapter.update_pull_request_branch(args.number)
    output_result(
        _("Updated branch for PR #{number}.").format(number=args.number),
        result="branch_updated",
        fmt=fmt,
        jq=jq,
        number=args.number,
    )


def handle_ready(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr ready <number> のハンドラ。"""
    adapter = get_adapter()
    adapter.mark_pull_request_ready(args.number)
    output_result(
        _("Marked PR #{number} as ready for review.").format(number=args.number),
        result="ready",
        fmt=fmt,
        jq=jq,
        number=args.number,
    )


def handle_status(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr status のハンドラ。"""
    from gfo.output import output_grouped

    adapter = get_adapter()
    username = adapter.get_current_username()

    created = adapter.list_pull_requests(state="open", author=username)
    assigned = adapter.list_pull_requests(state="open", assignee=username)

    output_grouped(
        {"created": created, "assigned": assigned},
        fields=["number", "title", "state", "author"],
        fmt=fmt,
        jq=jq,
        labels={"created": _("Created by you"), "assigned": _("Assigned to you")},
        empty_message=_("  No pull requests found."),
    )


def handle_subscribe(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr subscribe <number> のハンドラ。"""
    adapter = get_adapter()
    adapter.subscribe_pull_request(args.number)
    output_result(
        _("Subscribed to PR #{number}.").format(number=args.number),
        result="subscribed",
        fmt=fmt,
        jq=jq,
        number=args.number,
    )


def handle_unsubscribe(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr unsubscribe <number> のハンドラ。"""
    adapter = get_adapter()
    adapter.unsubscribe_pull_request(args.number)
    output_result(
        _("Unsubscribed from PR #{number}.").format(number=args.number),
        result="unsubscribed",
        fmt=fmt,
        jq=jq,
        number=args.number,
    )
