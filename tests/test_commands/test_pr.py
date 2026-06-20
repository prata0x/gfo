"""gfo.commands.pr のテスト。"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from gfo.adapter.base import CheckRun, PullRequestCommit, PullRequestFile
from gfo.commands import pr as pr_cmd
from gfo.exceptions import ConfigError, GfoError, NotFoundError
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

        mock_adapter.list_pull_requests.assert_called_once_with(
            state="open",
            limit=30,
            author=None,
            label=None,
            assignee=None,
            search=None,
            base=None,
            head=None,
            draft=None,
            milestone=None,
        )

    def test_passes_filter_params(self, sample_config, mock_adapter, capsys):
        args = make_args(
            state="open",
            limit=30,
            author="alice",
            label="bug",
            assignee="bob",
            search="fix",
            base="main",
            head="feature",
            draft=True,
        )
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_list(args, fmt="table")

        mock_adapter.list_pull_requests.assert_called_once_with(
            state="open",
            limit=30,
            author="alice",
            label="bug",
            assignee="bob",
            search="fix",
            base="main",
            head="feature",
            draft=True,
            milestone=None,
        )

    # NOTE: フィルタ未指定時に全 filter kwargs が None になることは
    # test_calls_list_pull_requests の assert_called_once_with(...) が完全に検証済み。
    # 同内容を個別 assert で重複させていた test_default_filter_params_are_none は削除。

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
            reviewers=None,
            assignees=None,
            labels=None,
            milestone=None,
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

    def test_passes_reviewers_to_adapter(self, sample_config, mock_adapter, capsys):
        args = make_args(
            head="feature/x",
            base="main",
            title="My PR",
            body="",
            draft=False,
            reviewer=["alice", "bob"],
            assignee=None,
            label=None,
            milestone=None,
            fill=False,
        )
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_create(args, fmt="table")
        call_kwargs = mock_adapter.create_pull_request.call_args.kwargs
        assert call_kwargs["reviewers"] == ["alice", "bob"]

    def test_passes_assignees_to_adapter(self, sample_config, mock_adapter, capsys):
        args = make_args(
            head="feature/x",
            base="main",
            title="My PR",
            body="",
            draft=False,
            reviewer=None,
            assignee=["alice"],
            label=None,
            milestone=None,
            fill=False,
        )
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_create(args, fmt="table")
        call_kwargs = mock_adapter.create_pull_request.call_args.kwargs
        assert call_kwargs["assignees"] == ["alice"]

    def test_passes_labels_to_adapter(self, sample_config, mock_adapter, capsys):
        args = make_args(
            head="feature/x",
            base="main",
            title="My PR",
            body="",
            draft=False,
            reviewer=None,
            assignee=None,
            label=["bug", "urgent"],
            milestone=None,
            fill=False,
        )
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_create(args, fmt="table")
        call_kwargs = mock_adapter.create_pull_request.call_args.kwargs
        assert call_kwargs["labels"] == ["bug", "urgent"]

    def test_passes_milestone_to_adapter(self, sample_config, mock_adapter, capsys):
        args = make_args(
            head="feature/x",
            base="main",
            title="My PR",
            body="",
            draft=False,
            reviewer=None,
            assignee=None,
            label=None,
            milestone="v1.0",
            fill=False,
        )
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_create(args, fmt="table")
        call_kwargs = mock_adapter.create_pull_request.call_args.kwargs
        assert call_kwargs["milestone"] == "v1.0"

    def test_fill_sets_body_from_commit(self, sample_config, mock_adapter, capsys):
        args = make_args(
            head="feature/x",
            base="main",
            title="My PR",
            body="",
            draft=False,
            reviewer=None,
            assignee=None,
            label=None,
            milestone=None,
            fill=True,
        )
        with (
            _patch_all(sample_config, mock_adapter),
            patch(
                "gfo.commands.pr.gfo.git_util.get_last_commit_body", return_value="Commit body text"
            ),
        ):
            pr_cmd.handle_create(args, fmt="table")
        call_kwargs = mock_adapter.create_pull_request.call_args.kwargs
        assert call_kwargs["body"] == "Commit body text"

    def test_fill_does_not_override_explicit_body(self, sample_config, mock_adapter, capsys):
        args = make_args(
            head="feature/x",
            base="main",
            title="My PR",
            body="explicit body",
            draft=False,
            reviewer=None,
            assignee=None,
            label=None,
            milestone=None,
            fill=True,
        )
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_create(args, fmt="table")
        call_kwargs = mock_adapter.create_pull_request.call_args.kwargs
        assert call_kwargs["body"] == "explicit body"

    def test_none_options_not_passed_when_unset(self, sample_config, mock_adapter, capsys):
        args = make_args(
            head="feature/x",
            base="main",
            title="My PR",
            body="",
            draft=False,
            reviewer=None,
            assignee=None,
            label=None,
            milestone=None,
            fill=False,
        )
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_create(args, fmt="table")
        call_kwargs = mock_adapter.create_pull_request.call_args.kwargs
        assert call_kwargs["reviewers"] is None
        assert call_kwargs["assignees"] is None
        assert call_kwargs["labels"] is None
        assert call_kwargs["milestone"] is None

    def test_body_file_overrides_body(self, sample_config, mock_adapter, capsys, tmp_path):
        """--body-file が指定されたらファイル内容を body として使用する。"""
        body_path = tmp_path / "body.md"
        body_path.write_text("Body from file")
        args = make_args(
            head="feature/x",
            base="main",
            title="My PR",
            body="",
            draft=False,
            body_file=str(body_path),
        )
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_create(args, fmt="table")
        call_kwargs = mock_adapter.create_pull_request.call_args.kwargs
        assert call_kwargs["body"] == "Body from file"

    def test_body_file_none_uses_body(self, sample_config, mock_adapter, capsys):
        """--body-file 未指定なら --body の値を使用する。"""
        args = make_args(
            head="feature/x",
            base="main",
            title="My PR",
            body="Inline body",
            draft=False,
            body_file=None,
        )
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_create(args, fmt="table")
        call_kwargs = mock_adapter.create_pull_request.call_args.kwargs
        assert call_kwargs["body"] == "Inline body"

    def test_body_file_not_found_raises_gfo_error(self, sample_config, mock_adapter):
        """存在しないファイルを --body-file に指定すると GfoError を送出する。"""
        args = make_args(
            head="feature/x",
            base="main",
            title="My PR",
            body="",
            draft=False,
            body_file="nonexistent.txt",
        )
        with _patch_all(sample_config, mock_adapter):
            with pytest.raises(GfoError, match="File not found"):
                pr_cmd.handle_create(args, fmt="table")


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
        args = make_args(number=1, merge=False, squash=False, rebase=False)
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_merge(args, fmt="table")

        mock_adapter.merge_pull_request.assert_called_once_with(
            1, method="merge", title=None, message=None
        )

    def test_squash_method(self, sample_config, mock_adapter):
        args = make_args(number=2, squash=True)
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_merge(args, fmt="table")

        mock_adapter.merge_pull_request.assert_called_once_with(
            2, method="squash", title=None, message=None
        )

    def test_rebase_method(self, sample_config, mock_adapter):
        args = make_args(number=3, rebase=True)
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_merge(args, fmt="table")

        mock_adapter.merge_pull_request.assert_called_once_with(
            3, method="rebase", title=None, message=None
        )

    def test_delete_branch_after_merge(self, sample_config, mock_adapter):
        args = make_args(number=1, merge=False, squash=False, rebase=False, delete_branch=True)
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_merge(args, fmt="table")

        mock_adapter.merge_pull_request.assert_called_once_with(
            1, method="merge", title=None, message=None
        )
        mock_adapter.get_pull_request.assert_called_once_with(1)
        mock_adapter.delete_branch.assert_called_once_with(name="feature/test")

    def test_no_delete_branch_by_default(self, sample_config, mock_adapter):
        args = make_args(number=1, merge=False, squash=False, rebase=False)
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_merge(args, fmt="table")

        mock_adapter.delete_branch.assert_not_called()

    def test_subject_and_body(self, sample_config, mock_adapter):
        args = make_args(
            number=1,
            merge=False,
            squash=False,
            rebase=False,
            subject="Custom title",
            body="Custom body",
        )
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_merge(args, fmt="table")

        mock_adapter.merge_pull_request.assert_called_once_with(
            1, method="merge", title="Custom title", message="Custom body"
        )

    def test_subject_only(self, sample_config, mock_adapter):
        args = make_args(number=1, merge=False, squash=False, rebase=False, subject="Title only")
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_merge(args, fmt="table")

        mock_adapter.merge_pull_request.assert_called_once_with(
            1, method="merge", title="Title only", message=None
        )


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


class TestHandleLock:
    def test_lock_pull_request(self, sample_config, mock_adapter):
        args = make_args(number=1, reason=None)
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_lock(args, fmt="table")

        mock_adapter.lock_pull_request.assert_called_once_with(1, reason=None)

    def test_lock_pull_request_with_reason(self, sample_config, mock_adapter):
        args = make_args(number=1, reason="resolved")
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_lock(args, fmt="table")

        mock_adapter.lock_pull_request.assert_called_once_with(1, reason="resolved")

    def test_unlock_pull_request(self, sample_config, mock_adapter):
        args = make_args(number=1)
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_unlock(args, fmt="table")

        mock_adapter.unlock_pull_request.assert_called_once_with(1)


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
    def test_writes_diff_chunks_to_stdout_buffer(self):
        """ストリーミング応答を sys.stdout.buffer.write に順番通り書き出す。"""
        with patch_adapter("gfo.commands.pr") as adapter:
            adapter.get_pull_request_diff.return_value = iter(
                [b"diff --git a/file.txt b/file.txt\n", b"--- a/file.txt\n"]
            )
            args = make_args(number=1)
            with patch("sys.stdout") as mock_stdout:
                pr_cmd.handle_diff(args, fmt="table")
        adapter.get_pull_request_diff.assert_called_once_with(1)
        # buffer.write が両チャンク順に呼ばれていること
        writes = [call.args[0] for call in mock_stdout.buffer.write.call_args_list]
        assert writes == [b"diff --git a/file.txt b/file.txt\n", b"--- a/file.txt\n"]
        mock_stdout.buffer.flush.assert_called_once_with()


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

    def test_list_action_non_empty_json(self, capsys):
        """list[str] を json 出力してもクラッシュしないこと（output() 誤用の回帰）。"""
        with patch_adapter("gfo.commands.pr") as adapter:
            adapter.list_requested_reviewers.return_value = ["alice", "bob"]
            args = make_args(number=1, reviewer_action=None)
            pr_cmd.handle_reviewers(args, fmt="json")
        out = capsys.readouterr().out
        assert json.loads(out) == ["alice", "bob"]

    def test_list_action_non_empty_table(self, capsys):
        """table 出力では各レビュアーを1行ずつ表示すること。"""
        with patch_adapter("gfo.commands.pr") as adapter:
            adapter.list_requested_reviewers.return_value = ["alice", "bob"]
            args = make_args(number=1, reviewer_action=None)
            pr_cmd.handle_reviewers(args, fmt="table")
        out = capsys.readouterr().out
        assert out.splitlines() == ["alice", "bob"]

    def test_list_action_jq(self, capsys):
        """--jq が list[str] 出力に接続されていること。"""
        with patch_adapter("gfo.commands.pr") as adapter:
            adapter.list_requested_reviewers.return_value = ["alice", "bob"]
            args = make_args(number=1, reviewer_action=None)
            pr_cmd.handle_reviewers(args, fmt="json", jq=".[0]")
        out = capsys.readouterr().out
        assert "alice" in out

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
            args = make_args(number=1, squash=True, auto=True)
            pr_cmd.handle_merge(args, fmt="table")
        adapter.enable_auto_merge.assert_called_once_with(1, merge_method="squash")
        adapter.merge_pull_request.assert_not_called()

    def test_auto_merge_warns_subject_body(self):
        import warnings

        with patch_adapter("gfo.commands.pr") as adapter:
            args = make_args(number=1, squash=False, auto=True, subject="Title", body="Body")
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                pr_cmd.handle_merge(args, fmt="table")
            assert len(w) == 1
            assert "--subject/--body" in str(w[0].message)
        adapter.enable_auto_merge.assert_called_once()

    def test_auto_with_delete_branch_raises(self):
        """--auto + --delete-branch はマージ前にブランチが消えるため拒否すること。"""
        with patch_adapter("gfo.commands.pr") as adapter:
            args = make_args(number=1, squash=False, auto=True, delete_branch=True)
            with pytest.raises(ConfigError, match="--delete-branch cannot be combined"):
                pr_cmd.handle_merge(args, fmt="table")
        adapter.enable_auto_merge.assert_not_called()
        adapter.delete_branch.assert_not_called()


class TestHandleMergeDisableAuto:
    def test_disable_auto_merge_calls_adapter(self):
        with patch_adapter("gfo.commands.pr") as adapter:
            args = make_args(number=1, squash=False, auto=False, disable_auto=True)
            pr_cmd.handle_merge(args, fmt="table")
        adapter.disable_auto_merge.assert_called_once_with(1)
        adapter.merge_pull_request.assert_not_called()

    def test_disable_auto_with_delete_branch_raises(self):
        """--disable-auto + --delete-branch も同様に拒否すること。"""
        with patch_adapter("gfo.commands.pr") as adapter:
            args = make_args(number=1, squash=False, disable_auto=True, delete_branch=True)
            with pytest.raises(ConfigError, match="--delete-branch cannot be combined"):
                pr_cmd.handle_merge(args, fmt="table")
        adapter.disable_auto_merge.assert_not_called()
        adapter.delete_branch.assert_not_called()
        adapter.enable_auto_merge.assert_not_called()

    def test_disable_auto_prints_message(self, capsys):
        with patch_adapter("gfo.commands.pr"):
            args = make_args(number=42, squash=False, auto=False, disable_auto=True)
            pr_cmd.handle_merge(args, fmt="table")
        out = capsys.readouterr().out
        assert "42" in out
        assert "Disabled" in out

    def test_disable_auto_ignores_merge_method(self):
        """--disable-auto と --squash を同時指定しても disable_auto_merge のみ呼ばれる。"""
        with patch_adapter("gfo.commands.pr") as adapter:
            args = make_args(number=1, squash=True, auto=False, disable_auto=True)
            pr_cmd.handle_merge(args, fmt="table")
        adapter.disable_auto_merge.assert_called_once_with(1)
        adapter.merge_pull_request.assert_not_called()

    def test_disable_auto_wins_over_auto(self):
        """--disable-auto と --auto 同時指定時は disable_auto が優先される。"""
        with patch_adapter("gfo.commands.pr") as adapter:
            args = make_args(number=1, squash=False, auto=True, disable_auto=True)
            pr_cmd.handle_merge(args, fmt="table")
        adapter.disable_auto_merge.assert_called_once_with(1)
        adapter.enable_auto_merge.assert_not_called()


def test_pr_list_config_error(capsys):
    """resolve_project_config が ConfigError を投げた場合に CLI で exit code 6 になる。"""
    from gfo.cli import main

    with patch("gfo.commands.pr.get_adapter", side_effect=ConfigError("not configured")):
        result = main(["pr", "list"])

    assert result == 6
    assert "not configured" in capsys.readouterr().err


class TestHandleListWeb:
    def test_opens_browser(self, sample_config, mock_adapter):
        args = make_args(state="open", limit=30, web=True)
        with (
            _patch_all(sample_config, mock_adapter),
            patch("webbrowser.open") as mock_open,
        ):
            pr_cmd.handle_list(args, fmt="table")
        mock_adapter.get_web_url.assert_called_once_with("pr")
        mock_open.assert_called_once_with(mock_adapter.get_web_url.return_value)

    def test_does_not_call_api(self, sample_config, mock_adapter):
        args = make_args(state="open", limit=30, web=True)
        with (
            _patch_all(sample_config, mock_adapter),
            patch("webbrowser.open"),
        ):
            pr_cmd.handle_list(args, fmt="table")
        mock_adapter.list_pull_requests.assert_not_called()


class TestHandleViewWeb:
    def test_opens_browser(self, sample_config, mock_adapter):
        args = make_args(number=42, web=True)
        with (
            _patch_all(sample_config, mock_adapter),
            patch("webbrowser.open") as mock_open,
        ):
            pr_cmd.handle_view(args, fmt="table")
        mock_adapter.get_web_url.assert_called_once_with("pr", 42)
        mock_open.assert_called_once_with(mock_adapter.get_web_url.return_value)

    def test_does_not_call_api(self, sample_config, mock_adapter):
        args = make_args(number=42, web=True)
        with (
            _patch_all(sample_config, mock_adapter),
            patch("webbrowser.open"),
        ):
            pr_cmd.handle_view(args, fmt="table")
        mock_adapter.get_pull_request.assert_not_called()


class TestWebWithJsonFormat:
    """--web + --format json の組み合わせテスト（#37）。"""

    def test_list_web_json_opens_browser_no_json_output(self, sample_config, mock_adapter, capsys):
        """--web 時は fmt="json" でもブラウザを開き、JSON 出力しない。"""
        args = make_args(state="open", limit=30, web=True)
        with (
            _patch_all(sample_config, mock_adapter),
            patch("webbrowser.open") as mock_open,
        ):
            pr_cmd.handle_list(args, fmt="json")
        mock_open.assert_called_once()
        mock_adapter.list_pull_requests.assert_not_called()
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_view_web_json_opens_browser_no_json_output(self, sample_config, mock_adapter, capsys):
        """--web + fmt="json" で PR view もブラウザ表示のみ。"""
        args = make_args(number=42, web=True)
        with (
            _patch_all(sample_config, mock_adapter),
            patch("webbrowser.open") as mock_open,
        ):
            pr_cmd.handle_view(args, fmt="json")
        mock_open.assert_called_once()
        mock_adapter.get_pull_request.assert_not_called()
        captured = capsys.readouterr()
        assert captured.out == ""


