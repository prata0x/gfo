"""GiteaAdapter のテスト。"""

from __future__ import annotations

import json

import pytest
import responses

from gfo.adapter.base import (
    Branch,
    Comment,
    CommitStatus,
    DeployKey,
    Issue,
    Milestone,
    Pipeline,
    PullRequest,
    Release,
    Repository,
    Review,
    Tag,
    Webhook,
    WikiPage,
)
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


def _comment_data(*, comment_id=10):
    return {
        "id": comment_id,
        "body": "A comment",
        "user": {"login": "commenter"},
        "html_url": f"https://gitea.example.com/test-owner/test-repo/issues/1#issuecomment-{comment_id}",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-02T00:00:00Z",
    }


def _review_data(*, review_id=20, state="APPROVED"):
    return {
        "id": review_id,
        "state": state,
        "body": "LGTM",
        "user": {"login": "reviewer"},
        "html_url": f"https://gitea.example.com/test-owner/test-repo/pulls/1#pullrequestreview-{review_id}",
        "submitted_at": "2025-01-01T00:00:00Z",
    }


def _branch_data(*, name="feature", sha="abc123"):
    return {
        "name": name,
        "commit": {
            "sha": sha,
            "url": f"https://gitea.example.com/test-owner/test-repo/commit/{sha}",
        },
        "protected": False,
    }


def _tag_data(*, name="v1.0.0", sha="def456"):
    return {
        "name": name,
        "commit": {"sha": sha},
        "zipball_url": "",
        "tarball_url": "",
    }


def _commit_status_data(*, state="success", context="ci/test"):
    return {
        "state": state,
        "context": context,
        "description": "Tests passed",
        "target_url": "https://ci.example.com/build/1",
        "created_at": "2025-01-01T00:00:00Z",
    }


def _webhook_data(*, hook_id=100):
    return {
        "id": hook_id,
        "config": {"url": "https://example.com/hook", "content_type": "json"},
        "events": ["push", "pull_request"],
        "active": True,
    }


def _deploy_key_data(*, key_id=200):
    return {
        "id": key_id,
        "title": "Deploy Key",
        "key": "ssh-rsa AAAA...",
        "read_only": True,
    }


def _pipeline_data(*, run_id=300, status="success"):
    return {
        "id": run_id,
        "status": status,
        "head_branch": "main",
        "html_url": f"https://gitea.example.com/test-owner/test-repo/actions/runs/{run_id}",
        "created": "2025-01-01T00:00:00Z",
    }


def _wiki_page_data(*, title="Home"):
    return {
        "title": title,
        "content": "# Home page",
        "html_url": f"https://gitea.example.com/test-owner/test-repo/wiki/{title}",
        "last_commit": {"created": "2025-01-01T00:00:00Z"},
    }


class TestToComment:
    def test_basic(self):
        comment = GiteaAdapter._to_comment(_comment_data())
        assert comment.id == 10
        assert comment.body == "A comment"
        assert comment.author == "commenter"

    def test_null_user(self):
        data = _comment_data()
        data["user"] = None
        from gfo.exceptions import GfoError

        with pytest.raises(GfoError):
            GiteaAdapter._to_comment(data)


class TestToReview:
    def test_basic(self):
        review = GiteaAdapter._to_review(_review_data())
        assert review.id == 20
        assert review.body == "LGTM"
        assert review.author == "reviewer"

    def test_state_approved(self):
        review = GiteaAdapter._to_review(_review_data(state="APPROVED"))
        assert review.state == "approved"

    def test_state_changes_requested(self):
        review = GiteaAdapter._to_review(_review_data(state="CHANGES_REQUESTED"))
        assert review.state == "changes_requested"

    def test_state_commented(self):
        review = GiteaAdapter._to_review(_review_data(state="COMMENTED"))
        assert review.state == "commented"


class TestToBranch:
    def test_basic(self):
        branch = GiteaAdapter._to_branch(_branch_data())
        assert branch.name == "feature"
        assert branch.sha == "abc123"
        assert branch.protected is False

    def test_commit_id_fallback(self):
        data = _branch_data()
        del data["commit"]["sha"]
        data["commit"]["id"] = "fallback_sha"
        # sha がない場合は commit.id にフォールバック（Gitea/Gogs 系との互換）
        branch = GiteaAdapter._to_branch(data)
        assert branch.sha == "fallback_sha"


