"""BacklogAdapter のテスト。"""

from __future__ import annotations

import json

import pytest
import responses

from gfo.adapter.backlog import BacklogAdapter
from gfo.adapter.base import Issue, PullRequest, Repository
from gfo.adapter.registry import get_adapter_class
from gfo.exceptions import AuthenticationError, NotFoundError, NotSupportedError, ServerError


BASE = "https://example.backlog.com/api/v2"
PR_PATH = f"{BASE}/projects/TEST/git/repositories/test-repo/pullRequests"
ISSUES_PATH = f"{BASE}/issues"


# --- サンプルデータ ---

def _pr_data(*, number=1, status_id=1):
    return {
        "number": number,
        "summary": f"PR #{number}",
        "description": "pr description",
        "status": {"id": status_id, "name": "Open"},
        "createdUser": {"userId": "author", "name": "Author"},
        "branch": "feature",
        "base": "main",
        "url": f"{BASE}/projects/TEST/git/repositories/test-repo/pullRequests/{number}",
        "created": "2025-01-01T00:00:00Z",
        "updated": "2025-01-02T00:00:00Z",
    }


def _issue_data(*, id=1, issue_key="TEST-1", status_id=1):
    return {
        "id": id,
        "issueKey": issue_key,
        "summary": f"Issue #{id}",
        "description": "issue body",
        "status": {"id": status_id, "name": "Open"},
        "createdUser": {"userId": "creator", "name": "Creator"},
        "assignee": {"userId": "dev", "name": "Dev"},
        "url": f"{BASE}/issues/{id}",
        "created": "2025-01-01T00:00:00Z",
    }


def _repo_data(*, name="test-repo"):
    return {
        "name": name,
        "displayName": f"TEST/{name}",
        "description": "a test repo",
        "httpUrl": f"https://example.backlog.com/git/TEST/{name}.git",
    }


# --- 変換ヘルパーのテスト ---

class TestToPullRequest:
    def test_open(self):
        pr = BacklogAdapter._to_pull_request(_pr_data(status_id=1))
        assert pr.state == "open"
        assert pr.number == 1
        assert pr.title == "PR #1"
        assert pr.author == "author"
        assert pr.source_branch == "feature"
        assert pr.target_branch == "main"
        assert pr.draft is False

    def test_processing(self):
        pr = BacklogAdapter._to_pull_request(_pr_data(status_id=2))
        assert pr.state == "open"

    def test_closed(self):
        pr = BacklogAdapter._to_pull_request(_pr_data(status_id=4))
        assert pr.state == "closed"

    def test_merged(self):
        pr = BacklogAdapter._to_pull_request(_pr_data(status_id=5))
        assert pr.state == "merged"

    def test_body_none(self):
        data = _pr_data()
        data.pop("description")
        pr = BacklogAdapter._to_pull_request(data)
        assert pr.body is None


class TestToIssue:
    def test_open(self):
        issue = BacklogAdapter._to_issue(_issue_data(status_id=1))
        assert issue.state == "open"
        assert issue.title == "Issue #1"
        assert issue.author == "creator"
        assert issue.assignees == ["dev"]
        assert issue.body == "issue body"

    def test_closed(self):
        issue = BacklogAdapter._to_issue(_issue_data(status_id=4))
        assert issue.state == "closed"

    def test_no_assignee(self):
        data = _issue_data()
        data["assignee"] = None
        issue = BacklogAdapter._to_issue(data)
        assert issue.assignees == []

    def test_issue_number_from_key(self):
        issue = BacklogAdapter._to_issue(_issue_data(issue_key="TEST-42"))
        assert issue.number == 42

    def test_issue_key_without_hyphen_falls_back_to_id(self):
        """issueKey に '-' がない場合、id にフォールバックする。"""
        data = _issue_data(issue_key="INVALID")
        issue = BacklogAdapter._to_issue(data)
        assert issue.number == data["id"]

    def test_empty_assignee_object(self):
        """assignee が空オブジェクトの場合、assignees は空リストになる。"""
        data = _issue_data()
        data["assignee"] = {}
        issue = BacklogAdapter._to_issue(data)
        assert issue.assignees == []


