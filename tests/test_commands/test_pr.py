"""gfo.commands.pr のテスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gfo.adapter.base import CheckRun, PullRequestCommit, PullRequestFile
from gfo.commands import pr as pr_cmd
from gfo.exceptions import ConfigError, NotFoundError
from tests.test_commands.conftest import make_args, patch_adapter


@pytest.fixture
def mock_adapter(sample_pr):
    adapter = MagicMock()
    adapter.list_pull_requests.return_value = [sample_pr]
    adapter.create_pull_request.return_value = sample_pr
    adapter.get_pull_request.return_value = sample_pr
    adapter.get_pr_checkout_refspec.return_value = "refs/pull/1/head"
    return adapter


def _patch_all(sample_config, mock_adapter):
    """resolve_project_config と create_adapter をまとめてパッチするコンテキスト。"""
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        with patch("gfo.commands.pr.get_adapter", return_value=mock_adapter):
            yield

    return _ctx()


class TestHandleList:
    def test_calls_list_pull_requests(self, sample_config, mock_adapter, capsys):
        args = make_args(state="open", limit=30)
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_list(args, fmt="table")

        mock_adapter.list_pull_requests.assert_called_once_with(state="open", limit=30)

    def test_outputs_results(self, sample_config, mock_adapter, capsys):
        args = make_args(state="open", limit=30)
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_list(args, fmt="table")

        out = capsys.readouterr().out
        assert "Test PR" in out
        assert "open" in out

    def test_json_format(self, sample_config, mock_adapter, capsys):
        args = make_args(state="open", limit=10)
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_list(args, fmt="json")

        import json

        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, list)
        assert data[0]["title"] == "Test PR"

    def test_plain_format(self, sample_config, mock_adapter, capsys):
        args = make_args(state="open", limit=30)
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_list(args, fmt="plain")

        out = capsys.readouterr().out
        assert "\t" in out
        assert "NUMBER" not in out
        assert "Test PR" in out


class TestHandleCreate:
    def test_uses_provided_args(self, sample_config, mock_adapter, capsys):
        args = make_args(
            head="feature/test",
            base="main",
            title="My PR",
            body="Description",
            draft=False,
        )
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_create(args, fmt="table")

        mock_adapter.create_pull_request.assert_called_once_with(
            title="My PR",
            body="Description",
            base="main",
            head="feature/test",
            draft=False,
        )

    def test_infers_head_from_git(self, sample_config, mock_adapter, capsys):
        args = make_args(head=None, base="main", title="My PR", body="", draft=False)
        with (
            _patch_all(sample_config, mock_adapter),
            patch("gfo.commands.pr.gfo.git_util.get_current_branch", return_value="feature/auto"),
        ):
            pr_cmd.handle_create(args, fmt="table")

        call_kwargs = mock_adapter.create_pull_request.call_args.kwargs
        assert call_kwargs["head"] == "feature/auto"

    def test_infers_base_from_git(self, sample_config, mock_adapter, capsys):
        args = make_args(head="feature/x", base=None, title="My PR", body="", draft=False)
        with (
            _patch_all(sample_config, mock_adapter),
            patch("gfo.commands.pr.gfo.git_util.get_default_branch", return_value="develop"),
        ):
            pr_cmd.handle_create(args, fmt="table")

        call_kwargs = mock_adapter.create_pull_request.call_args.kwargs
        assert call_kwargs["base"] == "develop"

    def test_infers_title_from_last_commit(self, sample_config, mock_adapter, capsys):
        args = make_args(head="feature/x", base="main", title=None, body="", draft=False)
        with (
            _patch_all(sample_config, mock_adapter),
            patch(
                "gfo.commands.pr.gfo.git_util.get_last_commit_subject",
                return_value="Auto commit title",
            ),
        ):
            pr_cmd.handle_create(args, fmt="table")

        call_kwargs = mock_adapter.create_pull_request.call_args.kwargs
        assert call_kwargs["title"] == "Auto commit title"

    def test_draft_flag(self, sample_config, mock_adapter, capsys):
        args = make_args(head="feature/x", base="main", title="Draft", body="", draft=True)
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_create(args, fmt="table")

        call_kwargs = mock_adapter.create_pull_request.call_args.kwargs
        assert call_kwargs["draft"] is True

    def test_title_with_surrounding_whitespace_is_stripped(self, sample_config, mock_adapter):
        """前後に空白を持つ title は strip されてアダプターに渡される。"""
        args = make_args(head="feature/x", base="main", title="  My PR  ", body="", draft=False)
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_create(args, fmt="table")

        call_kwargs = mock_adapter.create_pull_request.call_args.kwargs
        assert call_kwargs["title"] == "My PR"


class TestHandleCreateTitleValidation:
    def test_no_title_and_no_commit_raises_config_error(self, sample_config, mock_adapter):
        """title=None かつ git から取得もできない場合は ConfigError を送出する。"""
        args = make_args(head="feature/x", base="main", title=None, body="", draft=False)
        with (
            _patch_all(sample_config, mock_adapter),
            patch("gfo.commands.pr.gfo.git_util.get_last_commit_subject", return_value=""),
            pytest.raises(ConfigError, match="Could not determine PR title"),
        ):
            pr_cmd.handle_create(args, fmt="table")

    def test_whitespace_title_raises_config_error(self, sample_config, mock_adapter):
        """title が空白のみの場合は ConfigError を送出する。"""
        args = make_args(head="feature/x", base="main", title="   ", body="", draft=False)
        with (
            _patch_all(sample_config, mock_adapter),
            pytest.raises(ConfigError, match="Could not determine PR title"),
        ):
            pr_cmd.handle_create(args, fmt="table")


class TestHandleView:
    def test_calls_get_pull_request(self, sample_config, mock_adapter, capsys):
        args = make_args(number=1)
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_view(args, fmt="table")

        mock_adapter.get_pull_request.assert_called_once_with(1)

    def test_outputs_pr(self, sample_config, mock_adapter, capsys):
        args = make_args(number=1)
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_view(args, fmt="table")

        out = capsys.readouterr().out
        assert "Test PR" in out


class TestHandleMerge:
    def test_calls_merge_pull_request(self, sample_config, mock_adapter):
        args = make_args(number=1, method="merge")
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_merge(args, fmt="table")

        mock_adapter.merge_pull_request.assert_called_once_with(1, method="merge")

    def test_squash_method(self, sample_config, mock_adapter):
        args = make_args(number=2, method="squash")
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_merge(args, fmt="table")

        mock_adapter.merge_pull_request.assert_called_once_with(2, method="squash")


class TestHandleClose:
    def test_calls_close_pull_request(self, sample_config, mock_adapter):
        args = make_args(number=1)
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_close(args, fmt="table")

        mock_adapter.close_pull_request.assert_called_once_with(1)


class TestHandleReopen:
    def test_calls_reopen_pull_request(self, sample_config, mock_adapter):
        args = make_args(number=1)
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_reopen(args, fmt="table")

        mock_adapter.reopen_pull_request.assert_called_once_with(1)

    def test_different_number(self, sample_config, mock_adapter):
        args = make_args(number=42)
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_reopen(args, fmt="table")

        mock_adapter.reopen_pull_request.assert_called_once_with(42)


class TestHandleCheckout:
    def test_fetches_and_checks_out(self, sample_config, mock_adapter):
        args = make_args(number=1)
        with (
            _patch_all(sample_config, mock_adapter),
            patch("gfo.commands.pr.gfo.git_util.git_fetch") as mock_fetch,
            patch("gfo.commands.pr.gfo.git_util.git_checkout_branch") as mock_checkout,
        ):
            pr_cmd.handle_checkout(args, fmt="table")

        mock_adapter.get_pull_request.assert_called_once_with(1)
        mock_adapter.get_pr_checkout_refspec.assert_called_once()
        mock_fetch.assert_called_once_with("origin", "refs/pull/1/head")
        mock_checkout.assert_called_once_with("feature/test")

    def test_checkout_pr_not_found_raises(self, sample_config, mock_adapter):
        mock_adapter.get_pull_request.side_effect = NotFoundError("/pulls/999")
        args = make_args(number=999)
        with _patch_all(sample_config, mock_adapter):
            with pytest.raises(NotFoundError):
                pr_cmd.handle_checkout(args, fmt="table")

    def test_checkout_git_fetch_failure(self, sample_config, mock_adapter):
        import subprocess

        args = make_args(number=1)
        with (
            _patch_all(sample_config, mock_adapter),
            patch(
                "gfo.commands.pr.gfo.git_util.git_fetch",
                side_effect=subprocess.CalledProcessError(1, "git"),
            ),
        ):
            with pytest.raises(subprocess.CalledProcessError):
                pr_cmd.handle_checkout(args, fmt="table")


class TestErrorPropagation:
    """アダプターのエラーがハンドラを通じて伝搬する。"""

    def test_list_http_error(self, sample_config, mock_adapter):
        mock_adapter.list_pull_requests.side_effect = NotFoundError("/pulls")
        args = make_args(state="open", limit=30)
        with _patch_all(sample_config, mock_adapter):
            with pytest.raises(NotFoundError):
                pr_cmd.handle_list(args, fmt="table")

    def test_view_http_error(self, sample_config, mock_adapter):
        mock_adapter.get_pull_request.side_effect = NotFoundError("/pulls/999")
        args = make_args(number=999)
        with _patch_all(sample_config, mock_adapter):
            with pytest.raises(NotFoundError):
                pr_cmd.handle_view(args, fmt="table")

    def test_merge_http_error(self, sample_config, mock_adapter):
        mock_adapter.merge_pull_request.side_effect = NotFoundError("/pulls/999/merge")
        args = make_args(number=999, method="merge")
        with _patch_all(sample_config, mock_adapter):
            with pytest.raises(NotFoundError):
                pr_cmd.handle_merge(args, fmt="table")


class TestHandleDiff:
    def test_prints_diff(self, capsys):
        with patch_adapter("gfo.commands.pr") as adapter:
            adapter.get_pull_request_diff.return_value = "diff --git a/file.txt b/file.txt\n"
            args = make_args(number=1)
            pr_cmd.handle_diff(args, fmt="table")
        captured = capsys.readouterr()
        assert "diff --git" in captured.out
        adapter.get_pull_request_diff.assert_called_once_with(1)


class TestHandleChecks:
    SAMPLE_CHECK = CheckRun(
        name="ci/build",
        status="completed",
        conclusion="success",
        url="https://example.com/checks/1",
        started_at="2024-01-01T00:00:00Z",
    )

    def test_calls_list_pull_request_checks(self, capsys):
        with patch_adapter("gfo.commands.pr") as adapter:
            adapter.list_pull_request_checks.return_value = [self.SAMPLE_CHECK]
            args = make_args(number=1)
            pr_cmd.handle_checks(args, fmt="table")
        adapter.list_pull_request_checks.assert_called_once_with(1)
        out = capsys.readouterr().out
        assert "ci/build" in out

    def test_json_format(self, capsys):
        import json

        with patch_adapter("gfo.commands.pr") as adapter:
            adapter.list_pull_request_checks.return_value = [self.SAMPLE_CHECK]
            args = make_args(number=1)
            pr_cmd.handle_checks(args, fmt="json")
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert data[0]["name"] == "ci/build"


class TestHandleFiles:
    SAMPLE_FILE = PullRequestFile(
        filename="src/main.py",
        status="modified",
        additions=10,
        deletions=2,
    )

    def test_calls_list_pull_request_files(self, capsys):
        with patch_adapter("gfo.commands.pr") as adapter:
            adapter.list_pull_request_files.return_value = [self.SAMPLE_FILE]
            args = make_args(number=1)
            pr_cmd.handle_files(args, fmt="table")
        adapter.list_pull_request_files.assert_called_once_with(1)
        out = capsys.readouterr().out
        assert "src/main.py" in out

    def test_json_format(self, capsys):
        import json

        with patch_adapter("gfo.commands.pr") as adapter:
            adapter.list_pull_request_files.return_value = [self.SAMPLE_FILE]
            args = make_args(number=1)
            pr_cmd.handle_files(args, fmt="json")
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert data[0]["filename"] == "src/main.py"


class TestHandleCommits:
    SAMPLE_COMMIT = PullRequestCommit(
        sha="abc1234",
        message="fix: resolve bug",
        author="dev-user",
        created_at="2024-01-01T00:00:00Z",
    )

    def test_calls_list_pull_request_commits(self, capsys):
        with patch_adapter("gfo.commands.pr") as adapter:
            adapter.list_pull_request_commits.return_value = [self.SAMPLE_COMMIT]
            args = make_args(number=1)
            pr_cmd.handle_commits(args, fmt="table")
        adapter.list_pull_request_commits.assert_called_once_with(1)
        out = capsys.readouterr().out
        assert "abc1234" in out

    def test_json_format(self, capsys):
        import json

        with patch_adapter("gfo.commands.pr") as adapter:
            adapter.list_pull_request_commits.return_value = [self.SAMPLE_COMMIT]
            args = make_args(number=1)
            pr_cmd.handle_commits(args, fmt="json")
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert data[0]["sha"] == "abc1234"


class TestHandleReviewers:
    def test_list_action(self, capsys):
        with patch_adapter("gfo.commands.pr") as adapter:
            adapter.list_requested_reviewers.return_value = []
            args = make_args(number=1, reviewer_action=None)
            pr_cmd.handle_reviewers(args, fmt="json")
        adapter.list_requested_reviewers.assert_called_once_with(1)
        out = capsys.readouterr().out
        assert "[]" in out

    def test_add_action(self):
        with patch_adapter("gfo.commands.pr") as adapter:
            args = make_args(number=1, reviewer_action="add", users=["user1", "user2"])
            pr_cmd.handle_reviewers(args, fmt="table")
        adapter.request_reviewers.assert_called_once_with(1, ["user1", "user2"])

    def test_remove_action(self):
        with patch_adapter("gfo.commands.pr") as adapter:
            args = make_args(number=1, reviewer_action="remove", users=["user1"])
            pr_cmd.handle_reviewers(args, fmt="table")
        adapter.remove_reviewers.assert_called_once_with(1, ["user1"])


class TestHandleUpdateBranch:
    def test_calls_update_pull_request_branch(self):
        with patch_adapter("gfo.commands.pr") as adapter:
            args = make_args(number=1)
            pr_cmd.handle_update_branch(args, fmt="table")
        adapter.update_pull_request_branch.assert_called_once_with(1)


class TestHandleReady:
    def test_calls_mark_pull_request_ready(self):
        with patch_adapter("gfo.commands.pr") as adapter:
            args = make_args(number=1)
            pr_cmd.handle_ready(args, fmt="table")
        adapter.mark_pull_request_ready.assert_called_once_with(1)


class TestHandleMergeAuto:
    def test_auto_merge_calls_enable_auto_merge(self):
        with patch_adapter("gfo.commands.pr") as adapter:
            args = make_args(number=1, method="squash", auto=True)
            pr_cmd.handle_merge(args, fmt="table")
        adapter.enable_auto_merge.assert_called_once_with(1, merge_method="squash")
        adapter.merge_pull_request.assert_not_called()


def test_pr_list_config_error(capsys):
    """resolve_project_config が ConfigError を投げた場合に CLI で exit code 6 になる。"""
    from gfo.cli import main

    with patch("gfo.commands.pr.get_adapter", side_effect=ConfigError("not configured")):
        result = main(["pr", "list"])

    assert result == 6
    assert "not configured" in capsys.readouterr().err
