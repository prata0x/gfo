"""GitHubAdapter のテスト。"""

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
)
from gfo.adapter.github import GitHubAdapter
from gfo.adapter.registry import get_adapter_class
from gfo.exceptions import AuthenticationError, NotFoundError, ServerError

BASE = "https://api.github.com"
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
        "html_url": f"https://github.com/test-owner/test-repo/pull/{number}",
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
        "html_url": f"https://github.com/test-owner/test-repo/issues/{number}",
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
        "clone_url": f"https://github.com/{full_name}.git",
        "html_url": f"https://github.com/{full_name}",
    }


def _release_data(*, tag="v1.0.0"):
    return {
        "tag_name": tag,
        "name": f"Release {tag}",
        "body": "release notes",
        "draft": False,
        "prerelease": False,
        "html_url": f"https://github.com/test-owner/test-repo/releases/tag/{tag}",
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


def _comment_data(*, comment_id=10):
    return {
        "id": comment_id,
        "body": "A comment",
        "user": {"login": "commenter"},
        "html_url": f"https://github.com/test-owner/test-repo/issues/1#issuecomment-{comment_id}",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-02T00:00:00Z",
    }


def _review_data(*, review_id=20, state="APPROVED"):
    return {
        "id": review_id,
        "state": state,
        "body": "LGTM",
        "user": {"login": "reviewer"},
        "html_url": f"https://github.com/test-owner/test-repo/pull/1#pullrequestreview-{review_id}",
        "submitted_at": "2025-01-01T00:00:00Z",
    }


def _branch_data(*, name="feature", sha="abc123"):
    return {
        "name": name,
        "commit": {
            "sha": sha,
            "url": f"https://api.github.com/repos/test-owner/test-repo/commits/{sha}",
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


def _pipeline_data(*, run_id=300, status="completed", conclusion="success"):
    return {
        "id": run_id,
        "status": status,
        "conclusion": conclusion,
        "head_branch": "main",
        "html_url": f"https://github.com/test-owner/test-repo/actions/runs/{run_id}",
        "created_at": "2025-01-01T00:00:00Z",
    }


# --- 変換メソッドのテスト ---


class TestToPullRequest:
    def test_open(self):
        pr = GitHubAdapter._to_pull_request(_pr_data())
        assert pr.state == "open"
        assert pr.number == 1
        assert pr.author == "author1"
        assert pr.source_branch == "feature"
        assert pr.draft is False

    def test_closed(self):
        pr = GitHubAdapter._to_pull_request(_pr_data(state="closed"))
        assert pr.state == "closed"

    def test_merged(self):
        pr = GitHubAdapter._to_pull_request(
            _pr_data(state="closed", merged_at="2025-01-03T00:00:00Z")
        )
        assert pr.state == "merged"


class TestToIssue:
    def test_basic(self):
        issue = GitHubAdapter._to_issue(_issue_data())
        assert issue.number == 1
        assert issue.author == "reporter"
        assert issue.assignees == ["dev1"]
        assert issue.labels == ["bug"]


class TestToRepository:
    def test_basic(self):
        repo = GitHubAdapter._to_repository(_repo_data())
        assert repo.name == "test-repo"
        assert repo.full_name == "test-owner/test-repo"
        assert repo.private is False


class TestToRelease:
    def test_basic(self):
        rel = GitHubAdapter._to_release(_release_data())
        assert rel.tag == "v1.0.0"
        assert rel.title == "Release v1.0.0"


class TestToLabel:
    def test_basic(self):
        label = GitHubAdapter._to_label(_label_data())
        assert label.name == "bug"
        assert label.color == "d73a4a"


class TestToMilestone:
    def test_basic(self):
        ms = GitHubAdapter._to_milestone(_milestone_data())
        assert ms.number == 1
        assert ms.due_date == "2025-06-01T00:00:00Z"


class TestToComment:
    def test_basic(self):
        comment = GitHubAdapter._to_comment(_comment_data())
        assert comment.id == 10
        assert comment.body == "A comment"
        assert comment.author == "commenter"

    def test_null_user(self):
        data = _comment_data()
        data["user"] = None
        from gfo.exceptions import GfoError

        with pytest.raises(GfoError):
            GitHubAdapter._to_comment(data)


class TestToReview:
    def test_basic(self):
        review = GitHubAdapter._to_review(_review_data())
        assert review.id == 20
        assert review.body == "LGTM"
        assert review.author == "reviewer"

    def test_state_approved(self):
        review = GitHubAdapter._to_review(_review_data(state="APPROVED"))
        assert review.state == "approved"

    def test_state_changes_requested(self):
        review = GitHubAdapter._to_review(_review_data(state="CHANGES_REQUESTED"))
        assert review.state == "changes_requested"

    def test_state_commented(self):
        review = GitHubAdapter._to_review(_review_data(state="COMMENTED"))
        assert review.state == "commented"


class TestToBranch:
    def test_basic(self):
        branch = GitHubAdapter._to_branch(_branch_data())
        assert branch.name == "feature"
        assert branch.sha == "abc123"
        assert branch.protected is False

    def test_commit_id_fallback(self):
        data = _branch_data()
        del data["commit"]["sha"]
        data["commit"]["id"] = "fallback_sha"
        # sha なしの場合は空文字になる（_to_branch は sha のみ参照）
        branch = GitHubAdapter._to_branch(data)
        assert branch.sha == ""


class TestToTag:
    def test_basic(self):
        tag = GitHubAdapter._to_tag(_tag_data())
        assert tag.name == "v1.0.0"
        assert tag.sha == "def456"

    def test_with_message(self):
        data = _tag_data()
        data["message"] = "release v1.0.0"
        tag = GitHubAdapter._to_tag(data)
        # _to_tag は message フィールドを使わず常に "" を設定する
        assert tag.message == ""


class TestToCommitStatus:
    def test_basic(self):
        cs = GitHubAdapter._to_commit_status(_commit_status_data())
        assert cs.state == "success"
        assert cs.context == "ci/test"
        assert cs.description == "Tests passed"
        assert cs.target_url == "https://ci.example.com/build/1"
        assert cs.created_at == "2025-01-01T00:00:00Z"


class TestToWebhook:
    def test_basic(self):
        hook = GitHubAdapter._to_webhook(_webhook_data())
        assert hook.id == 100
        assert hook.url == "https://example.com/hook"
        assert hook.events == ("push", "pull_request")
        assert hook.active is True


class TestToDeployKey:
    def test_basic(self):
        dk = GitHubAdapter._to_deploy_key(_deploy_key_data())
        assert dk.id == 200
        assert dk.title == "Deploy Key"
        assert dk.key == "ssh-rsa AAAA..."
        assert dk.read_only is True


class TestToPipeline:
    def test_completed_success(self):
        pl = GitHubAdapter._to_pipeline(_pipeline_data(status="completed", conclusion="success"))
        assert pl.status == "success"
        assert pl.id == 300
        assert pl.ref == "main"

    def test_completed_failure(self):
        pl = GitHubAdapter._to_pipeline(_pipeline_data(status="completed", conclusion="failure"))
        assert pl.status == "failure"

    def test_in_progress(self):
        pl = GitHubAdapter._to_pipeline(_pipeline_data(status="in_progress", conclusion=None))
        assert pl.status == "running"

    def test_queued(self):
        pl = GitHubAdapter._to_pipeline(_pipeline_data(status="queued", conclusion=None))
        assert pl.status == "pending"


# --- PR 系 ---


class TestListPullRequests:
    def test_open(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls",
            json=[_pr_data()],
            status=200,
        )
        prs = github_adapter.list_pull_requests()
        assert len(prs) == 1
        assert prs[0].state == "open"

    def test_merged_filter(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls",
            json=[
                _pr_data(number=1, state="closed", merged_at="2025-01-03T00:00:00Z"),
                _pr_data(number=2, state="closed"),
            ],
            status=200,
        )
        prs = github_adapter.list_pull_requests(state="merged")
        assert len(prs) == 1
        assert prs[0].number == 1

    def test_pagination(self, mock_responses, github_adapter):
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
        prs = github_adapter.list_pull_requests(limit=10)
        assert len(prs) == 2


class TestCreatePullRequest:
    def test_create(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/pulls",
            json=_pr_data(),
            status=201,
        )
        pr = github_adapter.create_pull_request(
            title="PR #1",
            body="desc",
            base="main",
            head="feature",
        )
        assert isinstance(pr, PullRequest)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["draft"] is False

    def test_create_draft(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/pulls",
            json=_pr_data(draft=True),
            status=201,
        )
        _ = github_adapter.create_pull_request(
            title="Draft",
            body="",
            base="main",
            head="feature",
            draft=True,
        )
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["draft"] is True


class TestGetPullRequest:
    def test_get(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls/42",
            json=_pr_data(number=42),
            status=200,
        )
        pr = github_adapter.get_pull_request(42)
        assert pr.number == 42


class TestMergePullRequest:
    def test_merge(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.PUT,
            f"{REPOS}/pulls/1/merge",
            json={"merged": True},
            status=200,
        )
        github_adapter.merge_pull_request(1)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["merge_method"] == "merge"

    def test_merge_squash(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.PUT,
            f"{REPOS}/pulls/1/merge",
            json={"merged": True},
            status=200,
        )
        github_adapter.merge_pull_request(1, method="squash")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["merge_method"] == "squash"


class TestClosePullRequest:
    def test_close(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/pulls/1",
            json=_pr_data(state="closed"),
            status=200,
        )
        github_adapter.close_pull_request(1)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["state"] == "closed"


class TestCheckoutRefspec:
    def test_refspec(self, github_adapter):
        assert github_adapter.get_pr_checkout_refspec(42) == "refs/pull/42/head"


# --- Issue 系 ---


class TestListIssues:
    def test_excludes_prs(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues",
            json=[_issue_data(number=1), _issue_data(number=2, has_pr=True)],
            status=200,
        )
        issues = github_adapter.list_issues()
        assert len(issues) == 1
        assert issues[0].number == 1

    def test_with_filters(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues",
            json=[_issue_data()],
            status=200,
        )
        issues = github_adapter.list_issues(assignee="dev1", label="bug")
        assert len(issues) == 1
        req = mock_responses.calls[0].request
        assert "assignee=dev1" in req.url
        assert "labels=bug" in req.url


class TestCreateIssue:
    def test_create(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/issues",
            json=_issue_data(),
            status=201,
        )
        issue = github_adapter.create_issue(title="Issue #1", body="body")
        assert isinstance(issue, Issue)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert "assignees" not in req_body
        assert "labels" not in req_body

    def test_create_with_assignee_and_label(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/issues",
            json=_issue_data(),
            status=201,
        )
        github_adapter.create_issue(
            title="Issue",
            assignee="dev1",
            label="bug",
        )
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["assignees"] == ["dev1"]
        assert req_body["labels"] == ["bug"]


class TestGetIssue:
    def test_get(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues/5",
            json=_issue_data(number=5),
            status=200,
        )
        issue = github_adapter.get_issue(5)
        assert issue.number == 5


class TestCloseIssue:
    def test_close(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/issues/3",
            json=_issue_data(number=3, state="closed"),
            status=200,
        )
        github_adapter.close_issue(3)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["state"] == "closed"


# --- Repository 系 ---


class TestListRepositories:
    def test_with_owner(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/users/someone/repos",
            json=[_repo_data()],
            status=200,
        )
        repos = github_adapter.list_repositories(owner="someone")
        assert len(repos) == 1

    def test_no_owner(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/user/repos",
            json=[_repo_data()],
            status=200,
        )
        repos = github_adapter.list_repositories()
        assert len(repos) == 1

    def test_owner_with_special_chars_is_encoded(self, mock_responses, github_adapter):
        """list_repositories(owner="...") で特殊文字が URL エンコードされる（R41-01）。"""
        mock_responses.add(
            responses.GET,
            f"{BASE}/users/org%2Fsub/repos",
            json=[_repo_data()],
            status=200,
        )
        github_adapter.list_repositories(owner="org/sub")
        assert "%2F" in mock_responses.calls[0].request.url


class TestCreateRepository:
    def test_create(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.POST,
            f"{BASE}/user/repos",
            json=_repo_data(),
            status=201,
        )
        repo = github_adapter.create_repository(name="test-repo")
        assert isinstance(repo, Repository)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["name"] == "test-repo"


class TestGetRepository:
    def test_get(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/repos/other/other-repo",
            json=_repo_data(name="other-repo", full_name="other/other-repo"),
            status=200,
        )
        repo = github_adapter.get_repository(owner="other", name="other-repo")
        assert repo.name == "other-repo"

    def test_get_defaults(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}",
            json=_repo_data(),
            status=200,
        )
        repo = github_adapter.get_repository()
        assert repo.full_name == "test-owner/test-repo"

    def test_get_owner_with_special_chars_is_encoded(self, mock_responses, github_adapter):
        """owner に特殊文字が含まれる場合、URL エンコードされてリクエストされる。"""
        mock_responses.add(
            responses.GET,
            f"{BASE}/repos/org%2Fsub/repo",
            json=_repo_data(name="repo", full_name="org/sub/repo"),
            status=200,
        )
        github_adapter.get_repository(owner="org/sub", name="repo")
        assert "%2F" in mock_responses.calls[0].request.url


# --- Release 系 ---


class TestListReleases:
    def test_list(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/releases",
            json=[_release_data()],
            status=200,
        )
        releases = github_adapter.list_releases()
        assert len(releases) == 1
        assert releases[0].tag == "v1.0.0"


class TestCreateRelease:
    def test_create(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/releases",
            json=_release_data(),
            status=201,
        )
        rel = github_adapter.create_release(tag="v1.0.0", title="Release v1.0.0")
        assert isinstance(rel, Release)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["tag_name"] == "v1.0.0"


# --- Label 系 ---


class TestListLabels:
    def test_list(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/labels",
            json=[_label_data(), _label_data(name="enhancement")],
            status=200,
        )
        labels = github_adapter.list_labels()
        assert len(labels) == 2


class TestCreateLabel:
    def test_create(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/labels",
            json=_label_data(),
            status=201,
        )
        label = github_adapter.create_label(name="bug", color="d73a4a")
        assert label.name == "bug"

    def test_create_optional_fields(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/labels",
            json={"name": "minimal", "color": None, "description": None},
            status=201,
        )
        github_adapter.create_label(name="minimal")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert "color" not in req_body
        assert "description" not in req_body

    def test_create_with_description(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/labels",
            json={"name": "bug", "color": "d73a4a", "description": "Something broken"},
            status=201,
        )
        github_adapter.create_label(name="bug", color="d73a4a", description="Something broken")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["description"] == "Something broken"


# --- Milestone 系 ---


class TestListMilestones:
    def test_list(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/milestones",
            json=[_milestone_data()],
            status=200,
        )
        milestones = github_adapter.list_milestones()
        assert len(milestones) == 1
        assert milestones[0].title == "v1.0"


class TestCreateMilestone:
    def test_create(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/milestones",
            json=_milestone_data(),
            status=201,
        )
        ms = github_adapter.create_milestone(title="v1.0", due_date="2025-06-01T00:00:00Z")
        assert isinstance(ms, Milestone)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["due_on"] == "2025-06-01T00:00:00Z"

    def test_create_optional_fields(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/milestones",
            json=_milestone_data(),
            status=201,
        )
        github_adapter.create_milestone(title="v1.0")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert "description" not in req_body
        assert "due_on" not in req_body

    def test_create_with_description(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/milestones",
            json=_milestone_data(),
            status=201,
        )
        github_adapter.create_milestone(title="v1.0", description="First release")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["description"] == "First release"


# --- Registry ---


class TestReposPath:
    def test_non_ascii_owner_encoded(self):
        """非ASCII owner が URL エンコードされる。"""
        from gfo.http import HttpClient

        client = HttpClient("https://api.github.com")
        adapter = GitHubAdapter(client, "日本語-owner", "my-repo")
        path = adapter._repos_path()
        assert "日本語" not in path
        assert "%E6%97%A5%E6%9C%AC%E8%AA%9E" in path

    def test_special_char_owner_encoded(self):
        """スペースを含む owner が URL エンコードされる。"""
        from gfo.http import HttpClient

        client = HttpClient("https://api.github.com")
        adapter = GitHubAdapter(client, "my owner", "my-repo")
        path = adapter._repos_path()
        assert " " not in path
        assert "my%20owner" in path


class TestRegistry:
    def test_registered(self):
        assert get_adapter_class("github") is GitHubAdapter


class TestErrorHandling:
    """HTTP エラーが適切な例外に変換されることを確認する。"""

    def test_not_found_raises_error(self, mock_responses, github_adapter):
        mock_responses.add(responses.GET, f"{REPOS}/issues/999", status=404)
        with pytest.raises(NotFoundError):
            github_adapter.get_issue(999)

    def test_401_raises_auth_error(self, mock_responses, github_adapter):
        mock_responses.add(responses.GET, f"{REPOS}/pulls", status=401)
        with pytest.raises(AuthenticationError):
            github_adapter.list_pull_requests()

    def test_500_raises_server_error(self, mock_responses, github_adapter):
        mock_responses.add(responses.GET, f"{REPOS}/issues", status=500)
        with pytest.raises(ServerError):
            github_adapter.list_issues()

    def test_malformed_pr_raises_gfo_error(self, mock_responses, github_adapter):
        """_to_pull_request で必須フィールド欠落 → GfoError。"""
        from gfo.exceptions import GfoError

        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls/1",
            json={"incomplete": True},
            status=200,
        )
        with pytest.raises(GfoError):
            github_adapter.get_pull_request(1)

    def test_malformed_issue_raises_gfo_error(self, mock_responses, github_adapter):
        """_to_issue で必須フィールド欠落 → GfoError。"""
        from gfo.exceptions import GfoError

        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues/1",
            json={"incomplete": True},
            status=200,
        )
        with pytest.raises(GfoError):
            github_adapter.get_issue(1)

    def test_malformed_milestone_raises_gfo_error(self, mock_responses, github_adapter):
        """_to_milestone で必須フィールド欠落 → GfoError。"""
        from gfo.exceptions import GfoError

        mock_responses.add(
            responses.GET,
            f"{REPOS}/milestones",
            json=[{"incomplete": True}],
            status=200,
        )
        with pytest.raises(GfoError):
            github_adapter.list_milestones()

    def test_malformed_repository_raises_gfo_error(self, mock_responses, github_adapter):
        """_to_repository で必須フィールド欠落 → GfoError。"""
        from gfo.exceptions import GfoError

        mock_responses.add(
            responses.GET,
            f"{REPOS}",
            json={"incomplete": True},
            status=200,
        )
        with pytest.raises(GfoError):
            github_adapter.get_repository()

    def test_malformed_release_raises_gfo_error(self, mock_responses, github_adapter):
        """_to_release で必須フィールド欠落 → GfoError。"""
        from gfo.exceptions import GfoError

        mock_responses.add(
            responses.GET,
            f"{REPOS}/releases",
            json=[{"incomplete": True}],
            status=200,
        )
        with pytest.raises(GfoError):
            github_adapter.list_releases()

    def test_malformed_label_raises_gfo_error(self, mock_responses, github_adapter):
        """_to_label で必須フィールド欠落 → GfoError。"""
        from gfo.exceptions import GfoError

        mock_responses.add(
            responses.GET,
            f"{REPOS}/labels",
            json=[{"incomplete": True}],
            status=200,
        )
        with pytest.raises(GfoError):
            github_adapter.list_labels()


