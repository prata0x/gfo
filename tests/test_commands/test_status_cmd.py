"""gfo.commands.status のテスト。"""

from __future__ import annotations

import json

import pytest

from gfo.adapter.base import CommitStatus
from gfo.commands import status as status_cmd
from gfo.exceptions import HttpError
from tests.test_commands.conftest import make_args, patch_adapter

SAMPLE_STATUS = CommitStatus(
    state="success",
    context="ci/build",
    description="Build passed",
    target_url="https://ci.example.com/1",
    created_at="2024-01-01T00:00:00Z",
)


class TestHandleList:
    def test_calls_list_commit_statuses(self, capsys):
        with patch_adapter("gfo.commands.status") as adapter:
            adapter.list_commit_statuses.return_value = [SAMPLE_STATUS]
            args = make_args(ref="abc123", limit=30)
            status_cmd.handle_list(args, fmt="table")
        adapter.list_commit_statuses.assert_called_once_with("abc123", limit=30)

    def test_list_empty(self, capsys):
        """空リスト返却時に 'No results found.' が出力される。"""
        with patch_adapter("gfo.commands.status") as adapter:
            adapter.list_commit_statuses.return_value = []
            args = make_args(ref="abc123", limit=30)
            status_cmd.handle_list(args, fmt="table")
        out = capsys.readouterr().out
        assert "No results found." in out

    def test_list_json_format(self, capsys):
        """fmt='json' で JSON 配列が出力される。"""
        with patch_adapter("gfo.commands.status") as adapter:
            adapter.list_commit_statuses.return_value = [SAMPLE_STATUS]
            args = make_args(ref="abc123", limit=30)
            status_cmd.handle_list(args, fmt="json")
        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["state"] == "success"
        assert data[0]["context"] == "ci/build"

    def test_list_with_jq(self, capsys):
        """--jq '.[].state' が適用される。"""
        with patch_adapter("gfo.commands.status") as adapter:
            adapter.list_commit_statuses.return_value = [SAMPLE_STATUS]
            args = make_args(ref="abc123", limit=30)
            status_cmd.handle_list(args, fmt="json", jq=".[].state")
        out = capsys.readouterr().out
        assert "success" in out

    def test_list_limit_forwarded(self):
        """args.limit がアダプターに渡される。"""
        with patch_adapter("gfo.commands.status") as adapter:
            adapter.list_commit_statuses.return_value = []
            args = make_args(ref="abc123", limit=5)
            status_cmd.handle_list(args, fmt="table")
        adapter.list_commit_statuses.assert_called_once_with("abc123", limit=5)


class TestHandleCreate:
    def test_calls_create_commit_status(self):
        with patch_adapter("gfo.commands.status") as adapter:
            adapter.create_commit_status.return_value = SAMPLE_STATUS
            args = make_args(
                ref="abc123",
                state="success",
                context="ci/build",
                description="passed",
                url="https://ci.example.com",
            )
            status_cmd.handle_create(args, fmt="table")
        adapter.create_commit_status.assert_called_once_with(
            "abc123",
            state="success",
            context="ci/build",
            description="passed",
            target_url="https://ci.example.com",
        )

    def test_create_optional_args_none(self):
        """context=None, description=None, url=None は空文字列にフォールバックする。"""
        with patch_adapter("gfo.commands.status") as adapter:
            adapter.create_commit_status.return_value = SAMPLE_STATUS
            args = make_args(
                ref="abc123",
                state="pending",
                context=None,
                description=None,
                url=None,
            )
            status_cmd.handle_create(args, fmt="table")
        adapter.create_commit_status.assert_called_once_with(
            "abc123",
            state="pending",
            context="",
            description="",
            target_url="",
        )

    def test_create_json_format(self, capsys):
        """作成結果が JSON 形式で出力される。"""
        with patch_adapter("gfo.commands.status") as adapter:
            adapter.create_commit_status.return_value = SAMPLE_STATUS
            args = make_args(
                ref="abc123",
                state="success",
                context="ci/build",
                description="passed",
                url="https://ci.example.com",
            )
            status_cmd.handle_create(args, fmt="json")
        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, list)
        assert data[0]["state"] == "success"

    def test_create_error_propagation(self):
        """HttpError(403) がそのまま伝搬する。"""
        with patch_adapter("gfo.commands.status") as adapter:
            adapter.create_commit_status.side_effect = HttpError(403, "Forbidden")
            args = make_args(
                ref="abc123",
                state="success",
                context="ci/build",
                description="passed",
                url="https://ci.example.com",
            )
            with pytest.raises(HttpError) as exc_info:
                status_cmd.handle_create(args, fmt="table")
            assert exc_info.value.status_code == 403
