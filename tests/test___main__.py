"""gfo/__main__.py のテスト。python -m gfo のエントリポイント動作を確認する。"""

from __future__ import annotations

import runpy
import sys
from unittest.mock import patch

import pytest


def test_main_module_exits_with_1_when_no_args():
    """引数なしで python -m gfo を実行すると help を表示して終了コード 1 を返す。"""
    with patch.object(sys, "argv", ["gfo"]):
        with pytest.raises(SystemExit) as exc_info:
            runpy.run_module("gfo", run_name="__main__", alter_sys=True)
    assert exc_info.value.code == 1