# --- Delete 系 ---


class TestDeleteRelease:
    def test_delete(self, mock_responses, github_adapter):
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
        github_adapter.delete_release(tag="v1.0.0")

    def test_tag_url_encoded(self, mock_responses, github_adapter):
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
        github_adapter.delete_release(tag="v1.0.0+rc1")
        assert "%2B" in mock_responses.calls[0].request.url


class TestDeleteLabel:
    def test_delete(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/labels/bug",
            status=204,
        )
        github_adapter.delete_label(name="bug")

    def test_name_url_encoded(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/labels/my%20label",
            status=204,
        )
        github_adapter.delete_label(name="my label")
        assert "%20" in mock_responses.calls[0].request.url


class TestDeleteMilestone:
    def test_delete(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/milestones/3",
            status=204,
        )
        github_adapter.delete_milestone(number=3)


class TestDeleteRepository:
    def test_delete(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.DELETE,
            REPOS,
            status=204,
        )
        github_adapter.delete_repository()
        assert mock_responses.calls[0].request.method == "DELETE"
        assert mock_responses.calls[0].request.url.endswith("/repos/test-owner/test-repo")


# --- Comment 系 ---


class TestListComments:
    def test_list(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues/1/comments",
            json=[_comment_data()],
            status=200,
        )
        comments = github_adapter.list_comments("issue", 1)
        assert len(comments) == 1
        assert isinstance(comments[0], Comment)
        assert comments[0].body == "A comment"

    def test_pr_resource(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues/2/comments",
            json=[_comment_data(comment_id=11)],
            status=200,
        )
        comments = github_adapter.list_comments("pr", 2)
        assert len(comments) == 1


