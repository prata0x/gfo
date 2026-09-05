"""gfo collaborator サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse
import json

from gfo.commands import confirm_action, get_adapter
from gfo.i18n import _
from gfo.output import _sanitize_for_plain, apply_jq_filter, output_result


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
            print(_sanitize_for_plain(username))


def handle_add(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo collaborator add <username> のハンドラ。"""
    adapter = get_adapter()
    adapter.add_collaborator(username=args.username, permission=args.permission)
    output_result(
        _("Added collaborator '{username}'.").format(username=args.username),
        result="added",
        fmt=fmt,
        jq=jq,
        username=args.username,
    )


def handle_remove(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo collaborator remove <username> のハンドラ。"""
    adapter = get_adapter()
    if not confirm_action(
        args,
        _("Are you sure you want to remove collaborator '{username}'? [y/N]: ").format(
            username=args.username
        ),
        fmt=fmt,
        jq=jq,
    ):
        return
    adapter.remove_collaborator(username=args.username)
    output_result(
        _("Removed collaborator '{username}'.").format(username=args.username),
        result="removed",
        fmt=fmt,
        jq=jq,
        username=args.username,
    )
