"""Gitea 統合テスト。

Gitea/Forgejo 共通のテストは base_gitea_family.GiteaFamilyIntegrationBase に集約。
このファイルには Gitea 固有の差分（wiki の main→master 同期など）のみ記述する。
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

import pytest

from tests.integration.base_gitea_family import GiteaFamilyIntegrationBase
from tests.integration.conftest import get_service_config

CONFIG = get_service_config("gitea")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.selfhosted,
    pytest.mark.skipif(CONFIG is None, reason="Gitea credentials not configured"),
]


class TestGiteaIntegration(GiteaFamilyIntegrationBase):
    """Gitea に対する統合テスト。

    テストメソッドはアルファベット順（名前順）に実行される。
    テスト間で作成したリソースの番号をクラス変数で共有する。
    """

    CONFIG = CONFIG

    def test_01_repo_view(self) -> None:
        repo = self.adapter.get_repository()
        assert repo.name == self.config.repo
        assert self.config.owner in repo.full_name

    @classmethod
    def _make_askpass_env(cls, token: str, username: str = "gfo-admin") -> dict:
        """GIT_ASKPASS 用の環境変数辞書を生成する。

        トークンを URL に直接埋め込む代わりに、GIT_ASKPASS スクリプト経由で
        認証情報を渡す。一時ファイルにヘルパースクリプトを書き出し、
        GIT_ASKPASS に設定する。
        """
        askpass_script = os.path.join(os.path.dirname(__file__), "git_askpass_helper.py")
        # GIT_ASKPASS は実行可能ファイルのパスのみ受け付ける（引数不可）ため、
        # Python インタープリタ経由で呼び出すラッパーを一時ファイルに書き出す
        wrapper_dir = tempfile.mkdtemp(prefix="gfo-askpass-")
        if sys.platform == "win32":
            wrapper_path = os.path.join(wrapper_dir, "askpass.bat")
            with open(wrapper_path, "w") as f:
                f.write(f'@"{sys.executable}" "{askpass_script}" %1\n')
        else:
            wrapper_path = os.path.join(wrapper_dir, "askpass.sh")
            with open(wrapper_path, "w") as f:
                f.write(f'#!/bin/sh\n"{sys.executable}" "{askpass_script}" "$1"\n')
            os.chmod(wrapper_path, 0o755)
        return {
            **os.environ,
            "GIT_ASKPASS": wrapper_path,
            "GFO_GIT_USERNAME": username,
            "GFO_GIT_TOKEN": token,
        }

    @classmethod
    def _sync_wiki_master(cls) -> None:
        """Gitea 1.22 の wiki ブランチ不整合修正: main → master を同期する。

        Gitea 1.22 は wiki への書き込みを main ブランチ、
        読み取りを master ブランチで行うため、write 後に手動で同期が必要。
        GIT_ASKPASS を使用してトークンを安全に渡す。
        """
        host = cls.config.host or "localhost:3000"
        owner = cls.config.owner
        repo = cls.config.repo
        token = cls.config.token
        wiki_url = f"http://{host}/{owner}/{repo}.wiki.git"
        git_env = cls._make_askpass_env(token)

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            wiki_dir = f"{tmpdir}/wiki"
            try:
                r = subprocess.run(
                    ["git", "clone", "--depth=1", wiki_url, wiki_dir],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    env=git_env,
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
                    env=git_env,
                    timeout=30,
                )
            except Exception:
                pass  # ベストエフォート

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
        # TODO: _client はプライベートメンバーへの依存。公開 API への移行を検討。
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
