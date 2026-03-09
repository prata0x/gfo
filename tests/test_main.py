"""__main__.py のテスト（python -m gfo エントリポイント）。"""

from __future__ import annotations

import subprocess
import sys


def test_python_m_gfo_no_args():
    """python -m gfo は引数なしで exit code 1 を返す。"""
    result = subprocess.run(
        [sys.executable, "-m", "gfo"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "gfo" in result.stdout  # help テキスト


def test_python_m_gfo_version():
    """python -m gfo --version は exit code 0 を返す。"""
    result = subprocess.run(
        [sys.executable, "-m", "gfo", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "gfo" in result.stdout
