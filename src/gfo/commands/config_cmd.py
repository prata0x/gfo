"""gfo config サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse
import json

from gfo.config import (
    get_config_path,
    get_config_value,
    load_user_config,
    set_config_value,
    unset_config_value,
)
from gfo.exceptions import ConfigError
from gfo.i18n import _
from gfo.output import apply_jq_filter


def handle_get(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo config get のハンドラ。"""
    value = get_config_value(args.key)
    if value is None:
        raise ConfigError(_("Key not found: {key}").format(key=args.key))

    if fmt == "json":
        json_str = json.dumps({"key": args.key, "value": value}, ensure_ascii=False, indent=2)
        print(apply_jq_filter(json_str, jq) if jq else json_str)
    else:
        print(value)


def handle_set(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo config set のハンドラ。"""
    set_config_value(args.key, args.value)
    if fmt == "json":
        json_str = json.dumps({"key": args.key, "value": args.value}, ensure_ascii=False, indent=2)
        print(apply_jq_filter(json_str, jq) if jq else json_str)


def handle_list(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo config list のハンドラ。"""
    cfg = load_user_config()

    if fmt == "json":
        json_str = json.dumps(cfg, ensure_ascii=False, indent=2)
        print(apply_jq_filter(json_str, jq) if jq else json_str)
        return

    entries = _flatten(cfg)
    if not entries:
        print(_("No configuration set."))
        return

    for key, value in entries:
        print(f"{key}={value}")


def handle_unset(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo config unset のハンドラ。"""
    removed = unset_config_value(args.key)
    if not removed:
        raise ConfigError(_("Key not found: {key}").format(key=args.key))
    if fmt == "json":
        json_str = json.dumps({"key": args.key, "removed": True}, ensure_ascii=False, indent=2)
        print(apply_jq_filter(json_str, jq) if jq else json_str)


def handle_path(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo config path のハンドラ。"""
    path = get_config_path()
    if fmt == "json":
        json_str = json.dumps({"path": str(path)}, ensure_ascii=False, indent=2)
        print(apply_jq_filter(json_str, jq) if jq else json_str)
    else:
        print(path)


def _flatten(data: dict, prefix: str = "") -> list[tuple[str, str]]:
    """ネストされた dict をフラットな (キー, 値) リストに変換する。

    ドットを含むキーは引用符で囲み、出力をそのまま get/set/unset に渡せるようにする。
    """
    entries: list[tuple[str, str]] = []
    for key, value in data.items():
        escaped = f'"{key}"' if "." in key else key
        full_key = f"{prefix}{escaped}" if not prefix else f"{prefix}.{escaped}"
        if isinstance(value, dict):
            entries.extend(_flatten(value, full_key))
        else:
            entries.append((full_key, str(value)))
    return entries