class TestToTag:
    def test_basic(self):
        tag = GiteaAdapter._to_tag(_tag_data())
        assert tag.name == "v1.0.0"
        assert tag.sha == "def456"

    def test_with_message(self):
        data = _tag_data()
        data["message"] = "release v1.0.0"
        tag = GiteaAdapter._to_tag(data)
        # _to_tag は message フィールドを使わず常に "" を設定する
        assert tag.message == ""


class TestToCommitStatus:
    def test_basic(self):
        cs = GiteaAdapter._to_commit_status(_commit_status_data())
        assert cs.state == "success"
        assert cs.context == "ci/test"
        assert cs.description == "Tests passed"
        assert cs.target_url == "https://ci.example.com/build/1"
        assert cs.created_at == "2025-01-01T00:00:00Z"


class TestToWebhook:
    def test_basic(self):
        hook = GiteaAdapter._to_webhook(_webhook_data())
        assert hook.id == 100
        assert hook.url == "https://example.com/hook"
        assert hook.events == ("push", "pull_request")
        assert hook.active is True


class TestToDeployKey:
    def test_basic(self):
        dk = GiteaAdapter._to_deploy_key(_deploy_key_data())
        assert dk.id == 200
        assert dk.title == "Deploy Key"
        assert dk.key == "ssh-rsa AAAA..."
        assert dk.read_only is True


class TestToPipelineData:
    def test_success(self):
        pl = GiteaAdapter._to_pipeline_data(_pipeline_data(status="success"))
        assert pl.status == "success"
        assert pl.id == 300
        assert pl.ref == "main"

    def test_failure(self):
        pl = GiteaAdapter._to_pipeline_data(_pipeline_data(status="failure"))
        assert pl.status == "failure"

    def test_running(self):
        pl = GiteaAdapter._to_pipeline_data(_pipeline_data(status="running"))
        assert pl.status == "running"

    def test_waiting_to_pending(self):
        pl = GiteaAdapter._to_pipeline_data(_pipeline_data(status="waiting"))
        assert pl.status == "pending"

    def test_queued_to_pending(self):
        pl = GiteaAdapter._to_pipeline_data(_pipeline_data(status="queued"))
        assert pl.status == "pending"

    def test_cancelled(self):
        pl = GiteaAdapter._to_pipeline_data(_pipeline_data(status="cancelled"))
        assert pl.status == "cancelled"


class TestToWikiPageData:
    def test_basic(self):
        page = GiteaAdapter._to_wiki_page_data(_wiki_page_data())
        assert page.id == 0
        assert page.title == "Home"
        assert page.content == "# Home page"
        assert "wiki/Home" in page.url
        assert page.updated_at == "2025-01-01T00:00:00Z"

    def test_no_last_commit(self):
        data = _wiki_page_data()
        data.pop("last_commit")
        page = GiteaAdapter._to_wiki_page_data(data)
        assert page.updated_at is None


# --- PR 系 ---


class TestListPullRequests:
    def test_open(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls",
            json=[_pr_data()],
            status=200,
        )
        prs = gitea_adapter.list_pull_requests()
        assert len(prs) == 1
        assert prs[0].state == "open"

    def test_merged_filter(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls",
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
            responses.GET,
            f"{REPOS}/pulls",
            json=[_pr_data(number=1)],
            status=200,
            headers={"Link": f'<{REPOS}/pulls?page=2>; rel="next"'},
        )
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls",
            json=[_pr_data(number=2)],
            status=200,
        )
        prs = gitea_adapter.list_pull_requests(limit=10)
        assert len(prs) == 2
        req = mock_responses.calls[0].request
        assert "limit=" in req.url
        assert "per_page=" not in req.url


class TestCreatePullRequest:
    def test_create(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/pulls",
            json=_pr_data(),
            status=201,
        )
        pr = gitea_adapter.create_pull_request(
            title="PR #1",
            body="desc",
            base="main",
            head="feature",
        )
        assert isinstance(pr, PullRequest)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["draft"] is False

    def test_create_draft(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/pulls",
            json=_pr_data(draft=True),
            status=201,
        )
        _ = gitea_adapter.create_pull_request(
            title="Draft",
            body="",
            base="main",
            head="feature",
            draft=True,
        )
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["draft"] is True


class TestGetPullRequest:
    def test_get(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls/42",
            json=_pr_data(number=42),
            status=200,
        )
        pr = gitea_adapter.get_pull_request(42)
        assert pr.number == 42


