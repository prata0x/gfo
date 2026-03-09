"""GitLabAdapter のテスト。"""

from __future__ import annotations

import json
from urllib.parse import quote

import pytest
import responses

from gfo.adapter.base import Issue, Label, Milestone, PullRequest, Release, Repository
from gfo.adapter.gitlab import GitLabAdapter
from gfo.adapter.registry import get_adapter_class
from gfo.exceptions import AuthenticationError, NotFoundError, ServerError


BASE = "https://gitlab.com/api/v4"
PROJECT = f"{BASE}/projects/{quote('test-owner/test-repo', safe='')}"


# --- サンプルデータ ---

def _mr_data(*, iid=1, state="opened", draft=False):
    return {
        "iid": iid,
        "title": f"MR !{iid}",
        "description": "description",
        "state": state,
        "author": {"username": "author1"},
        "source_branch": "feature",
        "target_branch": "main",
        "draft": draft,
        "web_url": f"https://gitlab.com/test-owner/test-repo/-/merge_requests/{iid}",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-02T00:00:00Z",
    }


def _issue_data(*, iid=1, state="opened"):
    return {
        "iid": iid,
        "title": f"Issue #{iid}",
        "description": "issue body",
        "state": state,
        "author": {"username": "reporter"},
        "assignees": [{"username": "dev1"}],
        "labels": ["bug"],
        "web_url": f"https://gitlab.com/test-owner/test-repo/-/issues/{iid}",
        "created_at": "2025-01-01T00:00:00Z",
    }


def _repo_data(*, name="test-repo", path_with_namespace="test-owner/test-repo"):
    return {
        "name": name,
        "path_with_namespace": path_with_namespace,
        "description": "A test repo",
        "visibility": "public",
        "default_branch": "main",
        "http_url_to_repo": f"https://gitlab.com/{path_with_namespace}.git",
        "web_url": f"https://gitlab.com/{path_with_namespace}",
    }


def _release_data(*, tag="v1.0.0"):
    return {
        "tag_name": tag,
        "name": f"Release {tag}",
        "description": "release notes",
        "upcoming_release": False,
        "_links": {"self": f"https://gitlab.com/test-owner/test-repo/-/releases/{tag}"},
        "created_at": "2025-01-01T00:00:00Z",
    }


def _label_data(*, name="bug"):
    return {"name": name, "color": "#d73a4a", "description": "Something isn't working"}


def _milestone_data(*, iid=1):
    return {
        "iid": iid,
        "title": f"v{iid}.0",
        "description": "milestone desc",
        "state": "active",
        "due_date": "2025-06-01",
    }


# --- _project_path テスト ---

class TestProjectPath:
    def test_basic_owner_repo(self):
        """通常の owner/repo が URL エンコードされる。"""
        from gfo.http import HttpClient
        client = HttpClient(BASE)
        adapter = GitLabAdapter(client, "test-owner", "test-repo")
        path = adapter._project_path()
        assert path == f"/projects/{quote('test-owner/test-repo', safe='')}"

    def test_three_level_subgroup(self):
        """3階層サブグループ owner/sub1/sub2 + repo が正しくエンコードされる。"""
        from gfo.http import HttpClient
        client = HttpClient(BASE)
        adapter = GitLabAdapter(client, "group/sub1/sub2", "myrepo")
        path = adapter._project_path()
        assert path == f"/projects/{quote('group/sub1/sub2/myrepo', safe='')}"
        assert path == "/projects/group%2Fsub1%2Fsub2%2Fmyrepo"


# --- 変換メソッドのテスト ---

class TestToPullRequest:
    def test_open(self):
        pr = GitLabAdapter._to_pull_request(_mr_data())
        assert pr.state == "open"
        assert pr.number == 1
        assert pr.author == "author1"
        assert pr.source_branch == "feature"
        assert pr.draft is False

    def test_closed(self):
        pr = GitLabAdapter._to_pull_request(_mr_data(state="closed"))
        assert pr.state == "closed"

    def test_merged(self):
        pr = GitLabAdapter._to_pull_request(_mr_data(state="merged"))
        assert pr.state == "merged"


class TestToIssue:
    def test_basic(self):
        issue = GitLabAdapter._to_issue(_issue_data())
        assert issue.number == 1
        assert issue.author == "reporter"
        assert issue.assignees == ["dev1"]
        assert issue.labels == ["bug"]
        assert issue.state == "open"


class TestToRepository:
    def test_basic(self):
        repo = GitLabAdapter._to_repository(_repo_data())
        assert repo.name == "test-repo"
        assert repo.full_name == "test-owner/test-repo"
        assert repo.private is False


