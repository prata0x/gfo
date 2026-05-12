"""GiteaAdapter のテスト。"""

from __future__ import annotations

import json

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
from gfo.adapter.gitea import GiteaAdapter
from gfo.adapter.registry import get_adapter_class
from gfo.exceptions import (
    AuthenticationError,
    GfoError,
    NotFoundError,
    NotSupportedError,
    ServerError,
)

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


def _repo_data(*, name="test-repo", full_name="test-owner/test-repo", private=False):
    return {
        "name": name,
        "full_name": full_name,
        "description": "A test repo",
        "private": private,
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
        assert repo.visibility == "public"


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

    def test_merged_fetches_all_pages_to_meet_limit(self, mock_responses, gitea_adapter):
        """state="merged" は closed を全件取得してから merged のみ抽出して limit を満たすこと。"""
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls",
            json=[
                _pr_data(number=1, state="closed", merged_at="2025-01-03T00:00:00Z"),
                _pr_data(number=2, state="closed"),
            ],
            status=200,
            headers={"Link": f'<{REPOS}/pulls?page=2>; rel="next"'},
        )
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls",
            json=[
                _pr_data(number=3, state="closed"),
                _pr_data(number=4, state="closed", merged_at="2025-01-04T00:00:00Z"),
            ],
            status=200,
        )
        prs = gitea_adapter.list_pull_requests(state="merged", limit=2)
        assert len(prs) == 2
        assert {pr.number for pr in prs} == {1, 4}

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

    def test_author_filter(self, mock_responses, gitea_adapter):
        """author パラメータが poster としてクエリパラメータに送信されることを確認する。"""
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls",
            json=[_pr_data()],
            status=200,
        )
        gitea_adapter.list_pull_requests(author="alice")
        assert "poster=alice" in mock_responses.calls[0].request.url

    def test_label_filter(self, mock_responses, gitea_adapter):
        """label パラメータが labels としてクエリパラメータに送信されることを確認する。"""
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls",
            json=[_pr_data()],
            status=200,
        )
        gitea_adapter.list_pull_requests(label="bug")
        assert "labels=bug" in mock_responses.calls[0].request.url

    def test_assignee_filter(self, mock_responses, gitea_adapter):
        """assignee パラメータがクエリパラメータに送信されることを確認する。"""
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls",
            json=[_pr_data()],
            status=200,
        )
        gitea_adapter.list_pull_requests(assignee="dev")
        assert "assignee=dev" in mock_responses.calls[0].request.url

    def test_search_filter(self, mock_responses, gitea_adapter):
        """search パラメータが q としてクエリパラメータに送信されることを確認する。"""
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls",
            json=[_pr_data()],
            status=200,
        )
        gitea_adapter.list_pull_requests(search="keyword")
        assert "q=keyword" in mock_responses.calls[0].request.url

    def test_base_filter(self, mock_responses, gitea_adapter):
        """base パラメータがクエリパラメータに送信されることを確認する。"""
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls",
            json=[_pr_data()],
            status=200,
        )
        gitea_adapter.list_pull_requests(base="main")
        assert "base=main" in mock_responses.calls[0].request.url

    def test_head_filter(self, mock_responses, gitea_adapter):
        """head パラメータがクエリパラメータに送信されることを確認する。"""
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls",
            json=[_pr_data()],
            status=200,
        )
        gitea_adapter.list_pull_requests(head="feature")
        assert "head=feature" in mock_responses.calls[0].request.url

    def test_draft_warns(self, mock_responses, gitea_adapter):
        """draft パラメータが未対応の警告を出すことを確認する。"""
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls",
            json=[_pr_data()],
            status=200,
        )
        with pytest.warns(UserWarning, match="does not support draft"):
            gitea_adapter.list_pull_requests(draft=True)


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

    def test_create_with_reviewers(self, mock_responses, gitea_adapter):
        mock_responses.add(responses.POST, f"{REPOS}/pulls", json=_pr_data(), status=201)
        mock_responses.add(
            responses.POST, f"{REPOS}/pulls/1/requested_reviewers", json={}, status=201
        )
        gitea_adapter.create_pull_request(
            title="PR #1",
            body="desc",
            base="main",
            head="feature",
            reviewers=["alice", "bob"],
        )
        req_body = json.loads(mock_responses.calls[1].request.body)
        assert req_body["reviewers"] == ["alice", "bob"]

    def test_create_with_assignees(self, mock_responses, gitea_adapter):
        mock_responses.add(responses.POST, f"{REPOS}/pulls", json=_pr_data(), status=201)
        gitea_adapter.create_pull_request(
            title="PR #1",
            body="desc",
            base="main",
            head="feature",
            assignees=["alice"],
        )
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["assignees"] == ["alice"]

    def test_create_with_labels(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/labels",
            json=[
                {"id": 1, "name": "bug", "color": "ff0000"},
                {"id": 2, "name": "urgent", "color": "00ff00"},
            ],
            status=200,
        )
        mock_responses.add(responses.POST, f"{REPOS}/pulls", json=_pr_data(), status=201)
        gitea_adapter.create_pull_request(
            title="PR #1",
            body="desc",
            base="main",
            head="feature",
            labels=["bug", "urgent"],
        )
        req_body = json.loads(mock_responses.calls[1].request.body)
        assert req_body["labels"] == [1, 2]

    def test_create_with_milestone(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/milestones",
            json=[
                {"id": 1, "title": "v1.0", "description": None, "state": "open", "due_on": None},
            ],
            status=200,
        )
        mock_responses.add(responses.POST, f"{REPOS}/pulls", json=_pr_data(), status=201)
        gitea_adapter.create_pull_request(
            title="PR #1",
            body="desc",
            base="main",
            head="feature",
            milestone="v1.0",
        )
        req_body = json.loads(mock_responses.calls[1].request.body)
        assert req_body["milestone"] == 1

    def test_create_with_label_not_found(self, mock_responses, gitea_adapter):
        mock_responses.add(responses.GET, f"{REPOS}/labels", json=[], status=200)
        with pytest.raises(GfoError, match="Label not found"):
            gitea_adapter.create_pull_request(
                title="PR #1",
                body="desc",
                base="main",
                head="feature",
                labels=["nonexistent"],
            )

    def test_create_with_label_on_paginated_results(self, mock_responses, gitea_adapter):
        """_resolve_label_ids が複数ページに分かれたラベルを全件取得して解決すること。"""
        # 1 ページ目（Link ヘッダで 2 ページ目を示す）
        mock_responses.add(
            responses.GET,
            f"{REPOS}/labels",
            json=[{"id": 1, "name": "bug", "color": "#ff0000"}],
            status=200,
            headers={"Link": f'<{REPOS}/labels?page=2>; rel="next"'},
        )
        # 2 ページ目（探しているラベルはこちらにある）
        mock_responses.add(
            responses.GET,
            f"{REPOS}/labels",
            json=[{"id": 99, "name": "urgent", "color": "#00ff00"}],
            status=200,
        )
        mock_responses.add(responses.POST, f"{REPOS}/pulls", json=_pr_data(), status=201)
        gitea_adapter.create_pull_request(
            title="PR #1",
            body="desc",
            base="main",
            head="feature",
            labels=["urgent"],
        )
        req_body = json.loads(mock_responses.calls[-1].request.body)
        assert req_body["labels"] == [99]


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

    def test_merge_with_commit_message(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/pulls/1/merge",
            json={"merged": True},
            status=200,
        )
        gitea_adapter.merge_pull_request(1, title="Custom title", message="Custom body")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["MergeTitleField"] == "Custom title"
        assert req_body["MergeMessageField"] == "Custom body"

    def test_merge_with_title_only(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/pulls/1/merge",
            status=200,
        )
        gitea_adapter.merge_pull_request(1, title="Custom title")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["MergeTitleField"] == "Custom title"
        assert "MergeMessageField" not in req_body


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


