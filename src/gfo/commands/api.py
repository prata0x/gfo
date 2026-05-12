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
    path = args.path
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
