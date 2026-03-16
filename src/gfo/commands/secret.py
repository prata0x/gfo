"""gfo secret サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse
import os

from gfo.commands import get_adapter
from gfo.exceptions import GfoError
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo secret list のハンドラ。"""
    adapter = get_adapter()
    secrets = adapter.list_secrets(limit=args.limit)
    output(secrets, fmt=fmt, fields=["name", "updated_at"], jq=jq)


def handle_set(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo secret set <name> のハンドラ。"""
    adapter = get_adapter()
    if args.value is not None:
        value = args.value
    elif args.env_var is not None:
        env_val = os.environ.get(args.env_var)
        if env_val is None:
            raise GfoError(f"Environment variable '{args.env_var}' is not set.")
        value = env_val
    else:
        if args.file is None:
            raise GfoError("Specify --value, --env-var, or --file.")
        try:
            with open(args.file) as f:
                value = f.read().strip()
        except FileNotFoundError:
            raise GfoError(f"File not found: {args.file}")
        except PermissionError:
            raise GfoError(f"Permission denied: {args.file}")
    secret = adapter.set_secret(args.name, value)
    output(secret, fmt=fmt, jq=jq)


def handle_delete(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo secret delete <name> のハンドラ。"""
    adapter = get_adapter()
    adapter.delete_secret(args.name)
    print(f"Deleted secret '{args.name}'.")
