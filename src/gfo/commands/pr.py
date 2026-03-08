"""gfo pr サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

import gfo.git_util
from gfo.adapter.registry import create_adapter
from gfo.config import resolve_project_config
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo pr list のハンドラ。"""
    config = resolve_project_config()
    adapter = create_adapter(config)
    prs = adapter.list_pull_requests(state=args.state, limit=args.limit)
    output(prs, fmt=fmt, fields=["number", "title", "state", "author"])


def handle_create(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo pr create のハンドラ。"""
    config = resolve_project_config()
    adapter = create_adapter(config)
    head = args.head or gfo.git_util.get_current_branch()
    base = args.base or gfo.git_util.get_default_branch()
    title = args.title or gfo.git_util.get_last_commit_subject()
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
    config = resolve_project_config()
    adapter = create_adapter(config)
    pr = adapter.get_pull_request(args.number)
    output(pr, fmt=fmt)


def handle_merge(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo pr merge <number> のハンドラ。"""
    config = resolve_project_config()
    adapter = create_adapter(config)
    adapter.merge_pull_request(args.number, method=args.method)


def handle_close(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo pr close <number> のハンドラ。"""
    config = resolve_project_config()
    adapter = create_adapter(config)
    adapter.close_pull_request(args.number)


def handle_checkout(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo pr checkout <number> のハンドラ。"""
    config = resolve_project_config()
    adapter = create_adapter(config)
    pr = adapter.get_pull_request(args.number)
    refspec = adapter.get_pr_checkout_refspec(args.number, pr=pr)
    gfo.git_util.git_fetch("origin", refspec)
    gfo.git_util.git_checkout_new_branch(pr.source_branch)
