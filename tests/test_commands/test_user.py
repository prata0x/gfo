"""gfo.commands.user のテスト。"""

from __future__ import annotations

import json

from gfo.commands import user as user_cmd
from tests.test_commands.conftest import make_args, patch_adapter


class TestHandleWhoami:
    def test_calls_get_current_user(self, capsys):
        with patch_adapter("gfo.commands.user") as adapter:
            adapter.get_current_user.return_value = {
                "login": "testuser",
                "email": "test@example.com",
            }
            args = make_args()
            user_cmd.handle_whoami(args, fmt="table")
        adapter.get_current_user.assert_called_once()

    def test_outputs_json(self, capsys):
        with patch_adapter("gfo.commands.user") as adapter:
            adapter.get_current_user.return_value = {"login": "testuser"}
            args = make_args()
            user_cmd.handle_whoami(args, fmt="json")
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["login"] == "testuser"
