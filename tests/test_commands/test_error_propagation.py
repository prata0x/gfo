"""エラーサブクラス（401/404/429/NetworkError）のコマンド層伝搬テスト。

既存のコマンドテストは HttpError(500) を生成して side_effect にすることが多く、
AuthenticationError / NotFoundError / RateLimitError / NetworkError の各サブクラスが
コマンドハンドラを通過して呼び出し元に伝搬することを確認していない。

コマンド層に「HttpError だけ捕まえて AuthError を握りつぶす」分岐が紛れ込んでも
検出できなかったため、代表的なハンドラに対しサブクラス分岐の伝搬を検証する。
"""

from __future__ import annotations

import pytest

from gfo.commands import label as label_cmd
from gfo.commands import pr as pr_cmd
from gfo.commands import repo as repo_cmd
from gfo.exceptions import (
    AuthenticationError,
    NetworkError,
    NotFoundError,
    RateLimitError,
    ServerError,
)

from .conftest import make_args, patch_adapter


def _error_cases():
    """サブクラス別のエラーインスタンスと期待される例外型のペア。"""
    return [
        pytest.param(AuthenticationError(401, "/x"), AuthenticationError, id="401"),
        pytest.param(NotFoundError("/x"), NotFoundError, id="404"),
        pytest.param(RateLimitError(60, "/x"), RateLimitError, id="429"),
        pytest.param(ServerError(500, "/x"), ServerError, id="500"),
        pytest.param(NetworkError("connection refused"), NetworkError, id="network"),
    ]


class TestPrListPropagation:
    @pytest.mark.parametrize("error,exc_class", _error_cases())
    def test_pr_list_propagates_error_subclass(self, error, exc_class):
        """pr list がアダプターのエラーサブクラスをそのまま伝搬すること。"""
        args = make_args(
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
            web=False,
        )
        with patch_adapter("gfo.commands.pr") as adapter:
            adapter.list_pull_requests.side_effect = error
            with pytest.raises(exc_class):
                pr_cmd.handle_list(args, fmt="table")


class TestRepoViewPropagation:
    @pytest.mark.parametrize("error,exc_class", _error_cases())
    def test_repo_view_propagates_error_subclass(self, error, exc_class):
        """repo view がアダプターのエラーサブクラスをそのまま伝搬すること。"""
        args = make_args(repo=None, web=False)
        with patch_adapter("gfo.commands.repo") as adapter:
            adapter.get_repository.side_effect = error
            with pytest.raises(exc_class):
                repo_cmd.handle_view(args, fmt="table")


class TestLabelListPropagation:
    @pytest.mark.parametrize("error,exc_class", _error_cases())
    def test_label_list_propagates_error_subclass(self, error, exc_class):
        """label list がアダプターのエラーサブクラスをそのまま伝搬すること。"""
        args = make_args(limit=30)
        with patch_adapter("gfo.commands.label") as adapter:
            adapter.list_labels.side_effect = error
            with pytest.raises(exc_class):
                label_cmd.handle_list(args, fmt="table")
