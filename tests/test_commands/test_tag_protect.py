"""gfo.commands.tag_protect のテスト。"""

from __future__ import annotations

import json

import pytest

from gfo.adapter.base import TagProtection
from gfo.commands import tag_protect as tp_cmd
from gfo.exceptions import HttpError
from tests.test_commands.conftest import make_args, patch_adapter

SAMPLE_TP = TagProtection(
    id=1,
    pattern="v*",
    create_access_level="maintainer",
)


class TestHandleList:
    def test_calls_list(self, capsys):
        with patch_adapter("gfo.commands.tag_protect") as adapter:
            adapter.list_tag_protections.return_value = [SAMPLE_TP]
            args = make_args(limit=30)
            tp_cmd.handle_list(args, fmt="table")
        adapter.list_tag_protections.assert_called_once_with(limit=30)
        out = capsys.readouterr().out
        assert "v*" in out

    def test_json_format(self, capsys):
        with patch_adapter("gfo.commands.tag_protect") as adapter:
            adapter.list_tag_protections.return_value = [SAMPLE_TP]
            args = make_args(limit=30)
            tp_cmd.handle_list(args, fmt="json")
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert isinstance(parsed, list)
        assert parsed[0]["pattern"] == "v*"

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.tag_protect") as adapter:
            adapter.list_tag_protections.side_effect = HttpError(500, "Server error")
            args = make_args(limit=30)
            with pytest.raises(HttpError):
                tp_cmd.handle_list(args, fmt="table")


class TestHandleCreate:
    def test_creates_tag_protection(self, capsys):
        with patch_adapter("gfo.commands.tag_protect") as adapter:
            adapter.create_tag_protection.return_value = SAMPLE_TP
            args = make_args(pattern="v*", access_level=None)
            tp_cmd.handle_create(args, fmt="table")
        adapter.create_tag_protection.assert_called_once_with("v*", create_access_level=None)

    def test_creates_with_access_level(self, capsys):
        with patch_adapter("gfo.commands.tag_protect") as adapter:
            adapter.create_tag_protection.return_value = SAMPLE_TP
            args = make_args(pattern="v*", access_level="maintainer")
            tp_cmd.handle_create(args, fmt="table")
        adapter.create_tag_protection.assert_called_once_with(
            "v*", create_access_level="maintainer"
        )

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.tag_protect") as adapter:
            adapter.create_tag_protection.side_effect = HttpError(403, "Forbidden")
            args = make_args(pattern="v*", access_level=None)
            with pytest.raises(HttpError):
                tp_cmd.handle_create(args, fmt="table")


class TestHandleDelete:
    def test_calls_delete(self, capsys):
        with patch_adapter("gfo.commands.tag_protect") as adapter:
            args = make_args(id=1)
            tp_cmd.handle_delete(args, fmt="table")
        adapter.delete_tag_protection.assert_called_once_with(1)
        out = capsys.readouterr().out
        assert "Deleted" in out
        assert "1" in out

    def test_string_id(self):
        with patch_adapter("gfo.commands.tag_protect") as adapter:
            args = make_args(id="v*")
            tp_cmd.handle_delete(args, fmt="table")
        adapter.delete_tag_protection.assert_called_once_with("v*")

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.tag_protect") as adapter:
            adapter.delete_tag_protection.side_effect = HttpError(404, "Not found")
            args = make_args(id=1)
            with pytest.raises(HttpError):
                tp_cmd.handle_delete(args, fmt="table")
