"""gfo.commands.search のテスト。"""

from __future__ import annotations

from gfo.adapter.base import Issue, Repository
from gfo.commands import search as search_cmd
from tests.test_commands.conftest import make_args, patch_adapter

SAMPLE_REPO = Repository(
    name="test-repo",
    full_name="owner/test-repo",
    description="A test",
    private=False,
    default_branch="main",
    clone_url="https://github.com/owner/test-repo.git",
    url="https://github.com/owner/test-repo",
)

SAMPLE_ISSUE = Issue(
    number=1,
    title="Found Issue",
    body="body",
    state="open",
    author="user",
    assignees=[],
    labels=[],
    url="",
    created_at="2024-01-01T00:00:00Z",
)


class TestHandleRepos:
    def test_calls_search_repositories(self, capsys):
        with patch_adapter("gfo.commands.search") as adapter:
            adapter.search_repositories.return_value = [SAMPLE_REPO]
            args = make_args(query="test", limit=10)
            search_cmd.handle_repos(args, fmt="table")
        adapter.search_repositories.assert_called_once_with("test", limit=10)


class TestHandleIssues:
    def test_calls_search_issues(self, capsys):
        with patch_adapter("gfo.commands.search") as adapter:
            adapter.search_issues.return_value = [SAMPLE_ISSUE]
            args = make_args(query="bug", limit=20)
            search_cmd.handle_issues(args, fmt="table")
        adapter.search_issues.assert_called_once_with("bug", limit=20)
