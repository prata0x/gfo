"""ForgejoAdapter のテスト。"""

from __future__ import annotations

import responses

from gfo.adapter.forgejo import ForgejoAdapter
from gfo.adapter.gitea import GiteaAdapter
from gfo.adapter.registry import get_adapter_class


BASE = "https://forgejo.example.com/api/v1"
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
        "html_url": f"https://forgejo.example.com/test-owner/test-repo/pulls/{number}",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-02T00:00:00Z",
    }


class TestRegistry:
    def test_registered(self):
        assert get_adapter_class("forgejo") is ForgejoAdapter


class TestInheritance:
    def test_is_gitea_adapter(self, forgejo_adapter):
        assert isinstance(forgejo_adapter, GiteaAdapter)

    def test_service_name(self, forgejo_adapter):
        assert forgejo_adapter.service_name == "Forgejo"


class TestToPullRequest:
    def test_closed(self):
        pr = ForgejoAdapter._to_pull_request(_pr_data(state="closed", merged_at=None))
        assert pr.state == "closed"

    def test_merged(self):
        pr = ForgejoAdapter._to_pull_request(
            _pr_data(state="closed", merged_at="2025-01-01T00:00:00Z")
        )
        assert pr.state == "merged"


class TestListPullRequests:
    def test_open(self, mock_responses, forgejo_adapter):
        mock_responses.add(
            responses.GET, f"{REPOS}/pulls",
            json=[_pr_data()], status=200,
        )
        prs = forgejo_adapter.list_pull_requests()
        assert len(prs) == 1
        assert prs[0].state == "open"
        assert prs[0].number == 1

    def test_pagination(self, mock_responses, forgejo_adapter):
        import json as json_mod

        next_url = f"{REPOS}/pulls?page=2&limit=30"
        call_count = {"n": 0}

        def callback(request):
            call_count["n"] += 1
            if call_count["n"] == 1:
                headers = {"Link": f'<{next_url}>; rel="next"'}
                return (200, headers, json_mod.dumps([_pr_data(number=1), _pr_data(number=2)]))
            return (200, {}, json_mod.dumps([_pr_data(number=3)]))

        mock_responses.add_callback(responses.GET, f"{REPOS}/pulls", callback=callback)
        prs = forgejo_adapter.list_pull_requests(limit=0)
        assert len(prs) == 3
        assert call_count["n"] == 2
