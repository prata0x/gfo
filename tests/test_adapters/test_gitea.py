"""GiteaAdapter のテスト。"""

from __future__ import annotations

import json

import pytest
import responses

from gfo.adapter.base import Issue, Label, Milestone, PullRequest, Release, Repository
from gfo.adapter.gitea import GiteaAdapter
from gfo.adapter.registry import get_adapter_class
from gfo.exceptions import AuthenticationError, NotFoundError, ServerError


BASE = "https://gitea.example.com/api/v1"
REPOS = f"{BASE}/repos/test-owner/test-repo"


# --- サンプルデータ ---

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
        "html_url": f"https://gitea.example.com/test-owner/test-repo/pulls/{number}",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-02T00:00:00Z",
    }


def _issue_data(*, number=1, state="open", has_pr=False):
    data = {
        "number": number,
        "title": f"Issue #{number}",
        "body": "issue body",
        "state": state,
        "user": {"login": "reporter"},
        "assignees": [{"login": "dev1"}],
        "labels": [{"name": "bug"}],
        "html_url": f"https://gitea.example.com/test-owner/test-repo/issues/{number}",
        "created_at": "2025-01-01T00:00:00Z",
    }
    if has_pr:
        data["pull_request"] = {"url": "..."}
    return data


def _repo_data(*, name="test-repo", full_name="test-owner/test-repo"):
    return {
        "name": name,
        "full_name": full_name,
        "description": "A test repo",
        "private": False,
        "default_branch": "main",
        "clone_url": f"https://gitea.example.com/{full_name}.git",
        "html_url": f"https://gitea.example.com/{full_name}",
    }


def _release_data(*, tag="v1.0.0"):
    return {
        "tag_name": tag,
        "name": f"Release {tag}",
        "body": "release notes",
        "draft": False,
        "prerelease": False,
        "html_url": f"https://gitea.example.com/test-owner/test-repo/releases/tag/{tag}",
        "created_at": "2025-01-01T00:00:00Z",
    }


def _label_data(*, name="bug"):
    return {"name": name, "color": "d73a4a", "description": "Something isn't working"}


def _milestone_data(*, number=1):
    return {
        "number": number,
        "title": f"v{number}.0",
        "description": "milestone desc",
        "state": "open",
        "due_on": "2025-06-01T00:00:00Z",
    }


# --- 変換メソッドのテスト ---

class TestToPullRequest:
    def test_open(self):
        pr = GiteaAdapter._to_pull_request(_pr_data())
        assert pr.state == "open"
        assert pr.number == 1
        assert pr.author == "author1"
        assert pr.source_branch == "feature"
        assert pr.draft is False

    def test_closed(self):
        pr = GiteaAdapter._to_pull_request(_pr_data(state="closed"))
        assert pr.state == "closed"

    def test_merged(self):
        pr = GiteaAdapter._to_pull_request(
            _pr_data(state="closed", merged_at="2025-01-03T00:00:00Z")
        )
        assert pr.state == "merged"


class TestToIssue:
    def test_basic(self):
        issue = GiteaAdapter._to_issue(_issue_data())
        assert issue.number == 1
        assert issue.author == "reporter"
        assert issue.assignees == ["dev1"]
        assert issue.labels == ["bug"]


class TestToRepository:
    def test_basic(self):
        repo = GiteaAdapter._to_repository(_repo_data())
        assert repo.name == "test-repo"
        assert repo.full_name == "test-owner/test-repo"
        assert repo.private is False


class TestToRelease:
    def test_basic(self):
        rel = GiteaAdapter._to_release(_release_data())
        assert rel.tag == "v1.0.0"
        assert rel.title == "Release v1.0.0"


class TestToLabel:
    def test_basic(self):
        label = GiteaAdapter._to_label(_label_data())
        assert label.name == "bug"
        assert label.color == "d73a4a"


class TestToMilestone:
    def test_basic(self):
        ms = GiteaAdapter._to_milestone(_milestone_data())
        assert ms.number == 1
        assert ms.due_date == "2025-06-01T00:00:00Z"


# --- PR 系 ---

class TestListPullRequests:
    def test_open(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET, f"{REPOS}/pulls",
            json=[_pr_data()], status=200,
        )
        prs = gitea_adapter.list_pull_requests()
        assert len(prs) == 1
        assert prs[0].state == "open"

    def test_merged_filter(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET, f"{REPOS}/pulls",
            json=[
                _pr_data(number=1, state="closed", merged_at="2025-01-03T00:00:00Z"),
                _pr_data(number=2, state="closed"),
            ],
            status=200,
        )
        prs = gitea_adapter.list_pull_requests(state="merged")
        assert len(prs) == 1
        assert prs[0].number == 1

    def test_pagination_uses_limit_param(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET, f"{REPOS}/pulls",
            json=[_pr_data(number=1)], status=200,
            headers={"Link": f'<{REPOS}/pulls?page=2>; rel="next"'},
        )
        mock_responses.add(
            responses.GET, f"{REPOS}/pulls",
            json=[_pr_data(number=2)], status=200,
        )
        prs = gitea_adapter.list_pull_requests(limit=10)
        assert len(prs) == 2
        req = mock_responses.calls[0].request
        assert "limit=" in req.url
        assert "per_page=" not in req.url


