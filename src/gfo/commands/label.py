"""gfo label サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse
import re

from gfo.commands import get_adapter
from gfo.exceptions import ConfigError
from gfo.i18n import _
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo label list のハンドラ。"""
    adapter = get_adapter()
    labels = adapter.list_labels()
    output(labels, fmt=fmt, fields=["name", "color", "description"], jq=jq)


def handle_create(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo label create のハンドラ。"""
    name = args.name.strip()
    if not name:
        raise ConfigError(_("name must not be empty."))
    color = args.color
    if color is not None:
        color = color.removeprefix("#")
        if not re.fullmatch(r"[0-9a-fA-F]{6}", color):
            raise ConfigError(
                _("Invalid color '{color}'. Expected 6-digit hex color (e.g. ff0000).").format(
                    color=args.color
                )
            )
    adapter = get_adapter()
    label = adapter.create_label(
        name=name,
        color=color,
        description=args.description,
    )
    output(label, fmt=fmt, jq=jq)


def handle_delete(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo label delete のハンドラ。"""
    name = args.name.strip()
    if not name:
        raise ConfigError(_("name must not be empty."))
    adapter = get_adapter()
    adapter.delete_label(name=name)
    print(_("Deleted label '{name}'.").format(name=name))


def handle_update(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo label update <name> のハンドラ。"""
    name = args.name.strip()
    if not name:
        raise ConfigError(_("name must not be empty."))
    color = args.color
    if color is not None:
        color = color.removeprefix("#")
        if not re.fullmatch(r"[0-9a-fA-F]{6}", color):
            raise ConfigError(
                _("Invalid color '{color}'. Expected 6-digit hex color (e.g. ff0000).").format(
                    color=args.color
                )
            )
    adapter = get_adapter()
    label = adapter.update_label(
        name=name,
        new_name=args.new_name,
        color=color,
        description=args.description,
    )
    output(label, fmt=fmt, jq=jq)
