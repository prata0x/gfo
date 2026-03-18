"""GitLabAdapter のテスト。"""

from __future__ import annotations

import json
from urllib.parse import quote

import pytest
import responses

from gfo.adapter.base import (
    Branch,
    CheckRun,
    Comment,
    CommitStatus,
    DeployKey,
    Issue,
    Milestone,
    Pipeline,
    PullRequest,
    PullRequestCommit,
    PullRequestFile,
    Release,
    Repository,
    Review,
    Tag,
    Webhook,
    WikiPage,
)
from gfo.adapter.gitlab import GitLabAdapter
from gfo.adapter.registry import get_adapter_class
from gfo.exceptions import AuthenticationError, NotFoundError, NotSupportedError, ServerError

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
        "path": name,
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


def _comment_data(*, comment_id=10):
    return {
        "id": comment_id,
        "body": "A comment",
        "author": {"username": "commenter"},
        "web_url": f"https://gitlab.com/test-owner/test-repo/-/issues/1#note_{comment_id}",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-02T00:00:00Z",
    }


def _review_data_approved():
    """GitLab の approvals レスポンス。"""
    return {
        "approved_by": [
            {"user": {"username": "reviewer1"}},
        ]
    }


def _branch_data(*, name="feature", sha="abc123"):
    return {
        "name": name,
        "commit": {"id": sha},
        "web_url": f"https://gitlab.com/test-owner/test-repo/-/tree/{name}",
        "protected": False,
    }


def _tag_data(*, name="v1.0.0", sha="def456"):
    return {
        "name": name,
        "commit": {"id": sha, "message": "Release"},
    }


def _commit_status_data(*, state="success", name="ci/test"):
    return {
        "status": state,
        "name": name,
        "description": "Tests passed",
        "target_url": "https://ci.example.com/build/1",
        "created_at": "2025-01-01T00:00:00Z",
    }


def _webhook_data(*, hook_id=100):
    return {
        "id": hook_id,
        "url": "https://example.com/hook",
        "push_events": True,
        "issues_events": False,
        "merge_requests_events": False,
        "token": "",
        "enable_ssl_verification": True,
    }


def _deploy_key_data(*, key_id=200):
    return {
        "id": key_id,
        "title": "Deploy Key",
        "key": "ssh-rsa AAAA...",
        "can_push": False,
    }


def _pipeline_data(*, pipeline_id=300, status="success"):
    return {
        "id": pipeline_id,
        "status": status,
        "ref": "main",
        "web_url": f"https://gitlab.com/test-owner/test-repo/-/pipelines/{pipeline_id}",
        "created_at": "2025-01-01T00:00:00Z",
    }


def _wiki_page_data(*, slug="home"):
    return {
        "slug": slug,
        "title": slug.capitalize(),
        "content": f"# {slug.capitalize()}",
        "web_url": f"https://gitlab.com/test-owner/test-repo/-/wikis/{slug}",
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

    def test_links_is_null_falls_back_to_web_url(self):
        """_links が null（None）の場合は web_url にフォールバックする（AttributeError 防止）。"""
        data = _release_data()
        data["_links"] = None
        data["web_url"] = "https://gitlab.com/test-owner/test-repo/-/releases/v1.0.0"
        rel = GitLabAdapter._to_release(data)
        assert rel.url == "https://gitlab.com/test-owner/test-repo/-/releases/v1.0.0"

    def test_links_without_self_falls_back_to_web_url(self):
        """_links に self キーがない場合は web_url にフォールバックする。"""
        data = _release_data()
        data["_links"] = {}  # self キーなし
        data["web_url"] = "https://gitlab.com/test-owner/test-repo/-/releases/v1.0.0"
        rel = GitLabAdapter._to_release(data)
        assert rel.url == "https://gitlab.com/test-owner/test-repo/-/releases/v1.0.0"

    def test_no_links_field_falls_back_to_web_url(self):
        """_links フィールド自体がない場合は web_url にフォールバックする。"""
        data = _release_data()
        del data["_links"]
        data["web_url"] = "https://gitlab.com/test-owner/test-repo/-/releases/v1.0.0"
        rel = GitLabAdapter._to_release(data)
        assert rel.url == "https://gitlab.com/test-owner/test-repo/-/releases/v1.0.0"

    def test_non_dict_links_raises_gfo_error(self):
        """_links が dict 以外の truthy 値のとき AttributeError でなく GfoError になる。"""
        from gfo.exceptions import GfoError

        data = _release_data()
        data["_links"] = "not a dict"
        with pytest.raises(GfoError):
            GitLabAdapter._to_release(data)


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
        assert ms.state == "open"  # GitLab "active" → 内部表現 "open"

    def test_closed_state(self):
        data = _milestone_data().copy()
        data["state"] = "closed"
        ms = GitLabAdapter._to_milestone(data)
        assert ms.state == "closed"


# --- PR (MR) 系 ---


class TestListPullRequests:
    def test_open(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/merge_requests",
            json=[_mr_data()],
            status=200,
        )
        prs = gitlab_adapter.list_pull_requests()
        assert len(prs) == 1
        assert prs[0].state == "open"
        req = mock_responses.calls[0].request
        assert "state=opened" in req.url

    def test_merged_filter(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/merge_requests",
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
            responses.GET,
            f"{PROJECT}/merge_requests",
            json=[_mr_data(iid=1)],
            status=200,
            headers={"X-Next-Page": "2"},
        )
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/merge_requests",
            json=[_mr_data(iid=2)],
            status=200,
        )
        prs = gitlab_adapter.list_pull_requests(limit=10)
        assert len(prs) == 2

    def test_pagination_limit_truncates(self, mock_responses, gitlab_adapter):
        """limit=1 のとき 1 ページ目の 1 件で打ち切られる。"""
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/merge_requests",
            json=[_mr_data(iid=1), _mr_data(iid=2)],
            status=200,
            headers={"X-Next-Page": "2"},
        )
        prs = gitlab_adapter.list_pull_requests(limit=1)
        assert len(prs) == 1
        assert prs[0].number == 1
        assert len(mock_responses.calls) == 1  # 2 ページ目へのリクエストなし

    def test_all_state_sends_all_param(self, mock_responses, gitlab_adapter):
        """state='all' のとき state=all を API に送る（GitLab API は 'all' をサポートする）。"""
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/merge_requests",
            json=[_mr_data(iid=1), _mr_data(iid=2, state="merged")],
            status=200,
        )
        prs = gitlab_adapter.list_pull_requests(state="all")
        assert len(prs) == 2
        req = mock_responses.calls[0].request
        assert "state=all" in req.url


class TestCreatePullRequest:
    def test_create(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST,
            f"{PROJECT}/merge_requests",
            json=_mr_data(),
            status=201,
        )
        pr = gitlab_adapter.create_pull_request(
            title="MR !1",
            body="desc",
            base="main",
            head="feature",
        )
        assert isinstance(pr, PullRequest)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["source_branch"] == "feature"
        assert req_body["target_branch"] == "main"
        assert req_body["draft"] is False

    def test_create_draft(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST,
            f"{PROJECT}/merge_requests",
            json=_mr_data(draft=True),
            status=201,
        )
        _ = gitlab_adapter.create_pull_request(
            title="Draft",
            body="",
            base="main",
            head="feature",
            draft=True,
        )
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["draft"] is True


class TestGetPullRequest:
    def test_get(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/merge_requests/42",
            json=_mr_data(iid=42),
            status=200,
        )
        pr = gitlab_adapter.get_pull_request(42)
        assert pr.number == 42


class TestMergePullRequest:
    def test_merge(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.PUT,
            f"{PROJECT}/merge_requests/1/merge",
            json={"state": "merged"},
            status=200,
        )
        gitlab_adapter.merge_pull_request(1)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body == {}  # method="merge" は追加 payload なし

    def test_merge_squash(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.PUT,
            f"{PROJECT}/merge_requests/1/merge",
            json={"state": "merged"},
            status=200,
        )
        gitlab_adapter.merge_pull_request(1, method="squash")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body.get("squash") is True
        assert "merge_method" not in req_body

    def test_merge_rebase_calls_rebase_endpoint(self, mock_responses, gitlab_adapter):
        """method="rebase" は /merge ではなく /rebase エンドポイントを呼ぶ。"""
        mock_responses.add(
            responses.PUT,
            f"{PROJECT}/merge_requests/2/rebase",
            json={},
            status=200,
        )
        gitlab_adapter.merge_pull_request(2, method="rebase")
        assert len(mock_responses.calls) == 1
        assert "/rebase" in mock_responses.calls[0].request.url

    def test_merge_invalid_method_raises(self, gitlab_adapter):
        from gfo.exceptions import GfoError

        with pytest.raises(GfoError, match="method must be one of"):
            gitlab_adapter.merge_pull_request(1, method="fast-forward")


