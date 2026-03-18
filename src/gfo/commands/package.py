"""gfo package サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.commands import get_adapter
from gfo.i18n import _
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo package list のハンドラ。"""
    adapter = get_adapter()
    packages = adapter.list_packages(
        package_type=getattr(args, "type", None),
        limit=getattr(args, "limit", 30),
    )
    output(packages, fmt=fmt, fields=["name", "type", "version", "owner"], jq=jq)


def handle_view(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo package view のハンドラ。"""
    adapter = get_adapter()
    package = adapter.get_package(
        args.package_type,
        args.name,
        version=getattr(args, "version", None),
    )
    output(package, fmt=fmt, jq=jq)


def handle_delete(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo package delete のハンドラ。"""
    adapter = get_adapter()
    if not getattr(args, "yes", False):
        confirm = input(
            _("Are you sure you want to delete package '{type}/{name}@{version}'? [y/N]: ").format(
                type=args.package_type, name=args.name, version=args.version
            )
        )
        if confirm.lower() not in ("y", "yes"):
            print(_("Aborted."))
            return
    adapter.delete_package(args.package_type, args.name, args.version)
    print(
        _("Deleted package '{type}/{name}@{version}'.").format(
            type=args.package_type, name=args.name, version=args.version
        )
    )
