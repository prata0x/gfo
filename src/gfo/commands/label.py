"""gfo label サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.adapter.registry import create_adapter
from gfo.config import resolve_project_config
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo label list のハンドラ。"""
    config = resolve_project_config()
    adapter = create_adapter(config)
    labels = adapter.list_labels()
    output(labels, fmt=fmt, fields=["name", "color", "description"])


def handle_create(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo label create のハンドラ。"""
    config = resolve_project_config()
    adapter = create_adapter(config)
    label = adapter.create_label(
        name=args.name,
        color=args.color,
        description=args.description,
    )
    output(label, fmt=fmt)
