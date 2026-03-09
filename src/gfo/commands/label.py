"""gfo label サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse
import re

from gfo.commands import get_adapter
from gfo.exceptions import ConfigError
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo label list のハンドラ。"""
    adapter = get_adapter()
    labels = adapter.list_labels()
    output(labels, fmt=fmt, fields=["name", "color", "description"])


def handle_create(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo label create のハンドラ。"""
    name = args.name.strip()
    if not name:
        raise ConfigError("name must not be empty.")
    color = args.color
    if color is not None:
        color = color.removeprefix("#")
        if not re.fullmatch(r"[0-9a-fA-F]{6}", color):
            raise ConfigError(
                f"Invalid color '{args.color}'. Expected 6-digit hex color (e.g. ff0000)."
            )
    adapter = get_adapter()
    label = adapter.create_label(
        name=name,
        color=color,
        description=args.description,
    )
    output(label, fmt=fmt)
