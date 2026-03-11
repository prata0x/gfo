"""AzureDevOpsAdapter のテスト。"""

from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

import pytest
import responses

from gfo.adapter.azure_devops import (
    AzureDevOpsAdapter,
    _add_refs_prefix,
    _strip_refs_prefix,
)
from gfo.adapter.base import (
    Branch,
    Comment,
    CommitStatus,
    Issue,
    Pipeline,
    PullRequest,
    Repository,
    Review,
    Tag,
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

    def test_null_default_branch_yields_empty_string(self, azure_devops_adapter):
        """defaultBranch フィールドが null でも GfoError にならず default_branch が "" になる。"""
        data = _repo_data()
        data["defaultBranch"] = None
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
            responses.GET,
            f"{GIT}/pullrequests",
            json={"value": [_pr_data()], "count": 1},
            status=200,
        )
        prs = azure_devops_adapter.list_pull_requests()
        assert len(prs) == 1
        assert prs[0].state == "open"
        req = mock_responses.calls[0].request
        assert "searchCriteria.status=active" in req.url

    def test_all(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.GET,
            f"{GIT}/pullrequests",
            json={"value": [_pr_data()], "count": 1},
            status=200,
        )
        prs = azure_devops_adapter.list_pull_requests(state="all")
        assert len(prs) == 1
        req = mock_responses.calls[0].request
        assert "searchCriteria.status" not in req.url

    def test_merged_filter(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.GET,
            f"{GIT}/pullrequests",
            json={"value": [_pr_data(status="completed")]},
            status=200,
        )
        prs = azure_devops_adapter.list_pull_requests(state="merged")
        assert prs[0].state == "merged"
        req = mock_responses.calls[0].request
        assert "searchCriteria.status=completed" in req.url

    def test_pagination(self, mock_responses, azure_devops_adapter):
        """$top/$skip ベースのページネーションで2ページ取得。"""
        mock_responses.add(
            responses.GET,
            f"{GIT}/pullrequests",
            json={"value": [_pr_data(pull_request_id=i) for i in range(1, 31)]},
            status=200,
        )
        mock_responses.add(
            responses.GET,
            f"{GIT}/pullrequests",
            json={"value": [_pr_data(pull_request_id=31)]},
            status=200,
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

        from gfo.adapter.azure_devops import AzureDevOpsAdapter
        from gfo.http import HttpClient

        client = HttpClient(
            BASE,
            basic_auth=("", "test-pat"),
            default_params={"api-version": "7.1"},
        )
        adapter = AzureDevOpsAdapter(
            client,
            "test-owner",
            "test-repo",
            organization="test-org",
            project_key="test-project",
        )
        responses.add(
            responses.GET,
            f"{GIT}/pullrequests",
            json={"value": [_pr_data()], "count": 1},
            status=200,
        )
        adapter.list_pull_requests()
        req = responses.calls[0].request
        auth_header = req.headers.get("Authorization", "")
        assert auth_header.startswith("Basic ")
        encoded = auth_header[len("Basic ") :]
        decoded = base64.b64decode(encoded).decode("ascii")
        assert decoded == ":test-pat"


class TestCreatePullRequest:
    def test_create(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.POST,
            f"{GIT}/pullrequests",
            json=_pr_data(),
            status=201,
        )
        pr = azure_devops_adapter.create_pull_request(
            title="PR #1",
            body="desc",
            base="main",
            head="feature",
        )
        assert isinstance(pr, PullRequest)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["sourceRefName"] == "refs/heads/feature"
        assert req_body["targetRefName"] == "refs/heads/main"

    def test_draft(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.POST,
            f"{GIT}/pullrequests",
            json=_pr_data(is_draft=True),
            status=201,
        )
        _ = azure_devops_adapter.create_pull_request(
            title="Draft PR",
            body="",
            base="main",
            head="feature",
            draft=True,
        )
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["isDraft"] is True


class TestGetPullRequest:
    def test_get(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.GET,
            f"{GIT}/pullrequests/42",
            json=_pr_data(pull_request_id=42),
            status=200,
        )
        pr = azure_devops_adapter.get_pull_request(42)
        assert pr.number == 42


class TestMergePullRequest:
    @pytest.mark.parametrize(
        "method,strategy",
        [
            ("merge", "noFastForward"),
            ("squash", "squash"),
            ("rebase", "rebase"),
        ],
    )
    def test_merge_strategies(self, mock_responses, azure_devops_adapter, method, strategy):
        mock_responses.add(
            responses.GET,
            f"{GIT}/pullrequests/1",
            json=_pr_data(),
            status=200,
        )
        mock_responses.add(
            responses.PATCH,
            f"{GIT}/pullrequests/1",
            json=_pr_data(status="completed"),
            status=200,
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
            responses.GET,
            f"{GIT}/pullrequests/1",
            json=pr_data_no_commit,
            status=200,
        )
        with pytest.raises(GfoError, match="lastMergeSourceCommit not found"):
            azure_devops_adapter.merge_pull_request(1)

    def test_merge_non_dict_response_raises_gfo_error(self, mock_responses, azure_devops_adapter):
        """pullrequests エンドポイントが dict 以外を返した場合 GfoError になる。"""
        from gfo.exceptions import GfoError

        mock_responses.add(
            responses.GET,
            f"{GIT}/pullrequests/1",
            json=[],
            status=200,
        )
        with pytest.raises(GfoError, match="Unexpected API response from pullrequests"):
            azure_devops_adapter.merge_pull_request(1)


class TestClosePullRequest:
    def test_close(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{GIT}/pullrequests/1",
            json=_pr_data(status="abandoned"),
            status=200,
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
            responses.POST,
            f"{WIT}/wiql",
            json={"workItems": [{"id": 1}, {"id": 2}]},
            status=200,
        )
        mock_responses.add(
            responses.GET,
            f"{WIT}/workitems",
            json={"value": [_issue_data(id=1), _issue_data(id=2)]},
            status=200,
        )
        issues = azure_devops_adapter.list_issues()
        assert len(issues) == 2
        wiql_body = json.loads(mock_responses.calls[0].request.body)
        assert "NOT IN ('Closed', 'Done', 'Removed')" in wiql_body["query"]
        qs = parse_qs(urlparse(mock_responses.calls[0].request.url).query)
        assert qs.get("$top") == ["30"]  # デフォルト limit=30 が $top に渡されることを確認

    def test_closed(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.POST,
            f"{WIT}/wiql",
            json={"workItems": [{"id": 1}]},
            status=200,
        )
        mock_responses.add(
            responses.GET,
            f"{WIT}/workitems",
            json={"value": [_issue_data(id=1, state="Closed")]},
            status=200,
        )
        _ = azure_devops_adapter.list_issues(state="closed")
        wiql_body = json.loads(mock_responses.calls[0].request.body)
        assert "IN ('Closed', 'Done', 'Removed')" in wiql_body["query"]

    def test_with_assignee_and_label(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.POST,
            f"{WIT}/wiql",
            json={"workItems": [{"id": 1}]},
            status=200,
        )
        mock_responses.add(
            responses.GET,
            f"{WIT}/workitems",
            json={"value": [_issue_data(id=1)]},
            status=200,
        )
        azure_devops_adapter.list_issues(assignee="dev@example.com", label="bug")
        wiql_body = json.loads(mock_responses.calls[0].request.body)
        assert "[System.AssignedTo] = 'dev@example.com'" in wiql_body["query"]
        assert "[System.Tags] CONTAINS 'bug'" in wiql_body["query"]

    def test_empty_result(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.POST,
            f"{WIT}/wiql",
            json={"workItems": []},
            status=200,
        )
        issues = azure_devops_adapter.list_issues()
        assert issues == []

    def test_limit_zero_returns_all(self, mock_responses, azure_devops_adapter):
        """limit=0 は全件取得を意味し、空リストを返さない。"""
        mock_responses.add(
            responses.POST,
            f"{WIT}/wiql",
            json={"workItems": [{"id": 1}, {"id": 2}, {"id": 3}]},
            status=200,
        )
        mock_responses.add(
            responses.GET,
            f"{WIT}/workitems",
            json={"value": [_issue_data(id=1), _issue_data(id=2), _issue_data(id=3)]},
            status=200,
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
            responses.POST,
            f"{WIT}/wiql",
            json={"workItems": [{"id": i} for i in range(1, 202)]},
            status=200,
        )
        # 最初のバッチ (200 件) を処理
        mock_responses.add(
            responses.GET,
            f"{WIT}/workitems",
            json={"value": [_issue_data(id=i) for i in range(1, 201)]},
            status=200,
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
            responses.POST,
            f"{WIT}/wiql",
            json=["unexpected", "list"],
            status=200,
        )
        with pytest.raises(GfoError, match="WIQL"):
            azure_devops_adapter.list_issues()

    def test_malformed_wiql_work_item_raises_gfo_error(self, mock_responses, azure_devops_adapter):
        """WIQL レスポンスの workItems 要素に id がないとき GfoError。"""
        from gfo.exceptions import GfoError

        mock_responses.add(
            responses.POST,
            f"{WIT}/wiql",
            json={"workItems": [{"no_id": True}]},
            status=200,
        )
        with pytest.raises(GfoError, match="WIQL"):
            azure_devops_adapter.list_issues()

    def test_non_dict_workitems_response_raises_gfo_error(
        self, mock_responses, azure_devops_adapter
    ):
        """workitems バッチエンドポイントが dict 以外を返したとき GfoError。"""
        from gfo.exceptions import GfoError

        mock_responses.add(
            responses.POST,
            f"{WIT}/wiql",
            json={"workItems": [{"id": 1}]},
            status=200,
        )
        mock_responses.add(
            responses.GET,
            f"{WIT}/workitems",
            json=["unexpected"],
            status=200,
        )
        with pytest.raises(GfoError, match="workitems"):
            azure_devops_adapter.list_issues()


class TestCreateIssue:
    def test_create(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.POST,
            f"{WIT}/workitems/$Task",
            json=_issue_data(),
            status=200,
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
            responses.POST,
            f"{WIT}/workitems/$Task",
            json=_issue_data(),
            status=200,
        )
        azure_devops_adapter.create_issue(
            title="Item",
            assignee="dev@example.com",
            label="bug",
        )
        ops = json.loads(mock_responses.calls[0].request.body)
        paths = [op["path"] for op in ops]
        assert "/fields/System.AssignedTo" in paths
        assert "/fields/System.Tags" in paths

    def test_create_with_custom_work_item_type(self, mock_responses, azure_devops_adapter):
        """work_item_type にスペースを含む値（"User Story" 等）が URL エンコードされる。"""
        mock_responses.add(
            responses.POST,
            f"{WIT}/workitems/$User%20Story",
            json=_issue_data(),
            status=200,
        )
        issue = azure_devops_adapter.create_issue(
            title="Story #1",
            work_item_type="User Story",
        )
        assert isinstance(issue, Issue)
        assert "$User%20Story" in mock_responses.calls[0].request.url


class TestGetIssue:
    def test_get(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.GET,
            f"{WIT}/workitems/5",
            json=_issue_data(id=5),
            status=200,
        )
        issue = azure_devops_adapter.get_issue(5)
        assert issue.number == 5


class TestCloseIssue:
    def test_close(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{WIT}/workitems/3",
            json=_issue_data(id=3, state="Closed"),
            status=200,
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
            responses.GET,
            f"{BASE}/git/repositories",
            json={"value": [_repo_data()]},
            status=200,
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
            responses.POST,
            f"{BASE}/git/repositories",
            json=_repo_data(name="new-repo"),
            status=201,
        )
        repo = azure_devops_adapter.create_repository(name="new-repo")
        assert isinstance(repo, Repository)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["name"] == "new-repo"
        assert "project" not in req_body  # project はベース URL に含まれるため不要


class TestGetRepository:
    def test_get(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/git/repositories/test-repo",
            json=_repo_data(),
            status=200,
        )
        repo = azure_devops_adapter.get_repository()
        assert repo.name == "test-repo"

    def test_get_by_name(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/git/repositories/other-repo",
            json=_repo_data(name="other-repo"),
            status=200,
        )
        repo = azure_devops_adapter.get_repository(name="other-repo")
        assert repo.name == "other-repo"

    def test_get_repo_with_space_is_encoded(self, mock_responses, azure_devops_adapter):
        """スペースを含むリポジトリ名が URL エンコードされる（R33-02）。"""
        mock_responses.add(
            responses.GET,
            f"{BASE}/git/repositories/My%20Repo",
            json=_repo_data(name="My Repo"),
            status=200,
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
            responses.GET,
            f"{GIT}/pullrequests/1",
            json={"incomplete": True},
            status=200,
        )
        with pytest.raises(GfoError):
            azure_devops_adapter.get_pull_request(1)

    def test_malformed_repository_raises_gfo_error(self, mock_responses, azure_devops_adapter):
        """_to_repository で必須フィールド欠落 → GfoError。"""
        from gfo.exceptions import GfoError

        mock_responses.add(
            responses.GET,
            f"{GIT}",
            json={"incomplete": True},
            status=200,
        )
        with pytest.raises(GfoError):
            azure_devops_adapter.get_repository()

    def test_malformed_issue_raises_gfo_error(self, mock_responses, azure_devops_adapter):
        """_to_issue で必須フィールド欠落 → GfoError。"""
        from gfo.exceptions import GfoError

        mock_responses.add(
            responses.POST,
            f"{WIT}/wiql",
            json={"workItems": [{"id": 1}]},
            status=200,
        )
        mock_responses.add(
            responses.GET,
            f"{WIT}/workitems",
            json={"value": [{"incomplete": True}]},
            status=200,
        )
        with pytest.raises(GfoError):
            azure_devops_adapter.list_issues()


class TestDeleteIssue:
    def test_delete(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{WIT}/workitems/10",
            status=200,
        )
        azure_devops_adapter.delete_issue(10)
        assert mock_responses.calls[0].request.method == "DELETE"
        assert "/workitems/10" in mock_responses.calls[0].request.url


class TestDeleteRepository:
    def test_delete(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.GET,
            GIT,
            json={"id": "repo-uuid-123", "name": "test-repo"},
            status=200,
        )
        mock_responses.add(
            responses.DELETE,
            f"{BASE}/git/repositories/repo-uuid-123",
            status=204,
        )
        azure_devops_adapter.delete_repository()
        assert mock_responses.calls[0].request.method == "GET"
        assert mock_responses.calls[1].request.method == "DELETE"

    def test_malformed_response_raises_gfo_error(self, mock_responses, azure_devops_adapter):
        from gfo.exceptions import GfoError

        mock_responses.add(
            responses.GET,
            GIT,
            json={"incomplete": True},
            status=200,
        )
        with pytest.raises(GfoError):
            azure_devops_adapter.delete_repository()


# --- サンプルデータ（拡張） ---


def _comment_data(*, comment_id=10):
    return {
        "id": comment_id,
        "content": "A comment",
        "author": {"uniqueName": "commenter@example.com"},
        "publishedDate": "2025-01-01T00:00:00Z",
        "lastUpdatedDate": "2025-01-02T00:00:00Z",
    }


def _thread_data(*, comment_id=10):
    return {
        "id": 1,
        "comments": [_comment_data(comment_id=comment_id)],
        "status": "active",
    }


def _review_data(*, reviewer_id="abc-123", vote=10):
    return {
        "id": reviewer_id,
        "uniqueName": "reviewer@example.com",
        "displayName": "Reviewer",
        "vote": vote,
        "url": f"https://dev.azure.com/test-org/test-project/_apis/git/repositories/test-repo/pullrequests/1/reviewers/{reviewer_id}",
    }


def _branch_data_az(*, name="feature", sha="abc123"):
    return {
        "name": f"refs/heads/{name}",
        "objectId": sha,
    }


def _tag_data_az(*, name="v1.0.0", sha="def456"):
    return {
        "name": f"refs/tags/{name}",
        "objectId": sha,
    }


def _commit_status_data(*, state="succeeded", context_name="test", context_genre="ci"):
    return {
        "state": state,
        "context": {"name": context_name, "genre": context_genre},
        "description": "Tests passed",
        "targetUrl": "https://ci.example.com/build/1",
        "creationDate": "2025-01-01T00:00:00Z",
    }


def _pipeline_data_az(*, run_id=300, status="completed", result="succeeded"):
    return {
        "id": run_id,
        "status": status,
        "result": result,
        "sourceBranch": "refs/heads/main",
        "_links": {
            "web": {
                "href": f"https://dev.azure.com/test-org/test-project/_build/results?buildId={run_id}"
            }
        },
        "queueTime": "2025-01-01T00:00:00Z",
    }


# --- Comment 系 ---


class TestListComments:
    def test_list_pr(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.GET,
            f"{GIT}/pullrequests/1/threads",
            json={"value": [_thread_data()], "count": 1},
            status=200,
        )
        comments = azure_devops_adapter.list_comments("pr", 1)
        assert len(comments) == 1
        assert isinstance(comments[0], Comment)

    def test_list_issue(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.GET,
            f"{WIT}/workitems/1/comments",
            json={"comments": [_comment_data()], "count": 1},
            status=200,
        )
        comments = azure_devops_adapter.list_comments("issue", 1)
        assert len(comments) == 1


class TestCreateComment:
    def test_create_pr(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.POST,
            f"{GIT}/pullrequests/1/threads",
            json=_thread_data(),
            status=201,
        )
        comment = azure_devops_adapter.create_comment("pr", 1, body="A comment")
        assert isinstance(comment, Comment)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["comments"][0]["content"] == "A comment"

    def test_create_issue(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.POST,
            f"{WIT}/workitems/1/comments",
            json=_comment_data(),
            status=201,
        )
        comment = azure_devops_adapter.create_comment("issue", 1, body="A comment")
        assert isinstance(comment, Comment)


class TestUpdateCommentNotSupported:
    def test_raises(self, azure_devops_adapter):
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.update_comment("pr", 10, body="Updated")


class TestDeleteCommentNotSupported:
    def test_raises(self, azure_devops_adapter):
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.delete_comment("pr", 10)


# --- PR Update / Issue Update ---


class TestUpdatePullRequest:
    def test_update_title(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{GIT}/pullrequests/1",
            json=_pr_data(),
            status=200,
        )
        pr = azure_devops_adapter.update_pull_request(1, title="New Title")
        assert isinstance(pr, PullRequest)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["title"] == "New Title"

    def test_update_base(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{GIT}/pullrequests/1",
            json=_pr_data(),
            status=200,
        )
        azure_devops_adapter.update_pull_request(1, base="develop")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["targetRefName"] == "refs/heads/develop"


class TestUpdateIssue:
    def test_update_title(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{WIT}/workitems/1",
            json=_issue_data(),
            status=200,
        )
        issue = azure_devops_adapter.update_issue(1, title="New Title")
        assert isinstance(issue, Issue)
        req_body = json.loads(mock_responses.calls[0].request.body)
        patch_op = next((op for op in req_body if op["path"] == "/fields/System.Title"), None)
        assert patch_op is not None
        assert patch_op["value"] == "New Title"


# --- Review 系 ---


class TestListReviews:
    def test_list(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.GET,
            f"{GIT}/pullrequests/1/reviewers",
            json={"value": [_review_data()], "count": 1},
            status=200,
        )
        reviews = azure_devops_adapter.list_reviews(1)
        assert len(reviews) == 1
        assert isinstance(reviews[0], Review)
        assert reviews[0].state == "approved"


class TestCreateReview:
    def test_approve(self, mock_responses, azure_devops_adapter):
        # connectionData は組織スコープ URL（プロジェクトスコープ BASE とは別）
        mock_responses.add(
            responses.GET,
            "https://dev.azure.com/test-org/_apis/connectionData",
            json={"authenticatedUser": {"id": "user-id-123", "providerDisplayName": "testuser"}},
            status=200,
        )
        mock_responses.add(
            responses.PUT,
            f"{GIT}/pullrequests/1/reviewers/user-id-123",
            json=_review_data(vote=10),
            status=200,
        )
        azure_devops_adapter.create_review(1, state="approve")
        put_body = json.loads(mock_responses.calls[1].request.body)
        assert put_body["vote"] == 10


# --- Branch 系 ---


class TestListBranches:
    def test_list(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.GET,
            f"{GIT}/refs",
            json={"value": [_branch_data_az()], "count": 1},
            status=200,
        )
        branches = azure_devops_adapter.list_branches()
        assert len(branches) == 1
        assert isinstance(branches[0], Branch)
        assert branches[0].name == "feature"


class TestCreateBranch:
    def test_create(self, mock_responses, azure_devops_adapter):
        # create_branch は refs POST 後に refs GET して Branch を返す
        mock_responses.add(
            responses.POST,
            f"{GIT}/refs",
            json=[{"name": "refs/heads/new-branch", "newObjectId": "abc123"}],
            status=200,
        )
        mock_responses.add(
            responses.GET,
            f"{GIT}/refs",
            json={"value": [_branch_data_az(name="new-branch", sha="abc123")], "count": 1},
            status=200,
        )
        branch = azure_devops_adapter.create_branch(name="new-branch", ref="abc123")
        assert isinstance(branch, Branch)


class TestDeleteBranch:
    def test_delete(self, mock_responses, azure_devops_adapter):
        # まず SHA を取得するため refs を取得
        mock_responses.add(
            responses.GET,
            f"{GIT}/refs",
            json={"value": [_branch_data_az(name="feature", sha="abc123")], "count": 1},
            status=200,
        )
        mock_responses.add(
            responses.POST,
            f"{GIT}/refs",
            json={"value": [{"success": True}]},
            status=200,
        )
        azure_devops_adapter.delete_branch(name="feature")


# --- Tag 系 ---


class TestListTags:
    def test_list(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.GET,
            f"{GIT}/refs",
            json={"value": [_tag_data_az()], "count": 1},
            status=200,
        )
        tags = azure_devops_adapter.list_tags()
        assert len(tags) == 1
        assert isinstance(tags[0], Tag)
        assert tags[0].name == "v1.0.0"


class TestCreateTag:
    def test_create(self, mock_responses, azure_devops_adapter):
        # create_tag は refs POST を使う（pushes は commit が必要なため使用しない）
        mock_responses.add(
            responses.POST,
            f"{GIT}/refs",
            json=[{"name": "refs/tags/v2.0.0", "newObjectId": "abc123"}],
            status=200,
        )
        tag = azure_devops_adapter.create_tag(name="v2.0.0", ref="abc123")
        assert isinstance(tag, Tag)


# --- CommitStatus 系 ---


class TestListCommitStatuses:
    def test_list(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.GET,
            f"{GIT}/commits/abc123/statuses",
            json={"value": [_commit_status_data()], "count": 1},
            status=200,
        )
        statuses = azure_devops_adapter.list_commit_statuses("abc123")
        assert len(statuses) == 1
        assert isinstance(statuses[0], CommitStatus)
        assert statuses[0].state == "success"


class TestCreateCommitStatus:
    def test_create(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.POST,
            f"{GIT}/commits/abc123/statuses",
            json=_commit_status_data(),
            status=201,
        )
        status = azure_devops_adapter.create_commit_status(
            "abc123", state="success", context="ci/test"
        )
        assert isinstance(status, CommitStatus)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["state"] == "succeeded"


# --- File 系 ---


class TestGetFileContent:
    def test_get(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.GET,
            f"{GIT}/items",
            json={"content": "file content", "objectId": "sha123"},
            status=200,
        )
        content, sha = azure_devops_adapter.get_file_content("README.md")
        assert content == "file content"
        assert sha == "sha123"


class TestCreateOrUpdateFile:
    def test_create(self, mock_responses, azure_devops_adapter):
        # create_or_update_file は refs を GET してから pushes を POST する
        mock_responses.add(
            responses.GET,
            f"{GIT}/refs",
            json={"value": [_branch_data_az(name="main", sha="abc123")], "count": 1},
            status=200,
        )
        mock_responses.add(
            responses.POST,
            f"{GIT}/pushes",
            json={"refUpdates": [], "commits": [{"commitId": "commit-sha-xyz"}]},
            status=201,
        )
        result = azure_devops_adapter.create_or_update_file(
            "new-file.md", content="content", message="Add file"
        )
        req_body = json.loads(mock_responses.calls[1].request.body)
        assert req_body["commits"][0]["comment"] == "Add file"
        assert result == "commit-sha-xyz"


class TestDeleteFile:
    def test_delete(self, mock_responses, azure_devops_adapter):
        # delete_file も refs を GET してから pushes を POST する
        mock_responses.add(
            responses.GET,
            f"{GIT}/refs",
            json={"value": [_branch_data_az(name="main", sha="abc123")], "count": 1},
            status=200,
        )
        mock_responses.add(
            responses.POST,
            f"{GIT}/pushes",
            json={"refUpdates": [], "commits": []},
            status=201,
        )
        azure_devops_adapter.delete_file("to-delete.md", sha="", message="Delete")
        assert mock_responses.calls[1].request.method == "POST"


# --- Webhook/DeployKey/Collaborator: NotSupportedError ---


class TestWebhookNotSupported:
    def test_list_raises(self, azure_devops_adapter):
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.list_webhooks()

    def test_create_raises(self, azure_devops_adapter):
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.create_webhook(url="https://example.com", events=["push"])

    def test_delete_raises(self, azure_devops_adapter):
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.delete_webhook(hook_id=1)


class TestDeployKeyNotSupported:
    def test_list_raises(self, azure_devops_adapter):
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.list_deploy_keys()


class TestCollaboratorNotSupported:
    def test_list_raises(self, azure_devops_adapter):
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.list_collaborators()


# --- Pipeline 系 ---


class TestListPipelines:
    def test_list(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/build/builds",
            json={"value": [_pipeline_data_az()], "count": 1},
            status=200,
        )
        pipelines = azure_devops_adapter.list_pipelines()
        assert len(pipelines) == 1
        assert isinstance(pipelines[0], Pipeline)

    def test_with_ref(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/build/builds",
            json={"value": [_pipeline_data_az()], "count": 1},
            status=200,
        )
        azure_devops_adapter.list_pipelines(ref="main")
        req = mock_responses.calls[0].request
        assert "branchName" in req.url or "refs%2Fheads%2Fmain" in req.url or "main" in req.url


class TestGetPipeline:
    def test_get(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/build/builds/300",
            json=_pipeline_data_az(run_id=300),
            status=200,
        )
        pipeline = azure_devops_adapter.get_pipeline(300)
        assert isinstance(pipeline, Pipeline)
        assert pipeline.id == 300


class TestCancelPipeline:
    def test_cancel(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{BASE}/build/builds/300",
            json=_pipeline_data_az(run_id=300, status="cancelling"),
            status=200,
        )
        azure_devops_adapter.cancel_pipeline(300)
        assert mock_responses.calls[0].request.method == "PATCH"


# --- User / Search 系 ---


class TestGetCurrentUser:
    def test_get(self, mock_responses, azure_devops_adapter):
        # get_current_user は connectionData を使う（組織スコープ URL）
        mock_responses.add(
            responses.GET,
            "https://dev.azure.com/test-org/_apis/connectionData",
            json={"authenticatedUser": {"id": "user-id-123", "providerDisplayName": "testuser"}},
            status=200,
        )
        user = azure_devops_adapter.get_current_user()
        assert user["login"] == "testuser"
        assert user["id"] == "user-id-123"


class TestSearchRepositories:
    def test_search(self, mock_responses, azure_devops_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/git/repositories",
            json={"value": [_repo_data()], "count": 1},
            status=200,
        )
        repos = azure_devops_adapter.search_repositories("test")
        assert isinstance(repos, list)


class TestSearchIssues:
    def test_search(self, mock_responses, azure_devops_adapter):
        # WIQL POST
        mock_responses.add(
            responses.POST,
            f"{BASE}/wit/wiql",
            json={"workItems": [{"id": 1, "url": "..."}]},
            status=200,
        )
        # バッチ GET
        mock_responses.add(
            responses.GET,
            f"{WIT}/workitems",
            json={"value": [_issue_data()], "count": 1},
            status=200,
        )
        issues = azure_devops_adapter.search_issues("bug")
        assert isinstance(issues, list)


# --- 変換メソッドのテスト（追加） ---


class TestToComment:
    def test_basic_comment(self):
        """通常のコメントデータ（comments キーなし）を正常変換する。"""
        data = _comment_data(comment_id=10)
        comment = AzureDevOpsAdapter._to_comment(data)
        assert isinstance(comment, Comment)
        assert comment.id == 10
        assert comment.body == "A comment"
        assert comment.author == "commenter@example.com"

    def test_thread_comment(self):
        """PR Thread 形式（comments 配列を含む）を正常変換する。"""
        data = _thread_data(comment_id=20)
        comment = AzureDevOpsAdapter._to_comment(data)
        assert isinstance(comment, Comment)
        assert comment.id == 20
        assert comment.body == "A comment"
        assert comment.author == "commenter@example.com"

    def test_display_name_fallback(self):
        """author に uniqueName がなく displayName のみの場合のフォールバック。"""
        data = {
            "id": 30,
            "content": "body",
            "author": {"displayName": "Display User"},
            "publishedDate": "2025-01-01T00:00:00Z",
        }
        comment = AzureDevOpsAdapter._to_comment(data)
        assert comment.author == "Display User"


class TestToReview:
    def test_approved(self):
        """vote=10 → approved に変換される。"""
        data = _review_data(vote=10)
        review = AzureDevOpsAdapter._to_review(data)
        assert isinstance(review, Review)
        assert review.state == "approved"
        assert review.author == "reviewer@example.com"

    def test_rejected(self):
        """vote=-10 → changes_requested に変換される。"""
        data = _review_data(vote=-10)
        review = AzureDevOpsAdapter._to_review(data)
        assert review.state == "changes_requested"

    def test_no_vote(self):
        """vote=0 → commented に変換される。"""
        data = _review_data(vote=0)
        review = AzureDevOpsAdapter._to_review(data)
        assert review.state == "commented"

    def test_weak_approved(self):
        """vote=5 → approved に変換される。"""
        data = _review_data(vote=5)
        review = AzureDevOpsAdapter._to_review(data)
        assert review.state == "approved"

    def test_weak_rejected(self):
        """vote=-5 → changes_requested に変換される。"""
        data = _review_data(vote=-5)
        review = AzureDevOpsAdapter._to_review(data)
        assert review.state == "changes_requested"


class TestToBranch:
    def test_basic(self):
        """refs/heads/ プレフィックスを strip して Branch を返す。"""
        data = _branch_data_az(name="feature", sha="abc123")
        branch = AzureDevOpsAdapter._to_branch(data)
        assert isinstance(branch, Branch)
        assert branch.name == "feature"
        assert branch.sha == "abc123"

    def test_name_without_prefix(self):
        """refs/heads/ プレフィックスがない場合もそのまま name を返す。"""
        data = {"name": "main", "objectId": "def456"}
        branch = AzureDevOpsAdapter._to_branch(data)
        assert branch.name == "main"
        assert branch.sha == "def456"


class TestToTag:
    def test_basic(self):
        """refs/tags/ プレフィックスを strip して Tag を返す。"""
        data = _tag_data_az(name="v1.0.0", sha="def456")
        tag = AzureDevOpsAdapter._to_tag(data)
        assert isinstance(tag, Tag)
        assert tag.name == "v1.0.0"
        assert tag.sha == "def456"

    def test_name_without_prefix(self):
        """refs/tags/ プレフィックスがない場合もそのまま name を返す。"""
        data = {"name": "v2.0.0", "objectId": "abc123"}
        tag = AzureDevOpsAdapter._to_tag(data)
        assert tag.name == "v2.0.0"
        assert tag.sha == "abc123"


class TestToCommitStatus:
    def test_basic(self):
        """context.name/genre, state の正常変換。"""
        data = _commit_status_data(state="succeeded", context_name="build", context_genre="ci")
        status = AzureDevOpsAdapter._to_commit_status(data)
        assert isinstance(status, CommitStatus)
        assert status.state == "success"
        assert status.context == "ci/build"
        assert status.description == "Tests passed"

    def test_failed_state(self):
        """state=failed → failure に変換される。"""
        data = _commit_status_data(state="failed", context_name="test", context_genre="")
        status = AzureDevOpsAdapter._to_commit_status(data)
        assert status.state == "failure"
        # genre が空の場合 context は name のみ
        assert status.context == "test"

    def test_pending_state(self):
        """state=pending → pending に変換される。"""
        data = _commit_status_data(state="pending", context_name="build", context_genre="ci")
        status = AzureDevOpsAdapter._to_commit_status(data)
        assert status.state == "pending"


class TestToPipeline:
    def test_completed_succeeded(self):
        """status=completed, result=succeeded → success。"""
        data = _pipeline_data_az(status="completed", result="succeeded")
        pipeline = AzureDevOpsAdapter._to_pipeline(data)
        assert isinstance(pipeline, Pipeline)
        assert pipeline.status == "success"

    def test_completed_failed(self):
        """status=completed, result=failed → failure。"""
        data = _pipeline_data_az(status="completed", result="failed")
        pipeline = AzureDevOpsAdapter._to_pipeline(data)
        assert pipeline.status == "failure"

    def test_in_progress(self):
        """status=inProgress → running。"""
        data = _pipeline_data_az(status="inProgress", result="")
        pipeline = AzureDevOpsAdapter._to_pipeline(data)
        assert pipeline.status == "running"

    def test_not_started(self):
        """status=notStarted → pending。"""
        data = _pipeline_data_az(status="notStarted", result="")
        pipeline = AzureDevOpsAdapter._to_pipeline(data)
        assert pipeline.status == "pending"

    def test_cancelling(self):
        """status=cancelling → cancelled。"""
        data = _pipeline_data_az(status="cancelling", result="")
        pipeline = AzureDevOpsAdapter._to_pipeline(data)
        assert pipeline.status == "cancelled"


class TestDeleteTag:
    def test_basic(self, mock_responses, azure_devops_adapter):
        """refs GET でオブジェクト ID 取得 → refs POST で削除の 2 ステップフロー。"""
        mock_responses.add(
            responses.GET,
            f"{GIT}/refs",
            json={"value": [_tag_data_az(name="v1.0.0", sha="def456")], "count": 1},
            status=200,
        )
        mock_responses.add(
            responses.POST,
            f"{GIT}/refs",
            json=[{"success": True}],
            status=200,
        )
        azure_devops_adapter.delete_tag(name="v1.0.0")
        # POST リクエストのボディに oldObjectId=def456, newObjectId=000...0 を確認（配列形式）
        import json as _json

        post_body = _json.loads(mock_responses.calls[1].request.body)
        ref_update = post_body[0]
        assert ref_update["name"] == "refs/tags/v1.0.0"
        assert ref_update["oldObjectId"] == "def456"
        assert ref_update["newObjectId"] == "0" * 40

    def test_not_found(self, mock_responses, azure_devops_adapter):
        """タグが存在しない場合は NotFoundError を raise する。"""
        mock_responses.add(
            responses.GET,
            f"{GIT}/refs",
            json={"value": [], "count": 0},
            status=200,
        )
        with pytest.raises(NotFoundError):
            azure_devops_adapter.delete_tag(name="nonexistent")