class TestMergePullRequest:
    def test_merge(self, mock_responses, gitea_adapter):
        """merge_pull_request は POST .../merge エンドポイントを使用する（R35修正確認）。"""
        mock_responses.add(
            responses.POST,
            f"{REPOS}/pulls/1/merge",
            json={"merged": True},
            status=200,
        )
        gitea_adapter.merge_pull_request(1)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["Do"] == "merge"
        assert mock_responses.calls[0].request.method == "POST"

    def test_merge_squash(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/pulls/1/merge",
            json={"merged": True},
            status=200,
        )
        gitea_adapter.merge_pull_request(1, method="squash")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["Do"] == "squash"


class TestClosePullRequest:
    def test_close(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/pulls/1",
            json=_pr_data(state="closed"),
            status=200,
        )
        gitea_adapter.close_pull_request(1)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["state"] == "closed"


class TestCheckoutRefspec:
    def test_refspec(self, gitea_adapter):
        assert gitea_adapter.get_pr_checkout_refspec(42) == "refs/pull/42/head"


# --- Issue 系 ---


class TestListIssues:
    def test_excludes_prs(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues",
            json=[_issue_data(number=1), _issue_data(number=2, has_pr=True)],
            status=200,
        )
        issues = gitea_adapter.list_issues()
        assert len(issues) == 1
        assert issues[0].number == 1

    def test_with_filters(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues",
            json=[_issue_data()],
            status=200,
        )
        issues = gitea_adapter.list_issues(assignee="dev1", label="bug")
        assert len(issues) == 1
        req = mock_responses.calls[0].request
        assert "assignee=dev1" in req.url
        assert "labels=bug" in req.url

    def test_pagination_uses_limit_param(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues",
            json=[_issue_data()],
            status=200,
        )
        gitea_adapter.list_issues(limit=20)
        req = mock_responses.calls[0].request
        assert "limit=" in req.url
        assert "per_page=" not in req.url


class TestCreateIssue:
    def test_create(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/issues",
            json=_issue_data(),
            status=201,
        )
        issue = gitea_adapter.create_issue(title="Issue #1", body="body")
        assert isinstance(issue, Issue)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert "assignees" not in req_body
        assert "labels" not in req_body

    def test_create_with_assignee_and_label(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/issues",
            json=_issue_data(),
            status=201,
        )
        gitea_adapter.create_issue(
            title="Issue",
            assignee="dev1",
            label="bug",
        )
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["assignees"] == ["dev1"]
        assert req_body["labels"] == ["bug"]


class TestGetIssue:
    def test_get(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues/5",
            json=_issue_data(number=5),
            status=200,
        )
        issue = gitea_adapter.get_issue(5)
        assert issue.number == 5


class TestCloseIssue:
    def test_close(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/issues/3",
            json=_issue_data(number=3, state="closed"),
            status=200,
        )
        gitea_adapter.close_issue(3)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["state"] == "closed"


# --- Repository 系 ---


class TestListRepositories:
    def test_with_owner(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/users/someone/repos",
            json=[_repo_data()],
            status=200,
        )
        repos = gitea_adapter.list_repositories(owner="someone")
        assert len(repos) == 1

    def test_no_owner(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/user/repos",
            json=[_repo_data()],
            status=200,
        )
        repos = gitea_adapter.list_repositories()
        assert len(repos) == 1

    def test_owner_with_special_chars_is_encoded(self, mock_responses, gitea_adapter):
        """list_repositories(owner="...") で特殊文字が URL エンコードされる（R41-01）。"""
        mock_responses.add(
            responses.GET,
            f"{BASE}/users/org%2Fsub/repos",
            json=[_repo_data()],
            status=200,
        )
        gitea_adapter.list_repositories(owner="org/sub")
        assert "%2F" in mock_responses.calls[0].request.url

    def test_pagination_uses_limit_param(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/user/repos",
            json=[_repo_data()],
            status=200,
        )
        gitea_adapter.list_repositories(limit=20)
        req = mock_responses.calls[0].request
        assert "limit=" in req.url
        assert "per_page=" not in req.url


class TestCreateRepository:
    def test_create(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{BASE}/user/repos",
            json=_repo_data(),
            status=201,
        )
        repo = gitea_adapter.create_repository(name="test-repo")
        assert isinstance(repo, Repository)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["name"] == "test-repo"


