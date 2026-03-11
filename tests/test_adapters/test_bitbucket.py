"""BitbucketAdapter のテスト。"""

from __future__ import annotations

import json
from urllib.parse import unquote, unquote_plus

import pytest
import responses

from gfo.adapter.base import (
    Branch,
    Comment,
    CommitStatus,
    DeployKey,
    Issue,
    Pipeline,
    PullRequest,
    Repository,
    Review,
    Tag,
    Webhook,
)
from gfo.adapter.bitbucket import BitbucketAdapter
from gfo.adapter.registry import get_adapter_class
from gfo.exceptions import AuthenticationError, NotFoundError, NotSupportedError, ServerError

BASE = "https://api.bitbucket.org/2.0"
REPOS = f"{BASE}/repositories/test-workspace/test-repo"


# --- サンプルデータ ---


def _pr_data(*, id=1, state="OPEN"):
    return {
        "id": id,
        "title": f"PR #{id}",
        "description": "pr description",
        "state": state,
        "author": {"nickname": "author1"},
        "source": {"branch": {"name": "feature"}},
        "destination": {"branch": {"name": "main"}},
        "links": {
            "html": {"href": f"https://bitbucket.org/test-workspace/test-repo/pull-requests/{id}"}
        },
        "created_on": "2025-01-01T00:00:00Z",
        "updated_on": "2025-01-02T00:00:00Z",
    }


def _issue_data(*, id=1, state="new"):
    return {
        "id": id,
        "title": f"Issue #{id}",
        "content": {"raw": "issue body"},
        "state": state,
        "reporter": {"nickname": "reporter1"},
        "assignee": {"nickname": "dev1"},
        "links": {"html": {"href": f"https://bitbucket.org/test-workspace/test-repo/issues/{id}"}},
        "created_on": "2025-01-01T00:00:00Z",
    }


def _repo_data(*, slug="test-repo", full_name="test-workspace/test-repo"):
    return {
        "slug": slug,
        "full_name": full_name,
        "description": "A test repo",
        "is_private": False,
        "mainbranch": {"name": "main"},
        "links": {
            "clone": [
                {"name": "https", "href": f"https://bitbucket.org/{full_name}.git"},
                {"name": "ssh", "href": f"git@bitbucket.org:{full_name}.git"},
            ],
            "html": {"href": f"https://bitbucket.org/{full_name}"},
        },
    }


# --- 変換メソッドのテスト ---


class TestToPullRequest:
    def test_open(self):
        pr = BitbucketAdapter._to_pull_request(_pr_data())
        assert pr.state == "open"
        assert pr.number == 1
        assert pr.author == "author1"
        assert pr.source_branch == "feature"
        assert pr.target_branch == "main"
        assert pr.draft is False

    def test_declined(self):
        pr = BitbucketAdapter._to_pull_request(_pr_data(state="DECLINED"))
        assert pr.state == "closed"

    def test_superseded(self):
        pr = BitbucketAdapter._to_pull_request(_pr_data(state="SUPERSEDED"))
        assert pr.state == "closed"

    def test_merged(self):
        pr = BitbucketAdapter._to_pull_request(_pr_data(state="MERGED"))
        assert pr.state == "merged"


class TestToIssue:
    def test_new(self):
        issue = BitbucketAdapter._to_issue(_issue_data())
        assert issue.number == 1
        assert issue.state == "open"
        assert issue.body == "issue body"
        assert issue.author == "reporter1"
        assert issue.assignees == ["dev1"]
        assert issue.labels == []

    def test_open_state(self):
        issue = BitbucketAdapter._to_issue(_issue_data(state="open"))
        assert issue.state == "open"

    def test_closed_state(self):
        issue = BitbucketAdapter._to_issue(_issue_data(state="closed"))
        assert issue.state == "closed"

    def test_no_assignee(self):
        data = _issue_data()
        data["assignee"] = None
        issue = BitbucketAdapter._to_issue(data)
        assert issue.assignees == []

    def test_assignee_without_nickname(self):
        """assignee が nickname を持たない場合は空リストを返す。"""
        data = _issue_data()
        data["assignee"] = {"display_name": "User Name"}
        issue = BitbucketAdapter._to_issue(data)
        assert issue.assignees == []

    def test_non_dict_content_raises_gfo_error(self):
        """content が dict 以外の truthy 値のとき AttributeError でなく GfoError になる。"""
        from gfo.exceptions import GfoError

        data = _issue_data()
        data["content"] = "not a dict"
        with pytest.raises(GfoError):
            BitbucketAdapter._to_issue(data)


class TestToRepository:
    def test_basic(self):
        repo = BitbucketAdapter._to_repository(_repo_data())
        assert repo.name == "test-repo"
        assert repo.full_name == "test-workspace/test-repo"
        assert repo.private is False
        assert repo.default_branch == "main"
        assert "https" in repo.clone_url

    def test_no_mainbranch(self):
        data = _repo_data()
        data["mainbranch"] = None
        repo = BitbucketAdapter._to_repository(data)
        assert repo.default_branch is None

    def test_null_links_raises_gfo_error_not_attribute_error(self):
        """links フィールドが null のとき AttributeError でなく GfoError が発生する。"""
        from gfo.exceptions import GfoError

        data = _repo_data()
        data["links"] = None
        with pytest.raises(GfoError):
            BitbucketAdapter._to_repository(data)