class TestReopenPullRequest:
    def test_reopen(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/pulls/1",
            json=_pr_data(state="open"),
            status=200,
        )
        gitea_adapter.reopen_pull_request(1)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["state"] == "open"


class TestLockPullRequest:
    def test_lock(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.PUT,
            f"{REPOS}/issues/1/lock",
            status=204,
        )
        gitea_adapter.lock_pull_request(1)

    def test_unlock(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/issues/1/lock",
            status=204,
        )
        gitea_adapter.unlock_pull_request(1)


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

    def test_author_filter(self, mock_responses, gitea_adapter):
        """author フィルタが created_by パラメータとして送信されることを確認する。"""
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues",
            json=[_issue_data()],
            status=200,
        )
        gitea_adapter.list_issues(author="alice")
        req = mock_responses.calls[0].request
        assert "created_by=alice" in req.url

    def test_milestone_filter(self, mock_responses, gitea_adapter):
        """milestone フィルタが milestones パラメータとして送信されることを確認する。"""
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues",
            json=[_issue_data()],
            status=200,
        )
        gitea_adapter.list_issues(milestone="v1.0")
        req = mock_responses.calls[0].request
        assert "milestones=v1.0" in req.url

    def test_search_filter(self, mock_responses, gitea_adapter):
        """search フィルタが q パラメータとして送信されることを確認する。"""
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues",
            json=[_issue_data()],
            status=200,
        )
        gitea_adapter.list_issues(search="login bug")
        req = mock_responses.calls[0].request
        assert "q=" in req.url


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
            responses.GET,
            f"{REPOS}/labels",
            json=[{"id": 7, "name": "bug", "color": "#d73a4a"}],
        )
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
        req_body = json.loads(mock_responses.calls[1].request.body)
        assert req_body["assignees"] == ["dev1"]
        assert req_body["labels"] == [7]

    def test_create_with_due_date(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/issues",
            json=_issue_data(),
            status=201,
        )
        gitea_adapter.create_issue(title="Issue", due_date="2026-04-01")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["due_date"] == "2026-04-01"

    def test_create_without_due_date(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/issues",
            json=_issue_data(),
            status=201,
        )
        gitea_adapter.create_issue(title="Issue")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert "due_date" not in req_body


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


class TestReopenIssue:
    def test_reopen(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/issues/3",
            json=_issue_data(number=3, state="open"),
            status=200,
        )
        gitea_adapter.reopen_issue(3)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["state"] == "open"


class TestLockIssue:
    def test_lock(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.PUT,
            f"{REPOS}/issues/3/lock",
            status=204,
        )
        gitea_adapter.lock_issue(3)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body == {}

    def test_lock_with_reason(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.PUT,
            f"{REPOS}/issues/3/lock",
            status=204,
        )
        gitea_adapter.lock_issue(3, reason="spam")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body == {"lock_reason": "spam"}

    def test_unlock(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/issues/3/lock",
            status=204,
        )
        gitea_adapter.unlock_issue(3)


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

    def test_create_org_repo(self, mock_responses, gitea_adapter):
        """組織リポジトリを作成する。"""
        mock_responses.add(
            responses.POST,
            f"{BASE}/orgs/my-org/repos",
            json=_repo_data(),
            status=201,
        )
        gitea_adapter.create_repository(name="new-repo", organization="my-org")
        # POST 先が /orgs/my-org/repos であること
        assert "/orgs/my-org/repos" in mock_responses.calls[0].request.url

    def test_create_internal_raises(self, gitea_adapter):
        """internal visibility は Gitea で未サポート。"""
        with pytest.raises(NotSupportedError):
            gitea_adapter.create_repository(name="new-repo", visibility="internal")


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

    def test_create_with_target(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/releases",
            json=_release_data(),
            status=201,
        )
        gitea_adapter.create_release(tag="v1.0.0", target="develop")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["target_commitish"] == "develop"

    def test_create_without_target_omits_target_commitish(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/releases",
            json=_release_data(),
            status=201,
        )
        gitea_adapter.create_release(tag="v1.0.0")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert "target_commitish" not in req_body


class TestGetRelease:
    def test_get(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/releases/tags/v1.0.0",
            json=_release_data(),
            status=200,
        )
        rel = gitea_adapter.get_release(tag="v1.0.0")
        assert isinstance(rel, Release)
        assert rel.tag == "v1.0.0"

    def test_tag_url_encoded(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/releases/tags/v1.0.0%2Brc1",
            json=_release_data(tag="v1.0.0+rc1"),
            status=200,
        )
        rel = gitea_adapter.get_release(tag="v1.0.0+rc1")
        assert rel.tag == "v1.0.0+rc1"


class TestUpdateRelease:
    def test_update(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/releases/tags/v1.0.0",
            json={"id": 42, "tag_name": "v1.0.0"},
            status=200,
        )
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/releases/42",
            json=_release_data(),
            status=200,
        )
        rel = gitea_adapter.update_release(tag="v1.0.0", title="Updated")
        assert isinstance(rel, Release)
        req_body = json.loads(mock_responses.calls[1].request.body)
        assert req_body["name"] == "Updated"

    def test_update_all_fields(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/releases/tags/v1.0.0",
            json={"id": 42, "tag_name": "v1.0.0"},
            status=200,
        )
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/releases/42",
            json=_release_data(),
            status=200,
        )
        gitea_adapter.update_release(
            tag="v1.0.0",
            title="New",
            notes="Notes",
            draft=True,
            prerelease=True,
        )
        req_body = json.loads(mock_responses.calls[1].request.body)
        assert req_body["name"] == "New"
        assert req_body["body"] == "Notes"
        assert req_body["draft"] is True
        assert req_body["prerelease"] is True

    def test_update_no_optional_fields(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/releases/tags/v1.0.0",
            json={"id": 42, "tag_name": "v1.0.0"},
            status=200,
        )
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/releases/42",
            json=_release_data(),
            status=200,
        )
        gitea_adapter.update_release(tag="v1.0.0")
        req_body = json.loads(mock_responses.calls[1].request.body)
        assert "name" not in req_body
        assert "body" not in req_body
        assert "draft" not in req_body
        assert "prerelease" not in req_body


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


class TestUpdateLabel:
    def test_update(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/labels",
            json=[{"id": 10, "name": "bug", "color": "d73a4a", "description": ""}],
            status=200,
        )
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/labels/10",
            json=_label_data(name="bug-fix"),
            status=200,
        )
        label = gitea_adapter.update_label(name="bug", new_name="bug-fix")
        assert label.name == "bug-fix"

    def test_update_color(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/labels",
            json=[{"id": 10, "name": "bug", "color": "d73a4a", "description": ""}],
            status=200,
        )
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/labels/10",
            json=_label_data(),
            status=200,
        )
        gitea_adapter.update_label(name="bug", color="ff0000")
        req_body = json.loads(mock_responses.calls[1].request.body)
        assert req_body["color"] == "ff0000"

    def test_not_found_raises_error(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/labels",
            json=[{"id": 10, "name": "other", "color": "d73a4a", "description": ""}],
            status=200,
        )
        with pytest.raises(NotFoundError):
            gitea_adapter.update_label(name="bug", new_name="bug-fix")

    def test_optional_fields_omitted(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/labels",
            json=[{"id": 10, "name": "bug", "color": "d73a4a", "description": ""}],
            status=200,
        )
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/labels/10",
            json=_label_data(),
            status=200,
        )
        gitea_adapter.update_label(name="bug")
        req_body = json.loads(mock_responses.calls[1].request.body)
        assert "name" not in req_body
        assert "color" not in req_body
        assert "description" not in req_body


class TestDeleteMilestone:
    def test_delete(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/milestones/3",
            status=204,
        )
        gitea_adapter.delete_milestone(number=3)


