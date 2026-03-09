"""BitbucketAdapter のテスト。"""

from __future__ import annotations

import json

import pytest
import responses

from gfo.adapter.base import Issue, PullRequest, Repository
from gfo.adapter.bitbucket import BitbucketAdapter
from gfo.adapter.registry import get_adapter_class
from gfo.exceptions import AuthenticationError, NotFoundError, NotSupportedError, ServerError


BASE = "https://api.bitbucket.org/2.0"
REPOS = f"{BASE}/repositories/test-workspace/test-repo"


# --- サンプルデータ ---

def _pr_data(*, id=1, state="OPEN"):
    return {
        "id": id,
        "title": f"PR #{id}",
        "description": "pr description",
        "state": state,
        "author": {"nickname": "author1"},
        "source": {"branch": {"name": "feature"}},
        "destination": {"branch": {"name": "main"}},
        "links": {"html": {"href": f"https://bitbucket.org/test-workspace/test-repo/pull-requests/{id}"}},
        "created_on": "2025-01-01T00:00:00Z",
        "updated_on": "2025-01-02T00:00:00Z",
    }


def _issue_data(*, id=1, state="new"):
    return {
        "id": id,
        "title": f"Issue #{id}",
        "content": {"raw": "issue body"},
        "state": state,
        "reporter": {"nickname": "reporter1"},
        "assignee": {"nickname": "dev1"},
        "links": {"html": {"href": f"https://bitbucket.org/test-workspace/test-repo/issues/{id}"}},
        "created_on": "2025-01-01T00:00:00Z",
    }


def _repo_data(*, slug="test-repo", full_name="test-workspace/test-repo"):
    return {
        "slug": slug,
        "full_name": full_name,
        "description": "A test repo",
        "is_private": False,
        "mainbranch": {"name": "main"},
        "links": {
            "clone": [
                {"name": "https", "href": f"https://bitbucket.org/{full_name}.git"},
                {"name": "ssh", "href": f"git@bitbucket.org:{full_name}.git"},
            ],
            "html": {"href": f"https://bitbucket.org/{full_name}"},
        },
    }


# --- 変換メソッドのテスト ---

class TestToPullRequest:
    def test_open(self):
        pr = BitbucketAdapter._to_pull_request(_pr_data())
        assert pr.state == "open"
        assert pr.number == 1
        assert pr.author == "author1"
        assert pr.source_branch == "feature"
        assert pr.target_branch == "main"
        assert pr.draft is False

    def test_declined(self):
        pr = BitbucketAdapter._to_pull_request(_pr_data(state="DECLINED"))
        assert pr.state == "closed"

    def test_superseded(self):
        pr = BitbucketAdapter._to_pull_request(_pr_data(state="SUPERSEDED"))
        assert pr.state == "closed"

    def test_merged(self):
        pr = BitbucketAdapter._to_pull_request(_pr_data(state="MERGED"))
        assert pr.state == "merged"


class TestToIssue:
    def test_new(self):
        issue = BitbucketAdapter._to_issue(_issue_data())
        assert issue.number == 1
        assert issue.state == "open"
        assert issue.body == "issue body"
        assert issue.author == "reporter1"
        assert issue.assignees == ["dev1"]
        assert issue.labels == []

    def test_open_state(self):
        issue = BitbucketAdapter._to_issue(_issue_data(state="open"))
        assert issue.state == "open"

    def test_closed_state(self):
        issue = BitbucketAdapter._to_issue(_issue_data(state="closed"))
        assert issue.state == "closed"

    def test_no_assignee(self):
        data = _issue_data()
        data["assignee"] = None
        issue = BitbucketAdapter._to_issue(data)
        assert issue.assignees == []


class TestToRepository:
    def test_basic(self):
        repo = BitbucketAdapter._to_repository(_repo_data())
        assert repo.name == "test-repo"
        assert repo.full_name == "test-workspace/test-repo"
        assert repo.private is False
        assert repo.default_branch == "main"
        assert "https" in repo.clone_url

    def test_no_mainbranch(self):
        data = _repo_data()
        data["mainbranch"] = None
        repo = BitbucketAdapter._to_repository(data)
        assert repo.default_branch is None


