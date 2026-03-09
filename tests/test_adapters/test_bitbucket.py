"""BitbucketAdapter のテスト。"""

from __future__ import annotations

import json
from urllib.parse import unquote, unquote_plus

import pytest
import responses

from gfo.adapter.base import Issue, PullRequest, Repository
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
        "links": {"html": {"href": f"https://bitbucket.org/test-workspace/test-repo/pull-requests/{id}"}},
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
            responses.GET, f"{REPOS}/pullrequests",
            json={"values": [_pr_data()], "next": None}, status=200,
        )
        prs = bitbucket_adapter.list_pull_requests()
        assert len(prs) == 1
        assert prs[0].state == "open"
        req = mock_responses.calls[0].request
        assert "state=OPEN" in req.url

    def test_merged_filter(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET, f"{REPOS}/pullrequests",
            json={"values": [_pr_data(state="MERGED")]}, status=200,
        )
        prs = bitbucket_adapter.list_pull_requests(state="merged")
        assert len(prs) == 1
        assert prs[0].state == "merged"
        req = mock_responses.calls[0].request
        assert "state=MERGED" in req.url

    def test_all_state_omits_filter(self, mock_responses, bitbucket_adapter):
        """state='all' のとき state パラメータを送らない（Bitbucket API は 'ALL' を受け付けない）。"""
        mock_responses.add(
            responses.GET, f"{REPOS}/pullrequests",
            json={"values": [_pr_data(), _pr_data(id=2, state="MERGED")]}, status=200,
        )
        prs = bitbucket_adapter.list_pull_requests(state="all")
        assert len(prs) == 2
        req = mock_responses.calls[0].request
        assert "state=" not in req.url

    def test_pagination(self, mock_responses, bitbucket_adapter):
        page2_url = f"{REPOS}/pullrequests?state=OPEN&page=2"
        mock_responses.add(
            responses.GET, f"{REPOS}/pullrequests",
            json={"values": [_pr_data(id=1)], "next": page2_url}, status=200,
        )
        mock_responses.add(
            responses.GET, page2_url,
            json={"values": [_pr_data(id=2)]}, status=200,
        )
        prs = bitbucket_adapter.list_pull_requests(limit=10)
        assert len(prs) == 2

    def test_pagination_stops_on_different_origin(self, mock_responses, bitbucket_adapter):
        """next URL が別オリジンを指す場合はページネーションを中断する（SSRF 防止）。"""
        other_origin_url = "https://evil.example.com/api/pullrequests?page=2"
        mock_responses.add(
            responses.GET, f"{REPOS}/pullrequests",
            json={"values": [_pr_data(id=1)], "next": other_origin_url}, status=200,
        )
        prs = bitbucket_adapter.list_pull_requests(limit=10)
        # 別オリジンへのリクエストは行われず、1件のみ返る
        assert len(prs) == 1
        assert len(mock_responses.calls) == 1


class TestCreatePullRequest:
    def test_create(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.POST, f"{REPOS}/pullrequests",
            json=_pr_data(), status=201,
        )
        pr = bitbucket_adapter.create_pull_request(
            title="PR #1", body="desc", base="main", head="feature",
        )
        assert isinstance(pr, PullRequest)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["source"]["branch"]["name"] == "feature"
        assert req_body["destination"]["branch"]["name"] == "main"


class TestCreatePullRequestDescription:
    def test_create_with_description(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.POST, f"{REPOS}/pullrequests",
            json=_pr_data(), status=201,
        )
        bitbucket_adapter.create_pull_request(
            title="PR", body="Description text", base="main", head="feature",
        )
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["description"] == "Description text"


class TestGetPullRequest:
    def test_get(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET, f"{REPOS}/pullrequests/42",
            json=_pr_data(id=42), status=200,
        )
        pr = bitbucket_adapter.get_pull_request(42)
        assert pr.number == 42


class TestMergePullRequest:
    def test_merge(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.POST, f"{REPOS}/pullrequests/1/merge",
            json={"state": "MERGED"}, status=200,
        )
        bitbucket_adapter.merge_pull_request(1)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["merge_strategy"] == "merge_commit"

    def test_squash_method(self, mock_responses, bitbucket_adapter):
        """method='squash' → merge_strategy='squash' がリクエストに含まれる。"""
        mock_responses.add(
            responses.POST, f"{REPOS}/pullrequests/1/merge",
            json={"state": "MERGED"}, status=200,
        )
        bitbucket_adapter.merge_pull_request(1, method="squash")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["merge_strategy"] == "squash"

    def test_rebase_method(self, mock_responses, bitbucket_adapter):
        """method='rebase' → merge_strategy='fast_forward' がリクエストに含まれる。"""
        mock_responses.add(
            responses.POST, f"{REPOS}/pullrequests/1/merge",
            json={"state": "MERGED"}, status=200,
        )
        bitbucket_adapter.merge_pull_request(1, method="rebase")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["merge_strategy"] == "fast_forward"