class TestGetMilestone:
    def test_get(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/milestones/1",
            json=_milestone_data(),
            status=200,
        )
        ms = gitea_adapter.get_milestone(1)
        assert isinstance(ms, Milestone)
        assert ms.title == "v1.0"

    def test_get_number(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/milestones/5",
            json=_milestone_data(number=5),
            status=200,
        )
        ms = gitea_adapter.get_milestone(5)
        assert ms.number == 5


class TestUpdateMilestone:
    def test_update_title(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/milestones/1",
            json=_milestone_data(),
            status=200,
        )
        ms = gitea_adapter.update_milestone(1, title="v2.0")
        assert isinstance(ms, Milestone)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["title"] == "v2.0"

    def test_update_state(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/milestones/1",
            json=_milestone_data(),
            status=200,
        )
        gitea_adapter.update_milestone(1, state="closed")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["state"] == "closed"

    def test_update_due_date(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/milestones/1",
            json=_milestone_data(),
            status=200,
        )
        gitea_adapter.update_milestone(1, due_date="2026-01-01")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["due_on"] == "2026-01-01"

    def test_update_optional_fields_omitted(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/milestones/1",
            json=_milestone_data(),
            status=200,
        )
        gitea_adapter.update_milestone(1)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert "title" not in req_body
        assert "description" not in req_body
        assert "due_on" not in req_body
        assert "state" not in req_body


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

    def test_add_labels(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls/1",
            json={
                **_pr_data(),
                "labels": [{"id": 1, "name": "existing"}],
                "assignees": [],
            },
            status=200,
        )
        mock_responses.add(
            responses.GET,
            f"{REPOS}/labels",
            json=[
                {"id": 1, "name": "existing", "color": "ff0000"},
                {"id": 2, "name": "new", "color": "00ff00"},
            ],
            status=200,
        )
        mock_responses.add(responses.PATCH, f"{REPOS}/pulls/1", json=_pr_data(), status=200)
        gitea_adapter.update_pull_request(1, add_labels=["new"])
        req_body = json.loads(mock_responses.calls[2].request.body)
        assert sorted(req_body["labels"]) == [1, 2]

    def test_milestone(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/milestones",
            json=[
                {"id": 3, "title": "v1.0", "description": None, "state": "open", "due_on": None},
            ],
            status=200,
        )
        mock_responses.add(responses.PATCH, f"{REPOS}/pulls/1", json=_pr_data(), status=200)
        gitea_adapter.update_pull_request(1, milestone="v1.0")
        req_body = json.loads(mock_responses.calls[1].request.body)
        assert req_body["milestone"] == 3

    def test_draft_true(self, mock_responses, gitea_adapter):
        mock_responses.add(responses.PATCH, f"{REPOS}/pulls/1", json=_pr_data(), status=200)
        gitea_adapter.update_pull_request(1, draft=True)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["draft"] is True

    def test_draft_false(self, mock_responses, gitea_adapter):
        mock_responses.add(responses.PATCH, f"{REPOS}/pulls/1", json=_pr_data(), status=200)
        gitea_adapter.update_pull_request(1, draft=False)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["draft"] is False

    def test_remove_labels(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls/1",
            json={
                **_pr_data(),
                "labels": [{"id": 1, "name": "bug"}, {"id": 2, "name": "wontfix"}],
                "assignees": [],
            },
            status=200,
        )
        mock_responses.add(
            responses.GET,
            f"{REPOS}/labels",
            json=[
                {"id": 1, "name": "bug", "color": "ff0000"},
                {"id": 2, "name": "wontfix", "color": "cccccc"},
            ],
            status=200,
        )
        mock_responses.add(responses.PATCH, f"{REPOS}/pulls/1", json=_pr_data(), status=200)
        gitea_adapter.update_pull_request(1, remove_labels=["wontfix"])
        req_body = json.loads(mock_responses.calls[2].request.body)
        assert req_body["labels"] == [1]

    def test_add_assignees(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls/1",
            json={
                **_pr_data(),
                "labels": [],
                "assignees": [{"login": "dev1"}],
            },
            status=200,
        )
        mock_responses.add(responses.PATCH, f"{REPOS}/pulls/1", json=_pr_data(), status=200)
        gitea_adapter.update_pull_request(1, add_assignees=["dev2"])
        req_body = json.loads(mock_responses.calls[1].request.body)
        assert sorted(req_body["assignees"]) == ["dev1", "dev2"]

    def test_remove_assignees(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls/1",
            json={
                **_pr_data(),
                "labels": [],
                "assignees": [{"login": "dev1"}, {"login": "dev2"}],
            },
            status=200,
        )
        mock_responses.add(responses.PATCH, f"{REPOS}/pulls/1", json=_pr_data(), status=200)
        gitea_adapter.update_pull_request(1, remove_assignees=["dev2"])
        req_body = json.loads(mock_responses.calls[1].request.body)
        assert req_body["assignees"] == ["dev1"]


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

    def test_update_due_date(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/issues/1",
            json=_issue_data(),
            status=200,
        )
        gitea_adapter.update_issue(1, due_date="2026-05-01")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["due_date"] == "2026-05-01"

    def test_add_labels(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues/1",
            json={
                **_issue_data(),
                "labels": [{"id": 1, "name": "bug"}],
                "assignees": [{"login": "dev1"}],
            },
            status=200,
        )
        mock_responses.add(
            responses.GET,
            f"{REPOS}/labels",
            json=[
                {"id": 1, "name": "bug", "color": "ff0000"},
                {"id": 5, "name": "feature", "color": "00ff00"},
            ],
            status=200,
        )
        mock_responses.add(responses.PATCH, f"{REPOS}/issues/1", json=_issue_data(), status=200)
        gitea_adapter.update_issue(1, add_labels=["feature"])
        req_body = json.loads(mock_responses.calls[2].request.body)
        assert sorted(req_body["labels"]) == [1, 5]

    def test_add_assignees(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues/1",
            json={
                **_issue_data(),
                "labels": [],
                "assignees": [{"login": "dev1"}],
            },
            status=200,
        )
        mock_responses.add(responses.PATCH, f"{REPOS}/issues/1", json=_issue_data(), status=200)
        gitea_adapter.update_issue(1, add_assignees=["dev2"])
        req_body = json.loads(mock_responses.calls[1].request.body)
        assert sorted(req_body["assignees"]) == ["dev1", "dev2"]

    def test_milestone(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/milestones",
            json=[
                {"id": 7, "title": "v2.0", "description": None, "state": "open", "due_on": None},
            ],
            status=200,
        )
        mock_responses.add(responses.PATCH, f"{REPOS}/issues/1", json=_issue_data(), status=200)
        gitea_adapter.update_issue(1, milestone="v2.0")
        req_body = json.loads(mock_responses.calls[1].request.body)
        assert req_body["milestone"] == 7

    def test_remove_labels(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues/1",
            json={
                **_issue_data(),
                "labels": [{"id": 1, "name": "bug"}, {"id": 5, "name": "feature"}],
                "assignees": [],
            },
            status=200,
        )
        mock_responses.add(
            responses.GET,
            f"{REPOS}/labels",
            json=[
                {"id": 1, "name": "bug", "color": "ff0000"},
                {"id": 5, "name": "feature", "color": "00ff00"},
            ],
            status=200,
        )
        mock_responses.add(responses.PATCH, f"{REPOS}/issues/1", json=_issue_data(), status=200)
        gitea_adapter.update_issue(1, remove_labels=["feature"])
        req_body = json.loads(mock_responses.calls[2].request.body)
        assert req_body["labels"] == [1]

    def test_remove_assignees(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues/1",
            json={
                **_issue_data(),
                "labels": [],
                "assignees": [{"login": "dev1"}, {"login": "dev2"}],
            },
            status=200,
        )
        mock_responses.add(responses.PATCH, f"{REPOS}/issues/1", json=_issue_data(), status=200)
        gitea_adapter.update_issue(1, remove_assignees=["dev2"])
        req_body = json.loads(mock_responses.calls[1].request.body)
        assert req_body["assignees"] == ["dev1"]


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
        assert req_body["event"] == "APPROVED"

    def test_request_changes(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/pulls/1/reviews",
            json={
                "id": 21,
                "state": "CHANGES_REQUESTED",
                "body": "要修正",
                "user": {"login": "reviewer"},
                "html_url": "",
                "submitted_at": "2025-01-01T00:00:00Z",
            },
            status=200,
        )
        review = gitea_adapter.create_review(1, state="REQUEST_CHANGES", body="要修正")
        assert review.state == "changes_requested"
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["event"] == "REQUEST_CHANGES"
        assert req_body["body"] == "要修正"

    def test_comment(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/pulls/1/reviews",
            json={
                "id": 22,
                "state": "COMMENTED",
                "body": "LGTM",
                "user": {"login": "reviewer"},
                "html_url": "",
                "submitted_at": "2025-01-01T00:00:00Z",
            },
            status=200,
        )
        review = gitea_adapter.create_review(1, state="COMMENT", body="LGTM")
        assert review.state == "commented"
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["event"] == "COMMENT"
        assert req_body["body"] == "LGTM"


