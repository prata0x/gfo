"""Bitbucket Cloud 統合テスト。

Bitbucket は release / label / milestone 非対応。
"""

from __future__ import annotations

import pytest

from gfo.exceptions import NotSupportedError
from tests.integration.conftest import ServiceTestConfig, create_test_adapter, get_service_config

CONFIG = get_service_config("bitbucket")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.saas,
    pytest.mark.skipif(CONFIG is None, reason="Bitbucket credentials not configured"),
]


class TestBitbucketIntegration:
    """Bitbucket Cloud に対する統合テスト。"""

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
        repos = self.adapter.list_repositories(owner=self.config.owner, limit=10)
        assert len(repos) > 0

    # --- Label (非対応) ---

    def test_03_label_not_supported(self) -> None:
        with pytest.raises(NotSupportedError):
            self.adapter.list_labels()

    def test_04_label_create_not_supported(self) -> None:
        with pytest.raises(NotSupportedError):
            self.adapter.create_label(name="test")

    # --- Milestone (非対応) ---

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

    # --- Pull Request ---

    def test_11_pr_create(self) -> None:
        import time

        # 残留オープン PR を閉じる（前回テストが途中終了した場合の対応）
        for pr in self.adapter.list_pull_requests(state="open"):
            if pr.title == "gfo-test-pr":
                try:
                    self.adapter.close_pull_request(pr.number)
                except Exception:
                    pass

        # 前回マージ済みで差分がない場合に備えてマーカーファイルを更新
        # Bitbucket src API はマルチパートのため _session を直接使用する
        content = f"test run {time.time()}\n"
        self.adapter._client._session.post(
            f"{self.adapter._client.base_url}{self.adapter._repos_path()}/src",
            data={
                "message": "test: update marker for PR",
                "branch": self.config.test_branch,
            },
            files={"test-pr-marker.txt": ("test-pr-marker.txt", content.encode(), "text/plain")},
        )

        pr = self.adapter.create_pull_request(
            title="gfo-test-pr",
            body="Integration test",
            base=self.config.default_branch,
            head=self.config.test_branch,
        )
        assert pr.state == "open"
        self.__class__._pr_number = pr.number

    def test_12_pr_list(self) -> None:
        assert self._pr_number is not None
        prs = self.adapter.list_pull_requests(state="open", limit=10)
        numbers = [p.number for p in prs]
        assert self._pr_number in numbers

    def test_13_pr_view(self) -> None:
        assert self._pr_number is not None
        pr = self.adapter.get_pull_request(self._pr_number)
        assert pr.title == "gfo-test-pr"

    def test_14_pr_merge(self) -> None:
        assert self._pr_number is not None
        self.adapter.merge_pull_request(self._pr_number, method="merge")
        pr = self.adapter.get_pull_request(self._pr_number)
        assert pr.state == "merged"

    # --- Release (非対応) ---

    def test_15_release_not_supported(self) -> None:
        with pytest.raises(NotSupportedError):
            self.adapter.list_releases()

    def test_16_release_create_not_supported(self) -> None:
        with pytest.raises(NotSupportedError):
            self.adapter.create_release(tag="test", title="test")

    # --- PR close ---

    def test_17_pr_close(self) -> None:
        import time

        import requests as _requests

        parts = self.config.token.split(":", 1)
        auth = (parts[0], parts[1])
        content = f"close-{int(time.time())}"
        _requests.post(
            f"https://api.bitbucket.org/2.0/repositories/{self.config.owner}/{self.config.repo}/src",
            auth=auth,
            data={
                "test-close-marker.txt": content,
                "branch": self.config.test_branch,
                "message": "test: add marker for close test",
            },
        )
        # 既存オープンPRを閉じる
        for pr in self.adapter.list_pull_requests(state="open"):
            self.adapter.close_pull_request(pr.number)
        pr = self.adapter.create_pull_request(
            title="gfo-test-pr-close",
            body="Integration test",
            base=self.config.default_branch,
            head=self.config.test_branch,
        )
        self.adapter.close_pull_request(pr.number)
        closed = self.adapter.get_pull_request(pr.number)
        assert closed.state == "closed"

    # --- Issue delete ---

    def test_18_issue_delete(self) -> None:
        assert self._issue_number is not None
        self.adapter.delete_issue(self._issue_number)
        issues = self.adapter.list_issues(state="all", limit=50)
        assert not any(i.number == self._issue_number for i in issues)

    # --- Label delete (非対応) ---

    def test_19_label_delete_not_supported(self) -> None:
        with pytest.raises(NotSupportedError):
            self.adapter.delete_label(name="gfo-test-label")

    # --- Milestone delete (非対応) ---

    def test_20_milestone_delete_not_supported(self) -> None:
        with pytest.raises(NotSupportedError):
            self.adapter.delete_milestone(number=1)

    # --- Release delete (非対応) ---

    def test_21_release_delete_not_supported(self) -> None:
        with pytest.raises(NotSupportedError):
            self.adapter.delete_release(tag="v0.0.1-test")

    # --- Repo create and delete ---

    def test_22_repo_create_and_delete(self) -> None:
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
