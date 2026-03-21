"""gfo.commands.collaborator のテスト。"""

from __future__ import annotations

import json

import pytest

from gfo.commands import collaborator as collab_cmd
from gfo.exceptions import HttpError
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

    def test_list_empty(self, capsys):
        """空リスト返却時に table では何も出力せず、json では空配列が出力される。"""
        with patch_adapter("gfo.commands.collaborator") as adapter:
            adapter.list_collaborators.return_value = []
            args = make_args(limit=30)
            collab_cmd.handle_list(args, fmt="table")
        out_table = capsys.readouterr().out
        assert out_table == ""

        with patch_adapter("gfo.commands.collaborator") as adapter:
            adapter.list_collaborators.return_value = []
            args = make_args(limit=30)
            collab_cmd.handle_list(args, fmt="json")
        out_json = capsys.readouterr().out
        data = json.loads(out_json)
        assert data == []

    def test_list_plain_format(self, capsys):
        """table 形式で1行1ユーザー名が出力される。"""
        with patch_adapter("gfo.commands.collaborator") as adapter:
            adapter.list_collaborators.return_value = ["alice", "bob", "charlie"]
            args = make_args(limit=30)
            collab_cmd.handle_list(args, fmt="table")
        out = capsys.readouterr().out
        lines = out.strip().split("\n")
        assert "alice" in lines[0]
        assert "bob" in lines[1]
        assert "charlie" in lines[2]

    def test_list_jq_filter(self, capsys):
        """jq フィルタが適用される。"""
        with patch_adapter("gfo.commands.collaborator") as adapter:
            adapter.list_collaborators.return_value = ["alice", "bob"]
            args = make_args(limit=30)
            collab_cmd.handle_list(args, fmt="json", jq=".[0]")
        out = capsys.readouterr().out
        assert "alice" in out


class TestHandleAdd:
    def test_calls_add_collaborator(self):
        with patch_adapter("gfo.commands.collaborator") as adapter:
            args = make_args(username="charlie", permission="write")
            collab_cmd.handle_add(args, fmt="table")
        adapter.add_collaborator.assert_called_once_with(username="charlie", permission="write")

    def test_add_permission_values(self):
        """複数の permission 値がアダプターに正しく渡される。"""
        for perm in ["read", "write", "admin"]:
            with patch_adapter("gfo.commands.collaborator") as adapter:
                args = make_args(username="user1", permission=perm)
                collab_cmd.handle_add(args, fmt="table")
            adapter.add_collaborator.assert_called_once_with(username="user1", permission=perm)

    def test_add_error_propagation(self):
        """HttpError(403) がそのまま伝搬する。"""
        with patch_adapter("gfo.commands.collaborator") as adapter:
            adapter.add_collaborator.side_effect = HttpError(403, "Forbidden")
            args = make_args(username="user1", permission="write")
            with pytest.raises(HttpError) as exc_info:
                collab_cmd.handle_add(args, fmt="table")
            assert exc_info.value.status_code == 403


class TestHandleRemove:
    def test_calls_remove_collaborator(self):
        with patch_adapter("gfo.commands.collaborator") as adapter:
            args = make_args(username="charlie")
            collab_cmd.handle_remove(args, fmt="table")
        adapter.remove_collaborator.assert_called_once_with(username="charlie")

    def test_remove_error_propagation(self):
        """HttpError(404) がそのまま伝搬する。"""
        with patch_adapter("gfo.commands.collaborator") as adapter:
            adapter.remove_collaborator.side_effect = HttpError(404, "Not Found")
            args = make_args(username="nonexistent")
            with pytest.raises(HttpError) as exc_info:
                collab_cmd.handle_remove(args, fmt="table")
            assert exc_info.value.status_code == 404
