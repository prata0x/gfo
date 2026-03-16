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

    gfo.auth.save_token(host, token)
    print(_("Token saved for {host}").format(host=host))


def handle_status(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo auth status のハンドラ。"""
    entries = gfo.auth.get_auth_status()

    if not entries:
        print(_("No tokens configured."))
        return

    col_widths = {
        "host": max(len(e["host"]) for e in entries),
        "status": max(len(e["status"]) for e in entries),
        "source": max(len(e["source"]) for e in entries),
    }
    col_widths["host"] = min(max(col_widths["host"], 4), 50)
    col_widths["status"] = min(max(col_widths["status"], 6), 20)
    col_widths["source"] = min(max(col_widths["source"], 6), 40)

    header = (
        f"{_('HOST'):<{col_widths['host']}}  "
        f"{_('STATUS'):<{col_widths['status']}}  "
        f"{_('SOURCE'):<{col_widths['source']}}"
    )
    print(header)
    print("-" * len(header))
    for e in entries:
        print(
            f"{e['host']:<{col_widths['host']}}  "
            f"{e['status']:<{col_widths['status']}}  "
            f"{e['source']:<{col_widths['source']}}"
        )