class TestGetRepository:
    def test_get(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/repos/other/other-repo",
            json=_repo_data(name="other-repo", full_name="other/other-repo"),
            status=200,
        )
        repo = gitea_adapter.get_repository(owner="other", name="other-repo")
        assert repo.name == "other-repo"

    def test_get_defaults(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}",
            json=_repo_data(),
            status=200,
        )
        repo = gitea_adapter.get_repository()
        assert repo.full_name == "test-owner/test-repo"

    def test_get_owner_with_special_chars_is_encoded(self, mock_responses, gitea_adapter):
        """owner に特殊文字が含まれる場合、URL エンコードされてリクエストされる。"""
        mock_responses.add(
            responses.GET,
            f"{BASE}/repos/org%2Fsub/repo",
            json=_repo_data(name="repo", full_name="org/sub/repo"),
            status=200,
        )
        gitea_adapter.get_repository(owner="org/sub", name="repo")
        assert "%2F" in mock_responses.calls[0].request.url


# --- Release 系 ---


class TestListReleases:
    def test_list(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/releases",
            json=[_release_data()],
            status=200,
        )
        releases = gitea_adapter.list_releases()
        assert len(releases) == 1
        assert releases[0].tag == "v1.0.0"

    def test_pagination_uses_limit_param(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/releases",
            json=[_release_data()],
            status=200,
        )
        gitea_adapter.list_releases(limit=20)
        req = mock_responses.calls[0].request
        assert "limit=" in req.url
        assert "per_page=" not in req.url


class TestCreateRelease:
    def test_create(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/releases",
            json=_release_data(),
            status=201,
        )
        rel = gitea_adapter.create_release(tag="v1.0.0", title="Release v1.0.0")
        assert isinstance(rel, Release)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["tag_name"] == "v1.0.0"


# --- Label 系 ---


class TestListLabels:
    def test_list(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/labels",
            json=[_label_data(), _label_data(name="enhancement")],
            status=200,
        )
        labels = gitea_adapter.list_labels()
        assert len(labels) == 2

    def test_list_fetches_all_pages(self, mock_responses, gitea_adapter):
        """list_labels は limit=0 で全ページを取得する（30 件上限なし）。"""
        page2_url = f"{REPOS}/labels?limit=50&page=2"
        mock_responses.add(
            responses.GET,
            f"{REPOS}/labels",
            json=[_label_data(name=f"label-{i}") for i in range(50)],
            headers={"Link": f'<{page2_url}>; rel="next"'},
            status=200,
        )
        mock_responses.add(
            responses.GET,
            page2_url,
            json=[_label_data(name="last-label")],
            status=200,
        )
        labels = gitea_adapter.list_labels()
        assert len(labels) == 51


class TestCreateLabel:
    def test_create(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/labels",
            json=_label_data(),
            status=201,
        )
        label = gitea_adapter.create_label(name="bug", color="d73a4a")
        assert label.name == "bug"

    def test_create_optional_fields(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/labels",
            json={"name": "minimal", "color": None, "description": None},
            status=201,
        )
        gitea_adapter.create_label(name="minimal")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert "color" not in req_body
        assert "description" not in req_body

    def test_create_with_description(self, mock_responses, gitea_adapter):
        """description を渡すとペイロードに含まれる。"""
        mock_responses.add(
            responses.POST,
            f"{REPOS}/labels",
            json=_label_data(),
            status=201,
        )
        gitea_adapter.create_label(name="bug", color="d73a4a", description="Bug report")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["description"] == "Bug report"


# --- Milestone 系 ---


class TestListMilestones:
    def test_list(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/milestones",
            json=[_milestone_data()],
            status=200,
        )
        milestones = gitea_adapter.list_milestones()
        assert len(milestones) == 1
        assert milestones[0].title == "v1.0"

    def test_list_fetches_all_pages(self, mock_responses, gitea_adapter):
        """list_milestones は limit=0 で全ページを取得する（30 件上限なし）。"""
        page2_url = f"{REPOS}/milestones?limit=50&page=2"
        mock_responses.add(
            responses.GET,
            f"{REPOS}/milestones",
            json=[_milestone_data() for _ in range(50)],
            headers={"Link": f'<{page2_url}>; rel="next"'},
            status=200,
        )
        mock_responses.add(
            responses.GET,
            page2_url,
            json=[_milestone_data()],
            status=200,
        )
        milestones = gitea_adapter.list_milestones()
        assert len(milestones) == 51


