"""gfo.commands.variable のテスト。"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from gfo.adapter.base import Variable
from gfo.commands import variable as variable_cmd
from gfo.exceptions import GfoError, HttpError
from tests.test_commands.conftest import make_args, patch_adapter

SAMPLE_VAR = Variable(name="MY_VAR", value="val", created_at="2024-01-01", updated_at="2024-01-02")


class TestHandleList:
    def test_calls_list_variables(self, capsys):
        with patch_adapter("gfo.commands.variable") as adapter:
            adapter.list_variables.return_value = [SAMPLE_VAR]
            args = make_args(limit=30)
            variable_cmd.handle_list(args, fmt="table")
        adapter.list_variables.assert_called_once_with(limit=30)
        out = capsys.readouterr().out
        assert "MY_VAR" in out

    def test_json_format(self, capsys):
        with patch_adapter("gfo.commands.variable") as adapter:
            adapter.list_variables.return_value = [SAMPLE_VAR]
            args = make_args(limit=30)
            variable_cmd.handle_list(args, fmt="json")
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert isinstance(parsed, list)
        assert parsed[0]["name"] == "MY_VAR"

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.variable") as adapter:
            adapter.list_variables.side_effect = HttpError(500, "Server error")
            args = make_args(limit=30)
            with pytest.raises(HttpError):
                variable_cmd.handle_list(args, fmt="table")


class TestHandleSet:
    def test_calls_set_variable(self):
        with patch_adapter("gfo.commands.variable") as adapter:
            adapter.set_variable.return_value = SAMPLE_VAR
            args = make_args(name="MY_VAR", value="val", masked=False)
            variable_cmd.handle_set(args, fmt="table")
        adapter.set_variable.assert_called_once_with("MY_VAR", "val", masked=False)

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.variable") as adapter:
            adapter.set_variable.side_effect = HttpError(403, "Forbidden")
            args = make_args(name="MY_VAR", value="val", masked=False)
            with pytest.raises(HttpError):
                variable_cmd.handle_set(args, fmt="table")


class TestHandleGet:
    def test_prints_value(self, capsys):
        with patch_adapter("gfo.commands.variable") as adapter:
            adapter.get_variable.return_value = SAMPLE_VAR
            args = make_args(name="MY_VAR")
            variable_cmd.handle_get(args, fmt="table")
        out = capsys.readouterr().out
        assert out.strip() == "val"

    def test_json_format(self, capsys):
        """fmt="json" のとき output() 経由で JSON が出力される。"""
        with patch_adapter("gfo.commands.variable") as adapter:
            adapter.get_variable.return_value = SAMPLE_VAR
            args = make_args(name="MY_VAR")
            variable_cmd.handle_get(args, fmt="json")
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed[0]["name"] == "MY_VAR"
        assert parsed[0]["value"] == "val"

    def test_jq_forces_json(self, capsys):
        """jq 引数指定時でも fmt="table" の場合 JSON 出力に切り替わる。"""
        with patch_adapter("gfo.commands.variable") as adapter:
            adapter.get_variable.return_value = SAMPLE_VAR
            args = make_args(name="MY_VAR")
            with patch("gfo.output.apply_jq_filter", return_value='"val"') as mock_jq:
                variable_cmd.handle_get(args, fmt="table", jq=".[0].value")
            mock_jq.assert_called_once()
            out = capsys.readouterr().out
            assert "val" in out

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.variable") as adapter:
            adapter.get_variable.side_effect = HttpError(404, "Not found")
            args = make_args(name="MY_VAR")
            with pytest.raises(HttpError):
                variable_cmd.handle_get(args, fmt="table")


class TestHandleDelete:
    def test_calls_delete(self):
        with patch_adapter("gfo.commands.variable") as adapter:
            args = make_args(name="MY_VAR")
            variable_cmd.handle_delete(args, fmt="table")
        adapter.delete_variable.assert_called_once_with("MY_VAR")

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.variable") as adapter:
            adapter.delete_variable.side_effect = GfoError("not found")
            args = make_args(name="MY_VAR")
            with pytest.raises(GfoError, match="not found"):
                variable_cmd.handle_delete(args, fmt="table")