# --- PR 系 ---


class TestListPullRequests:
    def test_open(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pullrequests",
            json={"values": [_pr_data()], "next": None},
            status=200,
        )
        prs = bitbucket_adapter.list_pull_requests()
        assert len(prs) == 1
        assert prs[0].state == "open"
        req = mock_responses.calls[0].request
        assert "state=OPEN" in req.url

    def test_merged_filter(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pullrequests",
            json={"values": [_pr_data(state="MERGED")]},
            status=200,
        )
        prs = bitbucket_adapter.list_pull_requests(state="merged")
        assert len(prs) == 1
        assert prs[0].state == "merged"
        req = mock_responses.calls[0].request
        assert "state=MERGED" in req.url

    def test_all_state_omits_filter(self, mock_responses, bitbucket_adapter):
        """state='all' のとき state パラメータを送らない。"""
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pullrequests",
            json={"values": [_pr_data(), _pr_data(id=2, state="MERGED")]},
            status=200,
        )
        prs = bitbucket_adapter.list_pull_requests(state="all")
        assert len(prs) == 2
        req = mock_responses.calls[0].request
        assert "state=" not in req.url

    def test_pagination(self, mock_responses, bitbucket_adapter):
        page2_url = f"{REPOS}/pullrequests?state=OPEN&page=2"
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pullrequests",
            json={"values": [_pr_data(id=1)], "next": page2_url},
            status=200,
        )
        mock_responses.add(
            responses.GET,
            page2_url,
            json={"values": [_pr_data(id=2)]},
            status=200,
        )
        prs = bitbucket_adapter.list_pull_requests(limit=10)
        assert len(prs) == 2

    def test_pagination_stops_on_different_origin(self, mock_responses, bitbucket_adapter):
        """next URL が別オリジンを指す場合はページネーションを中断する（SSRF 防止）。"""
        other_origin_url = "https://evil.example.com/api/pullrequests?page=2"
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pullrequests",
            json={"values": [_pr_data(id=1)], "next": other_origin_url},
            status=200,
        )
        prs = bitbucket_adapter.list_pull_requests(limit=10)
        # 別オリジンへのリクエストは行われず、1件のみ返る
        assert len(prs) == 1
        assert len(mock_responses.calls) == 1


class TestCreatePullRequest:
    def test_create(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/pullrequests",
            json=_pr_data(),
            status=201,
        )
        pr = bitbucket_adapter.create_pull_request(
            title="PR #1",
            body="desc",
            base="main",
            head="feature",
        )
        assert isinstance(pr, PullRequest)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["source"]["branch"]["name"] == "feature"
        assert req_body["destination"]["branch"]["name"] == "main"


class TestCreatePullRequestDescription:
    def test_create_with_description(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/pullrequests",
            json=_pr_data(),
            status=201,
        )
        bitbucket_adapter.create_pull_request(
            title="PR",
            body="Description text",
            base="main",
            head="feature",
        )
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["description"] == "Description text"


class TestGetPullRequest:
    def test_get(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pullrequests/42",
            json=_pr_data(id=42),
            status=200,
        )
        pr = bitbucket_adapter.get_pull_request(42)
        assert pr.number == 42


class TestMergePullRequest:
    def test_merge(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/pullrequests/1/merge",
            json={"state": "MERGED"},
            status=200,
        )
        bitbucket_adapter.merge_pull_request(1)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["merge_strategy"] == "merge_commit"

    def test_squash_method(self, mock_responses, bitbucket_adapter):
        """method='squash' → merge_strategy='squash' がリクエストに含まれる。"""
        mock_responses.add(
            responses.POST,
            f"{REPOS}/pullrequests/1/merge",
            json={"state": "MERGED"},
            status=200,
        )
        bitbucket_adapter.merge_pull_request(1, method="squash")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["merge_strategy"] == "squash"

    def test_rebase_method(self, mock_responses, bitbucket_adapter):
        """method='rebase' → merge_strategy='fast_forward' がリクエストに含まれる。"""
        mock_responses.add(
            responses.POST,
            f"{REPOS}/pullrequests/1/merge",
            json={"state": "MERGED"},
            status=200,
        )
        bitbucket_adapter.merge_pull_request(1, method="rebase")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["merge_strategy"] == "fast_forward"


class TestClosePullRequest:
    def test_close(self, mock_responses, bitbucket_adapter):
        """close_pull_request は POST .../decline エンドポイントを使用する（R34修正確認）。"""
        mock_responses.add(
            responses.POST,
            f"{REPOS}/pullrequests/1/decline",
            json=_pr_data(state="DECLINED"),
            status=200,
        )
        bitbucket_adapter.close_pull_request(1)
        assert mock_responses.calls[0].request.method == "POST"
        assert "/decline" in mock_responses.calls[0].request.url


class TestCheckoutRefspec:
    def test_with_pr(self, bitbucket_adapter):
        pr = BitbucketAdapter._to_pull_request(_pr_data())
        assert bitbucket_adapter.get_pr_checkout_refspec(1, pr=pr) == "feature"

    def test_without_pr(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pullrequests/1",
            json=_pr_data(),
            status=200,
        )
        assert bitbucket_adapter.get_pr_checkout_refspec(1) == "feature"