class TestCreateMilestone:
    def test_create(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/milestones",
            json=_milestone_data(),
            status=201,
        )
        ms = gitea_adapter.create_milestone(title="v1.0", due_date="2025-06-01T00:00:00Z")
        assert isinstance(ms, Milestone)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["due_on"] == "2025-06-01T00:00:00Z"

    def test_create_optional_fields(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/milestones",
            json=_milestone_data(),
            status=201,
        )
        gitea_adapter.create_milestone(title="v1.0")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert "description" not in req_body
        assert "due_on" not in req_body

    def test_create_with_description(self, mock_responses, gitea_adapter):
        """description を渡すとペイロードに含まれる。"""
        mock_responses.add(
            responses.POST,
            f"{REPOS}/milestones",
            json=_milestone_data(),
            status=201,
        )
        gitea_adapter.create_milestone(title="v1.0", description="First release")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["description"] == "First release"


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


# --- Delete 系 ---


class TestDeleteRelease:
    def test_delete(self, mock_responses, gitea_adapter):
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
        gitea_adapter.delete_release(tag="v1.0.0")

    def test_tag_url_encoded(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/releases/tags/v1.0.0%2Brc1",
            json={"id": 99, "tag_name": "v1.0.0+rc1"},
            status=200,
        )
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/releases/99",
            status=204,
        )
        gitea_adapter.delete_release(tag="v1.0.0+rc1")
        assert "%2B" in mock_responses.calls[0].request.url


class TestDeleteLabel:
    def test_delete(self, mock_responses, gitea_adapter):
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
        gitea_adapter.delete_label(name="bug")

    def test_not_found_raises_error(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/labels",
            json=[{"id": 10, "name": "other", "color": "d73a4a", "description": ""}],
            status=200,
        )
        with pytest.raises(NotFoundError):
            gitea_adapter.delete_label(name="bug")


class TestDeleteMilestone:
    def test_delete(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/milestones/3",
            status=204,
        )
        gitea_adapter.delete_milestone(number=3)


class TestDeleteIssue:
    def test_delete(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/issues/4",
            status=204,
        )
        gitea_adapter.delete_issue(4)
        assert mock_responses.calls[0].request.method == "DELETE"
        assert mock_responses.calls[0].request.url.endswith("/issues/4")


class TestDeleteRepository:
    def test_delete(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.DELETE,
            REPOS,
            status=204,
        )
        gitea_adapter.delete_repository()
        assert mock_responses.calls[0].request.method == "DELETE"


# --- Comment 系 ---


class TestListComments:
    def test_list(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues/1/comments",
            json=[
                {
                    "id": 10,
                    "body": "A comment",
                    "user": {"login": "commenter"},
                    "html_url": "",
                    "created_at": "2025-01-01T00:00:00Z",
                    "updated_at": "2025-01-02T00:00:00Z",
                }
            ],
            status=200,
        )
        comments = gitea_adapter.list_comments("issue", 1)
        assert len(comments) == 1
        assert isinstance(comments[0], Comment)


class TestCreateComment:
    def test_create(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/issues/1/comments",
            json={
                "id": 10,
                "body": "Hello",
                "user": {"login": "commenter"},
                "html_url": "",
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-02T00:00:00Z",
            },
            status=201,
        )
        comment = gitea_adapter.create_comment("issue", 1, body="Hello")
        assert isinstance(comment, Comment)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["body"] == "Hello"


class TestUpdateComment:
    def test_update(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/issues/comments/10",
            json={
                "id": 10,
                "body": "Updated",
                "user": {"login": "commenter"},
                "html_url": "",
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-02T00:00:00Z",
            },
            status=200,
        )
        comment = gitea_adapter.update_comment("issue", 10, body="Updated")
        assert isinstance(comment, Comment)


class TestDeleteComment:
    def test_delete(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/issues/comments/10",
            status=204,
        )
        gitea_adapter.delete_comment("issue", 10)
        assert mock_responses.calls[0].request.method == "DELETE"


# --- PR Update / Issue Update ---


class TestUpdatePullRequest:
    def test_update_title(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/pulls/1",
            json=_pr_data(),
            status=200,
        )
        pr = gitea_adapter.update_pull_request(1, title="New Title")
        assert isinstance(pr, PullRequest)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["title"] == "New Title"

    def test_only_changed_fields_sent(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/pulls/1",
            json=_pr_data(),
            status=200,
        )
        gitea_adapter.update_pull_request(1, title="Only Title")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert "body" not in req_body


class TestUpdateIssue:
    def test_update_title(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/issues/1",
            json=_issue_data(),
            status=200,
        )
        issue = gitea_adapter.update_issue(1, title="New Title")
        assert isinstance(issue, Issue)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["title"] == "New Title"


