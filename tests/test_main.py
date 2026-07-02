"""__main__.py のテスト（python -m gfo エントリポイント）。"""

from __future__ import annotations

import json
import os
import subprocess
import sys


def test_python_m_gfo_no_args(tmp_path):
    """python -m gfo は引数なしで exit code 1 を返す（auto-JSON 無効時は help）。"""
    env = {**os.environ, "GFO_NO_AUTO_JSON": "1", "XDG_CONFIG_HOME": str(tmp_path)}
    result = subprocess.run(
        [sys.executable, "-m", "gfo"],
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert result.returncode == 1
    assert "gfo" in result.stdout  # help テキスト


def test_python_m_gfo_no_args_non_tty_json(tmp_path):
    """python -m gfo は非 TTY の auto-JSON で構造化エラーを stderr に返す。"""
    env = {**os.environ, "XDG_CONFIG_HOME": str(tmp_path)}
    env.pop("GFO_NO_AUTO_JSON", None)
    result = subprocess.run(
        [sys.executable, "-m", "gfo"],
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert result.returncode == 1
    data = json.loads(result.stderr)
    assert data["error"] == "general_error"
    assert data["exit_code"] == 1


def test_python_m_gfo_version():
    """python -m gfo --version は exit code 0 を返す。"""
    result = subprocess.run(
        [sys.executable, "-m", "gfo", "--version"],
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0
    assert "gfo" in result.stdout
