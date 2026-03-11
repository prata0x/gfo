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
        cls._update_issue_number: int | None = None
        cls._update_pr_number: int | None = None
        cls._update_issue_comment_id: int | None = None
        cls._head_sha: str | None = None

    @classmethod
    def teardown_class(cls) -> None:
        try:
            cls.adapter.delete_branch(name="gfo-test-branch-temp")
        except Exception:
            pass
        try:
            cls.adapter.delete_tag(name="v0.0.2-test")
        except Exception:
            pass
        # 前回テストで残ったファイルのクリーンアップ
        for branch in [cls.config.test_branch, cls.config.default_branch]:
            try:
                _, sha = cls.adapter.get_file_content("gfo-test-file.txt", ref=branch)
                if sha:
                    cls.adapter.delete_file(
                        "gfo-test-file.txt",
                        sha=sha,
                        message="cleanup: gfo-test-file.txt",
                        branch=branch,
                    )
            except Exception:
                pass
        if cls._update_issue_number is not None:
            try:
                cls.adapter.delete_issue(cls._update_issue_number)
            except Exception:
                pass
        if cls._update_pr_number is not None:
            try:
                cls.adapter.close_pull_request(cls._update_pr_number)
            except Exception:
                pass

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

    # --- update_issue ---

    def test_23_update_issue(self) -> None:
        """Issue (Work Item) の title 更新テスト。"""
        issue = self.adapter.create_issue(
            title="gfo-test-update-issue",
            body="original body",
        )
        self.__class__._update_issue_number = issue.number
        updated = self.adapter.update_issue(
            issue.number,
            title="gfo-test-update-issue-updated",
        )
        assert updated.title == "gfo-test-update-issue-updated"

    # --- update_pr ---

    def test_24_update_pr(self) -> None:
        """PR の title 更新テスト。"""
        import time

        # test_branch に差分を追加
        refs_resp = self.adapter._client.get(
            f"{self.adapter._git_path()}/refs",
            params={"filter": f"heads/{self.config.test_branch}"},
        )
        old_object_id = refs_resp.json()["value"][0]["objectId"]
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
                                "comment": "test: add marker for update_pr test",
                                "changes": [
                                    {
                                        "changeType": change_type,
                                        "item": {"path": "/test-update-pr-marker.txt"},
                                        "newContent": {
                                            "content": f"update-pr-{int(time.time())}",
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
                refs_resp = self.adapter._client.get(
                    f"{self.adapter._git_path()}/refs",
                    params={"filter": f"heads/{self.config.test_branch}"},
                )
                old_object_id = refs_resp.json()["value"][0]["objectId"]

        # 既存オープン PR を閉じる
        for pr in self.adapter.list_pull_requests(state="open"):
            if pr.title in ("gfo-test-update-pr", "gfo-test-update-pr-updated"):
                try:
                    self.adapter.close_pull_request(pr.number)
                except Exception:
                    pass

        pr = self.adapter.create_pull_request(
            title="gfo-test-update-pr",
            body="Integration test",
            base=self.config.default_branch,
            head=self.config.test_branch,
        )
        self.__class__._update_pr_number = pr.number
        updated = self.adapter.update_pull_request(
            pr.number,
            title="gfo-test-update-pr-updated",
        )
        assert updated.title == "gfo-test-update-pr-updated"

    # --- create_comment (issue) + list_comments ---

    def test_25_issue_comment_create(self) -> None:
        """Issue コメント作成テスト。"""
        assert self._update_issue_number is not None
        comment = self.adapter.create_comment(
            "issue", self._update_issue_number, body="test comment body"
        )
        assert comment.body == "test comment body"
        self.__class__._update_issue_comment_id = comment.id

    def test_26_issue_comment_list(self) -> None:
        """Issue コメント一覧テスト。"""
        assert self._update_issue_number is not None
        comments = self.adapter.list_comments("issue", self._update_issue_number)
        assert any(c.id == self._update_issue_comment_id for c in comments)

    # --- update_comment (NSE) + delete_comment (NSE) ---

    def test_27_comment_update_not_supported(self) -> None:
        """Azure DevOps は comment update 非対応。"""
        assert self._update_issue_comment_id is not None
        with pytest.raises(NotSupportedError):
            self.adapter.update_comment("issue", self._update_issue_comment_id, body="updated")

    def test_28_comment_delete_not_supported(self) -> None:
        """Azure DevOps は comment delete 非対応。"""
        assert self._update_issue_comment_id is not None
        with pytest.raises(NotSupportedError):
            self.adapter.delete_comment("issue", self._update_issue_comment_id)

    # --- create_comment (pr) + list_comments (pr) ---

    def test_29_pr_comment(self) -> None:
        """PR にコメント作成・一覧取得テスト。"""
        assert self._update_pr_number is not None
        comment = self.adapter.create_comment("pr", self._update_pr_number, body="pr comment body")
        assert comment.body == "pr comment body"
        comments = self.adapter.list_comments("pr", self._update_pr_number)
        assert isinstance(comments, list)

    # --- review ---

    def test_30_review(self) -> None:
        """PR に review 作成・一覧テスト。"""
        assert self._update_pr_number is not None
        review = self.adapter.create_review(self._update_pr_number, state="COMMENT", body="")
        assert review is not None
        reviews = self.adapter.list_reviews(self._update_pr_number)
        assert isinstance(reviews, list)

    # --- cleanup ---

    def test_31_cleanup_updates(self) -> None:
        """update_issue/update_pr のクリーンアップ。"""
        if self._update_issue_number is not None:
            self.adapter.close_issue(self._update_issue_number)
        if self._update_pr_number is not None:
            self.adapter.close_pull_request(self._update_pr_number)

    # --- list_branches + create_branch + delete_branch ---

    def test_32_list_branches(self) -> None:
        """ブランチ一覧テスト。"""
        branches = self.adapter.list_branches()
        names = [b.name for b in branches]
        assert self.config.default_branch in names

    def test_33_create_branch(self) -> None:
        """ブランチ作成テスト。AzDO は ref に commit hash を要求する。"""
        refs_resp = self.adapter._client.get(
            f"{self.adapter._git_path()}/refs",
            params={"filter": f"heads/{self.config.default_branch}"},
        )
        head_sha = refs_resp.json()["value"][0]["objectId"]
        branch = self.adapter.create_branch(
            name="gfo-test-branch-temp",
            ref=head_sha,
        )
        assert branch.name == "gfo-test-branch-temp"

    def test_34_delete_branch(self) -> None:
        """ブランチ削除テスト。"""
        self.adapter.delete_branch(name="gfo-test-branch-temp")
        branches_after = self.adapter.list_branches()
        assert not any(b.name == "gfo-test-branch-temp" for b in branches_after)

    # --- create_tag + list_tags + delete_tag ---

    def test_35_create_tag(self) -> None:
        """タグ作成テスト。AzDO は ref に commit hash を要求する。"""
        refs_resp = self.adapter._client.get(
            f"{self.adapter._git_path()}/refs",
            params={"filter": f"heads/{self.config.default_branch}"},
        )
        head_sha = refs_resp.json()["value"][0]["objectId"]
        self.__class__._head_sha = head_sha
        tag = self.adapter.create_tag(name="v0.0.2-test", ref=head_sha)
        assert tag.name == "v0.0.2-test"

    def test_36_list_tags(self) -> None:
        """タグ一覧テスト。"""
        tags = self.adapter.list_tags()
        assert any(t.name == "v0.0.2-test" for t in tags)

    def test_37_delete_tag(self) -> None:
        """タグ削除テスト。"""
        self.adapter.delete_tag(name="v0.0.2-test")
        tags_after = self.adapter.list_tags()
        assert not any(t.name == "v0.0.2-test" for t in tags_after)

    # --- create_commit_status + list_commit_statuses ---

    def test_38_create_commit_status(self) -> None:
        """コミットステータス作成テスト。"""
        assert self._head_sha is not None
        status = self.adapter.create_commit_status(
            self._head_sha,
            state="success",
            context="gfo-ci/test",
            description="Integration test status",
        )
        assert status.state == "success"

    def test_39_list_commit_statuses(self) -> None:
        """コミットステータス一覧テスト。"""
        assert self._head_sha is not None
        statuses = self.adapter.list_commit_statuses(self._head_sha)
        assert isinstance(statuses, list)

    # --- file CRUD ---

    def test_40_file_crud(self) -> None:
        """ファイルの作成・取得・更新・削除テスト。"""
        # 前回テストで残ったファイルを先にクリーンアップ
        try:
            _, sha = self.adapter.get_file_content("gfo-test-file.txt", ref=self.config.test_branch)
            if sha:
                self.adapter.delete_file(
                    "gfo-test-file.txt",
                    sha=sha,
                    message="cleanup: gfo-test-file.txt",
                    branch=self.config.test_branch,
                )
        except Exception:
            pass
        self.adapter.create_or_update_file(
            "gfo-test-file.txt",
            content="hello gfo",
            message="test: create gfo-test-file.txt",
            branch=self.config.test_branch,
        )
        content, sha = self.adapter.get_file_content(
            "gfo-test-file.txt", ref=self.config.test_branch
        )
        assert content == "hello gfo"
        self.adapter.create_or_update_file(
            "gfo-test-file.txt",
            content="updated gfo",
            message="test: update gfo-test-file.txt",
            sha=sha,
            branch=self.config.test_branch,
        )
        content2, sha2 = self.adapter.get_file_content(
            "gfo-test-file.txt", ref=self.config.test_branch
        )
        assert content2 == "updated gfo"
        self.adapter.delete_file(
            "gfo-test-file.txt",
            sha=sha2,
            message="test: delete gfo-test-file.txt",
            branch=self.config.test_branch,
        )

    # --- webhook NSE ---

    def test_41_webhook_not_supported(self) -> None:
        """Azure DevOps は webhook 非対応。"""
        with pytest.raises(NotSupportedError):
            self.adapter.list_webhooks()
        with pytest.raises(NotSupportedError):
            self.adapter.create_webhook(url="https://example.com/webhook", events=["push"])

    # --- deploy_key NSE ---

    def test_42_deploy_key_not_supported(self) -> None:
        """Azure DevOps は deploy key 非対応。"""
        with pytest.raises(NotSupportedError):
            self.adapter.list_deploy_keys()
        with pytest.raises(NotSupportedError):
            self.adapter.create_deploy_key(title="test", key="ssh-ed25519 AAAA test")

    # --- get_current_user ---

    def test_43_get_current_user(self) -> None:
        """現在のユーザー情報取得テスト。"""
        user = self.adapter.get_current_user()
        assert isinstance(user, dict)
        assert "id" in user or "displayName" in user

    # --- search + misc ---

    def test_44_search_and_misc(self) -> None:
        """search_repositories, search_issues, collaborators NSE, wiki NSE テスト。"""
        repos = self.adapter.search_repositories(self.config.repo[:4], limit=5)
        assert isinstance(repos, list)
        issues = self.adapter.search_issues("gfo-test", limit=5)
        assert isinstance(issues, list)
        # list_collaborators は NSE
        with pytest.raises(NotSupportedError):
            self.adapter.list_collaborators()
        # wiki は NSE
        with pytest.raises(NotSupportedError):
            self.adapter.list_wiki_pages()
        with pytest.raises(NotSupportedError):
            self.adapter.create_wiki_page(title="test", content="test")
        # get_pr_checkout_refspec テスト
        prs = self.adapter.list_pull_requests(state="open", limit=1)
        if prs:
            refspec = self.adapter.get_pr_checkout_refspec(prs[0].number)
            assert isinstance(refspec, str)
