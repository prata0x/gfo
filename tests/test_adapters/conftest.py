"""test_adapters 共通フィクスチャ。"""

from __future__ import annotations

import pytest
import responses

from gfo.http import HttpClient
from gfo.adapter.github import GitHubAdapter
from gfo.adapter.gitlab import GitLabAdapter


BASE_URL = "https://api.github.com"
GITLAB_BASE_URL = "https://gitlab.com/api/v4"


@pytest.fixture
def mock_responses():
    with responses.RequestsMock() as rsps:
        yield rsps


@pytest.fixture
def github_client():
    return HttpClient(BASE_URL, auth_header={"Authorization": "Bearer test-token"})


@pytest.fixture
def github_adapter(github_client):
    return GitHubAdapter(github_client, "test-owner", "test-repo")


@pytest.fixture
def gitlab_client():
    return HttpClient(GITLAB_BASE_URL, auth_header={"Private-Token": "test-token"})


@pytest.fixture
def gitlab_adapter(gitlab_client):
    return GitLabAdapter(gitlab_client, "test-owner", "test-repo")