# --- PR 系 ---

class TestListPullRequests:
    def test_open(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET, f"{REPOS}/pullrequests",
            json={"values": [_pr_data()], "next": None}, status=200,
        )
        prs = bitbucket_adapter.list_pull_requests()
        assert len(prs) == 1
        assert prs[0].state == "open"
        req = mock_responses.calls[0].request
        assert "state=OPEN" in req.url

    def test_merged_filter(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET, f"{REPOS}/pullrequests",
            json={"values": [_pr_data(state="MERGED")]}, status=200,
        )
        prs = bitbucket_adapter.list_pull_requests(state="merged")
        assert len(prs) == 1
        assert prs[0].state == "merged"
        req = mock_responses.calls[0].request
        assert "state=MERGED" in req.url

    def test_pagination(self, mock_responses, bitbucket_adapter):
        page2_url = f"{REPOS}/pullrequests?state=OPEN&page=2"
        mock_responses.add(
            responses.GET, f"{REPOS}/pullrequests",
            json={"values": [_pr_data(id=1)], "next": page2_url}, status=200,
        )
        mock_responses.add(
            responses.GET, page2_url,
            json={"values": [_pr_data(id=2)]}, status=200,
        )
        prs = bitbucket_adapter.list_pull_requests(limit=10)
        assert len(prs) == 2


class TestCreatePullRequest:
    def test_create(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.POST, f"{REPOS}/pullrequests",
            json=_pr_data(), status=201,
        )
        pr = bitbucket_adapter.create_pull_request(
            title="PR #1", body="desc", base="main", head="feature",
        )
        assert isinstance(pr, PullRequest)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["source"]["branch"]["name"] == "feature"
        assert req_body["destination"]["branch"]["name"] == "main"


class TestCreatePullRequestDescription:
    def test_create_with_description(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.POST, f"{REPOS}/pullrequests",
            json=_pr_data(), status=201,
        )
        bitbucket_adapter.create_pull_request(
            title="PR", body="Description text", base="main", head="feature",
        )
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["description"] == "Description text"


class TestGetPullRequest:
    def test_get(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET, f"{REPOS}/pullrequests/42",
            json=_pr_data(id=42), status=200,
        )
        pr = bitbucket_adapter.get_pull_request(42)
        assert pr.number == 42


class TestMergePullRequest:
    def test_merge(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.POST, f"{REPOS}/pullrequests/1/merge",
            json={"state": "MERGED"}, status=200,
        )
        bitbucket_adapter.merge_pull_request(1)


class TestClosePullRequest:
    def test_close(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.PUT, f"{REPOS}/pullrequests/1",
            json=_pr_data(state="DECLINED"), status=200,
        )
        bitbucket_adapter.close_pull_request(1)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["state"] == "DECLINED"


class TestCheckoutRefspec:
    def test_with_pr(self, bitbucket_adapter):
        pr = BitbucketAdapter._to_pull_request(_pr_data())
        assert bitbucket_adapter.get_pr_checkout_refspec(1, pr=pr) == "feature"

    def test_without_pr(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET, f"{REPOS}/pullrequests/1",
            json=_pr_data(), status=200,
        )
        assert bitbucket_adapter.get_pr_checkout_refspec(1) == "feature"


# --- Issue 系 ---

class TestListIssues:
    def test_list(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET, f"{REPOS}/issues",
            json={"values": [_issue_data(id=1), _issue_data(id=2)]}, status=200,
        )
        issues = bitbucket_adapter.list_issues()
        assert len(issues) == 2


class TestCreateIssue:
    def test_create(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.POST, f"{REPOS}/issues",
            json=_issue_data(), status=201,
        )
        issue = bitbucket_adapter.create_issue(title="Issue #1", body="body")
        assert isinstance(issue, Issue)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["content"]["raw"] == "body"
        assert "assignee" not in req_body

    def test_create_with_assignee(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.POST, f"{REPOS}/issues",
            json=_issue_data(), status=201,
        )
        bitbucket_adapter.create_issue(title="Issue", assignee="dev1")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["assignee"]["nickname"] == "dev1"