class TestClosePullRequest:
    def test_close(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.PUT,
            f"{PROJECT}/merge_requests/1",
            json=_mr_data(state="closed"),
            status=200,
        )
        gitlab_adapter.close_pull_request(1)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["state_event"] == "close"


class TestReopenPullRequest:
    def test_reopen(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.PUT,
            f"{PROJECT}/merge_requests/1",
            json=_mr_data(state="opened"),
            status=200,
        )
        gitlab_adapter.reopen_pull_request(1)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["state_event"] == "reopen"


class TestCheckoutRefspec:
    def test_refspec(self, gitlab_adapter):
        assert gitlab_adapter.get_pr_checkout_refspec(42) == "refs/merge-requests/42/head"


# --- Issue 系 ---


class TestListIssues:
    def test_list(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/issues",
            json=[_issue_data(iid=1), _issue_data(iid=2)],
            status=200,
        )
        issues = gitlab_adapter.list_issues()
        assert len(issues) == 2

    def test_with_filters(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/issues",
            json=[_issue_data()],
            status=200,
        )
        issues = gitlab_adapter.list_issues(assignee="dev1", label="bug")
        assert len(issues) == 1
        req = mock_responses.calls[0].request
        assert "assignee_username=dev1" in req.url
        assert "labels=bug" in req.url

    def test_all_state_sends_all_param(self, mock_responses, gitlab_adapter):
        """state='all' のとき state=all を API に送る（GitLab API は 'all' をサポートする）。"""
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/issues",
            json=[_issue_data(iid=1), _issue_data(iid=2)],
            status=200,
        )
        issues = gitlab_adapter.list_issues(state="all")
        assert len(issues) == 2
        req = mock_responses.calls[0].request
        assert "state=all" in req.url


class TestCreateIssue:
    def test_create(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST,
            f"{PROJECT}/issues",
            json=_issue_data(),
            status=201,
        )
        issue = gitlab_adapter.create_issue(title="Issue #1", body="body")
        assert isinstance(issue, Issue)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert "assignee_username" not in req_body
        assert "labels" not in req_body

    def test_create_with_assignee_and_label(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST,
            f"{PROJECT}/issues",
            json=_issue_data(),
            status=201,
        )
        gitlab_adapter.create_issue(
            title="Issue",
            assignee="dev1",
            label="bug",
        )
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["assignee_username"] == "dev1"
        assert req_body["labels"] == "bug"


class TestGetIssue:
    def test_get(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/issues/5",
            json=_issue_data(iid=5),
            status=200,
        )
        issue = gitlab_adapter.get_issue(5)
        assert issue.number == 5


class TestCloseIssue:
    def test_close(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.PUT,
            f"{PROJECT}/issues/3",
            json=_issue_data(iid=3, state="closed"),
            status=200,
        )
        gitlab_adapter.close_issue(3)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["state_event"] == "close"


class TestReopenIssue:
    def test_reopen(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.PUT,
            f"{PROJECT}/issues/3",
            json=_issue_data(iid=3, state="opened"),
            status=200,
        )
        gitlab_adapter.reopen_issue(3)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["state_event"] == "reopen"


# --- Repository 系 ---


class TestListRepositories:
    def test_with_owner(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/users/someone/projects",
            json=[_repo_data()],
            status=200,
        )
        repos = gitlab_adapter.list_repositories(owner="someone")
        assert len(repos) == 1

    def test_no_owner(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/projects",
            json=[_repo_data()],
            status=200,
        )
        repos = gitlab_adapter.list_repositories()
        assert len(repos) == 1

    def test_owner_with_special_chars_is_encoded(self, mock_responses, gitlab_adapter):
        """list_repositories(owner="...") で特殊文字が URL エンコードされる（R41-01）。"""
        mock_responses.add(
            responses.GET,
            f"{BASE}/users/org%2Fsub/projects",
            json=[_repo_data()],
            status=200,
        )
        gitlab_adapter.list_repositories(owner="org/sub")
        assert "%2F" in mock_responses.calls[0].request.url


class TestCreateRepository:
    def test_create(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST,
            f"{BASE}/projects",
            json=_repo_data(),
            status=201,
        )
        repo = gitlab_adapter.create_repository(name="test-repo")
        assert isinstance(repo, Repository)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["name"] == "test-repo"
        assert req_body["visibility"] == "public"


class TestGetRepository:
    def test_get(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/projects/{quote('other/other-repo', safe='')}",
            json=_repo_data(name="other-repo", path_with_namespace="other/other-repo"),
            status=200,
        )
        repo = gitlab_adapter.get_repository(owner="other", name="other-repo")
        assert repo.name == "other-repo"

    def test_get_defaults(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{PROJECT}",
            json=_repo_data(),
            status=200,
        )
        repo = gitlab_adapter.get_repository()
        assert repo.full_name == "test-owner/test-repo"


# --- Release 系 ---


class TestListReleases:
    def test_list(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/releases",
            json=[_release_data()],
            status=200,
        )
        releases = gitlab_adapter.list_releases()
        assert len(releases) == 1
        assert releases[0].tag == "v1.0.0"


class TestCreateRelease:
    def test_create(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{PROJECT}",
            json=_repo_data(),
            status=200,
        )
        mock_responses.add(
            responses.POST,
            f"{PROJECT}/releases",
            json=_release_data(),
            status=201,
        )
        rel = gitlab_adapter.create_release(tag="v1.0.0", title="Release v1.0.0")
        assert isinstance(rel, Release)
        req_body = json.loads(mock_responses.calls[1].request.body)
        assert req_body["tag_name"] == "v1.0.0"
        assert req_body["ref"] == "main"

    def test_create_prerelease(self, mock_responses, gitlab_adapter):
        """prerelease=True のとき upcoming_release がペイロードに含まれる。"""
        mock_responses.add(
            responses.GET,
            f"{PROJECT}",
            json=_repo_data(),
            status=200,
        )
        mock_responses.add(
            responses.POST,
            f"{PROJECT}/releases",
            json=_release_data(),
            status=201,
        )
        gitlab_adapter.create_release(tag="v1.0.0-rc1", prerelease=True)
        req_body = json.loads(mock_responses.calls[1].request.body)
        assert req_body["upcoming_release"] is True


class TestGetRelease:
    def test_get(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/releases/v1.0.0",
            json=_release_data(),
            status=200,
        )
        rel = gitlab_adapter.get_release(tag="v1.0.0")
        assert isinstance(rel, Release)
        assert rel.tag == "v1.0.0"


class TestUpdateRelease:
    def test_update(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.PUT,
            f"{PROJECT}/releases/v1.0.0",
            json=_release_data(),
            status=200,
        )
        rel = gitlab_adapter.update_release(tag="v1.0.0", title="Updated")
        assert isinstance(rel, Release)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["name"] == "Updated"

    def test_update_notes(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.PUT,
            f"{PROJECT}/releases/v1.0.0",
            json=_release_data(),
            status=200,
        )
        gitlab_adapter.update_release(tag="v1.0.0", notes="New notes")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["description"] == "New notes"

    def test_update_prerelease(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.PUT,
            f"{PROJECT}/releases/v1.0.0",
            json=_release_data(),
            status=200,
        )
        gitlab_adapter.update_release(tag="v1.0.0", prerelease=True)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["upcoming_release"] is True

    def test_update_no_optional_fields(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.PUT,
            f"{PROJECT}/releases/v1.0.0",
            json=_release_data(),
            status=200,
        )
        gitlab_adapter.update_release(tag="v1.0.0")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert "name" not in req_body
        assert "description" not in req_body
        assert "upcoming_release" not in req_body


# --- Label 系 ---


