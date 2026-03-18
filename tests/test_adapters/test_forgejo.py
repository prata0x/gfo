"""ForgejoAdapter のテスト。"""

from __future__ import annotations

import json as json_mod

import pytest
import responses

from gfo.adapter.base import Issue, PullRequest, Repository
from gfo.adapter.forgejo import ForgejoAdapter
from gfo.adapter.gitea import GiteaAdapter
from gfo.adapter.registry import get_adapter_class
from gfo.exceptions import AuthenticationError, NotFoundError, ServerError

BASE = "https://forgejo.example.com/api/v1"
REPOS = f"{BASE}/repos/test-owner/test-repo"


def _pr_data(*, number=1, state="open", merged_at=None, draft=False):
    return {
        "number": number,
        "title": f"PR #{number}",
        "body": "description",
        "state": state,
        "merged_at": merged_at,
        "user": {"login": "author1"},
        "head": {"ref": "feature"},
        "base": {"ref": "main"},
        "draft": draft,
        "html_url": f"https://forgejo.example.com/test-owner/test-repo/pulls/{number}",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-02T00:00:00Z",
    }


def _issue_data(*, number=1, state="open"):
    return {
        "number": number,
        "title": f"Issue #{number}",
        "body": "issue body",
        "state": state,
        "user": {"login": "reporter"},
        "assignees": [],
        "labels": [],
        "html_url": f"https://forgejo.example.com/test-owner/test-repo/issues/{number}",
        "created_at": "2025-01-01T00:00:00Z",
    }


def _repo_data():
    return {
        "name": "test-repo",
        "full_name": "test-owner/test-repo",
        "description": "A test repo",
        "private": False,
        "default_branch": "main",
        "clone_url": "https://forgejo.example.com/test-owner/test-repo.git",
        "html_url": "https://forgejo.example.com/test-owner/test-repo",
    }


class TestRegistry:
    def test_registered(self):
        assert get_adapter_class("forgejo") is ForgejoAdapter


class TestInheritance:
    def test_is_gitea_adapter(self, forgejo_adapter):
        assert isinstance(forgejo_adapter, GiteaAdapter)

    def test_service_name(self, forgejo_adapter):
        assert forgejo_adapter.service_name == "Forgejo"

    def test_service_name_not_gitea(self, forgejo_adapter):
        assert forgejo_adapter.service_name != "Gitea"


class TestToPullRequest:
    def test_open(self):
        pr = ForgejoAdapter._to_pull_request(_pr_data())
        assert pr.state == "open"
        assert pr.number == 1
        assert pr.author == "author1"

    def test_closed(self):
        pr = ForgejoAdapter._to_pull_request(_pr_data(state="closed", merged_at=None))
        assert pr.state == "closed"

    def test_merged(self):
        pr = ForgejoAdapter._to_pull_request(
            _pr_data(state="closed", merged_at="2025-01-01T00:00:00Z")
        )
        assert pr.state == "merged"


class TestGiteaApiCompatibility:
    """ForgejoAdapter が Gitea API v1 互換パスを使用することを確認する。"""

    def test_pr_endpoint_uses_gitea_path(self, mock_responses, forgejo_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls",
            json=[_pr_data()],
            status=200,
        )
        forgejo_adapter.list_pull_requests()
        assert mock_responses.calls[0].request.url.startswith(f"{REPOS}/pulls")

    def test_pagination_uses_limit_param(self, mock_responses, forgejo_adapter):
        """Gitea 互換: ページネーションは per_page= ではなく limit= を使う。"""
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls",
            json=[_pr_data()],
            status=200,
        )
        forgejo_adapter.list_pull_requests(limit=20)
        req_url = mock_responses.calls[0].request.url
        assert "limit=" in req_url
        assert "per_page=" not in req_url

    def test_issues_endpoint_uses_gitea_path(self, mock_responses, forgejo_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues",
            json=[_issue_data()],
            status=200,
        )
        forgejo_adapter.list_issues()
        assert mock_responses.calls[0].request.url.startswith(f"{REPOS}/issues")

    def test_issues_pagination_uses_limit_param(self, mock_responses, forgejo_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues",
            json=[_issue_data()],
            status=200,
        )
        forgejo_adapter.list_issues(limit=10)
        req_url = mock_responses.calls[0].request.url
        assert "limit=" in req_url
        assert "per_page=" not in req_url

    def test_checkout_refspec_uses_gitea_format(self, forgejo_adapter):
        """Gitea 互換: チェックアウト refspec は refs/pull/{n}/head 形式。"""
        assert forgejo_adapter.get_pr_checkout_refspec(7) == "refs/pull/7/head"