# --- Review 系 ---


class TestListReviews:
    def test_list(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls/1/reviews",
            json=[
                {
                    "id": 20,
                    "state": "APPROVED",
                    "body": "LGTM",
                    "user": {"login": "reviewer"},
                    "html_url": "",
                    "submitted_at": "2025-01-01T00:00:00Z",
                }
            ],
            status=200,
        )
        reviews = gitea_adapter.list_reviews(1)
        assert len(reviews) == 1
        assert isinstance(reviews[0], Review)


class TestCreateReview:
    def test_approve(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/pulls/1/reviews",
            json={
                "id": 20,
                "state": "APPROVED",
                "body": "",
                "user": {"login": "reviewer"},
                "html_url": "",
                "submitted_at": "2025-01-01T00:00:00Z",
            },
            status=200,
        )
        review = gitea_adapter.create_review(1, state="approve")
        assert isinstance(review, Review)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["event"] == "APPROVE"


# --- Branch 系 ---


class TestListBranches:
    def test_list(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/branches",
            json=[{"name": "feature", "commit": {"id": "abc123", "url": ""}, "protected": False}],
            status=200,
        )
        branches = gitea_adapter.list_branches()
        assert len(branches) == 1
        assert isinstance(branches[0], Branch)
        assert branches[0].name == "feature"

    def test_pagination_uses_limit_param(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/branches",
            json=[{"name": "main", "commit": {"id": "abc", "url": ""}, "protected": False}],
            status=200,
        )
        gitea_adapter.list_branches(limit=20)
        req = mock_responses.calls[0].request
        assert "limit=" in req.url


class TestCreateBranch:
    def test_create(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/branches",
            json={"name": "new-branch", "commit": {"id": "abc123", "url": ""}, "protected": False},
            status=201,
        )
        branch = gitea_adapter.create_branch(name="new-branch", ref="main")
        assert isinstance(branch, Branch)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["new_branch_name"] == "new-branch"
        assert req_body["old_branch_name"] == "main"


class TestDeleteBranch:
    def test_delete(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/branches/feature",
            status=204,
        )
        gitea_adapter.delete_branch(name="feature")
        assert mock_responses.calls[0].request.method == "DELETE"


# --- Tag 系 ---


class TestListTags:
    def test_list(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/tags",
            json=[
                {
                    "name": "v1.0.0",
                    "commit": {"sha": "def456"},
                    "zipball_url": "",
                    "tarball_url": "",
                }
            ],
            status=200,
        )
        tags = gitea_adapter.list_tags()
        assert len(tags) == 1
        assert isinstance(tags[0], Tag)
        assert tags[0].name == "v1.0.0"


class TestCreateTag:
    def test_create(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/tags",
            json={"name": "v2.0.0", "commit": {"sha": "newsha"}, "message": "Release"},
            status=201,
        )
        tag = gitea_adapter.create_tag(name="v2.0.0", ref="main", message="Release")
        assert isinstance(tag, Tag)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["tag_name"] == "v2.0.0"
        assert req_body["target"] == "main"
        assert req_body["message"] == "Release"


class TestDeleteTag:
    def test_delete(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/tags/v1.0.0",
            status=204,
        )
        gitea_adapter.delete_tag(name="v1.0.0")
        assert mock_responses.calls[0].request.method == "DELETE"


# --- CommitStatus 系 ---


class TestListCommitStatuses:
    def test_list(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/statuses/abc123",
            json=[
                {
                    "state": "success",
                    "context": "ci/test",
                    "description": "Passed",
                    "target_url": "",
                    "created_at": "2025-01-01T00:00:00Z",
                }
            ],
            status=200,
        )
        statuses = gitea_adapter.list_commit_statuses("abc123")
        assert len(statuses) == 1
        assert isinstance(statuses[0], CommitStatus)


class TestCreateCommitStatus:
    def test_create(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/statuses/abc123",
            json={
                "state": "success",
                "context": "ci/test",
                "description": "Passed",
                "target_url": "",
                "created_at": "2025-01-01T00:00:00Z",
            },
            status=201,
        )
        status = gitea_adapter.create_commit_status("abc123", state="success", context="ci/test")
        assert isinstance(status, CommitStatus)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["state"] == "success"


# --- File 系 ---


class TestGetFileContent:
    def test_get(self, mock_responses, gitea_adapter):
        import base64 as _b64

        content_b64 = _b64.b64encode(b"file content").decode()
        mock_responses.add(
            responses.GET,
            f"{REPOS}/contents/README.md",
            json={"content": content_b64, "sha": "sha1"},
            status=200,
        )
        content, sha = gitea_adapter.get_file_content("README.md")
        assert content == "file content"
        assert sha == "sha1"


