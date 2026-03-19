"""gfo.commands.tag のテスト。"""

from __future__ import annotations

import json

import pytest

from gfo.adapter.base import Tag
from gfo.commands import tag as tag_cmd
from gfo.exceptions import HttpError
from tests.test_commands.conftest import make_args, patch_adapter

SAMPLE_TAG = Tag(name="v1.0.0", sha="abc123", message="Release v1.0.0", url="")


class TestHandleView:
    def test_calls_get_tag(self):
        with patch_adapter("gfo.commands.tag") as adapter:
            adapter.get_tag.return_value = SAMPLE_TAG
            args = make_args(name="v1.0.0")
            tag_cmd.handle_view(args, fmt="table")
        adapter.get_tag.assert_called_once_with("v1.0.0")

    def test_outputs_result(self, capsys):
        with patch_adapter("gfo.commands.tag") as adapter:
            adapter.get_tag.return_value = SAMPLE_TAG
            args = make_args(name="v1.0.0")
            tag_cmd.handle_view(args, fmt="table")
        out = capsys.readouterr().out
        assert "v1.0.0" in out
        assert "abc123" in out

    def test_json_format(self, capsys):
        with patch_adapter("gfo.commands.tag") as adapter:
            adapter.get_tag.return_value = SAMPLE_TAG
            args = make_args(name="v1.0.0")
            tag_cmd.handle_view(args, fmt="json")
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert isinstance(parsed, list)
        assert parsed[0]["name"] == "v1.0.0"

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.tag") as adapter:
            adapter.get_tag.side_effect = HttpError(404, "Not found")
            args = make_args(name="nonexistent")
            with pytest.raises(HttpError):
                tag_cmd.handle_view(args, fmt="table")


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
