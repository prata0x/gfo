"""gfo.commands.wiki のテスト。"""

from __future__ import annotations

from gfo.adapter.base import WikiPage, WikiRevision
from gfo.commands import wiki as wiki_cmd
from tests.test_commands.conftest import make_args, patch_adapter

SAMPLE_PAGE = WikiPage(
    id=1,
    title="Home",
    content="# Welcome",
    url="https://example.com/wiki/Home",
    updated_at="2024-01-01T00:00:00Z",
)


class TestHandleList:
    def test_calls_list_wiki_pages(self, capsys):
        with patch_adapter("gfo.commands.wiki") as adapter:
            adapter.list_wiki_pages.return_value = [SAMPLE_PAGE]
            args = make_args(limit=30)
            wiki_cmd.handle_list(args, fmt="table")
        adapter.list_wiki_pages.assert_called_once_with(limit=30)


class TestHandleView:
    def test_calls_get_wiki_page(self, capsys):
        with patch_adapter("gfo.commands.wiki") as adapter:
            adapter.get_wiki_page.return_value = SAMPLE_PAGE
            args = make_args(id="1")
            wiki_cmd.handle_view(args, fmt="table")
        adapter.get_wiki_page.assert_called_once_with("1")


class TestHandleCreate:
    def test_calls_create_wiki_page(self):
        with patch_adapter("gfo.commands.wiki") as adapter:
            adapter.create_wiki_page.return_value = SAMPLE_PAGE
            args = make_args(title="Home", content="# Welcome")
            wiki_cmd.handle_create(args, fmt="table")
        adapter.create_wiki_page.assert_called_once_with(title="Home", content="# Welcome")


class TestHandleUpdate:
    def test_calls_update_wiki_page(self):
        with patch_adapter("gfo.commands.wiki") as adapter:
            adapter.update_wiki_page.return_value = SAMPLE_PAGE
            args = make_args(id="1", title="New Title", content=None)
            wiki_cmd.handle_update(args, fmt="table")
        adapter.update_wiki_page.assert_called_once_with("1", title="New Title", content=None)


class TestHandleDelete:
    def test_calls_delete_wiki_page(self):
        with patch_adapter("gfo.commands.wiki") as adapter:
            args = make_args(id="1")
            wiki_cmd.handle_delete(args, fmt="table")
        adapter.delete_wiki_page.assert_called_once_with("1")


# --- Phase 5: wiki revisions ---

SAMPLE_REVISION = WikiRevision(
    sha="abc123",
    author="alice",
    message="Update page",
    created_at="2024-01-01T00:00:00Z",
)


class TestHandleRevisions:
    def test_calls_list_wiki_revisions(self, capsys):
        with patch_adapter("gfo.commands.wiki") as adapter:
            adapter.list_wiki_revisions.return_value = [SAMPLE_REVISION]
            args = make_args(page_name="Home")
            wiki_cmd.handle_revisions(args, fmt="table")
        adapter.list_wiki_revisions.assert_called_once_with("Home")
