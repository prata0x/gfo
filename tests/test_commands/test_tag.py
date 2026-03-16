"""gfo.commands.tag のテスト。"""

from __future__ import annotations

from gfo.adapter.base import Tag
from gfo.commands import tag as tag_cmd
from tests.test_commands.conftest import make_args, patch_adapter

SAMPLE_TAG = Tag(name="v1.0.0", sha="abc123", message="Release v1.0.0", url="")


class TestHandleList:
    def test_calls_list_tags(self, capsys):
        with patch_adapter("gfo.commands.tag") as adapter:
            adapter.list_tags.return_value = [SAMPLE_TAG]
            args = make_args(limit=30)
            tag_cmd.handle_list(args, fmt="table")
        adapter.list_tags.assert_called_once_with(limit=30)

    def test_outputs_results(self, capsys):
        with patch_adapter("gfo.commands.tag") as adapter:
            adapter.list_tags.return_value = [SAMPLE_TAG]
            args = make_args(limit=30)
            tag_cmd.handle_list(args, fmt="table")
        out = capsys.readouterr().out
        assert "v1.0.0" in out


class TestHandleCreate:
    def test_calls_create_tag(self):
        with patch_adapter("gfo.commands.tag") as adapter:
            adapter.create_tag.return_value = SAMPLE_TAG
            args = make_args(name="v2.0.0", ref="main", message="Release")
            tag_cmd.handle_create(args, fmt="table")
        adapter.create_tag.assert_called_once_with(name="v2.0.0", ref="main", message="Release")


class TestHandleDelete:
    def test_calls_delete_tag(self):
        with patch_adapter("gfo.commands.tag") as adapter:
            args = make_args(name="v1.0.0")
            tag_cmd.handle_delete(args, fmt="table")
        adapter.delete_tag.assert_called_once_with(name="v1.0.0")
