"""Forgejo 統合テスト。

Gitea/Forgejo 共通のテストは base_gitea_family.GiteaFamilyIntegrationBase に集約。
このファイルには Forgejo 固有の差分（wiki の挙動など）のみ記述する。
"""

from __future__ import annotations

import pytest

from tests.integration.base_gitea_family import GiteaFamilyIntegrationBase
from tests.integration.conftest import get_service_config

CONFIG = get_service_config("forgejo")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.selfhosted,
    pytest.mark.skipif(CONFIG is None, reason="Forgejo credentials not configured"),
]


class TestForgejoIntegration(GiteaFamilyIntegrationBase):
    """Forgejo に対する統合テスト。

    共通テストは GiteaFamilyIntegrationBase から継承。
    Forgejo 固有のオーバーライドのみここに定義する。
    """

    CONFIG = CONFIG

    # --- wiki CRUD ---

    def test_45_wiki_crud(self) -> None:
        """Wiki ページの作成・取得・一覧・更新・削除テスト。

        Forgejo は Gitea 1.22 の main/master 不整合が修正済みのため、
        _sync_wiki_master() は不要。
        """
        # Wiki を有効化
        # TODO: _client, _repos_path() はプライベートメンバーへの依存。公開 API への移行を検討。
        try:
            self.adapter._client.patch(
                f"{self.adapter._repos_path()}",
                json={"has_wiki": True},
            )
        except Exception:
            pass
        try:
            for p in self.adapter.list_wiki_pages():
                if p.title == "gfo-test-wiki":
                    self.adapter.delete_wiki_page(p.id)
        except Exception:
            pass
        page = self.adapter.create_wiki_page(
            title="gfo-test-wiki",
            content="hello wiki content",
        )
        assert page.title == "gfo-test-wiki"
        # sub_url（page.id）を使って取得・更新・削除する
        page_read = self.adapter.get_wiki_page(page.id)
        assert page_read.title == "gfo-test-wiki"
        pages = self.adapter.list_wiki_pages()
        assert any(p.title == "gfo-test-wiki" for p in pages)
        updated_page = self.adapter.update_wiki_page(
            page.id,
            content="updated wiki content",
        )
        assert "updated" in updated_page.content
        self.adapter.delete_wiki_page(page.id)
        pages_after = self.adapter.list_wiki_pages()
        assert not any(p.title == "gfo-test-wiki" for p in pages_after)
