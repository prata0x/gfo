"""GitHub 統合テスト。"""

from __future__ import annotations

import pytest

from tests.integration.conftest import create_test_adapter, get_service_config

CONFIG = get_service_config("github")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.saas,
    pytest.mark.skipif(CONFIG is None, reason="GitHub credentials not configured"),
]


class TestGitHubIntegration:
    """GitHub に対する統合テスト。"""

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
            # リリース削除では git タグが残るため個別削除
            cls.adapter._client.delete(f"{cls.adapter._repos_path()}/git/refs/tags/v0.0.1-test")
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
        assert repo.full_name == f"{self.config.owner}/{self.config.repo}"

    def test_02_repo_list(self) -> None:
        # owner 指定は公開リポジトリのみ返すため、認証済み一覧（プライベート含む）を使用
        repos = self.adapter.list_repositories(limit=10)
        assert len(repos) > 0
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
        assert issue.title == "gfo-test-issue"
        assert issue.state == "open"
        self.__class__._issue_number = issue.number

    def test_08_issue_list(self) -> None:
        import time

        assert self._issue_number is not None
        # GitHub API は private repo で作成直後の issue がリストに反映されるまで遅延がある場合がある
        time.sleep(2)
        numbers: list[int] = []
        for _ in range(5):
            issues = self.adapter.list_issues(state="open", limit=0)
            numbers = [i.number for i in issues]
            if self._issue_number in numbers:
                break
            time.sleep(2)
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
        import base64
        import time

        from gfo.exceptions import GfoError

        # 前回マージ済みの場合はブランチに差分がないため、テストファイルを更新してコミットを追加する
        content = base64.b64encode(f"test run {time.time()}".encode()).decode()
        marker_path = f"{self.adapter._repos_path()}/contents/test-pr-marker.txt"
        payload: dict = {
            "message": "test: update marker for PR",
            "content": content,
            "branch": self.config.test_branch,
        }
        try:
            existing = self.adapter._client.get(
                marker_path, params={"ref": self.config.test_branch}
            )
            payload["sha"] = existing.json()["sha"]
        except GfoError:
            pass  # ファイルが存在しない場合は sha なしで新規作成
        self.adapter._client.put(marker_path, json=payload)

        pr = self.adapter.create_pull_request(
            title="gfo-test-pr",
            body="Integration test",
            base=self.config.default_branch,
            head=self.config.test_branch,
        )
        assert pr.title == "gfo-test-pr"
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
        import time

        # GitHub API は作成直後のリリースがリストに反映されるまで遅延がある場合がある
        tags: list[str] = []
        for _ in range(5):
            releases = self.adapter.list_releases(limit=0)
            tags = [r.tag for r in releases]
            if "v0.0.1-test" in tags:
                break
            time.sleep(2)
        assert "v0.0.1-test" in tags
