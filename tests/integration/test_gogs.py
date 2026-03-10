"""Gogs 統合テスト。

Gogs は PR / Label / Milestone 非対応のため、
Issue / Repository / Release のみテストする。
"""

from __future__ import annotations

import pytest

from gfo.exceptions import NotSupportedError
from tests.integration.conftest import create_test_adapter, get_service_config

CONFIG = get_service_config("gogs")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.selfhosted,
    pytest.mark.skipif(CONFIG is None, reason="Gogs credentials not configured"),
]


class TestGogsIntegration:
    """Gogs に対する統合テスト。"""

    @classmethod
    def setup_class(cls) -> None:
        assert CONFIG is not None
        cls.adapter = create_test_adapter(CONFIG)
        cls.config = CONFIG
        cls._issue_number: int | None = None

    # --- Repository ---

    def test_01_repo_view(self) -> None:
        repo = self.adapter.get_repository()
        assert repo.name == self.config.repo

    def test_02_repo_list(self) -> None:
        repos = self.adapter.list_repositories(owner=self.config.owner, limit=10)
        names = [r.name for r in repos]
        assert self.config.repo in names

    # --- Label (非対応 → NotSupportedError) ---

    def test_03_label_not_supported(self) -> None:
        with pytest.raises(NotSupportedError):
            self.adapter.list_labels()

    def test_04_label_create_not_supported(self) -> None:
        with pytest.raises(NotSupportedError):
            self.adapter.create_label(name="test", color="ff0000")

    # --- Milestone (非対応 → NotSupportedError) ---

    def test_05_milestone_not_supported(self) -> None:
        with pytest.raises(NotSupportedError):
            self.adapter.list_milestones()

    def test_06_milestone_create_not_supported(self) -> None:
        with pytest.raises(NotSupportedError):
            self.adapter.create_milestone(title="test")

    # --- Issue ---

    def test_07_issue_create(self) -> None:
        issue = self.adapter.create_issue(title="gfo-test-issue", body="Integration test")
        assert issue.state == "open"
        self.__class__._issue_number = issue.number

    def test_08_issue_list(self) -> None:
        assert self._issue_number is not None
        issues = self.adapter.list_issues(state="open", limit=10)
        numbers = [i.number for i in issues]
        assert self._issue_number in numbers

    def test_09_issue_view(self) -> None:
        assert self._issue_number is not None
        issue = self.adapter.get_issue(self._issue_number)
        assert issue.title == "gfo-test-issue"

    def test_10_issue_close(self) -> None:
        assert self._issue_number is not None
        self.adapter.close_issue(self._issue_number)
        issue = self.adapter.get_issue(self._issue_number)
        assert issue.state == "closed"

    # --- Pull Request (非対応 → NotSupportedError) ---

    def test_11_pr_not_supported(self) -> None:
        with pytest.raises(NotSupportedError):
            self.adapter.list_pull_requests()

    def test_12_pr_create_not_supported(self) -> None:
        with pytest.raises(NotSupportedError):
            self.adapter.create_pull_request(
                title="test", base="main", head="test",
            )

    # --- Release ---

    def test_13_release_create(self) -> None:
        release = self.adapter.create_release(
            tag="v0.0.1-test", title="Test Release", notes="Integration test",
        )
        assert release.tag == "v0.0.1-test"

    def test_14_release_list(self) -> None:
        releases = self.adapter.list_releases(limit=10)
        tags = [r.tag for r in releases]
        assert "v0.0.1-test" in tags