# --- Branch 系 ---


class TestGetBranch:
    def test_get(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/branches/feature",
            json=_branch_data(),
            status=200,
        )
        branch = gitea_adapter.get_branch("feature")
        assert isinstance(branch, Branch)
        assert branch.name == "feature"
        assert branch.sha == "abc123"

    def test_not_found(self, mock_responses, gitea_adapter):
        from gfo.exceptions import NotFoundError

        mock_responses.add(
            responses.GET,
            f"{REPOS}/branches/nonexistent",
            json={"message": "Branch not found"},
            status=404,
        )
        with pytest.raises(NotFoundError):
            gitea_adapter.get_branch("nonexistent")


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


class TestGetTag:
    def test_get(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/tags/v1.0.0",
            json=_tag_data(),
            status=200,
        )
        tag = gitea_adapter.get_tag("v1.0.0")
        assert isinstance(tag, Tag)
        assert tag.name == "v1.0.0"
        assert tag.sha == "def456"

    def test_not_found(self, mock_responses, gitea_adapter):
        from gfo.exceptions import NotFoundError

        mock_responses.add(
            responses.GET,
            f"{REPOS}/tags/nonexistent",
            json={"message": "Not Found"},
            status=404,
        )
        with pytest.raises(NotFoundError):
            gitea_adapter.get_tag("nonexistent")


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
            json={
                "content": {"name": "new-file.md", "sha": "newsha"},
                "commit": {"sha": "commit-abc123"},
            },
            status=201,
        )
        result = gitea_adapter.create_or_update_file(
            "new-file.md", content="new content", message="Add file"
        )
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["content"] == content_b64
        assert result == "commit-abc123"

    def test_update_existing(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.PUT,
            f"{REPOS}/contents/existing.md",
            json={
                "content": {"name": "existing.md", "sha": "updatedsha"},
                "commit": {"sha": "commit-updated"},
            },
            status=200,
        )
        result = gitea_adapter.create_or_update_file(
            "existing.md", content="updated", message="Update", sha="oldsha"
        )
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["sha"] == "oldsha"
        assert result == "commit-updated"


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


class TestSyncFork:
    def test_sync_fork(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            REPOS,
            json=_repo_data(),
            status=200,
        )
        mock_responses.add(
            responses.POST,
            f"{REPOS}/merge-upstream",
            json={},
            status=200,
        )
        gitea_adapter.sync_fork()
        req_body = json.loads(mock_responses.calls[1].request.body)
        assert req_body["branch"] == "main"

    def test_sync_fork_with_branch(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/merge-upstream",
            json={},
            status=200,
        )
        gitea_adapter.sync_fork(branch="develop")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["branch"] == "develop"


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


class TestTestWebhook:
    def test_test(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/hooks/100/tests",
            status=204,
        )
        gitea_adapter.test_webhook(hook_id=100)
        assert mock_responses.calls[0].request.method == "POST"


class TestUpdateWebhook:
    def test_update_url(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/hooks/100",
            json={
                "id": 100,
                "config": {"url": "https://new.example.com/hook", "content_type": "json"},
                "events": ["push"],
                "active": True,
            },
            status=200,
        )
        webhook = gitea_adapter.update_webhook(100, url="https://new.example.com/hook")
        assert webhook.url == "https://new.example.com/hook"
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["config"]["url"] == "https://new.example.com/hook"

    def test_update_events(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/hooks/100",
            json={
                "id": 100,
                "config": {"url": "https://example.com/hook", "content_type": "json"},
                "events": ["push", "issues"],
                "active": True,
            },
            status=200,
        )
        webhook = gitea_adapter.update_webhook(100, events=["push", "issues"])
        assert "push" in webhook.events
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["events"] == ["push", "issues"]

    def test_update_active(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/hooks/100",
            json={
                "id": 100,
                "config": {"url": "https://example.com/hook", "content_type": "json"},
                "events": ["push"],
                "active": False,
            },
            status=200,
        )
        webhook = gitea_adapter.update_webhook(100, active=False)
        assert webhook.active is False


# --- DeployKey 系 ---


class TestGetDeployKey:
    def test_get(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/keys/200",
            json=_deploy_key_data(),
            status=200,
        )
        key = gitea_adapter.get_deploy_key(200)
        assert isinstance(key, DeployKey)
        assert key.id == 200
        assert key.title == "Deploy Key"

    def test_not_found(self, mock_responses, gitea_adapter):
        from gfo.exceptions import NotFoundError

        mock_responses.add(
            responses.GET,
            f"{REPOS}/keys/999",
            json={"message": "Not Found"},
            status=404,
        )
        with pytest.raises(NotFoundError):
            gitea_adapter.get_deploy_key(999)


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


class TestTriggerPipeline:
    def test_trigger_with_workflow(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/actions/workflows/ci.yml/dispatches",
            status=204,
        )
        pipeline = gitea_adapter.trigger_pipeline("main", workflow="ci.yml")
        assert pipeline.status == "pending"
        assert pipeline.ref == "main"

    def test_trigger_with_inputs(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/actions/workflows/ci.yml/dispatches",
            status=204,
        )
        pipeline = gitea_adapter.trigger_pipeline(
            "main", workflow="ci.yml", inputs={"key": "value"}
        )
        req = mock_responses.calls[0].request
        body = json.loads(req.body)
        assert body["inputs"] == {"key": "value"}
        assert pipeline.status == "pending"

    def test_trigger_without_workflow_raises(self, gitea_adapter):
        from gfo.exceptions import GfoError

        with pytest.raises(GfoError, match="--workflow"):
            gitea_adapter.trigger_pipeline("main")

    def test_trigger_404(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/actions/workflows/ci.yml/dispatches",
            status=404,
        )
        with pytest.raises(NotFoundError):
            gitea_adapter.trigger_pipeline("main", workflow="ci.yml")


class TestRetryPipeline:
    def test_retry(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/actions/runs/300/rerun",
            status=201,
        )
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
        pipeline = gitea_adapter.retry_pipeline(300)
        assert isinstance(pipeline, Pipeline)
        assert pipeline.id == 300

    def test_retry_404(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/actions/runs/999/rerun",
            status=404,
        )
        with pytest.raises(NotFoundError):
            gitea_adapter.retry_pipeline(999)


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


# --- Phase 2: PR operations ---


class TestGetPullRequestDiffGitea:
    def test_get_diff(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls/1.diff",
            body="diff --git a/file.py b/file.py\n--- a/file.py\n+++ b/file.py",
            status=200,
        )
        chunks = gitea_adapter.get_pull_request_diff(1)
        diff = b"".join(chunks)
        assert b"diff --git" in diff


