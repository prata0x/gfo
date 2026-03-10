"""Backlog 統合テスト。

Backlog は有料サービスのため、デフォルトではスキップされる。
アカウント保有者が手動で環境変数を設定した場合のみ実行される。

非対応操作: pr merge / release / label / milestone
"""

from __future__ import annotations

import os

import pytest

from gfo.exceptions import NotSupportedError
from tests.integration.conftest import create_test_adapter, get_service_config

CONFIG = get_service_config("backlog")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.saas,
    pytest.mark.skipif(
        CONFIG is None,
        reason="Backlog credentials not configured (paid service)",
    ),
]


class TestBacklogIntegration:
    """Backlog に対する統合テスト。"""

    @classmethod
    def setup_class(cls) -> None:
        assert CONFIG is not None
        cls.adapter = create_test_adapter(CONFIG)
        cls.config = CONFIG
        cls._issue_number: int | None = None
        cls._pr_number: int | None = None

    # --- Repository ---

    def test_01_repo_view(self) -> None:
        repo = self.adapter.get_repository()
        assert repo.name == self.config.repo

    def test_02_repo_list(self) -> None:
        repos = self.adapter.list_repositories(limit=10)
        assert len(repos) > 0

    # --- Label (非対応) ---

    def test_03_label_not_supported(self) -> None:
        with pytest.raises(NotSupportedError):
            self.adapter.list_labels()

    # --- Milestone (非対応) ---

    def test_04_milestone_not_supported(self) -> None:
        with pytest.raises(NotSupportedError):
            self.adapter.list_milestones()

    # --- Issue ---

    def test_05_issue_create(self) -> None:
        issue = self.adapter.create_issue(title="gfo-test-issue", body="Integration test")
        assert issue.title == "gfo-test-issue"
        self.__class__._issue_number = issue.number

    def test_06_issue_list(self) -> None:
        issues = self.adapter.list_issues(state="open", limit=10)
        assert len(issues) > 0

    def test_07_issue_view(self) -> None:
        assert self._issue_number is not None
        issue = self.adapter.get_issue(self._issue_number)
        assert issue.title == "gfo-test-issue"

    def test_08_issue_close(self) -> None:
        assert self._issue_number is not None
        self.adapter.close_issue(self._issue_number)
        issue = self.adapter.get_issue(self._issue_number)
        assert issue.state == "closed"

    # --- Pull Request (merge 以外は対応) ---

    def test_09_pr_create(self) -> None:
        pr = self.adapter.create_pull_request(
            title="gfo-test-pr", body="Integration test",
            base=self.config.default_branch, head=self.config.test_branch,
        )
        assert pr.state == "open"
        self.__class__._pr_number = pr.number

    def test_10_pr_list(self) -> None:
        assert self._pr_number is not None
        prs = self.adapter.list_pull_requests(state="open", limit=10)
        numbers = [p.number for p in prs]
        assert self._pr_number in numbers

    def test_11_pr_view(self) -> None:
        assert self._pr_number is not None
        pr = self.adapter.get_pull_request(self._pr_number)
        assert pr.title == "gfo-test-pr"

    def test_12_pr_merge_not_supported(self) -> None:
        assert self._pr_number is not None
        with pytest.raises(NotSupportedError):
            self.adapter.merge_pull_request(self._pr_number)

    def test_13_pr_close(self) -> None:
        assert self._pr_number is not None
        self.adapter.close_pull_request(self._pr_number)

    # --- Release (非対応) ---

    def test_14_release_not_supported(self) -> None:
        with pytest.raises(NotSupportedError):
            self.adapter.list_releases()