class TestListLabels:
    def test_list(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/labels",
            json=[_label_data(), _label_data(name="enhancement")],
            status=200,
        )
        labels = gitlab_adapter.list_labels()
        assert len(labels) == 2

    def test_list_fetches_all_pages(self, mock_responses, gitlab_adapter):
        """list_labels は limit=0 で全ページを取得する（30 件上限なし）。"""
        # 1 ページ目: 20 件 + X-Next-Page: 2
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/labels",
            json=[_label_data(name=f"label-{i}") for i in range(20)],
            headers={"X-Next-Page": "2"},
            status=200,
        )
        # 2 ページ目: 1 件 + X-Next-Page なし（最終ページ）
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/labels",
            json=[_label_data(name="last-label")],
            status=200,
        )
        labels = gitlab_adapter.list_labels()
        assert len(labels) == 21


class TestCreateLabel:
    def test_create(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST,
            f"{PROJECT}/labels",
            json=_label_data(),
            status=201,
        )
        label = gitlab_adapter.create_label(name="bug", color="d73a4a")
        assert label.name == "bug"
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["color"] == "#d73a4a"

    def test_create_optional_fields(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST,
            f"{PROJECT}/labels",
            json={"name": "minimal", "color": None, "description": None},
            status=201,
        )
        gitlab_adapter.create_label(name="minimal")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert "color" not in req_body
        assert "description" not in req_body

    def test_create_with_description(self, mock_responses, gitlab_adapter):
        """description を渡すとペイロードに含まれる。"""
        mock_responses.add(
            responses.POST,
            f"{PROJECT}/labels",
            json=_label_data(),
            status=201,
        )
        gitlab_adapter.create_label(name="bug", color="d73a4a", description="Bug report")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["description"] == "Bug report"


# --- Milestone 系 ---


class TestListMilestones:
    def test_list(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/milestones",
            json=[_milestone_data()],
            status=200,
        )
        milestones = gitlab_adapter.list_milestones()
        assert len(milestones) == 1
        assert milestones[0].title == "v1.0"

    def test_list_fetches_all_pages(self, mock_responses, gitlab_adapter):
        """list_milestones は limit=0 で全ページを取得する（30 件上限なし）。"""
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/milestones",
            json=[_milestone_data() for _ in range(20)],
            headers={"X-Next-Page": "2"},
            status=200,
        )
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/milestones",
            json=[_milestone_data()],
            status=200,
        )
        milestones = gitlab_adapter.list_milestones()
        assert len(milestones) == 21


class TestCreateMilestone:
    def test_create(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST,
            f"{PROJECT}/milestones",
            json=_milestone_data(),
            status=201,
        )
        ms = gitlab_adapter.create_milestone(title="v1.0", due_date="2025-06-01")
        assert isinstance(ms, Milestone)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["due_date"] == "2025-06-01"

    def test_create_optional_fields(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST,
            f"{PROJECT}/milestones",
            json=_milestone_data(),
            status=201,
        )
        gitlab_adapter.create_milestone(title="v1.0")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert "description" not in req_body
        assert "due_date" not in req_body

    def test_create_with_description(self, mock_responses, gitlab_adapter):
        """description を渡すとペイロードに含まれる。"""
        mock_responses.add(
            responses.POST,
            f"{PROJECT}/milestones",
            json=_milestone_data(),
            status=201,
        )
        gitlab_adapter.create_milestone(title="v1.0", description="First stable release")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["description"] == "First stable release"


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

    def test_malformed_pr_raises_gfo_error(self, mock_responses, gitlab_adapter):
        """_to_pull_request で必須フィールド欠落 → GfoError。"""
        from gfo.exceptions import GfoError

        mock_responses.add(
            responses.GET,
            f"{PROJECT}/merge_requests/1",
            json={"incomplete": True},
            status=200,
        )
        with pytest.raises(GfoError):
            gitlab_adapter.get_pull_request(1)

    def test_malformed_issue_raises_gfo_error(self, mock_responses, gitlab_adapter):
        """_to_issue で必須フィールド欠落 → GfoError。"""
        from gfo.exceptions import GfoError

        mock_responses.add(
            responses.GET,
            f"{PROJECT}/issues/1",
            json={"incomplete": True},
            status=200,
        )
        with pytest.raises(GfoError):
            gitlab_adapter.get_issue(1)

    def test_malformed_milestone_raises_gfo_error(self, mock_responses, gitlab_adapter):
        """_to_milestone で必須フィールド欠落 → GfoError。"""
        from gfo.exceptions import GfoError

        mock_responses.add(
            responses.GET,
            f"{PROJECT}/milestones",
            json=[{"incomplete": True}],
            status=200,
        )
        with pytest.raises(GfoError):
            gitlab_adapter.list_milestones()

    def test_malformed_repository_raises_gfo_error(self, mock_responses, gitlab_adapter):
        """_to_repository で必須フィールド欠落 → GfoError。"""
        from gfo.exceptions import GfoError

        mock_responses.add(
            responses.GET,
            f"{PROJECT}",
            json={"incomplete": True},
            status=200,
        )
        with pytest.raises(GfoError):
            gitlab_adapter.get_repository()

    def test_malformed_release_raises_gfo_error(self, mock_responses, gitlab_adapter):
        """_to_release で必須フィールド欠落 → GfoError。"""
        from gfo.exceptions import GfoError

        mock_responses.add(
            responses.GET,
            f"{PROJECT}/releases",
            json=[{"incomplete": True}],
            status=200,
        )
        with pytest.raises(GfoError):
            gitlab_adapter.list_releases()

    def test_malformed_label_raises_gfo_error(self, mock_responses, gitlab_adapter):
        """_to_label で必須フィールド欠落 → GfoError。"""
        from gfo.exceptions import GfoError

        mock_responses.add(
            responses.GET,
            f"{PROJECT}/labels",
            json=[{"incomplete": True}],
            status=200,
        )
        with pytest.raises(GfoError):
            gitlab_adapter.list_labels()


# --- Delete 系 ---


class TestDeleteRelease:
    def test_delete(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{PROJECT}/releases/v1.0.0",
            status=200,
        )
        gitlab_adapter.delete_release(tag="v1.0.0")

    def test_tag_url_encoded(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{PROJECT}/releases/v1.0.0%2Brc1",
            status=200,
        )
        gitlab_adapter.delete_release(tag="v1.0.0+rc1")
        assert "%2B" in mock_responses.calls[0].request.url


class TestDeleteLabel:
    def test_delete(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{PROJECT}/labels/bug",
            status=204,
        )
        gitlab_adapter.delete_label(name="bug")

    def test_name_url_encoded(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{PROJECT}/labels/my%20label",
            status=204,
        )
        gitlab_adapter.delete_label(name="my label")
        assert "%20" in mock_responses.calls[0].request.url


class TestUpdateLabel:
    def test_update(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.PUT,
            f"{PROJECT}/labels/bug",
            json=_label_data(name="bug-fix"),
            status=200,
        )
        label = gitlab_adapter.update_label(name="bug", new_name="bug-fix")
        assert label.name == "bug-fix"
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["name"] == "bug-fix"

    def test_update_color(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.PUT,
            f"{PROJECT}/labels/bug",
            json=_label_data(),
            status=200,
        )
        gitlab_adapter.update_label(name="bug", color="ff0000")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["color"] == "#ff0000"

    def test_update_description(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.PUT,
            f"{PROJECT}/labels/bug",
            json=_label_data(),
            status=200,
        )
        gitlab_adapter.update_label(name="bug", description="Updated desc")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["description"] == "Updated desc"

    def test_name_url_encoded(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.PUT,
            f"{PROJECT}/labels/my%20label",
            json=_label_data(name="my label"),
            status=200,
        )
        gitlab_adapter.update_label(name="my label", new_name="renamed")
        assert "%20" in mock_responses.calls[0].request.url

    def test_optional_fields_omitted(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.PUT,
            f"{PROJECT}/labels/bug",
            json=_label_data(),
            status=200,
        )
        gitlab_adapter.update_label(name="bug")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert "name" not in req_body
        assert "color" not in req_body
        assert "description" not in req_body


