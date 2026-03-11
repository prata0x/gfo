"""Bitbucket Cloud 統合テスト。

Bitbucket は release / label / milestone 非対応。
"""

from __future__ import annotations

import pytest

from gfo.exceptions import AuthenticationError, NotSupportedError
from tests.integration.conftest import (
    TEST_SSH_PUBLIC_KEY,
    ServiceTestConfig,
    create_test_adapter,
    get_service_config,
)

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
        cls._update_issue_number: int | None = None
        cls._update_pr_number: int | None = None
        cls._update_issue_comment_id: int | None = None
        cls._webhook_id: int | None = None
        cls._deploy_key_id: int | None = None
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
        if cls._webhook_id is not None:
            try:
                cls.adapter.delete_webhook(hook_id=cls._webhook_id)
            except Exception:
                pass
        if cls._deploy_key_id is not None:
            try:
                cls.adapter.delete_deploy_key(key_id=cls._deploy_key_id)
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

    # --- update_issue ---

    def test_23_update_issue(self) -> None:
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

    # --- update_pr ---

    def test_24_update_pr(self) -> None:
        """PR の title 更新テスト。"""
        import time

        # test_branch にマーカーファイルを追加して差分を確保
        content = f"update-pr-{time.time()}\n"
        self.adapter._client._session.post(
            f"{self.adapter._client.base_url}{self.adapter._repos_path()}/src",
            data={
                "message": "test: add marker for update_pr test",
                "branch": self.config.test_branch,
            },
            files={
                "test-update-pr-marker.txt": (
                    "test-update-pr-marker.txt",
                    content.encode(),
                    "text/plain",
                )
            },
        )
        # 残留オープン PR を閉じる
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
        """Issue にコメント作成テスト。"""
        assert self._update_issue_number is not None
        comment = self.adapter.create_comment(
            "issue", self._update_issue_number, body="test comment body"
        )
        assert comment.body == "test comment body"
        self.__class__._update_issue_comment_id = comment.id

    def test_26_issue_comment_list(self) -> None:
        """Issue のコメント一覧テスト。"""
        assert self._update_issue_number is not None
        comments = self.adapter.list_comments("issue", self._update_issue_number)
        assert any(c.id == self._update_issue_comment_id for c in comments)

    # --- update_comment / delete_comment (NSE) ---
    # Bitbucket: issue comment update/delete には URL に issue_number が必要なため NSE

    def test_27_issue_comment_update(self) -> None:
        """Bitbucket は comment update が NSE（issue_number が URL に必要）。"""
        with pytest.raises(NotSupportedError):
            self.adapter.update_comment("issue", 1, body="updated")
        with pytest.raises(NotSupportedError):
            self.adapter.update_comment("pr", 1, body="updated")

    def test_28_issue_comment_delete(self) -> None:
        """Bitbucket は comment delete が NSE（issue_number が URL に必要）。"""
        with pytest.raises(NotSupportedError):
            self.adapter.delete_comment("issue", 1)
        with pytest.raises(NotSupportedError):
            self.adapter.delete_comment("pr", 1)

    # --- create_comment (pr) + list_comments (pr) ---

    def test_29_pr_comment(self) -> None:
        """PR にコメント作成・一覧取得テスト。"""
        assert self._update_pr_number is not None
        comment = self.adapter.create_comment("pr", self._update_pr_number, body="pr comment body")
        assert comment.body == "pr comment body"
        comments = self.adapter.list_comments("pr", self._update_pr_number)
        assert any(c.id == comment.id for c in comments)

    # --- review ---

    def test_30_review(self) -> None:
        """PR に review 作成・一覧テスト。"""
        assert self._update_pr_number is not None
        review = self.adapter.create_review(
            self._update_pr_number, state="COMMENT", body="test review"
        )
        assert review.body == "test review"
        reviews = self.adapter.list_reviews(self._update_pr_number)
        assert isinstance(reviews, list)

    # --- cleanup: close update_issue + close update_pr ---

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
        """ブランチ作成テスト。Bitbucket は ref に commit hash を要求する。"""
        branches = self.adapter.list_branches()
        default = next(b for b in branches if b.name == self.config.default_branch)
        branch = self.adapter.create_branch(
            name="gfo-test-branch-temp",
            ref=default.sha,
        )
        assert branch.name == "gfo-test-branch-temp"

    def test_34_delete_branch(self) -> None:
        """ブランチ削除テスト。"""
        self.adapter.delete_branch(name="gfo-test-branch-temp")
        branches_after = self.adapter.list_branches()
        assert not any(b.name == "gfo-test-branch-temp" for b in branches_after)

    # --- create_tag + list_tags + delete_tag ---

    def test_35_create_tag(self) -> None:
        """タグ作成テスト。Bitbucket は ref に commit hash を要求する。"""
        branches = self.adapter.list_branches()
        default = next(b for b in branches if b.name == self.config.default_branch)
        tag = self.adapter.create_tag(name="v0.0.2-test", ref=default.sha)
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
        branches = self.adapter.list_branches()
        default = next(b for b in branches if b.name == self.config.default_branch)
        self.__class__._head_sha = default.sha
        status = self.adapter.create_commit_status(
            default.sha,
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
        """ファイルの作成・取得・更新・削除テスト。Bitbucket は sha 不要。"""
        self.adapter.create_or_update_file(
            "gfo-test-file.txt",
            content="hello gfo",
            message="test: create gfo-test-file.txt",
            branch=self.config.test_branch,
        )
        content, _ = self.adapter.get_file_content("gfo-test-file.txt", ref=self.config.test_branch)
        assert content == "hello gfo"
        self.adapter.create_or_update_file(
            "gfo-test-file.txt",
            content="updated gfo",
            message="test: update gfo-test-file.txt",
            branch=self.config.test_branch,
        )
        content2, _ = self.adapter.get_file_content(
            "gfo-test-file.txt", ref=self.config.test_branch
        )
        assert content2 == "updated gfo"
        self.adapter.delete_file(
            "gfo-test-file.txt",
            sha="",
            message="test: delete gfo-test-file.txt",
            branch=self.config.test_branch,
        )

    # --- webhook CRUD ---

    def test_41_webhook_crud(self) -> None:
        """Webhook の作成・一覧・削除テスト（トークンに webhook スコープがない場合はスキップ）。"""
        try:
            for h in self.adapter.list_webhooks():
                if h.url == "https://example.com/webhook":
                    self.adapter.delete_webhook(hook_id=h.id)
        except Exception:
            pass
        try:
            hook = self.adapter.create_webhook(
                url="https://example.com/webhook",
                events=["repo:push"],
            )
        except AuthenticationError:
            pytest.skip("Token does not have webhook scope")
        self.__class__._webhook_id = hook.id
        hooks = self.adapter.list_webhooks()
        assert any(h.id == self._webhook_id for h in hooks)
        self.adapter.delete_webhook(hook_id=self._webhook_id)
        self.__class__._webhook_id = None
        hooks_after = self.adapter.list_webhooks()
        assert not any(h.url == "https://example.com/webhook" for h in hooks_after)

    # --- deploy_key CRUD ---

    def test_42_deploy_key_crud(self) -> None:
        """デプロイキーの作成・一覧・削除テスト（トークンに deploy-keys スコープがない場合はスキップ）。"""
        try:
            for k in self.adapter.list_deploy_keys():
                if k.title == "gfo-test-deploy-key":
                    self.adapter.delete_deploy_key(key_id=k.id)
        except Exception:
            pass
        try:
            key = self.adapter.create_deploy_key(
                title="gfo-test-deploy-key",
                key=TEST_SSH_PUBLIC_KEY,
            )
        except AuthenticationError:
            pytest.skip("Token does not have deploy-keys scope")
        self.__class__._deploy_key_id = key.id
        keys = self.adapter.list_deploy_keys()
        assert any(k.id == self._deploy_key_id for k in keys)
        self.adapter.delete_deploy_key(key_id=self._deploy_key_id)
        self.__class__._deploy_key_id = None
        keys_after = self.adapter.list_deploy_keys()
        assert not any(k.id == self._deploy_key_id for k in keys_after)

    # --- get_current_user ---

    def test_43_get_current_user(self) -> None:
        """現在のユーザー情報取得テスト（トークンに account スコープがない場合はスキップ）。"""
        try:
            user = self.adapter.get_current_user()
        except AuthenticationError:
            pytest.skip("Token does not have account scope")
        assert isinstance(user, dict)
        assert "account_id" in user or "username" in user or "nickname" in user

    # --- search + misc ---

    def test_44_search_and_misc(self) -> None:
        """search_repositories, search_issues, list_collaborators, get_pr_checkout_refspec, wiki NSE テスト。"""
        repos = self.adapter.search_repositories(self.config.repo[:4], limit=5)
        assert isinstance(repos, list)
        issues = self.adapter.search_issues("gfo-test", limit=5)
        assert isinstance(issues, list)
        try:
            collaborators = self.adapter.list_collaborators()
            assert isinstance(collaborators, list)
        except AuthenticationError:
            pass  # account スコープなしの場合はスキップ
        # PR が存在すれば checkout refspec テスト
        prs = self.adapter.list_pull_requests(state="open", limit=1)
        if prs:
            refspec = self.adapter.get_pr_checkout_refspec(prs[0].number)
            assert isinstance(refspec, str)
        # Wiki は非対応
        with pytest.raises(NotSupportedError):
            self.adapter.list_wiki_pages()
        with pytest.raises(NotSupportedError):
            self.adapter.create_wiki_page(title="test", content="test")