class TestToRepository:
    def test_basic(self):
        repo = BacklogAdapter._to_repository(_repo_data())
        assert repo.name == "test-repo"
        assert repo.full_name == "TEST/test-repo"
        assert repo.private is True
        assert "test-repo" in repo.clone_url


# --- PR 系 ---

class TestListPullRequests:
    def test_open(self, mock_responses, backlog_adapter):
        mock_responses.add(
            responses.GET, PR_PATH,
            json=[_pr_data()], status=200,
        )
        prs = backlog_adapter.list_pull_requests()
        assert len(prs) == 1
        assert prs[0].state == "open"
        req = mock_responses.calls[0].request
        assert "statusId" in req.url

    def test_closed(self, mock_responses, backlog_adapter):
        mock_responses.add(
            responses.GET, PR_PATH,
            json=[_pr_data(status_id=4)], status=200,
        )
        prs = backlog_adapter.list_pull_requests(state="closed")
        assert prs[0].state == "closed"

    def test_merged(self, mock_responses, backlog_adapter):
        mock_responses.add(
            responses.GET, f"{BASE}/projects/TEST/statuses",
            json=[{"id": 5, "name": "Merged"}], status=200,
        )
        mock_responses.add(
            responses.GET, PR_PATH,
            json=[_pr_data(status_id=5)], status=200,
        )
        prs = backlog_adapter.list_pull_requests(state="merged")
        assert prs[0].state == "merged"

    def test_all(self, mock_responses, backlog_adapter):
        mock_responses.add(
            responses.GET, f"{BASE}/projects/TEST/statuses",
            json=[{"id": 5, "name": "Merged"}], status=200,
        )
        mock_responses.add(
            responses.GET, PR_PATH,
            json=[_pr_data()], status=200,
        )
        prs = backlog_adapter.list_pull_requests(state="all")
        assert len(prs) == 1
        req = mock_responses.calls[1].request
        assert "statusId" not in req.url

    def test_merged_no_status(self, mock_responses, backlog_adapter):
        """merged ステータスが見つからない場合はフィルタなしで取得。"""
        mock_responses.add(
            responses.GET, f"{BASE}/projects/TEST/statuses",
            json=[{"id": 1, "name": "Open"}], status=200,
        )
        mock_responses.add(
            responses.GET, PR_PATH,
            json=[], status=200,
        )
        prs = backlog_adapter.list_pull_requests(state="merged")
        assert prs == []

    def test_pagination(self, mock_responses, backlog_adapter):
        """offset ベースのページネーションで2ページ取得。"""
        mock_responses.add(
            responses.GET, f"{BASE}/projects/TEST/statuses",
            json=[{"id": 5, "name": "Merged"}], status=200,
        )
        mock_responses.add(
            responses.GET, PR_PATH,
            json=[_pr_data(number=i) for i in range(1, 21)], status=200,
        )
        mock_responses.add(
            responses.GET, PR_PATH,
            json=[_pr_data(number=21)], status=200,
        )
        prs = backlog_adapter.list_pull_requests(state="all", limit=0)
        assert len(prs) == 21
        req1 = mock_responses.calls[1].request
        req2 = mock_responses.calls[2].request
        assert "count=20" in req1.url
        assert "offset=0" in req1.url
        assert "offset=20" in req2.url


class TestCreatePullRequest:
    def test_create(self, mock_responses, backlog_adapter):
        mock_responses.add(
            responses.POST, PR_PATH,
            json=_pr_data(), status=201,
        )
        mock_responses.add(
            responses.GET, f"{BASE}/projects/TEST/statuses",
            json=[{"id": 5, "name": "Merged"}], status=200,
        )
        pr = backlog_adapter.create_pull_request(
            title="PR #1", body="desc", base="main", head="feature",
        )
        assert isinstance(pr, PullRequest)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["summary"] == "PR #1"
        assert req_body["base"] == "main"
        assert req_body["branch"] == "feature"


class TestGetPullRequest:
    def test_get(self, mock_responses, backlog_adapter):
        mock_responses.add(
            responses.GET, f"{BASE}/projects/TEST/statuses",
            json=[{"id": 5, "name": "Merged"}], status=200,
        )
        mock_responses.add(
            responses.GET, f"{PR_PATH}/42",
            json=_pr_data(number=42), status=200,
        )
        pr = backlog_adapter.get_pull_request(42)
        assert pr.number == 42


