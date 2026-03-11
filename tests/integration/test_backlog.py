"""Backlog 統合テスト。

Backlog は有料サービスのため、デフォルトではスキップされる。
アカウント保有者が手動で環境変数を設定した場合のみ実行される。

非対応操作: pr merge / release / label / milestone
"""

from __future__ import annotations

import pytest

from gfo.exceptions import NotSupportedError
from tests.integration.conftest import ServiceTestConfig, create_test_adapter, get_service_config

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
        cls._update_issue_number: int | None = None
        cls._update_pr_number: int | None = None
        cls._update_issue_comment_id: int | None = None
        cls._update_pr_comment_id: int | None = None
        cls._webhook_id: int | None = None
        cls._wiki_page_id: int | None = None

    @classmethod
    def teardown_class(cls) -> None:
        try:
            cls.adapter.delete_branch(name="gfo-test-branch-temp")
        except Exception:
            pass
        if cls._webhook_id is not None:
            try:
                cls.adapter.delete_webhook(hook_id=cls._webhook_id)
            except Exception:
                pass
        if cls._wiki_page_id is not None:
            try:
                cls.adapter.delete_wiki_page(cls._wiki_page_id)
            except Exception:
                pass
        if cls._update_issue_number is not None:
            try:
                cls.adapter.close_issue(cls._update_issue_number)
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
            title="gfo-test-pr",
            body="Integration test",
            base=self.config.default_branch,
            head=self.config.test_branch,
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

    # --- create_label/milestone/release NSE ---

    def test_15_create_nse(self) -> None:
        """create_label, create_milestone, create_release は非対応。"""
        with pytest.raises(NotSupportedError):
            self.adapter.create_label(name="test-label", color="ff0000")
        with pytest.raises(NotSupportedError):
            self.adapter.create_milestone(title="test-milestone")
        with pytest.raises(NotSupportedError):
            self.adapter.create_release(tag="v0.0.1-test", title="Test Release")

    # --- delete_label/milestone/release NSE ---

    def test_16_delete_nse(self) -> None:
        """delete_label, delete_milestone, delete_release は非対応。"""
        with pytest.raises(NotSupportedError):
            self.adapter.delete_label(name="test-label")
        with pytest.raises(NotSupportedError):
            self.adapter.delete_milestone(number=1)
        with pytest.raises(NotSupportedError):
            self.adapter.delete_release(tag="v0.0.1-test")

    # --- delete_issue ---

    def test_17_delete_issue(self) -> None:
        """Issue の削除テスト。"""
        assert self._issue_number is not None
        self.adapter.delete_issue(self._issue_number)

    # --- create_repository + delete_repository ---

    def test_18_repo_create_and_delete(self) -> None:
        """リポジトリの作成・削除テスト。"""
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

    def test_19_update_issue(self) -> None:
        """Issue の title/body 更新テスト。"""
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

    # --- update_pull_request ---

    def test_20_update_pull_request(self) -> None:
        """PR の title 更新テスト。"""
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

    def test_21_issue_comment(self) -> None:
        """Issue にコメント作成・一覧取得テスト。"""
        assert self._update_issue_number is not None
        comment = self.adapter.create_comment(
            "issue", self._update_issue_number, body="test comment body"
        )
        assert comment.body == "test comment body"
        self.__class__._update_issue_comment_id = comment.id
        comments = self.adapter.list_comments("issue", self._update_issue_number)
        assert any(c.id == self._update_issue_comment_id for c in comments)

    # --- update_comment + delete_comment ---

    def test_22_comment_update_and_delete(self) -> None:
        """Issue コメントの更新・削除テスト。"""
        assert self._update_issue_comment_id is not None
        updated = self.adapter.update_comment(
            "issue", self._update_issue_comment_id, body="updated comment"
        )
        assert updated.body == "updated comment"
        self.adapter.delete_comment("issue", self._update_issue_comment_id)

    # --- create_comment (pr) + list_comments (pr) ---

    def test_23_pr_comment(self) -> None:
        """PR にコメント作成・一覧取得テスト。"""
        assert self._update_pr_number is not None
        comment = self.adapter.create_comment("pr", self._update_pr_number, body="pr comment body")
        assert comment.body == "pr comment body"
        self.__class__._update_pr_comment_id = comment.id
        comments = self.adapter.list_comments("pr", self._update_pr_number)
        assert any(c.id == self._update_pr_comment_id for c in comments)

    # --- cleanup ---

    def test_24_cleanup_updates(self) -> None:
        """update_issue/update_pr のクリーンアップ。"""
        if self._update_issue_number is not None:
            self.adapter.close_issue(self._update_issue_number)
        if self._update_pr_number is not None:
            self.adapter.close_pull_request(self._update_pr_number)

    # --- list_branches + create_branch + delete_branch ---

    def test_25_branch_operations(self) -> None:
        """ブランチの一覧・作成・削除テスト。"""
        branches = self.adapter.list_branches()
        names = [b.name for b in branches]
        assert self.config.default_branch in names
        branch = self.adapter.create_branch(
            name="gfo-test-branch-temp",
            ref=self.config.default_branch,
        )
        assert branch.name == "gfo-test-branch-temp"
        self.adapter.delete_branch(name="gfo-test-branch-temp")
        branches_after = self.adapter.list_branches()
        assert not any(b.name == "gfo-test-branch-temp" for b in branches_after)

    # --- list_tags + create_tag + delete_tag NSE ---

    def test_26_tag_operations(self) -> None:
        """タグの一覧・作成テスト。delete_tag は非対応。"""
        tag = self.adapter.create_tag(
            name="v0.0.2-test",
            ref=self.config.default_branch,
        )
        assert tag.name == "v0.0.2-test"
        tags = self.adapter.list_tags()
        assert any(t.name == "v0.0.2-test" for t in tags)
        with pytest.raises(NotSupportedError):
            self.adapter.delete_tag(name="v0.0.2-test")

    # --- webhook CRUD ---

    def test_27_webhook_crud(self) -> None:
        """Webhook の作成・一覧・削除テスト。"""
        try:
            for h in self.adapter.list_webhooks():
                if h.url == "https://example.com/webhook":
                    self.adapter.delete_webhook(hook_id=h.id)
        except Exception:
            pass
        hook = self.adapter.create_webhook(
            url="https://example.com/webhook",
            events=[],
        )
        self.__class__._webhook_id = hook.id
        hooks = self.adapter.list_webhooks()
        assert any(h.id == self._webhook_id for h in hooks)
        self.adapter.delete_webhook(hook_id=self._webhook_id)
        self.__class__._webhook_id = None
        hooks_after = self.adapter.list_webhooks()
        assert not any(h.id == self._webhook_id for h in hooks_after)

    # --- get_current_user + search + list_collaborators ---

    def test_28_user_and_search(self) -> None:
        """get_current_user, search_repositories, search_issues, list_collaborators テスト。"""
        user = self.adapter.get_current_user()
        assert isinstance(user, dict)
        repos = self.adapter.search_repositories(self.config.repo[:4], limit=5)
        assert isinstance(repos, list)
        issues = self.adapter.search_issues("gfo-test", limit=5)
        assert isinstance(issues, list)
        collaborators = self.adapter.list_collaborators()
        assert isinstance(collaborators, list)

    # --- wiki CRUD ---

    def test_29_wiki_crud(self) -> None:
        """Wiki ページの作成・取得・一覧・更新・削除テスト。"""
        # 残留ページを削除
        try:
            for p in self.adapter.list_wiki_pages():
                if p.title == "gfo-test-wiki":
                    self.adapter.delete_wiki_page(p.id)
        except Exception:
            pass
        page = self.adapter.create_wiki_page(
            title="gfo-test-wiki",
            content="hello wiki",
        )
        self.__class__._wiki_page_id = page.id
        assert page.title == "gfo-test-wiki"
        fetched = self.adapter.get_wiki_page(page.id)
        assert fetched.title == "gfo-test-wiki"
        pages = self.adapter.list_wiki_pages()
        assert any(p.title == "gfo-test-wiki" for p in pages)
        updated = self.adapter.update_wiki_page(page.id, content="updated wiki content")
        assert "updated wiki content" in updated.content
        self.adapter.delete_wiki_page(page.id)
        self.__class__._wiki_page_id = None
        pages_after = self.adapter.list_wiki_pages()
        assert not any(p.title == "gfo-test-wiki" for p in pages_after)

    # --- commit_status NSE + file NSE + deploy_key NSE ---

    def test_30_nse_operations(self) -> None:
        """commit_status, file CRUD, deploy_key は非対応。"""
        with pytest.raises(NotSupportedError):
            self.adapter.create_commit_status("abc123", state="success", context="gfo-ci/test")
        with pytest.raises(NotSupportedError):
            self.adapter.get_file_content("README.md")
        with pytest.raises(NotSupportedError):
            self.adapter.create_or_update_file("test.txt", content="hello", message="test")
        with pytest.raises(NotSupportedError):
            self.adapter.list_deploy_keys()
        with pytest.raises(NotSupportedError):
            self.adapter.create_deploy_key(title="test", key="ssh-ed25519 AAAA test")

    # --- review NSE + pipeline NSE ---

    def test_31_review_pipeline_nse(self) -> None:
        """review, pipeline は非対応。"""
        assert self._pr_number is not None
        with pytest.raises(NotSupportedError):
            self.adapter.create_review(self._pr_number, state="COMMENT", body="test")
        with pytest.raises(NotSupportedError):
            self.adapter.list_pipelines()
