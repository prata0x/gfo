"""AzureDevOpsAdapter のテスト。"""

from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

import pytest
import responses

from gfo.adapter.base import Issue, PullRequest, Repository
from gfo.adapter.azure_devops import (
    AzureDevOpsAdapter,
    _add_refs_prefix,
    _strip_refs_prefix,
)
from gfo.adapter.registry import get_adapter_class
from gfo.exceptions import AuthenticationError, NotFoundError, NotSupportedError, ServerError


BASE = "https://dev.azure.com/test-org/test-project/_apis"
GIT = f"{BASE}/git/repositories/test-repo"
WIT = f"{BASE}/wit"


# --- サンプルデータ ---

def _pr_data(*, pull_request_id=1, status="active", is_draft=False):
    return {
        "pullRequestId": pull_request_id,
        "title": f"PR #{pull_request_id}",
        "description": "pr description",
        "status": status,
        "createdBy": {"uniqueName": "author@example.com"},
        "sourceRefName": "refs/heads/feature",
        "targetRefName": "refs/heads/main",
        "isDraft": is_draft,
        "url": f"https://dev.azure.com/test-org/test-project/_apis/git/repositories/test-repo/pullRequests/{pull_request_id}",
        "creationDate": "2025-01-01T00:00:00Z",
        "closedDate": None,
        "lastMergeSourceCommit": {"commitId": "abc123", "url": "https://example.com"},
    }


def _issue_data(*, id=1, state="New"):
    return {
        "id": id,
        "url": f"https://dev.azure.com/test-org/test-project/_apis/wit/workItems/{id}",
        "fields": {
            "System.Title": f"Work Item #{id}",
            "System.Description": "issue body",
            "System.State": state,
            "System.CreatedBy": {"uniqueName": "creator@example.com"},
            "System.AssignedTo": {"uniqueName": "dev@example.com"},
            "System.Tags": "bug; urgent",
            "System.CreatedDate": "2025-01-01T00:00:00Z",
        },
    }


def _repo_data(*, name="test-repo"):
    return {
        "name": name,
        "remoteUrl": f"https://dev.azure.com/test-org/test-project/_git/{name}",
        "webUrl": f"https://dev.azure.com/test-org/test-project/_git/{name}",
        "defaultBranch": "refs/heads/main",
        "project": {"description": "A test project"},
    }


# --- 変換メソッドのテスト ---

class TestToPullRequest:
    def test_active(self):
        pr = AzureDevOpsAdapter._to_pull_request(_pr_data())
        assert pr.state == "open"
        assert pr.number == 1
        assert pr.author == "author@example.com"
        assert pr.source_branch == "feature"
        assert pr.target_branch == "main"
        assert pr.draft is False

    def test_abandoned(self):
        pr = AzureDevOpsAdapter._to_pull_request(_pr_data(status="abandoned"))
        assert pr.state == "closed"

    def test_completed(self):
        pr = AzureDevOpsAdapter._to_pull_request(_pr_data(status="completed"))
        assert pr.state == "merged"

    def test_draft(self):
        pr = AzureDevOpsAdapter._to_pull_request(_pr_data(is_draft=True))
        assert pr.draft is True

    def test_refs_strip(self):
        data = _pr_data()
        data["sourceRefName"] = "refs/heads/feat/xyz"
        pr = AzureDevOpsAdapter._to_pull_request(data)
        assert pr.source_branch == "feat/xyz"

    def test_url_uses_web_url(self):
        data = _pr_data(pull_request_id=42)
        data["repository"] = {"webUrl": "https://dev.azure.com/org/proj/_git/repo"}
        pr = AzureDevOpsAdapter._to_pull_request(data)
        assert pr.url == "https://dev.azure.com/org/proj/_git/repo/pullrequest/42"

    def test_url_fallback_when_no_web_url(self):
        data = _pr_data(pull_request_id=42)
        data["repository"] = {}  # webUrl なし
        pr = AzureDevOpsAdapter._to_pull_request(data)
        assert pr.url == data["url"]  # API URL にフォールバック

    def test_url_fallback_when_no_repository(self):
        data = _pr_data(pull_request_id=42)
        data.pop("repository", None)  # repository フィールドなし
        pr = AzureDevOpsAdapter._to_pull_request(data)
        assert pr.url == data["url"]

    def test_url_fallback_when_repository_is_null(self):
        """repository フィールドが null のとき AttributeError にならず url にフォールバックする。"""
        data = _pr_data(pull_request_id=42)
        data["repository"] = None
        pr = AzureDevOpsAdapter._to_pull_request(data)
        assert pr.url == data["url"]