class TestCreatePullRequest:
    def test_create(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST, f"{REPOS}/pulls",
            json=_pr_data(), status=201,
        )
        pr = gitea_adapter.create_pull_request(
            title="PR #1", body="desc", base="main", head="feature",
        )
        assert isinstance(pr, PullRequest)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["draft"] is False

    def test_create_draft(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST, f"{REPOS}/pulls",
            json=_pr_data(draft=True), status=201,
        )
        pr = gitea_adapter.create_pull_request(
            title="Draft", body="", base="main", head="feature", draft=True,
        )
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["draft"] is True


class TestGetPullRequest:
    def test_get(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET, f"{REPOS}/pulls/42",
            json=_pr_data(number=42), status=200,
        )
        pr = gitea_adapter.get_pull_request(42)
        assert pr.number == 42


class TestMergePullRequest:
    def test_merge(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.PUT, f"{REPOS}/pulls/1/merge",
            json={"merged": True}, status=200,
        )
        gitea_adapter.merge_pull_request(1)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["merge_method"] == "merge"

    def test_merge_squash(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.PUT, f"{REPOS}/pulls/1/merge",
            json={"merged": True}, status=200,
        )
        gitea_adapter.merge_pull_request(1, method="squash")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["merge_method"] == "squash"


class TestClosePullRequest:
    def test_close(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.PATCH, f"{REPOS}/pulls/1",
            json=_pr_data(state="closed"), status=200,
        )
        gitea_adapter.close_pull_request(1)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["state"] == "closed"


class TestCheckoutRefspec:
    def test_refspec(self, gitea_adapter):
        assert gitea_adapter.get_pr_checkout_refspec(42) == "pull/42/head"


# --- Issue 系 ---

class TestListIssues:
    def test_excludes_prs(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET, f"{REPOS}/issues",
            json=[_issue_data(number=1), _issue_data(number=2, has_pr=True)],
            status=200,
        )
        issues = gitea_adapter.list_issues()
        assert len(issues) == 1
        assert issues[0].number == 1

    def test_with_filters(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET, f"{REPOS}/issues",
            json=[_issue_data()], status=200,
        )
        issues = gitea_adapter.list_issues(assignee="dev1", label="bug")
        assert len(issues) == 1
        req = mock_responses.calls[0].request
        assert "assignee=dev1" in req.url
        assert "labels=bug" in req.url

    def test_pagination_uses_limit_param(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET, f"{REPOS}/issues",
            json=[_issue_data()], status=200,
        )
        gitea_adapter.list_issues(limit=20)
        req = mock_responses.calls[0].request
        assert "limit=" in req.url
        assert "per_page=" not in req.url


class TestCreateIssue:
    def test_create(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST, f"{REPOS}/issues",
            json=_issue_data(), status=201,
        )
        issue = gitea_adapter.create_issue(title="Issue #1", body="body")
        assert isinstance(issue, Issue)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert "assignees" not in req_body
        assert "labels" not in req_body

    def test_create_with_assignee_and_label(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST, f"{REPOS}/issues",
            json=_issue_data(), status=201,
        )
        gitea_adapter.create_issue(
            title="Issue", assignee="dev1", label="bug",
        )
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["assignees"] == ["dev1"]
        assert req_body["labels"] == ["bug"]


class TestGetIssue:
    def test_get(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET, f"{REPOS}/issues/5",
            json=_issue_data(number=5), status=200,
        )
        issue = gitea_adapter.get_issue(5)
        assert issue.number == 5


class TestCloseIssue:
    def test_close(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.PATCH, f"{REPOS}/issues/3",
            json=_issue_data(number=3, state="closed"), status=200,
        )
        gitea_adapter.close_issue(3)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["state"] == "closed"


# --- Repository 系 ---

class TestListRepositories:
    def test_with_owner(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET, f"{BASE}/users/someone/repos",
            json=[_repo_data()], status=200,
        )
        repos = gitea_adapter.list_repositories(owner="someone")
        assert len(repos) == 1

    def test_no_owner(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET, f"{BASE}/user/repos",
            json=[_repo_data()], status=200,
        )
        repos = gitea_adapter.list_repositories()
        assert len(repos) == 1

    def test_pagination_uses_limit_param(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET, f"{BASE}/user/repos",
            json=[_repo_data()], status=200,
        )
        gitea_adapter.list_repositories(limit=20)
        req = mock_responses.calls[0].request
        assert "limit=" in req.url
        assert "per_page=" not in req.url