class TestToRelease:
    def test_basic(self):
        rel = GitLabAdapter._to_release(_release_data())
        assert rel.tag == "v1.0.0"
        assert rel.title == "Release v1.0.0"


class TestToLabel:
    def test_basic(self):
        label = GitLabAdapter._to_label(_label_data())
        assert label.name == "bug"
        assert label.color == "d73a4a"


class TestToMilestone:
    def test_basic(self):
        ms = GitLabAdapter._to_milestone(_milestone_data())
        assert ms.number == 1
        assert ms.due_date == "2025-06-01"
        assert ms.state == "active"


# --- PR (MR) 系 ---

class TestListPullRequests:
    def test_open(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET, f"{PROJECT}/merge_requests",
            json=[_mr_data()], status=200,
        )
        prs = gitlab_adapter.list_pull_requests()
        assert len(prs) == 1
        assert prs[0].state == "open"
        req = mock_responses.calls[0].request
        assert "state=opened" in req.url

    def test_merged_filter(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET, f"{PROJECT}/merge_requests",
            json=[_mr_data(iid=1, state="merged")],
            status=200,
        )
        prs = gitlab_adapter.list_pull_requests(state="merged")
        assert len(prs) == 1
        assert prs[0].state == "merged"
        req = mock_responses.calls[0].request
        assert "state=merged" in req.url

    def test_pagination(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET, f"{PROJECT}/merge_requests",
            json=[_mr_data(iid=1)], status=200,
            headers={"X-Next-Page": "2"},
        )
        mock_responses.add(
            responses.GET, f"{PROJECT}/merge_requests",
            json=[_mr_data(iid=2)], status=200,
        )
        prs = gitlab_adapter.list_pull_requests(limit=10)
        assert len(prs) == 2

    def test_pagination_limit_truncates(self, mock_responses, gitlab_adapter):
        """limit=1 のとき 1 ページ目の 1 件で打ち切られる。"""
        mock_responses.add(
            responses.GET, f"{PROJECT}/merge_requests",
            json=[_mr_data(iid=1), _mr_data(iid=2)], status=200,
            headers={"X-Next-Page": "2"},
        )
        prs = gitlab_adapter.list_pull_requests(limit=1)
        assert len(prs) == 1
        assert prs[0].number == 1
        assert len(mock_responses.calls) == 1  # 2 ページ目へのリクエストなし


    def test_all_state_sends_all_param(self, mock_responses, gitlab_adapter):
        """state='all' のとき state=all を API に送る（GitLab API は 'all' をサポートする）。"""
        mock_responses.add(
            responses.GET, f"{PROJECT}/merge_requests",
            json=[_mr_data(iid=1), _mr_data(iid=2, state="merged")], status=200,
        )
        prs = gitlab_adapter.list_pull_requests(state="all")
        assert len(prs) == 2
        req = mock_responses.calls[0].request
        assert "state=all" in req.url


class TestCreatePullRequest:
    def test_create(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST, f"{PROJECT}/merge_requests",
            json=_mr_data(), status=201,
        )
        pr = gitlab_adapter.create_pull_request(
            title="MR !1", body="desc", base="main", head="feature",
        )
        assert isinstance(pr, PullRequest)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["source_branch"] == "feature"
        assert req_body["target_branch"] == "main"
        assert req_body["draft"] is False

    def test_create_draft(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST, f"{PROJECT}/merge_requests",
            json=_mr_data(draft=True), status=201,
        )
        pr = gitlab_adapter.create_pull_request(
            title="Draft", body="", base="main", head="feature", draft=True,
        )
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["draft"] is True


class TestGetPullRequest:
    def test_get(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET, f"{PROJECT}/merge_requests/42",
            json=_mr_data(iid=42), status=200,
        )
        pr = gitlab_adapter.get_pull_request(42)
        assert pr.number == 42


class TestMergePullRequest:
    def test_merge(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.PUT, f"{PROJECT}/merge_requests/1/merge",
            json={"state": "merged"}, status=200,
        )
        gitlab_adapter.merge_pull_request(1)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body == {}  # method="merge" は追加 payload なし

    def test_merge_squash(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.PUT, f"{PROJECT}/merge_requests/1/merge",
            json={"state": "merged"}, status=200,
        )
        gitlab_adapter.merge_pull_request(1, method="squash")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body.get("squash") is True
        assert "merge_method" not in req_body

    def test_merge_rebase_calls_rebase_endpoint(self, mock_responses, gitlab_adapter):
        """method="rebase" は /merge ではなく /rebase エンドポイントを呼ぶ。"""
        mock_responses.add(
            responses.PUT, f"{PROJECT}/merge_requests/2/rebase",
            json={}, status=200,
        )
        gitlab_adapter.merge_pull_request(2, method="rebase")
        assert len(mock_responses.calls) == 1
        assert "/rebase" in mock_responses.calls[0].request.url

    def test_merge_invalid_method_raises(self, gitlab_adapter):
        with pytest.raises(ValueError, match="method must be one of"):
            gitlab_adapter.merge_pull_request(1, method="fast-forward")


