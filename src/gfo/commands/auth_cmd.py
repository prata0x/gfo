"""gfo auth サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse
import getpass
import sys

import gfo.auth
import gfo.detect
from gfo.exceptions import ConfigError, DetectionError, GitCommandError
from gfo.i18n import _


def handle_login(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo auth login のハンドラ。"""
    if args.host:
        host = args.host
    else:
        try:
            result = gfo.detect.detect_service()
            host = result.host
        except (DetectionError, GitCommandError):
            raise ConfigError(
                _("Could not detect host. Use --host option: gfo auth login --host <host>")
            )

    if args.token:
        print(_("Warning: passing tokens via --token is insecure."), file=sys.stderr)
        token = args.token
    else:
        token = getpass.getpass(_("Token: "))

    account = getattr(args, "account", "default")
    gfo.auth.save_token(host, token, account=account)
    print(_("Token saved for {host} (account: {account})").format(host=host, account=account))


def handle_status(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo auth status のハンドラ。"""
    entries = gfo.auth.get_auth_status()

    if not entries:
        if fmt == "json":
            print("[]")
        else:
            print(_("No tokens configured."))
        return

    if fmt == "json":
        import json

        print(json.dumps(entries, ensure_ascii=False, indent=2))
        return

    col_widths = {
        "host": max(len(e["host"]) for e in entries),
        "account": max(
            (len(e["account"]) + len(e["active"]) + (1 if e["active"] else 0)) for e in entries
        ),
        "status": max(len(e["status"]) for e in entries),
        "source": max(len(e["source"]) for e in entries),
    }
    col_widths["host"] = min(max(col_widths["host"], 4), 50)
    col_widths["account"] = min(max(col_widths["account"], 7), 30)
    col_widths["status"] = min(max(col_widths["status"], 6), 20)
    col_widths["source"] = min(max(col_widths["source"], 6), 40)

    header = (
        f"{_('HOST'):<{col_widths['host']}}  "
        f"{_('ACCOUNT'):<{col_widths['account']}}  "
        f"{_('STATUS'):<{col_widths['status']}}  "
        f"{_('SOURCE'):<{col_widths['source']}}"
    )
    print(header)
    print("-" * len(header))
    for e in entries:
        account_display = f"{e['account']} {e['active']}" if e["active"] else e["account"]
        print(
            f"{e['host']:<{col_widths['host']}}  "
            f"{account_display:<{col_widths['account']}}  "
            f"{e['status']:<{col_widths['status']}}  "
            f"{e['source']:<{col_widths['source']}}"
        )


def handle_switch(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo auth switch のハンドラ。"""
    if args.host:
        host = args.host
    else:
        try:
            result = gfo.detect.detect_service()
            host = result.host
        except (DetectionError, GitCommandError):
            raise ConfigError(
                _("Could not detect host. Use --host option: gfo auth switch --host <host> ACCOUNT")
            )

    gfo.auth.switch_account(host, args.account)
    print(_("Switched to account '{account}' for {host}").format(account=args.account, host=host))


def handle_logout(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo auth logout のハンドラ。"""
    if args.host:
        host = args.host
    else:
        try:
            result = gfo.detect.detect_service()
            host = result.host
        except (DetectionError, GitCommandError):
            raise ConfigError(
                _("Could not detect host. Use --host option: gfo auth logout --host <host>")
            )

    account = getattr(args, "account", None)
    gfo.auth.remove_token(host, account=account)

    if account:
        print(_("Logged out account '{account}' from {host}").format(account=account, host=host))
    else:
        print(_("Logged out from {host}").format(host=host))
