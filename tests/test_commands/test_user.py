"""gfo.commands.user のテスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from gfo.commands import user as user_cmd
from tests.test_commands.conftest import make_args


def _patch(adapter):
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        with patch("gfo.commands.user.get_adapter", return_value=adapter):
            yield

    return _ctx()


class TestHandleWhoami:
    def test_calls_get_current_user(self, capsys):
        adapter = MagicMock()
        adapter.get_current_user.return_value = {"login": "testuser", "email": "test@example.com"}
        args = make_args()
        with _patch(adapter):
            user_cmd.handle_whoami(args, fmt="table")
        adapter.get_current_user.assert_called_once()

    def test_outputs_json(self, capsys):
        adapter = MagicMock()
        adapter.get_current_user.return_value = {"login": "testuser"}
        args = make_args()
        with _patch(adapter):
            user_cmd.handle_whoami(args, fmt="json")
        import json

        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["login"] == "testuser"
