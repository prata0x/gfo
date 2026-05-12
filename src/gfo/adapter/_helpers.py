"""アダプター内部で共有するヘルパー関数。

`base.py` と `github_like.py` の循環参照を防ぐため、両者から参照される
ユーティリティをここに集約する。
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import TypeVar

from gfo.exceptions import GfoError

_F = TypeVar("_F", bound=Callable[..., object])


def _wrap_conversion_error(func: _F) -> _F:
    """_to_* 変換メソッド用デコレータ。

    KeyError / TypeError を捕捉して GfoError に変換する。
    """

    @functools.wraps(func)
    def wrapper(*args: object, **kwargs: object) -> object:
        try:
            return func(*args, **kwargs)
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

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