class TestListPullRequestChecksGitea:
    def test_list_checks(self, mock_responses, gitea_adapter):
        pr = _pr_data()
        pr["head"]["sha"] = "abc123"
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls/1",
            json=pr,
            status=200,
        )
        mock_responses.add(
            responses.GET,
            f"{REPOS}/statuses/abc123",
            json=[
                {
                    "context": "ci/build",
                    "status": "success",
                    "target_url": "https://ci.example.com/1",
                    "created_at": "2025-01-01T00:00:00Z",
                }
            ],
            status=200,
        )
        checks = gitea_adapter.list_pull_request_checks(1)
        assert len(checks) == 1
        assert isinstance(checks[0], CheckRun)
        assert checks[0].name == "ci/build"
        assert checks[0].status == "success"


class TestListPullRequestFilesGitea:
    def test_list_files(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls/1/files",
            json=[
                {
                    "filename": "src/main.py",
                    "status": "modified",
                    "additions": 10,
                    "deletions": 3,
                }
            ],
            status=200,
        )
        files = gitea_adapter.list_pull_request_files(1)
        assert len(files) == 1
        assert isinstance(files[0], PullRequestFile)
        assert files[0].filename == "src/main.py"
        assert files[0].status == "modified"
        assert files[0].additions == 10
        assert files[0].deletions == 3


class TestListPullRequestCommitsGitea:
    def test_list_commits(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls/1/commits",
            json=[
                {
                    "sha": "abc123",
                    "commit": {
                        "message": "fix bug",
                        "author": {"name": "dev1", "date": "2025-01-01T00:00:00Z"},
                    },
                    "author": {"login": "dev1"},
                }
            ],
            status=200,
        )
        commits = gitea_adapter.list_pull_request_commits(1)
        assert len(commits) == 1
        assert isinstance(commits[0], PullRequestCommit)
        assert commits[0].sha == "abc123"
        assert commits[0].message == "fix bug"
        assert commits[0].author == "dev1"


class TestListRequestedReviewersGitea:
    def test_list_reviewers(self, mock_responses, gitea_adapter):
        pr = _pr_data()
        pr["requested_reviewers"] = [{"login": "reviewer1"}, {"login": "reviewer2"}]
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls/1",
            json=pr,
            status=200,
        )
        reviewers = gitea_adapter.list_requested_reviewers(1)
        assert reviewers == ["reviewer1", "reviewer2"]


class TestRequestReviewersGitea:
    def test_request(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/pulls/1/requested_reviewers",
            json={},
            status=201,
        )
        gitea_adapter.request_reviewers(1, ["reviewer1"])
        body = json.loads(mock_responses.calls[0].request.body)
        assert body["reviewers"] == ["reviewer1"]


class TestUpdatePullRequestBranchGitea:
    def test_update_branch(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/pulls/1/update",
            json={},
            status=200,
        )
        gitea_adapter.update_pull_request_branch(1)
        assert mock_responses.calls[0].request.method == "POST"


class TestDismissReviewGitea:
    def test_dismiss(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/pulls/1/reviews/42/dismissals",
            json={"id": 42},
            status=200,
        )
        gitea_adapter.dismiss_review(1, 42, message="stale review")
        body = json.loads(mock_responses.calls[0].request.body)
        assert body["message"] == "stale review"


class TestMarkPullRequestReadyGitea:
    def test_mark_ready(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/pulls/1",
            json=_pr_data(),
            status=200,
        )
        gitea_adapter.mark_pull_request_ready(1)
        body = json.loads(mock_responses.calls[0].request.body)
        assert body["state"] == "open"


# --- Phase 3: リポジトリ操作・リリースアセット ---


class TestUpdateRepositoryGitea:
    @responses.activate
    def test_update_description(self, gitea_adapter):
        responses.add(responses.PATCH, f"{REPOS}", json=_repo_data(), status=200)
        repo = gitea_adapter.update_repository(description="new desc")
        assert isinstance(repo, Repository)
        assert json.loads(responses.calls[0].request.body)["description"] == "new desc"

    @responses.activate
    def test_update_name(self, gitea_adapter):
        responses.add(responses.PATCH, f"{REPOS}", json=_repo_data(), status=200)
        gitea_adapter.update_repository(name="new-name")
        assert json.loads(responses.calls[0].request.body)["name"] == "new-name"

    @responses.activate
    def test_update_private(self, gitea_adapter):
        responses.add(responses.PATCH, f"{REPOS}", json=_repo_data(), status=200)
        gitea_adapter.update_repository(private=True)
        assert json.loads(responses.calls[0].request.body)["private"] is True

    @responses.activate
    def test_allow_squash_merge(self, gitea_adapter):
        responses.add(responses.PATCH, f"{REPOS}", json=_repo_data(), status=200)
        gitea_adapter.update_repository(allow_squash_merge=True)
        assert json.loads(responses.calls[0].request.body)["default_merge_style"] == "squash"

    @responses.activate
    def test_allow_rebase_merge(self, gitea_adapter):
        responses.add(responses.PATCH, f"{REPOS}", json=_repo_data(), status=200)
        gitea_adapter.update_repository(allow_rebase_merge=True)
        assert json.loads(responses.calls[0].request.body)["default_merge_style"] == "rebase"

    @responses.activate
    def test_delete_branch_on_merge(self, gitea_adapter):
        responses.add(responses.PATCH, f"{REPOS}", json=_repo_data(), status=200)
        gitea_adapter.update_repository(delete_branch_on_merge=True)
        body = json.loads(responses.calls[0].request.body)
        assert body["default_delete_branch_after_merge"] is True


class TestDisableAutoMergeGitea:
    def test_calls_delete(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/pulls/1/merge",
            status=204,
        )
        gitea_adapter.disable_auto_merge(1)
        assert mock_responses.calls[0].request.method == "DELETE"


class TestListContributorsGitea:
    def test_basic(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/contributors",
            json=[{"login": "alice", "contributions": 100}],
            status=200,
        )
        contributors = gitea_adapter.list_contributors()
        assert len(contributors) == 1
        assert contributors[0].username == "alice"
        assert contributors[0].commits == 100

    def test_api_not_found_raises(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/contributors",
            status=404,
        )
        with pytest.raises(NotSupportedError):
            gitea_adapter.list_contributors()

    def test_auth_error_propagates(self, mock_responses, gitea_adapter):
        """401 を NotSupportedError に潰さず AuthenticationError として伝播させる。"""
        from gfo.exceptions import AuthenticationError

        mock_responses.add(
            responses.GET,
            f"{REPOS}/contributors",
            json={"message": "unauthorized"},
            status=401,
        )
        with pytest.raises(AuthenticationError):
            gitea_adapter.list_contributors()

    def test_server_error_propagates(self, mock_responses, gitea_adapter):
        """5xx を NotSupportedError に潰さず ServerError として伝播させる。"""
        from gfo.exceptions import ServerError

        mock_responses.add(
            responses.GET,
            f"{REPOS}/contributors",
            json={"message": "internal"},
            status=500,
        )
        with pytest.raises(ServerError):
            gitea_adapter.list_contributors()


class TestArchiveRepositoryGitea:
    @responses.activate
    def test_archive(self, gitea_adapter):
        responses.add(responses.PATCH, f"{REPOS}", json=_repo_data(), status=200)
        gitea_adapter.archive_repository()
        assert json.loads(responses.calls[0].request.body)["archived"] is True


class TestUnarchiveRepositoryGitea:
    @responses.activate
    def test_unarchive_via_update(self, gitea_adapter):
        responses.add(responses.PATCH, f"{REPOS}", json=_repo_data(), status=200)
        gitea_adapter.update_repository(archived=False)
        assert json.loads(responses.calls[0].request.body)["archived"] is False


