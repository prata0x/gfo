"""gfo.commands.pr のテスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gfo.adapter.base import PullRequest
from gfo.commands import pr as pr_cmd
from gfo.exceptions import ConfigError, NotFoundError
from tests.test_commands.conftest import make_args


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
        # 1件リストは output.py が単一オブジェクトとして出力する
        if isinstance(data, list):
            assert data[0]["title"] == "Test PR"
        else:
            assert data["title"] == "Test PR"

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
        with _patch_all(sample_config, mock_adapter), \
             patch("gfo.commands.pr.gfo.git_util.get_current_branch", return_value="feature/auto"):
            pr_cmd.handle_create(args, fmt="table")

        call_kwargs = mock_adapter.create_pull_request.call_args.kwargs
        assert call_kwargs["head"] == "feature/auto"

    def test_infers_base_from_git(self, sample_config, mock_adapter, capsys):
        args = make_args(head="feature/x", base=None, title="My PR", body="", draft=False)
        with _patch_all(sample_config, mock_adapter), \
             patch("gfo.commands.pr.gfo.git_util.get_default_branch", return_value="develop"):
            pr_cmd.handle_create(args, fmt="table")

        call_kwargs = mock_adapter.create_pull_request.call_args.kwargs
        assert call_kwargs["base"] == "develop"

    def test_infers_title_from_last_commit(self, sample_config, mock_adapter, capsys):
        args = make_args(head="feature/x", base="main", title=None, body="", draft=False)
        with _patch_all(sample_config, mock_adapter), \
             patch("gfo.commands.pr.gfo.git_util.get_last_commit_subject", return_value="Auto commit title"):
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
        with _patch_all(sample_config, mock_adapter), \
             patch("gfo.commands.pr.gfo.git_util.get_last_commit_subject", return_value=""), \
             pytest.raises(ConfigError, match="Could not determine PR title"):
            pr_cmd.handle_create(args, fmt="table")

    def test_whitespace_title_raises_config_error(self, sample_config, mock_adapter):
        """title が空白のみの場合は ConfigError を送出する。"""
        args = make_args(head="feature/x", base="main", title="   ", body="", draft=False)
        with _patch_all(sample_config, mock_adapter), \
             pytest.raises(ConfigError, match="Could not determine PR title"):
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


class TestHandleCheckout:
    def test_fetches_and_checks_out(self, sample_config, mock_adapter):
        args = make_args(number=1)
        with _patch_all(sample_config, mock_adapter), \
             patch("gfo.commands.pr.gfo.git_util.git_fetch") as mock_fetch, \
             patch("gfo.commands.pr.gfo.git_util.git_checkout_branch") as mock_checkout:
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
        with _patch_all(sample_config, mock_adapter), \
             patch("gfo.commands.pr.gfo.git_util.git_fetch",
                   side_effect=subprocess.CalledProcessError(1, "git")):
            with pytest.raises(subprocess.CalledProcessError):
                pr_cmd.handle_checkout(args, fmt="table")


def test_pr_list_config_error(capsys):
    """resolve_project_config が ConfigError を投げた場合に CLI で exit code 1 になる。"""
    from gfo.cli import main

    with patch("gfo.commands.pr.get_adapter",
               side_effect=ConfigError("not configured")):
        result = main(["pr", "list"])

    assert result == 1
    assert "not configured" in capsys.readouterr().err