class TestMergePullRequest:
    def test_not_supported(self, backlog_adapter):
        with pytest.raises(NotSupportedError) as exc_info:
            backlog_adapter.merge_pull_request(1)
        err = exc_info.value
        assert err.web_url is not None
        assert "pullRequests/1" in err.web_url


class TestClosePullRequest:
    def test_close(self, mock_responses, backlog_adapter):
        mock_responses.add(
            responses.PATCH, f"{PR_PATH}/1",
            json=_pr_data(status_id=4), status=200,
        )
        backlog_adapter.close_pull_request(1)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["statusId"] == 4


class TestCheckoutRefspec:
    def test_with_pr(self, backlog_adapter):
        data = _pr_data()
        pr = BacklogAdapter._to_pull_request(data)
        refspec = backlog_adapter.get_pr_checkout_refspec(1, pr=pr)
        assert refspec == "feature"

    def test_without_pr(self, mock_responses, backlog_adapter):
        mock_responses.add(
            responses.GET, f"{BASE}/projects/TEST/statuses",
            json=[{"id": 5, "name": "Merged"}], status=200,
        )
        mock_responses.add(
            responses.GET, f"{PR_PATH}/1",
            json=_pr_data(), status=200,
        )
        refspec = backlog_adapter.get_pr_checkout_refspec(1)
        assert refspec == "feature"


# --- Issue 系 ---

class TestListIssues:
    def test_open(self, mock_responses, backlog_adapter):
        mock_responses.add(
            responses.GET, f"{BASE}/projects/TEST",
            json={"id": 100, "projectKey": "TEST"}, status=200,
        )
        mock_responses.add(
            responses.GET, ISSUES_PATH,
            json=[_issue_data()], status=200,
        )
        issues = backlog_adapter.list_issues()
        assert len(issues) == 1
        assert issues[0].state == "open"

    def test_closed(self, mock_responses, backlog_adapter):
        mock_responses.add(
            responses.GET, f"{BASE}/projects/TEST",
            json={"id": 100, "projectKey": "TEST"}, status=200,
        )
        mock_responses.add(
            responses.GET, ISSUES_PATH,
            json=[_issue_data(status_id=4)], status=200,
        )
        issues = backlog_adapter.list_issues(state="closed")
        assert issues[0].state == "closed"

    def test_all(self, mock_responses, backlog_adapter):
        mock_responses.add(
            responses.GET, f"{BASE}/projects/TEST",
            json={"id": 100, "projectKey": "TEST"}, status=200,
        )
        mock_responses.add(
            responses.GET, ISSUES_PATH,
            json=[_issue_data()], status=200,
        )
        issues = backlog_adapter.list_issues(state="all")
        req = mock_responses.calls[1].request
        assert "statusId" not in req.url

    def test_assignee_filter(self, mock_responses, backlog_adapter):
        """assignee を指定すると assigneeUserId[] パラメータが追加される。"""
        mock_responses.add(
            responses.GET, f"{BASE}/projects/TEST",
            json={"id": 100, "projectKey": "TEST"}, status=200,
        )
        mock_responses.add(
            responses.GET, ISSUES_PATH,
            json=[_issue_data()], status=200,
        )
        backlog_adapter.list_issues(assignee="12345")
        req = mock_responses.calls[1].request
        assert "assigneeUserId" in req.url
        assert "12345" in req.url

    def test_label_filter(self, mock_responses, backlog_adapter):
        """label を指定すると keyword パラメータが追加される。"""
        mock_responses.add(
            responses.GET, f"{BASE}/projects/TEST",
            json={"id": 100, "projectKey": "TEST"}, status=200,
        )
        mock_responses.add(
            responses.GET, ISSUES_PATH,
            json=[_issue_data()], status=200,
        )
        backlog_adapter.list_issues(label="bug")
        req = mock_responses.calls[1].request
        assert "keyword" in req.url
        assert "bug" in req.url

    def test_project_id_cached(self, mock_responses, backlog_adapter):
        """project_id は2回目以降キャッシュされる。"""
        mock_responses.add(
            responses.GET, f"{BASE}/projects/TEST",
            json={"id": 100, "projectKey": "TEST"}, status=200,
        )
        mock_responses.add(
            responses.GET, ISSUES_PATH,
            json=[], status=200,
        )
        mock_responses.add(
            responses.GET, ISSUES_PATH,
            json=[], status=200,
        )
        backlog_adapter.list_issues()
        backlog_adapter.list_issues()
        # /projects/TEST は1回だけ呼ばれるはず
        project_calls = [c for c in mock_responses.calls if "/projects/TEST" in c.request.url and "issues" not in c.request.url and "statuses" not in c.request.url]
        assert len(project_calls) == 1