class TestToIssue:
    def test_new(self):
        issue = AzureDevOpsAdapter._to_issue(_issue_data())
        assert issue.number == 1
        assert issue.state == "open"
        assert issue.body == "issue body"
        assert issue.author == "creator@example.com"
        assert issue.assignees == ["dev@example.com"]
        assert issue.labels == ["bug", "urgent"]

    def test_closed_state(self):
        issue = AzureDevOpsAdapter._to_issue(_issue_data(state="Closed"))
        assert issue.state == "closed"

    def test_done_state(self):
        issue = AzureDevOpsAdapter._to_issue(_issue_data(state="Done"))
        assert issue.state == "closed"

    def test_removed_state(self):
        issue = AzureDevOpsAdapter._to_issue(_issue_data(state="Removed"))
        assert issue.state == "closed"

    def test_active_state(self):
        issue = AzureDevOpsAdapter._to_issue(_issue_data(state="Active"))
        assert issue.state == "open"

    def test_no_assignee(self):
        data = _issue_data()
        data["fields"].pop("System.AssignedTo")
        issue = AzureDevOpsAdapter._to_issue(data)
        assert issue.assignees == []

    def test_assignee_without_unique_name(self):
        """assignee が uniqueName を持たない場合は空リストを返す。"""
        data = _issue_data()
        data["fields"]["System.AssignedTo"] = {"displayName": "Dev User"}
        issue = AzureDevOpsAdapter._to_issue(data)
        assert issue.assignees == []

    def test_no_tags(self):
        data = _issue_data()
        data["fields"]["System.Tags"] = ""
        issue = AzureDevOpsAdapter._to_issue(data)
        assert issue.labels == []

    def test_updated_at_mapped_from_changed_date(self):
        """System.ChangedDate が updated_at に正しくマッピングされる。"""
        data = _issue_data()
        data["fields"]["System.ChangedDate"] = "2025-06-01T12:00:00Z"
        issue = AzureDevOpsAdapter._to_issue(data)
        assert issue.updated_at == "2025-06-01T12:00:00Z"

    def test_updated_at_is_none_when_missing(self):
        """System.ChangedDate がない場合、updated_at は None になる。"""
        data = _issue_data()
        data["fields"].pop("System.ChangedDate", None)
        issue = AzureDevOpsAdapter._to_issue(data)
        assert issue.updated_at is None

    def test_null_created_by_yields_empty_author(self):
        """System.CreatedBy が null でも AttributeError にならず author が空文字になる。"""
        data = _issue_data()
        data["fields"]["System.CreatedBy"] = None
        issue = AzureDevOpsAdapter._to_issue(data)
        assert issue.author == ""

    def test_non_dict_created_by_raises_gfo_error(self):
        """System.CreatedBy が dict 以外の truthy 値のとき AttributeError でなく GfoError になる。"""
        from gfo.exceptions import GfoError
        data = _issue_data()
        data["fields"]["System.CreatedBy"] = "not a dict"
        with pytest.raises(GfoError):
            AzureDevOpsAdapter._to_issue(data)


