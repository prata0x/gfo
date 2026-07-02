"""gfo auth サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse
import dataclasses
import getpass
import sys

import gfo.auth
import gfo.detect
from gfo.detect import normalize_host
from gfo.exceptions import ConfigError, DetectionError, GitCommandError
from gfo.i18n import _
from gfo.output import output


@dataclasses.dataclass
class _AuthStatusEntry:
    """auth status の 1 エントリ。共通 output() に乗せるための dataclass。"""

    host: str
    status: str
    source: str
    account: str
    active: str


def handle_login(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo auth login のハンドラ。"""
    if args.host:
        host = normalize_host(args.host)
    else:
        try:
            result = gfo.detect.detect_service()
            host = result.host
        except (DetectionError, GitCommandError) as e:
            raise ConfigError(
                _("Could not detect host. Use --host option: gfo auth login --host <host>")
            ) from e

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
    entries = [_AuthStatusEntry(**e) for e in gfo.auth.get_auth_status()]

    if fmt == "json":
        output(entries, fmt=fmt, jq=jq)
        return

    if not entries:
        if fmt != "plain":
            print(_("No tokens configured."))
        return

    # table / plain では active マーク (*) を account 列に畳み込んで表示する
    display = [
        dataclasses.replace(e, account=f"{e.account} {e.active}" if e.active else e.account)
        for e in entries
    ]
    output(display, fmt=fmt, fields=["host", "account", "status", "source"])


def handle_switch(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo auth switch のハンドラ。"""
    if args.host:
        host = normalize_host(args.host)
    else:
        try:
            result = gfo.detect.detect_service()
            host = result.host
        except (DetectionError, GitCommandError) as e:
            raise ConfigError(
                _("Could not detect host. Use --host option: gfo auth switch --host <host> ACCOUNT")
            ) from e

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
        except (DetectionError, GitCommandError) as e:
            raise ConfigError(
                _("Could not detect host. Use --host option: gfo auth token --host <host>")
            ) from e

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
        except (DetectionError, GitCommandError) as e:
            raise ConfigError(
                _("Could not detect host. Use --host option: gfo auth logout --host <host>")
            ) from e

    account = getattr(args, "account", None)
    gfo.auth.remove_token(host, account=account)

    if account:
        print(_("Logged out account '{account}' from {host}").format(account=account, host=host))
    else:
        print(_("Logged out from {host}").format(host=host))