class TestCreateComment:
    def test_create(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/issues/1/comments",
            json=_comment_data(),
            status=201,
        )
        comment = github_adapter.create_comment("issue", 1, body="A comment")
        assert isinstance(comment, Comment)

    def test_request_body(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/issues/1/comments",
            json=_comment_data(),
            status=201,
        )
        github_adapter.create_comment("issue", 1, body="Hello")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["body"] == "Hello"


class TestUpdateComment:
    def test_update(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/issues/comments/10",
            json=_comment_data(),
            status=200,
        )
        comment = github_adapter.update_comment("issue", 10, body="Updated")
        assert isinstance(comment, Comment)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["body"] == "Updated"


class TestDeleteComment:
    def test_delete(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/issues/comments/10",
            status=204,
        )
        github_adapter.delete_comment("issue", 10)
        assert mock_responses.calls[0].request.method == "DELETE"


# --- PR Update / Issue Update ---


class TestUpdatePullRequest:
    def test_update_title(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/pulls/1",
            json=_pr_data(),
            status=200,
        )
        pr = github_adapter.update_pull_request(1, title="New Title")
        assert isinstance(pr, PullRequest)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["title"] == "New Title"

    def test_update_body(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/pulls/1",
            json=_pr_data(),
            status=200,
        )
        github_adapter.update_pull_request(1, body="New body")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["body"] == "New body"

    def test_only_changed_fields_sent(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/pulls/1",
            json=_pr_data(),
            status=200,
        )
        github_adapter.update_pull_request(1, title="Only Title")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert "body" not in req_body
        assert "base" not in req_body


