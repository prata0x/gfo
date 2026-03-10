"""test_commands 共通フィクスチャ。"""

from __future__ import annotations

import argparse

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
