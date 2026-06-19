"""テスト共通フィクスチャ。"""

from __future__ import annotations

import os

# gfo.i18n はモジュールロード時に LANGUAGE を参照するため、
# gfo モジュールの import より前にセットする必要がある。
os.environ.setdefault("LANGUAGE", "C")

from pathlib import Path
from unittest.mock import patch

import pytest

from gfo.adapter.base import GitServiceAdapter


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """一時的な設定ディレクトリ。config.py の get_config_dir() をパッチする。"""
    d = tmp_path / "gfo_config"
    d.mkdir()
    with patch("gfo.config.get_config_dir", return_value=d):
        yield d


class StubAdapter(GitServiceAdapter):
    """全抽象メソッドを最小スタブ実装した具象サブクラス（テスト共通）。

    base.py のデフォルト実装（delete_*, get_pr_checkout_refspec, add_topic 等）や
    ABC 規約の検証に使う。`base.py` のシグネチャ変更時はここ 1 箇所だけ直せばよい。
    `tests/test_adapter_base.py` と `tests/test_adapters/test_base.py` の両方が import する。
    """

    service_name = "stub"

    def list_pull_requests(self, *, state="open", limit=30):
        return []

    def create_pull_request(self, *, title, body="", base, head, draft=False):
        return None  # type: ignore[return-value]

    def get_pull_request(self, number):
        return None  # type: ignore[return-value]

    def merge_pull_request(self, number, *, method="merge", title=None, message=None):
        return None

    def close_pull_request(self, number):
        return None

    def list_issues(self, *, state="open", assignee=None, label=None, limit=30):
        return []

    def create_issue(self, *, title, body="", assignee=None, label=None, **kwargs):
        return None  # type: ignore[return-value]

    def get_issue(self, number):
        return None  # type: ignore[return-value]

    def close_issue(self, number):
        return None

    def list_repositories(self, *, owner=None, limit=30):
        return []

    def create_repository(self, *, name, visibility="public", description=""):
        return None  # type: ignore[return-value]

    def get_repository(self, owner=None, name=None):
        return None  # type: ignore[return-value]

    def list_releases(self, *, limit=30):
        return []

    def create_release(self, *, tag, title="", notes="", draft=False, prerelease=False):
        return None  # type: ignore[return-value]

    def list_labels(self, *, limit=0):
        return []

    def create_label(self, *, name, color=None, description=None):
        return None  # type: ignore[return-value]

    def list_milestones(self, *, limit=0):
        return []

    def create_milestone(self, *, title, description=None, due_date=None):
        return None  # type: ignore[return-value]

    def list_comments(self, resource, number, *, limit=30):
        return []

    def create_comment(self, resource, number, *, body):
        return None  # type: ignore[return-value]

    def update_pull_request(self, number, *, title=None, body=None, base=None):
        return None  # type: ignore[return-value]

    def update_issue(self, number, *, title=None, body=None, assignee=None, label=None):
        return None  # type: ignore[return-value]

    def list_branches(self, *, limit=30):
        return []

    def create_branch(self, *, name, ref):
        return None  # type: ignore[return-value]


@pytest.fixture
def make_stub_adapter():
    """StubAdapter のインスタンスを生成するファクトリ。"""

    def _make(*, client=None, owner="o", repo="r"):
        return StubAdapter(client=client, owner=owner, repo=repo)

    return _make
