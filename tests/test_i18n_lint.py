"""ユーザー向けエラーメッセージ・警告が _() を通っているかの静的検査（AST ベース）。

`raise GfoError("literal")` / `raise ConfigError(f"...")` のような、翻訳を通らない
文字列リテラルを直接 message に渡す raise を検出する。正しい形は
`raise ConfigError(_("No tokens configured for host: {host}").format(host=host))`。
`warnings.warn("literal")` も同様に検出する（warnings.warn() はユーザーに直接表示される
点で例外メッセージと同じ「ユーザー向けメッセージ」であり、.claude/rules/01-exceptions.md
の対象に含まれる）。

対象は src/gfo 配下の全モジュール（adapter/ と commands/ を含む）。
`ValueError` 等の内部契約エラーは対象外（rules 01 参照）。
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_SRC_DIR = Path(__file__).parent.parent / "src" / "gfo"

# 文字列 message をコンストラクタに直接受け取るユーザー向け例外。
# NotSupportedError / UnsupportedServiceError は識別子（service 名等）を受け取り
# 内部で i18n 済みテンプレートに埋め込むため対象外。
_USER_FACING_EXCEPTIONS = {
    "GfoError",
    "ConfigError",
    "AuthError",
    "DetectionError",
    "HttpError",
    "ValidationError",
}

_MODULES = sorted(_SRC_DIR.rglob("*.py"))


def _exception_name(func: ast.expr) -> str | None:
    """raise 対象の Call から例外クラス名を取り出す（Name / Attribute 両対応）。"""
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _is_untranslated_literal(arg: ast.expr) -> bool:
    """引数が _() を通らない文字列リテラル（f-string / .format() 込み）かを判定する。"""
    if isinstance(arg, ast.Constant):
        return isinstance(arg.value, str)
    if isinstance(arg, ast.JoinedStr):  # f-string
        return True
    # "literal {x}".format(...) — _( "..." ).format(...) は func.value が Call なので False
    if (
        isinstance(arg, ast.Call)
        and isinstance(arg.func, ast.Attribute)
        and arg.func.attr == "format"
    ):
        return _is_untranslated_literal(arg.func.value)
    return False


def _is_warnings_warn_call(func: ast.expr) -> bool:
    """`warnings.warn(...)` 呼び出しかを判定する（`import warnings` 前提の Attribute 形式のみ）。"""
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "warn"
        and (isinstance(func.value, ast.Name) and func.value.id == "warnings")
    )


def _iter_violations(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    violations: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
            if _exception_name(node.exc.func) not in _USER_FACING_EXCEPTIONS:
                continue
            if any(_is_untranslated_literal(arg) for arg in node.exc.args):
                violations.append(node.lineno)
        elif (
            isinstance(node, ast.Call)
            and _is_warnings_warn_call(node.func)
            and node.args
            and _is_untranslated_literal(node.args[0])
        ):
            violations.append(node.lineno)
    return violations


@pytest.mark.parametrize("path", _MODULES, ids=lambda p: str(p.relative_to(_SRC_DIR)))
def test_user_facing_error_messages_are_translated(path: Path):
    violations = _iter_violations(path)
    assert not violations, (
        f"{path.relative_to(_SRC_DIR)}:{violations} — user-facing exception/warning raised with a "
        "string literal that does not go through _(). Wrap the message in _() and add a ja "
        "translation to gfo.po (see .claude/rules/01-exceptions.md)."
    )


# ── .po カバレッジ検査 ──

_PO_PATH = _SRC_DIR / "locale" / "ja" / "LC_MESSAGES" / "gfo.po"


def _parse_po_msgids(po_path: Path) -> set[str]:
    """PO ファイルから msgid の集合を返す（hatch_build.py と同じ単純パーサ）。"""
    msgids: set[str] = set()
    lines = po_path.read_text(encoding="utf-8").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("msgid "):
            msgid = ast.literal_eval(line[6:])
            i += 1
            while i < len(lines) and lines[i].strip().startswith('"'):
                msgid += ast.literal_eval(lines[i].strip())
                i += 1
            msgids.add(msgid)
        else:
            i += 1
    return msgids


def _collect_source_msgids(path: Path) -> set[str]:
    """モジュール内の _() 呼び出しの文字列リテラル msgid を収集する。"""
    msgids: set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            msgids.add(node.args[0].value)
    return msgids


def test_all_msgids_have_ja_translation():
    """src/gfo 配下の全 _() msgid が gfo.po に登録されている（未訳の混入防止）。"""
    po_msgids = _parse_po_msgids(_PO_PATH)
    missing: dict[str, list[str]] = {}
    for path in _MODULES:
        for msgid in _collect_source_msgids(path):
            if msgid not in po_msgids:
                missing.setdefault(str(path.relative_to(_SRC_DIR)), []).append(msgid)
    assert not missing, (
        f"msgids missing from gfo.po: {missing} — add a ja translation entry for each."
    )
