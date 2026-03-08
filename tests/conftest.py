"""テスト共通フィクスチャ。"""

from __future__ import annotations

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


@pytest.fixture
def mock_git_config():
    """git config の読み書きをモックする dict ベースのフィクスチャ。"""
    store = {}

    def _get(key, cwd=None):
        return store.get(key)

    def _set(key, value, cwd=None):
        store[key] = value

    with patch("gfo.git_util.git_config_get", side_effect=_get), \
         patch("gfo.git_util.git_config_set", side_effect=_set):
        yield store


@pytest.fixture
def mock_remote_url():
    """git remote URL をモックするファクトリフィクスチャ。"""
    def _factory(url: str):
        return patch("gfo.git_util.get_remote_url", return_value=url)
    return _factory
