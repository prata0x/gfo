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

    GNU gettext の優先順位 LANGUAGE > LC_ALL > LC_MESSAGES > LANG を尊重し、
    最後のフォールバックとして OS のデフォルトロケール (Windows 対応) を見る。
    """
    # 1. LANGUAGE (GNU gettext 専用): コロン区切り複数言語
    val = os.environ.get("LANGUAGE")
    if val:
        return [lang for lang in val.split(":") if lang]
    # 2. LC_ALL > LC_MESSAGES > LANG (POSIX 標準の言語設定)
    for env_name in ("LC_ALL", "LC_MESSAGES", "LANG"):
        raw = os.environ.get(env_name)
        if not raw:
            continue
        # "ja_JP.UTF-8" → "ja_JP" のように encoding 部分を切り落とす
        code = raw.split(".")[0].split("@")[0]
        if code and code != "C":
            return [code]
    # 3. OS のデフォルトロケール（Windows 対応）
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
