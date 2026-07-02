"""ユーザー向けエラーメッセージが _() を通っているかの静的検査（AST ベース）。

`raise GfoError("literal")` / `raise ConfigError(f"...")` のような、翻訳を通らない
文字列リテラルを直接 message に渡す raise を検出する。正しい形は
`raise ConfigError(_("No tokens configured for host: {host}").format(host=host))`。

対象は src/gfo 直下のトップレベルモジュールのみ。adapter/ と commands/ には
未対応箇所が残っているため対象外（issue #83 で追跡）。
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

_MODULES = sorted(_SRC_DIR.glob("*.py"))


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


def _iter_violations(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    violations: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Raise) or not isinstance(node.exc, ast.Call):
            continue
        if _exception_name(node.exc.func) not in _USER_FACING_EXCEPTIONS:
            continue
        if any(_is_untranslated_literal(arg) for arg in node.exc.args):
            violations.append(node.lineno)
    return violations


@pytest.mark.parametrize("path", _MODULES, ids=lambda p: p.name)
def test_user_facing_error_messages_are_translated(path: Path):
    violations = _iter_violations(path)
    assert not violations, (
        f"{path.name}:{violations} — user-facing exception raised with a string literal "
        "that does not go through _(). Wrap the message in _() and add a ja translation "
        "to gfo.po (see .claude/rules/01-exceptions.md)."
    )