class TestPrListArgParsing:
    """pr list の CLI 引数パースのテスト。"""

    def test_filter_args_parsed(self):
        from gfo.cli import create_parser

        parser, _ = create_parser()
        ns = parser.parse_args(["pr", "list", "--author", "alice", "--label", "bug", "--draft"])
        assert ns.author == "alice"
        assert ns.label == "bug"
        assert ns.draft is True

    def test_no_draft_flag(self):
        from gfo.cli import create_parser

        parser, _ = create_parser()
        ns = parser.parse_args(["pr", "list", "--no-draft"])
        assert ns.draft is False

    def test_default_draft_is_none(self):
        from gfo.cli import create_parser

        parser, _ = create_parser()
        ns = parser.parse_args(["pr", "list"])
        assert ns.draft is None


class TestHandleStatus:
    """pr status のテスト。"""

    @pytest.fixture
    def status_adapter(self, sample_pr):
        adapter = MagicMock()
        adapter.get_current_username.return_value = "test-user"
        adapter.list_pull_requests.return_value = [sample_pr]
        return adapter

    def test_calls_api_with_username(self, sample_config, status_adapter):
        args = make_args()
        with patch("gfo.commands.pr.get_adapter", return_value=status_adapter):
            pr_cmd.handle_status(args, fmt="table")

        status_adapter.get_current_username.assert_called_once()
        assert status_adapter.list_pull_requests.call_count == 2
        calls = status_adapter.list_pull_requests.call_args_list
        assert calls[0].kwargs == {"state": "open", "author": "test-user"}
        assert calls[1].kwargs == {"state": "open", "assignee": "test-user"}

    def test_table_output_has_sections(self, sample_config, status_adapter, capsys):
        args = make_args()
        with patch("gfo.commands.pr.get_adapter", return_value=status_adapter):
            pr_cmd.handle_status(args, fmt="table")

        captured = capsys.readouterr().out
        assert "Created by you" in captured
        assert "Assigned to you" in captured
        assert "Test PR" in captured

    def test_empty_sections(self, sample_config, capsys):
        adapter = MagicMock()
        adapter.get_current_username.return_value = "nobody"
        adapter.list_pull_requests.return_value = []
        args = make_args()
        with patch("gfo.commands.pr.get_adapter", return_value=adapter):
            pr_cmd.handle_status(args, fmt="table")

        captured = capsys.readouterr().out
        assert "No pull requests found." in captured

    def test_json_output(self, sample_config, status_adapter, capsys):
        args = make_args()
        with patch("gfo.commands.pr.get_adapter", return_value=status_adapter):
            pr_cmd.handle_status(args, fmt="json")

        import json

        captured = capsys.readouterr().out
        data = json.loads(captured)
        assert "created" in data
        assert "assigned" in data
        assert "review_requested" not in data
        assert len(data["created"]) == 1
        assert data["created"][0]["title"] == "Test PR"

    def test_error_propagates(self, sample_config):
        adapter = MagicMock()
        adapter.get_current_username.side_effect = NotFoundError()
        args = make_args()
        with (
            patch("gfo.commands.pr.get_adapter", return_value=adapter),
            pytest.raises(NotFoundError),
        ):
            pr_cmd.handle_status(args, fmt="table")