class TestCreateOrUpdateFile:
    def test_create_new(self, mock_responses, gitea_adapter):
        import base64 as _b64

        content_b64 = _b64.b64encode(b"new content").decode()
        mock_responses.add(
            responses.POST,
            f"{REPOS}/contents/new-file.md",
            json={"content": {"name": "new-file.md", "sha": "newsha"}},
            status=201,
        )
        gitea_adapter.create_or_update_file(
            "new-file.md", content="new content", message="Add file"
        )
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["content"] == content_b64

    def test_update_existing(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.PUT,
            f"{REPOS}/contents/existing.md",
            json={"content": {"name": "existing.md", "sha": "updatedsha"}},
            status=200,
        )
        gitea_adapter.create_or_update_file(
            "existing.md", content="updated", message="Update", sha="oldsha"
        )
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["sha"] == "oldsha"


class TestDeleteFile:
    def test_delete(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/contents/to-delete.md",
            json={"commit": {"sha": "commitsha"}},
            status=200,
        )
        gitea_adapter.delete_file("to-delete.md", sha="filsha", message="Delete file")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["sha"] == "filsha"


# --- Fork 系 ---


class TestForkRepository:
    def test_fork(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/forks",
            json=_repo_data(),
            status=202,
        )
        repo = gitea_adapter.fork_repository()
        assert isinstance(repo, Repository)

    def test_fork_with_org(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/forks",
            json=_repo_data(),
            status=202,
        )
        gitea_adapter.fork_repository(organization="myorg")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["organization"] == "myorg"


# --- Webhook 系 ---


class TestListWebhooks:
    def test_list(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/hooks",
            json=[
                {
                    "id": 100,
                    "config": {"url": "https://example.com/hook", "content_type": "json"},
                    "events": ["push"],
                    "active": True,
                    "type": "gitea",
                }
            ],
            status=200,
        )
        webhooks = gitea_adapter.list_webhooks()
        assert len(webhooks) == 1
        assert isinstance(webhooks[0], Webhook)


class TestCreateWebhook:
    def test_create(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/hooks",
            json={
                "id": 100,
                "config": {"url": "https://example.com/hook", "content_type": "json"},
                "events": ["push"],
                "active": True,
                "type": "gitea",
            },
            status=201,
        )
        webhook = gitea_adapter.create_webhook(url="https://example.com/hook", events=["push"])
        assert isinstance(webhook, Webhook)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["type"] == "gitea"
        assert req_body["config"]["url"] == "https://example.com/hook"


class TestDeleteWebhook:
    def test_delete(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/hooks/100",
            status=204,
        )
        gitea_adapter.delete_webhook(hook_id=100)
        assert mock_responses.calls[0].request.method == "DELETE"


# --- DeployKey 系 ---


class TestListDeployKeys:
    def test_list(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/keys",
            json=[{"id": 200, "title": "Deploy Key", "key": "ssh-rsa AAAA...", "read_only": True}],
            status=200,
        )
        keys = gitea_adapter.list_deploy_keys()
        assert len(keys) == 1
        assert isinstance(keys[0], DeployKey)


class TestCreateDeployKey:
    def test_create(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/keys",
            json={"id": 200, "title": "Deploy Key", "key": "ssh-rsa AAAA...", "read_only": True},
            status=201,
        )
        key = gitea_adapter.create_deploy_key(
            title="Deploy Key", key="ssh-rsa AAAA...", read_only=True
        )
        assert isinstance(key, DeployKey)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["read_only"] is True


class TestDeleteDeployKey:
    def test_delete(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/keys/200",
            status=204,
        )
        gitea_adapter.delete_deploy_key(key_id=200)
        assert mock_responses.calls[0].request.method == "DELETE"


# --- Collaborator 系 ---


class TestListCollaborators:
    def test_list(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/collaborators",
            json=[{"login": "collab1"}, {"login": "collab2"}],
            status=200,
        )
        collabs = gitea_adapter.list_collaborators()
        assert collabs == ["collab1", "collab2"]


class TestAddCollaborator:
    def test_add(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.PUT,
            f"{REPOS}/collaborators/newuser",
            status=204,
        )
        gitea_adapter.add_collaborator(username="newuser")
        assert mock_responses.calls[0].request.method == "PUT"