class TestClosePullRequest:
    def test_close(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.PUT, f"{REPOS}/pullrequests/1",
            json=_pr_data(state="DECLINED"), status=200,
        )
        bitbucket_adapter.close_pull_request(1)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["state"] == "DECLINED"


class TestCheckoutRefspec:
    def test_with_pr(self, bitbucket_adapter):
        pr = BitbucketAdapter._to_pull_request(_pr_data())
        assert bitbucket_adapter.get_pr_checkout_refspec(1, pr=pr) == "feature"

    def test_without_pr(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET, f"{REPOS}/pullrequests/1",
            json=_pr_data(), status=200,
        )
        assert bitbucket_adapter.get_pr_checkout_refspec(1) == "feature"


# --- Issue 系 ---

class TestListIssues:
    def test_list(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET, f"{REPOS}/issues",
            json={"values": [_issue_data(id=1), _issue_data(id=2)]}, status=200,
        )
        issues = bitbucket_adapter.list_issues()
        assert len(issues) == 2


    def test_closed_state_filter(self, mock_responses, bitbucket_adapter):
        """state='closed' のとき q に resolved 等の全非 open 状態を包含するフィルタが追加される。"""
        mock_responses.add(
            responses.GET, f"{REPOS}/issues",
            json={"values": [_issue_data(state="resolved")]}, status=200,
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
        """state='all' のとき q フィルタを送らない（'all' は Bitbucket の有効な state 値ではない）。"""
        mock_responses.add(
            responses.GET, f"{REPOS}/issues",
            json={"values": [_issue_data(id=1), _issue_data(id=2)]}, status=200,
        )
        issues = bitbucket_adapter.list_issues(state="all")
        assert len(issues) == 2
        req = mock_responses.calls[0].request
        assert "q=" not in req.url

    def test_assignee_filter(self, mock_responses, bitbucket_adapter):
        """assignee を指定すると q に assignee.nickname フィルタが追加される。"""
        mock_responses.add(
            responses.GET, f"{REPOS}/issues",
            json={"values": [_issue_data()]}, status=200,
        )
        bitbucket_adapter.list_issues(state="open", assignee="alice")
        req = mock_responses.calls[0].request
        decoded_url = unquote(req.url)
        assert 'assignee.nickname="alice"' in decoded_url
        assert 'state="new"' in decoded_url

    def test_assignee_filter_with_all_state(self, mock_responses, bitbucket_adapter):
        """state='all' + assignee のとき state フィルタなしで assignee のみ含まれる。"""
        mock_responses.add(
            responses.GET, f"{REPOS}/issues",
            json={"values": [_issue_data()]}, status=200,
        )
        bitbucket_adapter.list_issues(state="all", assignee="bob")
        req = mock_responses.calls[0].request
        decoded_url = unquote(req.url)
        assert 'assignee.nickname="bob"' in decoded_url
        assert 'state="' not in decoded_url

    def test_label_filter(self, mock_responses, bitbucket_adapter):
        """label を指定すると q に component.name フィルタが追加される。"""
        mock_responses.add(
            responses.GET, f"{REPOS}/issues",
            json={"values": [_issue_data()]}, status=200,
        )
        bitbucket_adapter.list_issues(state="all", label="bug")
        req = mock_responses.calls[0].request
        decoded_url = unquote(req.url)
        assert 'component.name="bug"' in decoded_url

    def test_custom_state_filter(self, mock_responses, bitbucket_adapter):
        """'open'/'closed'/'all' 以外の state を直接指定すると state="{state}" フィルタが追加される。"""
        mock_responses.add(
            responses.GET, f"{REPOS}/issues",
            json={"values": [_issue_data(state="resolved")]}, status=200,
        )
        bitbucket_adapter.list_issues(state="resolved")
        req = mock_responses.calls[0].request
        decoded_url = unquote(req.url)
        assert 'state="resolved"' in decoded_url


class TestCreateIssue:
    def test_create(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.POST, f"{REPOS}/issues",
            json=_issue_data(), status=201,
        )
        issue = bitbucket_adapter.create_issue(title="Issue #1", body="body")
        assert isinstance(issue, Issue)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["content"]["raw"] == "body"
        assert "assignee" not in req_body

    def test_create_with_assignee(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.POST, f"{REPOS}/issues",
            json=_issue_data(), status=201,
        )
        bitbucket_adapter.create_issue(title="Issue", assignee="dev1")
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["assignee"]["nickname"] == "dev1"

    def test_create_with_label_sets_component(self, mock_responses, bitbucket_adapter):
        """label を指定すると payload に component.name が設定される。"""
        mock_responses.add(
            responses.POST, f"{REPOS}/issues",
            json=_issue_data(), status=201,
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
            responses.GET, f"{REPOS}/issues/5",
            json=_issue_data(id=5), status=200,
        )
        issue = bitbucket_adapter.get_issue(5)
        assert issue.number == 5


class TestCloseIssue:
    def test_close(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.PUT, f"{REPOS}/issues/3",
            json=_issue_data(id=3, state="resolved"), status=200,
        )
        bitbucket_adapter.close_issue(3)
        req_body = json.loads(mock_responses.calls[0].request.body)
        assert req_body["state"] == "resolved"


# --- Repository 系 ---

class TestListRepositories:
    def test_with_owner(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET, f"{BASE}/repositories/someone",
            json={"values": [_repo_data()]}, status=200,
        )
        repos = bitbucket_adapter.list_repositories(owner="someone")
        assert len(repos) == 1

    def test_no_owner(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET, f"{BASE}/repositories/test-workspace",
            json={"values": [_repo_data()]}, status=200,
        )
        repos = bitbucket_adapter.list_repositories()
        assert len(repos) == 1

    def test_owner_with_slash_is_encoded(self, mock_responses, bitbucket_adapter):
        """list_repositories(owner="org/sub") でスラッシュが URL エンコードされる（R42-01）。"""
        mock_responses.add(
            responses.GET, f"{BASE}/repositories/org%2Fsub",
            json={"values": [_repo_data()]}, status=200,
        )
        bitbucket_adapter.list_repositories(owner="org/sub")
        assert "%2F" in mock_responses.calls[0].request.url


class TestCreateRepository:
    def test_create(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.POST, f"{BASE}/repositories/test-workspace/new-repo",
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
            responses.POST, f"{BASE}/repositories/test-workspace/my%2Frepo",
            json=_repo_data(slug="my/repo", full_name="test-workspace/my/repo"),
            status=201,
        )
        bitbucket_adapter.create_repository(name="my/repo")
        assert "%2F" in mock_responses.calls[0].request.url


class TestGetRepository:
    def test_get(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET, f"{BASE}/repositories/other/other-repo",
            json=_repo_data(slug="other-repo", full_name="other/other-repo"),
            status=200,
        )
        repo = bitbucket_adapter.get_repository(owner="other", name="other-repo")
        assert repo.name == "other-repo"

    def test_get_defaults(self, mock_responses, bitbucket_adapter):
        mock_responses.add(
            responses.GET, f"{REPOS}",
            json=_repo_data(), status=200,
        )
        repo = bitbucket_adapter.get_repository()
        assert repo.full_name == "test-workspace/test-repo"

    def test_get_owner_with_slash_is_encoded(self, mock_responses, bitbucket_adapter):
        """get_repository(owner="org/sub") でスラッシュが URL エンコードされる（R42-01）。"""
        mock_responses.add(
            responses.GET, f"{BASE}/repositories/org%2Fsub/test-repo",
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
            responses.GET, f"{REPOS}/pullrequests/1",
            json={"incomplete": True}, status=200,
        )
        with pytest.raises(GfoError):
            bitbucket_adapter.get_pull_request(1)

    def test_malformed_issue_raises_gfo_error(self, mock_responses, bitbucket_adapter):
        """_to_issue で必須フィールド欠落 → GfoError。"""
        from gfo.exceptions import GfoError
        mock_responses.add(
            responses.GET, f"{REPOS}/issues",
            json={"values": [{"incomplete": True}], "next": None}, status=200,
        )
        with pytest.raises(GfoError):
            bitbucket_adapter.list_issues()

    def test_malformed_repository_raises_gfo_error(self, mock_responses, bitbucket_adapter):
        """_to_repository で必須フィールド欠落 → GfoError。"""
        from gfo.exceptions import GfoError
        mock_responses.add(
            responses.GET, f"{REPOS}",
            json={"incomplete": True}, status=200,
        )
        with pytest.raises(GfoError):
            bitbucket_adapter.get_repository()
