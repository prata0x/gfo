"""GitBucketAdapter のテスト。"""

from __future__ import annotations

import json as json_mod
from unittest.mock import MagicMock, patch

import pytest
import responses

from gfo.adapter.base import Issue, PullRequest, Release, Repository
from gfo.adapter.gitbucket import GitBucketAdapter
from gfo.adapter.github import GitHubAdapter
from gfo.adapter.registry import get_adapter_class
from gfo.exceptions import AuthenticationError, GfoError, NotFoundError, ServerError

BASE = "https://gitbucket.example.com/api/v3"
REPOS = f"{BASE}/repos/test-owner/test-repo"


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
        "html_url": f"https://gitbucket.example.com/test-owner/test-repo/pulls/{number}",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-02T00:00:00Z",
    }


def _issue_data(*, number=1, state="open"):
    return {
        "number": number,
        "title": f"Issue #{number}",
        "body": "issue body",
        "state": state,
        "user": {"login": "reporter"},
        "assignees": [],
        "labels": [],
        "html_url": f"https://gitbucket.example.com/test-owner/test-repo/issues/{number}",
        "created_at": "2025-01-01T00:00:00Z",
    }


def _repo_data():
    return {
        "name": "test-repo",
        "full_name": "test-owner/test-repo",
        "description": "A test repo",
        "private": False,
        "default_branch": "main",
        "clone_url": "https://gitbucket.example.com/test-owner/test-repo.git",
        "html_url": "https://gitbucket.example.com/test-owner/test-repo",
    }


class TestRegistry:
    def test_registered(self):
        assert get_adapter_class("gitbucket") is GitBucketAdapter


class TestInheritance:
    def test_is_github_adapter(self, gitbucket_adapter):
        assert isinstance(gitbucket_adapter, GitHubAdapter)

    def test_service_name(self, gitbucket_adapter):
        assert gitbucket_adapter.service_name == "GitBucket"

    def test_service_name_not_github(self, gitbucket_adapter):
        assert gitbucket_adapter.service_name != "GitHub"


class TestToPullRequest:
    def test_open(self):
        pr = GitBucketAdapter._to_pull_request(_pr_data())
        assert pr.state == "open"
        assert pr.number == 1
        assert pr.author == "author1"

    def test_closed(self):
        pr = GitBucketAdapter._to_pull_request(_pr_data(state="closed", merged_at=None))
        assert pr.state == "closed"

    def test_merged(self):
        pr = GitBucketAdapter._to_pull_request(
            _pr_data(state="closed", merged_at="2025-01-01T00:00:00Z")
        )
        assert pr.state == "merged"


class TestGitHubApiCompatibility:
    """GitBucketAdapter が GitHub API v3 互換パスを使用することを確認する。"""

    def test_pr_endpoint_uses_github_path(self, mock_responses, gitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls",
            json=[_pr_data()],
            status=200,
        )
        gitbucket_adapter.list_pull_requests()
        assert mock_responses.calls[0].request.url.startswith(f"{REPOS}/pulls")

    def test_pagination_uses_per_page_param(self, mock_responses, gitbucket_adapter):
        """GitHub 互換: ページネーションは per_page= パラメータを使う。"""
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls",
            json=[_pr_data()],
            status=200,
        )
        gitbucket_adapter.list_pull_requests(limit=20)
        req_url = mock_responses.calls[0].request.url
        assert "per_page=" in req_url

    def test_issues_endpoint_uses_github_path(self, mock_responses, gitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues",
            json=[_issue_data()],
            status=200,
        )
        gitbucket_adapter.list_issues()
        assert mock_responses.calls[0].request.url.startswith(f"{REPOS}/issues")

    def test_checkout_refspec_uses_github_format(self, gitbucket_adapter):
        """GitHub 互換: チェックアウト refspec は refs/pull/{n}/head 形式。"""
        assert gitbucket_adapter.get_pr_checkout_refspec(7) == "refs/pull/7/head"

    def test_base_url_uses_api_v3_path(self, gitbucket_adapter):
        """GitBucket は /api/v3 パスを使用する（GitHub の api.github.com とは異なる）。"""
        assert "/api/v3" in gitbucket_adapter._client._base_url