# --- Issue 系 ---


class TestListIssues:
    def test_list(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues",
            json={"values": [_issue_data(id=1), _issue_data(id=2)]},
            status=200,
        )
        issues = bitbucket_adapter.list_issues()
        assert len(issues) == 2

    def test_closed_state_filter(self, mock_responses, bitbucket_adapter):
        """state='closed' のとき q に resolved 等の全非 open 状態を包含するフィルタが追加される。"""
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues",
            json={"values": [_issue_data(state="resolved")]},
            status=200,
        )
        issues = bitbucket_adapter.list_issues(state="closed")
        assert len(issues) == 1
        req = mock_responses.calls[0].request
        # unquote_plus: クエリ文字列の + をスペースに戻して比較する
        decoded_url = unquote_plus(req.url)
        # close_issue が state="resolved" を使うため、resolved も含む NOT IN open 形式で問い合わせる
        assert 'state != "new"' in decoded_url
        assert 'state != "open"' in decoded_url

    def test_all_state_omits_filter(self, mock_responses, bitbucket_adapter):
        """state='all' のとき q フィルタを送らない。"""
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues",
            json={"values": [_issue_data(id=1), _issue_data(id=2)]},
            status=200,
        )
        issues = bitbucket_adapter.list_issues(state="all")
        assert len(issues) == 2
        req = mock_responses.calls[0].request
        assert "q=" not in req.url

    def test_assignee_filter(self, mock_responses, bitbucket_adapter):
        """assignee を指定すると q に assignee.nickname フィルタが追加される。"""
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues",
            json={"values": [_issue_data()]},
            status=200,
        )
        bitbucket_adapter.list_issues(state="open", assignee="alice")
        req = mock_responses.calls[0].request
        decoded_url = unquote(req.url)
        assert 'assignee.nickname="alice"' in decoded_url
        assert 'state="new"' in decoded_url

    def test_assignee_filter_with_all_state(self, mock_responses, bitbucket_adapter):
        """state='all' + assignee のとき state フィルタなしで assignee のみ含まれる。"""
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues",
            json={"values": [_issue_data()]},
            status=200,
        )
        bitbucket_adapter.list_issues(state="all", assignee="bob")
        req = mock_responses.calls[0].request
        decoded_url = unquote(req.url)
        assert 'assignee.nickname="bob"' in decoded_url
        assert 'state="' not in decoded_url

    def test_label_filter(self, mock_responses, bitbucket_adapter):
        """label を指定すると q に component.name フィルタが追加される。"""
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues",
            json={"values": [_issue_data()]},
            status=200,
        )
        bitbucket_adapter.list_issues(state="all", label="bug")
        req = mock_responses.calls[0].request
        decoded_url = unquote(req.url)
        assert 'component.name="bug"' in decoded_url

    def test_custom_state_filter(self, mock_responses, bitbucket_adapter):
        """state が open/closed/all 以外の場合、その値をそのままフィルタに使う。"""
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues",
            json={"values": [_issue_data(state="resolved")]},
            status=200,
        )
        bitbucket_adapter.list_issues(state="resolved")
        req = mock_responses.calls[0].request
        decoded_url = unquote(req.url)
        assert 'state="resolved"' in decoded_url


class TestCreateIssue:
    def test_create(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/issues",
            json=_issue_data(),
            status=201,
        )
        issue = bitbucket_adapter.create_issue(title="Issue #1", body="body")
        assert isinstance(issue, Issue)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["content"]["raw"] == "body"
        assert "assignee" not in req_body

    def test_create_with_assignee(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/issues",
            json=_issue_data(),
            status=201,
        )
        bitbucket_adapter.create_issue(title="Issue", assignee="dev1")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["assignee"]["nickname"] == "dev1"

    def test_create_with_label_sets_component(self, mock_responses, bitbucket_adapter):
        """label を指定すると payload に component.name が設定される。"""
        mock_responses.add(
            responses.POST,
            f"{REPOS}/issues",
            json=_issue_data(),
            status=201,
        )
        bitbucket_adapter.create_issue(title="Issue", label="bug")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["component"]["name"] == "bug"

    def test_to_issue_with_component_maps_to_labels(self):
        """API レスポンスに component があるとき labels に変換される。"""
        data = _issue_data()
        data["component"] = {"name": "bug"}
        issue = BitbucketAdapter._to_issue(data)
        assert issue.labels == ["bug"]

    def test_to_issue_without_component_has_empty_labels(self):
        """component がないとき labels は空リスト。"""
        issue = BitbucketAdapter._to_issue(_issue_data())
        assert issue.labels == []

    def test_to_issue_with_null_content_returns_none_body(self):
        """API が content: null を返しても AttributeError にならない。"""
        data = _issue_data()
        data["content"] = None
        issue = BitbucketAdapter._to_issue(data)
        assert issue.body is None


class TestGetIssue:
    def test_get(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues/5",
            json=_issue_data(id=5),
            status=200,
        )
        issue = bitbucket_adapter.get_issue(5)
        assert issue.number == 5


class TestCloseIssue:
    def test_close(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.PUT,
            f"{REPOS}/issues/3",
            json=_issue_data(id=3, state="resolved"),
            status=200,
        )
        bitbucket_adapter.close_issue(3)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["state"] == "resolved"