class TestListPullRequests:
    def test_open(self, mock_responses, forgejo_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls",
            json=[_pr_data()],
            status=200,
        )
        prs = forgejo_adapter.list_pull_requests()
        assert len(prs) == 1
        assert prs[0].state == "open"
        assert prs[0].number == 1

    def test_merged_filter(self, mock_responses, forgejo_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls",
            json=[
                _pr_data(number=1, state="closed", merged_at="2025-01-03T00:00:00Z"),
                _pr_data(number=2, state="closed"),
            ],
            status=200,
        )
        prs = forgejo_adapter.list_pull_requests(state="merged")
        assert len(prs) == 1
        assert prs[0].number == 1

    def test_pagination(self, mock_responses, forgejo_adapter):
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


class TestCreatePullRequest:
    def test_create(self, mock_responses, forgejo_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/pulls",
            json=_pr_data(),
            status=201,
        )
        pr = forgejo_adapter.create_pull_request(
            title="PR #1",
            body="desc",
            base="main",
            head="feature",
        )
        assert isinstance(pr, PullRequest)
        req_body = json_mod.loads(mock_responses.calls[0].request.body)
        assert req_body["draft"] is False

    def test_create_draft(self, mock_responses, forgejo_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/pulls",
            json=_pr_data(draft=True),
            status=201,
        )
        forgejo_adapter.create_pull_request(
            title="Draft",
            body="",
            base="main",
            head="feature",
            draft=True,
        )
        req_body = json_mod.loads(mock_responses.calls[0].request.body)
        assert req_body["draft"] is True


class TestGetPullRequest:
    def test_get(self, mock_responses, forgejo_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls/42",
            json=_pr_data(number=42),
            status=200,
        )
        pr = forgejo_adapter.get_pull_request(42)
        assert pr.number == 42


class TestMergePullRequest:
    def test_merge(self, mock_responses, forgejo_adapter):
        """merge_pull_request は POST .../merge エンドポイントを使用する（R35修正確認）。"""
        mock_responses.add(
            responses.POST,
            f"{REPOS}/pulls/1/merge",
            json={"merged": True},
            status=200,
        )
        forgejo_adapter.merge_pull_request(1)
        req_body = json_mod.loads(mock_responses.calls[0].request.body)
        assert req_body["Do"] == "merge"
        assert mock_responses.calls[0].request.method == "POST"


class TestClosePullRequest:
    def test_close(self, mock_responses, forgejo_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/pulls/1",
            json=_pr_data(state="closed"),
            status=200,
        )
        forgejo_adapter.close_pull_request(1)
        req_body = json_mod.loads(mock_responses.calls[0].request.body)
        assert req_body["state"] == "closed"


class TestReopenPullRequest:
    def test_reopen(self, mock_responses, forgejo_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/pulls/1",
            json=_pr_data(state="open"),
            status=200,
        )
        forgejo_adapter.reopen_pull_request(1)
        req_body = json_mod.loads(mock_responses.calls[0].request.body)
        assert req_body["state"] == "open"


class TestListIssues:
    def test_list(self, mock_responses, forgejo_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues",
            json=[_issue_data()],
            status=200,
        )
        issues = forgejo_adapter.list_issues()
        assert len(issues) == 1
        assert isinstance(issues[0], Issue)

    def test_with_filters(self, mock_responses, forgejo_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues",
            json=[_issue_data()],
            status=200,
        )
        forgejo_adapter.list_issues(assignee="dev1", label="bug")
        req_url = mock_responses.calls[0].request.url
        assert "assignee=dev1" in req_url
        assert "labels=bug" in req_url