class TestUpdateIssue:
    def test_update_title(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/issues/1",
            json=_issue_data(),
            status=200,
        )
        issue = github_adapter.update_issue(1, title="New Title")
        assert isinstance(issue, Issue)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["title"] == "New Title"

    def test_only_changed_fields_sent(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/issues/1",
            json=_issue_data(),
            status=200,
        )
        github_adapter.update_issue(1, title="Title Only")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert "body" not in req_body
        assert "assignees" not in req_body


# --- Review 系 ---


class TestListReviews:
    def test_list(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls/1/reviews",
            json=[_review_data()],
            status=200,
        )
        reviews = github_adapter.list_reviews(1)
        assert len(reviews) == 1
        assert isinstance(reviews[0], Review)
        assert reviews[0].state == "approved"


class TestCreateReview:
    def test_approve(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/pulls/1/reviews",
            json=_review_data(state="APPROVED"),
            status=200,
        )
        review = github_adapter.create_review(1, state="approve")
        assert isinstance(review, Review)

    def test_request_body(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/pulls/1/reviews",
            json=_review_data(state="APPROVED"),
            status=200,
        )
        github_adapter.create_review(1, state="approve", body="LGTM")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["event"] == "APPROVE"
        assert req_body["body"] == "LGTM"


# --- Branch 系 ---


