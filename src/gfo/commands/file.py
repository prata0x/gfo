"""gfo file サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse
import sys

from gfo.commands import get_adapter
from gfo.exceptions import NotFoundError


def handle_get(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo file get <path> [--ref REF] のハンドラ。"""
    adapter = get_adapter()
    content, sha = adapter.get_file_content(args.path, ref=args.ref)
    if fmt == "json":
        import json

        print(json.dumps({"path": args.path, "content": content, "sha": sha}, ensure_ascii=False))
    else:
        print(content)


def handle_put(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo file put <path> --message TEXT のハンドラ。stdin からファイル内容を読み込む。"""
    adapter = get_adapter()
    content = sys.stdin.read()
    # SHA が必要な場合は既存ファイルから取得
    sha: str | None = None
    try:
        _, sha = adapter.get_file_content(args.path, ref=args.branch)
    except NotFoundError:
        sha = None
    adapter.create_or_update_file(
        args.path,
        content=content,
        message=args.message,
        sha=sha,
        branch=args.branch,
    )


def handle_delete(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo file delete <path> --message TEXT のハンドラ。"""
    adapter = get_adapter()
    _, sha = adapter.get_file_content(args.path, ref=args.branch)
    adapter.delete_file(args.path, sha=sha, message=args.message, branch=args.branch)
