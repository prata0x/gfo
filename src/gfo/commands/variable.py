"""gfo variable サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.commands import get_adapter
from gfo.i18n import _
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo variable list のハンドラ。"""
    adapter = get_adapter()
    scope = getattr(args, "org", None)
    variables = adapter.list_variables(scope=scope, limit=args.limit)
    output(variables, fmt=fmt, fields=["name", "value", "updated_at"], jq=jq)


def handle_set(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo variable set <name> --value VALUE のハンドラ。"""
    adapter = get_adapter()
    scope = getattr(args, "org", None)
    variable = adapter.set_variable(
        args.name, args.value, scope=scope, masked=getattr(args, "masked", False)
    )
    output(variable, fmt=fmt, jq=jq)


def handle_get(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo variable get <name> のハンドラ。"""
    adapter = get_adapter()
    scope = getattr(args, "org", None)
    variable = adapter.get_variable(args.name, scope=scope)
    if fmt == "json" or jq is not None:
        output(variable, fmt="json", jq=jq)
    else:
        print(variable.value)


def handle_delete(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo variable delete <name> のハンドラ。"""
    adapter = get_adapter()
    scope = getattr(args, "org", None)
    adapter.delete_variable(args.name, scope=scope)
    print(_("Deleted variable '{name}'.").format(name=args.name))