class TestDeleteMilestone:
    def test_delete(self, mock_responses, gitlab_adapter):
        # delete_milestone は iid→global id 解決のため GET を先に呼ぶ
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/milestones",
            json=[
                {
                    "id": 99,
                    "iid": 3,
                    "title": "v1.0",
                    "state": "active",
                    "description": None,
                    "due_date": None,
                }
            ],
            status=200,
        )
        mock_responses.add(
            responses.DELETE,
            f"{PROJECT}/milestones/99",
            status=204,
        )
        gitlab_adapter.delete_milestone(number=3)


def _milestone_iid_resolve_mocks(mock_responses, iid=3, global_id=99):
    """iid→global id 解決用の GET モックを登録する。"""
    mock_responses.add(
        responses.GET,
        f"{PROJECT}/milestones",
        json=[
            {
                "id": global_id,
                "iid": iid,
                "title": "v1.0",
                "state": "active",
                "description": None,
                "due_date": None,
            }
        ],
        status=200,
    )


class TestGetMilestone:
    def test_get(self, mock_responses, gitlab_adapter):
        _milestone_iid_resolve_mocks(mock_responses, iid=1, global_id=42)
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/milestones/42",
            json=_milestone_data(),
            status=200,
        )
        ms = gitlab_adapter.get_milestone(1)
        assert isinstance(ms, Milestone)
        assert ms.title == "v1.0"

    def test_get_not_found(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/milestones",
            json=[],
            status=200,
        )
        with pytest.raises(NotFoundError):
            gitlab_adapter.get_milestone(999)


class TestUpdateMilestone:
    def test_update_title(self, mock_responses, gitlab_adapter):
        _milestone_iid_resolve_mocks(mock_responses, iid=1, global_id=42)
        mock_responses.add(
            responses.PUT,
            f"{PROJECT}/milestones/42",
            json=_milestone_data(),
            status=200,
        )
        ms = gitlab_adapter.update_milestone(1, title="v2.0")
        assert isinstance(ms, Milestone)
        req_body = json.loads(mock_responses.calls[1].request.body)
        assert req_body["title"] == "v2.0"

    def test_update_state_closed(self, mock_responses, gitlab_adapter):
        _milestone_iid_resolve_mocks(mock_responses, iid=1, global_id=42)
        mock_responses.add(
            responses.PUT,
            f"{PROJECT}/milestones/42",
            json=_milestone_data(),
            status=200,
        )
        gitlab_adapter.update_milestone(1, state="closed")
        req_body = json.loads(mock_responses.calls[1].request.body)
        assert req_body["state_event"] == "close"

    def test_update_state_open(self, mock_responses, gitlab_adapter):
        _milestone_iid_resolve_mocks(mock_responses, iid=1, global_id=42)
        mock_responses.add(
            responses.PUT,
            f"{PROJECT}/milestones/42",
            json=_milestone_data(),
            status=200,
        )
        gitlab_adapter.update_milestone(1, state="open")
        req_body = json.loads(mock_responses.calls[1].request.body)
        assert req_body["state_event"] == "activate"

    def test_update_due_date(self, mock_responses, gitlab_adapter):
        _milestone_iid_resolve_mocks(mock_responses, iid=1, global_id=42)
        mock_responses.add(
            responses.PUT,
            f"{PROJECT}/milestones/42",
            json=_milestone_data(),
            status=200,
        )
        gitlab_adapter.update_milestone(1, due_date="2026-06-01")
        req_body = json.loads(mock_responses.calls[1].request.body)
        assert req_body["due_date"] == "2026-06-01"

    def test_update_optional_fields_omitted(self, mock_responses, gitlab_adapter):
        _milestone_iid_resolve_mocks(mock_responses, iid=1, global_id=42)
        mock_responses.add(
            responses.PUT,
            f"{PROJECT}/milestones/42",
            json=_milestone_data(),
            status=200,
        )
        gitlab_adapter.update_milestone(1)
        req_body = json.loads(mock_responses.calls[1].request.body)
        assert "title" not in req_body
        assert "description" not in req_body
        assert "due_date" not in req_body
        assert "state_event" not in req_body


class TestDeleteIssue:
    def test_delete(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{PROJECT}/issues/5",
            status=204,
        )
        gitlab_adapter.delete_issue(5)
        assert mock_responses.calls[0].request.method == "DELETE"
        assert mock_responses.calls[0].request.url.endswith("/issues/5")


class TestDeleteRepository:
    def test_delete(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.DELETE,
            PROJECT,
            status=202,
        )
        gitlab_adapter.delete_repository()
        assert mock_responses.calls[0].request.method == "DELETE"


# --- Comment 系 ---


class TestListComments:
    def test_list_issue(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/issues/1/notes",
            json=[_comment_data()],
            status=200,
        )
        comments = gitlab_adapter.list_comments("issue", 1)
        assert len(comments) == 1
        assert isinstance(comments[0], Comment)

    def test_list_pr(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/merge_requests/1/notes",
            json=[_comment_data()],
            status=200,
        )
        comments = gitlab_adapter.list_comments("pr", 1)
        assert len(comments) == 1


class TestCreateComment:
    def test_create_issue(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST,
            f"{PROJECT}/issues/1/notes",
            json=_comment_data(),
            status=201,
        )
        comment = gitlab_adapter.create_comment("issue", 1, body="Hello")
        assert isinstance(comment, Comment)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["body"] == "Hello"

    def test_create_pr(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST,
            f"{PROJECT}/merge_requests/1/notes",
            json=_comment_data(),
            status=201,
        )
        comment = gitlab_adapter.create_comment("pr", 1, body="LGTM")
        assert isinstance(comment, Comment)


class TestUpdateCommentNotSupported:
    def test_raises(self, gitlab_adapter):
        with pytest.raises(NotSupportedError):
            gitlab_adapter.update_comment("pr", 10, body="Updated")


class TestDeleteCommentNotSupported:
    def test_raises(self, gitlab_adapter):
        with pytest.raises(NotSupportedError):
            gitlab_adapter.delete_comment("pr", 10)


# --- PR Update / Issue Update ---


class TestUpdatePullRequest:
    def test_update_title(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.PUT,
            f"{PROJECT}/merge_requests/1",
            json=_mr_data(),
            status=200,
        )
        pr = gitlab_adapter.update_pull_request(1, title="New Title")
        assert isinstance(pr, PullRequest)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["title"] == "New Title"

    def test_update_body(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.PUT,
            f"{PROJECT}/merge_requests/1",
            json=_mr_data(),
            status=200,
        )
        gitlab_adapter.update_pull_request(1, body="New desc")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["description"] == "New desc"

    def test_update_base(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.PUT,
            f"{PROJECT}/merge_requests/1",
            json=_mr_data(),
            status=200,
        )
        gitlab_adapter.update_pull_request(1, base="develop")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["target_branch"] == "develop"


class TestUpdateIssue:
    def test_update_title(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.PUT,
            f"{PROJECT}/issues/1",
            json=_issue_data(),
            status=200,
        )
        issue = gitlab_adapter.update_issue(1, title="New Title")
        assert isinstance(issue, Issue)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["title"] == "New Title"

    def test_update_assignee(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.PUT,
            f"{PROJECT}/issues/1",
            json=_issue_data(),
            status=200,
        )
        gitlab_adapter.update_issue(1, assignee="devuser")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["assignee_username"] == "devuser"


# --- Review 系 ---


class TestListReviews:
    def test_list(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/merge_requests/1/approvals",
            json=_review_data_approved(),
            status=200,
        )
        reviews = gitlab_adapter.list_reviews(1)
        assert len(reviews) == 1
        assert isinstance(reviews[0], Review)
        assert reviews[0].state == "approved"


class TestCreateReview:
    def test_approve(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST,
            f"{PROJECT}/merge_requests/1/approve",
            json={"approved": True},
            status=201,
        )
        gitlab_adapter.create_review(1, state="approve")
        assert mock_responses.calls[0].request.method == "POST"

    def test_request_changes(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST,
            f"{PROJECT}/merge_requests/1/unapprove",
            json={"approved": False},
            status=201,
        )
        gitlab_adapter.create_review(1, state="request_changes")

    def test_comment_state(self, mock_responses, gitlab_adapter):
        """COMMENT 状態（else 分岐）はノートとして作成し state="commented" を返す。"""
        mock_responses.add(
            responses.POST,
            f"{PROJECT}/merge_requests/1/notes",
            json={"id": 42, "author": {"username": "commenter"}, "body": "LGTM"},
            status=201,
        )
        review = gitlab_adapter.create_review(1, state="COMMENT", body="LGTM")
        assert review.state == "commented"
        assert review.id == 42


