"""テスト共通フィクスチャ。"""

from __future__ import annotations

import os

# gfo.i18n はモジュールロード時に LANGUAGE を参照するため、
# gfo モジュールの import より前にセットする必要がある。
os.environ.setdefault("LANGUAGE", "C")

from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """一時的な設定ディレクトリ。config.py の get_config_dir() をパッチする。"""
    d = tmp_path / "gfo_config"
    d.mkdir()
    with patch("gfo.config.get_config_dir", return_value=d):
        yield d