class TestClosePullRequest:
    def test_close(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.PUT, f"{PROJECT}/merge_requests/1",
            json=_mr_data(state="closed"), status=200,
        )
        gitlab_adapter.close_pull_request(1)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["state_event"] == "close"


class TestCheckoutRefspec:
    def test_refspec(self, gitlab_adapter):
        assert gitlab_adapter.get_pr_checkout_refspec(42) == "merge-requests/42/head"


# --- Issue 系 ---

class TestListIssues:
    def test_list(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET, f"{PROJECT}/issues",
            json=[_issue_data(iid=1), _issue_data(iid=2)],
            status=200,
        )
        issues = gitlab_adapter.list_issues()
        assert len(issues) == 2

    def test_with_filters(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET, f"{PROJECT}/issues",
            json=[_issue_data()], status=200,
        )
        issues = gitlab_adapter.list_issues(assignee="dev1", label="bug")
        assert len(issues) == 1
        req = mock_responses.calls[0].request
        assert "assignee_username=dev1" in req.url
        assert "labels=bug" in req.url


    def test_all_state_sends_all_param(self, mock_responses, gitlab_adapter):
        """state='all' のとき state=all を API に送る（GitLab API は 'all' をサポートする）。"""
        mock_responses.add(
            responses.GET, f"{PROJECT}/issues",
            json=[_issue_data(iid=1), _issue_data(iid=2)], status=200,
        )
        issues = gitlab_adapter.list_issues(state="all")
        assert len(issues) == 2
        req = mock_responses.calls[0].request
        assert "state=all" in req.url


class TestCreateIssue:
    def test_create(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST, f"{PROJECT}/issues",
            json=_issue_data(), status=201,
        )
        issue = gitlab_adapter.create_issue(title="Issue #1", body="body")
        assert isinstance(issue, Issue)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert "assignee_username" not in req_body
        assert "labels" not in req_body

    def test_create_with_assignee_and_label(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST, f"{PROJECT}/issues",
            json=_issue_data(), status=201,
        )
        gitlab_adapter.create_issue(
            title="Issue", assignee="dev1", label="bug",
        )
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["assignee_username"] == "dev1"
        assert req_body["labels"] == "bug"


class TestGetIssue:
    def test_get(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET, f"{PROJECT}/issues/5",
            json=_issue_data(iid=5), status=200,
        )
        issue = gitlab_adapter.get_issue(5)
        assert issue.number == 5


class TestCloseIssue:
    def test_close(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.PUT, f"{PROJECT}/issues/3",
            json=_issue_data(iid=3, state="closed"), status=200,
        )
        gitlab_adapter.close_issue(3)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["state_event"] == "close"


# --- Repository 系 ---

class TestListRepositories:
    def test_with_owner(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET, f"{BASE}/users/someone/projects",
            json=[_repo_data()], status=200,
        )
        repos = gitlab_adapter.list_repositories(owner="someone")
        assert len(repos) == 1

    def test_no_owner(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET, f"{BASE}/projects",
            json=[_repo_data()], status=200,
        )
        repos = gitlab_adapter.list_repositories()
        assert len(repos) == 1

    def test_owner_with_special_chars_is_encoded(self, mock_responses, gitlab_adapter):
        """list_repositories(owner="...") で特殊文字が URL エンコードされる（R41-01）。"""
        mock_responses.add(
            responses.GET, f"{BASE}/users/org%2Fsub/projects",
            json=[_repo_data()], status=200,
        )
        gitlab_adapter.list_repositories(owner="org/sub")
        assert "%2F" in mock_responses.calls[0].request.url


class TestCreateRepository:
    def test_create(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST, f"{BASE}/projects",
            json=_repo_data(), status=201,
        )
        repo = gitlab_adapter.create_repository(name="test-repo")
        assert isinstance(repo, Repository)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["name"] == "test-repo"
        assert req_body["visibility"] == "public"


class TestGetRepository:
    def test_get(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET, f"{BASE}/projects/{quote('other/other-repo', safe='')}",
            json=_repo_data(name="other-repo", path_with_namespace="other/other-repo"),
            status=200,
        )
        repo = gitlab_adapter.get_repository(owner="other", name="other-repo")
        assert repo.name == "other-repo"

    def test_get_defaults(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET, f"{PROJECT}",
            json=_repo_data(), status=200,
        )
        repo = gitlab_adapter.get_repository()
        assert repo.full_name == "test-owner/test-repo"