# --- Branch 系 ---


class TestListBranches:
    def test_list(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/repository/branches",
            json=[_branch_data()],
            status=200,
        )
        branches = gitlab_adapter.list_branches()
        assert len(branches) == 1
        assert isinstance(branches[0], Branch)
        assert branches[0].name == "feature"


class TestCreateBranch:
    def test_create(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST,
            f"{PROJECT}/repository/branches",
            json=_branch_data(name="new-branch"),
            status=201,
        )
        branch = gitlab_adapter.create_branch(name="new-branch", ref="main")
        assert isinstance(branch, Branch)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["branch"] == "new-branch"
        assert req_body["ref"] == "main"


class TestDeleteBranch:
    def test_delete(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{PROJECT}/repository/branches/feature",
            status=204,
        )
        gitlab_adapter.delete_branch(name="feature")
        assert mock_responses.calls[0].request.method == "DELETE"


# --- Tag 系 ---


class TestListTags:
    def test_list(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/repository/tags",
            json=[_tag_data()],
            status=200,
        )
        tags = gitlab_adapter.list_tags()
        assert len(tags) == 1
        assert isinstance(tags[0], Tag)
        assert tags[0].name == "v1.0.0"


class TestCreateTag:
    def test_create(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST,
            f"{PROJECT}/repository/tags",
            json=_tag_data(name="v2.0.0"),
            status=201,
        )
        tag = gitlab_adapter.create_tag(name="v2.0.0", ref="main")
        assert isinstance(tag, Tag)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["tag_name"] == "v2.0.0"
        assert req_body["ref"] == "main"


class TestDeleteTag:
    def test_delete(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{PROJECT}/repository/tags/v1.0.0",
            status=204,
        )
        gitlab_adapter.delete_tag(name="v1.0.0")
        assert mock_responses.calls[0].request.method == "DELETE"


# --- CommitStatus 系 ---


class TestListCommitStatuses:
    def test_list(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/repository/commits/abc123/statuses",
            json=[_commit_status_data()],
            status=200,
        )
        statuses = gitlab_adapter.list_commit_statuses("abc123")
        assert len(statuses) == 1
        assert isinstance(statuses[0], CommitStatus)


class TestCreateCommitStatus:
    def test_create(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST,
            f"{PROJECT}/statuses/abc123",
            json=_commit_status_data(),
            status=201,
        )
        status = gitlab_adapter.create_commit_status("abc123", state="success", context="ci/test")
        assert isinstance(status, CommitStatus)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["state"] == "success"
        assert req_body["name"] == "ci/test"


# --- File 系 ---


class TestGetFileContent:
    def test_get(self, mock_responses, gitlab_adapter):
        import base64 as _b64

        content_b64 = _b64.b64encode(b"file content").decode()
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/repository/files/README.md",
            json={"content": content_b64, "blob_id": "sha1", "commit_id": "sha1"},
            status=200,
        )
        content, sha = gitlab_adapter.get_file_content("README.md")
        assert content == "file content"


class TestCreateOrUpdateFile:
    def test_create_new(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST,
            f"{PROJECT}/repository/files/new-file.md",
            json={"file_name": "new-file.md", "branch": "main"},
            status=201,
        )
        gitlab_adapter.create_or_update_file(
            "new-file.md", content="new content", message="Add file"
        )
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["commit_message"] == "Add file"

    def test_update_existing(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.PUT,
            f"{PROJECT}/repository/files/existing.md",
            json={"file_name": "existing.md", "branch": "main"},
            status=200,
        )
        gitlab_adapter.create_or_update_file(
            "existing.md", content="updated", message="Update", sha="oldsha"
        )
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["commit_message"] == "Update"


class TestDeleteFile:
    def test_delete(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{PROJECT}/repository/files/to-delete.md",
            status=204,
        )
        gitlab_adapter.delete_file("to-delete.md", sha="filsha", message="Delete file")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["commit_message"] == "Delete file"


# --- Fork 系 ---


class TestForkRepository:
    def test_fork(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST,
            f"{PROJECT}/fork",
            json=_repo_data(),
            status=202,
        )
        repo = gitlab_adapter.fork_repository()
        assert isinstance(repo, Repository)

    def test_fork_with_org(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST,
            f"{PROJECT}/fork",
            json=_repo_data(),
            status=202,
        )
        gitlab_adapter.fork_repository(organization="myorg")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["namespace_path"] == "myorg"


# --- Webhook 系 ---


class TestListWebhooks:
    def test_list(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/hooks",
            json=[_webhook_data()],
            status=200,
        )
        webhooks = gitlab_adapter.list_webhooks()
        assert len(webhooks) == 1
        assert isinstance(webhooks[0], Webhook)


class TestCreateWebhook:
    def test_create(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST,
            f"{PROJECT}/hooks",
            json=_webhook_data(),
            status=201,
        )
        webhook = gitlab_adapter.create_webhook(url="https://example.com/hook", events=["push"])
        assert isinstance(webhook, Webhook)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["url"] == "https://example.com/hook"
        assert req_body["push_events"] is True


class TestDeleteWebhook:
    def test_delete(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{PROJECT}/hooks/100",
            status=204,
        )
        gitlab_adapter.delete_webhook(hook_id=100)
        assert mock_responses.calls[0].request.method == "DELETE"


class TestTestWebhook:
    def test_test(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST,
            f"{PROJECT}/hooks/100/test/push_events",
            status=200,
        )
        gitlab_adapter.test_webhook(hook_id=100)
        assert mock_responses.calls[0].request.method == "POST"


# --- DeployKey 系 ---


class TestListDeployKeys:
    def test_list(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/deploy_keys",
            json=[_deploy_key_data()],
            status=200,
        )
        keys = gitlab_adapter.list_deploy_keys()
        assert len(keys) == 1
        assert isinstance(keys[0], DeployKey)


class TestCreateDeployKey:
    def test_create(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST,
            f"{PROJECT}/deploy_keys",
            json=_deploy_key_data(),
            status=201,
        )
        key = gitlab_adapter.create_deploy_key(
            title="Deploy Key", key="ssh-rsa AAAA...", read_only=True
        )
        assert isinstance(key, DeployKey)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["can_push"] is False


class TestDeleteDeployKey:
    def test_delete(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{PROJECT}/deploy_keys/200",
            status=204,
        )
        gitlab_adapter.delete_deploy_key(key_id=200)
        assert mock_responses.calls[0].request.method == "DELETE"


# --- Collaborator 系 ---


class TestListCollaborators:
    def test_list(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/members",
            json=[{"username": "collab1"}, {"username": "collab2"}],
            status=200,
        )
        collabs = gitlab_adapter.list_collaborators()
        assert collabs == ["collab1", "collab2"]


class TestAddCollaborator:
    def test_add(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/users",
            json=[{"id": 42, "username": "newuser"}],
            status=200,
        )
        mock_responses.add(
            responses.POST,
            f"{PROJECT}/members",
            json={"id": 42, "username": "newuser", "access_level": 40},
            status=201,
        )
        gitlab_adapter.add_collaborator(username="newuser")
        assert mock_responses.calls[1].request.method == "POST"


class TestRemoveCollaborator:
    def test_remove(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/users",
            json=[{"id": 42, "username": "olduser"}],
            status=200,
        )
        mock_responses.add(
            responses.DELETE,
            f"{PROJECT}/members/42",
            status=204,
        )
        gitlab_adapter.remove_collaborator(username="olduser")
        assert mock_responses.calls[1].request.method == "DELETE"


# --- Pipeline 系 ---


class TestListPipelines:
    def test_list(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/pipelines",
            json=[_pipeline_data()],
            status=200,
        )
        pipelines = gitlab_adapter.list_pipelines()
        assert len(pipelines) == 1
        assert isinstance(pipelines[0], Pipeline)

    def test_with_ref(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/pipelines",
            json=[_pipeline_data()],
            status=200,
        )
        gitlab_adapter.list_pipelines(ref="main")
        req = mock_responses.calls[0].request
        assert "ref=main" in req.url


