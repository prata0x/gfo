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


def _parse_headers(header_list: list[str] | None) -> dict[str, str]:
    """--header 引数をパースして dict に変換する。"""
    if not header_list:
        return {}
    headers: dict[str, str] = {}
    for h in header_list:
        if ":" not in h:
            raise ConfigError(_("Invalid header format: '{h}'. Use 'Key: Value'.").format(h=h))
        key, value = h.split(":", 1)
        headers[key.strip()] = value.strip()
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

    if jq:
        print(apply_jq_filter(body, jq))
    else:
        print(body)
