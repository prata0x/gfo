"""Azure DevOps 統合テスト。

Azure DevOps は release / label / milestone 非対応。
"""

from __future__ import annotations

import pytest

from gfo.exceptions import GfoError, NotSupportedError
from tests.integration.conftest import ServiceTestConfig, create_test_adapter, get_service_config

CONFIG = get_service_config("azure-devops")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.saas,
    pytest.mark.skipif(CONFIG is None, reason="Azure DevOps credentials not configured"),
]


class TestAzureDevOpsIntegration:
    """Azure DevOps に対する統合テスト。"""

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

    # --- Issue (Azure DevOps: Work Items) ---

    def test_07_issue_create(self) -> None:
        issue = self.adapter.create_issue(title="gfo-test-issue", body="Integration test")
        assert issue.title == "gfo-test-issue"
        self.__class__._issue_number = issue.number

    def test_08_issue_list(self) -> None:
        issues = self.adapter.list_issues(state="open", limit=10)
        assert len(issues) > 0

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
        import time

        assert self._pr_number is not None
        self.adapter.merge_pull_request(self._pr_number, method="merge")
        # Azure DevOps のマージは非同期の場合があるためポーリングして確認
        for _ in range(10):
            pr = self.adapter.get_pull_request(self._pr_number)
            if pr.state == "merged":
                break
            time.sleep(1)
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

        # ブランチの最新コミットID取得
        refs_resp = self.adapter._client.get(
            f"{self.adapter._git_path()}/refs",
            params={"filter": f"heads/{self.config.test_branch}"},
        )
        old_object_id = refs_resp.json()["value"][0]["objectId"]
        # コミット追加（ファイルが既存の場合は edit、なければ add）
        for change_type in ("add", "edit"):
            try:
                self.adapter._client.post(
                    f"{self.adapter._git_path()}/pushes",
                    json={
                        "refUpdates": [
                            {
                                "name": f"refs/heads/{self.config.test_branch}",
                                "oldObjectId": old_object_id,
                            }
                        ],
                        "commits": [
                            {
                                "comment": "test: add marker for close test",
                                "changes": [
                                    {
                                        "changeType": change_type,
                                        "item": {"path": "/test-close-marker.txt"},
                                        "newContent": {
                                            "content": f"close-{int(time.time())}",
                                            "contentType": "rawtext",
                                        },
                                    }
                                ],
                            }
                        ],
                    },
                )
                break
            except GfoError:
                if change_type == "edit":
                    raise
                # ファイル既存エラーの場合は edit で再試行するため objectId を再取得
                refs_resp = self.adapter._client.get(
                    f"{self.adapter._git_path()}/refs",
                    params={"filter": f"heads/{self.config.test_branch}"},
                )
                old_object_id = refs_resp.json()["value"][0]["objectId"]
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