class TestListBranches:
    def test_list(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/branches",
            json=[_branch_data()],
            status=200,
        )
        branches = github_adapter.list_branches()
        assert len(branches) == 1
        assert isinstance(branches[0], Branch)
        assert branches[0].name == "feature"


class TestCreateBranch:
    def test_create_from_sha(self, mock_responses, github_adapter):
        # 40文字の hex SHA を渡すと直接 POST /git/refs する
        sha40 = "a" * 40
        mock_responses.add(
            responses.POST,
            f"{REPOS}/git/refs",
            json={"ref": "refs/heads/new-branch", "object": {"sha": sha40}},
            status=201,
        )
        mock_responses.add(
            responses.GET,
            f"{REPOS}/branches/new-branch",
            json=_branch_data(name="new-branch", sha=sha40),
            status=200,
        )
        branch = github_adapter.create_branch(name="new-branch", ref=sha40)
        assert isinstance(branch, Branch)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["ref"] == "refs/heads/new-branch"
        assert req_body["sha"] == sha40

    def test_create_from_branch_name(self, mock_responses, github_adapter):
        # 既存ブランチ名が ref として渡された場合、SHA を解決してから作成する
        mock_responses.add(
            responses.GET,
            f"{REPOS}/git/ref/heads/main",
            json={"object": {"sha": "sha999"}},
            status=200,
        )
        mock_responses.add(
            responses.POST,
            f"{REPOS}/git/refs",
            json={"ref": "refs/heads/new-branch", "object": {"sha": "sha999"}},
            status=201,
        )
        mock_responses.add(
            responses.GET,
            f"{REPOS}/branches/new-branch",
            json=_branch_data(name="new-branch", sha="sha999"),
            status=200,
        )
        github_adapter.create_branch(name="new-branch", ref="main")
        post_body = json.loads(mock_responses.calls[1].request.body)
        assert post_body["sha"] == "sha999"