class TestGetIssue:
    def test_get(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET, f"{REPOS}/issues/5",
            json=_issue_data(id=5), status=200,
        )
        issue = bitbucket_adapter.get_issue(5)
        assert issue.number == 5


class TestCloseIssue:
    def test_close(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.PUT, f"{REPOS}/issues/3",
            json=_issue_data(id=3, state="resolved"), status=200,
        )
        bitbucket_adapter.close_issue(3)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["state"] == "resolved"


# --- Repository 系 ---

class TestListRepositories:
    def test_with_owner(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET, f"{BASE}/repositories/someone",
            json={"values": [_repo_data()]}, status=200,
        )
        repos = bitbucket_adapter.list_repositories(owner="someone")
        assert len(repos) == 1

    def test_no_owner(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET, f"{BASE}/repositories/test-workspace",
            json={"values": [_repo_data()]}, status=200,
        )
        repos = bitbucket_adapter.list_repositories()
        assert len(repos) == 1


class TestCreateRepository:
    def test_create(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.POST, f"{BASE}/repositories/test-workspace/new-repo",
            json=_repo_data(slug="new-repo", full_name="test-workspace/new-repo"),
            status=201,
        )
        repo = bitbucket_adapter.create_repository(name="new-repo")
        assert isinstance(repo, Repository)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["scm"] == "git"
        assert req_body["is_private"] is False


class TestGetRepository:
    def test_get(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET, f"{BASE}/repositories/other/other-repo",
            json=_repo_data(slug="other-repo", full_name="other/other-repo"),
            status=200,
        )
        repo = bitbucket_adapter.get_repository(owner="other", name="other-repo")
        assert repo.name == "other-repo"

    def test_get_defaults(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET, f"{REPOS}",
            json=_repo_data(), status=200,
        )
        repo = bitbucket_adapter.get_repository()
        assert repo.full_name == "test-workspace/test-repo"


# --- NotSupportedError ---

class TestNotSupported:
    def test_list_releases(self, bitbucket_adapter):
        with pytest.raises(NotSupportedError):
            bitbucket_adapter.list_releases()

    def test_create_release(self, bitbucket_adapter):
        with pytest.raises(NotSupportedError):
            bitbucket_adapter.create_release(tag="v1.0")

    def test_list_labels(self, bitbucket_adapter):
        with pytest.raises(NotSupportedError):
            bitbucket_adapter.list_labels()

    def test_create_label(self, bitbucket_adapter):
        with pytest.raises(NotSupportedError):
            bitbucket_adapter.create_label(name="bug")

    def test_list_milestones(self, bitbucket_adapter):
        with pytest.raises(NotSupportedError):
            bitbucket_adapter.list_milestones()

    def test_create_milestone(self, bitbucket_adapter):
        with pytest.raises(NotSupportedError):
            bitbucket_adapter.create_milestone(title="v1.0")


# --- Registry ---

class TestRegistry:
    def test_registered(self):
        assert get_adapter_class("bitbucket") is BitbucketAdapter


class TestErrorHandling:
    """HTTP エラーが適切な例外に変換されることを確認する。"""

    def test_not_found_raises_error(self, mock_responses, bitbucket_adapter):
        mock_responses.add(responses.GET, f"{REPOS}/pullrequests/999", status=404)
        with pytest.raises(NotFoundError):
            bitbucket_adapter.get_pull_request(999)

    def test_401_raises_auth_error(self, mock_responses, bitbucket_adapter):
        mock_responses.add(responses.GET, f"{REPOS}/pullrequests", status=401)
        with pytest.raises(AuthenticationError):
            bitbucket_adapter.list_pull_requests()

    def test_500_raises_server_error(self, mock_responses, bitbucket_adapter):
        mock_responses.add(responses.GET, f"{REPOS}/issues", status=500)
        with pytest.raises(ServerError):
            bitbucket_adapter.list_issues()
