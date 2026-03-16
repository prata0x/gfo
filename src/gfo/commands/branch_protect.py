"""gfo branch-protect サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.commands import get_adapter
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo branch-protect list のハンドラ。"""
    adapter = get_adapter()
    protections = adapter.list_branch_protections(limit=args.limit)
    output(
        protections,
        fmt=fmt,
        fields=["branch", "require_reviews", "enforce_admins", "allow_force_push"],
        jq=jq,
    )


def handle_view(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo branch-protect view <branch> のハンドラ。"""
    adapter = get_adapter()
    protection = adapter.get_branch_protection(args.branch)
    output(protection, fmt=fmt, jq=jq)


def handle_set(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo branch-protect set <branch> のハンドラ。"""
    adapter = get_adapter()
    protection = adapter.set_branch_protection(
        args.branch,
        require_reviews=args.require_reviews,
        require_status_checks=args.require_status_checks,
        enforce_admins=args.enforce_admins,
        allow_force_push=args.allow_force_push,
        allow_deletions=args.allow_deletions,
    )
    output(protection, fmt=fmt, jq=jq)


def handle_remove(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo branch-protect remove <branch> のハンドラ。"""
    adapter = get_adapter()
    adapter.remove_branch_protection(args.branch)