class TestCreateIssue:
    def test_create_with_auto_type_and_priority(self, mock_responses, backlog_adapter):
        mock_responses.add(
            responses.GET, f"{BASE}/projects/TEST",
            json={"id": 100, "projectKey": "TEST"}, status=200,
        )
        mock_responses.add(
            responses.GET, f"{BASE}/projects/TEST/issueTypes",
            json=[{"id": 2, "name": "Task"}], status=200,
        )
        mock_responses.add(
            responses.GET, f"{BASE}/priorities",
            json=[{"id": 3, "name": "中"}], status=200,
        )
        mock_responses.add(
            responses.POST, ISSUES_PATH,
            json=_issue_data(), status=201,
        )
        issue = backlog_adapter.create_issue(title="Issue #1", body="body")
        assert isinstance(issue, Issue)
        req_body = json.loads(mock_responses.calls[3].request.body)
        assert req_body["summary"] == "Issue #1"
        assert req_body["issueTypeId"] == 2
        assert req_body["priorityId"] == 3

    def test_create_with_explicit_type_and_priority(self, mock_responses, backlog_adapter):
        mock_responses.add(
            responses.GET, f"{BASE}/projects/TEST",
            json={"id": 100, "projectKey": "TEST"}, status=200,
        )
        mock_responses.add(
            responses.POST, ISSUES_PATH,
            json=_issue_data(), status=201,
        )
        issue = backlog_adapter.create_issue(title="Issue #1", issue_type=2, priority=3)
        assert isinstance(issue, Issue)
        # issueTypes と priorities は取得されない
        assert len(mock_responses.calls) == 2

    def test_create_normal_priority_fallback(self, mock_responses, backlog_adapter):
        """'Normal' という英語名でも中/Normal が選ばれる。"""
        mock_responses.add(
            responses.GET, f"{BASE}/projects/TEST",
            json={"id": 100, "projectKey": "TEST"}, status=200,
        )
        mock_responses.add(
            responses.GET, f"{BASE}/projects/TEST/issueTypes",
            json=[{"id": 2, "name": "Task"}], status=200,
        )
        mock_responses.add(
            responses.GET, f"{BASE}/priorities",
            json=[{"id": 1, "name": "High"}, {"id": 3, "name": "Normal"}, {"id": 5, "name": "Low"}],
            status=200,
        )
        mock_responses.add(
            responses.POST, ISSUES_PATH,
            json=_issue_data(), status=201,
        )
        backlog_adapter.create_issue(title="Issue")
        req_body = json.loads(mock_responses.calls[3].request.body)
        assert req_body["priorityId"] == 3

    def test_create_raises_when_no_issue_types(self, mock_responses, backlog_adapter):
        """issueTypes が空のとき GfoError を送出する。"""
        from gfo.exceptions import GfoError
        mock_responses.add(
            responses.GET, f"{BASE}/projects/TEST",
            json={"id": 100, "projectKey": "TEST"}, status=200,
        )
        mock_responses.add(
            responses.GET, f"{BASE}/projects/TEST/issueTypes",
            json=[], status=200,
        )
        mock_responses.add(
            responses.GET, f"{BASE}/priorities",
            json=[{"id": 3, "name": "中"}], status=200,
        )
        with pytest.raises(GfoError, match="no issue types"):
            backlog_adapter.create_issue(title="Issue")

    def test_create_raises_when_no_priorities(self, mock_responses, backlog_adapter):
        """priorities が空のとき GfoError を送出する。"""
        from gfo.exceptions import GfoError
        mock_responses.add(
            responses.GET, f"{BASE}/projects/TEST",
            json={"id": 100, "projectKey": "TEST"}, status=200,
        )
        mock_responses.add(
            responses.GET, f"{BASE}/projects/TEST/issueTypes",
            json=[{"id": 2, "name": "Task"}], status=200,
        )
        mock_responses.add(
            responses.GET, f"{BASE}/priorities",
            json=[], status=200,
        )
        with pytest.raises(GfoError, match="no priorities"):
            backlog_adapter.create_issue(title="Issue")

    def test_create_with_assignee(self, mock_responses, backlog_adapter):
        """assignee を渡すと assigneeUserId がペイロードに含まれる。"""
        mock_responses.add(
            responses.GET, f"{BASE}/projects/TEST",
            json={"id": 100, "projectKey": "TEST"}, status=200,
        )
        mock_responses.add(
            responses.POST, ISSUES_PATH,
            json=_issue_data(), status=201,
        )
        backlog_adapter.create_issue(title="Issue", issue_type=2, priority=3, assignee="alice")
        req_body = json.loads(mock_responses.calls[1].request.body)
        assert req_body["assigneeUserId"] == "alice"


