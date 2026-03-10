"""gfo.commands.wiki のテスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from gfo.adapter.base import WikiPage
from gfo.commands import wiki as wiki_cmd
from tests.test_commands.conftest import make_args

SAMPLE_PAGE = WikiPage(
    id=1,
    title="Home",
    content="# Welcome",
    url="https://example.com/wiki/Home",
    updated_at="2024-01-01T00:00:00Z",
)


def _patch(adapter):
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        with patch("gfo.commands.wiki.get_adapter", return_value=adapter):
            yield

    return _ctx()


class TestHandleList:
    def test_calls_list_wiki_pages(self, capsys):
        adapter = MagicMock()
        adapter.list_wiki_pages.return_value = [SAMPLE_PAGE]
        args = make_args(limit=30)
        with _patch(adapter):
            wiki_cmd.handle_list(args, fmt="table")
        adapter.list_wiki_pages.assert_called_once_with(limit=30)


class TestHandleView:
    def test_calls_get_wiki_page(self, capsys):
        adapter = MagicMock()
        adapter.get_wiki_page.return_value = SAMPLE_PAGE
        args = make_args(id="1")
        with _patch(adapter):
            wiki_cmd.handle_view(args, fmt="table")
        adapter.get_wiki_page.assert_called_once_with("1")


class TestHandleCreate:
    def test_calls_create_wiki_page(self):
        adapter = MagicMock()
        adapter.create_wiki_page.return_value = SAMPLE_PAGE
        args = make_args(title="Home", content="# Welcome")
        with _patch(adapter):
            wiki_cmd.handle_create(args, fmt="table")
        adapter.create_wiki_page.assert_called_once_with(title="Home", content="# Welcome")


class TestHandleUpdate:
    def test_calls_update_wiki_page(self):
        adapter = MagicMock()
        adapter.update_wiki_page.return_value = SAMPLE_PAGE
        args = make_args(id="1", title="New Title", content=None)
        with _patch(adapter):
            wiki_cmd.handle_update(args, fmt="table")
        adapter.update_wiki_page.assert_called_once_with("1", title="New Title", content=None)


class TestHandleDelete:
    def test_calls_delete_wiki_page(self):
        adapter = MagicMock()
        args = make_args(id="1")
        with _patch(adapter):
            wiki_cmd.handle_delete(args, fmt="table")
        adapter.delete_wiki_page.assert_called_once_with("1")