class TestHandleListMilestone:
    """pr list --milestone のテスト。"""

    def test_passes_milestone_to_adapter(self, sample_config, mock_adapter, capsys):
        args = make_args(state="open", limit=30, milestone="v1.0")
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_list(args, fmt="table")
        call_kwargs = mock_adapter.list_pull_requests.call_args.kwargs
        assert call_kwargs["milestone"] == "v1.0"

    def test_milestone_default_is_none(self, sample_config, mock_adapter, capsys):
        args = make_args(state="open", limit=30)
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_list(args, fmt="table")
        call_kwargs = mock_adapter.list_pull_requests.call_args.kwargs
        assert call_kwargs["milestone"] is None


class TestPrListMilestoneArgParsing:
    """pr list --milestone の CLI 引数パースのテスト。"""

    def test_milestone_parsed(self):
        from gfo.cli import create_parser

        parser, _ = create_parser()
        ns = parser.parse_args(["pr", "list", "--milestone", "v2.0"])
        assert ns.milestone == "v2.0"

    def test_milestone_short_flag(self):
        from gfo.cli import create_parser

        parser, _ = create_parser()
        ns = parser.parse_args(["pr", "list", "-m", "v2.0"])
        assert ns.milestone == "v2.0"

    def test_milestone_default_is_none(self):
        from gfo.cli import create_parser

        parser, _ = create_parser()
        ns = parser.parse_args(["pr", "list"])
        assert not hasattr(ns, "milestone") or ns.milestone is None