class TestGetIssue:
    def test_get(self, mock_responses, backlog_adapter):
        mock_responses.add(
            responses.GET, f"{ISSUES_PATH}/TEST-5",
            json=_issue_data(id=5, issue_key="TEST-5"), status=200,
        )
        issue = backlog_adapter.get_issue(5)
        assert issue.title == "Issue #5"


class TestCloseIssue:
    def test_close(self, mock_responses, backlog_adapter):
        mock_responses.add(
            responses.PATCH, f"{BASE}/issues/TEST-3",
            json=_issue_data(id=3, status_id=4), status=200,
        )
        backlog_adapter.close_issue(3)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["statusId"] == 4


# --- Repository 系 ---

class TestListRepositories:
    def test_list(self, mock_responses, backlog_adapter):
        mock_responses.add(
            responses.GET, f"{BASE}/projects/TEST/git/repositories",
            json=[_repo_data()], status=200,
        )
        repos = backlog_adapter.list_repositories()
        assert len(repos) == 1
        assert isinstance(repos[0], Repository)


class TestCreateRepository:
    def test_create(self, mock_responses, backlog_adapter):
        mock_responses.add(
            responses.POST, f"{BASE}/projects/TEST/git/repositories",
            json=_repo_data(name="new-repo"), status=201,
        )
        repo = backlog_adapter.create_repository(name="new-repo")
        assert isinstance(repo, Repository)
        assert repo.name == "new-repo"
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["name"] == "new-repo"

    def test_create_with_description(self, mock_responses, backlog_adapter):
        """description を渡すとペイロードに含まれる。"""
        mock_responses.add(
            responses.POST, f"{BASE}/projects/TEST/git/repositories",
            json=_repo_data(name="new-repo"), status=201,
        )
        backlog_adapter.create_repository(name="new-repo", description="My repo")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["description"] == "My repo"


class TestGetRepository:
    def test_get(self, mock_responses, backlog_adapter):
        mock_responses.add(
            responses.GET, f"{BASE}/projects/TEST/git/repositories/test-repo",
            json=_repo_data(), status=200,
        )
        repo = backlog_adapter.get_repository()
        assert repo.name == "test-repo"

    def test_get_by_name(self, mock_responses, backlog_adapter):
        mock_responses.add(
            responses.GET, f"{BASE}/projects/TEST/git/repositories/other-repo",
            json=_repo_data(name="other-repo"), status=200,
        )
        repo = backlog_adapter.get_repository(name="other-repo")
        assert repo.name == "other-repo"

    def test_get_repo_with_special_chars_is_encoded(self, mock_responses, backlog_adapter):
        """非 ASCII 文字を含むリポジトリ名が URL エンコードされる（R33-01）。"""
        mock_responses.add(
            responses.GET,
            f"{BASE}/projects/TEST/git/repositories/%E6%97%A5%E6%9C%AC%E8%AA%9E",
            json=_repo_data(name="日本語"), status=200,
        )
        repo = backlog_adapter.get_repository(name="日本語")
        assert repo.name == "日本語"


# --- NotSupportedError ---

