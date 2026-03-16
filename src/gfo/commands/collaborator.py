"""gfo collaborator サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse
import json

from gfo.commands import get_adapter
from gfo.output import apply_jq_filter


def handle_list(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo collaborator list のハンドラ。"""
    adapter = get_adapter()
    usernames = adapter.list_collaborators(limit=args.limit)
    if fmt == "json":
        json_str = json.dumps(usernames, ensure_ascii=False)
        if jq is not None:
            print(apply_jq_filter(json_str, jq))
        else:
            print(json_str)
    else:
        for username in usernames:
            print(username)


def handle_add(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo collaborator add <username> のハンドラ。"""
    adapter = get_adapter()
    adapter.add_collaborator(username=args.username, permission=args.permission)


def handle_remove(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo collaborator remove <username> のハンドラ。"""
    adapter = get_adapter()
    adapter.remove_collaborator(username=args.username)
