"""gfo.commands.collaborator のテスト。"""

from __future__ import annotations

import json

from gfo.commands import collaborator as collab_cmd
from tests.test_commands.conftest import make_args, patch_adapter


class TestHandleList:
    def test_calls_list_collaborators(self, capsys):
        with patch_adapter("gfo.commands.collaborator") as adapter:
            adapter.list_collaborators.return_value = ["alice", "bob"]
            args = make_args(limit=30)
            collab_cmd.handle_list(args, fmt="table")
        adapter.list_collaborators.assert_called_once_with(limit=30)
        out = capsys.readouterr().out
        assert "alice" in out

    def test_json_format(self, capsys):
        with patch_adapter("gfo.commands.collaborator") as adapter:
            adapter.list_collaborators.return_value = ["alice"]
            args = make_args(limit=30)
            collab_cmd.handle_list(args, fmt="json")
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data == ["alice"]


class TestHandleAdd:
    def test_calls_add_collaborator(self):
        with patch_adapter("gfo.commands.collaborator") as adapter:
            args = make_args(username="charlie", permission="write")
            collab_cmd.handle_add(args, fmt="table")
        adapter.add_collaborator.assert_called_once_with(username="charlie", permission="write")


class TestHandleRemove:
    def test_calls_remove_collaborator(self):
        with patch_adapter("gfo.commands.collaborator") as adapter:
            args = make_args(username="charlie")
            collab_cmd.handle_remove(args, fmt="table")
        adapter.remove_collaborator.assert_called_once_with(username="charlie")