class TestListRepositoriesArchivedGitea:
    def test_archived_filter_true(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/user/repos",
            json=[
                {**_repo_data(name="active"), "archived": False},
                {**_repo_data(name="old"), "archived": True},
            ],
            status=200,
        )
        repos = gitea_adapter.list_repositories(archived=True)
        assert len(repos) == 1
        assert repos[0].name == "old"

    def test_archived_filter_false(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/user/repos",
            json=[
                {**_repo_data(name="active"), "archived": False},
                {**_repo_data(name="old"), "archived": True},
            ],
            status=200,
        )
        repos = gitea_adapter.list_repositories(archived=False)
        assert len(repos) == 1
        assert repos[0].name == "active"


class TestCreateRepositoryAutoInitGitea:
    @responses.activate
    def test_auto_init_true(self, gitea_adapter):
        responses.add(responses.POST, f"{BASE}/user/repos", json=_repo_data(), status=201)
        gitea_adapter.create_repository(name="test-repo", auto_init=True)
        req_body = json.loads(responses.calls[0].request.body)
        assert req_body["auto_init"] is True

    @responses.activate
    def test_auto_init_false(self, gitea_adapter):
        responses.add(responses.POST, f"{BASE}/user/repos", json=_repo_data(), status=201)
        gitea_adapter.create_repository(name="test-repo", auto_init=False)
        req_body = json.loads(responses.calls[0].request.body)
        assert "auto_init" not in req_body


class TestGetLanguagesGitea:
    @responses.activate
    def test_get_languages(self, gitea_adapter):
        responses.add(
            responses.GET, f"{REPOS}/languages", json={"Python": 45678, "Go": 1234}, status=200
        )
        result = gitea_adapter.get_languages()
        assert result == {"Python": 45678, "Go": 1234}


class TestTopicsGitea:
    @responses.activate
    def test_list_topics(self, gitea_adapter):
        responses.add(responses.GET, f"{REPOS}/topics", json={"topics": ["python"]}, status=200)
        result = gitea_adapter.list_topics()
        assert result == ["python"]

    @responses.activate
    def test_set_topics(self, gitea_adapter):
        responses.add(responses.PUT, f"{REPOS}/topics", json={"topics": ["a", "b"]}, status=200)
        result = gitea_adapter.set_topics(["a", "b"])
        assert result == ["a", "b"]

    @responses.activate
    def test_add_topic(self, gitea_adapter):
        responses.add(responses.PUT, f"{REPOS}/topics/newtopic", status=204)
        responses.add(
            responses.GET, f"{REPOS}/topics", json={"topics": ["python", "newtopic"]}, status=200
        )
        result = gitea_adapter.add_topic("newtopic")
        assert "newtopic" in result

    @responses.activate
    def test_remove_topic(self, gitea_adapter):
        responses.add(responses.DELETE, f"{REPOS}/topics/oldtopic", status=204)
        responses.add(responses.GET, f"{REPOS}/topics", json={"topics": ["python"]}, status=200)
        result = gitea_adapter.remove_topic("oldtopic")
        assert "oldtopic" not in result


class TestCompareGitea:
    @responses.activate
    def test_compare(self, gitea_adapter):
        from gfo.adapter.base import CompareResult

        responses.add(
            responses.GET,
            f"{REPOS}/compare/main...feature",
            json={
                "total_commits": 3,
                "files": [
                    {"filename": "a.py", "status": "modified", "additions": 10, "deletions": 2}
                ],
            },
            status=200,
        )
        result = gitea_adapter.compare("main", "feature")
        assert isinstance(result, CompareResult)
        assert result.total_commits == 3
        assert len(result.files) == 1


class TestGetLatestReleaseGitea:
    @responses.activate
    def test_get_latest(self, gitea_adapter):
        responses.add(responses.GET, f"{REPOS}/releases", json=[_release_data()], status=200)
        release = gitea_adapter.get_latest_release()
        assert release.tag == "v1.0.0"


class TestReleaseAssetsGitea:
    @responses.activate
    def test_list_release_assets(self, gitea_adapter):
        responses.add(
            responses.GET,
            f"{REPOS}/releases/tags/v1.0.0",
            json={
                **_release_data(),
                "assets": [
                    {
                        "id": 1,
                        "name": "app.zip",
                        "size": 1024,
                        "browser_download_url": "https://example.com/app.zip",
                        "created_at": "2025-01-01T00:00:00Z",
                    }
                ],
            },
            status=200,
        )
        assets = gitea_adapter.list_release_assets(tag="v1.0.0")
        assert len(assets) == 1
        assert assets[0].name == "app.zip"

    @responses.activate
    def test_delete_release_asset(self, gitea_adapter):
        responses.add(
            responses.GET,
            f"{REPOS}/releases/tags/v1.0.0",
            json={**_release_data(), "id": 42},
            status=200,
        )
        responses.add(responses.DELETE, f"{REPOS}/releases/42/assets/1", status=204)
        gitea_adapter.delete_release_asset(tag="v1.0.0", asset_id=1)


class TestUpdateReleaseAsset:
    def test_update_name(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/releases/tags/v1.0.0",
            json={
                "id": 42,
                "tag_name": "v1.0.0",
                "name": "v1.0.0",
                "body": "",
                "draft": False,
                "prerelease": False,
                "created_at": "2025-01-01T00:00:00Z",
            },
            status=200,
        )
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/releases/42/assets/1",
            json={
                "id": 1,
                "name": "renamed.zip",
                "size": 1024,
                "browser_download_url": "https://gitea.example.com/renamed.zip",
                "created_at": "2025-01-01T00:00:00Z",
            },
            status=200,
        )
        asset = gitea_adapter.update_release_asset(tag="v1.0.0", asset_id=1, name="renamed.zip")
        assert asset.name == "renamed.zip"

    def test_not_found(self, mock_responses, gitea_adapter):
        from gfo.exceptions import NotFoundError

        mock_responses.add(
            responses.GET,
            f"{REPOS}/releases/tags/v1.0.0",
            json={"message": "Not Found"},
            status=404,
        )
        with pytest.raises(NotFoundError):
            gitea_adapter.update_release_asset(tag="v1.0.0", asset_id=999, name="x.zip")


class TestListIssueTemplatesGitea:
    @responses.activate
    def test_list_templates(self, gitea_adapter):
        responses.add(
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
                {
                    "name": "Feature Request",
                    "title": "[Feature]: ",
                    "body": "## Feature\n...",
                    "about": "Request a feature",
                    "labels": ["enhancement"],
                },
            ],
            status=200,
        )
        templates = gitea_adapter.list_issue_templates()
        assert len(templates) == 2
        assert templates[0].name == "Bug Report"
        assert templates[0].title == "[Bug]: "
        assert templates[0].body == "## Description\n..."
        assert templates[0].about == "Report a bug"
        assert templates[0].labels == ("bug",)
        # 2番目: content がないので body フォールバック
        assert templates[1].body == "## Feature\n..."

    @responses.activate
    def test_empty_list(self, gitea_adapter):
        responses.add(
            responses.GET,
            f"{REPOS}/issue_templates",
            json=[],
            status=200,
        )
        templates = gitea_adapter.list_issue_templates()
        assert templates == []

    @responses.activate
    def test_not_found(self, gitea_adapter):
        responses.add(
            responses.GET,
            f"{REPOS}/issue_templates",
            json={"message": "Not Found"},
            status=404,
        )
        templates = gitea_adapter.list_issue_templates()
        assert templates == []


