"""gfo.commands.variable のテスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from gfo.adapter.base import Variable
from gfo.commands import variable as variable_cmd
from tests.test_commands.conftest import make_args

SAMPLE_VAR = Variable(name="MY_VAR", value="val", created_at="2024-01-01", updated_at="2024-01-02")


def _patch(adapter):
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        with patch("gfo.commands.variable.get_adapter", return_value=adapter):
            yield

    return _ctx()


class TestHandleList:
    def test_calls_list_variables(self, capsys):
        adapter = MagicMock()
        adapter.list_variables.return_value = [SAMPLE_VAR]
        args = make_args(limit=30)
        with _patch(adapter):
            variable_cmd.handle_list(args, fmt="table")
        adapter.list_variables.assert_called_once_with(limit=30)
        out = capsys.readouterr().out
        assert "MY_VAR" in out


class TestHandleSet:
    def test_calls_set_variable(self):
        adapter = MagicMock()
        adapter.set_variable.return_value = SAMPLE_VAR
        args = make_args(name="MY_VAR", value="val", masked=False)
        with _patch(adapter):
            variable_cmd.handle_set(args, fmt="table")
        adapter.set_variable.assert_called_once_with("MY_VAR", "val", masked=False)


class TestHandleGet:
    def test_prints_value(self, capsys):
        adapter = MagicMock()
        adapter.get_variable.return_value = SAMPLE_VAR
        args = make_args(name="MY_VAR")
        with _patch(adapter):
            variable_cmd.handle_get(args, fmt="table")
        out = capsys.readouterr().out
        assert out.strip() == "val"


class TestHandleDelete:
    def test_calls_delete(self):
        adapter = MagicMock()
        args = make_args(name="MY_VAR")
        with _patch(adapter):
            variable_cmd.handle_delete(args, fmt="table")
        adapter.delete_variable.assert_called_once_with("MY_VAR")