class TestHandleSubscribe:
    """pr subscribe / unsubscribe のテスト。"""

    def test_subscribe_calls_adapter(self):
        with patch_adapter("gfo.commands.pr") as adapter:
            args = make_args(number=42)
            pr_cmd.handle_subscribe(args, fmt="table")
        adapter.subscribe_pull_request.assert_called_once_with(42)

    def test_unsubscribe_calls_adapter(self):
        with patch_adapter("gfo.commands.pr") as adapter:
            args = make_args(number=42)
            pr_cmd.handle_unsubscribe(args, fmt="table")
        adapter.unsubscribe_pull_request.assert_called_once_with(42)

    def test_subscribe_prints_message(self, capsys):
        with patch_adapter("gfo.commands.pr"):
            args = make_args(number=7)
            pr_cmd.handle_subscribe(args, fmt="table")
        out = capsys.readouterr().out
        assert "7" in out

    def test_unsubscribe_prints_message(self, capsys):
        with patch_adapter("gfo.commands.pr"):
            args = make_args(number=7)
            pr_cmd.handle_unsubscribe(args, fmt="table")
        out = capsys.readouterr().out
        assert "7" in out

    def test_subscribe_error_propagates(self):
        with patch_adapter("gfo.commands.pr") as adapter:
            adapter.subscribe_pull_request.side_effect = NotFoundError("/pulls/999")
            args = make_args(number=999)
            with pytest.raises(NotFoundError):
                pr_cmd.handle_subscribe(args, fmt="table")


