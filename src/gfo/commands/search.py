"""gfo search サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.commands import get_adapter
from gfo.output import output


def handle_repos(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo search repos <query> のハンドラ。"""
    adapter = get_adapter()
    repos = adapter.search_repositories(args.query, limit=args.limit)
    output(repos, fmt=fmt, fields=["full_name", "description", "private"], jq=jq)


def handle_issues(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo search issues <query> のハンドラ。"""
    adapter = get_adapter()
    issues = adapter.search_issues(args.query, limit=args.limit)
    output(issues, fmt=fmt, fields=["number", "title", "state", "author"], jq=jq)


def handle_prs(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo search prs <query> のハンドラ。"""
    adapter = get_adapter()
    prs = adapter.search_pull_requests(
        args.query,
        state=getattr(args, "state", None),
        limit=args.limit,
    )
    output(prs, fmt=fmt, fields=["number", "title", "state", "author"], jq=jq)


def handle_commits(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo search commits <query> のハンドラ。"""
    adapter = get_adapter()
    commits = adapter.search_commits(
        args.query,
        author=getattr(args, "author", None),
        since=getattr(args, "since", None),
        until=getattr(args, "until", None),
        limit=args.limit,
    )
    output(commits, fmt=fmt, fields=["sha", "message", "author", "created_at"], jq=jq)
