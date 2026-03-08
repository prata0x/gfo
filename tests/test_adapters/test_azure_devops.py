"""AzureDevOpsAdapter のテスト。"""

from __future__ import annotations

import json

import pytest
import responses

from gfo.adapter.base import Issue, PullRequest, Repository
from gfo.adapter.azure_devops import (
    AzureDevOpsAdapter,
    _add_refs_prefix,
    _strip_refs_prefix,
)
from gfo.adapter.registry import get_adapter_class
from gfo.exceptions import NotSupportedError


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

    def test_no_tags(self):
        data = _issue_data()
        data["fields"]["System.Tags"] = ""
        issue = AzureDevOpsAdapter._to_issue(data)
        assert issue.labels == []


class TestToRepository:
    def test_basic(self, azure_devops_adapter):
        repo = azure_devops_adapter._to_repository(_repo_data())
        assert repo.name == "test-repo"
        assert repo.full_name == "test-project/test-repo"
        assert repo.private is True
        assert repo.default_branch == "main"
        assert "test-repo" in repo.clone_url

    def test_no_default_branch(self, azure_devops_adapter):
        data = _repo_data()
        data["defaultBranch"] = ""
        repo = azure_devops_adapter._to_repository(data)
        assert repo.default_branch == ""


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
        assert azure_devops_adapter.get_pr_checkout_refspec(42) == "pull/42/head"


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