class TestListPullRequests:
    def test_open(self, mock_responses, gitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls",
            json=[_pr_data()],
            status=200,
        )
        prs = gitbucket_adapter.list_pull_requests()
        assert len(prs) == 1
        assert prs[0].state == "open"
        assert prs[0].number == 1

    def test_merged_filter(self, mock_responses, gitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls",
            json=[
                _pr_data(number=1, state="closed", merged_at="2025-01-03T00:00:00Z"),
                _pr_data(number=2, state="closed"),
            ],
            status=200,
        )
        prs = gitbucket_adapter.list_pull_requests(state="merged")
        assert len(prs) == 1
        assert prs[0].number == 1

    def test_pagination(self, mock_responses, gitbucket_adapter):
        next_url = f"{REPOS}/pulls?page=2&per_page=30"
        call_count = {"n": 0}

        def callback(request):
            call_count["n"] += 1
            if call_count["n"] == 1:
                headers = {"Link": f'<{next_url}>; rel="next"'}
                return (200, headers, json_mod.dumps([_pr_data(number=1), _pr_data(number=2)]))
            return (200, {}, json_mod.dumps([_pr_data(number=3)]))

        mock_responses.add_callback(responses.GET, f"{REPOS}/pulls", callback=callback)
        prs = gitbucket_adapter.list_pull_requests(limit=0)
        assert len(prs) == 3
        assert call_count["n"] == 2


class TestCreatePullRequest:
    def test_create(self, mock_responses, gitbucket_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/pulls",
            json=_pr_data(),
            status=201,
        )
        pr = gitbucket_adapter.create_pull_request(
            title="PR #1",
            body="desc",
            base="main",
            head="feature",
        )
        assert isinstance(pr, PullRequest)
        req_body = json_mod.loads(mock_responses.calls[0].request.body)
        assert req_body["draft"] is False

    def test_create_draft(self, mock_responses, gitbucket_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/pulls",
            json=_pr_data(draft=True),
            status=201,
        )
        gitbucket_adapter.create_pull_request(
            title="Draft",
            body="",
            base="main",
            head="feature",
            draft=True,
        )
        req_body = json_mod.loads(mock_responses.calls[0].request.body)
        assert req_body["draft"] is True


class TestGetPullRequest:
    def test_get(self, mock_responses, gitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls/42",
            json=_pr_data(number=42),
            status=200,
        )
        pr = gitbucket_adapter.get_pull_request(42)
        assert pr.number == 42


class TestMergePullRequest:
    def test_merge(self, mock_responses, gitbucket_adapter):
        mock_responses.add(
            responses.PUT,
            f"{REPOS}/pulls/1/merge",
            json={"merged": True},
            status=200,
        )
        gitbucket_adapter.merge_pull_request(1)
        req_body = json_mod.loads(mock_responses.calls[0].request.body)
        assert req_body["merge_method"] == "merge"


class TestClosePullRequest:
    def test_close(self, mock_responses, gitbucket_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/pulls/1",
            json=_pr_data(state="closed"),
            status=200,
        )
        gitbucket_adapter.close_pull_request(1)
        req_body = json_mod.loads(mock_responses.calls[0].request.body)
        assert req_body["state"] == "closed"


class TestListIssues:
    def test_list(self, mock_responses, gitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues",
            json=[_issue_data()],
            status=200,
        )
        issues = gitbucket_adapter.list_issues()
        assert len(issues) == 1
        assert isinstance(issues[0], Issue)

    def test_with_filters(self, mock_responses, gitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues",
            json=[_issue_data()],
            status=200,
        )
        gitbucket_adapter.list_issues(assignee="dev1", label="bug")
        req_url = mock_responses.calls[0].request.url
        assert "assignee=dev1" in req_url
        assert "labels=bug" in req_url