class TestToRepository:
    def test_basic(self, azure_devops_adapter):
        repo = azure_devops_adapter._to_repository(_repo_data(), "test-project")
        assert repo.name == "test-repo"
        assert repo.full_name == "test-project/test-repo"
        assert repo.private is True
        assert repo.default_branch == "main"
        assert "test-repo" in repo.clone_url

    def test_no_default_branch(self, azure_devops_adapter):
        data = _repo_data()
        data["defaultBranch"] = ""
        repo = azure_devops_adapter._to_repository(data, "test-project")
        assert repo.default_branch == ""

    def test_null_project_yields_none_description(self, azure_devops_adapter):
        """project フィールドが null でも AttributeError にならず description が None になる。"""
        data = _repo_data()
        data["project"] = None
        repo = azure_devops_adapter._to_repository(data, "test-project")
        assert repo.description is None


# --- PR 系 ---

class TestListPullRequests:
    def test_open(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.GET, f"{GIT}/pullrequests",
            json={"value": [_pr_data()], "count": 1}, status=200,
        )
        prs = azure_devops_adapter.list_pull_requests()
        assert len(prs) == 1
        assert prs[0].state == "open"
        req = mock_responses.calls[0].request
        assert "searchCriteria.status=active" in req.url

    def test_all(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.GET, f"{GIT}/pullrequests",
            json={"value": [_pr_data()], "count": 1}, status=200,
        )
        prs = azure_devops_adapter.list_pull_requests(state="all")
        assert len(prs) == 1
        req = mock_responses.calls[0].request
        assert "searchCriteria.status" not in req.url

    def test_merged_filter(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.GET, f"{GIT}/pullrequests",
            json={"value": [_pr_data(status="completed")]}, status=200,
        )
        prs = azure_devops_adapter.list_pull_requests(state="merged")
        assert prs[0].state == "merged"
        req = mock_responses.calls[0].request
        assert "searchCriteria.status=completed" in req.url

    def test_pagination(self, mock_responses, azure_devops_adapter):
        """$top/$skip ベースのページネーションで2ページ取得。"""
        mock_responses.add(
            responses.GET, f"{GIT}/pullrequests",
            json={"value": [_pr_data(pull_request_id=i) for i in range(1, 31)]}, status=200,
        )
        mock_responses.add(
            responses.GET, f"{GIT}/pullrequests",
            json={"value": [_pr_data(pull_request_id=31)]}, status=200,
        )
        prs = azure_devops_adapter.list_pull_requests(limit=0)
        assert len(prs) == 31
        req1 = mock_responses.calls[0].request
        req2 = mock_responses.calls[1].request
        assert "%24top=30" in req1.url or "$top=30" in req1.url
        assert "%24skip=0" in req1.url or "$skip=0" in req1.url
        assert "%24skip=30" in req2.url or "$skip=30" in req2.url


class TestBasicAuth:
    @responses.activate
    def test_basic_auth_header_encoding(self):
        import base64
        from gfo.http import HttpClient
        from gfo.adapter.azure_devops import AzureDevOpsAdapter

        client = HttpClient(
            BASE,
            basic_auth=("", "test-pat"),
            default_params={"api-version": "7.1"},
        )
        adapter = AzureDevOpsAdapter(
            client, "test-owner", "test-repo",
            organization="test-org", project_key="test-project",
        )
        responses.add(
            responses.GET, f"{GIT}/pullrequests",
            json={"value": [_pr_data()], "count": 1}, status=200,
        )
        adapter.list_pull_requests()
        req = responses.calls[0].request
        auth_header = req.headers.get("Authorization", "")
        assert auth_header.startswith("Basic ")
        encoded = auth_header[len("Basic "):]
        decoded = base64.b64decode(encoded).decode("ascii")
        assert decoded == ":test-pat"


class TestCreatePullRequest:
    def test_create(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.POST, f"{GIT}/pullrequests",
            json=_pr_data(), status=201,
        )
        pr = azure_devops_adapter.create_pull_request(
            title="PR #1", body="desc", base="main", head="feature",
        )
        assert isinstance(pr, PullRequest)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["sourceRefName"] == "refs/heads/feature"
        assert req_body["targetRefName"] == "refs/heads/main"

    def test_draft(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.POST, f"{GIT}/pullrequests",
            json=_pr_data(is_draft=True), status=201,
        )
        pr = azure_devops_adapter.create_pull_request(
            title="Draft PR", body="", base="main", head="feature", draft=True,
        )
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["isDraft"] is True


