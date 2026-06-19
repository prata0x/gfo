"""GogsAdapter のテスト。"""

from __future__ import annotations

from unittest.mock import patch

import pytest
import responses

from gfo.adapter.gitea import GiteaAdapter
from gfo.adapter.gogs import GogsAdapter
from gfo.adapter.registry import get_adapter_class
from gfo.exceptions import NotSupportedError

BASE = "https://gogs.example.com/api/v1"
WEB_BASE = "https://gogs.example.com"
REPOS = f"{BASE}/repos/test-owner/test-repo"


def _issue_data(*, number=1, state="open"):
    return {
        "number": number,
        "title": f"Issue #{number}",
        "body": "description",
        "state": state,
        "user": {"login": "author1"},
        "assignees": [],
        "labels": [],
        "html_url": f"{WEB_BASE}/test-owner/test-repo/issues/{number}",
        "created_at": "2025-01-01T00:00:00Z",
    }


class TestRegistry:
    def test_registered(self):
        assert get_adapter_class("gogs") is GogsAdapter


class TestInheritance:
    def test_is_gitea_adapter(self, gogs_adapter):
        assert isinstance(gogs_adapter, GiteaAdapter)

    def test_service_name(self, gogs_adapter):
        assert gogs_adapter.service_name == "Gogs"


_REPO_WEB = f"{WEB_BASE}/test-owner/test-repo"
# web_url を検証しないケース（NotSupportedError が出ることだけ確認）の番兵。
_NO_WEB_URL_CHECK = object()

# (id, 呼び出し, 期待 web_url)。
#   文字列 → exc.web_url が一致すること / None → exc.web_url is None /
#   _NO_WEB_URL_CHECK → web_url を検証しない。
_NOT_SUPPORTED_CASES = [
    ("list_pull_requests", lambda a: a.list_pull_requests(), f"{_REPO_WEB}/pulls"),
    (
        "create_pull_request",
        lambda a: a.create_pull_request(title="PR", base="main", head="feature"),
        f"{_REPO_WEB}/compare",
    ),
    ("get_pull_request", lambda a: a.get_pull_request(1), f"{_REPO_WEB}/pulls/1"),
    ("merge_pull_request", lambda a: a.merge_pull_request(1), f"{_REPO_WEB}/pulls/1"),
    ("close_pull_request", lambda a: a.close_pull_request(1), f"{_REPO_WEB}/pulls/1"),
    ("get_pr_checkout_refspec", lambda a: a.get_pr_checkout_refspec(1), f"{_REPO_WEB}/pulls/1"),
    ("reopen_pull_request", lambda a: a.reopen_pull_request(1), f"{_REPO_WEB}/pulls/1"),
    ("update_pull_request", lambda a: a.update_pull_request(1, title="New"), f"{_REPO_WEB}/pulls"),
    ("list_reviews", lambda a: a.list_reviews(1), f"{_REPO_WEB}/pulls"),
    ("create_review", lambda a: a.create_review(1, state="approve"), f"{_REPO_WEB}/pulls"),
    ("list_labels", lambda a: a.list_labels(), None),
    ("create_label", lambda a: a.create_label(name="bug"), None),
    ("delete_label", lambda a: a.delete_label(name="bug"), None),
    ("update_label", lambda a: a.update_label(name="bug", new_name="bug-fix"), None),
    ("list_milestones", lambda a: a.list_milestones(), None),
    ("create_milestone", lambda a: a.create_milestone(title="v1.0"), None),
    ("delete_milestone", lambda a: a.delete_milestone(number=1), None),
    ("get_milestone", lambda a: a.get_milestone(1), None),
    ("update_milestone", lambda a: a.update_milestone(1, title="v2.0"), None),
    ("list_releases", lambda a: a.list_releases(), None),
    ("create_release", lambda a: a.create_release(tag="v1.0.0"), None),
    ("delete_release", lambda a: a.delete_release(tag="v1.0.0"), None),
    ("get_release", lambda a: a.get_release(tag="v1.0.0"), None),
    ("update_release", lambda a: a.update_release(tag="v1.0.0"), None),
    ("update_comment", lambda a: a.update_comment("issue", 10, body="Updated"), _NO_WEB_URL_CHECK),
    ("delete_comment", lambda a: a.delete_comment("issue", 10), _NO_WEB_URL_CHECK),
    ("list_pipelines", lambda a: a.list_pipelines(), _NO_WEB_URL_CHECK),
    ("get_pipeline", lambda a: a.get_pipeline(1), _NO_WEB_URL_CHECK),
    ("cancel_pipeline", lambda a: a.cancel_pipeline(1), _NO_WEB_URL_CHECK),
]


