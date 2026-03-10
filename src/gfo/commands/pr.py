"""gfo pr サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

import gfo.git_util
from gfo.commands import get_adapter
from gfo.exceptions import ConfigError
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo pr list のハンドラ。"""
    adapter = get_adapter()
    prs = adapter.list_pull_requests(state=args.state, limit=args.limit)
    output(prs, fmt=fmt, fields=["number", "title", "state", "author"])


def handle_create(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo pr create のハンドラ。"""
    adapter = get_adapter()
    head = args.head or gfo.git_util.get_current_branch()
    base = args.base or gfo.git_util.get_default_branch()
    title = (args.title or gfo.git_util.get_last_commit_subject() or "").strip()
    if not title:
        raise ConfigError("Could not determine PR title. Use --title option.")
    pr = adapter.create_pull_request(
        title=title,
        body=args.body or "",
        base=base,
        head=head,
        draft=args.draft,
    )
    output(pr, fmt=fmt)


def handle_view(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo pr view <number> のハンドラ。"""
    adapter = get_adapter()
    pr = adapter.get_pull_request(args.number)
    output(pr, fmt=fmt)


def handle_merge(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo pr merge <number> のハンドラ。"""
    adapter = get_adapter()
    adapter.merge_pull_request(args.number, method=args.method)


def handle_close(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo pr close <number> のハンドラ。"""
    adapter = get_adapter()
    adapter.close_pull_request(args.number)


def handle_checkout(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo pr checkout <number> のハンドラ。"""
    adapter = get_adapter()
    pr = adapter.get_pull_request(args.number)
    refspec = adapter.get_pr_checkout_refspec(args.number, pr=pr)
    gfo.git_util.git_fetch("origin", refspec)
    gfo.git_util.git_checkout_branch(pr.source_branch)


def handle_update(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo pr update <number> のハンドラ。"""
    adapter = get_adapter()
    pr = adapter.update_pull_request(
        args.number,
        title=args.title,
        body=args.body,
        base=args.base,
    )
    output(pr, fmt=fmt)