class TestListRepositories:
    def test_no_owner(self, mock_responses, gitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/user/repos",
            json=[_repo_data()],
            status=200,
        )
        repos = gitbucket_adapter.list_repositories()
        assert len(repos) == 1
        assert isinstance(repos[0], Repository)

    def test_with_owner(self, mock_responses, gitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/users/someone/repos",
            json=[_repo_data()],
            status=200,
        )
        repos = gitbucket_adapter.list_repositories(owner="someone")
        assert len(repos) == 1


class TestErrorHandling:
    """HTTP エラーが適切な例外に変換されることを確認する。"""

    def test_not_found_raises_error(self, mock_responses, gitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls/999",
            json={"message": "Not Found"},
            status=404,
        )
        with pytest.raises(NotFoundError):
            gitbucket_adapter.get_pull_request(999)

    def test_auth_error_raises_error(self, mock_responses, gitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls",
            json={"message": "Unauthorized"},
            status=401,
        )
        with pytest.raises(AuthenticationError):
            gitbucket_adapter.list_pull_requests()

    def test_server_error_raises_error(self, mock_responses, gitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues",
            json={"message": "Internal Server Error"},
            status=500,
        )
        with pytest.raises(ServerError):
            gitbucket_adapter.list_issues()


class TestDeleteInheritance:
    """GitHubAdapter から継承した delete メソッドが動作することを確認する。"""

    def test_delete_release(self, mock_responses, gitbucket_adapter):
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
        gitbucket_adapter.delete_release(tag="v1.0.0")

    def test_delete_label(self, mock_responses, gitbucket_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/labels/bug",
            status=204,
        )
        gitbucket_adapter.delete_label(name="bug")

    def test_delete_milestone(self, mock_responses, gitbucket_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/milestones/3",
            status=204,
        )
        gitbucket_adapter.delete_milestone(number=3)

    def test_delete_issue_raises_not_supported(self, gitbucket_adapter):
        """GitBucket は issue delete 未対応（GitHub 継承）→ NotSupportedError。"""
        from gfo.exceptions import NotSupportedError

        with pytest.raises(NotSupportedError):
            gitbucket_adapter.delete_issue(1)

    def test_delete_repository(self, mock_responses, gitbucket_adapter):
        mock_responses.add(
            responses.DELETE,
            REPOS,
            status=204,
        )
        gitbucket_adapter.delete_repository()
        assert mock_responses.calls[0].request.method == "DELETE"


class TestParseResponse:
    """_parse_response のテスト。"""

    def test_dict_returned_as_is(self, gitbucket_adapter):
        resp = MagicMock()
        resp.json.return_value = {"key": "value"}
        assert gitbucket_adapter._parse_response(resp) == {"key": "value"}

    def test_string_json_is_parsed(self, gitbucket_adapter):
        resp = MagicMock()
        resp.json.return_value = '{"tag_name": "v1.0.0"}'
        result = gitbucket_adapter._parse_response(resp)
        assert result == {"tag_name": "v1.0.0"}

    def test_invalid_string_json_raises_gfo_error(self, gitbucket_adapter):
        resp = MagicMock()
        resp.json.return_value = "not valid json {"
        with pytest.raises(GfoError, match="failed to parse"):
            gitbucket_adapter._parse_response(resp)

    def test_non_dict_raises_gfo_error(self, gitbucket_adapter):
        resp = MagicMock()
        resp.json.return_value = [1, 2, 3]
        with pytest.raises(GfoError, match="unexpected response type"):
            gitbucket_adapter._parse_response(resp)


class TestWebBaseUrl:
    """_web_base_url のテスト。"""

    def test_standard_https(self, gitbucket_adapter):
        assert gitbucket_adapter._web_base_url() == "https://gitbucket.example.com"

    def test_non_standard_port_included(self):
        from gfo.http import HttpClient

        client = HttpClient("http://gitbucket.local:8080/api/v3", auth_header={})
        adapter = GitBucketAdapter(client, "owner", "repo")
        assert adapter._web_base_url() == "http://gitbucket.local:8080"

    def test_standard_port_excluded(self):
        from gfo.http import HttpClient

        client = HttpClient("https://gitbucket.example.com:443/api/v3", auth_header={})
        adapter = GitBucketAdapter(client, "owner", "repo")
        assert adapter._web_base_url() == "https://gitbucket.example.com"