class TestCreateRepository:
    def test_create(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST, f"{BASE}/user/repos",
            json=_repo_data(), status=201,
        )
        repo = gitea_adapter.create_repository(name="test-repo")
        assert isinstance(repo, Repository)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["name"] == "test-repo"


class TestGetRepository:
    def test_get(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET, f"{BASE}/repos/other/other-repo",
            json=_repo_data(name="other-repo", full_name="other/other-repo"),
            status=200,
        )
        repo = gitea_adapter.get_repository(owner="other", name="other-repo")
        assert repo.name == "other-repo"

    def test_get_defaults(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET, f"{REPOS}",
            json=_repo_data(), status=200,
        )
        repo = gitea_adapter.get_repository()
        assert repo.full_name == "test-owner/test-repo"


# --- Release 系 ---

class TestListReleases:
    def test_list(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET, f"{REPOS}/releases",
            json=[_release_data()], status=200,
        )
        releases = gitea_adapter.list_releases()
        assert len(releases) == 1
        assert releases[0].tag == "v1.0.0"

    def test_pagination_uses_limit_param(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET, f"{REPOS}/releases",
            json=[_release_data()], status=200,
        )
        gitea_adapter.list_releases(limit=20)
        req = mock_responses.calls[0].request
        assert "limit=" in req.url
        assert "per_page=" not in req.url


class TestCreateRelease:
    def test_create(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST, f"{REPOS}/releases",
            json=_release_data(), status=201,
        )
        rel = gitea_adapter.create_release(tag="v1.0.0", title="Release v1.0.0")
        assert isinstance(rel, Release)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["tag_name"] == "v1.0.0"


# --- Label 系 ---

class TestListLabels:
    def test_list(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET, f"{REPOS}/labels",
            json=[_label_data(), _label_data(name="enhancement")],
            status=200,
        )
        labels = gitea_adapter.list_labels()
        assert len(labels) == 2


class TestCreateLabel:
    def test_create(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST, f"{REPOS}/labels",
            json=_label_data(), status=201,
        )
        label = gitea_adapter.create_label(name="bug", color="d73a4a")
        assert label.name == "bug"

    def test_create_optional_fields(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST, f"{REPOS}/labels",
            json={"name": "minimal", "color": None, "description": None},
            status=201,
        )
        gitea_adapter.create_label(name="minimal")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert "color" not in req_body
        assert "description" not in req_body


# --- Milestone 系 ---

class TestListMilestones:
    def test_list(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET, f"{REPOS}/milestones",
            json=[_milestone_data()], status=200,
        )
        milestones = gitea_adapter.list_milestones()
        assert len(milestones) == 1
        assert milestones[0].title == "v1.0"


class TestCreateMilestone:
    def test_create(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST, f"{REPOS}/milestones",
            json=_milestone_data(), status=201,
        )
        ms = gitea_adapter.create_milestone(title="v1.0", due_date="2025-06-01T00:00:00Z")
        assert isinstance(ms, Milestone)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["due_on"] == "2025-06-01T00:00:00Z"

    def test_create_optional_fields(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST, f"{REPOS}/milestones",
            json=_milestone_data(), status=201,
        )
        gitea_adapter.create_milestone(title="v1.0")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert "description" not in req_body
        assert "due_on" not in req_body


# --- Registry ---

class TestReposPath:
    def test_non_ascii_owner_encoded(self):
        """非ASCII owner が URL エンコードされる。"""
        from gfo.http import HttpClient
        client = HttpClient("https://gitea.example.com/api/v1")
        adapter = GiteaAdapter(client, "日本語-owner", "my-repo")
        path = adapter._repos_path()
        assert "日本語" not in path
        assert "%E6%97%A5%E6%9C%AC%E8%AA%9E" in path


class TestRegistry:
    def test_registered(self):
        assert get_adapter_class("gitea") is GiteaAdapter


class TestErrorHandling:
    """HTTP エラーが適切な例外に変換されることを確認する。"""

    def test_not_found_raises_error(self, mock_responses, gitea_adapter):
        mock_responses.add(responses.GET, f"{REPOS}/issues/999", status=404)
        with pytest.raises(NotFoundError):
            gitea_adapter.get_issue(999)

    def test_401_raises_auth_error(self, mock_responses, gitea_adapter):
        mock_responses.add(responses.GET, f"{REPOS}/pulls", status=401)
        with pytest.raises(AuthenticationError):
            gitea_adapter.list_pull_requests()

    def test_500_raises_server_error(self, mock_responses, gitea_adapter):
        mock_responses.add(responses.GET, f"{REPOS}/issues", status=500)
        with pytest.raises(ServerError):
            gitea_adapter.list_issues()
