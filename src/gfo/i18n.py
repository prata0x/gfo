"""gettext ベースの国際化モジュール。"""

from __future__ import annotations

import gettext
import locale
import os
from pathlib import Path

_LOCALE_DIR = Path(__file__).parent / "locale"
_DOMAIN = "gfo"


def _get_languages() -> list[str] | None:
    """環境変数からロケールを解決する。

    LANGUAGE 環境変数を最優先で使用する。
    未設定の場合は OS のデフォルトロケールにフォールバックする。
    """
    # LANGUAGE は GNU gettext の標準的な言語選択変数
    val = os.environ.get("LANGUAGE")
    if val:
        return [lang for lang in val.split(":") if lang]
    # OS のデフォルトロケール（Windows 対応）
    try:
        os_locale = locale.getlocale()[0]
        if os_locale:
            code = os_locale.split(".")[0]
            # Windows の "Japanese_Japan" → "ja_JP" に正規化
            lang_part = code.split("_")[0].lower()
            alias = locale.locale_alias.get(lang_part, "")
            if alias:
                code = alias.split(".")[0]
            return [code]
    except Exception:  # nosec B110 - locale detection is best-effort
        pass
    return None


_translation = gettext.translation(
    _DOMAIN,
    localedir=str(_LOCALE_DIR),
    languages=_get_languages(),
    fallback=True,
)

_ = _translation.gettext
ngettext = _translation.ngettext
