"""gfo issue-template サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.commands import get_adapter
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo issue-template list のハンドラ。"""
    adapter = get_adapter()
    templates = adapter.list_issue_templates()
    output(templates, fmt=fmt, fields=["name", "title", "about"], jq=jq)
