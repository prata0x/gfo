"""gfo.i18n モジュールのテスト。"""

from __future__ import annotations

import importlib
import os
from unittest import mock

import gfo.i18n


def test_fallback_returns_english():
    """LANGUAGE 未設定時（fallback）は英語がそのまま返る。"""
    with mock.patch.dict(os.environ, {"LANGUAGE": "C"}, clear=False):
        mod = importlib.reload(gfo.i18n)
        assert mod._("Git Forge Operator") == "Git Forge Operator"
        assert mod._("No results found.") == "No results found."


def test_japanese_locale():
    """LANGUAGE=ja 時は日本語翻訳が返る。"""
    with mock.patch.dict(os.environ, {"LANGUAGE": "ja"}, clear=False):
        mod = importlib.reload(gfo.i18n)
        assert mod._("Git Forge Operator") == "Git Forge Operator"
        assert mod._("No results found.") == "結果が見つかりません。"


def test_format_placeholders():
    """プレースホルダー付き翻訳文字列が正しく動作する。"""
    with mock.patch.dict(os.environ, {"LANGUAGE": "ja"}, clear=False):
        mod = importlib.reload(gfo.i18n)
        result = mod._("Deleted issue '{number}'.").format(number=42)
        assert result == "Issue '42' を削除しました。"


def test_format_placeholders_english():
    """英語 fallback でもプレースホルダーが正しく動作する。"""
    with mock.patch.dict(os.environ, {"LANGUAGE": "C"}, clear=False):
        mod = importlib.reload(gfo.i18n)
        result = mod._("Deleted issue '{number}'.").format(number=42)
        assert result == "Deleted issue '42'."


def test_unknown_msgid_returns_original():
    """未登録メッセージはそのまま返る（fallback 動作）。"""
    with mock.patch.dict(os.environ, {"LANGUAGE": "ja"}, clear=False):
        mod = importlib.reload(gfo.i18n)
        assert mod._("some unknown message") == "some unknown message"


def test_windows_locale_fallback():
    """Windows ロケール名 (Japanese_Japan) が POSIX 形式に正規化され日本語翻訳が返る。"""
    env = {k: v for k, v in os.environ.items() if k != "LANGUAGE"}
    with (
        mock.patch.dict(os.environ, env, clear=True),
        mock.patch("locale.getlocale", return_value=("Japanese_Japan", "932")),
    ):
        mod = importlib.reload(gfo.i18n)
        assert mod._("No results found.") == "結果が見つかりません。"


def test_language_empty_string_fallback():
    """LANGUAGE="" 空文字列の場合は OS ロケールにフォールバックする。"""
    with (
        mock.patch.dict(os.environ, {"LANGUAGE": ""}, clear=False),
        mock.patch("locale.getlocale", return_value=("ja_JP", "UTF-8")),
    ):
        mod = importlib.reload(gfo.i18n)
        assert mod._("No results found.") == "結果が見つかりません。"


def test_ngettext_exported():
    """ngettext がエクスポートされている。"""
    assert callable(gfo.i18n.ngettext)