class TestGetPipeline:
    def test_get(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/pipelines/300",
            json=_pipeline_data(pipeline_id=300),
            status=200,
        )
        pipeline = gitlab_adapter.get_pipeline(300)
        assert isinstance(pipeline, Pipeline)
        assert pipeline.id == 300


class TestCancelPipeline:
    def test_cancel(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST,
            f"{PROJECT}/pipelines/300/cancel",
            json=_pipeline_data(pipeline_id=300, status="canceled"),
            status=200,
        )
        gitlab_adapter.cancel_pipeline(300)
        assert mock_responses.calls[0].request.method == "POST"


class TestTriggerPipeline:
    def test_trigger(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST,
            f"{PROJECT}/pipeline",
            json=_pipeline_data(pipeline_id=400),
            status=201,
        )
        pipeline = gitlab_adapter.trigger_pipeline("main")
        assert isinstance(pipeline, Pipeline)
        req = mock_responses.calls[0].request
        body = json.loads(req.body)
        assert body["ref"] == "main"

    def test_trigger_with_inputs(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST,
            f"{PROJECT}/pipeline",
            json=_pipeline_data(pipeline_id=400),
            status=201,
        )
        gitlab_adapter.trigger_pipeline("main", inputs={"KEY": "val"})
        req = mock_responses.calls[0].request
        body = json.loads(req.body)
        assert body["variables"] == [{"key": "KEY", "value": "val"}]

    def test_trigger_404(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST,
            f"{PROJECT}/pipeline",
            status=404,
        )
        with pytest.raises(NotFoundError):
            gitlab_adapter.trigger_pipeline("main")


class TestRetryPipeline:
    def test_retry(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST,
            f"{PROJECT}/pipelines/300/retry",
            json=_pipeline_data(pipeline_id=300),
            status=200,
        )
        pipeline = gitlab_adapter.retry_pipeline(300)
        assert isinstance(pipeline, Pipeline)
        assert pipeline.id == 300

    def test_retry_404(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST,
            f"{PROJECT}/pipelines/999/retry",
            status=404,
        )
        with pytest.raises(NotFoundError):
            gitlab_adapter.retry_pipeline(999)


class TestGetPipelineLogs:
    def test_logs_with_job_id(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/jobs/42/trace",
            body="job log output",
            status=200,
        )
        logs = gitlab_adapter.get_pipeline_logs(300, job_id=42)
        assert "job log output" in logs

    def test_logs_all_jobs(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/pipelines/300/jobs",
            json=[{"id": 1, "name": "build"}, {"id": 2, "name": "test"}],
            status=200,
        )
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/jobs/1/trace",
            body="build log",
            status=200,
        )
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/jobs/2/trace",
            body="test log",
            status=200,
        )
        logs = gitlab_adapter.get_pipeline_logs(300)
        assert "=== build ===" in logs
        assert "build log" in logs
        assert "=== test ===" in logs
        assert "test log" in logs

    def test_logs_404(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/jobs/999/trace",
            status=404,
        )
        with pytest.raises(NotFoundError):
            gitlab_adapter.get_pipeline_logs(300, job_id=999)


# --- User / Search 系 ---


class TestGetCurrentUser:
    def test_get(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/user",
            json={"username": "testuser", "id": 1},
            status=200,
        )
        user = gitlab_adapter.get_current_user()
        assert user["username"] == "testuser"


class TestSearchRepositories:
    def test_search(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/projects",
            json=[_repo_data()],
            status=200,
        )
        repos = gitlab_adapter.search_repositories("test")
        assert len(repos) >= 1
        assert isinstance(repos[0], Repository)


class TestSearchIssues:
    def test_search(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/issues",
            json=[_issue_data()],
            status=200,
        )
        issues = gitlab_adapter.search_issues("bug")
        assert len(issues) == 1
        assert isinstance(issues[0], Issue)


# --- Wiki 系 ---


class TestListWikiPages:
    def test_list(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/wikis",
            json=[_wiki_page_data()],
            status=200,
        )
        pages = gitlab_adapter.list_wiki_pages()
        assert len(pages) == 1
        assert isinstance(pages[0], WikiPage)


class TestGetWikiPage:
    def test_get(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/wikis/home",
            json=_wiki_page_data(slug="home"),
            status=200,
        )
        page = gitlab_adapter.get_wiki_page("home")
        assert isinstance(page, WikiPage)
        assert page.title == "Home"


class TestCreateWikiPage:
    def test_create(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.POST,
            f"{PROJECT}/wikis",
            json=_wiki_page_data(),
            status=201,
        )
        page = gitlab_adapter.create_wiki_page(title="Home", content="# Home")
        assert isinstance(page, WikiPage)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["title"] == "Home"


class TestUpdateWikiPage:
    def test_update(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.PUT,
            f"{PROJECT}/wikis/home",
            json=_wiki_page_data(),
            status=200,
        )
        page = gitlab_adapter.update_wiki_page("home", title="Home", content="Updated")
        assert isinstance(page, WikiPage)


class TestDeleteWikiPage:
    def test_delete(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{PROJECT}/wikis/home",
            status=204,
        )
        gitlab_adapter.delete_wiki_page("home")
        assert mock_responses.calls[0].request.method == "DELETE"


# --- 変換ヘルパー単体テスト ---


class TestToComment:
    def test_basic(self):
        data = {
            "id": 10,
            "body": "A comment",
            "author": {"username": "commenter"},
            "created_at": "2025-01-01T00:00:00Z",
        }
        comment = GitLabAdapter._to_comment(data)
        assert isinstance(comment, Comment)
        assert comment.id == 10
        assert comment.body == "A comment"
        assert comment.author == "commenter"


class TestToReview:
    def test_approved(self):
        data = {"id": 1, "state": "approved", "user": {"username": "reviewer1"}}
        review = GitLabAdapter._to_review(data)
        assert isinstance(review, Review)
        assert review.state == "approved"

    def test_unapproved(self):
        data = {"id": 2, "state": "unapproved", "user": {"username": "reviewer2"}}
        review = GitLabAdapter._to_review(data)
        assert isinstance(review, Review)
        assert review.state == "changes_requested"


class TestToBranch:
    def test_basic(self):
        data = {
            "name": "feature",
            "commit": {"id": "abc123"},
            "protected": False,
        }
        branch = GitLabAdapter._to_branch(data)
        assert isinstance(branch, Branch)
        assert branch.name == "feature"
        assert branch.sha == "abc123"


class TestToTag:
    def test_basic(self):
        data = {
            "name": "v1.0.0",
            "commit": {"id": "def456"},
            "message": "Release v1.0.0",
        }
        tag = GitLabAdapter._to_tag(data)
        assert isinstance(tag, Tag)
        assert tag.name == "v1.0.0"
        assert tag.sha == "def456"
        assert tag.message == "Release v1.0.0"


class TestToCommitStatus:
    def test_success(self):
        data = {
            "status": "success",
            "name": "ci/test",
            "description": "Tests passed",
            "target_url": "https://ci.example.com/1",
            "created_at": "2025-01-01T00:00:00Z",
        }
        cs = GitLabAdapter._to_commit_status(data)
        assert isinstance(cs, CommitStatus)
        assert cs.state == "success"
        assert cs.context == "ci/test"

    def test_failed(self):
        data = {"status": "failed", "name": "ci/test", "created_at": "2025-01-01T00:00:00Z"}
        cs = GitLabAdapter._to_commit_status(data)
        assert cs.state == "failure"

    def test_running(self):
        data = {"status": "running", "name": "ci/test", "created_at": "2025-01-01T00:00:00Z"}
        cs = GitLabAdapter._to_commit_status(data)
        assert cs.state == "pending"

    def test_pending(self):
        data = {"status": "pending", "name": "ci/test", "created_at": "2025-01-01T00:00:00Z"}
        cs = GitLabAdapter._to_commit_status(data)
        assert cs.state == "pending"


