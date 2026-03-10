"""Gogs 統合テスト。

Gogs は PR / Label / Milestone 非対応のため、
Issue / Repository / Release のみテストする。
"""

from __future__ import annotations

import pytest

from gfo.exceptions import NotSupportedError
from tests.integration.conftest import ServiceTestConfig, create_test_adapter, get_service_config

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
                title="test",
                base="main",
                head="test",
            )

    # --- Release (非対応 → NotSupportedError) ---

    def test_13_release_create_not_supported(self) -> None:
        with pytest.raises(NotSupportedError):
            self.adapter.create_release(
                tag="v0.0.1-test",
                title="Test Release",
                notes="Integration test",
            )

    def test_14_release_list_not_supported(self) -> None:
        with pytest.raises(NotSupportedError):
            self.adapter.list_releases(limit=10)

    # --- Issue delete（非対応）---

    def test_15_issue_delete_not_supported(self) -> None:
        assert self._issue_number is not None
        with pytest.raises(NotSupportedError):
            self.adapter.delete_issue(self._issue_number)

    # --- PR close (非対応) ---

    def test_17_pr_close_not_supported(self) -> None:
        with pytest.raises(NotSupportedError):
            self.adapter.close_pull_request(1)

    # --- Repo create and delete ---

    def test_16_repo_create_and_delete(self) -> None:
        import time

        temp_name = f"gfo-test-temp-{int(time.time())}"
        temp_adapter = None
        try:
            repo = self.adapter.create_repository(
                name=temp_name, private=True, description="Integration test temp"
            )
            assert repo.name == temp_name
            temp_config = ServiceTestConfig(
                service_type=self.config.service_type,
                host=self.config.host,
                api_url=self.config.api_url,
                owner=self.config.owner,
                repo=temp_name,
                token=self.config.token,
                organization=self.config.organization,
                project_key=self.config.project_key,
            )
            temp_adapter = create_test_adapter(temp_config)
            temp_adapter.delete_repository()
        except Exception:
            if temp_adapter is not None:
                try:
                    temp_adapter.delete_repository()
                except Exception:
                    pass
            raise