class TestGetPullRequest:
    def test_get(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.GET, f"{GIT}/pullrequests/42",
            json=_pr_data(pull_request_id=42), status=200,
        )
        pr = azure_devops_adapter.get_pull_request(42)
        assert pr.number == 42


class TestMergePullRequest:
    @pytest.mark.parametrize("method,strategy", [
        ("merge", "noFastForward"),
        ("squash", "squash"),
        ("rebase", "rebase"),
    ])
    def test_merge_strategies(self, mock_responses, azure_devops_adapter, method, strategy):
        mock_responses.add(
            responses.GET, f"{GIT}/pullrequests/1",
            json=_pr_data(), status=200,
        )
        mock_responses.add(
            responses.PATCH, f"{GIT}/pullrequests/1",
            json=_pr_data(status="completed"), status=200,
        )
        azure_devops_adapter.merge_pull_request(1, method=method)
        req_body = json.loads(mock_responses.calls[1].request.body)
        assert req_body["status"] == "completed"
        assert req_body["completionOptions"]["mergeStrategy"] == strategy
        assert req_body["lastMergeSourceCommit"]["commitId"] == "abc123"


    def test_merge_missing_last_merge_commit_raises_gfo_error(
        self, mock_responses, azure_devops_adapter
    ):
        """lastMergeSourceCommit が欠落している PR をマージしようとすると GfoError。"""
        from gfo.exceptions import GfoError
        pr_data_no_commit = _pr_data()
        del pr_data_no_commit["lastMergeSourceCommit"]
        mock_responses.add(
            responses.GET, f"{GIT}/pullrequests/1",
            json=pr_data_no_commit, status=200,
        )
        with pytest.raises(GfoError, match="lastMergeSourceCommit not found"):
            azure_devops_adapter.merge_pull_request(1)

    def test_merge_non_dict_response_raises_gfo_error(
        self, mock_responses, azure_devops_adapter
    ):
        """pullrequests エンドポイントが dict 以外を返した場合 GfoError になる。"""
        from gfo.exceptions import GfoError
        mock_responses.add(
            responses.GET, f"{GIT}/pullrequests/1",
            json=[], status=200,
        )
        with pytest.raises(GfoError, match="Unexpected API response from pullrequests"):
            azure_devops_adapter.merge_pull_request(1)


class TestClosePullRequest:
    def test_close(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.PATCH, f"{GIT}/pullrequests/1",
            json=_pr_data(status="abandoned"), status=200,
        )
        azure_devops_adapter.close_pull_request(1)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["status"] == "abandoned"


class TestCheckoutRefspec:
    def test_refspec(self, azure_devops_adapter):
        assert azure_devops_adapter.get_pr_checkout_refspec(42) == "refs/pull/42/head"


# --- Issue (Work Item) 系 ---

