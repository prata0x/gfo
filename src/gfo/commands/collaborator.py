"""gfo collaborator サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.commands import get_adapter


def handle_list(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo collaborator list のハンドラ。"""
    adapter = get_adapter()
    usernames = adapter.list_collaborators(limit=args.limit)
    if fmt == "json":
        import json

        print(json.dumps(usernames, ensure_ascii=False))
    else:
        for username in usernames:
            print(username)


def handle_add(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo collaborator add <username> のハンドラ。"""
    adapter = get_adapter()
    adapter.add_collaborator(username=args.username, permission=args.permission)


def handle_remove(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo collaborator remove <username> のハンドラ。"""
    adapter = get_adapter()
    adapter.remove_collaborator(username=args.username)
