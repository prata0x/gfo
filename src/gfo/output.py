"""データクラスのリストを table / json / plain 形式に変換して stdout に出力する。"""

from __future__ import annotations

import dataclasses
import json
from typing import Any


def output(data: Any, *, fmt: str = "table", fields: list[str] | None = None) -> None:
    """データを指定フォーマットで stdout に出力する。"""
    if isinstance(data, list):
        items = data
    else:
        items = [data]

    if not items:
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
        rows.append([str(d.get(f, "")) for f in fields])

    widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(val))

    lines: list[str] = []
    header_line = "  ".join(h.ljust(w) for h, w in zip(headers, widths))
    lines.append(header_line.rstrip())
    sep_line = "  ".join("-" * w for w in widths)
    lines.append(sep_line.rstrip())
    for row in rows:
        data_line = "  ".join(val.ljust(w) for val, w in zip(row, widths))
        lines.append(data_line.rstrip())

    return "\n".join(lines)


def format_json(items: list) -> str:
    """JSON 形式にフォーマットする。"""
    dicts = [dataclasses.asdict(item) for item in items]
    data = dicts[0] if len(dicts) == 1 else dicts
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


def format_plain(items: list, fields: list[str]) -> str:
    """プレーン形式にフォーマットする。タブ区切り、ヘッダーなし。"""
    lines: list[str] = []
    for item in items:
        d = dataclasses.asdict(item)
        lines.append("\t".join(str(d.get(f, "")) for f in fields))
    return "\n".join(lines)
