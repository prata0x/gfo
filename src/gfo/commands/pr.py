"""gfo pr サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

import gfo.git_util
from gfo.commands import get_adapter
from gfo.exceptions import ConfigError
from gfo.i18n import _
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr list のハンドラ。"""
    adapter = get_adapter()
    prs = adapter.list_pull_requests(state=args.state, limit=args.limit)
    output(prs, fmt=fmt, fields=["number", "title", "state", "author"], jq=jq)


def handle_create(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr create のハンドラ。"""
    adapter = get_adapter()
    head = args.head or gfo.git_util.get_current_branch()
    base = args.base or gfo.git_util.get_default_branch()
    title = (args.title or gfo.git_util.get_last_commit_subject() or "").strip()
    if not title:
        raise ConfigError(_("Could not determine PR title. Use --title option."))
    pr = adapter.create_pull_request(
        title=title,
        body=args.body or "",
        base=base,
        head=head,
        draft=args.draft,
    )
    output(pr, fmt=fmt, jq=jq)


def handle_view(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr view <number> のハンドラ。"""
    adapter = get_adapter()
    pr = adapter.get_pull_request(args.number)
    output(pr, fmt=fmt, jq=jq)


def handle_merge(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr merge <number> のハンドラ。"""
    adapter = get_adapter()
    if getattr(args, "auto", False):
        adapter.enable_auto_merge(args.number, merge_method=args.method)
        print(_("Enabled auto-merge for PR #{number}.").format(number=args.number))
    else:
        adapter.merge_pull_request(args.number, method=args.method)
        print(_("Merged PR #{number}.").format(number=args.number))


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


def handle_checkout(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr checkout <number> のハンドラ。"""
    adapter = get_adapter()
    pr = adapter.get_pull_request(args.number)
    refspec = adapter.get_pr_checkout_refspec(args.number, pr=pr)
    gfo.git_util.git_fetch("origin", refspec)
    gfo.git_util.git_checkout_branch(pr.source_branch)


def handle_update(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr update <number> のハンドラ。"""
    adapter = get_adapter()
    pr = adapter.update_pull_request(
        args.number,
        title=args.title,
        body=args.body,
        base=args.base,
    )
    output(pr, fmt=fmt, jq=jq)


def handle_diff(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo pr diff <number> のハンドラ。"""
    adapter = get_adapter()
    diff_text = adapter.get_pull_request_diff(args.number)
    print(diff_text, end="")


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
