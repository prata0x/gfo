"""gfo pr サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

import gfo.git_util
from gfo.commands import get_adapter, open_in_browser, read_file_arg
from gfo.exceptions import ConfigError
from gfo.i18n import _
from gfo.output import output


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
    base = args.base or gfo.git_util.get_default_branch()
    title = (args.title or gfo.git_util.get_last_commit_subject() or "").strip()
    if not title:
        raise ConfigError(_("Could not determine PR title. Use --title option."))
    if getattr(args, "fill", False):
        body = args.body or gfo.git_util.get_last_commit_body() or ""
    else:
        body = args.body or ""
    if getattr(args, "dry_run", False):
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
        print(_("Disabled auto-merge for PR #{number}.").format(number=args.number))
    elif getattr(args, "auto", False):
        if getattr(args, "subject", None) or getattr(args, "body", None):
            warnings.warn(_("--subject/--body are ignored when --auto is used."), stacklevel=1)
        adapter.enable_auto_merge(args.number, merge_method=method)
        print(_("Enabled auto-merge for PR #{number}.").format(number=args.number))
    else:
        adapter.merge_pull_request(
            args.number,
            method=method,
            title=getattr(args, "subject", None),
            message=getattr(args, "body", None),
        )
        print(_("Merged PR #{number}.").format(number=args.number))
    if source_branch:
        adapter.delete_branch(name=source_branch)
        print(_("Deleted branch '{branch}'.").format(branch=source_branch))


def handle_close(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr close <number> のハンドラ。"""
    adapter = get_adapter()
    adapter.close_pull_request(args.number)
    print(_("Closed PR #{number}.").format(number=args.number))


def handle_reopen(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr reopen <number> のハンドラ。"""
    adapter = get_adapter()
    adapter.reopen_pull_request(args.number)
    print(_("Reopened PR #{number}.").format(number=args.number))


def handle_lock(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr lock <number> のハンドラ。"""
    adapter = get_adapter()
    adapter.lock_pull_request(args.number, reason=getattr(args, "reason", None))
    print(_("Locked PR #{number}.").format(number=args.number))


def handle_unlock(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr unlock <number> のハンドラ。"""
    adapter = get_adapter()
    adapter.unlock_pull_request(args.number)
    print(_("Unlocked PR #{number}.").format(number=args.number))


def handle_checkout(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr checkout <number> のハンドラ。"""
    adapter = get_adapter()
    pr = adapter.get_pull_request(args.number)
    refspec = adapter.get_pr_checkout_refspec(args.number, pr=pr)
    gfo.git_util.git_fetch("origin", refspec)
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
        print(_("Added reviewers to PR #{number}.").format(number=args.number))
    elif action == "remove":
        adapter.remove_reviewers(args.number, args.users)
        print(_("Removed reviewers from PR #{number}.").format(number=args.number))
    else:
        reviewers = adapter.list_requested_reviewers(args.number)
        output(reviewers, fmt=fmt, jq=jq)


def handle_update_branch(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr update-branch <number> のハンドラ。"""
    adapter = get_adapter()
    adapter.update_pull_request_branch(args.number)
    print(_("Updated branch for PR #{number}.").format(number=args.number))


def handle_ready(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr ready <number> のハンドラ。"""
    adapter = get_adapter()
    adapter.mark_pull_request_ready(args.number)
    print(_("Marked PR #{number} as ready for review.").format(number=args.number))


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
    print(_("Subscribed to PR #{number}.").format(number=args.number))


def handle_unsubscribe(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr unsubscribe <number> のハンドラ。"""
    adapter = get_adapter()
    adapter.unsubscribe_pull_request(args.number)
    print(_("Unsubscribed from PR #{number}.").format(number=args.number))
