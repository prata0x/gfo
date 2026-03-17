"""GitServiceAdapter ABC のテスト。"""

from __future__ import annotations

import pytest

from gfo.adapter.base import GitServiceAdapter
from gfo.exceptions import NotSupportedError

EXPECTED_ABSTRACT_METHODS = frozenset(
    {
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
        "list_comments",
        "create_comment",
        "update_pull_request",
        "update_issue",
        "list_branches",
        "create_branch",
    }
)


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

    def list_comments(self, resource, number, *, limit=30):
        return []

    def create_comment(self, resource, number, *, body):
        return None  # type: ignore[return-value]

    def update_pull_request(self, number, *, title=None, body=None, base=None):
        return None  # type: ignore[return-value]

    def update_issue(self, number, *, title=None, body=None, assignee=None, label=None):
        return None  # type: ignore[return-value]

    def list_branches(self, *, limit=30):
        return []

    def create_branch(self, *, name, ref):
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


class TestDeleteDefaults:
    def setup_method(self):
        self.adapter = StubAdapter(client=None, owner="o", repo="r")

    def test_delete_release_raises_not_supported_error(self):
        with pytest.raises(NotSupportedError) as exc_info:
            self.adapter.delete_release(tag="v1.0.0")
        assert exc_info.value.service == "stub"
        assert exc_info.value.operation == "release delete"

    def test_delete_label_raises_not_supported_error(self):
        with pytest.raises(NotSupportedError) as exc_info:
            self.adapter.delete_label(name="bug")
        assert exc_info.value.service == "stub"
        assert exc_info.value.operation == "label delete"

    def test_delete_milestone_raises_not_supported_error(self):
        with pytest.raises(NotSupportedError) as exc_info:
            self.adapter.delete_milestone(number=1)
        assert exc_info.value.service == "stub"
        assert exc_info.value.operation == "milestone delete"

    def test_get_milestone_raises_not_supported_error(self):
        with pytest.raises(NotSupportedError) as exc_info:
            self.adapter.get_milestone(1)
        assert exc_info.value.service == "stub"
        assert exc_info.value.operation == "milestone view"

    def test_update_milestone_raises_not_supported_error(self):
        with pytest.raises(NotSupportedError) as exc_info:
            self.adapter.update_milestone(1, title="v2.0")
        assert exc_info.value.service == "stub"
        assert exc_info.value.operation == "milestone update"
