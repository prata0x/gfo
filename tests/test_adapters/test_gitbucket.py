"""GitBucketAdapter のテスト。"""

from __future__ import annotations

import responses

from gfo.adapter.gitbucket import GitBucketAdapter
from gfo.adapter.github import GitHubAdapter
from gfo.adapter.registry import get_adapter_class


BASE = "https://gitbucket.example.com/api/v3"
REPOS = f"{BASE}/repos/test-owner/test-repo"


def _pr_data(*, number=1, state="open", merged_at=None):
    return {
        "number": number,
        "title": f"PR #{number}",
        "body": "description",
        "state": state,
        "merged_at": merged_at,
        "user": {"login": "author1"},
        "head": {"ref": "feature"},
        "base": {"ref": "main"},
        "draft": False,
        "html_url": f"https://gitbucket.example.com/test-owner/test-repo/pulls/{number}",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-02T00:00:00Z",
    }


class TestRegistry:
    def test_registered(self):
        assert get_adapter_class("gitbucket") is GitBucketAdapter


class TestInheritance:
    def test_is_github_adapter(self, gitbucket_adapter):
        assert isinstance(gitbucket_adapter, GitHubAdapter)

    def test_service_name(self, gitbucket_adapter):
        assert gitbucket_adapter.service_name == "GitBucket"


class TestListPullRequests:
    def test_open(self, mock_responses, gitbucket_adapter):
        mock_responses.add(
            responses.GET, f"{REPOS}/pulls",
            json=[_pr_data()], status=200,
        )
        prs = gitbucket_adapter.list_pull_requests()
        assert len(prs) == 1
        assert prs[0].state == "open"
        assert prs[0].number == 1