class TestDeleteIssue:
    def test_delete(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/issues/7",
            status=204,
        )
        bitbucket_adapter.delete_issue(7)
        assert mock_responses.calls[0].request.method == "DELETE"
        assert mock_responses.calls[0].request.url.endswith("/issues/7")


# --- Repository 系 ---


class TestListRepositories:
    def test_with_owner(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/repositories/someone",
            json={"values": [_repo_data()]},
            status=200,
        )
        repos = bitbucket_adapter.list_repositories(owner="someone")
        assert len(repos) == 1

    def test_no_owner(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/repositories/test-workspace",
            json={"values": [_repo_data()]},
            status=200,
        )
        repos = bitbucket_adapter.list_repositories()
        assert len(repos) == 1

    def test_owner_with_slash_is_encoded(self, mock_responses, bitbucket_adapter):
        """list_repositories(owner="org/sub") でスラッシュが URL エンコードされる（R42-01）。"""
        mock_responses.add(
            responses.GET,
            f"{BASE}/repositories/org%2Fsub",
            json={"values": [_repo_data()]},
            status=200,
        )
        bitbucket_adapter.list_repositories(owner="org/sub")
        assert "%2F" in mock_responses.calls[0].request.url


class TestCreateRepository:
    def test_create(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.POST,
            f"{BASE}/repositories/test-workspace/new-repo",
            json=_repo_data(slug="new-repo", full_name="test-workspace/new-repo"),
            status=201,
        )
        repo = bitbucket_adapter.create_repository(name="new-repo")
        assert isinstance(repo, Repository)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["scm"] == "git"
        assert req_body["is_private"] is False

    def test_name_with_slash_is_encoded(self, mock_responses, bitbucket_adapter):
        """create_repository で name のスラッシュが URL エンコードされる（R42-01）。"""
        mock_responses.add(
            responses.POST,
            f"{BASE}/repositories/test-workspace/my%2Frepo",
            json=_repo_data(slug="my/repo", full_name="test-workspace/my/repo"),
            status=201,
        )
        bitbucket_adapter.create_repository(name="my/repo")
        assert "%2F" in mock_responses.calls[0].request.url


class TestGetRepository:
    def test_get(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/repositories/other/other-repo",
            json=_repo_data(slug="other-repo", full_name="other/other-repo"),
            status=200,
        )
        repo = bitbucket_adapter.get_repository(owner="other", name="other-repo")
        assert repo.name == "other-repo"

    def test_get_defaults(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}",
            json=_repo_data(),
            status=200,
        )
        repo = bitbucket_adapter.get_repository()
        assert repo.full_name == "test-workspace/test-repo"

    def test_get_owner_with_slash_is_encoded(self, mock_responses, bitbucket_adapter):
        """get_repository(owner="org/sub") でスラッシュが URL エンコードされる（R42-01）。"""
        mock_responses.add(
            responses.GET,
            f"{BASE}/repositories/org%2Fsub/test-repo",
            json=_repo_data(slug="test-repo", full_name="org/sub/test-repo"),
            status=200,
        )
        bitbucket_adapter.get_repository(owner="org/sub", name="test-repo")
        assert "%2F" in mock_responses.calls[0].request.url

    def test_repos_path_is_url_encoded(self, mock_responses):
        """owner/repo に特殊文字が含まれる場合に URL エンコードされる（R33-03）。"""
        from gfo.adapter.bitbucket import BitbucketAdapter
        from gfo.http import HttpClient

        client = HttpClient("https://api.bitbucket.org/2.0", basic_auth=("u", "p"))
        adapter = BitbucketAdapter(client, "my workspace", "my repo")
        mock_responses.add(
            responses.GET,
            f"{BASE}/repositories/my%20workspace/my%20repo",
            json=_repo_data(slug="my repo", full_name="my workspace/my repo"),
            status=200,
        )
        repo = adapter.get_repository()
        assert repo.name == "my repo"


# --- NotSupportedError ---


class TestNotSupported:
    def test_list_releases(self, bitbucket_adapter):
        with pytest.raises(NotSupportedError):
            bitbucket_adapter.list_releases()

    def test_create_release(self, bitbucket_adapter):
        with pytest.raises(NotSupportedError):
            bitbucket_adapter.create_release(tag="v1.0")

    def test_list_labels(self, bitbucket_adapter):
        with pytest.raises(NotSupportedError):
            bitbucket_adapter.list_labels()

    def test_create_label(self, bitbucket_adapter):
        with pytest.raises(NotSupportedError):
            bitbucket_adapter.create_label(name="bug")

    def test_list_milestones(self, bitbucket_adapter):
        with pytest.raises(NotSupportedError):
            bitbucket_adapter.list_milestones()

    def test_create_milestone(self, bitbucket_adapter):
        with pytest.raises(NotSupportedError):
            bitbucket_adapter.create_milestone(title="v1.0")


# --- Registry ---


class TestRegistry:
    def test_registered(self):
        assert get_adapter_class("bitbucket") is BitbucketAdapter