class TestDeleteBranch:
    def test_delete(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/git/refs/heads/feature",
            status=204,
        )
        github_adapter.delete_branch(name="feature")
        assert mock_responses.calls[0].request.method == "DELETE"


# --- Tag 系 ---


class TestListTags:
    def test_list(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/tags",
            json=[_tag_data()],
            status=200,
        )
        tags = github_adapter.list_tags()
        assert len(tags) == 1
        assert isinstance(tags[0], Tag)
        assert tags[0].name == "v1.0.0"


class TestCreateTag:
    def test_create(self, mock_responses, github_adapter):
        # 40文字の hex SHA を渡すと直接 POST /git/refs する
        sha40 = "d" * 40
        mock_responses.add(
            responses.POST,
            f"{REPOS}/git/refs",
            json={"ref": "refs/tags/v2.0.0", "object": {"sha": sha40}},
            status=201,
        )
        mock_responses.add(
            responses.GET,
            f"{REPOS}/tags",
            json=[_tag_data(name="v2.0.0", sha=sha40)],
            status=200,
        )
        tag = github_adapter.create_tag(name="v2.0.0", ref=sha40)
        assert isinstance(tag, Tag)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["ref"] == "refs/tags/v2.0.0"


class TestDeleteTag:
    def test_delete(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/git/refs/tags/v1.0.0",
            status=204,
        )
        github_adapter.delete_tag(name="v1.0.0")
        assert mock_responses.calls[0].request.method == "DELETE"