class TestListIssues:
    def test_open(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.POST, f"{WIT}/wiql",
            json={"workItems": [{"id": 1}, {"id": 2}]}, status=200,
        )
        mock_responses.add(
            responses.GET, f"{WIT}/workitems",
            json={"value": [_issue_data(id=1), _issue_data(id=2)]}, status=200,
        )
        issues = azure_devops_adapter.list_issues()
        assert len(issues) == 2
        wiql_body = json.loads(mock_responses.calls[0].request.body)
        assert "NOT IN ('Closed', 'Done', 'Removed')" in wiql_body["query"]
        qs = parse_qs(urlparse(mock_responses.calls[0].request.url).query)
        assert qs.get("$top") == ["30"]  # デフォルト limit=30 が $top に渡されることを確認

    def test_closed(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.POST, f"{WIT}/wiql",
            json={"workItems": [{"id": 1}]}, status=200,
        )
        mock_responses.add(
            responses.GET, f"{WIT}/workitems",
            json={"value": [_issue_data(id=1, state="Closed")]}, status=200,
        )
        issues = azure_devops_adapter.list_issues(state="closed")
        wiql_body = json.loads(mock_responses.calls[0].request.body)
        assert "IN ('Closed', 'Done', 'Removed')" in wiql_body["query"]

    def test_with_assignee_and_label(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.POST, f"{WIT}/wiql",
            json={"workItems": [{"id": 1}]}, status=200,
        )
        mock_responses.add(
            responses.GET, f"{WIT}/workitems",
            json={"value": [_issue_data(id=1)]}, status=200,
        )
        azure_devops_adapter.list_issues(assignee="dev@example.com", label="bug")
        wiql_body = json.loads(mock_responses.calls[0].request.body)
        assert "[System.AssignedTo] = 'dev@example.com'" in wiql_body["query"]
        assert "[System.Tags] CONTAINS 'bug'" in wiql_body["query"]

    def test_empty_result(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.POST, f"{WIT}/wiql",
            json={"workItems": []}, status=200,
        )
        issues = azure_devops_adapter.list_issues()
        assert issues == []

    def test_limit_zero_returns_all(self, mock_responses, azure_devops_adapter):
        """limit=0 は全件取得を意味し、空リストを返さない。"""
        mock_responses.add(
            responses.POST, f"{WIT}/wiql",
            json={"workItems": [{"id": 1}, {"id": 2}, {"id": 3}]}, status=200,
        )
        mock_responses.add(
            responses.GET, f"{WIT}/workitems",
            json={"value": [_issue_data(id=1), _issue_data(id=2), _issue_data(id=3)]}, status=200,
        )
        issues = azure_devops_adapter.list_issues(limit=0)
        assert len(issues) == 3
        # limit=0（全件取得）の場合 $top=20000 を渡す（R38-02）
        qs = parse_qs(urlparse(mock_responses.calls[0].request.url).query)
        assert qs.get("$top") == ["20000"]

    def test_batch_limit_guard_breaks_early(self, mock_responses, azure_devops_adapter):
        """バッチ処理中に limit に達したら 2 回目のバッチを処理しない（早期 break）。"""
        # 201 個の ID を返す → バッチが [0:200] と [200:201] の 2 回に分かれる
        mock_responses.add(
            responses.POST, f"{WIT}/wiql",
            json={"workItems": [{"id": i} for i in range(1, 202)]}, status=200,
        )
        # 最初のバッチ (200 件) を処理
        mock_responses.add(
            responses.GET, f"{WIT}/workitems",
            json={"value": [_issue_data(id=i) for i in range(1, 201)]}, status=200,
        )
        # limit=200: 1 回目のバッチ後に len(results)=200 >= 200 となるので break
        issues = azure_devops_adapter.list_issues(limit=200)
        assert len(issues) == 200
        # WIQL + workitems 1 回のみ（2 回目のバッチは呼ばれない）
        assert len(mock_responses.calls) == 2


    def test_non_dict_wiql_response_raises_gfo_error(self, mock_responses, azure_devops_adapter):
        """WIQL エンドポイントが dict 以外を返したとき GfoError。"""
        from gfo.exceptions import GfoError
        mock_responses.add(
            responses.POST, f"{WIT}/wiql",
            json=["unexpected", "list"], status=200,
        )
        with pytest.raises(GfoError, match="WIQL"):
            azure_devops_adapter.list_issues()

    def test_malformed_wiql_work_item_raises_gfo_error(self, mock_responses, azure_devops_adapter):
        """WIQL レスポンスの workItems 要素に id がないとき GfoError。"""
        from gfo.exceptions import GfoError
        mock_responses.add(
            responses.POST, f"{WIT}/wiql",
            json={"workItems": [{"no_id": True}]}, status=200,
        )
        with pytest.raises(GfoError, match="WIQL"):
            azure_devops_adapter.list_issues()

    def test_non_dict_workitems_response_raises_gfo_error(self, mock_responses, azure_devops_adapter):
        """workitems バッチエンドポイントが dict 以外を返したとき GfoError。"""
        from gfo.exceptions import GfoError
        mock_responses.add(
            responses.POST, f"{WIT}/wiql",
            json={"workItems": [{"id": 1}]}, status=200,
        )
        mock_responses.add(
            responses.GET, f"{WIT}/workitems",
            json=["unexpected"], status=200,
        )
        with pytest.raises(GfoError, match="workitems"):
            azure_devops_adapter.list_issues()


