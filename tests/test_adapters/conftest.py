"""test_adapters 共通フィクスチャ。"""

from __future__ import annotations

import pytest
import responses

from gfo.http import HttpClient
from gfo.adapter.github import GitHubAdapter
from gfo.adapter.gitlab import GitLabAdapter
from gfo.adapter.bitbucket import BitbucketAdapter
from gfo.adapter.azure_devops import AzureDevOpsAdapter


BASE_URL = "https://api.github.com"
GITLAB_BASE_URL = "https://gitlab.com/api/v4"
BITBUCKET_BASE_URL = "https://api.bitbucket.org/2.0"
AZURE_DEVOPS_BASE_URL = "https://dev.azure.com/test-org/test-project/_apis"


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


@pytest.fixture
def bitbucket_client():
    return HttpClient(BITBUCKET_BASE_URL, basic_auth=("testuser", "testpass"))


@pytest.fixture
def bitbucket_adapter(bitbucket_client):
    return BitbucketAdapter(bitbucket_client, "test-workspace", "test-repo")


@pytest.fixture
def azure_devops_client():
    return HttpClient(
        AZURE_DEVOPS_BASE_URL,
        basic_auth=("", "test-pat"),
        default_params={"api-version": "7.1"},
    )


@pytest.fixture
def azure_devops_adapter(azure_devops_client):
    return AzureDevOpsAdapter(
        azure_devops_client, "test-owner", "test-repo",
        organization="test-org", project_key="test-project",
    )