# --- CommitStatus 系 ---


class TestListCommitStatuses:
    def test_list(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/statuses/abc123",
            json=[_commit_status_data()],
            status=200,
        )
        statuses = github_adapter.list_commit_statuses("abc123")
        assert len(statuses) == 1
        assert isinstance(statuses[0], CommitStatus)
        assert statuses[0].state == "success"


class TestCreateCommitStatus:
    def test_create(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/statuses/abc123",
            json=_commit_status_data(),
            status=201,
        )
        status = github_adapter.create_commit_status("abc123", state="success", context="ci/test")
        assert isinstance(status, CommitStatus)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["state"] == "success"
        assert req_body["context"] == "ci/test"


# --- File 系 ---


class TestGetFileContent:
    def test_get(self, mock_responses, github_adapter):
        import base64 as _b64

        content_b64 = _b64.b64encode(b"file content").decode()
        mock_responses.add(
            responses.GET,
            f"{REPOS}/contents/README.md",
            json={"content": content_b64, "sha": "sha1"},
            status=200,
        )
        content, sha = github_adapter.get_file_content("README.md")
        assert content == "file content"
        assert sha == "sha1"


class TestCreateOrUpdateFile:
    def test_create_new(self, mock_responses, github_adapter):
        import base64 as _b64

        content_b64 = _b64.b64encode(b"new content").decode()
        mock_responses.add(
            responses.PUT,
            f"{REPOS}/contents/new-file.md",
            json={"content": {"name": "new-file.md", "sha": "newsha"}},
            status=201,
        )
        github_adapter.create_or_update_file(
            "new-file.md", content="new content", message="Add file"
        )
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["message"] == "Add file"
        assert req_body["content"] == content_b64

    def test_update_existing(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.PUT,
            f"{REPOS}/contents/existing.md",
            json={"content": {"name": "existing.md", "sha": "updatedsha"}},
            status=200,
        )
        github_adapter.create_or_update_file(
            "existing.md", content="updated content", message="Update file", sha="oldsha"
        )
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["sha"] == "oldsha"


class TestDeleteFile:
    def test_delete(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/contents/to-delete.md",
            json={"commit": {"sha": "commitsha"}},
            status=200,
        )
        github_adapter.delete_file("to-delete.md", sha="filsha", message="Delete file")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["sha"] == "filsha"
        assert req_body["message"] == "Delete file"


# --- Fork 系 ---


class TestForkRepository:
    def test_fork(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/forks",
            json=_repo_data(name="test-repo", full_name="forker/test-repo"),
            status=202,
        )
        repo = github_adapter.fork_repository()
        assert isinstance(repo, Repository)

    def test_fork_with_org(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/forks",
            json=_repo_data(name="test-repo", full_name="myorg/test-repo"),
            status=202,
        )
        github_adapter.fork_repository(organization="myorg")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["organization"] == "myorg"


