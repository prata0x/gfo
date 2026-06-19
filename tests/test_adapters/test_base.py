"""GitServiceAdapter ABC のテスト。"""

from __future__ import annotations

import pytest

from gfo.adapter.base import GitServiceAdapter
from gfo.exceptions import NotSupportedError
from tests.conftest import StubAdapter

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
