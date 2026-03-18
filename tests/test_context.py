"""_context.py の ContextVar 単体テスト。"""

from __future__ import annotations

from gfo._context import cli_remote


def test_cli_remote_default_is_none():
    assert cli_remote.get() is None


def test_cli_remote_set_and_reset():
    token = cli_remote.set("github")
    assert cli_remote.get() == "github"
    cli_remote.reset(token)
    assert cli_remote.get() is None


def test_set_does_not_leak_between_calls():
    """set → reset 後に別の値を設定しても前回の値は残らない。"""
    t1 = cli_remote.set("first")
    cli_remote.reset(t1)
    t2 = cli_remote.set("second")
    assert cli_remote.get() == "second"
    cli_remote.reset(t2)
    assert cli_remote.get() is None