class TestToWebhook:
    def test_basic(self):
        data = {
            "id": 100,
            "url": "https://example.com/hook",
            "push_events": True,
            "issues_events": True,
            "merge_requests_events": False,
            "tag_push_events": False,
            "note_events": False,
            "confidential_note_events": False,
            "job_events": False,
            "pipeline_events": False,
            "wiki_page_events": False,
            "releases_events": False,
            "enable_ssl_verification": True,
        }
        webhook = GitLabAdapter._to_webhook(data)
        assert isinstance(webhook, Webhook)
        assert webhook.id == 100
        assert webhook.url == "https://example.com/hook"
        assert "push" in webhook.events
        assert "issues" in webhook.events
        assert "merge_requests" not in webhook.events


class TestToDeployKey:
    def test_basic(self):
        data = {
            "id": 200,
            "title": "Deploy Key",
            "key": "ssh-rsa AAAA...",
            "can_push": False,
        }
        dk = GitLabAdapter._to_deploy_key(data)
        assert isinstance(dk, DeployKey)
        assert dk.id == 200
        assert dk.title == "Deploy Key"
        assert dk.key == "ssh-rsa AAAA..."

    def test_can_push_true(self):
        data = {"id": 201, "title": "RW Key", "key": "ssh-rsa BBBB...", "can_push": True}
        dk = GitLabAdapter._to_deploy_key(data)
        assert dk.read_only is False

    def test_can_push_false(self):
        data = {"id": 202, "title": "RO Key", "key": "ssh-rsa CCCC...", "can_push": False}
        dk = GitLabAdapter._to_deploy_key(data)
        assert dk.read_only is True


class TestToPipeline:
    def test_basic(self):
        data = {
            "id": 300,
            "status": "success",
            "ref": "main",
            "web_url": "https://gitlab.com/test-owner/test-repo/-/pipelines/300",
            "created_at": "2025-01-01T00:00:00Z",
        }
        pipeline = GitLabAdapter._to_pipeline(data)
        assert isinstance(pipeline, Pipeline)
        assert pipeline.id == 300
        assert pipeline.status == "success"

    def test_failed_status(self):
        data = {"id": 301, "status": "failed", "ref": "main", "created_at": "2025-01-01T00:00:00Z"}
        pipeline = GitLabAdapter._to_pipeline(data)
        assert pipeline.status == "failure"

    def test_running_status(self):
        data = {
            "id": 302,
            "status": "running",
            "ref": "main",
            "created_at": "2025-01-01T00:00:00Z",
        }
        pipeline = GitLabAdapter._to_pipeline(data)
        assert pipeline.status == "running"


class TestToWikiPage:
    def test_basic(self):
        data = {
            "slug": "home",
            "title": "Home",
            "content": "# Home",
            "web_url": "https://gitlab.com/test-owner/test-repo/-/wikis/home",
        }
        page = GitLabAdapter._to_wiki_page(data)
        assert isinstance(page, WikiPage)
        assert page.title == "Home"
        assert page.content == "# Home"


# --- Phase 2: PR operations ---


class TestGetPullRequestDiff:
    def test_get_diff(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/merge_requests/1/diffs",
            json=[
                {
                    "old_path": "file.py",
                    "new_path": "file.py",
                    "diff": "@@ -1,3 +1,4 @@\n+new line",
                }
            ],
            status=200,
        )
        diff = gitlab_adapter.get_pull_request_diff(1)
        assert "--- a/file.py" in diff
        assert "+++ b/file.py" in diff
        assert "+new line" in diff


class TestListPullRequestChecks:
    def test_list_checks(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/merge_requests/1/pipelines",
            json=[
                {
                    "id": 100,
                    "status": "success",
                    "ref": "feature",
                    "web_url": "https://gitlab.com/pipelines/100",
                    "created_at": "2025-01-01T00:00:00Z",
                }
            ],
            status=200,
        )
        checks = gitlab_adapter.list_pull_request_checks(1)
        assert len(checks) == 1
        assert isinstance(checks[0], CheckRun)
        assert checks[0].name == "feature"
        assert checks[0].status == "success"


class TestListPullRequestFiles:
    def test_list_files(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/merge_requests/1/changes",
            json={
                "changes": [
                    {
                        "new_path": "src/main.py",
                        "old_path": "src/main.py",
                        "new_file": False,
                        "deleted_file": False,
                        "renamed_file": False,
                        "diff": "@@ -1,3 +1,5 @@\n+line1\n+line2\n-old",
                    }
                ]
            },
            status=200,
        )
        files = gitlab_adapter.list_pull_request_files(1)
        assert len(files) == 1
        assert isinstance(files[0], PullRequestFile)
        assert files[0].filename == "src/main.py"
        assert files[0].status == "modified"
        assert files[0].additions == 2
        assert files[0].deletions == 1


class TestListPullRequestCommits:
    def test_list_commits(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/merge_requests/1/commits",
            json=[
                {
                    "id": "abc123",
                    "message": "fix bug",
                    "author_name": "dev1",
                    "created_at": "2025-01-01T00:00:00Z",
                }
            ],
            status=200,
        )
        commits = gitlab_adapter.list_pull_request_commits(1)
        assert len(commits) == 1
        assert isinstance(commits[0], PullRequestCommit)
        assert commits[0].sha == "abc123"
        assert commits[0].message == "fix bug"
        assert commits[0].author == "dev1"


class TestListRequestedReviewersGitLab:
    def test_list_reviewers(self, mock_responses, gitlab_adapter):
        mr = _mr_data()
        mr["reviewers"] = [{"username": "reviewer1"}, {"username": "reviewer2"}]
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/merge_requests/1",
            json=mr,
            status=200,
        )
        reviewers = gitlab_adapter.list_requested_reviewers(1)
        assert reviewers == ["reviewer1", "reviewer2"]


class TestUpdatePullRequestBranchGitLab:
    def test_rebase(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.PUT,
            f"{PROJECT}/merge_requests/1/rebase",
            json={"rebase_in_progress": True},
            status=202,
        )
        gitlab_adapter.update_pull_request_branch(1)
        assert mock_responses.calls[0].request.method == "PUT"


class TestEnableAutoMergeGitLab:
    def test_enable(self, mock_responses, gitlab_adapter):
        mock_responses.add(
            responses.PUT,
            f"{PROJECT}/merge_requests/1/merge",
            json=_mr_data(),
            status=200,
        )
        gitlab_adapter.enable_auto_merge(1)
        body = json.loads(mock_responses.calls[0].request.body)
        assert body["merge_when_pipeline_succeeds"] is True


class TestMarkPullRequestReadyGitLab:
    def test_mark_ready(self, mock_responses, gitlab_adapter):
        mr = _mr_data()
        mr["title"] = "Draft: My MR"
        mock_responses.add(
            responses.GET,
            f"{PROJECT}/merge_requests/1",
            json=mr,
            status=200,
        )
        mock_responses.add(
            responses.PUT,
            f"{PROJECT}/merge_requests/1",
            json=_mr_data(),
            status=200,
        )
        gitlab_adapter.mark_pull_request_ready(1)
        body = json.loads(mock_responses.calls[1].request.body)
        assert body["title"] == "My MR"


# --- Phase 3: リポジトリ操作・リリースアセット ---


class TestUpdateRepositoryGitLab:
    @responses.activate
    def test_update_description(self, gitlab_adapter):
        responses.add(responses.PUT, f"{PROJECT}", json=_repo_data(), status=200)
        repo = gitlab_adapter.update_repository(description="new desc")
        assert isinstance(repo, Repository)
        assert json.loads(responses.calls[0].request.body)["description"] == "new desc"

    @responses.activate
    def test_update_private(self, gitlab_adapter):
        responses.add(responses.PUT, f"{PROJECT}", json=_repo_data(), status=200)
        gitlab_adapter.update_repository(private=True)
        body = json.loads(responses.calls[0].request.body)
        assert body["visibility"] == "private"

    @responses.activate
    def test_update_public(self, gitlab_adapter):
        responses.add(responses.PUT, f"{PROJECT}", json=_repo_data(), status=200)
        gitlab_adapter.update_repository(private=False)
        body = json.loads(responses.calls[0].request.body)
        assert body["visibility"] == "public"


class TestArchiveRepositoryGitLab:
    @responses.activate
    def test_archive(self, gitlab_adapter):
        responses.add(responses.POST, f"{PROJECT}/archive", json=_repo_data(), status=200)
        gitlab_adapter.archive_repository()
        assert responses.calls[0].request.method == "POST"