class TestMigrateRepository:
    @responses.activate
    def test_migrate(self, gitea_adapter):
        responses.add(
            responses.POST,
            f"{BASE}/repos/migrate",
            json=_repo_data(name="migrated", full_name="test-owner/migrated"),
            status=201,
        )
        repo = gitea_adapter.migrate_repository("https://github.com/old/repo.git", "migrated")
        assert repo.name == "migrated"

    @responses.activate
    def test_migrate_with_options(self, gitea_adapter):
        responses.add(
            responses.POST,
            f"{BASE}/repos/migrate",
            json=_repo_data(name="migrated", full_name="test-owner/migrated"),
            status=201,
        )
        repo = gitea_adapter.migrate_repository(
            "https://github.com/old/repo.git",
            "migrated",
            visibility="private",
            mirror=True,
            description="desc",
            auth_token="tok",
        )
        assert repo.name == "migrated"
        import json as json_mod

        body = json_mod.loads(responses.calls[0].request.body)
        assert body["private"] is True
        assert body["mirror"] is True
        assert body["description"] == "desc"
        assert body["auth_token"] == "tok"
        assert body["repo_owner"] == "test-owner"

    @responses.activate
    def test_migrate_org_repo(self, gitea_adapter):
        """組織にリポジトリを migrate する。"""
        responses.add(
            responses.POST,
            f"{BASE}/repos/migrate",
            json=_repo_data(full_name="my-org/migrated"),
            status=201,
        )
        gitea_adapter.migrate_repository(
            "https://other.com/repo.git", "migrated", organization="my-org"
        )
        import json as json_mod

        req_body = json_mod.loads(responses.calls[0].request.body)
        assert req_body["repo_owner"] == "my-org"


# ── C-01: download_release_asset パストラバーサル防止 ──


class TestDownloadReleaseAssetPathTraversal:
    @responses.activate
    def test_traversal_name_sanitized(self, gitea_adapter, tmp_path):
        """アセット名に ../ を含む場合に basename でサニタイズされることを検証する。"""
        responses.add(
            responses.GET,
            f"{REPOS}/releases/tags/v1.0.0",
            json={"id": 1, "tag_name": "v1.0.0"},
        )
        responses.add(
            responses.GET,
            f"{REPOS}/releases/1/assets/1",
            json={
                "name": "../malicious.bin",
                "id": 1,
                "browser_download_url": f"{REPOS}/releases/1/assets/1",
            },
        )
        responses.add(
            responses.GET,
            f"{REPOS}/releases/1/assets/1",
            body=b"content",
        )
        result = gitea_adapter.download_release_asset(
            tag="v1.0.0", asset_id=1, output_dir=str(tmp_path)
        )
        import os

        assert os.path.basename(result) == "malicious.bin"
        assert os.path.dirname(os.path.realpath(result)) == os.path.realpath(str(tmp_path))


class TestUpdateOrganization:
    def test_update_display_name(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.PATCH,
            "https://gitea.example.com/api/v1/orgs/my-org",
            json={
                "username": "my-org",
                "full_name": "New Name",
                "description": "desc",
            },
            status=200,
        )
        org = gitea_adapter.update_organization("my-org", display_name="New Name")
        assert org.display_name == "New Name"
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["full_name"] == "New Name"

    def test_update_description(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.PATCH,
            "https://gitea.example.com/api/v1/orgs/my-org",
            json={
                "username": "my-org",
                "full_name": "My Org",
                "description": "New description",
            },
            status=200,
        )
        org = gitea_adapter.update_organization("my-org", description="New description")
        assert org.description == "New description"


# --- Workflow ---


class TestListWorkflows:
    def test_list(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/actions/workflows",
            json={
                "workflows": [
                    {"id": 1, "name": "CI", "path": ".gitea/workflows/ci.yml", "state": "active"}
                ]
            },
            status=200,
        )
        from gfo.adapter.base import Workflow

        workflows = gitea_adapter.list_workflows()
        assert len(workflows) == 1
        assert isinstance(workflows[0], Workflow)
        assert workflows[0].name == "CI"

    def test_disabled_fork_state_preserved(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/actions/workflows",
            json={
                "workflows": [
                    {
                        "id": 1,
                        "name": "CI",
                        "path": ".gitea/workflows/ci.yml",
                        "state": "disabled_fork",
                    }
                ]
            },
            status=200,
        )
        workflows = gitea_adapter.list_workflows()
        assert workflows[0].state == "disabled_fork"

    def test_empty(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/actions/workflows",
            json={"workflows": []},
            status=200,
        )
        assert gitea_adapter.list_workflows() == []


class TestEnableWorkflow:
    def test_enable(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.PUT,
            f"{REPOS}/actions/workflows/1/enable",
            status=204,
        )
        gitea_adapter.enable_workflow(1)
        assert mock_responses.calls[0].request.method == "PUT"

    def test_not_found(self, mock_responses, gitea_adapter):
        from gfo.exceptions import NotFoundError

        mock_responses.add(
            responses.PUT,
            f"{REPOS}/actions/workflows/999/enable",
            status=404,
        )
        with pytest.raises(NotFoundError):
            gitea_adapter.enable_workflow("999")


class TestDisableWorkflow:
    def test_disable(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.PUT,
            f"{REPOS}/actions/workflows/1/disable",
            status=204,
        )
        gitea_adapter.disable_workflow(1)
        assert mock_responses.calls[0].request.method == "PUT"

    def test_not_found(self, mock_responses, gitea_adapter):
        from gfo.exceptions import NotFoundError

        mock_responses.add(
            responses.PUT,
            f"{REPOS}/actions/workflows/999/disable",
            status=404,
        )
        with pytest.raises(NotFoundError):
            gitea_adapter.disable_workflow("999")


# --- Artifact ---


class TestListArtifacts:
    def test_list(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/actions/runs/300/artifacts",
            json=[
                {
                    "id": 11,
                    "name": "build-output",
                    "size": 1024,
                    "url": "",
                    "created_at": "2025-01-01T00:00:00Z",
                }
            ],
            status=200,
        )
        from gfo.adapter.base import Artifact

        artifacts = gitea_adapter.list_artifacts(300)
        assert len(artifacts) == 1
        assert isinstance(artifacts[0], Artifact)
        assert artifacts[0].name == "build-output"


class TestDownloadArtifact:
    def test_download(self, mock_responses, gitea_adapter, tmp_path):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/actions/artifacts/11",
            json={"id": 11, "name": "build-output"},
            status=200,
        )
        mock_responses.add(
            responses.GET,
            f"{REPOS}/actions/artifacts/11/zip",
            body=b"PK\x03\x04zipdata",
            status=200,
        )
        result = gitea_adapter.download_artifact(300, 11, output_dir=str(tmp_path))
        import os

        assert os.path.basename(result) == "build-output.zip"
        assert os.path.exists(result)

    def test_not_found(self, mock_responses, gitea_adapter):
        from gfo.exceptions import NotFoundError

        mock_responses.add(
            responses.GET,
            f"{REPOS}/actions/artifacts/999",
            status=404,
        )
        with pytest.raises(NotFoundError):
            gitea_adapter.download_artifact("100", "999", output_dir="/tmp")


class TestDownloadRunLogs:
    def test_download(self, mock_responses, gitea_adapter, tmp_path):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/actions/runs/300/logs",
            body=b"PK\x03\x04logdata",
            status=200,
        )
        result = gitea_adapter.download_run_logs(300, output_dir=str(tmp_path))
        import os

        assert os.path.basename(result) == "logs-300.zip"
        assert os.path.exists(result)


class TestIssueSubscribe:
    def test_subscribe_issue(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/user",
            json={"login": "testuser"},
            status=200,
        )
        mock_responses.add(
            responses.PUT,
            f"{REPOS}/issues/1/subscriptions/testuser",
            status=204,
        )
        gitea_adapter.subscribe_issue(1)

    def test_unsubscribe_issue(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/user",
            json={"login": "testuser"},
            status=200,
        )
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/issues/1/subscriptions/testuser",
            status=204,
        )
        gitea_adapter.unsubscribe_issue(1)

    def test_subscribe_404(self, mock_responses, gitea_adapter):
        from gfo.exceptions import NotFoundError

        mock_responses.add(
            responses.GET,
            f"{BASE}/user",
            json={"login": "testuser"},
            status=200,
        )
        mock_responses.add(
            responses.PUT,
            f"{REPOS}/issues/999/subscriptions/testuser",
            json={"message": "Not Found"},
            status=404,
        )
        with pytest.raises(NotFoundError):
            gitea_adapter.subscribe_issue(999)