class TestListRepositories:
    def test_no_owner(self, mock_responses, forgejo_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/user/repos",
            json=[_repo_data()],
            status=200,
        )
        repos = forgejo_adapter.list_repositories()
        assert len(repos) == 1
        assert isinstance(repos[0], Repository)

    def test_with_owner(self, mock_responses, forgejo_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/users/someone/repos",
            json=[_repo_data()],
            status=200,
        )
        repos = forgejo_adapter.list_repositories(owner="someone")
        assert len(repos) == 1


class TestErrorHandling:
    """HTTP エラーが適切な例外に変換されることを確認する。"""

    def test_not_found_raises_error(self, mock_responses, forgejo_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls/999",
            json={"message": "Not Found"},
            status=404,
        )
        with pytest.raises(NotFoundError):
            forgejo_adapter.get_pull_request(999)

    def test_auth_error_raises_error(self, mock_responses, forgejo_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls",
            json={"message": "Unauthorized"},
            status=401,
        )
        with pytest.raises(AuthenticationError):
            forgejo_adapter.list_pull_requests()

    def test_server_error_raises_error(self, mock_responses, forgejo_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues",
            json={"message": "Internal Server Error"},
            status=500,
        )
        with pytest.raises(ServerError):
            forgejo_adapter.list_issues()


class TestDeleteInheritance:
    """GiteaAdapter から継承した delete メソッドが動作することを確認する。"""

    def test_delete_release(self, mock_responses, forgejo_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/releases/tags/v1.0.0",
            json={"id": 42, "tag_name": "v1.0.0"},
            status=200,
        )
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/releases/42",
            status=204,
        )
        forgejo_adapter.delete_release(tag="v1.0.0")

    def test_delete_label(self, mock_responses, forgejo_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/labels",
            json=[{"id": 10, "name": "bug", "color": "d73a4a", "description": ""}],
            status=200,
        )
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/labels/10",
            status=204,
        )
        forgejo_adapter.delete_label(name="bug")

    def test_delete_milestone(self, mock_responses, forgejo_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/milestones/3",
            status=204,
        )
        forgejo_adapter.delete_milestone(number=3)

    def test_get_milestone(self, mock_responses, forgejo_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/milestones/1",
            json={
                "number": 1,
                "title": "v1.0",
                "description": "desc",
                "state": "open",
                "due_on": "2026-01-01",
            },
            status=200,
        )
        ms = forgejo_adapter.get_milestone(1)
        assert ms.title == "v1.0"

    def test_update_milestone(self, mock_responses, forgejo_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/milestones/1",
            json={
                "number": 1,
                "title": "v2.0",
                "description": "desc",
                "state": "closed",
                "due_on": "2026-01-01",
            },
            status=200,
        )
        ms = forgejo_adapter.update_milestone(1, title="v2.0", state="closed")
        assert ms.title == "v2.0"

    def test_delete_issue(self, mock_responses, forgejo_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/issues/5",
            status=204,
        )
        forgejo_adapter.delete_issue(5)
        assert mock_responses.calls[0].request.method == "DELETE"

    def test_delete_repository(self, mock_responses, forgejo_adapter):
        mock_responses.add(
            responses.DELETE,
            REPOS,
            status=204,
        )
        forgejo_adapter.delete_repository()
        assert mock_responses.calls[0].request.method == "DELETE"

    def test_list_issue_templates(self, mock_responses, forgejo_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issue_templates",
            json=[
                {
                    "name": "Bug Report",
                    "title": "[Bug]: ",
                    "content": "## Description\n...",
                    "about": "Report a bug",
                    "labels": ["bug"],
                },
            ],
            status=200,
        )
        templates = forgejo_adapter.list_issue_templates()
        assert len(templates) == 1
        assert templates[0].name == "Bug Report"
        assert templates[0].labels == ("bug",)

    def test_list_issue_templates_empty(self, mock_responses, forgejo_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issue_templates",
            json=[],
            status=200,
        )
        templates = forgejo_adapter.list_issue_templates()
        assert templates == []

    def test_list_issue_templates_not_found(self, mock_responses, forgejo_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issue_templates",
            json={"message": "Not Found"},
            status=404,
        )
        templates = forgejo_adapter.list_issue_templates()
        assert templates == []
