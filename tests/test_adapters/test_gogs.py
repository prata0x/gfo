"""GogsAdapter のテスト。"""

from __future__ import annotations

import pytest
import responses

from gfo.adapter.gogs import GogsAdapter
from gfo.adapter.gitea import GiteaAdapter
from gfo.adapter.registry import get_adapter_class
from gfo.exceptions import NotSupportedError


BASE = "https://gogs.example.com/api/v1"
WEB_BASE = "https://gogs.example.com"
REPOS = f"{BASE}/repos/test-owner/test-repo"


def _issue_data(*, number=1, state="open"):
    return {
        "number": number,
        "title": f"Issue #{number}",
        "body": "description",
        "state": state,
        "user": {"login": "author1"},
        "assignees": [],
        "labels": [],
        "html_url": f"{WEB_BASE}/test-owner/test-repo/issues/{number}",
        "created_at": "2025-01-01T00:00:00Z",
    }


class TestRegistry:
    def test_registered(self):
        assert get_adapter_class("gogs") is GogsAdapter


class TestInheritance:
    def test_is_gitea_adapter(self, gogs_adapter):
        assert isinstance(gogs_adapter, GiteaAdapter)

    def test_service_name(self, gogs_adapter):
        assert gogs_adapter.service_name == "Gogs"


class TestNotSupportedOperations:
    def test_list_pull_requests(self, gogs_adapter):
        with pytest.raises(NotSupportedError) as exc_info:
            gogs_adapter.list_pull_requests()
        assert exc_info.value.web_url == f"{WEB_BASE}/test-owner/test-repo/pulls"

    def test_create_pull_request(self, gogs_adapter):
        with pytest.raises(NotSupportedError) as exc_info:
            gogs_adapter.create_pull_request(title="PR", base="main", head="feature")
        assert exc_info.value.web_url == f"{WEB_BASE}/test-owner/test-repo/compare"

    def test_get_pull_request(self, gogs_adapter):
        with pytest.raises(NotSupportedError) as exc_info:
            gogs_adapter.get_pull_request(1)
        assert exc_info.value.web_url == f"{WEB_BASE}/test-owner/test-repo/pulls/1"

    def test_merge_pull_request(self, gogs_adapter):
        with pytest.raises(NotSupportedError) as exc_info:
            gogs_adapter.merge_pull_request(1)
        assert exc_info.value.web_url == f"{WEB_BASE}/test-owner/test-repo/pulls/1"

    def test_close_pull_request(self, gogs_adapter):
        with pytest.raises(NotSupportedError) as exc_info:
            gogs_adapter.close_pull_request(1)
        assert exc_info.value.web_url == f"{WEB_BASE}/test-owner/test-repo/pulls/1"

    def test_list_labels(self, gogs_adapter):
        with pytest.raises(NotSupportedError) as exc_info:
            gogs_adapter.list_labels()
        assert exc_info.value.web_url is None

    def test_create_label(self, gogs_adapter):
        with pytest.raises(NotSupportedError) as exc_info:
            gogs_adapter.create_label(name="bug")
        assert exc_info.value.web_url is None

    def test_list_milestones(self, gogs_adapter):
        with pytest.raises(NotSupportedError) as exc_info:
            gogs_adapter.list_milestones()
        assert exc_info.value.web_url is None

    def test_create_milestone(self, gogs_adapter):
        with pytest.raises(NotSupportedError) as exc_info:
            gogs_adapter.create_milestone(title="v1.0")
        assert exc_info.value.web_url is None


class TestWebUrl:
    def test_standard_url(self, gogs_adapter):
        assert gogs_adapter._web_url() == "https://gogs.example.com"

    def test_url_with_port(self, gogs_client):
        from gfo.http import HttpClient
        client = HttpClient(
            "http://gogs.local:3000/api/v1",
            auth_header={"Authorization": "token test-token"},
        )
        adapter = GogsAdapter(client, "owner", "repo")
        assert adapter._web_url() == "http://gogs.local:3000"


class TestInheritedOperations:
    def test_list_issues(self, mock_responses, gogs_adapter):
        mock_responses.add(
            responses.GET, f"{REPOS}/issues",
            json=[_issue_data()], status=200,
        )
        issues = gogs_adapter.list_issues()
        assert len(issues) == 1
        assert issues[0].number == 1
        assert issues[0].state == "open"

    def test_list_issues_pagination(self, mock_responses, gogs_adapter):
        import json as json_mod

        next_url = f"{REPOS}/issues?page=2&limit=30"
        call_count = {"n": 0}

        def callback(request):
            call_count["n"] += 1
            if call_count["n"] == 1:
                headers = {"Link": f'<{next_url}>; rel="next"'}
                return (200, headers, json_mod.dumps([_issue_data(number=1), _issue_data(number=2)]))
            return (200, {}, json_mod.dumps([_issue_data(number=3)]))

        mock_responses.add_callback(responses.GET, f"{REPOS}/issues", callback=callback)
        issues = gogs_adapter.list_issues(limit=0)
        assert len(issues) == 3
        assert call_count["n"] == 2
