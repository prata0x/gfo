"""データクラスのリストを table / json / plain 形式に変換して stdout に出力する。"""

from __future__ import annotations

import dataclasses
import json
import subprocess  # nosec B404 - jq is a fixed, well-known command
import unicodedata
from typing import Any

from gfo.exceptions import GfoError
from gfo.i18n import _


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


def _field_str(val: Any) -> str:
    """フィールド値を文字列化する。None は空文字列に変換する。"""
    return "" if val is None else str(val)


def _sanitize_for_table(val: str) -> str:
    """テーブル表示用に改行・タブをエスケープする。"""
    return val.replace("\n", "\\n").replace("\r", "\\r").replace("\t", " ")


def _sanitize_for_plain(val: str) -> str:
    """プレーン形式用にタブをエスケープする（区切り文字との混同を避ける）。"""
    return val.replace("\t", "\\t")


def apply_jq_filter(json_str: str, expression: str) -> str:
    """JSON 文字列に jq 式を適用して結果を返す。

    Args:
        json_str: 入力 JSON 文字列
        expression: jq 式（例: '.[].title'）

    Returns:
        jq 適用後の文字列

    Raises:
        GfoError: jq コマンドが見つからない場合、または jq がエラーを返した場合
    """
    try:
        # jq の `recurse` 等で無限生成式を書かれてもプロセスが固まらないよう
        # 明示的に timeout を設定する (60 秒)。
        result = subprocess.run(  # nosec B603 B607 - jq is a fixed command, expression is user-provided filter
            ["jq", expression],
            input=json_str,
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
        return result.stdout.rstrip("\n")
    except FileNotFoundError as e:
        raise GfoError(
            _("jq command not found. Install it from https://jqlang.github.io/jq/")
        ) from e
    except subprocess.TimeoutExpired as e:
        raise GfoError(_("jq filter timed out after 60 seconds.")) from e
    except subprocess.CalledProcessError as e:
        raise GfoError(_("jq filter error: {error}").format(error=e.stderr.strip())) from e


def format_error_json(err: GfoError) -> str:
    """GfoError を JSON 文字列にフォーマットする。"""
    d: dict[str, Any] = {
        "error": err.error_code,
        "message": str(err),
        "exit_code": int(err.exit_code),
    }
    if hasattr(err, "hint") and err.hint:
        d["hint"] = err.hint
    return json.dumps(d, ensure_ascii=False)


def output(
    data: Any, *, fmt: str = "table", fields: list[str] | None = None, jq: str | None = None
) -> None:
    """データを指定フォーマットで stdout に出力する。"""
    # handle_schema() 等から _resolve_format() を経由せず直接呼ばれるため、
    # jq 指定時に fmt が "json" でない場合の防御的な上書きが必要
    if jq and fmt != "json":
        fmt = "json"
    if isinstance(data, list):
        items = data
    else:
        items = [data]

    if not items:
        if fmt == "json":
            json_str = "[]"
            if jq is not None:
                print(apply_jq_filter(json_str, jq))
            else:
                print(json_str)
        elif fmt == "plain":
            pass  # plain は空行なしで終了
        else:
            print(_("No results found."))
        return

    if fields is None:
        fields = [f.name for f in dataclasses.fields(items[0])]

    if fmt == "json":
        json_str = format_json(items)
        if jq is not None:
            print(apply_jq_filter(json_str, jq))
        else:
            print(json_str)
    elif fmt == "plain":
        print(format_plain(items, fields))
    else:
        # fmt は通常 "table"。未知の値が渡された場合もテーブルにフォールバックする
        print(format_table(items, fields))


def format_table(items: list, fields: list[str]) -> str:
    """テーブル形式にフォーマットする。"""
    headers = [f.upper() for f in fields]

    rows: list[list[str]] = []
    for item in items:
        d = dataclasses.asdict(item)
        rows.append([_sanitize_for_table(_field_str(d.get(f))) for f in fields])

    widths = [_display_width(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], _display_width(val))

    lines: list[str] = []
    header_line = "  ".join(_pad_right(h, w) for h, w in zip(headers, widths, strict=True))
    lines.append(header_line.rstrip())
    sep_line = "  ".join("-" * w for w in widths)
    lines.append(sep_line.rstrip())
    for row in rows:
        data_line = "  ".join(_pad_right(val, w) for val, w in zip(row, widths, strict=True))
        lines.append(data_line.rstrip())

    return "\n".join(lines)


def format_json(items: list) -> str:
    """JSON 形式にフォーマットする。"""
    dicts = [dataclasses.asdict(item) for item in items]
    return json.dumps(dicts, indent=2, ensure_ascii=False, default=str)


def format_plain(items: list, fields: list[str]) -> str:
    """プレーン形式にフォーマットする。タブ区切り、ヘッダーなし。"""
    lines: list[str] = []
    for item in items:
        d = dataclasses.asdict(item)
        lines.append("\t".join(_sanitize_for_plain(_field_str(d.get(f))) for f in fields))
    return "\n".join(lines)


def output_grouped(
    groups: dict[str, list],
    *,
    fields: list[str],
    fmt: str,
    jq: str | None = None,
    labels: dict[str, str] | None = None,
    empty_message: str | None = None,
) -> None:
    """グループ分けされたデータを出力する共通関数。

    `gfo pr status` / `gfo issue status` のように "created" / "assigned" のような
    複数セクションを 1 つの出力にまとめるためのヘルパー。

    - json: `{key: [asdict(item), ...]}` を 1 つの JSON にして出力 (jq 適用可)
    - plain / table: 各セクションを順にタイトル行 + テーブル / 空メッセージで出力

    Args:
        groups: セクションキー (JSON 安定キー) → アイテムリスト の OrderedDict 相当。
                JSON 出力のキーになるため、i18n を通さない安定文字列を渡すこと。
        fields: テーブル / plain で表示するフィールド名一覧
        fmt: "json" | "table" | "plain"
        jq: jq 式 (json モード時のみ適用)
        labels: table / plain 出力時にセクションタイトルとして使う i18n 済み文字列。
                未指定の場合は `groups` のキーをそのままタイトルにする。
        empty_message: 空セクション時のメッセージ (デフォルト "No results found.")
    """
    if fmt == "json" or jq is not None:
        data = {key: [dataclasses.asdict(item) for item in items] for key, items in groups.items()}
        json_str = json.dumps(data, indent=2, ensure_ascii=False, default=str)
        if jq is not None:
            print(apply_jq_filter(json_str, jq))
        else:
            print(json_str)
        return

    empty = empty_message if empty_message is not None else _("  No results found.")
    first = True
    for key, items in groups.items():
        if not first:
            print()
        first = False
        title = (labels or {}).get(key, key)
        print(title)
        if items:
            print(format_table(items, fields) if fmt != "plain" else format_plain(items, fields))
        else:
            print(empty)
