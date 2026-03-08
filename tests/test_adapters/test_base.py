"""GitServiceAdapter ABC のテスト。"""

from __future__ import annotations

import pytest

from gfo.adapter.base import GitServiceAdapter, PullRequest
from gfo.exceptions import NotSupportedError


EXPECTED_ABSTRACT_METHODS = frozenset({
    "list_pull_requests",
    "create_pull_request",
    "get_pull_request",
    "merge_pull_request",
    "close_pull_request",
    "list_issues",
    "create_issue",
    "get_issue",
    "close_issue",
    "list_repositories",
    "create_repository",
    "get_repository",
    "list_releases",
    "create_release",
    "list_labels",
    "create_label",
    "list_milestones",
    "create_milestone",
})


class StubAdapter(GitServiceAdapter):
    """全抽象メソッドをスタブ実装した具象サブクラス。"""

    service_name = "stub"

    def list_pull_requests(self, *, state="open", limit=30):
        return []

    def create_pull_request(self, *, title, body="", base, head, draft=False):
        return None  # type: ignore[return-value]

    def get_pull_request(self, number):
        return None  # type: ignore[return-value]

    def merge_pull_request(self, number, *, method="merge"):
        return None

    def close_pull_request(self, number):
        return None

    def list_issues(self, *, state="open", assignee=None, label=None, limit=30):
        return []

    def create_issue(self, *, title, body="", assignee=None, label=None, **kwargs):
        return None  # type: ignore[return-value]

    def get_issue(self, number):
        return None  # type: ignore[return-value]

    def close_issue(self, number):
        return None

    def list_repositories(self, *, owner=None, limit=30):
        return []

    def create_repository(self, *, name, private=False, description=""):
        return None  # type: ignore[return-value]

    def get_repository(self, owner=None, name=None):
        return None  # type: ignore[return-value]

    def list_releases(self, *, limit=30):
        return []

    def create_release(self, *, tag, title="", notes="", draft=False, prerelease=False):
        return None  # type: ignore[return-value]

    def list_labels(self):
        return []

    def create_label(self, *, name, color=None, description=None):
        return None  # type: ignore[return-value]

    def list_milestones(self):
        return []

    def create_milestone(self, *, title, description=None, due_date=None):
        return None  # type: ignore[return-value]


class TestAbstractMethods:
    def test_abstract_methods_match_expected(self):
        assert GitServiceAdapter.__abstractmethods__ == EXPECTED_ABSTRACT_METHODS

    def test_cannot_instantiate_abc_directly(self):
        with pytest.raises(TypeError):
            GitServiceAdapter(client=None, owner="o", repo="r")  # type: ignore[abstract]


class TestInit:
    def test_init_stores_attributes(self):
        client = object()
        adapter = StubAdapter(client=client, owner="myowner", repo="myrepo")
        assert adapter._client is client
        assert adapter._owner == "myowner"
        assert adapter._repo == "myrepo"


class TestGetPrCheckoutRefspec:
    def test_default_raises_not_supported_error(self):
        adapter = StubAdapter(client=None, owner="o", repo="r")
        with pytest.raises(NotSupportedError) as exc_info:
            adapter.get_pr_checkout_refspec(1)
        assert exc_info.value.service == "stub"
        assert exc_info.value.operation == "pr checkout"
