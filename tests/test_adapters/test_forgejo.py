"""ForgejoAdapter のテスト。

ForgejoAdapter は ``service_name`` 以外を一切オーバーライドしないため、CRUD / ``_to_*``
の挙動は GiteaAdapter（``tests/test_adapters/test_gitea.py``）のテストが網羅している。
本ファイルは Forgejo 固有の wiring（registry 登録・継承・Gitea API 互換パス）だけを検証し、
GiteaAdapter のテストと重複する挙動テストは持たない。

新たに override を追加した場合は :class:`TestNoBehavioralOverrides` が失敗するので、
その時点で当該挙動のテストを本ファイルへ個別に追加すること。
"""

from __future__ import annotations

import responses

from gfo.adapter.forgejo import ForgejoAdapter
from gfo.adapter.gitea import GiteaAdapter
from gfo.adapter.registry import get_adapter_class

BASE = "https://forgejo.example.com/api/v1"
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
        "html_url": f"https://forgejo.example.com/test-owner/test-repo/pulls/{number}",
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
        "html_url": f"https://forgejo.example.com/test-owner/test-repo/issues/{number}",
        "created_at": "2025-01-01T00:00:00Z",
    }


class TestRegistry:
    def test_registered(self):
        assert get_adapter_class("forgejo") is ForgejoAdapter


class TestInheritance:
    def test_is_gitea_adapter(self, forgejo_adapter):
        assert isinstance(forgejo_adapter, GiteaAdapter)

    def test_service_name(self, forgejo_adapter):
        assert forgejo_adapter.service_name == "Forgejo"

    def test_service_name_not_gitea(self, forgejo_adapter):
        assert forgejo_adapter.service_name != "Gitea"


class TestNoBehavioralOverrides:
    """Forgejo が GiteaAdapter から挙動を変えていないことを保証する。

    これが green である限り、CRUD/_to_* の挙動は GiteaAdapter のテストで担保される。
    override を足したらここが落ちるので、その挙動を本ファイルに個別テストする合図になる。
    """

    def test_only_overrides_service_name(self):
        # __dunder__ と ABCMeta の _abc_impl（具象 ABC サブクラスに必ず付く）は除外する。
        own = {k for k in vars(ForgejoAdapter) if not k.startswith("__") and k != "_abc_impl"}
        assert own == {"service_name"}, (
            f"ForgejoAdapter が service_name 以外を override している: {own - {'service_name'}}。"
            " override した挙動は本ファイルで個別にテストすること。"
        )


class TestGiteaApiCompatibility:
    """ForgejoAdapter が継承により Gitea API v1 互換パス/方式を使うことを確認する。"""

    def test_pr_endpoint_uses_gitea_path(self, mock_responses, forgejo_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls",
            json=[_pr_data()],
            status=200,
        )
        forgejo_adapter.list_pull_requests()
        assert mock_responses.calls[0].request.url.startswith(f"{REPOS}/pulls")

    def test_pagination_uses_limit_param(self, mock_responses, forgejo_adapter):
        """Gitea 互換: ページネーションは per_page= ではなく limit= を使う。"""
        mock_responses.add(
            responses.GET,
            f"{REPOS}/pulls",
            json=[_pr_data()],
            status=200,
        )
        forgejo_adapter.list_pull_requests(limit=20)
        req_url = mock_responses.calls[0].request.url
        assert "limit=" in req_url
        assert "per_page=" not in req_url

    def test_issues_endpoint_uses_gitea_path(self, mock_responses, forgejo_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues",
            json=[_issue_data()],
            status=200,
        )
        forgejo_adapter.list_issues()
        assert mock_responses.calls[0].request.url.startswith(f"{REPOS}/issues")

    def test_issues_pagination_uses_limit_param(self, mock_responses, forgejo_adapter):
        mock_responses.add(
            responses.GET,
            f"{REPOS}/issues",
            json=[_issue_data()],
            status=200,
        )
        forgejo_adapter.list_issues(limit=10)
        req_url = mock_responses.calls[0].request.url
        assert "limit=" in req_url
        assert "per_page=" not in req_url

    def test_checkout_refspec_uses_gitea_format(self, forgejo_adapter):
        """Gitea 互換: チェックアウト refspec は refs/pull/{n}/head 形式。"""
        assert forgejo_adapter.get_pr_checkout_refspec(7) == "refs/pull/7/head"