class TestPrSubscribeArgParsing:
    """pr subscribe / unsubscribe の CLI 引数パースのテスト。"""

    def test_subscribe_parsed(self):
        from gfo.cli import create_parser

        parser, _ = create_parser()
        ns = parser.parse_args(["pr", "subscribe", "42"])
        assert ns.subcommand == "subscribe"
        assert ns.number == 42

    def test_unsubscribe_parsed(self):
        from gfo.cli import create_parser

        parser, _ = create_parser()
        ns = parser.parse_args(["pr", "unsubscribe", "42"])
        assert ns.subcommand == "unsubscribe"
        assert ns.number == 42


class TestHandleCreateDryRun:
    """pr create --dry-run のテスト。"""

    def test_dry_run_does_not_call_api(self, sample_config, mock_adapter, capsys):
        args = make_args(
            head="feature/test",
            base="main",
            title="My PR",
            body="Description",
            draft=False,
            dry_run=True,
        )
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_create(args, fmt="table")
        mock_adapter.create_pull_request.assert_not_called()

    def test_dry_run_shows_title(self, sample_config, mock_adapter, capsys):
        args = make_args(
            head="feature/test",
            base="main",
            title="My PR",
            body="",
            draft=False,
            dry_run=True,
        )
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_create(args, fmt="table")
        out = capsys.readouterr().out
        assert "My PR" in out

    def test_dry_run_shows_branches(self, sample_config, mock_adapter, capsys):
        args = make_args(
            head="feature/test",
            base="main",
            title="My PR",
            body="",
            draft=False,
            dry_run=True,
        )
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_create(args, fmt="table")
        out = capsys.readouterr().out
        assert "feature/test" in out
        assert "main" in out

    def test_dry_run_shows_body(self, sample_config, mock_adapter, capsys):
        args = make_args(
            head="feature/test",
            base="main",
            title="My PR",
            body="Detailed description",
            draft=False,
            dry_run=True,
        )
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_create(args, fmt="table")
        out = capsys.readouterr().out
        assert "Detailed description" in out

    def test_dry_run_shows_draft(self, sample_config, mock_adapter, capsys):
        args = make_args(
            head="feature/test",
            base="main",
            title="My PR",
            body="",
            draft=True,
            dry_run=True,
        )
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_create(args, fmt="table")
        out = capsys.readouterr().out
        assert "Draft" in out

    def test_dry_run_json_format_still_shows_preview(self, sample_config, mock_adapter, capsys):
        """--dry-run + fmt=json でもプレビュー表示（JSON 出力にはならない）。"""
        args = make_args(
            head="feature/test",
            base="main",
            title="My PR",
            body="",
            draft=False,
            dry_run=True,
        )
        with _patch_all(sample_config, mock_adapter):
            pr_cmd.handle_create(args, fmt="json")
        mock_adapter.create_pull_request.assert_not_called()
        out = capsys.readouterr().out
        assert "My PR" in out