class TestErrorHandling:
    """HTTP エラーが適切な例外に変換されることを確認する。"""

    def test_not_found_raises_error(self, mock_responses, bitbucket_adapter):
        mock_responses.add(responses.GET, f"{REPOS}/pullrequests/999", status=404)
        with pytest.raises(NotFoundError):
            bitbucket_adapter.get_pull_request(999)

    def test_401_raises_auth_error(self, mock_responses, bitbucket_adapter):
        mock_responses.add(responses.GET, f"{REPOS}/pullrequests", status=401)
        with pytest.raises(AuthenticationError):
            bitbucket_adapter.list_pull_requests()

    def test_500_raises_server_error(self, mock_responses, bitbucket_adapter):
        mock_responses.add(responses.GET, f"{REPOS}/issues", status=500)
        with pytest.raises(ServerError):
            bitbucket_adapter.list_issues()

    def test_malformed_pr_raises_gfo_error(self, mock_responses, bitbucket_adapter):
        """_to_pull_request で必須フィールド欠落 → GfoError。"""
        from gfo.exceptions import GfoError

        mock_responses.add(
            responses.GET,
            f"{REPOS}/pullrequests/1",
            json={"incomplete": True},
            status=200,
        )
        with pytest.raises(GfoError):
            bitbucket_adapter.get_pull_request(1)

    def test_malformed_issue_raises_gfo_error(self, mock_responses, bitbucket_adapter):
        """_to_issue で必須フィールド欠落 → GfoError。"""
        from gfo.exceptions import GfoError

        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues",
            json={"values": [{"incomplete": True}], "next": None},
            status=200,
        )
        with pytest.raises(GfoError):
            bitbucket_adapter.list_issues()

    def test_malformed_repository_raises_gfo_error(self, mock_responses, bitbucket_adapter):
        """_to_repository で必須フィールド欠落 → GfoError。"""
        from gfo.exceptions import GfoError

        mock_responses.add(
            responses.GET,
            f"{REPOS}",
            json={"incomplete": True},
            status=200,
        )
        with pytest.raises(GfoError):
            bitbucket_adapter.get_repository()


class TestDeleteRepository:
    def test_delete(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.DELETE,
            REPOS,
            status=204,
        )
        bitbucket_adapter.delete_repository()
        assert mock_responses.calls[0].request.method == "DELETE"


# --- サンプルデータ（拡張） ---


def _comment_data(*, comment_id=10):
    return {
        "id": comment_id,
        "content": {"raw": "A comment"},
        "user": {"nickname": "commenter"},
        "links": {
            "html": {
                "href": "https://bitbucket.org/test-workspace/test-repo/issues/1/_/diff#comment-10"
            }
        },
        "created_on": "2025-01-01T00:00:00Z",
        "updated_on": "2025-01-02T00:00:00Z",
    }


def _review_data_participants():
    """PR の participants を含む PR レスポンス。"""
    return {
        **_pr_data(),
        "participants": [
            {"user": {"nickname": "reviewer1"}, "approved": True, "role": "REVIEWER"},
            {"user": {"nickname": "author1"}, "approved": False, "role": "AUTHOR"},
        ],
    }


def _branch_data(*, name="feature", sha="abc123"):
    return {
        "name": name,
        "target": {"hash": sha},
        "links": {"html": {"href": f"https://bitbucket.org/test-workspace/test-repo/src/{name}"}},
    }


def _tag_data(*, name="v1.0.0", sha="def456"):
    return {
        "name": name,
        "target": {"hash": sha},
        "message": "Release",
    }


def _commit_status_data(*, state="SUCCESSFUL", key="ci/test"):
    return {
        "state": state,
        "key": key,
        "description": "Tests passed",
        "url": "https://ci.example.com/build/1",
        "created_on": "2025-01-01T00:00:00Z",
    }


def _webhook_data(*, hook_id="{abc-123}"):
    return {
        "uuid": hook_id,
        "url": "https://example.com/hook",
        "events": ["repo:push"],
        "active": True,
    }


def _deploy_key_data(*, key_id=200):
    return {
        "id": key_id,
        "label": "Deploy Key",
        "key": "ssh-rsa AAAA...",
        "can_push": False,
    }


def _pipeline_data(*, pipeline_id=300):
    return {
        "uuid": str(pipeline_id),
        "state": {
            "name": "COMPLETED",
            "result": {"name": "SUCCESSFUL"},
        },
        "target": {"ref_name": "main"},
        "links": {
            "self": {
                "href": f"https://bitbucket.org/test-workspace/test-repo/addon/pipelines/home#!/results/{pipeline_id}"
            }
        },
        "created_on": "2025-01-01T00:00:00Z",
    }


# --- Comment 系 ---


class TestListComments:
    def test_list_issue(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues/1/comments",
            json={"values": [_comment_data()], "pagelen": 10},
            status=200,
        )
        comments = bitbucket_adapter.list_comments("issue", 1)
        assert len(comments) == 1
        assert isinstance(comments[0], Comment)
        assert comments[0].body == "A comment"

    def test_list_pr(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pullrequests/1/comments",
            json={"values": [_comment_data()], "pagelen": 10},
            status=200,
        )
        comments = bitbucket_adapter.list_comments("pr", 1)
        assert len(comments) == 1


class TestCreateComment:
    def test_create(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/issues/1/comments",
            json=_comment_data(),
            status=201,
        )
        comment = bitbucket_adapter.create_comment("issue", 1, body="A comment")
        assert isinstance(comment, Comment)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["content"]["raw"] == "A comment"


