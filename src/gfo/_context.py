"""CLI グローバルオプション（--remote / --repo）の値を伝搬する ContextVar。"""

from __future__ import annotations

from contextvars import ContextVar

cli_remote: ContextVar[str | None] = ContextVar("cli_remote", default=None)
cli_repo: ContextVar[str | None] = ContextVar("cli_repo", default=None)
