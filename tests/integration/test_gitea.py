"""Gitea 統合テスト。"""

from __future__ import annotations

import subprocess
import tempfile

import pytest

from gfo.exceptions import GfoError
from tests.integration.conftest import ServiceTestConfig, create_test_adapter, get_service_config

CONFIG = get_service_config("gitea")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.selfhosted,
    pytest.mark.skipif(CONFIG is None, reason="Gitea credentials not configured"),
]


class TestGiteaIntegration:
    """Gitea に対する統合テスト。

    テストメソッドはアルファベット順（名前順）に実行される。
    テスト間で作成したリソースの番号をクラス変数で共有する。
    """

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
        try:
            cls.adapter.delete_branch(name="gfo-test-branch-temp")
        except Exception:
            pass
        try:
            cls.adapter.delete_tag(name="v0.0.2-test")
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
            for p in cls.adapter.list_wiki_pages():
                if p.title == "gfo-test-wiki":
                    cls.adapter.delete_wiki_page(p.id)
        except Exception:
            pass
        try:
            content, sha = cls.adapter.get_file_content("gfo-test-file.txt")
            cls.adapter.delete_file("gfo-test-file.txt", sha=sha, message="teardown: cleanup")
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

    @classmethod
    def _sync_wiki_master(cls) -> None:
        """Gitea 1.22 の wiki ブランチ不整合修正: main → master を同期する。

        Gitea 1.22 は wiki への書き込みを main ブランチ、
        読み取りを master ブランチで行うため、write 後に手動で同期が必要。
        git clone + HEAD:refs/heads/master へ force push で同期する。
        """
        host = cls.config.host or "localhost:3000"
        owner = cls.config.owner
        repo = cls.config.repo
        token = cls.config.token
        wiki_url = f"http://gfo-admin:{token}@{host}/{owner}/{repo}.wiki.git"

        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = f"{tmpdir}/wiki"
            try:
                r = subprocess.run(
                    ["git", "clone", "--depth=1", wiki_url, wiki_dir],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    timeout=30,
                )
                if r.returncode != 0:
                    return  # wiki がまだ初期化されていない場合はスキップ
                # 現在の HEAD (= main の先端) を master ブランチとして force push
                subprocess.run(
                    ["git", "push", "origin", "HEAD:refs/heads/master", "--force"],
                    cwd=wiki_dir,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    timeout=30,
                )
            except Exception:
                pass  # ベストエフォート

    # --- Phase 1: Repository ---

    def test_01_repo_view(self) -> None:
        repo = self.adapter.get_repository()
        assert repo.name == self.config.repo
        assert self.config.owner in repo.full_name

    def test_02_repo_list(self) -> None:
        repos = self.adapter.list_repositories(owner=self.config.owner, limit=10)
        assert len(repos) > 0
        names = [r.name for r in repos]
        assert self.config.repo in names

    # --- Phase 2: Label ---

    def test_03_label_create(self) -> None:
        label = self.adapter.create_label(
            name="gfo-test-label",
            color="ff0000",
            description="Integration test label",
        )
        assert label.name == "gfo-test-label"

    def test_04_label_list(self) -> None:
        labels = self.adapter.list_labels()
        names = [lb.name for lb in labels]
        assert "gfo-test-label" in names

    # --- Phase 3: Milestone ---

    def test_05_milestone_create(self) -> None:
        ms = self.adapter.create_milestone(
            title="gfo-test-milestone",
            description="Integration test milestone",
        )
        assert ms.title == "gfo-test-milestone"

    def test_06_milestone_list(self) -> None:
        milestones = self.adapter.list_milestones()
        titles = [m.title for m in milestones]
        assert "gfo-test-milestone" in titles

    # --- Phase 4: Issue ---

    def test_07_issue_create(self) -> None:
        issue = self.adapter.create_issue(
            title="gfo-test-issue",
            body="Integration test issue",
        )
        assert issue.title == "gfo-test-issue"
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

    # --- Phase 5: Pull Request ---

    def test_11_pr_create(self) -> None:
        pr = self.adapter.create_pull_request(
            title="gfo-test-pr",
            body="Integration test PR",
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

    # --- Phase 6: Release ---

    def test_15_release_create(self) -> None:
        release = self.adapter.create_release(
            tag="v0.0.1-test",
            title="Test Release",
            notes="Integration test release",
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

        content = base64.b64encode(f"close-{time.time()}".encode()).decode()
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
            self.adapter._client.put(marker_path, json=payload)
        except GfoError:
            self.adapter._client.post(marker_path, json=payload)
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
        """PR の title 更新テスト。差分確保のため test_branch にコミットを追加してから PR 作成。"""
        import base64
        import time

        content = base64.b64encode(f"update-pr-{time.time()}".encode()).decode()
        marker_path = f"{self.adapter._repos_path()}/contents/test-update-pr-marker.txt"
        payload: dict = {
            "message": "test: add marker for update PR",
            "content": content,
            "branch": self.config.test_branch,
        }
        try:
            existing = self.adapter._client.get(
                marker_path, params={"ref": self.config.test_branch}
            )
            payload["sha"] = existing.json()["sha"]
            self.adapter._client.put(marker_path, json=payload)
        except GfoError:
            self.adapter._client.post(marker_path, json=payload)
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

    # --- update_comment ---

    def test_27_update_comment(self) -> None:
        """コメント本文を更新するテスト。"""
        assert self._update_issue_comment_id is not None
        updated = self.adapter.update_comment(
            "issue", self._update_issue_comment_id, body="updated comment body"
        )
        assert updated.body == "updated comment body"

    # --- delete_comment ---

    def test_28_delete_comment(self) -> None:
        """コメントを削除するテスト。"""
        assert self._update_issue_comment_id is not None
        assert self._update_issue_number is not None
        self.adapter.delete_comment("issue", self._update_issue_comment_id)
        comments = self.adapter.list_comments("issue", self._update_issue_number)
        assert not any(c.id == self._update_issue_comment_id for c in comments)

    # --- PR comment ---

    def test_29_pr_comment(self) -> None:
        """PR にコメントを作成・一覧取得するテスト。"""
        assert self._update_pr_number is not None
        comment = self.adapter.create_comment("pr", self._update_pr_number, body="test PR comment")
        assert comment.body == "test PR comment"
        self.__class__._update_pr_comment_id = comment.id
        comments = self.adapter.list_comments("pr", self._update_pr_number)
        assert any(c.id == self._update_pr_comment_id for c in comments)

    # --- review ---

    def test_30_review(self) -> None:
        """PR にレビューを作成・一覧取得するテスト。"""
        assert self._update_pr_number is not None
        review = self.adapter.create_review(
            self._update_pr_number, state="COMMENT", body="test review"
        )
        assert review.body == "test review"
        reviews = self.adapter.list_reviews(self._update_pr_number)
        assert len(reviews) > 0

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
        branches = self.adapter.list_branches()
        default = next(b for b in branches if b.name == self.config.default_branch)
        head_sha = default.sha
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
        branches = self.adapter.list_branches()
        default = next(b for b in branches if b.name == self.config.default_branch)
        self.__class__._head_sha = default.sha
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
        # create
        self.adapter.create_or_update_file(
            "gfo-test-file.txt",
            content="hello gfo",
            message="test: create gfo-test-file.txt",
            branch=self.config.test_branch,
        )
        # get
        content, sha = self.adapter.get_file_content(
            "gfo-test-file.txt", ref=self.config.test_branch
        )
        assert content == "hello gfo"
        # update
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
        # delete
        self.adapter.delete_file(
            "gfo-test-file.txt",
            sha=sha2,
            message="test: delete gfo-test-file.txt",
            branch=self.config.test_branch,
        )

    # --- webhook CRUD ---

    def test_41_webhook_crud(self) -> None:
        """Webhook の作成・一覧・削除テスト。"""
        # 残留フックを削除する
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
        from tests.integration.conftest import TEST_SSH_PUBLIC_KEY

        # 残留キーを削除する
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
        assert "login" in user

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

        Gitea 1.22 固有の挙動:
        - 書き込み（create/update）は main ブランチへのコミットが成功するが、
          レスポンスは master から読もうとして 404 を返す（バグ）。
        - 読み取り（list/get）は master ブランチから行う。
        - _sync_wiki_master() で master = main に同期してから読み取る。
        - ページ識別子は sub_url（例: "gfo-test-wiki.-"）を使用する。
        """
        # Wiki を有効化
        try:
            self.adapter._client.patch(
                f"{self.adapter._repos_path()}",
                json={"has_wiki": True},
            )
        except Exception:
            pass
        # master を main に同期してから読み取り可能な状態にする
        self._sync_wiki_master()
        # 残留ページを削除する（sub_url で識別）
        try:
            for p in self.adapter.list_wiki_pages():
                if p.title == "gfo-test-wiki":
                    self.adapter.delete_wiki_page(p.id)
            self._sync_wiki_master()
        except Exception:
            pass
        # Create: Gitea 1.22 はページを main に作成するが 404 を返す（バグ）
        from gfo.exceptions import NotFoundError

        try:
            self.adapter.create_wiki_page(title="gfo-test-wiki", content="hello wiki content")
        except NotFoundError:
            pass  # Gitea 1.22 bug: ページは作成されているが 404 が返る
        # 同期してから読み取る
        self._sync_wiki_master()
        pages = self.adapter.list_wiki_pages()
        wiki_page = next((p for p in pages if p.title == "gfo-test-wiki"), None)
        assert wiki_page is not None, "gfo-test-wiki が作成されているはず"
        # sub_url で取得
        page_read = self.adapter.get_wiki_page(wiki_page.id)
        assert page_read.title == "gfo-test-wiki"
        assert page_read.content == "hello wiki content"
        # Update: Gitea 1.22 は master に page が存在する状態なら PATCH 200 が返る
        updated_page = self.adapter.update_wiki_page(wiki_page.id, content="updated wiki content")
        assert "updated" in updated_page.content
        # 削除して確認
        self.adapter.delete_wiki_page(wiki_page.id)
        self._sync_wiki_master()
        pages_after = self.adapter.list_wiki_pages()
        assert not any(p.title == "gfo-test-wiki" for p in pages_after)