# --- Release 系 ---

class TestListReleases:
    def test_list(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET, f"{PROJECT}/releases",
            json=[_release_data()], status=200,
        )
        releases = gitlab_adapter.list_releases()
        assert len(releases) == 1
        assert releases[0].tag == "v1.0.0"


class TestCreateRelease:
    def test_create(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST, f"{PROJECT}/releases",
            json=_release_data(), status=201,
        )
        rel = gitlab_adapter.create_release(tag="v1.0.0", title="Release v1.0.0")
        assert isinstance(rel, Release)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["tag_name"] == "v1.0.0"


# --- Label 系 ---

class TestListLabels:
    def test_list(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET, f"{PROJECT}/labels",
            json=[_label_data(), _label_data(name="enhancement")],
            status=200,
        )
        labels = gitlab_adapter.list_labels()
        assert len(labels) == 2

    def test_list_fetches_all_pages(self, mock_responses, gitlab_adapter):
        """list_labels は limit=0 で全ページを取得する（30 件上限なし）。"""
        # 1 ページ目: 20 件 + X-Next-Page: 2
        mock_responses.add(
            responses.GET, f"{PROJECT}/labels",
            json=[_label_data(name=f"label-{i}") for i in range(20)],
            headers={"X-Next-Page": "2"},
            status=200,
        )
        # 2 ページ目: 1 件 + X-Next-Page なし（最終ページ）
        mock_responses.add(
            responses.GET, f"{PROJECT}/labels",
            json=[_label_data(name="last-label")],
            status=200,
        )
        labels = gitlab_adapter.list_labels()
        assert len(labels) == 21


class TestCreateLabel:
    def test_create(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST, f"{PROJECT}/labels",
            json=_label_data(), status=201,
        )
        label = gitlab_adapter.create_label(name="bug", color="d73a4a")
        assert label.name == "bug"
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["color"] == "#d73a4a"

    def test_create_optional_fields(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST, f"{PROJECT}/labels",
            json={"name": "minimal", "color": None, "description": None},
            status=201,
        )
        gitlab_adapter.create_label(name="minimal")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert "color" not in req_body
        assert "description" not in req_body


# --- Milestone 系 ---

class TestListMilestones:
    def test_list(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET, f"{PROJECT}/milestones",
            json=[_milestone_data()], status=200,
        )
        milestones = gitlab_adapter.list_milestones()
        assert len(milestones) == 1
        assert milestones[0].title == "v1.0"

    def test_list_fetches_all_pages(self, mock_responses, gitlab_adapter):
        """list_milestones は limit=0 で全ページを取得する（30 件上限なし）。"""
        mock_responses.add(
            responses.GET, f"{PROJECT}/milestones",
            json=[_milestone_data() for _ in range(20)],
            headers={"X-Next-Page": "2"},
            status=200,
        )
        mock_responses.add(
            responses.GET, f"{PROJECT}/milestones",
            json=[_milestone_data()],
            status=200,
        )
        milestones = gitlab_adapter.list_milestones()
        assert len(milestones) == 21


class TestCreateMilestone:
    def test_create(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST, f"{PROJECT}/milestones",
            json=_milestone_data(), status=201,
        )
        ms = gitlab_adapter.create_milestone(title="v1.0", due_date="2025-06-01")
        assert isinstance(ms, Milestone)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["due_date"] == "2025-06-01"

    def test_create_optional_fields(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST, f"{PROJECT}/milestones",
            json=_milestone_data(), status=201,
        )
        gitlab_adapter.create_milestone(title="v1.0")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert "description" not in req_body
        assert "due_date" not in req_body


# --- Registry ---

class TestRegistry:
    def test_registered(self):
        assert get_adapter_class("gitlab") is GitLabAdapter


class TestErrorHandling:
    """HTTP エラーが適切な例外に変換されることを確認する。"""

    def test_not_found_raises_error(self, mock_responses, gitlab_adapter):
        mock_responses.add(responses.GET, f"{PROJECT}/issues/999", status=404)
        with pytest.raises(NotFoundError):
            gitlab_adapter.get_issue(999)

    def test_401_raises_auth_error(self, mock_responses, gitlab_adapter):
        mock_responses.add(responses.GET, f"{PROJECT}/merge_requests", status=401)
        with pytest.raises(AuthenticationError):
            gitlab_adapter.list_pull_requests()

    def test_500_raises_server_error(self, mock_responses, gitlab_adapter):
        mock_responses.add(responses.GET, f"{PROJECT}/issues", status=500)
        with pytest.raises(ServerError):
            gitlab_adapter.list_issues()
