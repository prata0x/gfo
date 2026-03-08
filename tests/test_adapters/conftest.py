"""test_adapters 共通フィクスチャ。"""

from __future__ import annotations

import pytest
import responses

from gfo.http import HttpClient
from gfo.adapter.github import GitHubAdapter


BASE_URL = "https://api.github.com"


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
