"""gfo.commands.search のテスト。"""

from __future__ import annotations

from gfo.adapter.base import Commit, Issue, PullRequest, Repository
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


# --- Phase 5: search prs / search commits ---

SAMPLE_PR = PullRequest(
    number=1,
    title="Found PR",
    body="body",
    state="open",
    author="user",
    source_branch="feature",
    target_branch="main",
    draft=False,
    url="",
    created_at="2024-01-01T00:00:00Z",
)

SAMPLE_COMMIT = Commit(
    sha="abc123",
    message="fix bug",
    author="user",
    url="https://example.com/commit/abc123",
    created_at="2024-01-01T00:00:00Z",
)


class TestHandlePrs:
    def test_calls_search_pull_requests(self, capsys):
        with patch_adapter("gfo.commands.search") as adapter:
            adapter.search_pull_requests.return_value = [SAMPLE_PR]
            args = make_args(query="bug", state=None, limit=30)
            search_cmd.handle_prs(args, fmt="table")
        adapter.search_pull_requests.assert_called_once_with("bug", state=None, limit=30)


class TestHandleCommits:
    def test_calls_search_commits(self, capsys):
        with patch_adapter("gfo.commands.search") as adapter:
            adapter.search_commits.return_value = [SAMPLE_COMMIT]
            args = make_args(query="fix", author=None, since=None, until=None, limit=30)
            search_cmd.handle_commits(args, fmt="table")
        adapter.search_commits.assert_called_once_with(
            "fix", author=None, since=None, until=None, limit=30
        )