class TestNotSupportedOperations:
    @pytest.mark.parametrize(
        ("call", "expected_web_url"),
        [(c, w) for _, c, w in _NOT_SUPPORTED_CASES],
        ids=[name for name, _, _ in _NOT_SUPPORTED_CASES],
    )
    def test_raises_not_supported(self, gogs_adapter, call, expected_web_url):
        with pytest.raises(NotSupportedError) as exc_info:
            call(gogs_adapter)
        if expected_web_url is not _NO_WEB_URL_CHECK:
            assert exc_info.value.web_url == expected_web_url


class TestWebUrl:
    def test_standard_url(self, gogs_adapter):
        assert gogs_adapter._web_url() == "https://gogs.example.com"

    def test_url_with_port(self, gogs_client):
        from gfo.http import HttpClient

        client = HttpClient(
            "http://gogs.local:3000/api/v1",
            auth_header={"Authorization": "token test-token"},
        )
        adapter = GogsAdapter(client, "owner", "repo")
        assert adapter._web_url() == "http://gogs.local:3000"

    def test_web_url_owner_repo_with_special_chars_is_encoded(self, gogs_client):
        """owner/repo に特殊文字が含まれる場合に web_url が URL エンコードされる（R34-01）。"""
        from gfo.http import HttpClient

        client = HttpClient(
            "https://gogs.example.com/api/v1",
            auth_header={"Authorization": "token test-token"},
        )
        adapter = GogsAdapter(client, "my owner", "my repo")
        with pytest.raises(NotSupportedError) as exc_info:
            adapter.list_pull_requests()
        assert "my%20owner" in exc_info.value.web_url
        assert "my%20repo" in exc_info.value.web_url


class TestCreateWebhook:
    """Gogs は type:"gogs" 固有ペイロードで webhook を作成する。"""

    def _hook_response(self, *, hook_id=5, url="https://example.com/hook"):
        return {
            "id": hook_id,
            "type": "gogs",
            "config": {"url": url, "content_type": "json"},
            "events": ["push"],
            "active": True,
        }

    def test_payload_shape(self, mock_responses, gogs_adapter):
        import json as json_mod

        mock_responses.add(responses.POST, f"{REPOS}/hooks", json=self._hook_response(), status=201)
        hook = gogs_adapter.create_webhook(url="https://example.com/hook")
        assert hook.id == 5
        req_body = json_mod.loads(mock_responses.calls[0].request.body)
        # Gogs 固有: type="gogs"、config.content_type="json"、events デフォルト ["push"]。
        assert req_body["type"] == "gogs"
        assert req_body["config"]["url"] == "https://example.com/hook"
        assert req_body["config"]["content_type"] == "json"
        assert req_body["events"] == ["push"]
        assert req_body["active"] is True
        # secret 未指定なら config に含めない。
        assert "secret" not in req_body["config"]

    def test_with_secret_and_custom_events(self, mock_responses, gogs_adapter):
        import json as json_mod

        mock_responses.add(responses.POST, f"{REPOS}/hooks", json=self._hook_response(), status=201)
        gogs_adapter.create_webhook(
            url="https://example.com/hook",
            events=["push", "pull_request"],
            secret="s3cr3t",
        )
        req_body = json_mod.loads(mock_responses.calls[0].request.body)
        assert req_body["config"]["secret"] == "s3cr3t"
        assert req_body["events"] == ["push", "pull_request"]


