"""アダプター内部で共有するヘルパー関数。

`base.py` と `github_like.py` の循環参照を防ぐため、両者から参照される
ユーティリティをここに集約する。
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import TypeVar
from urllib.parse import urlparse

from gfo.exceptions import GfoError
from gfo.i18n import _

_F = TypeVar("_F", bound=Callable[..., object])


def _wrap_conversion_error(func: _F) -> _F:
    """_to_* 変換メソッド用デコレータ。

    KeyError / TypeError / AttributeError を捕捉して GfoError に変換する。
    AttributeError も API レスポンス形式違いで発生し得るため、一貫して
    GfoError でラップする (例: `data["user"]` が想定外に str で来て
    `.get("login")` が AttributeError を投げるケース)。
    """

    @functools.wraps(func)
    def wrapper(*args: object, **kwargs: object) -> object:
        try:
            return func(*args, **kwargs)
        except (KeyError, TypeError, AttributeError) as e:
            raise GfoError(
                _("Unexpected API response: missing field {error}").format(error=e)
            ) from e

    return wrapper  # type: ignore[return-value]


def _mask_token_in_exception(exc: BaseException, token: str | None) -> None:
    """例外の args 内の token 文字列を *** に置換する。

    migrate_repository / create_push_mirror など、payload に秘匿トークンを
    含めるメソッドで使う共通ユーティリティ。サーバー応答エラー本文や
    ネットワーク例外メッセージにトークンが漏れるのを防ぐ。
    """
    if not token or not exc.args:
        return
    new_args = tuple(a.replace(token, "***") if isinstance(a, str) else a for a in exc.args)
    if new_args != exc.args:
        exc.args = new_args


def _web_base_from_api_url(base_url: str, *, omit_default_ports: bool = False) -> str:
    """API base_url から Web UI ベース URL を構築する。

    `urlparse(...).hostname` は IPv6 リテラルのブラケットを剥がすため、
    ``f"{scheme}://{hostname}{port}"`` で再構築すると ``::1:3000`` のように
    host:port 区切りと区別できなくなる (#582 / #796)。IPv6 リテラルは再構築時に
    ブラケットを保持する。

    ``omit_default_ports`` が真の場合、ポートが 80/443 なら出力から省略する
    (GitBucket の既存挙動を維持するため)。
    """
    parsed = urlparse(base_url)
    hostname = parsed.hostname or ""
    if ":" in hostname:
        hostname = f"[{hostname}]"
    port = parsed.port
    if omit_default_ports and port in (80, 443):
        port_str = ""
    else:
        port_str = f":{port}" if port else ""
    return f"{parsed.scheme}://{hostname}{port_str}"