class TestCreateIssue:
    def test_create(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.POST, f"{WIT}/workitems/$Task",
            json=_issue_data(), status=200,
        )
        issue = azure_devops_adapter.create_issue(title="Work Item #1", body="body")
        assert isinstance(issue, Issue)
        req = mock_responses.calls[0].request
        assert req.headers["Content-Type"] == "application/json-patch+json"
        ops = json.loads(req.body)
        paths = [op["path"] for op in ops]
        assert "/fields/System.Title" in paths
        assert "/fields/System.Description" in paths

    def test_create_with_assignee_and_label(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.POST, f"{WIT}/workitems/$Task",
            json=_issue_data(), status=200,
        )
        azure_devops_adapter.create_issue(
            title="Item", assignee="dev@example.com", label="bug",
        )
        ops = json.loads(mock_responses.calls[0].request.body)
        paths = [op["path"] for op in ops]
        assert "/fields/System.AssignedTo" in paths
        assert "/fields/System.Tags" in paths


    def test_create_with_custom_work_item_type(self, mock_responses, azure_devops_adapter):
        """work_item_type にスペースを含む値（"User Story" 等）が URL エンコードされる。"""
        mock_responses.add(
            responses.POST, f"{WIT}/workitems/$User%20Story",
            json=_issue_data(), status=200,
        )
        issue = azure_devops_adapter.create_issue(
            title="Story #1", work_item_type="User Story",
        )
        assert isinstance(issue, Issue)
        assert "$User%20Story" in mock_responses.calls[0].request.url


class TestGetIssue:
    def test_get(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.GET, f"{WIT}/workitems/5",
            json=_issue_data(id=5), status=200,
        )
        issue = azure_devops_adapter.get_issue(5)
        assert issue.number == 5


class TestCloseIssue:
    def test_close(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.PATCH, f"{WIT}/workitems/3",
            json=_issue_data(id=3, state="Closed"), status=200,
        )
        azure_devops_adapter.close_issue(3)
        req = mock_responses.calls[0].request
        assert req.headers["Content-Type"] == "application/json-patch+json"
        ops = json.loads(req.body)
        assert ops[0]["op"] == "replace"
        assert ops[0]["path"] == "/fields/System.State"
        assert ops[0]["value"] == "Closed"


# --- Repository 系 ---

class TestListRepositories:
    def test_list(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.GET, f"{BASE}/git/repositories",
            json={"value": [_repo_data()]}, status=200,
        )
        repos = azure_devops_adapter.list_repositories()
        assert len(repos) == 1

    def test_owner_raises_not_supported(self, azure_devops_adapter):
        """Azure DevOps は owner によるフィルタを未サポート → NotSupportedError。"""
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.list_repositories(owner="someone")


class TestCreateRepository:
    def test_create(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.POST, f"{BASE}/git/repositories",
            json=_repo_data(name="new-repo"), status=201,
        )
        repo = azure_devops_adapter.create_repository(name="new-repo")
        assert isinstance(repo, Repository)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["project"]["id"] == "test-project"


class TestGetRepository:
    def test_get(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.GET, f"{BASE}/git/repositories/test-repo",
            json=_repo_data(), status=200,
        )
        repo = azure_devops_adapter.get_repository()
        assert repo.name == "test-repo"

    def test_get_by_name(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.GET, f"{BASE}/git/repositories/other-repo",
            json=_repo_data(name="other-repo"), status=200,
        )
        repo = azure_devops_adapter.get_repository(name="other-repo")
        assert repo.name == "other-repo"

    def test_get_repo_with_space_is_encoded(self, mock_responses, azure_devops_adapter):
        """スペースを含むリポジトリ名が URL エンコードされる（R33-02）。"""
        mock_responses.add(
            responses.GET, f"{BASE}/git/repositories/My%20Repo",
            json=_repo_data(name="My Repo"), status=200,
        )
        repo = azure_devops_adapter.get_repository(name="My Repo")
        assert repo.name == "My Repo"