class TestInheritedOperations:
    def test_create_issue(self, mock_responses, gogs_adapter):
        mock_responses.add(
            responses.POST,
            f"{REPOS}/issues",
            json=_issue_data(),
            status=201,
        )
        issue = gogs_adapter.create_issue(title="Test", body="body")
        assert issue.number == 1

    def test_close_issue(self, mock_responses, gogs_adapter):
        mock_responses.add(
            responses.PATCH,
            f"{REPOS}/issues/1",
            json=_issue_data(state="closed"),
            status=200,
        )
        gogs_adapter.close_issue(1)

    def test_get_issue(self, mock_responses, gogs_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues/1",
            json=_issue_data(),
            status=200,
        )
        issue = gogs_adapter.get_issue(1)
        assert issue.number == 1

    def test_list_issues(self, mock_responses, gogs_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues",
            json=[_issue_data()],
            status=200,
        )
        issues = gogs_adapter.list_issues()
        assert len(issues) == 1
        assert issues[0].number == 1
        assert issues[0].state == "open"

    def test_list_issues_pagination(self, mock_responses, gogs_adapter):
        import json as json_mod

        next_url = f"{REPOS}/issues?page=2&limit=30"
        call_count = {"n": 0}

        def callback(request):
            call_count["n"] += 1
            if call_count["n"] == 1:
                headers = {"Link": f'<{next_url}>; rel="next"'}
                return (
                    200,
                    headers,
                    json_mod.dumps([_issue_data(number=1), _issue_data(number=2)]),
                )
            return (200, {}, json_mod.dumps([_issue_data(number=3)]))

        mock_responses.add_callback(responses.GET, f"{REPOS}/issues", callback=callback)
        issues = gogs_adapter.list_issues(limit=0)
        assert len(issues) == 3
        assert call_count["n"] == 2


class TestDeleteInheritance:
    """Gogs の delete メソッドの動作確認。"""

    def test_delete_issue_raises_not_supported(self, gogs_adapter):
        """Gogs は issue delete 未対応 → NotSupportedError。"""
        from gfo.exceptions import NotSupportedError

        with pytest.raises(NotSupportedError):
            gogs_adapter.delete_issue(5)

    def test_delete_repository(self, mock_responses, gogs_adapter):
        mock_responses.add(
            responses.DELETE,
            REPOS,
            status=204,
        )
        gogs_adapter.delete_repository()
        assert mock_responses.calls[0].request.method == "DELETE"

    def test_migrate_repository_not_supported(self, gogs_adapter):
        with pytest.raises(NotSupportedError):
            gogs_adapter.migrate_repository("https://github.com/a/b.git", "c")


class TestSyncFork:
    def test_raises_not_supported(self, gogs_adapter):
        with pytest.raises(NotSupportedError):
            gogs_adapter.sync_fork()


class TestPackagesGogs:
    """Gogs はパッケージ API 未対応のため NotSupportedError を返す。"""

    def test_list_packages_raises(self, gogs_adapter):
        with pytest.raises(NotSupportedError):
            gogs_adapter.list_packages()

    def test_get_package_raises(self, gogs_adapter):
        with pytest.raises(NotSupportedError):
            gogs_adapter.get_package("container", "any")

    def test_delete_package_raises(self, gogs_adapter):
        with pytest.raises(NotSupportedError):
            gogs_adapter.delete_package("container", "any", "1.0")


class TestGogsErrorPropagation:
    """Gogs アダプターでも 401/404/5xx が適切なサブクラスで伝搬すること。

    Gogs テストは NotSupportedError 中心で、HTTP ステータス別エラーの確認が
    薄かったため、代表メソッドで一通り確認する。
    """

    def test_list_issues_unauthorized(self, mock_responses, gogs_adapter):
        from gfo.exceptions import AuthenticationError

        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues",
            json={"message": "unauthorized"},
            status=401,
        )
        with pytest.raises(AuthenticationError):
            gogs_adapter.list_issues()

    def test_get_issue_not_found(self, mock_responses, gogs_adapter):
        from gfo.exceptions import NotFoundError

        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues/99999",
            status=404,
        )
        with pytest.raises(NotFoundError):
            gogs_adapter.get_issue(99999)

    def test_list_issues_server_error(self, mock_responses, gogs_adapter):
        from gfo.exceptions import ServerError

        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues",
            json={"message": "internal"},
            status=500,
        )
        with pytest.raises(ServerError):
            gogs_adapter.list_issues()

    def test_rate_limit_propagates(self, mock_responses, gogs_adapter):
        from gfo.exceptions import RateLimitError

        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues",
            json={"message": "rate limited"},
            status=429,
            headers={"Retry-After": "60"},
        )
        # max_retries=1 のため 1 回リトライ → 同じく 429 → RateLimitError 伝搬
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues",
            json={"message": "rate limited"},
            status=429,
            headers={"Retry-After": "60"},
        )
        # time.sleep をモックして即時実行
        with patch("gfo.http.time.sleep") as mock_sleep:
            with pytest.raises(RateLimitError):
                gogs_adapter.list_issues()
        # リトライ前に Retry-After 秒待機していること
        mock_sleep.assert_called_once()
