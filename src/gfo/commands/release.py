"""gfo release サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.adapter.registry import create_adapter
from gfo.config import resolve_project_config
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo release list のハンドラ。"""
    config = resolve_project_config()
    adapter = create_adapter(config)
    releases = adapter.list_releases(limit=args.limit)
    output(releases, fmt=fmt, fields=["tag", "title", "draft", "prerelease"])


def handle_create(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo release create のハンドラ。"""
    config = resolve_project_config()
    adapter = create_adapter(config)
    title = args.title or args.tag
    release = adapter.create_release(
        tag=args.tag,
        title=title,
        notes=args.notes or "",
        draft=args.draft,
        prerelease=args.prerelease,
    )
    output(release, fmt=fmt)
