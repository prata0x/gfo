"""gfo batch pr create のテスト。"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from gfo.adapter.base import PullRequest
from gfo.commands import batch as batch_cmd
from gfo.exceptions import ConfigError, HttpError
from tests.test_commands.conftest import make_args


def _make_pr(number: int = 1, url: str = "https://github.com/owner/repo/pull/1") -> PullRequest:
    return PullRequest(
        number=number,
        title="Test",
        body="",
        state="open",
        author="user",
        source_branch="feature",
        target_branch="main",
        draft=False,
        url=url,
        created_at="2024-01-01T00:00:00Z",
    )


def _make_spec(service_type: str = "github", owner: str = "owner", repo: str = "repo") -> MagicMock:
    spec = MagicMock()
    spec.service_type = service_type
    spec.owner = owner
    spec.repo = repo
    return spec


class TestHandleBatchPr:
    """handle_batch_pr のテスト。"""

    @patch("gfo.commands.batch.create_adapter_from_spec")
    @patch("gfo.commands.batch.parse_service_spec")
    def test_single_repo_success(self, mock_parse, mock_create_adapter, capsys):
        """単一リポジトリへの PR 作成成功。"""
        spec = _make_spec()
        mock_parse.return_value = spec
        adapter = MagicMock()
        adapter.create_pull_request.return_value = _make_pr()
        mock_create_adapter.return_value = adapter

        args = make_args(
            repos="github:owner/repo",
            title="Test PR",
            body="body",
            head="feature",
            base="main",
            draft=False,
            dry_run=False,
            batch_pr_action="create",
        )

        batch_cmd.handle_batch_pr(args, fmt="table")

        adapter.create_pull_request.assert_called_once_with(
            title="Test PR",
            body="body",
            head="feature",
            base="main",
            draft=False,
        )
        captured = capsys.readouterr()
        assert "created" in captured.out
        assert "github:owner/repo" in captured.out

    @patch("gfo.commands.batch.create_adapter_from_spec")
    @patch("gfo.commands.batch.parse_service_spec")
    def test_multiple_repos_partial_failure(self, mock_parse, mock_create_adapter, capsys):
        """複数リポジトリ（一部成功/一部失敗）。"""
        spec1 = _make_spec("github", "owner1", "repo1")
        spec2 = _make_spec("gitlab", "owner2", "repo2")
        mock_parse.side_effect = [spec1, spec2]

        adapter1 = MagicMock()
        adapter1.create_pull_request.return_value = _make_pr(
            number=10, url="https://github.com/owner1/repo1/pull/10"
        )
        adapter2 = MagicMock()
        adapter2.create_pull_request.side_effect = HttpError(500, "Server Error")
        mock_create_adapter.side_effect = [adapter1, adapter2]

        args = make_args(
            repos="github:owner1/repo1,gitlab:owner2/repo2",
            title="Test PR",
            body="",
            head="feature",
            base="main",
            draft=False,
            dry_run=False,
            batch_pr_action="create",
        )

        batch_cmd.handle_batch_pr(args, fmt="table")

        captured = capsys.readouterr()
        assert "created" in captured.out
        assert "failed" in captured.out

    @patch("gfo.commands.batch.create_adapter_from_spec")
    @patch("gfo.commands.batch.parse_service_spec")
    def test_dry_run(self, mock_parse, mock_create_adapter, capsys):
        """--dry-run: create_pull_request が呼ばれないことを検証。"""
        spec = _make_spec()
        mock_parse.return_value = spec
        adapter = MagicMock()
        mock_create_adapter.return_value = adapter

        args = make_args(
            repos="github:owner/repo",
            title="Test PR",
            body="",
            head="feature",
            base="main",
            draft=False,
            dry_run=True,
            batch_pr_action="create",
        )

        batch_cmd.handle_batch_pr(args, fmt="table")

        adapter.create_pull_request.assert_not_called()
        captured = capsys.readouterr()
        assert "skipped" in captured.out

    @patch("gfo.commands.batch.create_adapter_from_spec")
    @patch("gfo.commands.batch.parse_service_spec")
    def test_json_output(self, mock_parse, mock_create_adapter, capsys):
        """JSON 出力形式テスト。"""
        spec = _make_spec()
        mock_parse.return_value = spec
        adapter = MagicMock()
        adapter.create_pull_request.return_value = _make_pr()
        mock_create_adapter.return_value = adapter

        args = make_args(
            repos="github:owner/repo",
            title="Test PR",
            body="",
            head="feature",
            base="main",
            draft=False,
            dry_run=False,
            batch_pr_action="create",
        )

        batch_cmd.handle_batch_pr(args, fmt="json")

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["status"] == "created"
        assert data[0]["number"] == 1
        assert data[0]["repo"] == "github:owner/repo"

    def test_no_batch_pr_action_raises_config_error(self):
        """batch_pr_action が None → ConfigError。"""
        args = make_args(
            repos="github:owner/repo",
            title="Test PR",
            body="",
            head="feature",
            base="main",
        )
        # batch_pr_action 属性なし → getattr で None

        with pytest.raises(ConfigError):
            batch_cmd.handle_batch_pr(args, fmt="table")

    @patch("gfo.commands.batch.create_adapter_from_spec")
    @patch("gfo.commands.batch.parse_service_spec")
    def test_empty_repos(self, mock_parse, mock_create_adapter, capsys):
        """空の repos → 空結果。"""
        args = make_args(
            repos="",
            title="Test PR",
            body="",
            head="feature",
            base="main",
            dry_run=False,
            batch_pr_action="create",
        )

        batch_cmd.handle_batch_pr(args, fmt="json")

        mock_parse.assert_not_called()
        mock_create_adapter.assert_not_called()
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data == []
