"""Gogs 統合テスト。

Gogs は PR / Label / Milestone 非対応のため、
Issue / Repository / Release のみテストする。
"""

from __future__ import annotations

import pytest

from gfo.exceptions import NotSupportedError
from tests.integration.conftest import (
    TEST_SSH_PUBLIC_KEY,
    ServiceTestConfig,
    create_test_adapter,
    get_service_config,
)

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
        cls._update_issue_number: int | None = None
        cls._update_issue_comment_id: int | None = None
        cls._webhook_id: int | None = None
        cls._deploy_key_id: int | None = None
        cls._head_sha: str | None = None

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

    # --- update_issue ---

    def test_18_update_issue(self) -> None:
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
        # クリーンアップ
        self.adapter.close_issue(issue.number)

    # --- update_pr（非対応）---

    def test_19_update_pr_not_supported(self) -> None:
        """Gogs は PR 非対応のため update_pull_request も NSE。"""
        with pytest.raises(NotSupportedError):
            self.adapter.update_pull_request(1, title="test")

    # --- create_comment (issue) + list_comments ---

    def test_20_issue_comment(self) -> None:
        """Issue にコメントを作成・一覧取得するテスト。"""
        assert self._issue_number is not None
        comment = self.adapter.create_comment("issue", self._issue_number, body="test comment body")
        assert comment.body == "test comment body"
        self.__class__._update_issue_comment_id = comment.id
        comments = self.adapter.list_comments("issue", self._issue_number)
        assert any(c.id == self._update_issue_comment_id for c in comments)

    # --- update_comment NSE + delete_comment NSE ---

    def test_21_comment_update_delete_not_supported(self) -> None:
        """Gogs は comment update/delete 非対応。"""
        assert self._update_issue_comment_id is not None
        with pytest.raises(NotSupportedError):
            self.adapter.update_comment("issue", self._update_issue_comment_id, body="updated")
        with pytest.raises(NotSupportedError):
            self.adapter.delete_comment("issue", self._update_issue_comment_id)

    # --- list_branches + create_branch + delete_branch ---

    def test_22_branch_operations(self) -> None:
        """ブランチの一覧・作成・削除テスト（Gogs: create_branch 未対応のため NSE スキップ）。"""
        branches = self.adapter.list_branches()
        names = [b.name for b in branches]
        assert self.config.default_branch in names
        try:
            branch = self.adapter.create_branch(
                name="gfo-test-branch-temp",
                ref=self.config.default_branch,
            )
            assert branch.name == "gfo-test-branch-temp"
            self.adapter.delete_branch(name="gfo-test-branch-temp")
            branches_after = self.adapter.list_branches()
            assert not any(b.name == "gfo-test-branch-temp" for b in branches_after)
        except NotSupportedError:
            pytest.skip("create_branch not supported by this Gogs instance")

    # --- create_tag + list_tags + delete_tag ---

    def test_23_tag_operations(self) -> None:
        """タグの作成・一覧・削除テスト（Gogs 0.13: create/delete 未対応のため NSE スキップ）。"""
        tags = self.adapter.list_tags()
        assert isinstance(tags, list)
        try:
            branch_resp = self.adapter._client.get(
                f"{self.adapter._repos_path()}/branches/{self.config.default_branch}"
            )
            commit = branch_resp.json()["commit"]
            # Gogs 0.13 は commit.id を使用、Gitea 系は commit.sha
            head_sha = commit.get("sha") or commit.get("id") or ""
            tag = self.adapter.create_tag(name="v0.0.2-test", ref=head_sha)
            assert tag.name == "v0.0.2-test"
            tags2 = self.adapter.list_tags()
            assert any(t.name == "v0.0.2-test" for t in tags2)
            self.adapter.delete_tag(name="v0.0.2-test")
            tags_after = self.adapter.list_tags()
            assert not any(t.name == "v0.0.2-test" for t in tags_after)
        except NotSupportedError:
            pytest.skip("create_tag not supported by this Gogs instance")

    # --- commit_status ---

    def test_24_commit_status(self) -> None:
        """コミットステータスの作成・一覧テスト（Gitea 継承、動作確認）。"""
        branch_resp = self.adapter._client.get(
            f"{self.adapter._repos_path()}/branches/{self.config.default_branch}"
        )
        commit = branch_resp.json()["commit"]
        # Gogs 0.13 は commit.id を使用、Gitea 系は commit.sha
        self.__class__._head_sha = commit.get("sha") or commit.get("id") or ""
        try:
            status = self.adapter.create_commit_status(
                self._head_sha,
                state="success",
                context="gfo-ci/test",
                description="Integration test status",
            )
            assert status.state == "success"
            statuses = self.adapter.list_commit_statuses(self._head_sha)
            assert isinstance(statuses, list)
        except NotSupportedError:
            pytest.skip("commit status not supported by this Gogs instance")

    # --- file CRUD ---

    def test_25_file_crud(self) -> None:
        """ファイルの作成・取得・更新・削除テスト（Gitea 継承、動作確認）。"""
        try:
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
        except NotSupportedError:
            pytest.skip("file operations not supported by this Gogs instance")

    # --- webhook CRUD ---

    def test_26_webhook_crud(self) -> None:
        """Webhook の作成・一覧・削除テスト（Gitea 継承、動作確認）。"""
        try:
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
            self.__class__._webhook_id = hook.id
            hooks = self.adapter.list_webhooks()
            assert any(h.id == self._webhook_id for h in hooks)
            self.adapter.delete_webhook(hook_id=self._webhook_id)
            hooks_after = self.adapter.list_webhooks()
            assert not any(h.id == self._webhook_id for h in hooks_after)
        except NotSupportedError:
            pytest.skip("webhook operations not supported by this Gogs instance")

    # --- deploy_key CRUD ---

    def test_27_deploy_key_crud(self) -> None:
        """デプロイキーの作成・一覧・削除テスト（Gitea 継承、動作確認）。"""
        try:
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
            self.__class__._deploy_key_id = key.id
            keys = self.adapter.list_deploy_keys()
            assert any(k.id == self._deploy_key_id for k in keys)
            self.adapter.delete_deploy_key(key_id=self._deploy_key_id)
            keys_after = self.adapter.list_deploy_keys()
            assert not any(k.id == self._deploy_key_id for k in keys_after)
        except NotSupportedError:
            pytest.skip("deploy key operations not supported by this Gogs instance")

    # --- get_current_user + search ---

    def test_28_user_and_search(self) -> None:
        """get_current_user, search_repositories, search_issues テスト。"""
        user = self.adapter.get_current_user()
        assert isinstance(user, dict)
        repos = self.adapter.search_repositories(self.config.repo[:4], limit=5)
        assert isinstance(repos, list)
        issues = self.adapter.search_issues("gfo-test", limit=5)
        assert isinstance(issues, list)

    # --- review NSE + pipeline NSE ---

    def test_29_review_pipeline_not_supported(self) -> None:
        """Gogs は review / pipeline 非対応（PR 非対応のため）。"""
        with pytest.raises(NotSupportedError):
            self.adapter.create_review(1, state="COMMENT", body="test")
        with pytest.raises(NotSupportedError):
            self.adapter.list_pipelines()

    # --- list_collaborators + wiki ---

    def test_30_collaborators_and_wiki(self) -> None:
        """list_collaborators と wiki CRUD テスト（Gitea 継承、動作確認）。"""
        try:
            collaborators = self.adapter.list_collaborators()
            assert isinstance(collaborators, list)
        except NotSupportedError:
            pytest.skip("list_collaborators not supported by this Gogs instance")
        try:
            try:
                self.adapter.delete_wiki_page("gfo-test-wiki")
            except Exception:
                pass
            page = self.adapter.create_wiki_page(
                title="gfo-test-wiki",
                content="hello wiki",
            )
            assert page.title == "gfo-test-wiki"
            pages = self.adapter.list_wiki_pages()
            assert any(p.title == "gfo-test-wiki" for p in pages)
            self.adapter.delete_wiki_page("gfo-test-wiki")
        except NotSupportedError:
            pytest.skip("wiki operations not supported by this Gogs instance")
