"""GitBucket 統合テスト。"""

from __future__ import annotations

import pytest

from gfo.exceptions import GfoError, NotSupportedError
from tests.integration.conftest import create_test_adapter, get_service_config

CONFIG = get_service_config("gitbucket")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.selfhosted,
    pytest.mark.skipif(CONFIG is None, reason="GitBucket credentials not configured"),
]


class TestGitBucketIntegration:
    """GitBucket に対する統合テスト。"""

    @classmethod
    def setup_class(cls) -> None:
        assert CONFIG is not None
        cls.adapter = create_test_adapter(CONFIG)
        cls.config = CONFIG
        cls._issue_number: int | None = None
        cls._pr_number: int | None = None

    @classmethod
    def teardown_class(cls) -> None:
        """テスト終了後にテスト用リソースを削除する。"""
        try:
            cls.adapter.delete_release(tag="v0.0.1-test")
        except Exception:
            pass
        try:
            cls.adapter.delete_label(name="gfo-test-label")
        except Exception:
            pass
        try:
            for ms in cls.adapter.list_milestones():
                if ms.title == "gfo-test-milestone":
                    cls.adapter.delete_milestone(number=ms.number)
                    break
        except Exception:
            pass

    # --- Repository ---

    def test_01_repo_view(self) -> None:
        repo = self.adapter.get_repository()
        assert repo.name == self.config.repo

    def test_02_repo_list(self) -> None:
        repos = self.adapter.list_repositories(owner=self.config.owner, limit=10)
        names = [r.name for r in repos]
        assert self.config.repo in names

    # --- Label ---

    def test_03_label_create(self) -> None:
        label = self.adapter.create_label(
            name="gfo-test-label",
            color="ff0000",
            description="Integration test",
        )
        assert label.name == "gfo-test-label"

    def test_04_label_list(self) -> None:
        labels = self.adapter.list_labels()
        names = [lb.name for lb in labels]
        assert "gfo-test-label" in names

    # --- Milestone ---

    def test_05_milestone_create(self) -> None:
        ms = self.adapter.create_milestone(
            title="gfo-test-milestone",
            description="Integration test",
        )
        assert ms.title == "gfo-test-milestone"

    def test_06_milestone_list(self) -> None:
        milestones = self.adapter.list_milestones()
        titles = [m.title for m in milestones]
        assert "gfo-test-milestone" in titles

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

    # --- Release ---

    def test_15_release_create(self) -> None:
        release = self.adapter.create_release(
            tag="v0.0.1-test",
            title="Test Release",
            notes="Integration test",
        )
        assert release.tag == "v0.0.1-test"

    def test_16_release_list(self) -> None:
        releases = self.adapter.list_releases(limit=10)
        tags = [r.tag for r in releases]
        assert "v0.0.1-test" in tags

    # --- PR close ---

    def test_17_pr_close(self) -> None:
        import base64
        import time

        content = base64.b64encode(f"close-test {time.time()}".encode()).decode()
        marker_path = f"{self.adapter._repos_path()}/contents/test-close-marker.txt"
        payload: dict = {
            "message": "test: add marker for close test",
            "content": content,
            "branch": self.config.test_branch,
        }
        try:
            existing = self.adapter._client.get(
                marker_path, params={"ref": self.config.test_branch}
            )
            payload["sha"] = existing.json()["sha"]
        except GfoError:
            pass
        self.adapter._client.put(marker_path, json=payload)
        pr = self.adapter.create_pull_request(
            title="gfo-test-pr-close",
            body="Integration test for close",
            base=self.config.default_branch,
            head=self.config.test_branch,
        )
        self.adapter.close_pull_request(pr.number)
        closed = self.adapter.get_pull_request(pr.number)
        assert closed.state == "closed"

    # --- Issue delete ---

    def test_18_issue_delete_not_supported(self) -> None:
        assert self._issue_number is not None
        with pytest.raises(NotSupportedError):
            self.adapter.delete_issue(self._issue_number)

    # --- Label delete ---

    def test_19_label_delete(self) -> None:
        self.adapter.delete_label(name="gfo-test-label")
        labels = self.adapter.list_labels()
        assert not any(lb.name == "gfo-test-label" for lb in labels)

    # --- Milestone delete ---

    def test_20_milestone_delete(self) -> None:
        milestones = self.adapter.list_milestones()
        test_ms = next((m for m in milestones if m.title == "gfo-test-milestone"), None)
        assert test_ms is not None
        self.adapter.delete_milestone(number=test_ms.number)
        milestones_after = self.adapter.list_milestones()
        assert not any(m.title == "gfo-test-milestone" for m in milestones_after)

    # --- Release delete ---

    def test_21_release_delete(self) -> None:
        self.adapter.delete_release(tag="v0.0.1-test")
        releases = self.adapter.list_releases()
        assert not any(r.tag == "v0.0.1-test" for r in releases)

    # --- Repo delete（非対応）---

    def test_22_repo_delete_not_supported(self) -> None:
        """GitBucket は DELETE /repos API 未実装のため非対応。"""
        with pytest.raises(NotSupportedError):
            self.adapter.delete_repository()
