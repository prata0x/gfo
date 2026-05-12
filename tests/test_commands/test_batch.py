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

    @patch("gfo.commands.batch.create_adapter_from_spec")
    @patch("gfo.commands.batch.parse_service_spec")
    def test_all_repos_fail(self, mock_parse, mock_create_adapter, capsys):
        """全リポジトリが失敗した場合、全 status="failed" のレポート出力。"""
        spec1 = _make_spec("github", "owner1", "repo1")
        spec2 = _make_spec("gitlab", "owner2", "repo2")
        mock_parse.side_effect = [spec1, spec2]

        adapter1 = MagicMock()
        adapter1.create_pull_request.side_effect = HttpError(500, "Error 1")
        adapter2 = MagicMock()
        adapter2.create_pull_request.side_effect = HttpError(403, "Error 2")
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

        batch_cmd.handle_batch_pr(args, fmt="json")

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert len(data) == 2
        assert all(r["status"] == "failed" for r in data)
        assert all(r["error"] is not None for r in data)

    @patch("gfo.commands.batch.create_adapter_from_spec")
    @patch("gfo.commands.batch.parse_service_spec")
    def test_invalid_spec_label_fallback(self, mock_parse, mock_create_adapter, capsys):
        """parse_service_spec が両方失敗 → 生の spec_str が repo_label に使われる。"""
        # 最初の parse_service_spec 呼び出しで create_adapter_from_spec が例外
        # except 内の parse_service_spec も失敗するケース
        mock_parse.side_effect = ConfigError("Invalid spec")

        args = make_args(
            repos="invalid-spec-string",
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
        assert len(data) == 1
        assert data[0]["status"] == "failed"
        assert data[0]["repo"] == "invalid-spec-string"

    @patch("gfo.commands.batch.create_adapter_from_spec")
    @patch("gfo.commands.batch.parse_service_spec")
    def test_draft_flag_forwarded(self, mock_parse, mock_create_adapter):
        """draft=True が create_pull_request に渡される。"""
        spec = _make_spec()
        mock_parse.return_value = spec
        adapter = MagicMock()
        adapter.create_pull_request.return_value = _make_pr()
        mock_create_adapter.return_value = adapter

        args = make_args(
            repos="github:owner/repo",
            title="Draft PR",
            body="body",
            head="feature",
            base="main",
            draft=True,
            dry_run=False,
            batch_pr_action="create",
        )

        batch_cmd.handle_batch_pr(args, fmt="table")

        adapter.create_pull_request.assert_called_once_with(
            title="Draft PR",
            body="body",
            head="feature",
            base="main",
            draft=True,
        )

    @patch("gfo.commands.batch.create_adapter_from_spec")
    @patch("gfo.commands.batch.parse_service_spec")
    def test_repos_whitespace_handling(self, mock_parse, mock_create_adapter, capsys):
        """前後の空白 + 空要素がスキップされる。"""
        spec = _make_spec()
        mock_parse.return_value = spec
        adapter = MagicMock()
        adapter.create_pull_request.return_value = _make_pr()
        mock_create_adapter.return_value = adapter

        args = make_args(
            repos=" , github:o/r , ",
            title="Test PR",
            body="",
            head="feature",
            base="main",
            draft=False,
            dry_run=False,
            batch_pr_action="create",
        )

        batch_cmd.handle_batch_pr(args, fmt="json")

        # 空要素がスキップされ、1つだけ処理される
        assert mock_parse.call_count == 1
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert len(data) == 1
        assert data[0]["status"] == "created"

    @patch("gfo.commands.batch.create_adapter_from_spec")
    @patch("gfo.commands.batch.parse_service_spec")
    def test_dry_run_json_output(self, mock_parse, mock_create_adapter, capsys):
        """dry_run 結果の JSON 内容検証。"""
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

        batch_cmd.handle_batch_pr(args, fmt="json")

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert len(data) == 1
        assert data[0]["status"] == "skipped"
        assert data[0]["number"] is None
        assert data[0]["url"] is None
        assert data[0]["error"] is None
        assert data[0]["repo"] == "github:owner/repo"

    @patch("gfo.commands.batch.create_adapter_from_spec")
    @patch("gfo.commands.batch.parse_service_spec")
    def test_mixed_order_preserved(self, mock_parse, mock_create_adapter, capsys):
        """成功→失敗→成功の results 順序保持。"""
        spec1 = _make_spec("github", "o1", "r1")
        spec2 = _make_spec("github", "o2", "r2")
        spec3 = _make_spec("github", "o3", "r3")
        mock_parse.side_effect = [spec1, spec2, spec3]

        adapter1 = MagicMock()
        adapter1.create_pull_request.return_value = _make_pr(number=1)
        adapter2 = MagicMock()
        adapter2.create_pull_request.side_effect = HttpError(500, "Error")
        adapter3 = MagicMock()
        adapter3.create_pull_request.return_value = _make_pr(number=3)
        mock_create_adapter.side_effect = [adapter1, adapter2, adapter3]

        args = make_args(
            repos="github:o1/r1,github:o2/r2,github:o3/r3",
            title="Test",
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
        assert len(data) == 3
        assert data[0]["status"] == "created"
        assert data[0]["repo"] == "github:o1/r1"
        assert data[1]["status"] == "failed"
        assert data[1]["repo"] == "github:o2/r2"
        assert data[2]["status"] == "created"
        assert data[2]["repo"] == "github:o3/r3"


class TestBatchPrCreateNonGfoErrorRaised:
    """batch pr create は GfoError 系のみ failed として記録し、
    プログラミングエラー（AttributeError 等）は握りつぶさず再 raise する。

    旧実装は except Exception で全例外を捕捉していたため、アダプターのレスポンス
    型ミスマッチ等の実装バグが「単に failed と表示される」だけで本番障害として
    顕在化しにくい状態だった。
    """

    @patch("gfo.commands.batch.create_adapter_from_spec")
    @patch("gfo.commands.batch.parse_service_spec")
    def test_attribute_error_is_re_raised(self, mock_parse_spec, mock_create_adapter):
        spec = MagicMock()
        spec.service_type = "github"
        spec.owner = "o1"
        spec.repo = "r1"
        mock_parse_spec.return_value = spec
        adapter = MagicMock()
        adapter.create_pull_request.side_effect = AttributeError("'NoneType' object has no 'x'")
        mock_create_adapter.return_value = adapter

        args = make_args(
            repos="github:o1/r1",
            title="t",
            body="b",
            head="feat",
            base="main",
            draft=False,
            dry_run=False,
            batch_pr_action="create",
        )
        with pytest.raises(AttributeError):
            batch_cmd.handle_batch_pr(args, fmt="json")

    @patch("gfo.commands.batch.parse_service_spec")
    def test_parse_spec_attribute_error_is_re_raised(self, mock_parse_spec):
        """`parse_service_spec` 自体が AttributeError を投げた場合も再 raise されること。

        旧実装で `except Exception` が握りつぶしていた範囲のうち、spec パース時の
        実装バグ (プログラミングエラー) も握りつぶさず本番ログに上げる挙動を
        テストでも担保する。
        """
        mock_parse_spec.side_effect = AttributeError("bug")
        args = make_args(
            repos="github:o1/r1",
            title="t",
            body="b",
            head="feat",
            base="main",
            draft=False,
            dry_run=False,
            batch_pr_action="create",
        )
        with pytest.raises(AttributeError, match="bug"):
            batch_cmd.handle_batch_pr(args, fmt="json")