class TestUpdateComment:
    def test_update_issue_raises_not_supported(self, bitbucket_adapter):
        # Bitbucket issue comment update には URL に issue_number が必要なため NSE
        with pytest.raises(NotSupportedError):
            bitbucket_adapter.update_comment("issue", 10, body="Updated")

    def test_update_pr_raises_not_supported(self, bitbucket_adapter):
        with pytest.raises(NotSupportedError):
            bitbucket_adapter.update_comment("pr", 10, body="Updated")


class TestDeleteComment:
    def test_delete_issue_raises_not_supported(self, bitbucket_adapter):
        # Bitbucket issue comment delete には URL に issue_number が必要なため NSE
        with pytest.raises(NotSupportedError):
            bitbucket_adapter.delete_comment("issue", 10)

    def test_delete_pr_raises_not_supported(self, bitbucket_adapter):
        with pytest.raises(NotSupportedError):
            bitbucket_adapter.delete_comment("pr", 10)


# --- PR Update / Issue Update ---


class TestUpdatePullRequest:
    def test_update_title(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.PUT,
            f"{REPOS}/pullrequests/1",
            json=_pr_data(),
            status=200,
        )
        pr = bitbucket_adapter.update_pull_request(1, title="New Title")
        assert isinstance(pr, PullRequest)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["title"] == "New Title"

    def test_update_base(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.PUT,
            f"{REPOS}/pullrequests/1",
            json=_pr_data(),
            status=200,
        )
        bitbucket_adapter.update_pull_request(1, base="develop")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["destination"]["branch"]["name"] == "develop"


class TestUpdateIssue:
    def test_update_title(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.PUT,
            f"{REPOS}/issues/1",
            json=_issue_data(),
            status=200,
        )
        issue = bitbucket_adapter.update_issue(1, title="New Title")
        assert isinstance(issue, Issue)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["title"] == "New Title"

    def test_update_assignee(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.PUT,
            f"{REPOS}/issues/1",
            json=_issue_data(),
            status=200,
        )
        bitbucket_adapter.update_issue(1, assignee="devuser")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["assignee"]["nickname"] == "devuser"


# --- Review 系 ---


class TestListReviews:
    def test_list(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pullrequests/1",
            json=_review_data_participants(),
            status=200,
        )
        reviews = bitbucket_adapter.list_reviews(1)
        assert len(reviews) == 1
        assert isinstance(reviews[0], Review)
        assert reviews[0].state == "approved"


class TestCreateReview:
    def test_approve(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/pullrequests/1/approve",
            json={"approved": True, "user": {"nickname": "reviewer"}},
            status=200,
        )
        bitbucket_adapter.create_review(1, state="approve")
        assert mock_responses.calls[0].request.method == "POST"

    def test_request_changes(self, mock_responses, bitbucket_adapter):
        """REQUEST_CHANGES 分岐は /request-changes エンドポイントを呼ぶ。"""
        mock_responses.add(
            responses.POST,
            f"{REPOS}/pullrequests/1/request-changes",
            json={},
            status=200,
        )
        review = bitbucket_adapter.create_review(1, state="REQUEST_CHANGES", body="Needs work")
        assert review.state == "changes_requested"
        assert mock_responses.calls[0].request.method == "POST"


# --- Branch 系 ---


class TestListBranches:
    def test_list(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/refs/branches",
            json={"values": [_branch_data()], "pagelen": 10},
            status=200,
        )
        branches = bitbucket_adapter.list_branches()
        assert len(branches) == 1
        assert isinstance(branches[0], Branch)
        assert branches[0].name == "feature"


class TestCreateBranch:
    def test_create(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/refs/branches",
            json=_branch_data(name="new-branch"),
            status=201,
        )
        branch = bitbucket_adapter.create_branch(name="new-branch", ref="abc123")
        assert isinstance(branch, Branch)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["name"] == "new-branch"
        assert req_body["target"]["hash"] == "abc123"


class TestDeleteBranch:
    def test_delete(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/refs/branches/feature",
            status=204,
        )
        bitbucket_adapter.delete_branch(name="feature")
        assert mock_responses.calls[0].request.method == "DELETE"


# --- Tag 系 ---


class TestListTags:
    def test_list(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/refs/tags",
            json={"values": [_tag_data()], "pagelen": 10},
            status=200,
        )
        tags = bitbucket_adapter.list_tags()
        assert len(tags) == 1
        assert isinstance(tags[0], Tag)
        assert tags[0].name == "v1.0.0"


class TestCreateTag:
    def test_create(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/refs/tags",
            json=_tag_data(name="v2.0.0"),
            status=201,
        )
        tag = bitbucket_adapter.create_tag(name="v2.0.0", ref="abc123")
        assert isinstance(tag, Tag)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["name"] == "v2.0.0"


class TestDeleteTag:
    def test_delete(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/refs/tags/v1.0.0",
            status=204,
        )
        bitbucket_adapter.delete_tag(name="v1.0.0")
        assert mock_responses.calls[0].request.method == "DELETE"


# --- CommitStatus 系 ---