class TestHandleCreateWeb:
    """pr create --web のテスト。"""

    def test_opens_browser_after_create(self, sample_config, mock_adapter):
        args = make_args(
            head="feature/test",
            base="main",
            title="My PR",
            body="",
            draft=False,
            web=True,
        )
        with (
            _patch_all(sample_config, mock_adapter),
            patch("webbrowser.open") as mock_open,
        ):
            pr_cmd.handle_create(args, fmt="table")
        mock_adapter.create_pull_request.assert_called_once()
        mock_open.assert_called_once_with("https://github.com/test-owner/test-repo/pull/1")

    def test_does_not_open_browser_without_flag(self, sample_config, mock_adapter):
        args = make_args(
            head="feature/test",
            base="main",
            title="My PR",
            body="",
            draft=False,
        )
        with (
            _patch_all(sample_config, mock_adapter),
            patch("webbrowser.open") as mock_open,
        ):
            pr_cmd.handle_create(args, fmt="table")
        mock_open.assert_not_called()

    def test_dry_run_does_not_open_browser(self, sample_config, mock_adapter):
        args = make_args(
            head="feature/test",
            base="main",
            title="My PR",
            body="",
            draft=False,
            dry_run=True,
            web=True,
        )
        with (
            _patch_all(sample_config, mock_adapter),
            patch("webbrowser.open") as mock_open,
        ):
            pr_cmd.handle_create(args, fmt="table")
        mock_adapter.create_pull_request.assert_not_called()
        mock_open.assert_not_called()