class TestRemoveCollaborator:
    def test_remove(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/collaborators/olduser",
            status=204,
        )
        gitea_adapter.remove_collaborator(username="olduser")
        assert mock_responses.calls[0].request.method == "DELETE"


# --- Pipeline 系 ---


class TestListPipelines:
    def test_list(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/actions/runs",
            json=[
                {
                    "id": 300,
                    "status": "success",
                    "head_branch": "main",
                    "html_url": "",
                    "created_at": "2025-01-01T00:00:00Z",
                }
            ],
            status=200,
        )
        pipelines = gitea_adapter.list_pipelines()
        assert len(pipelines) == 1
        assert isinstance(pipelines[0], Pipeline)

    def test_with_ref(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/actions/runs",
            json=[
                {
                    "id": 300,
                    "status": "success",
                    "head_branch": "main",
                    "html_url": "",
                    "created_at": "2025-01-01T00:00:00Z",
                }
            ],
            status=200,
        )
        gitea_adapter.list_pipelines(ref="main")
        req = mock_responses.calls[0].request
        assert "branch=main" in req.url


class TestGetPipeline:
    def test_get(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/actions/runs/300",
            json={
                "id": 300,
                "status": "success",
                "head_branch": "main",
                "html_url": "",
                "created_at": "2025-01-01T00:00:00Z",
            },
            status=200,
        )
        pipeline = gitea_adapter.get_pipeline(300)
        assert isinstance(pipeline, Pipeline)
        assert pipeline.id == 300


class TestCancelPipeline:
    def test_cancel(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/actions/runs/300/cancel",
            status=204,
        )
        gitea_adapter.cancel_pipeline(300)
        assert mock_responses.calls[0].request.method == "POST"


# --- User / Search 系 ---


class TestGetCurrentUser:
    def test_get(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/user",
            json={"login": "testuser", "id": 1},
            status=200,
        )
        user = gitea_adapter.get_current_user()
        assert user["login"] == "testuser"


class TestSearchRepositories:
    def test_search(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/repos/search",
            json=[_repo_data()],
            status=200,
        )
        repos = gitea_adapter.search_repositories("test")
        assert len(repos) == 1
        assert isinstance(repos[0], Repository)


class TestSearchIssues:
    def test_search(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues",
            json=[_issue_data()],
            status=200,
        )
        issues = gitea_adapter.search_issues("bug")
        assert len(issues) == 1
        assert isinstance(issues[0], Issue)


# --- Wiki 系 ---


class TestListWikiPages:
    def test_list(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/wiki/pages",
            json=[
                {
                    "title": "Home",
                    "content": "content",
                    "html_url": "",
                    "last_commit": {"id": "abc"},
                }
            ],
            status=200,
        )
        pages = gitea_adapter.list_wiki_pages()
        assert len(pages) == 1
        assert isinstance(pages[0], WikiPage)


class TestGetWikiPage:
    def test_get(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/wiki/page/Home",
            json={
                "title": "Home",
                "content": "# Home",
                "html_url": "",
                "last_commit": {"id": "abc"},
            },
            status=200,
        )
        page = gitea_adapter.get_wiki_page("Home")
        assert isinstance(page, WikiPage)
        assert page.title == "Home"


class TestCreateWikiPage:
    def test_create(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/wiki/new",
            json={
                "title": "New Page",
                "content": "content",
                "html_url": "",
                "last_commit": {"id": "abc"},
            },
            status=201,
        )
        page = gitea_adapter.create_wiki_page(title="New Page", content="content")
        assert isinstance(page, WikiPage)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["title"] == "New Page"


class TestUpdateWikiPage:
    def test_update(self, mock_responses, gitea_adapter):
        # 現在のページ内容を GET してから PATCH する
        mock_responses.add(
            responses.GET,
            f"{REPOS}/wiki/page/Home",
            json={"title": "Home", "content": "old", "html_url": "", "last_commit": {"id": "abc"}},
            status=200,
        )
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/wiki/page/Home",
            json={
                "title": "Home",
                "content": "new content",
                "html_url": "",
                "last_commit": {"id": "def"},
            },
            status=200,
        )
        page = gitea_adapter.update_wiki_page("Home", title="Home", content="new content")
        assert isinstance(page, WikiPage)


class TestDeleteWikiPage:
    def test_delete(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/wiki/page/Home",
            status=204,
        )
        gitea_adapter.delete_wiki_page("Home")
        assert mock_responses.calls[0].request.method == "DELETE"
