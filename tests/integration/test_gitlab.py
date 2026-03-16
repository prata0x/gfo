"""GitLab 統合テスト。"""

from __future__ import annotations

import pytest

from gfo.exceptions import GfoError, NotSupportedError
from tests.integration.conftest import (
    TEST_SSH_PUBLIC_KEY,
    ServiceTestConfig,
    create_test_adapter,
    get_service_config,
)

CONFIG = get_service_config("gitlab")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.saas,
    pytest.mark.skipif(CONFIG is None, reason="GitLab credentials not configured"),
]


class TestGitLabIntegration:
    """GitLab に対する統合テスト。"""

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
        cls._deploy_key_id: int | None = None
        cls._head_sha: str | None = None

    @classmethod
    def teardown_class(cls) -> None:
        """テスト終了後にテスト用リソースを削除する。"""
        try:
            cls.adapter.delete_release(tag="v0.0.1-test")
        except Exception:
            pass
        try:
            # リリース削除では git タグが残るため個別削除
            cls.adapter._client.delete(f"{cls.adapter._project_path()}/repository/tags/v0.0.1-test")
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
        # オープンなテスト用 MR を閉じる（マージ失敗時の残留対応）
        try:
            for pr in cls.adapter.list_pull_requests(state="open"):
                if pr.title == "gfo-test-pr":
                    cls.adapter.close_pull_request(pr.number)
        except Exception:
            pass
        try:
            cls.adapter.delete_branch(name="gfo-test-branch-temp")
        except Exception:
            pass
        try:
            cls.adapter._client.delete(f"{cls.adapter._project_path()}/repository/tags/v0.0.2-test")
        except Exception:
            pass
        try:
            if cls._webhook_id is not None:
                cls.adapter.delete_webhook(hook_id=cls._webhook_id)
        except Exception:
            pass
        try:
            if cls._deploy_key_id is not None:
                cls.adapter.delete_deploy_key(key_id=cls._deploy_key_id)
        except Exception:
            pass
        try:
            cls.adapter.delete_wiki_page("gfo-test-wiki")
        except Exception:
            pass
        try:
            if cls._update_issue_number is not None:
                cls.adapter.close_issue(cls._update_issue_number)
        except Exception:
            pass
        try:
            if cls._update_pr_number is not None:
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

    # --- Pull Request (GitLab では Merge Request) ---

    def test_11_pr_create(self) -> None:
        import time
        from urllib.parse import quote as _quote

        from gfo.exceptions import GfoError, NotFoundError

        # 残留オープン MR を閉じる（前回テストが途中終了した場合の対応）
        for pr in self.adapter.list_pull_requests(state="open"):
            if pr.title == "gfo-test-pr":
                try:
                    self.adapter.close_pull_request(pr.number)
                except Exception:
                    pass

        # test_branch が存在しない場合は再作成（前回マージで削除された場合の対応）
        try:
            self.adapter._client.get(
                f"{self.adapter._project_path()}/repository/branches"
                f"/{_quote(self.config.test_branch, safe='')}"
            )
        except NotFoundError:
            self.adapter._client.post(
                f"{self.adapter._project_path()}/repository/branches",
                json={"branch": self.config.test_branch, "ref": self.config.default_branch},
            )

        # ブランチに差分コミットを追加（前回マージ済みで差分がない場合の対応）
        content = f"test run {time.time()}\n"
        try:
            self.adapter._client.post(
                f"{self.adapter._project_path()}/repository/commits",
                json={
                    "branch": self.config.test_branch,
                    "commit_message": "test: update marker for MR",
                    "actions": [
                        {
                            "action": "update",
                            "file_path": "test-pr-marker.txt",
                            "content": content,
                        }
                    ],
                },
            )
        except GfoError:
            # ファイルが存在しない場合は create で再試行
            self.adapter._client.post(
                f"{self.adapter._project_path()}/repository/commits",
                json={
                    "branch": self.config.test_branch,
                    "commit_message": "test: add marker for MR",
                    "actions": [
                        {
                            "action": "create",
                            "file_path": "test-pr-marker.txt",
                            "content": content,
                        }
                    ],
                },
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
        # GitLab は MR 作成直後 merge_status が "checking" になるため、
        # "can_be_merged" になるまで最大 10 秒待機する
        import time

        merge_status = None
        for _ in range(10):
            resp = self.adapter._client.get(
                f"{self.adapter._project_path()}/merge_requests/{self._pr_number}"
            )
            merge_status = resp.json().get("merge_status")
            if merge_status == "can_be_merged":
                break
            time.sleep(1)
        if merge_status != "can_be_merged":
            pytest.fail(
                f"MR merge_status が 10 秒以内に 'can_be_merged' にならなかった: {merge_status}"
            )
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
        import time

        # マージ後にブランチが削除されている場合があるため再作成する
        try:
            self.adapter._client.get(
                f"{self.adapter._project_path()}/repository/branches/{self.config.test_branch}"
            )
        except GfoError:
            self.adapter._client.post(
                f"{self.adapter._project_path()}/repository/branches",
                json={"branch": self.config.test_branch, "ref": self.config.default_branch},
            )

        content = f"close-marker-{int(time.time())}"
        try:
            self.adapter._client.post(
                f"{self.adapter._project_path()}/repository/commits",
                json={
                    "branch": self.config.test_branch,
                    "commit_message": "test: add marker for close test",
                    "actions": [
                        {
                            "action": "update",
                            "file_path": "test-close-marker.txt",
                            "content": content,
                        }
                    ],
                },
            )
        except GfoError:
            self.adapter._client.post(
                f"{self.adapter._project_path()}/repository/commits",
                json={
                    "branch": self.config.test_branch,
                    "commit_message": "test: add marker for close test",
                    "actions": [
                        {
                            "action": "create",
                            "file_path": "test-close-marker.txt",
                            "content": content,
                        }
                    ],
                },
            )
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
            body="updated body",
        )
        assert updated.title == "gfo-test-update-issue-updated"

    # --- update_pr ---

    def test_24_update_pr(self) -> None:
        """MR（PR）の title 更新テスト。差分確保のため test_branch にコミットを追加してから MR 作成。"""
        import time
        from urllib.parse import quote as _quote

        from gfo.exceptions import NotFoundError

        # test_branch が存在しない場合は再作成
        try:
            self.adapter._client.get(
                f"{self.adapter._project_path()}/repository/branches"
                f"/{_quote(self.config.test_branch, safe='')}"
            )
        except NotFoundError:
            self.adapter._client.post(
                f"{self.adapter._project_path()}/repository/branches",
                json={"branch": self.config.test_branch, "ref": self.config.default_branch},
            )

        content = f"update-pr-{time.time()}\n"
        try:
            self.adapter._client.post(
                f"{self.adapter._project_path()}/repository/commits",
                json={
                    "branch": self.config.test_branch,
                    "commit_message": "test: add marker for update PR",
                    "actions": [
                        {
                            "action": "update",
                            "file_path": "test-update-pr-marker.txt",
                            "content": content,
                        }
                    ],
                },
            )
        except GfoError:
            self.adapter._client.post(
                f"{self.adapter._project_path()}/repository/commits",
                json={
                    "branch": self.config.test_branch,
                    "commit_message": "test: create marker for update PR",
                    "actions": [
                        {
                            "action": "create",
                            "file_path": "test-update-pr-marker.txt",
                            "content": content,
                        }
                    ],
                },
            )

        pr = self.adapter.create_pull_request(
            title="gfo-test-update-pr",
            body="original body",
            base=self.config.default_branch,
            head=self.config.test_branch,
        )
        self.__class__._update_pr_number = pr.number
        updated_pr = self.adapter.update_pull_request(
            pr.number,
            title="gfo-test-update-pr-updated",
        )
        assert updated_pr.title == "gfo-test-update-pr-updated"

    # --- create_comment (issue) ---

    def test_25_create_issue_comment(self) -> None:
        """Issue にコメントを作成するテスト。"""
        assert self._update_issue_number is not None
        comment = self.adapter.create_comment(
            "issue", self._update_issue_number, body="test comment body"
        )
        assert comment.body == "test comment body"
        self.__class__._update_issue_comment_id = comment.id

    # --- list_comments (issue) ---

    def test_26_list_issue_comments(self) -> None:
        """Issue コメント一覧に test_25 で作成したコメントが含まれることを確認する。"""
        assert self._update_issue_number is not None
        assert self._update_issue_comment_id is not None
        comments = self.adapter.list_comments("issue", self._update_issue_number)
        assert any(c.id == self._update_issue_comment_id for c in comments)

    # --- update_comment（GitLab 非対応）---

    def test_27_update_comment_not_supported(self) -> None:
        """GitLab は update_comment 非対応。"""
        assert self._update_issue_comment_id is not None
        with pytest.raises(NotSupportedError):
            self.adapter.update_comment("issue", self._update_issue_comment_id, body="updated")

    # --- delete_comment（GitLab 非対応）---

    def test_28_delete_comment_not_supported(self) -> None:
        """GitLab は delete_comment 非対応。"""
        assert self._update_issue_comment_id is not None
        with pytest.raises(NotSupportedError):
            self.adapter.delete_comment("issue", self._update_issue_comment_id)

    # --- PR comment ---

    def test_29_pr_comment(self) -> None:
        """MR にコメントを作成・一覧取得するテスト。"""
        assert self._update_pr_number is not None
        comment = self.adapter.create_comment("pr", self._update_pr_number, body="test PR comment")
        assert comment.body == "test PR comment"
        self.__class__._update_pr_comment_id = comment.id
        comments = self.adapter.list_comments("pr", self._update_pr_number)
        assert any(c.id == self._update_pr_comment_id for c in comments)

    # --- review ---

    def test_30_review(self) -> None:
        """MR にレビューを作成するテスト。GitLab は COMMENT state が approvals に反映されないため list のみ型チェック。"""
        assert self._update_pr_number is not None
        review = self.adapter.create_review(
            self._update_pr_number, state="COMMENT", body="test review"
        )
        assert review.body == "test review"
        reviews = self.adapter.list_reviews(self._update_pr_number)
        assert isinstance(
            reviews, list
        )  # COMMENT は approvals リストに出ないため len チェックしない

    # --- list_branches ---

    def test_32_list_branches(self) -> None:
        """ブランチ一覧にデフォルトブランチが含まれることを確認する。"""
        branches = self.adapter.list_branches()
        names = [b.name for b in branches]
        assert self.config.default_branch in names

    # --- create_branch ---

    def test_33_create_branch(self) -> None:
        """テスト用ブランチを作成するテスト。"""
        branch = self.adapter.create_branch(
            name="gfo-test-branch-temp",
            ref=self.config.default_branch,
        )
        assert branch.name == "gfo-test-branch-temp"

    # --- delete_branch ---

    def test_34_delete_branch(self) -> None:
        """test_33 で作成したブランチを削除するテスト。"""
        self.adapter.delete_branch(name="gfo-test-branch-temp")
        branches = self.adapter.list_branches()
        assert not any(b.name == "gfo-test-branch-temp" for b in branches)

    # --- create_tag ---

    def test_35_create_tag(self) -> None:
        """タグを作成するテスト。"""
        from urllib.parse import quote as _quote

        branch_resp = self.adapter._client.get(
            f"{self.adapter._project_path()}/repository/branches"
            f"/{_quote(self.config.default_branch, safe='')}"
        )
        head_sha = branch_resp.json()["commit"]["id"]
        tag = self.adapter.create_tag(name="v0.0.2-test", ref=head_sha)
        assert tag.name == "v0.0.2-test"

    # --- list_tags ---

    def test_36_list_tags(self) -> None:
        """タグ一覧に test_35 で作成したタグが含まれることを確認する。"""
        tags = self.adapter.list_tags()
        assert any(t.name == "v0.0.2-test" for t in tags)

    # --- delete_tag ---

    def test_37_delete_tag(self) -> None:
        """test_35 で作成したタグを削除するテスト。"""
        self.adapter.delete_tag(name="v0.0.2-test")
        tags = self.adapter.list_tags()
        assert not any(t.name == "v0.0.2-test" for t in tags)

    # --- create_commit_status ---

    def test_38_create_commit_status(self) -> None:
        """コミットステータスを作成するテスト。"""
        from urllib.parse import quote as _quote

        branch_resp = self.adapter._client.get(
            f"{self.adapter._project_path()}/repository/branches"
            f"/{_quote(self.config.default_branch, safe='')}"
        )
        self.__class__._head_sha = branch_resp.json()["commit"]["id"]
        status = self.adapter.create_commit_status(
            self._head_sha,
            state="success",
            context="gfo-ci/test",
            description="Integration test status",
        )
        assert status.state == "success"

    # --- list_commit_statuses ---

    def test_39_list_commit_statuses(self) -> None:
        """コミットステータス一覧を取得するテスト。"""
        assert self._head_sha is not None
        statuses = self.adapter.list_commit_statuses(self._head_sha)
        assert isinstance(statuses, list)

    # --- file CRUD ---

    def test_40_file_crud(self) -> None:
        """ファイルの作成・取得・更新・削除テスト。"""
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

    # --- webhook CRUD ---

    def test_41_webhook_crud(self) -> None:
        """Webhook の作成・一覧・削除テスト。"""
        try:
            for h in self.adapter.list_webhooks():
                if h.url == "https://example.com/webhook":
                    self.adapter.delete_webhook(hook_id=h.id)
        except Exception:
            pass
        hook = self.adapter.create_webhook(
            url="https://example.com/webhook",
            events=["push"],
        )
        assert hook.url == "https://example.com/webhook"
        self.__class__._webhook_id = hook.id
        hooks = self.adapter.list_webhooks()
        assert any(h.id == self._webhook_id for h in hooks)
        self.adapter.delete_webhook(hook_id=self._webhook_id)
        hooks_after = self.adapter.list_webhooks()
        assert not any(h.id == self._webhook_id for h in hooks_after)

    # --- deploy_key CRUD ---

    def test_42_deploy_key_crud(self) -> None:
        """デプロイキーの作成・一覧・削除テスト。"""
        try:
            for k in self.adapter.list_deploy_keys():
                if k.title == "gfo-test-deploy-key":
                    self.adapter.delete_deploy_key(key_id=k.id)
        except Exception:
            pass
        key = self.adapter.create_deploy_key(
            title="gfo-test-deploy-key",
            key=TEST_SSH_PUBLIC_KEY,
        )
        assert key.title == "gfo-test-deploy-key"
        self.__class__._deploy_key_id = key.id
        keys = self.adapter.list_deploy_keys()
        assert any(k.id == self._deploy_key_id for k in keys)
        self.adapter.delete_deploy_key(key_id=self._deploy_key_id)
        keys_after = self.adapter.list_deploy_keys()
        assert not any(k.id == self._deploy_key_id for k in keys_after)

    # --- get_current_user ---

    def test_43_get_current_user(self) -> None:
        """現在のユーザー情報を取得するテスト。"""
        user = self.adapter.get_current_user()
        assert isinstance(user, dict)
        assert "username" in user or "id" in user

    # --- search + misc ---

    def test_44_search_and_misc(self) -> None:
        """search_repositories, search_issues, list_collaborators, get_pr_checkout_refspec テスト。"""
        repos = self.adapter.search_repositories(self.config.repo[:4], limit=5)
        assert isinstance(repos, list)
        issues = self.adapter.search_issues("gfo-test", limit=5)
        assert isinstance(issues, list)
        collaborators = self.adapter.list_collaborators()
        assert isinstance(collaborators, list)
        assert self._pr_number is not None
        refspec = self.adapter.get_pr_checkout_refspec(self._pr_number)
        assert refspec

    # --- wiki CRUD ---

    def test_45_wiki_crud(self) -> None:
        """Wiki ページの作成・取得・一覧・更新・削除テスト。
        GitLab はタイトルの `-` をスペースに正規化するため `gfo test wiki` で検証する。
        """
        wiki_title = "gfo test wiki"
        wiki_slug = "gfo-test-wiki"
        try:
            self.adapter.delete_wiki_page(wiki_slug)
        except Exception:
            pass
        page = self.adapter.create_wiki_page(
            title=wiki_title,
            content="hello wiki content",
        )
        # GitLab はタイトルを正規化して返す（スペース区切り）
        assert page.title == wiki_title
        page_id = wiki_slug  # GitLab wiki の slug はハイフン区切り
        page_read = self.adapter.get_wiki_page(page_id)
        assert page_read.title == wiki_title
        pages = self.adapter.list_wiki_pages()
        assert any(p.title == wiki_title for p in pages)
        updated_page = self.adapter.update_wiki_page(
            page_id,
            content="updated wiki content",
        )
        assert "updated" in updated_page.content
        self.adapter.delete_wiki_page(page_id)
        pages_after = self.adapter.list_wiki_pages()
        assert not any(p.title == wiki_title for p in pages_after)

    # --- browse ---

    def test_46_browse(self) -> None:
        """get_web_url で Web URL を取得するテスト（--print モード相当）。"""
        url = self.adapter.get_web_url()
        assert isinstance(url, str)
        assert len(url) > 0
        assert "gitlab.com" in url

    # --- ssh-key CRUD ---

    def test_47_ssh_key_crud(self) -> None:
        """SSH キーの作成・一覧・削除テスト。"""
        import os
        import subprocess
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            key_path = os.path.join(tmpdir, "gfo_test_key")
            subprocess.run(
                ["ssh-keygen", "-t", "ed25519", "-f", key_path, "-N", "", "-C", "gfo-test"],
                capture_output=True,
                check=True,
            )
            with open(key_path + ".pub") as f:
                dummy_key = f.read().strip()
        # 残留キーをクリーンアップ
        try:
            for k in self.adapter.list_ssh_keys():
                if k.title == "gfo-test-ssh-key":
                    self.adapter.delete_ssh_key(key_id=k.id)
        except Exception:
            pass
        key = self.adapter.create_ssh_key(title="gfo-test-ssh-key", key=dummy_key)
        assert key.title == "gfo-test-ssh-key"
        keys = self.adapter.list_ssh_keys()
        assert any(k.id == key.id for k in keys)
        self.adapter.delete_ssh_key(key_id=key.id)
        keys_after = self.adapter.list_ssh_keys()
        assert not any(k.id == key.id for k in keys_after)

    # --- org ---

    def test_48_org_list(self) -> None:
        """Organization（グループ）一覧取得テスト。"""
        orgs = self.adapter.list_organizations()
        assert isinstance(orgs, list)

    # --- notification ---

    def test_49_notification_list(self) -> None:
        """通知（TODO）一覧取得テスト。"""
        notifications = self.adapter.list_notifications(limit=5)
        assert isinstance(notifications, list)

    # --- branch-protect ---

    def test_50_branch_protect_crud(self) -> None:
        """ブランチ保護の set → get → remove テスト。"""
        branch_name = self.config.test_branch
        # クリーンアップ
        try:
            self.adapter.remove_branch_protection(branch_name)
        except Exception:
            pass
        protection = self.adapter.set_branch_protection(branch_name)
        assert protection.branch == branch_name
        got = self.adapter.get_branch_protection(branch_name)
        assert got.branch == branch_name
        self.adapter.remove_branch_protection(branch_name)
        # 削除後は一覧に含まれないことを確認
        protections = self.adapter.list_branch_protections()
        assert not any(p.branch == branch_name for p in protections)

    # --- secret ---

    def test_51_secret_crud(self) -> None:
        """Secret（CI/CD variable, masked）の set → list → delete テスト。"""
        # クリーンアップ
        try:
            self.adapter.delete_secret("GFO_TEST_SECRET")
        except Exception:
            pass
        secret = self.adapter.set_secret("GFO_TEST_SECRET", "test-secret-value")
        assert secret.name == "GFO_TEST_SECRET"
        secrets = self.adapter.list_secrets()
        assert any(s.name == "GFO_TEST_SECRET" for s in secrets)
        self.adapter.delete_secret("GFO_TEST_SECRET")
        secrets_after = self.adapter.list_secrets()
        assert not any(s.name == "GFO_TEST_SECRET" for s in secrets_after)

    # --- variable ---

    def test_52_variable_crud(self) -> None:
        """Variable（CI/CD variable）の set → get → list → delete テスト。"""
        # クリーンアップ
        try:
            self.adapter.delete_variable("GFO_TEST_VAR")
        except Exception:
            pass
        var = self.adapter.set_variable("GFO_TEST_VAR", "test-value")
        assert var.name == "GFO_TEST_VAR"
        got = self.adapter.get_variable("GFO_TEST_VAR")
        assert got.name == "GFO_TEST_VAR"
        assert got.value == "test-value"
        variables = self.adapter.list_variables()
        assert any(v.name == "GFO_TEST_VAR" for v in variables)
        self.adapter.delete_variable("GFO_TEST_VAR")
        variables_after = self.adapter.list_variables()
        assert not any(v.name == "GFO_TEST_VAR" for v in variables_after)
