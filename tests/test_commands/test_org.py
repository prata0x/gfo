"""gfo.commands.org のテスト。"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from gfo.adapter.base import Organization, Repository
from gfo.commands import org as org_cmd
from gfo.exceptions import GfoError, HttpError
from tests.test_commands.conftest import make_args, patch_adapter

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


class TestHandleList:
    def test_calls_list_organizations(self, capsys):
        with patch_adapter("gfo.commands.org") as adapter:
            adapter.list_organizations.return_value = [SAMPLE_ORG]
            args = make_args(limit=30)
            org_cmd.handle_list(args, fmt="table")
        adapter.list_organizations.assert_called_once_with(limit=30)
        out = capsys.readouterr().out
        assert "my-org" in out

    def test_json_format(self, capsys):
        with patch_adapter("gfo.commands.org") as adapter:
            adapter.list_organizations.return_value = [SAMPLE_ORG]
            args = make_args(limit=30)
            org_cmd.handle_list(args, fmt="json")
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert isinstance(parsed, list)
        assert parsed[0]["name"] == "my-org"

    def test_error_propagation(self):
        """アダプターの HttpError がそのまま伝搬する。"""
        with patch_adapter("gfo.commands.org") as adapter:
            adapter.list_organizations.side_effect = HttpError(500, "Server error")
            args = make_args(limit=30)
            with pytest.raises(HttpError):
                org_cmd.handle_list(args, fmt="table")


class TestHandleView:
    def test_calls_get_organization(self, capsys):
        with patch_adapter("gfo.commands.org") as adapter:
            adapter.get_organization.return_value = SAMPLE_ORG
            args = make_args(name="my-org")
            org_cmd.handle_view(args, fmt="table")
        adapter.get_organization.assert_called_once_with("my-org")
        out = capsys.readouterr().out
        assert "my-org" in out

    def test_json_format(self, capsys):
        with patch_adapter("gfo.commands.org") as adapter:
            adapter.get_organization.return_value = SAMPLE_ORG
            args = make_args(name="my-org")
            org_cmd.handle_view(args, fmt="json")
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed[0]["name"] == "my-org"

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.org") as adapter:
            adapter.get_organization.side_effect = HttpError(404, "Not found")
            args = make_args(name="nope")
            with pytest.raises(HttpError):
                org_cmd.handle_view(args, fmt="table")


class TestHandleMembers:
    def test_calls_list_org_members(self, capsys):
        with patch_adapter("gfo.commands.org") as adapter:
            adapter.list_org_members.return_value = ["alice", "bob"]
            args = make_args(name="my-org", limit=30)
            org_cmd.handle_members(args, fmt="table")
        adapter.list_org_members.assert_called_once_with("my-org", limit=30)
        out = capsys.readouterr().out
        assert "alice" in out
        assert "bob" in out

    def test_json_format(self, capsys):
        with patch_adapter("gfo.commands.org") as adapter:
            adapter.list_org_members.return_value = ["alice", "bob"]
            args = make_args(name="my-org", limit=30)
            org_cmd.handle_members(args, fmt="json")
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed == ["alice", "bob"]

    def test_jq_filter(self, capsys):
        """jq 引数指定時に apply_jq_filter が呼ばれる。"""
        with patch_adapter("gfo.commands.org") as adapter:
            adapter.list_org_members.return_value = ["alice", "bob"]
            args = make_args(name="my-org", limit=30)
            with patch("gfo.commands.org.apply_jq_filter", return_value='"alice"') as mock_jq:
                org_cmd.handle_members(args, fmt="json", jq=".[0]")
            mock_jq.assert_called_once()
            out = capsys.readouterr().out
            assert "alice" in out

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.org") as adapter:
            adapter.list_org_members.side_effect = GfoError("forbidden")
            args = make_args(name="my-org", limit=30)
            with pytest.raises(GfoError, match="forbidden"):
                org_cmd.handle_members(args, fmt="table")


class TestHandleRepos:
    def test_calls_list_org_repos(self, capsys):
        with patch_adapter("gfo.commands.org") as adapter:
            adapter.list_org_repos.return_value = [SAMPLE_REPO]
            args = make_args(name="my-org", limit=30)
            org_cmd.handle_repos(args, fmt="table")
        adapter.list_org_repos.assert_called_once_with("my-org", limit=30)
        out = capsys.readouterr().out
        assert "repo1" in out

    def test_json_format(self, capsys):
        with patch_adapter("gfo.commands.org") as adapter:
            adapter.list_org_repos.return_value = [SAMPLE_REPO]
            args = make_args(name="my-org", limit=30)
            org_cmd.handle_repos(args, fmt="json")
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert isinstance(parsed, list)
        assert parsed[0]["name"] == "repo1"


class TestHandleCreate:
    def test_calls_create_organization(self, capsys):
        with patch_adapter("gfo.commands.org") as adapter:
            adapter.create_organization.return_value = SAMPLE_ORG
            args = make_args(name="my-org", display_name=None, description=None)
            org_cmd.handle_create(args, fmt="table")
        adapter.create_organization.assert_called_once_with(
            "my-org", display_name=None, description=None
        )
        out = capsys.readouterr().out
        assert "my-org" in out

    def test_with_display_name_and_description(self, capsys):
        with patch_adapter("gfo.commands.org") as adapter:
            adapter.create_organization.return_value = SAMPLE_ORG
            args = make_args(name="my-org", display_name="My Org", description="desc")
            org_cmd.handle_create(args, fmt="table")
        adapter.create_organization.assert_called_once_with(
            "my-org", display_name="My Org", description="desc"
        )

    def test_json_format(self, capsys):
        with patch_adapter("gfo.commands.org") as adapter:
            adapter.create_organization.return_value = SAMPLE_ORG
            args = make_args(name="my-org", display_name=None, description=None)
            org_cmd.handle_create(args, fmt="json")
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed[0]["name"] == "my-org"

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.org") as adapter:
            adapter.create_organization.side_effect = HttpError(422, "Validation error")
            args = make_args(name="bad", display_name=None, description=None)
            with pytest.raises(HttpError):
                org_cmd.handle_create(args, fmt="table")


class TestHandleDelete:
    def test_calls_delete_organization_with_yes(self, capsys):
        with patch_adapter("gfo.commands.org") as adapter:
            args = make_args(name="my-org", yes=True)
            org_cmd.handle_delete(args, fmt="table")
        adapter.delete_organization.assert_called_once_with("my-org")
        out = capsys.readouterr().out
        assert "my-org" in out

    def test_confirmation_prompt_accepted(self, capsys):
        with patch_adapter("gfo.commands.org") as adapter:
            args = make_args(name="my-org", yes=False)
            with patch("builtins.input", return_value="y"):
                org_cmd.handle_delete(args, fmt="table")
        adapter.delete_organization.assert_called_once_with("my-org")

    def test_confirmation_prompt_rejected(self, capsys):
        with patch_adapter("gfo.commands.org") as adapter:
            args = make_args(name="my-org", yes=False)
            with patch("builtins.input", return_value="n"):
                org_cmd.handle_delete(args, fmt="table")
        adapter.delete_organization.assert_not_called()
        out = capsys.readouterr().out
        assert "Aborted" in out

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.org") as adapter:
            adapter.delete_organization.side_effect = HttpError(403, "Forbidden")
            args = make_args(name="my-org", yes=True)
            with pytest.raises(HttpError):
                org_cmd.handle_delete(args, fmt="table")