class TestGetLanguagesGitLab:
    @responses.activate
    def test_get_languages(self, gitlab_adapter):
        responses.add(
            responses.GET, f"{PROJECT}/languages", json={"Python": 78.5, "Go": 21.5}, status=200
        )
        result = gitlab_adapter.get_languages()
        assert result["Python"] == 78.5


class TestTopicsGitLab:
    @responses.activate
    def test_list_topics(self, gitlab_adapter):
        responses.add(
            responses.GET,
            f"{PROJECT}",
            json={**_repo_data(), "topics": ["python", "cli"]},
            status=200,
        )
        result = gitlab_adapter.list_topics()
        assert result == ["python", "cli"]

    @responses.activate
    def test_set_topics(self, gitlab_adapter):
        responses.add(
            responses.PUT, f"{PROJECT}", json={**_repo_data(), "topics": ["a", "b"]}, status=200
        )
        result = gitlab_adapter.set_topics(["a", "b"])
        assert result == ["a", "b"]

    @responses.activate
    def test_add_topic(self, gitlab_adapter):
        responses.add(
            responses.GET, f"{PROJECT}", json={**_repo_data(), "topics": ["a"]}, status=200
        )
        responses.add(
            responses.PUT, f"{PROJECT}", json={**_repo_data(), "topics": ["a", "b"]}, status=200
        )
        result = gitlab_adapter.add_topic("b")
        assert "b" in result

    @responses.activate
    def test_remove_topic(self, gitlab_adapter):
        responses.add(
            responses.GET, f"{PROJECT}", json={**_repo_data(), "topics": ["a", "b"]}, status=200
        )
        responses.add(
            responses.PUT, f"{PROJECT}", json={**_repo_data(), "topics": ["a"]}, status=200
        )
        result = gitlab_adapter.remove_topic("b")
        assert "b" not in result


class TestCompareGitLab:
    @responses.activate
    def test_compare(self, gitlab_adapter):
        from gfo.adapter.base import CompareResult

        responses.add(
            responses.GET,
            f"{PROJECT}/repository/compare",
            json={
                "commits": [{"id": "abc"}, {"id": "def"}, {"id": "ghi"}],
                "diffs": [
                    {
                        "new_path": "a.py",
                        "old_path": "a.py",
                        "new_file": False,
                        "deleted_file": False,
                        "renamed_file": False,
                    }
                ],
            },
            status=200,
        )
        result = gitlab_adapter.compare("main", "feature")
        assert isinstance(result, CompareResult)
        assert result.total_commits == 3
        assert len(result.files) == 1
        assert result.files[0].status == "modified"


class TestGetLatestReleaseGitLab:
    @responses.activate
    def test_get_latest(self, gitlab_adapter):
        responses.add(responses.GET, f"{PROJECT}/releases", json=[_release_data()], status=200)
        release = gitlab_adapter.get_latest_release()
        assert release.tag == "v1.0.0"


class TestReleaseAssetsGitLab:
    @responses.activate
    def test_list_release_assets(self, gitlab_adapter):
        responses.add(
            responses.GET,
            f"{PROJECT}/releases/v1.0.0/assets/links",
            json=[
                {
                    "id": 1,
                    "name": "app.zip",
                    "url": "https://example.com/app.zip",
                    "direct_asset_url": "https://example.com/app.zip",
                },
            ],
            status=200,
        )
        assets = gitlab_adapter.list_release_assets(tag="v1.0.0")
        assert len(assets) == 1
        assert assets[0].name == "app.zip"

    @responses.activate
    def test_delete_release_asset(self, gitlab_adapter):
        responses.add(responses.DELETE, f"{PROJECT}/releases/v1.0.0/assets/links/1", status=204)
        gitlab_adapter.delete_release_asset(tag="v1.0.0", asset_id=1)


class TestListIssueTemplatesGitLab:
    @responses.activate
    def test_list_templates(self, gitlab_adapter):
        responses.add(
            responses.GET,
            f"{PROJECT}/templates/issues",
            json=[
                {"name": "Bug Report", "content": "## Bug\n...", "description": "Report a bug"},
                {
                    "name": "Feature",
                    "content": "## Feature\n...",
                    "description": "Request a feature",
                },
            ],
            status=200,
        )
        templates = gitlab_adapter.list_issue_templates()
        assert len(templates) == 2
        assert templates[0].name == "Bug Report"
        assert templates[0].body == "## Bug\n..."
        assert templates[0].about == "Report a bug"
        assert templates[0].labels == ()

    @responses.activate
    def test_empty_list(self, gitlab_adapter):
        responses.add(
            responses.GET,
            f"{PROJECT}/templates/issues",
            json=[],
            status=200,
        )
        templates = gitlab_adapter.list_issue_templates()
        assert templates == []

    @responses.activate
    def test_not_found(self, gitlab_adapter):
        responses.add(
            responses.GET,
            f"{PROJECT}/templates/issues",
            json={"message": "Not Found"},
            status=404,
        )
        templates = gitlab_adapter.list_issue_templates()
        assert templates == []


class TestMigrateRepository:
    @responses.activate
    def test_migrate(self, gitlab_adapter):
        responses.add(
            responses.POST,
            f"{BASE}/projects",
            json=_repo_data(name="migrated", path_with_namespace="test-owner/migrated"),
            status=201,
        )
        repo = gitlab_adapter.migrate_repository("https://github.com/old/repo.git", "migrated")
        assert repo.name == "migrated"

    @responses.activate
    def test_migrate_private_with_mirror(self, gitlab_adapter):
        responses.add(
            responses.POST,
            f"{BASE}/projects",
            json=_repo_data(name="migrated", path_with_namespace="test-owner/migrated"),
            status=201,
        )
        repo = gitlab_adapter.migrate_repository(
            "https://github.com/old/repo.git",
            "migrated",
            private=True,
            mirror=True,
            description="migrated repo",
        )
        assert repo.name == "migrated"
        import json as json_mod

        body = json_mod.loads(responses.calls[0].request.body)
        assert body["visibility"] == "private"
        assert body["mirror"] is True
        assert body["description"] == "migrated repo"

    @responses.activate
    def test_migrate_with_auth_token(self, gitlab_adapter):
        responses.add(
            responses.POST,
            f"{BASE}/projects",
            json=_repo_data(name="migrated", path_with_namespace="test-owner/migrated"),
            status=201,
        )
        repo = gitlab_adapter.migrate_repository(
            "https://github.com/old/repo.git",
            "migrated",
            auth_token="tok",
        )
        assert repo.name == "migrated"
        import json as json_mod

        body = json_mod.loads(responses.calls[0].request.body)
        assert "oauth2:tok@" in body["import_url"]


# ── C-01: download_release_asset パストラバーサル防止 ──


class TestDownloadReleaseAssetPathTraversal:
    @responses.activate
    def test_traversal_name_sanitized(self, gitlab_adapter, tmp_path):
        """アセット名に ../ を含む場合に basename でサニタイズされることを検証する。"""
        responses.add(
            responses.GET,
            f"{PROJECT}/releases/v1.0.0/assets/links/1",
            json={
                "name": "../malicious.bin",
                "id": 1,
                "direct_asset_url": "https://example.com/file",
            },
        )
        responses.add(
            responses.GET,
            "https://example.com/file",
            body=b"content",
        )
        result = gitlab_adapter.download_release_asset(
            tag="v1.0.0", asset_id=1, output_dir=str(tmp_path)
        )
        import os

        assert os.path.basename(result) == "malicious.bin"
        assert os.path.dirname(os.path.realpath(result)) == os.path.realpath(str(tmp_path))


# ── C-03: migrate_repository トークンマスク ──


class TestMigrateRepositoryTokenMask:
    @responses.activate
    def test_token_masked_on_error(self, gitlab_adapter):
        """migrate_repository のエラーメッセージからトークンがマスクされることを検証する。"""
        from gfo.exceptions import GfoError

        responses.add(
            responses.POST,
            f"{BASE}/projects",
            json={"message": "import failed"},
            status=500,
        )
        with pytest.raises(GfoError) as exc_info:
            gitlab_adapter.migrate_repository(
                "https://github.com/old/repo.git",
                "migrated",
                auth_token="super-secret-token",
            )
        assert "super-secret-token" not in str(exc_info.value)
