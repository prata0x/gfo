"""gfo release サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.commands import get_adapter
from gfo.exceptions import ConfigError
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo release list のハンドラ。"""
    adapter = get_adapter()
    releases = adapter.list_releases(limit=args.limit)
    output(releases, fmt=fmt, fields=["tag", "title", "draft", "prerelease"])


def handle_create(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo release create のハンドラ。"""
    tag = (args.tag or "").strip()
    if not tag:
        raise ConfigError("--tag is required. Use --tag <tag> to specify a release tag.")
    adapter = get_adapter()
    title = args.title or tag
    release = adapter.create_release(
        tag=tag,
        title=title,
        notes=args.notes or "",
        draft=args.draft,
        prerelease=args.prerelease,
    )
    output(release, fmt=fmt)
