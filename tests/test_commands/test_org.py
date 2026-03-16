"""gfo.commands.org のテスト。"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from gfo.adapter.base import Organization, Repository
from gfo.commands import org as org_cmd
from tests.test_commands.conftest import make_args

SAMPLE_ORG = Organization(
    name="my-org",
    display_name="My Organization",
    description="An org",
    url="https://github.com/my-org",
)

SAMPLE_REPO = Repository(
    name="repo1",
    full_name="my-org/repo1",
    description="",
    private=False,
    default_branch="main",
    clone_url="https://github.com/my-org/repo1.git",
    url="https://github.com/my-org/repo1",
)


def _patch(adapter):
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        with patch("gfo.commands.org.get_adapter", return_value=adapter):
            yield

    return _ctx()


class TestHandleList:
    def test_calls_list_organizations(self, capsys):
        adapter = MagicMock()
        adapter.list_organizations.return_value = [SAMPLE_ORG]
        args = make_args(limit=30)
        with _patch(adapter):
            org_cmd.handle_list(args, fmt="table")
        adapter.list_organizations.assert_called_once_with(limit=30)
        out = capsys.readouterr().out
        assert "my-org" in out


class TestHandleView:
    def test_calls_get_organization(self, capsys):
        adapter = MagicMock()
        adapter.get_organization.return_value = SAMPLE_ORG
        args = make_args(name="my-org")
        with _patch(adapter):
            org_cmd.handle_view(args, fmt="table")
        adapter.get_organization.assert_called_once_with("my-org")
        out = capsys.readouterr().out
        assert "my-org" in out


class TestHandleMembers:
    def test_calls_list_org_members(self, capsys):
        adapter = MagicMock()
        adapter.list_org_members.return_value = ["alice", "bob"]
        args = make_args(name="my-org", limit=30)
        with _patch(adapter):
            org_cmd.handle_members(args, fmt="table")
        adapter.list_org_members.assert_called_once_with("my-org", limit=30)
        out = capsys.readouterr().out
        assert "alice" in out
        assert "bob" in out

    def test_json_format(self, capsys):
        adapter = MagicMock()
        adapter.list_org_members.return_value = ["alice", "bob"]
        args = make_args(name="my-org", limit=30)
        with _patch(adapter):
            org_cmd.handle_members(args, fmt="json")
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed == ["alice", "bob"]


class TestHandleRepos:
    def test_calls_list_org_repos(self, capsys):
        adapter = MagicMock()
        adapter.list_org_repos.return_value = [SAMPLE_REPO]
        args = make_args(name="my-org", limit=30)
        with _patch(adapter):
            org_cmd.handle_repos(args, fmt="table")
        adapter.list_org_repos.assert_called_once_with("my-org", limit=30)
        out = capsys.readouterr().out
        assert "repo1" in out
