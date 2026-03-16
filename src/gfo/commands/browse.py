"""gfo browse サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse
import webbrowser

from gfo.commands import get_adapter


def handle_browse(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    adapter = get_adapter()
    resource = "repo"
    number = None
    if args.pr is not None:
        resource, number = "pr", args.pr
    elif args.issue is not None:
        resource, number = "issue", args.issue
    elif args.settings:
        resource = "settings"

    url = adapter.get_web_url(resource, number)

    if getattr(args, "print", False):
        print(url)
    else:
        webbrowser.open(url)
