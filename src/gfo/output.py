"""データクラスのリストを table / json / plain 形式に変換して stdout に出力する。"""

from __future__ import annotations

import dataclasses
import json
import sys
import unicodedata
from typing import Any


def _display_width(s: str) -> int:
    """文字列の表示幅を計算する。東アジア文字は幅2として計算する。"""
    width = 0
    for ch in s:
        ew = unicodedata.east_asian_width(ch)
        width += 2 if ew in ("W", "F") else 1
    return width


def _pad_right(val: str, width: int) -> str:
    """表示幅に合わせて右側をスペースでパディングする。"""
    w = _display_width(val)
    return val + " " * max(0, width - w)


def _sanitize_for_table(val: str) -> str:
    """テーブル表示用に改行・タブをエスケープする。"""
    return val.replace("\n", "\\n").replace("\r", "\\r").replace("\t", " ")


def _sanitize_for_plain(val: str) -> str:
    """プレーン形式用にタブをエスケープする（区切り文字との混同を避ける）。"""
    return val.replace("\t", "\\t")


def output(data: Any, *, fmt: str = "table", fields: list[str] | None = None) -> None:
    """データを指定フォーマットで stdout に出力する。"""
    if isinstance(data, list):
        items = data
    else:
        items = [data]

    if not items:
        if fmt == "json":
            print("[]")
        else:
            print("No results found.", file=sys.stderr)
        return

    if fields is None:
        fields = [f.name for f in dataclasses.fields(items[0])]

    if fmt == "json":
        print(format_json(items))
    elif fmt == "plain":
        print(format_plain(items, fields))
    else:
        print(format_table(items, fields))


def format_table(items: list, fields: list[str]) -> str:
    """テーブル形式にフォーマットする。"""
    headers = [f.upper() for f in fields]

    rows: list[list[str]] = []
    for item in items:
        d = dataclasses.asdict(item)
        rows.append([_sanitize_for_table(str(d.get(f, ""))) for f in fields])

    widths = [_display_width(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], _display_width(val))

    lines: list[str] = []
    header_line = "  ".join(_pad_right(h, w) for h, w in zip(headers, widths))
    lines.append(header_line.rstrip())
    sep_line = "  ".join("-" * w for w in widths)
    lines.append(sep_line.rstrip())
    for row in rows:
        data_line = "  ".join(_pad_right(val, w) for val, w in zip(row, widths))
        lines.append(data_line.rstrip())

    return "\n".join(lines)


def format_json(items: list) -> str:
    """JSON 形式にフォーマットする。"""
    dicts = [dataclasses.asdict(item) for item in items]
    data = dicts
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


def format_plain(items: list, fields: list[str]) -> str:
    """プレーン形式にフォーマットする。タブ区切り、ヘッダーなし。"""
    lines: list[str] = []
    for item in items:
        d = dataclasses.asdict(item)
        lines.append("\t".join(_sanitize_for_plain(str(d.get(f, ""))) for f in fields))
    return "\n".join(lines)