class TestOrgSecrets:
    def test_list_org_secrets(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/orgs/test-org/actions/secrets",
            json=[{"name": "ORG_SECRET", "created_at": "2024-01-01"}],
            status=200,
        )
        secrets = gitea_adapter.list_secrets(scope="test-org")
        assert len(secrets) == 1
        assert secrets[0].name == "ORG_SECRET"

    def test_delete_org_secret(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{BASE}/orgs/test-org/actions/secrets/ORG_SECRET",
            status=204,
        )
        gitea_adapter.delete_secret("ORG_SECRET", scope="test-org")


class TestOrgVariables:
    def test_list_org_variables(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/orgs/test-org/actions/variables",
            json=[{"name": "ORG_VAR", "value": "val"}],
            status=200,
        )
        variables = gitea_adapter.list_variables(scope="test-org")
        assert len(variables) == 1
        assert variables[0].name == "ORG_VAR"

    def test_delete_org_variable(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{BASE}/orgs/test-org/actions/variables/ORG_VAR",
            status=204,
        )
        gitea_adapter.delete_variable("ORG_VAR", scope="test-org")


class TestClientFilterLimit:
    """クライアント側フィルタ + limit が正しく動作するテスト。"""

    def test_repo_archived_with_limit(self, mock_responses, gitea_adapter):
        """repo archived=False + limit=1: 先頭が archived=True → スキップして2件目を返す。"""
        mock_responses.add(
            responses.GET,
            f"{BASE}/user/repos",
            json=[
                {**_repo_data(name="archived-repo"), "archived": True},
                {**_repo_data(name="active-repo"), "archived": False},
                {**_repo_data(name="active-repo2"), "archived": False},
            ],
            status=200,
        )
        result = gitea_adapter.list_repositories(archived=False, limit=1)
        assert len(result) == 1
        assert result[0].name == "active-repo"


# --- Packages ---


class TestPackagesGitea:
    """Gitea の list_packages / get_package / delete_package。"""

    def test_list_packages_basic(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/packages/test-owner",
            json=[
                {
                    "name": "mypkg",
                    "type": "container",
                    "version": "1.0",
                    "owner": {"login": "test-owner"},
                    "html_url": f"{BASE.replace('/api/v1', '')}/test-owner/-/packages/container/mypkg/1.0",
                    "created_at": "2025-01-01T00:00:00Z",
                }
            ],
            status=200,
        )
        pkgs = gitea_adapter.list_packages()
        assert len(pkgs) == 1
        assert pkgs[0].name == "mypkg"
        assert pkgs[0].type == "container"
        assert pkgs[0].version == "1.0"

    def test_list_packages_filtered_by_type(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/packages/test-owner",
            json=[],
            status=200,
        )
        gitea_adapter.list_packages(package_type="npm")
        sent = mock_responses.calls[0].request
        assert "type=npm" in sent.url

    def test_list_packages_empty(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/packages/test-owner",
            json=[],
            status=200,
        )
        assert gitea_adapter.list_packages() == []

    def test_get_package_with_version(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/packages/test-owner/container/mypkg/1.0",
            json={
                "name": "mypkg",
                "type": "container",
                "version": "1.0",
                "html_url": "x",
                "created_at": "2025-01-01T00:00:00Z",
            },
            status=200,
        )
        p = gitea_adapter.get_package("container", "mypkg", version="1.0")
        assert p.name == "mypkg"
        assert p.version == "1.0"

    def test_get_package_not_found(self, mock_responses, gitea_adapter):
        from gfo.exceptions import NotFoundError

        mock_responses.add(
            responses.GET,
            f"{BASE}/packages/test-owner/container/missing/1.0",
            status=404,
        )
        with pytest.raises(NotFoundError):
            gitea_adapter.get_package("container", "missing", version="1.0")

    def test_get_package_without_version_uses_list(self, mock_responses, gitea_adapter):
        """version 未指定時は list から最初の一致を返す。"""
        mock_responses.add(
            responses.GET,
            f"{BASE}/packages/test-owner",
            json=[
                {
                    "name": "mypkg",
                    "type": "container",
                    "version": "2.0",
                    "html_url": "x",
                    "created_at": "2025-01-01T00:00:00Z",
                }
            ],
            status=200,
        )
        p = gitea_adapter.get_package("container", "mypkg")
        assert p.version == "2.0"

    def test_get_package_without_version_empty_raises(self, mock_responses, gitea_adapter):
        from gfo.exceptions import NotFoundError

        mock_responses.add(
            responses.GET,
            f"{BASE}/packages/test-owner",
            json=[],
            status=200,
        )
        with pytest.raises(NotFoundError):
            gitea_adapter.get_package("container", "missing")

    def test_delete_package(self, mock_responses, gitea_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{BASE}/packages/test-owner/container/mypkg/1.0",
            status=204,
        )
        gitea_adapter.delete_package("container", "mypkg", "1.0")
        assert mock_responses.calls[0].request.method == "DELETE"


class TestReleaseAssetsUploadDownloadGitea:
    """Gitea の upload_release_asset / download_release_asset 多段フロー。"""

    def test_upload_release_asset(self, mock_responses, gitea_adapter, tmp_path):
        """tags → release_id → upload の 2 段フローを検証。"""
        # Step 1: タグから release_id を取得
        mock_responses.add(
            responses.GET,
            f"{REPOS}/releases/tags/v1.0",
            json={"id": 42, "tag_name": "v1.0"},
            status=200,
        )
        # Step 2: multipart で attachment アップロード
        mock_responses.add(
            responses.POST,
            f"{REPOS}/releases/42/assets",
            json={
                "id": 100,
                "name": "app.zip",
                "size": 0,
                "browser_download_url": "https://x/y",
                "created_at": "2025-01-01T00:00:00Z",
            },
            status=201,
        )
        f = tmp_path / "app.zip"
        f.write_bytes(b"binary")
        asset = gitea_adapter.upload_release_asset(tag="v1.0", file_path=str(f))
        assert asset.id == 100
        assert asset.name == "app.zip"

    def test_download_release_asset(self, mock_responses, gitea_adapter, tmp_path):
        """tags → release_id → meta → download の 3 段フローを検証。

        実装はメタの browser_download_url を優先し、無ければ
        {base}/releases/{release_id}/assets/{asset_id} を URL として組み立てる。
        """
        mock_responses.add(
            responses.GET,
            f"{REPOS}/releases/tags/v1.0",
            json={"id": 42},
            status=200,
        )
        # 2 回目: メタ取得（同じ URL を 3 回目でダウンロードに再利用）
        mock_responses.add(
            responses.GET,
            f"{REPOS}/releases/42/assets/7",
            json={"name": "app.zip"},
            status=200,
        )
        # 3 回目: ダウンロード（同じ URL を `responses` は順次消費する）
        mock_responses.add(
            responses.GET,
            f"{REPOS}/releases/42/assets/7",
            body=b"PK\x03\x04",
            status=200,
        )
        result = gitea_adapter.download_release_asset(
            tag="v1.0", asset_id=7, output_dir=str(tmp_path)
        )
        import os

        assert os.path.basename(result) == "app.zip"
        assert os.path.exists(result)

    def test_upload_release_asset_tag_not_found(self, mock_responses, gitea_adapter, tmp_path):
        """タグが見つからない場合は NotFoundError。"""
        from gfo.exceptions import NotFoundError

        mock_responses.add(
            responses.GET,
            f"{REPOS}/releases/tags/missing",
            status=404,
        )
        f = tmp_path / "app.zip"
        f.write_bytes(b"x")
        with pytest.raises(NotFoundError):
            gitea_adapter.upload_release_asset(tag="missing", file_path=str(f))
