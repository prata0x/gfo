"""gfo secret サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse
import os

from gfo.commands import get_adapter, read_file_arg
from gfo.exceptions import GfoError
from gfo.i18n import _
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo secret list のハンドラ。"""
    adapter = get_adapter()
    scope = getattr(args, "org", None)
    secrets = adapter.list_secrets(scope=scope, limit=args.limit)
    output(secrets, fmt=fmt, fields=["name", "updated_at"], jq=jq)


def handle_set(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo secret set <name> のハンドラ。"""
    adapter = get_adapter()
    if args.value is not None:
        value = args.value
    elif args.env_var is not None:
        env_val = os.environ.get(args.env_var)
        if env_val is None:
            raise GfoError(
                _("Environment variable '{env_var}' is not set.").format(env_var=args.env_var)
            )
        value = env_val
    else:
        if args.file is None:
            raise GfoError(_("Specify --value, --env-var, or --file."))
        value = read_file_arg(args.file).strip()
    scope = getattr(args, "org", None)
    secret = adapter.set_secret(args.name, value, scope=scope)
    output(secret, fmt=fmt, jq=jq)


def handle_delete(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo secret delete <name> のハンドラ。"""
    adapter = get_adapter()
    scope = getattr(args, "org", None)
    adapter.delete_secret(args.name, scope=scope)
    print(_("Deleted secret '{name}'.").format(name=args.name))
