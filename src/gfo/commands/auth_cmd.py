"""gfo auth サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse
import getpass
import sys

import gfo.auth
import gfo.detect
from gfo.detect import normalize_host
from gfo.exceptions import ConfigError, DetectionError, GitCommandError
from gfo.i18n import _


def handle_login(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo auth login のハンドラ。"""
    if args.host:
        host = normalize_host(args.host)
    else:
        try:
            result = gfo.detect.detect_service()
            host = result.host
        except (DetectionError, GitCommandError):
            raise ConfigError(
                _("Could not detect host. Use --host option: gfo auth login --host <host>")
            )

    # トークンの取得元優先順位:
    #   1. --token-stdin (stdin から読み込み)
    #   2. --token-file (ファイルから読み込み)
    #   3. --token (argv 経由・非推奨)
    #   4. 対話的に getpass で入力
    token_stdin = getattr(args, "token_stdin", False)
    token_file = getattr(args, "token_file", None)
    if token_stdin:
        token = sys.stdin.read().strip()
        if not token:
            raise ConfigError(_("Empty token received from stdin"))
    elif token_file:
        try:
            with open(token_file, encoding="utf-8") as f:
                token = f.read().strip()
        except OSError as e:
            raise ConfigError(
                _("Cannot read token file {path}: {error}").format(path=token_file, error=e)
            ) from e
        if not token:
            raise ConfigError(_("Empty token in file {path}").format(path=token_file))
        # POSIX 系で world/group readable のファイルからトークンを読むと
        # 他ユーザに漏れうるため警告 (Windows では mode bit が同じ意味を持たないのでスキップ)
        if sys.platform != "win32":
            import os as _os
            import warnings

            try:
                mode = _os.stat(token_file).st_mode
                if mode & 0o077:
                    warnings.warn(
                        _(
                            "Token file {path} is readable by other users "
                            "(mode {mode}). Run 'chmod 600 {path}' to restrict access."
                        ).format(path=token_file, mode=oct(mode & 0o777)),
                        stacklevel=2,
                    )
            except OSError:
                # 権限取得失敗は致命傷ではないので無視
                pass
    elif args.token:
        print(
            _(
                "Warning: --token is deprecated and will be removed in a future release. "
                "Passing tokens via --token is insecure (visible in process list). "
                "Use --token-stdin or --token-file instead."
            ),
            file=sys.stderr,
        )
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
        host = normalize_host(args.host)
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


def handle_token(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo auth token のハンドラ。"""
    if args.host:
        host = normalize_host(args.host)
        # service_type を解決: ユーザー設定 > 既知ホスト > プローブ > 空文字フォールバック
        from gfo.config import get_host_config
        from gfo.detect import get_known_service_type, probe_unknown_host

        host_cfg = get_host_config(host)
        if host_cfg and "type" in host_cfg:
            service_type = host_cfg["type"]
        else:
            service_type = get_known_service_type(host) or ""
            if not service_type:
                try:
                    service_type = probe_unknown_host(host) or ""
                except Exception:
                    service_type = ""
    else:
        try:
            result = gfo.detect.detect_service()
            host = result.host
            service_type = result.service_type or ""
        except (DetectionError, GitCommandError):
            raise ConfigError(
                _("Could not detect host. Use --host option: gfo auth token --host <host>")
            )

    token = gfo.auth.resolve_token(host, service_type)
    print(token)


def handle_logout(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo auth logout のハンドラ。"""
    if args.host:
        host = normalize_host(args.host)
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
