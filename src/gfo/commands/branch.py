"""gfo branch サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.commands import get_adapter
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo branch list のハンドラ。"""
    adapter = get_adapter()
    branches = adapter.list_branches(limit=args.limit)
    output(branches, fmt=fmt, fields=["name", "sha", "protected"])


def handle_create(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo branch create <name> --ref <sha-or-branch> のハンドラ。"""
    adapter = get_adapter()
    branch = adapter.create_branch(name=args.name, ref=args.ref)
    output(branch, fmt=fmt)


def handle_delete(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo branch delete <name> のハンドラ。"""
    adapter = get_adapter()
    adapter.delete_branch(name=args.name)