class TestPrCreateWebArgParsing:
    """pr create --web の CLI 引数パースのテスト。"""

    def test_web_flag_parsed(self):
        from gfo.cli import create_parser

        parser, _ = create_parser()
        ns = parser.parse_args(["pr", "create", "--title", "Test", "--web"])
        assert ns.web is True

    def test_web_short_flag_parsed(self):
        from gfo.cli import create_parser

        parser, _ = create_parser()
        ns = parser.parse_args(["pr", "create", "--title", "Test", "-w"])
        assert ns.web is True

    def test_web_default_is_false(self):
        from gfo.cli import create_parser

        parser, _ = create_parser()
        ns = parser.parse_args(["pr", "create", "--title", "Test"])
        assert ns.web is False


class TestPrCreateDryRunArgParsing:
    """pr create --dry-run の CLI 引数パースのテスト。"""

    def test_dry_run_flag_parsed(self):
        from gfo.cli import create_parser

        parser, _ = create_parser()
        ns = parser.parse_args(["pr", "create", "--title", "Test", "--dry-run"])
        assert ns.dry_run is True

    def test_dry_run_default_is_false(self):
        from gfo.cli import create_parser

        parser, _ = create_parser()
        ns = parser.parse_args(["pr", "create", "--title", "Test"])
        assert ns.dry_run is False
