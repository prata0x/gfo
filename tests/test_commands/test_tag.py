"""gfo.commands.tag のテスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from gfo.adapter.base import Tag
from gfo.commands import tag as tag_cmd
from tests.test_commands.conftest import make_args

SAMPLE_TAG = Tag(name="v1.0.0", sha="abc123", message="Release v1.0.0", url="")


def _patch(adapter):
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        with patch("gfo.commands.tag.get_adapter", return_value=adapter):
            yield

    return _ctx()


class TestHandleList:
    def test_calls_list_tags(self, capsys):
        adapter = MagicMock()
        adapter.list_tags.return_value = [SAMPLE_TAG]
        args = make_args(limit=30)
        with _patch(adapter):
            tag_cmd.handle_list(args, fmt="table")
        adapter.list_tags.assert_called_once_with(limit=30)

    def test_outputs_results(self, capsys):
        adapter = MagicMock()
        adapter.list_tags.return_value = [SAMPLE_TAG]
        args = make_args(limit=30)
        with _patch(adapter):
            tag_cmd.handle_list(args, fmt="table")
        out = capsys.readouterr().out
        assert "v1.0.0" in out


class TestHandleCreate:
    def test_calls_create_tag(self):
        adapter = MagicMock()
        adapter.create_tag.return_value = SAMPLE_TAG
        args = make_args(name="v2.0.0", ref="main", message="Release")
        with _patch(adapter):
            tag_cmd.handle_create(args, fmt="table")
        adapter.create_tag.assert_called_once_with(name="v2.0.0", ref="main", message="Release")


class TestHandleDelete:
    def test_calls_delete_tag(self):
        adapter = MagicMock()
        args = make_args(name="v1.0.0")
        with _patch(adapter):
            tag_cmd.handle_delete(args, fmt="table")
        adapter.delete_tag.assert_called_once_with(name="v1.0.0")