class TestCloseIssue:
    """close_issue のテスト（Web UI 経由）。"""

    def _make_session(self, login_status=200, close_status=302):
        session = MagicMock()
        login_resp = MagicMock()
        login_resp.status_code = login_status
        close_resp = MagicMock()
        close_resp.status_code = close_status
        session.post.side_effect = [login_resp, close_resp]
        return session

    def test_close_success(self, gitbucket_adapter):
        session = self._make_session(login_status=200, close_status=302)
        with patch("gfo.adapter.gitbucket._requests.Session", return_value=session):
            gitbucket_adapter.close_issue(1)

    def test_close_success_with_302_login(self, gitbucket_adapter):
        session = self._make_session(login_status=302, close_status=200)
        with patch("gfo.adapter.gitbucket._requests.Session", return_value=session):
            gitbucket_adapter.close_issue(5)

    def test_login_failure_raises_gfo_error(self, gitbucket_adapter):
        session = MagicMock()
        login_resp = MagicMock()
        login_resp.status_code = 500
        session.post.return_value = login_resp
        with patch("gfo.adapter.gitbucket._requests.Session", return_value=session):
            with pytest.raises(GfoError, match="login failed"):
                gitbucket_adapter.close_issue(1)

    def test_close_failure_raises_gfo_error(self, gitbucket_adapter):
        session = self._make_session(login_status=200, close_status=500)
        with patch("gfo.adapter.gitbucket._requests.Session", return_value=session):
            with pytest.raises(GfoError, match="close_issue failed"):
                gitbucket_adapter.close_issue(1)


class TestToRelease:
    """_to_release のテスト。"""

    def test_full_data(self):
        data = {
            "tag_name": "v1.0.0",
            "name": "Release 1.0.0",
            "body": "notes",
            "draft": False,
            "prerelease": False,
            "html_url": "https://gitbucket.example.com/owner/repo/releases/v1.0.0",
            "created_at": "2025-01-01T00:00:00Z",
        }
        rel = GitBucketAdapter._to_release(data)
        assert isinstance(rel, Release)
        assert rel.tag == "v1.0.0"
        assert rel.title == "Release 1.0.0"
        assert rel.url == "https://gitbucket.example.com/owner/repo/releases/v1.0.0"
        assert rel.created_at == "2025-01-01T00:00:00Z"

    def test_missing_optional_fields_fall_back_to_empty(self):
        data = {"tag_name": "v1.0.0"}
        rel = GitBucketAdapter._to_release(data)
        assert rel.url == ""
        assert rel.created_at == ""
        assert rel.title == ""

    def test_missing_tag_name_raises_gfo_error(self):
        with pytest.raises(GfoError):
            GitBucketAdapter._to_release({})


class TestCreateRelease:
    """create_release のテスト（二重エンコード JSON 対応）。"""

    def _release_payload(self, tag="v1.0.0"):
        return {
            "tag_name": tag,
            "name": f"Release {tag}",
            "body": "",
            "draft": False,
            "prerelease": False,
        }

    def test_create_normal_json(self, mock_responses, gitbucket_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/releases",
            json=self._release_payload(),
            status=201,
        )
        rel = gitbucket_adapter.create_release(tag="v1.0.0", title="Release v1.0.0")
        assert isinstance(rel, Release)
        assert rel.tag == "v1.0.0"

    def test_create_double_encoded_json(self, mock_responses, gitbucket_adapter):
        """GitBucket がレスポンスを JSON 文字列として二重エンコードする場合。"""
        inner = json_mod.dumps(self._release_payload())
        mock_responses.add(
            responses.POST,
            f"{REPOS}/releases",
            body=json_mod.dumps(inner),
            content_type="application/json",
            status=201,
        )
        rel = gitbucket_adapter.create_release(tag="v1.0.0", title="Release v1.0.0")
        assert rel.tag == "v1.0.0"
