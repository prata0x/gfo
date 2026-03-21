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

    def test_delete_error_not_found(self):
        """404 エラーが伝搬する。"""
        with patch_adapter("gfo.commands.tag") as adapter:
            adapter.delete_tag.side_effect = HttpError(404, "Not found")
            args = make_args(name="nonexistent")
            with pytest.raises(HttpError) as exc_info:
                tag_cmd.handle_delete(args, fmt="table")
            assert exc_info.value.status_code == 404


class TestHandleListEdgeCases:
    """handle_list の追加エッジケーステスト。"""

    def test_list_empty(self, capsys):
        """空リスト: テーブル出力でエラーなし。"""
        with patch_adapter("gfo.commands.tag") as adapter:
            adapter.list_tags.return_value = []
            args = make_args(limit=30)
            tag_cmd.handle_list(args, fmt="table")
        adapter.list_tags.assert_called_once_with(limit=30)

    def test_list_json_format(self, capsys):
        """JSON 出力形式テスト。"""
        with patch_adapter("gfo.commands.tag") as adapter:
            adapter.list_tags.return_value = [SAMPLE_TAG]
            args = make_args(limit=30)
            tag_cmd.handle_list(args, fmt="json")
        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "v1.0.0"
        assert data[0]["sha"] == "abc123"
        assert data[0]["message"] == "Release v1.0.0"


class TestHandleCreateEdgeCases:
    """handle_create の追加エッジケーステスト。"""

    def test_create_json_format(self, capsys):
        """JSON 出力形式テスト。"""
        created_tag = Tag(name="v2.0.0", sha="def456", message="Release", url="")
        with patch_adapter("gfo.commands.tag") as adapter:
            adapter.create_tag.return_value = created_tag
            args = make_args(name="v2.0.0", ref="main", message="Release")
            tag_cmd.handle_create(args, fmt="json")
        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, list)
        assert data[0]["name"] == "v2.0.0"

    def test_create_message_none_to_empty(self):
        """message=None の場合 or "" 分岐で空文字列が渡される。"""
        with patch_adapter("gfo.commands.tag") as adapter:
            adapter.create_tag.return_value = SAMPLE_TAG
            args = make_args(name="v2.0.0", ref="main", message=None)
            tag_cmd.handle_create(args, fmt="table")
        adapter.create_tag.assert_called_once_with(name="v2.0.0", ref="main", message="")

    def test_create_error_conflict(self):
        """409 コンフリクトエラーが伝搬する。"""
        with patch_adapter("gfo.commands.tag") as adapter:
            adapter.create_tag.side_effect = HttpError(409, "Tag already exists")
            args = make_args(name="v1.0.0", ref="main", message="")
            with pytest.raises(HttpError) as exc_info:
                tag_cmd.handle_create(args, fmt="table")
            assert exc_info.value.status_code == 409


class TestHandleViewEdgeCases:
    """handle_view の追加エッジケーステスト。"""

    def test_view_with_jq(self, capsys):
        """jq フィルター付き出力。"""
        from unittest.mock import patch as _patch

        with patch_adapter("gfo.commands.tag") as adapter:
            adapter.get_tag.return_value = SAMPLE_TAG
            args = make_args(name="v1.0.0")
            with _patch("gfo.output.apply_jq_filter", return_value='"v1.0.0"') as mock_jq:
                tag_cmd.handle_view(args, fmt="json", jq=".[0].name")
                mock_jq.assert_called_once()