# --- NotSupportedError ---

class TestNotSupported:
    def test_list_releases(self, azure_devops_adapter):
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.list_releases()

    def test_create_release(self, azure_devops_adapter):
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.create_release(tag="v1.0")

    def test_list_labels(self, azure_devops_adapter):
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.list_labels()

    def test_create_label(self, azure_devops_adapter):
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.create_label(name="bug")

    def test_list_milestones(self, azure_devops_adapter):
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.list_milestones()

    def test_create_milestone(self, azure_devops_adapter):
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.create_milestone(title="v1.0")


# --- refs/heads ヘルパー ---

class TestRefsPrefix:
    def test_add_plain(self):
        assert _add_refs_prefix("main") == "refs/heads/main"

    def test_add_idempotent(self):
        assert _add_refs_prefix("refs/heads/main") == "refs/heads/main"

    def test_strip_with_prefix(self):
        assert _strip_refs_prefix("refs/heads/main") == "main"

    def test_strip_without_prefix(self):
        assert _strip_refs_prefix("main") == "main"

    def test_roundtrip(self):
        assert _strip_refs_prefix(_add_refs_prefix("feature/xyz")) == "feature/xyz"


# --- Registry ---

class TestRegistry:
    def test_registered(self):
        assert get_adapter_class("azure-devops") is AzureDevOpsAdapter


class TestErrorHandling:
    """HTTP エラーが適切な例外に変換されることを確認する。"""

    def test_not_found_raises_error(self, mock_responses, azure_devops_adapter):
        mock_responses.add(responses.GET, f"{GIT}/pullrequests/999", status=404)
        with pytest.raises(NotFoundError):
            azure_devops_adapter.get_pull_request(999)

    def test_401_raises_auth_error(self, mock_responses, azure_devops_adapter):
        mock_responses.add(responses.GET, f"{GIT}/pullrequests", status=401)
        with pytest.raises(AuthenticationError):
            azure_devops_adapter.list_pull_requests()

    def test_500_raises_server_error(self, mock_responses, azure_devops_adapter):
        mock_responses.add(responses.POST, f"{GIT}/pullrequests", status=500)
        with pytest.raises(ServerError):
            azure_devops_adapter.create_pull_request(
                title="PR", body="", base="main", head="feature"
            )

    def test_malformed_pr_raises_gfo_error(self, mock_responses, azure_devops_adapter):
        """_to_pull_request で必須フィールド欠落 → GfoError。"""
        from gfo.exceptions import GfoError
        mock_responses.add(
            responses.GET, f"{GIT}/pullrequests/1",
            json={"incomplete": True}, status=200,
        )
        with pytest.raises(GfoError):
            azure_devops_adapter.get_pull_request(1)

    def test_malformed_repository_raises_gfo_error(self, mock_responses, azure_devops_adapter):
        """_to_repository で必須フィールド欠落 → GfoError。"""
        from gfo.exceptions import GfoError
        mock_responses.add(
            responses.GET, f"{GIT}",
            json={"incomplete": True}, status=200,
        )
        with pytest.raises(GfoError):
            azure_devops_adapter.get_repository()

    def test_malformed_issue_raises_gfo_error(self, mock_responses, azure_devops_adapter):
        """_to_issue で必須フィールド欠落 → GfoError。"""
        from gfo.exceptions import GfoError
        mock_responses.add(
            responses.POST, f"{WIT}/wiql",
            json={"workItems": [{"id": 1}]}, status=200,
        )
        mock_responses.add(
            responses.GET, f"{WIT}/workitems",
            json={"value": [{"incomplete": True}]}, status=200,
        )
        with pytest.raises(GfoError):
            azure_devops_adapter.list_issues()
