"""gfo release サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.commands import get_adapter
from gfo.exceptions import ConfigError
from gfo.i18n import _
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo release list のハンドラ。"""
    adapter = get_adapter()
    releases = adapter.list_releases(limit=args.limit)
    output(releases, fmt=fmt, fields=["tag", "title", "draft", "prerelease"], jq=jq)


def handle_create(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo release create のハンドラ。"""
    tag = (args.tag or "").strip()
    if not tag:
        raise ConfigError(_("tag must not be empty. Use 'gfo release create <tag>'."))
    adapter = get_adapter()
    title = (args.title or "").strip() or tag
    release = adapter.create_release(
        tag=tag,
        title=title,
        notes=args.notes or "",
        draft=args.draft,
        prerelease=args.prerelease,
    )
    output(release, fmt=fmt, jq=jq)


def handle_delete(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo release delete のハンドラ。"""
    tag = (args.tag or "").strip()
    if not tag:
        raise ConfigError(_("tag must not be empty. Use 'gfo release delete <tag>'."))
    adapter = get_adapter()
    adapter.delete_release(tag=tag)
    print(_("Deleted release '{tag}'.").format(tag=tag))