class TestListCommitStatuses:
    def test_list(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/commit/abc123/statuses",
            json={"values": [_commit_status_data()], "pagelen": 10},
            status=200,
        )
        statuses = bitbucket_adapter.list_commit_statuses("abc123")
        assert len(statuses) == 1
        assert isinstance(statuses[0], CommitStatus)
        assert statuses[0].state == "success"


class TestCreateCommitStatus:
    def test_create(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/commit/abc123/statuses/build",
            json=_commit_status_data(),
            status=201,
        )
        status = bitbucket_adapter.create_commit_status(
            "abc123", state="success", context="ci/test"
        )
        assert isinstance(status, CommitStatus)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["state"] == "SUCCESSFUL"
        assert req_body["key"] == "ci/test"


# --- File 系 ---


class TestGetFileContent:
    def test_get(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/src/main/README.md",
            body="file content",
            status=200,
        )
        content, sha = bitbucket_adapter.get_file_content("README.md", ref="main")
        assert content == "file content"
        assert sha == ""


class TestCreateOrUpdateFile:
    def test_create(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/src",
            status=201,
        )
        bitbucket_adapter.create_or_update_file(
            "new-file.md", content="new content", message="Add file"
        )
        assert mock_responses.calls[0].request.method == "POST"


class TestDeleteFile:
    def test_delete(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/src",
            status=201,
        )
        bitbucket_adapter.delete_file("to-delete.md", sha="", message="Delete file")
        assert mock_responses.calls[0].request.method == "POST"


# --- Fork 系 ---


class TestForkRepository:
    def test_fork(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/forks",
            json=_repo_data(),
            status=201,
        )
        repo = bitbucket_adapter.fork_repository()
        assert isinstance(repo, Repository)

    def test_fork_with_org(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/forks",
            json=_repo_data(),
            status=201,
        )
        bitbucket_adapter.fork_repository(organization="myworkspace")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["workspace"]["slug"] == "myworkspace"


# --- Webhook 系 ---


class TestListWebhooks:
    def test_list(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/hooks",
            json={"values": [_webhook_data()], "pagelen": 10},
            status=200,
        )
        webhooks = bitbucket_adapter.list_webhooks()
        assert len(webhooks) == 1
        assert isinstance(webhooks[0], Webhook)


class TestCreateWebhook:
    def test_create(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/hooks",
            json=_webhook_data(),
            status=201,
        )
        webhook = bitbucket_adapter.create_webhook(
            url="https://example.com/hook", events=["repo:push"]
        )
        assert isinstance(webhook, Webhook)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["url"] == "https://example.com/hook"
        assert "repo:push" in req_body["events"]


class TestDeleteWebhook:
    def test_delete(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/hooks/abc-123",
            status=204,
        )
        bitbucket_adapter.delete_webhook(hook_id="abc-123")
        assert mock_responses.calls[0].request.method == "DELETE"


# --- DeployKey 系 ---


class TestListDeployKeys:
    def test_list(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/deploy-keys",
            json={"values": [_deploy_key_data()], "pagelen": 10},
            status=200,
        )
        keys = bitbucket_adapter.list_deploy_keys()
        assert len(keys) == 1
        assert isinstance(keys[0], DeployKey)


class TestCreateDeployKey:
    def test_create(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/deploy-keys",
            json=_deploy_key_data(),
            status=201,
        )
        key = bitbucket_adapter.create_deploy_key(
            title="Deploy Key", key="ssh-rsa AAAA...", read_only=True
        )
        assert isinstance(key, DeployKey)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["label"] == "Deploy Key"


class TestDeleteDeployKey:
    def test_delete(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.DELETE,
            f"{REPOS}/deploy-keys/200",
            status=204,
        )
        bitbucket_adapter.delete_deploy_key(key_id=200)
        assert mock_responses.calls[0].request.method == "DELETE"


# --- Collaborator 系 ---


class TestListCollaborators:
    def test_list(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/permissions-config/users",
            json={
                "values": [{"user": {"nickname": "collab1"}}, {"user": {"nickname": "collab2"}}],
                "pagelen": 10,
            },
            status=200,
        )
        collabs = bitbucket_adapter.list_collaborators()
        assert "collab1" in collabs


class TestAddCollaboratorNotSupported:
    def test_raises(self, bitbucket_adapter):
        with pytest.raises(NotSupportedError):
            bitbucket_adapter.add_collaborator(username="newuser")


class TestRemoveCollaboratorNotSupported:
    def test_raises(self, bitbucket_adapter):
        with pytest.raises(NotSupportedError):
            bitbucket_adapter.remove_collaborator(username="olduser")


# --- Pipeline 系 ---


class TestListPipelines:
    def test_list(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pipelines",
            json={"values": [_pipeline_data()], "pagelen": 10},
            status=200,
        )
        pipelines = bitbucket_adapter.list_pipelines()
        assert len(pipelines) == 1
        assert isinstance(pipelines[0], Pipeline)


class TestGetPipeline:
    def test_get(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pipelines/300",
            json=_pipeline_data(pipeline_id=300),
            status=200,
        )
        pipeline = bitbucket_adapter.get_pipeline(300)
        assert isinstance(pipeline, Pipeline)


class TestCancelPipeline:
    def test_cancel(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/pipelines/300/stopPipeline",
            status=204,
        )
        bitbucket_adapter.cancel_pipeline(300)
        assert mock_responses.calls[0].request.method == "POST"