class TestNotSupported:
    def test_list_releases(self, backlog_adapter):
        with pytest.raises(NotSupportedError):
            backlog_adapter.list_releases()

    def test_create_release(self, backlog_adapter):
        with pytest.raises(NotSupportedError):
            backlog_adapter.create_release(tag="v1.0")

    def test_list_labels(self, backlog_adapter):
        with pytest.raises(NotSupportedError):
            backlog_adapter.list_labels()

    def test_create_label(self, backlog_adapter):
        with pytest.raises(NotSupportedError):
            backlog_adapter.create_label(name="bug")

    def test_list_milestones(self, backlog_adapter):
        with pytest.raises(NotSupportedError):
            backlog_adapter.list_milestones()

    def test_create_milestone(self, backlog_adapter):
        with pytest.raises(NotSupportedError):
            backlog_adapter.create_milestone(title="v1.0")


# --- _resolve_merged_status_id キャッシュ ---

class TestResolveMergedStatusId:
    def test_cached(self, mock_responses, backlog_adapter):
        mock_responses.add(
            responses.GET, f"{BASE}/projects/TEST/statuses",
            json=[{"id": 5, "name": "Merged"}], status=200,
        )
        id1 = backlog_adapter._resolve_merged_status_id()
        id2 = backlog_adapter._resolve_merged_status_id()
        assert id1 == 5
        assert id2 == 5
        assert len(mock_responses.calls) == 1  # キャッシュにより1回のみ


# --- Registry ---

class TestPrPath:
    def test_non_ascii_repo_encoded(self):
        """非ASCII repo 名が URL エンコードされる。"""
        from gfo.http import HttpClient
        client = HttpClient("https://example.backlog.com/api/v2")
        adapter = BacklogAdapter(client, "owner", "日本語-repo", project_key="TEST")
        path = adapter._pr_path()
        assert "日本語" not in path
        assert "%E6%97%A5%E6%9C%AC%E8%AA%9E" in path


class TestRegistry:
    def test_registered(self):
        assert get_adapter_class("backlog") is BacklogAdapter


class TestErrorHandling:
    """HTTP エラーが適切な例外に変換されることを確認する。"""

    def test_not_found_raises_error(self, mock_responses, backlog_adapter):
        mock_responses.add(responses.GET, f"{PR_PATH}/999", status=404)
        with pytest.raises(NotFoundError):
            backlog_adapter.get_pull_request(999)

    def test_401_raises_auth_error(self, mock_responses, backlog_adapter):
        mock_responses.add(responses.GET, f"{PR_PATH}", status=401)
        with pytest.raises(AuthenticationError):
            backlog_adapter.list_pull_requests()

    def test_500_raises_server_error(self, mock_responses, backlog_adapter):
        mock_responses.add(responses.GET, f"{BASE}/projects/TEST", status=500)
        with pytest.raises(ServerError):
            backlog_adapter.list_issues()

    def test_malformed_pr_raises_gfo_error(self, mock_responses, backlog_adapter):
        """_to_pull_request で必須フィールド欠落 → GfoError。"""
        from gfo.exceptions import GfoError
        mock_responses.add(
            responses.GET, f"{BASE}/projects/TEST/statuses",
            json=[{"id": 5, "name": "Merged"}], status=200,
        )
        mock_responses.add(
            responses.GET, f"{PR_PATH}/1",
            json={"incomplete": True}, status=200,
        )
        with pytest.raises(GfoError):
            backlog_adapter.get_pull_request(1)

    def test_malformed_issue_raises_gfo_error(self, mock_responses, backlog_adapter):
        """_to_issue で必須フィールド欠落 → GfoError。"""
        from gfo.exceptions import GfoError
        mock_responses.add(
            responses.GET, f"{BASE}/projects/TEST",
            json={"id": 100, "projectKey": "TEST"}, status=200,
        )
        mock_responses.add(
            responses.GET, ISSUES_PATH,
            json=[{"incomplete": True}], status=200,
        )
        with pytest.raises(GfoError):
            backlog_adapter.list_issues()

    def test_malformed_repository_raises_gfo_error(self, mock_responses, backlog_adapter):
        """_to_repository で必須フィールド欠落 → GfoError。"""
        from gfo.exceptions import GfoError
        mock_responses.add(
            responses.GET, f"{BASE}/projects/TEST/git/repositories/test-repo",
            json={"incomplete": True}, status=200,
        )
        with pytest.raises(GfoError):
            backlog_adapter.get_repository()
