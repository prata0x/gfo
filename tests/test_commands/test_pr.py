"""gfo.commands.pr のテスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gfo.adapter.base import PullRequest
from gfo.commands import pr as pr_cmd
from tests.test_commands.conftest import make_args


@pytest.fixture
def mock_config():
    from gfo.config import ProjectConfig
    return ProjectConfig(
        service_type="github",
        host="github.com",
        api_url="https://api.github.com",
        owner="test-owner",
        repo="test-repo",
    )


@pytest.fixture
def sample_pr():
    return PullRequest(
        number=1,
        title="Test PR",
        body="Test body",
        state="open",
        author="test-user",
        source_branch="feature/test",
        target_branch="main",
        draft=False,
        url="https://github.com/test-owner/test-repo/pull/1",
        created_at="2024-01-01T00:00:00Z",
        updated_at=None,
    )


@pytest.fixture
def mock_adapter(sample_pr):
    adapter = MagicMock()
    adapter.list_pull_requests.return_value = [sample_pr]
    adapter.create_pull_request.return_value = sample_pr
    adapter.get_pull_request.return_value = sample_pr
    adapter.get_pr_checkout_refspec.return_value = "refs/pull/1/head"
    return adapter


def _patch_all(mock_config, mock_adapter):
    """resolve_project_config と create_adapter をまとめてパッチするコンテキスト。"""
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        with patch("gfo.commands.pr.resolve_project_config", return_value=mock_config), \
             patch("gfo.commands.pr.create_adapter", return_value=mock_adapter):
            yield

    return _ctx()


class TestHandleList:
    def test_calls_list_pull_requests(self, mock_config, mock_adapter, capsys):
        args = make_args(state="open", limit=30)
        with _patch_all(mock_config, mock_adapter):
            pr_cmd.handle_list(args, fmt="table")

        mock_adapter.list_pull_requests.assert_called_once_with(state="open", limit=30)

    def test_outputs_results(self, mock_config, mock_adapter, capsys):
        args = make_args(state="open", limit=30)
        with _patch_all(mock_config, mock_adapter):
            pr_cmd.handle_list(args, fmt="table")

        out = capsys.readouterr().out
        assert "Test PR" in out
        assert "open" in out

    def test_json_format(self, mock_config, mock_adapter, capsys):
        args = make_args(state="open", limit=10)
        with _patch_all(mock_config, mock_adapter):
            pr_cmd.handle_list(args, fmt="json")

        import json
        out = capsys.readouterr().out
        data = json.loads(out)
        # 1件リストは output.py が単一オブジェクトとして出力する
        if isinstance(data, list):
            assert data[0]["title"] == "Test PR"
        else:
            assert data["title"] == "Test PR"


class TestHandleCreate:
    def test_uses_provided_args(self, mock_config, mock_adapter, capsys):
        args = make_args(
            head="feature/test",
            base="main",
            title="My PR",
            body="Description",
            draft=False,
        )
        with _patch_all(mock_config, mock_adapter):
            pr_cmd.handle_create(args, fmt="table")

        mock_adapter.create_pull_request.assert_called_once_with(
            title="My PR",
            body="Description",
            base="main",
            head="feature/test",
            draft=False,
        )

    def test_infers_head_from_git(self, mock_config, mock_adapter, capsys):
        args = make_args(head=None, base="main", title="My PR", body="", draft=False)
        with _patch_all(mock_config, mock_adapter), \
             patch("gfo.commands.pr.gfo.git_util.get_current_branch", return_value="feature/auto"):
            pr_cmd.handle_create(args, fmt="table")

        call_kwargs = mock_adapter.create_pull_request.call_args.kwargs
        assert call_kwargs["head"] == "feature/auto"

    def test_infers_base_from_git(self, mock_config, mock_adapter, capsys):
        args = make_args(head="feature/x", base=None, title="My PR", body="", draft=False)
        with _patch_all(mock_config, mock_adapter), \
             patch("gfo.commands.pr.gfo.git_util.get_default_branch", return_value="develop"):
            pr_cmd.handle_create(args, fmt="table")

        call_kwargs = mock_adapter.create_pull_request.call_args.kwargs
        assert call_kwargs["base"] == "develop"

    def test_infers_title_from_last_commit(self, mock_config, mock_adapter, capsys):
        args = make_args(head="feature/x", base="main", title=None, body="", draft=False)
        with _patch_all(mock_config, mock_adapter), \
             patch("gfo.commands.pr.gfo.git_util.get_last_commit_subject", return_value="Auto commit title"):
            pr_cmd.handle_create(args, fmt="table")

        call_kwargs = mock_adapter.create_pull_request.call_args.kwargs
        assert call_kwargs["title"] == "Auto commit title"

    def test_draft_flag(self, mock_config, mock_adapter, capsys):
        args = make_args(head="feature/x", base="main", title="Draft", body="", draft=True)
        with _patch_all(mock_config, mock_adapter):
            pr_cmd.handle_create(args, fmt="table")

        call_kwargs = mock_adapter.create_pull_request.call_args.kwargs
        assert call_kwargs["draft"] is True


class TestHandleView:
    def test_calls_get_pull_request(self, mock_config, mock_adapter, capsys):
        args = make_args(number=1)
        with _patch_all(mock_config, mock_adapter):
            pr_cmd.handle_view(args, fmt="table")

        mock_adapter.get_pull_request.assert_called_once_with(1)

    def test_outputs_pr(self, mock_config, mock_adapter, capsys):
        args = make_args(number=1)
        with _patch_all(mock_config, mock_adapter):
            pr_cmd.handle_view(args, fmt="table")

        out = capsys.readouterr().out
        assert "Test PR" in out


class TestHandleMerge:
    def test_calls_merge_pull_request(self, mock_config, mock_adapter):
        args = make_args(number=1, method="merge")
        with _patch_all(mock_config, mock_adapter):
            pr_cmd.handle_merge(args, fmt="table")

        mock_adapter.merge_pull_request.assert_called_once_with(1, method="merge")

    def test_squash_method(self, mock_config, mock_adapter):
        args = make_args(number=2, method="squash")
        with _patch_all(mock_config, mock_adapter):
            pr_cmd.handle_merge(args, fmt="table")

        mock_adapter.merge_pull_request.assert_called_once_with(2, method="squash")


class TestHandleClose:
    def test_calls_close_pull_request(self, mock_config, mock_adapter):
        args = make_args(number=1)
        with _patch_all(mock_config, mock_adapter):
            pr_cmd.handle_close(args, fmt="table")

        mock_adapter.close_pull_request.assert_called_once_with(1)


class TestHandleCheckout:
    def test_fetches_and_checks_out(self, mock_config, mock_adapter):
        args = make_args(number=1)
        with _patch_all(mock_config, mock_adapter), \
             patch("gfo.commands.pr.gfo.git_util.git_fetch") as mock_fetch, \
             patch("gfo.commands.pr.gfo.git_util.git_checkout_new_branch") as mock_checkout:
            pr_cmd.handle_checkout(args, fmt="table")

        mock_adapter.get_pull_request.assert_called_once_with(1)
        mock_adapter.get_pr_checkout_refspec.assert_called_once()
        mock_fetch.assert_called_once_with("origin", "refs/pull/1/head")
        mock_checkout.assert_called_once_with("feature/test")
