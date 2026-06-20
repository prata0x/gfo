"""gfo api コマンドのハンドラ。アダプター層をバイパスして任意の API パスにリクエストを送る。"""

from __future__ import annotations

import argparse
import json

from gfo.adapter.registry import create_http_client
from gfo.auth import resolve_token
from gfo.config import resolve_project_config
from gfo.exceptions import ConfigError
from gfo.i18n import _
from gfo.output import apply_jq_filter

_DISALLOWED_HEADERS = {"authorization", "cookie", "host", "proxy-authorization"}


def _validate_api_path(path: str) -> str:
    """API パスがベース URL のオリジンを変えないことを検証する。

    `gfo api` の PATH は argparse の自由入力で、`HttpClient.request` は
    `base_url + path` を素朴に連結する（同一オリジン検証を持たない）。
    先頭 `/` で始まらないパス（例: `@evil.com/...`, `.evil.com/...`,
    絶対 URL）はベースの authority を差し替えてしまい、認証トークンが
    攻撃者ホストへ送出される。相対パス（先頭 `/`、ただし `//` は不可）に
    限定し、制御文字も拒否する。
    """
    if any(c in path for c in ("\r", "\n", "\x00")):
        raise ConfigError(_("PATH contains control characters; refused."))
    if not path.startswith("/") or path.startswith("//"):
        raise ConfigError(
            _(
                "PATH must be a relative path starting with '/' "
                "(e.g. '/repos/owner/repo'). Absolute URLs are not allowed."
            )
        )
    return path


def _parse_headers(header_list: list[str] | None) -> dict[str, str]:
    """--header 引数をパースして dict に変換する。

    認証ヘッダの上書きや CRLF インジェクションを防ぐため、Authorization /
    Cookie / Host / Proxy-Authorization は明示的に拒否し、値・キーに含まれる
    CR/LF/NUL を検出した時点で ConfigError にする。
    """
    if not header_list:
        return {}
    headers: dict[str, str] = {}
    for h in header_list:
        if ":" not in h:
            raise ConfigError(_("Invalid header format: '{h}'. Use 'Key: Value'.").format(h=h))
        key, value = h.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ConfigError(_("Invalid header: empty key in '{h}'.").format(h=h))
        if key.lower() in _DISALLOWED_HEADERS:
            raise ConfigError(
                _(
                    "Header '{key}' cannot be set via --header (managed by gfo). "
                    "Use gfo auth / config options instead."
                ).format(key=key)
            )
        if any(c in key for c in ("\r", "\n", "\x00")) or any(
            c in value for c in ("\r", "\n", "\x00")
        ):
            raise ConfigError(
                _("Header '{key}' contains control characters; refused.").format(key=key)
            )
        headers[key] = value
    return headers


def handle_api(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo api のハンドラ。"""
    config = resolve_project_config()
    token = resolve_token(config.host, config.service_type)
    client = create_http_client(config.service_type, config.api_url, token)

    method = args.method.upper()
    path = _validate_api_path(args.path)
    headers = _parse_headers(getattr(args, "header", None))
    data = getattr(args, "data", None)
    try:
        json_data = json.loads(data) if data else None
    except json.JSONDecodeError as e:
        raise ConfigError(_("Invalid JSON in --data: {err}").format(err=e)) from e

    resp = client.request(method, path, json=json_data, headers=headers)
    body = resp.text

    if jq is not None:
        print(apply_jq_filter(body, jq))
    else:
        print(body)