# --- Webhook 系 ---


class TestListWebhooks:
    def test_list(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/hooks",
            json=[_webhook_data()],
            status=200,
        )
        webhooks = github_adapter.list_webhooks()
        assert len(webhooks) == 1
        assert isinstance(webhooks[0], Webhook)


class TestCreateWebhook:
    def test_create(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/hooks",
            json=_webhook_data(),
            status=201,
        )
        webhook = github_adapter.create_webhook(
            url="https://example.com/hook", events=["push", "pull_request"]
        )
        assert isinstance(webhook, Webhook)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["config"]["url"] == "https://example.com/hook"
        assert req_body["events"] == ["push", "pull_request"]


class TestDeleteWebhook:
    def test_delete(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/hooks/100",
            status=204,
        )
        github_adapter.delete_webhook(hook_id=100)
        assert mock_responses.calls[0].request.method == "DELETE"


# --- DeployKey 系 ---


class TestListDeployKeys:
    def test_list(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/keys",
            json=[_deploy_key_data()],
            status=200,
        )
        keys = github_adapter.list_deploy_keys()
        assert len(keys) == 1
        assert isinstance(keys[0], DeployKey)


class TestCreateDeployKey:
    def test_create(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/keys",
            json=_deploy_key_data(),
            status=201,
        )
        key = github_adapter.create_deploy_key(
            title="Deploy Key", key="ssh-rsa AAAA...", read_only=True
        )
        assert isinstance(key, DeployKey)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["title"] == "Deploy Key"
        assert req_body["read_only"] is True


class TestDeleteDeployKey:
    def test_delete(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/keys/200",
            status=204,
        )
        github_adapter.delete_deploy_key(key_id=200)
        assert mock_responses.calls[0].request.method == "DELETE"


# --- Collaborator 系 ---


class TestListCollaborators:
    def test_list(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/collaborators",
            json=[{"login": "collab1"}, {"login": "collab2"}],
            status=200,
        )
        collabs = github_adapter.list_collaborators()
        assert collabs == ["collab1", "collab2"]


class TestAddCollaborator:
    def test_add(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.PUT,
            f"{REPOS}/collaborators/newuser",
            status=201,
        )
        github_adapter.add_collaborator(username="newuser")
        assert mock_responses.calls[0].request.method == "PUT"


class TestRemoveCollaborator:
    def test_remove(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/collaborators/olduser",
            status=204,
        )
        github_adapter.remove_collaborator(username="olduser")
        assert mock_responses.calls[0].request.method == "DELETE"


# --- Pipeline 系 ---


class TestListPipelines:
    def test_list(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/actions/runs",
            json={"workflow_runs": [_pipeline_data()], "total_count": 1},
            status=200,
        )
        pipelines = github_adapter.list_pipelines()
        assert len(pipelines) == 1
        assert isinstance(pipelines[0], Pipeline)

    def test_with_ref(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/actions/runs",
            json={"workflow_runs": [_pipeline_data()], "total_count": 1},
            status=200,
        )
        github_adapter.list_pipelines(ref="main")
        req = mock_responses.calls[0].request
        assert "branch=main" in req.url


class TestGetPipeline:
    def test_get(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/actions/runs/300",
            json=_pipeline_data(run_id=300),
            status=200,
        )
        pipeline = github_adapter.get_pipeline(300)
        assert isinstance(pipeline, Pipeline)
        assert pipeline.id == 300


class TestCancelPipeline:
    def test_cancel(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/actions/runs/300/cancel",
            status=202,
        )
        github_adapter.cancel_pipeline(300)
        assert mock_responses.calls[0].request.method == "POST"


# --- User / Search 系 ---


class TestGetCurrentUser:
    def test_get(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/user",
            json={"login": "testuser", "id": 1},
            status=200,
        )
        user = github_adapter.get_current_user()
        assert user["login"] == "testuser"


class TestSearchRepositories:
    def test_search(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/search/repositories",
            json={"items": [_repo_data()], "total_count": 1},
            status=200,
        )
        repos = github_adapter.search_repositories("test")
        assert len(repos) == 1
        assert isinstance(repos[0], Repository)


class TestSearchIssues:
    def test_search(self, mock_responses, github_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/search/issues",
            json={"items": [_issue_data()], "total_count": 1},
            status=200,
        )
        issues = github_adapter.search_issues("bug")
        assert len(issues) == 1
        assert isinstance(issues[0], Issue)
