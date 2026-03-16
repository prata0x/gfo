"""test_commands 共通フィクスチャ。"""

from __future__ import annotations

import argparse
import contextlib
from unittest.mock import MagicMock, patch

import pytest

from gfo.adapter.base import PullRequest
from gfo.config import ProjectConfig


@pytest.fixture
def sample_config():
    return ProjectConfig(
        service_type="github",
        host="github.com",
        api_url="https://api.github.com",
        owner="test-owner",
        repo="test-repo",
    )


@pytest.fixture
def sample_pr():
    return PullRequest(
        number=1,
        title="Test PR",
        body="Test body",
        state="open",
        author="test-user",
        source_branch="feature/test",
        target_branch="main",
        draft=False,
        url="https://github.com/test-owner/test-repo/pull/1",
        created_at="2024-01-01T00:00:00Z",
        updated_at=None,
    )


def make_args(**kwargs) -> argparse.Namespace:
    """argparse.Namespace を簡単に生成するヘルパー。"""
    return argparse.Namespace(**kwargs)


@contextlib.contextmanager
def patch_adapter(module_path: str):
    """get_adapter をモックに差し替える共通コンテキストマネージャ。

    Usage::

        with patch_adapter("gfo.commands.org") as adapter:
            adapter.list_organizations.return_value = [...]
            org_cmd.handle_list(args, fmt="table")
    """
    adapter = MagicMock()
    with patch(f"{module_path}.get_adapter", return_value=adapter):
        yield adapter
