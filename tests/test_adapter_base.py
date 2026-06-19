from __future__ import annotations

import dataclasses
from unittest.mock import MagicMock

import pytest

from gfo.adapter.base import (
    GitHubLikeAdapter,
    GitServiceAdapter,
    Issue,
    Label,
    Milestone,
    PullRequest,
    Release,
    Repository,
)
from gfo.exceptions import NotSupportedError


class TestPullRequest:
    def test_create(self):
        pr = PullRequest(
            number=1,
            title="feat: add login",
            body="Implements login flow",
            state="open",
            author="alice",
            source_branch="feat/login",
            target_branch="main",
            draft=False,
            url="https://example.com/pr/1",
            created_at="2026-01-01T00:00:00Z",
            updated_at=None,
        )
        assert pr.number == 1
        assert pr.title == "feat: add login"
        assert pr.updated_at is None

    def test_updated_at_defaults_to_none(self):
        """updated_at を省略すると None になる（Issue との一貫性、R36-02）。"""
        pr = PullRequest(
            number=2,
            title="fix: bug",
            body=None,
            state="open",
            author="bob",
            source_branch="fix/bug",
            target_branch="main",
            draft=False,
            url="https://example.com/pr/2",
            created_at="2026-01-02T00:00:00Z",
        )
        assert pr.updated_at is None

    def test_frozen(self):
        pr = PullRequest(
            number=1,
            title="t",
            body=None,
            state="open",
            author="a",
            source_branch="b",
            target_branch="main",
            draft=False,
            url="u",
            created_at="c",
            updated_at=None,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            pr.title = "changed"  # type: ignore[misc]


class TestIssue:
    def test_create(self):
        issue = Issue(
            number=42,
            title="Bug report",
            body=None,
            state="open",
            author="bob",
            assignees=["alice"],
            labels=["bug", "high"],
            url="https://example.com/issue/42",
            created_at="2026-01-01T00:00:00Z",
        )
        assert issue.number == 42
        assert issue.labels == ["bug", "high"]
        assert issue.body is None

    def test_frozen(self):
        issue = Issue(
            number=1,
            title="t",
            body=None,
            state="open",
            author="a",
            assignees=[],
            labels=[],
            url="u",
            created_at="c",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            issue.state = "closed"  # type: ignore[misc]


class TestGitHubLikeAdapterToIssue:
    """GitHubLikeAdapter._to_issue() の変換テスト。"""

    _ISSUE_DATA = {
        "number": 10,
        "title": "Fix bug",
        "body": "Details",
        "state": "open",
        "user": {"login": "alice"},
        "assignees": [],
        "labels": [],
        "html_url": "https://github.com/org/repo/issues/10",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-02-01T00:00:00Z",
    }

    def test_updated_at_is_set(self):
        """_to_issue() が API レスポンスの updated_at を設定する（R37-01）。"""
        issue = GitHubLikeAdapter._to_issue(self._ISSUE_DATA)
        assert issue.updated_at == "2026-02-01T00:00:00Z"

    def test_updated_at_missing_becomes_none(self):
        """_to_issue() が updated_at なしのレスポンスで None を設定する（R37-01）。"""
        data = {k: v for k, v in self._ISSUE_DATA.items() if k != "updated_at"}
        issue = GitHubLikeAdapter._to_issue(data)
        assert issue.updated_at is None

    def test_basic_fields(self):
        """_to_issue() が基本フィールドを正しく変換する。"""
        issue = GitHubLikeAdapter._to_issue(self._ISSUE_DATA)
        assert issue.number == 10
        assert issue.title == "Fix bug"
        assert issue.author == "alice"
        assert issue.state == "open"


class TestRepository:
    def test_create(self):
        repo = Repository(
            name="gfo",
            full_name="owner/gfo",
            description="A tool",
            visibility="public",
            default_branch="main",
            clone_url="https://example.com/gfo.git",
            url="https://example.com/gfo",
        )
        assert repo.full_name == "owner/gfo"
        assert repo.visibility == "public"

    def test_optional_fields(self):
        repo = Repository(
            name="gfo",
            full_name="owner/gfo",
            description=None,
            visibility="private",
            default_branch=None,
            clone_url="https://example.com/gfo.git",
            url="https://example.com/gfo",
        )
        assert repo.description is None
        assert repo.default_branch is None

    def test_frozen(self):
        repo = Repository(
            name="gfo",
            full_name="owner/gfo",
            description=None,
            visibility="public",
            default_branch="main",
            clone_url="c",
            url="u",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            repo.name = "other"  # type: ignore[misc]


class TestRelease:
    def test_create(self):
        release = Release(
            tag="v1.0.0",
            title="Release 1.0.0",
            body="First release",
            draft=False,
            prerelease=False,
            url="https://example.com/release/v1.0.0",
            created_at="2026-01-01T00:00:00Z",
        )
        assert release.tag == "v1.0.0"
        assert release.draft is False

    def test_frozen(self):
        release = Release(
            tag="v1.0.0",
            title="t",
            body=None,
            draft=False,
            prerelease=False,
            url="u",
            created_at="c",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            release.tag = "v2.0.0"  # type: ignore[misc]


class TestLabel:
    def test_create(self):
        label = Label(name="bug", color="ff0000", description="Bug report")
        assert label.name == "bug"
        assert label.color == "ff0000"

    def test_optional_fields(self):
        label = Label(name="bug", color=None, description=None)
        assert label.color is None
        assert label.description is None

    def test_frozen(self):
        label = Label(name="bug", color=None, description=None)
        with pytest.raises(dataclasses.FrozenInstanceError):
            label.name = "feature"  # type: ignore[misc]


class TestGitServiceAdapterDeleteDefaults:
    """delete デフォルト実装が NotSupportedError を送出することを確認する。"""

    def _make_adapter(self):
        """抽象メソッドを最小限に実装したコンクリートサブクラスのインスタンスを返す。"""

        class MinimalAdapter(GitServiceAdapter):
            service_name = "TestService"

            def list_pull_requests(self, *, state="open", limit=30):
                return []

            def create_pull_request(self, *, title, body="", base, head, draft=False): ...
            def get_pull_request(self, number): ...
            def merge_pull_request(self, number, *, method="merge", title=None, message=None): ...
            def close_pull_request(self, number): ...
            def list_issues(self, *, state="open", assignee=None, label=None, limit=30):
                return []

            def create_issue(self, *, title, body="", assignee=None, label=None, **kwargs): ...
            def get_issue(self, number): ...
            def close_issue(self, number): ...
            def list_repositories(self, *, owner=None, limit=30):
                return []

            def create_repository(self, *, name, visibility="public", description=""): ...
            def get_repository(self, owner=None, name=None): ...
            def list_releases(self, *, limit=30):
                return []

            def create_release(self, *, tag, title="", notes="", draft=False, prerelease=False): ...
            def list_labels(self, *, limit=0):
                return []

            def create_label(self, *, name, color=None, description=None): ...
            def list_milestones(self, *, limit=0):
                return []

            def create_milestone(self, *, title, description=None, due_date=None): ...

            # Phase 1+ 追加抽象メソッドのスタブ
            def list_comments(self, resource, number, *, limit=30):
                return []

            def create_comment(self, resource, number, *, body): ...

            def update_pull_request(self, number, *, title=None, body=None, base=None): ...

            def update_issue(self, number, *, title=None, body=None, assignee=None, label=None): ...

            def list_branches(self, *, limit=30):
                return []

            def create_branch(self, *, name, ref): ...

        return MinimalAdapter(MagicMock(), "owner", "repo")

    def test_delete_issue_raises_not_supported(self):
        adapter = self._make_adapter()
        with pytest.raises(NotSupportedError):
            adapter.delete_issue(1)

    def test_delete_release_raises_not_supported(self):
        adapter = self._make_adapter()
        with pytest.raises(NotSupportedError):
            adapter.delete_release(tag="v1.0")

    def test_delete_label_raises_not_supported(self):
        adapter = self._make_adapter()
        with pytest.raises(NotSupportedError):
            adapter.delete_label(name="bug")

    def test_delete_milestone_raises_not_supported(self):
        adapter = self._make_adapter()
        with pytest.raises(NotSupportedError):
            adapter.delete_milestone(number=1)

    def test_delete_repository_raises_not_supported(self):
        adapter = self._make_adapter()
        with pytest.raises(NotSupportedError):
            adapter.delete_repository()


class TestMilestone:
    def test_create(self):
        ms = Milestone(
            number=1,
            title="v1.0",
            description="First milestone",
            state="open",
            due_date="2026-06-01",
        )
        assert ms.number == 1
        assert ms.title == "v1.0"

    def test_optional_fields(self):
        ms = Milestone(
            number=2,
            title="v2.0",
            description=None,
            state="closed",
            due_date=None,
        )
        assert ms.description is None
        assert ms.due_date is None

    def test_frozen(self):
        ms = Milestone(number=1, title="v1.0", description=None, state="open", due_date=None)
        with pytest.raises(dataclasses.FrozenInstanceError):
            ms.state = "closed"  # type: ignore[misc]


class TestGetCurrentUsername:
    """get_current_username() の変換テスト。"""

    def _make_adapter(self, user_data: dict):
        """get_current_user を差し替えたアダプターを返す。"""
        adapter = TestGitServiceAdapterDeleteDefaults()._make_adapter()
        adapter.get_current_user = lambda: user_data
        return adapter

    def test_login_key(self):
        adapter = self._make_adapter({"login": "alice"})
        assert adapter.get_current_username() == "alice"

    def test_username_key(self):
        adapter = self._make_adapter({"username": "bob"})
        assert adapter.get_current_username() == "bob"

    def test_nickname_key(self):
        adapter = self._make_adapter({"nickname": "charlie"})
        assert adapter.get_current_username() == "charlie"

    def test_userid_key(self):
        adapter = self._make_adapter({"userId": "dave123"})
        assert adapter.get_current_username() == "dave123"

    def test_no_matching_key_raises(self):
        from gfo.exceptions import GfoError

        adapter = self._make_adapter({"id": 42})
        with pytest.raises(GfoError, match="Cannot determine username"):
            adapter.get_current_username()

    def test_priority_order(self):
        """login が最優先で、他のキーより先にチェックされることを確認。"""
        adapter = self._make_adapter({"login": "first", "username": "second"})
        assert adapter.get_current_username() == "first"


class TestDefaultTopicMethods:
    """add_topic / remove_topic のデフォルト実装（list_topics + set_topics）の分岐。

    override 版（github/gitea/gitlab）はテスト済みだが、base.py のデフォルト実装の
    early-return 分岐（既存 topic を add / 不在 topic を remove）が未到達のため埋める。
    """

    def _make_adapter(self, current_topics: list[str]):
        adapter = TestGitServiceAdapterDeleteDefaults()._make_adapter()
        adapter.list_topics = lambda: list(current_topics)
        adapter.set_topics = MagicMock(side_effect=lambda topics: topics)
        return adapter

    def test_add_topic_appends_when_absent(self):
        adapter = self._make_adapter(["a", "b"])
        result = adapter.add_topic("c")
        assert result == ["a", "b", "c"]
        adapter.set_topics.assert_called_once_with(["a", "b", "c"])

    def test_add_topic_noop_when_present(self):
        """既存 topic を add すると set_topics を呼ばず現状を返す（early-return）。"""
        adapter = self._make_adapter(["a", "b"])
        result = adapter.add_topic("a")
        assert result == ["a", "b"]
        adapter.set_topics.assert_not_called()

    def test_remove_topic_removes_when_present(self):
        adapter = self._make_adapter(["a", "b"])
        result = adapter.remove_topic("a")
        assert result == ["b"]
        adapter.set_topics.assert_called_once_with(["b"])

    def test_remove_topic_noop_when_absent(self):
        """不在 topic を remove すると set_topics を呼ばず現状を返す（early-return）。"""
        adapter = self._make_adapter(["a", "b"])
        result = adapter.remove_topic("c")
        assert result == ["a", "b"]
        adapter.set_topics.assert_not_called()


class TestResolveMilestoneIdByTitle:
    """_resolve_milestone_id_by_title のデフォルト実装（list_milestones ループ）。"""

    def _make_adapter(self, milestones: list[Milestone]):
        adapter = TestGitServiceAdapterDeleteDefaults()._make_adapter()
        adapter.list_milestones = lambda *, limit=0: milestones
        return adapter

    def test_found_returns_number(self):
        adapter = self._make_adapter(
            [
                Milestone(number=3, title="v1.0", description=None, state="open", due_date=None),
                Milestone(number=7, title="v2.0", description=None, state="open", due_date=None),
            ]
        )
        assert adapter._resolve_milestone_id_by_title("v2.0") == 7

    def test_not_found_raises(self):
        from gfo.exceptions import GfoError

        adapter = self._make_adapter([])
        with pytest.raises(GfoError, match="Milestone not found"):
            adapter._resolve_milestone_id_by_title("nope")