# --- User / Search 系 ---


class TestGetCurrentUser:
    def test_get(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/user",
            json={"nickname": "testuser", "uuid": "{abc}"},
            status=200,
        )
        user = bitbucket_adapter.get_current_user()
        assert user["nickname"] == "testuser"


class TestSearchRepositories:
    def test_search(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{BASE}/repositories/test-workspace",
            json={"values": [_repo_data()], "pagelen": 10},
            status=200,
        )
        repos = bitbucket_adapter.search_repositories("test")
        assert len(repos) >= 1
        assert isinstance(repos[0], Repository)


class TestSearchIssues:
    def test_search(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues",
            json={"values": [_issue_data()], "pagelen": 10},
            status=200,
        )
        issues = bitbucket_adapter.search_issues("bug")
        assert len(issues) >= 1
        assert isinstance(issues[0], Issue)


# --- 変換ヘルパー単体テスト ---


class TestToComment:
    def test_basic(self):
        data = {
            "id": 10,
            "content": {"raw": "A comment"},
            "user": {"nickname": "commenter"},
            "created_on": "2025-01-01T00:00:00Z",
        }
        comment = BitbucketAdapter._to_comment(data)
        assert isinstance(comment, Comment)
        assert comment.id == 10
        assert comment.body == "A comment"
        assert comment.author == "commenter"


class TestToBranch:
    def test_basic(self):
        data = {
            "name": "feature",
            "target": {"hash": "abc123"},
        }
        branch = BitbucketAdapter._to_branch(data)
        assert isinstance(branch, Branch)
        assert branch.name == "feature"
        assert branch.sha == "abc123"


class TestToTag:
    def test_basic(self):
        data = {
            "name": "v1.0.0",
            "target": {"hash": "def456"},
        }
        tag = BitbucketAdapter._to_tag(data)
        assert isinstance(tag, Tag)
        assert tag.name == "v1.0.0"
        assert tag.sha == "def456"

    def test_with_message(self):
        data = {
            "name": "v2.0.0",
            "target": {"hash": "ghi789"},
            "message": "Release v2.0.0",
        }
        tag = BitbucketAdapter._to_tag(data)
        assert tag.message == "Release v2.0.0"


class TestToCommitStatus:
    def test_successful(self):
        data = {
            "state": "SUCCESSFUL",
            "key": "ci/test",
            "description": "Tests passed",
            "url": "https://ci.example.com/1",
            "created_on": "2025-01-01T00:00:00Z",
        }
        cs = BitbucketAdapter._to_commit_status(data)
        assert isinstance(cs, CommitStatus)
        assert cs.state == "success"
        assert cs.context == "ci/test"

    def test_failed(self):
        data = {"state": "FAILED", "key": "ci/test", "created_on": "2025-01-01T00:00:00Z"}
        cs = BitbucketAdapter._to_commit_status(data)
        assert cs.state == "failure"

    def test_inprogress(self):
        data = {"state": "INPROGRESS", "key": "ci/test", "created_on": "2025-01-01T00:00:00Z"}
        cs = BitbucketAdapter._to_commit_status(data)
        assert cs.state == "pending"


class TestToWebhook:
    def test_basic(self):
        data = {
            "uuid": "{abc-123}",
            "url": "https://example.com/hook",
            "events": ["repo:push", "pullrequest:created"],
            "active": True,
        }
        webhook = BitbucketAdapter._to_webhook(data)
        assert isinstance(webhook, Webhook)
        assert webhook.id == "abc-123"
        assert webhook.url == "https://example.com/hook"
        assert "repo:push" in webhook.events
        assert "pullrequest:created" in webhook.events


class TestToDeployKey:
    def test_basic(self):
        data = {
            "id": 200,
            "label": "Deploy Key",
            "key": "ssh-rsa AAAA...",
        }
        dk = BitbucketAdapter._to_deploy_key(data)
        assert isinstance(dk, DeployKey)
        assert dk.id == 200
        assert dk.title == "Deploy Key"
        assert dk.key == "ssh-rsa AAAA..."


class TestToPipeline:
    def test_successful(self):
        data = {
            "build_number": 1,
            "state": {
                "stage": {"name": "COMPLETED"},
                "result": {"name": "SUCCESSFUL"},
            },
            "target": {"ref_name": "main"},
            "created_on": "2025-01-01T00:00:00Z",
        }
        pipeline = BitbucketAdapter._to_pipeline(data)
        assert isinstance(pipeline, Pipeline)
        assert pipeline.status == "success"

    def test_failed(self):
        data = {
            "build_number": 2,
            "state": {
                "stage": {"name": "COMPLETED"},
                "result": {"name": "FAILED"},
            },
            "target": {"ref_name": "main"},
            "created_on": "2025-01-01T00:00:00Z",
        }
        pipeline = BitbucketAdapter._to_pipeline(data)
        assert pipeline.status == "failure"

    def test_in_progress(self):
        data = {
            "build_number": 3,
            "state": {
                "stage": {"name": "IN_PROGRESS"},
                "result": None,
            },
            "target": {"ref_name": "feature"},
            "created_on": "2025-01-01T00:00:00Z",
        }
        pipeline = BitbucketAdapter._to_pipeline(data)
        assert pipeline.status == "running"
