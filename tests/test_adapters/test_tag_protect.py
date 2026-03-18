"""全アダプターの TagProtection テスト。"""

from __future__ import annotations

import json

import pytest
import responses

from gfo.exceptions import AuthenticationError, NotFoundError, NotSupportedError

# --- GitHub ---


class TestGitHubTagProtect:
    @responses.activate
    def test_list(self, github_adapter):
        responses.add(
            responses.GET,
            "https://api.github.com/repos/test-owner/test-repo/tags/protection",
            json=[{"id": 1, "pattern": "v*"}],
        )
        tps = github_adapter.list_tag_protections()
        assert len(tps) == 1
        assert tps[0].id == 1
        assert tps[0].pattern == "v*"
        assert tps[0].create_access_level == ""

    @responses.activate
    def test_create(self, github_adapter):
        responses.add(
            responses.POST,
            "https://api.github.com/repos/test-owner/test-repo/tags/protection",
            json={"id": 2, "pattern": "release-*"},
            status=201,
        )
        tp = github_adapter.create_tag_protection("release-*")
        assert tp.id == 2
        assert tp.pattern == "release-*"
        req_body = json.loads(responses.calls[0].request.body)
        assert req_body["pattern"] == "release-*"

    @responses.activate
    def test_delete(self, github_adapter):
        responses.add(
            responses.DELETE,
            "https://api.github.com/repos/test-owner/test-repo/tags/protection/1",
            status=204,
        )
        github_adapter.delete_tag_protection(1)

    @responses.activate
    def test_list_empty(self, github_adapter):
        responses.add(
            responses.GET,
            "https://api.github.com/repos/test-owner/test-repo/tags/protection",
            json=[],
        )
        assert github_adapter.list_tag_protections() == []

    @responses.activate
    def test_list_404(self, github_adapter):
        responses.add(
            responses.GET,
            "https://api.github.com/repos/test-owner/test-repo/tags/protection",
            status=404,
        )
        with pytest.raises(NotFoundError):
            github_adapter.list_tag_protections()

    @responses.activate
    def test_delete_403(self, github_adapter):
        responses.add(
            responses.DELETE,
            "https://api.github.com/repos/test-owner/test-repo/tags/protection/1",
            status=403,
        )
        with pytest.raises(AuthenticationError):
            github_adapter.delete_tag_protection(1)


# --- GitLab ---


class TestGitLabTagProtect:
    @responses.activate
    def test_list(self, gitlab_adapter):
        responses.add(
            responses.GET,
            "https://gitlab.com/api/v4/projects/test-owner%2Ftest-repo/protected_tags",
            json=[
                {
                    "name": "v*",
                    "create_access_levels": [{"access_level": 40}],
                }
            ],
        )
        tps = gitlab_adapter.list_tag_protections()
        assert len(tps) == 1
        assert tps[0].id == "v*"
        assert tps[0].pattern == "v*"
        assert tps[0].create_access_level == "40"

    @responses.activate
    def test_create(self, gitlab_adapter):
        responses.add(
            responses.POST,
            "https://gitlab.com/api/v4/projects/test-owner%2Ftest-repo/protected_tags",
            json={
                "name": "release-*",
                "create_access_levels": [{"access_level": 30}],
            },
            status=201,
        )
        tp = gitlab_adapter.create_tag_protection("release-*", create_access_level="30")
        assert tp.pattern == "release-*"
        assert tp.create_access_level == "30"
        req_body = json.loads(responses.calls[0].request.body)
        assert req_body["name"] == "release-*"
        assert req_body["create_access_level"] == "30"

    @responses.activate
    def test_delete(self, gitlab_adapter):
        responses.add(
            responses.DELETE,
            "https://gitlab.com/api/v4/projects/test-owner%2Ftest-repo/protected_tags/v%2A",
            status=204,
        )
        gitlab_adapter.delete_tag_protection("v*")

    @responses.activate
    def test_list_empty(self, gitlab_adapter):
        responses.add(
            responses.GET,
            "https://gitlab.com/api/v4/projects/test-owner%2Ftest-repo/protected_tags",
            json=[],
        )
        assert gitlab_adapter.list_tag_protections() == []

    @responses.activate
    def test_list_404(self, gitlab_adapter):
        responses.add(
            responses.GET,
            "https://gitlab.com/api/v4/projects/test-owner%2Ftest-repo/protected_tags",
            status=404,
        )
        with pytest.raises(NotFoundError):
            gitlab_adapter.list_tag_protections()

    @responses.activate
    def test_delete_403(self, gitlab_adapter):
        responses.add(
            responses.DELETE,
            "https://gitlab.com/api/v4/projects/test-owner%2Ftest-repo/protected_tags/v%2A",
            status=403,
        )
        with pytest.raises(AuthenticationError):
            gitlab_adapter.delete_tag_protection("v*")


# --- Gitea ---


class TestGiteaTagProtect:
    @responses.activate
    def test_list(self, gitea_adapter):
        responses.add(
            responses.GET,
            "https://gitea.example.com/api/v1/repos/test-owner/test-repo/tag_protections",
            json=[
                {"id": 1, "name_pattern": "v*", "whitelist_teams": ""},
            ],
        )
        tps = gitea_adapter.list_tag_protections()
        assert len(tps) == 1
        assert tps[0].id == 1
        assert tps[0].pattern == "v*"

    @responses.activate
    def test_create(self, gitea_adapter):
        responses.add(
            responses.POST,
            "https://gitea.example.com/api/v1/repos/test-owner/test-repo/tag_protections",
            json={"id": 2, "name_pattern": "release-*", "whitelist_teams": ""},
            status=201,
        )
        tp = gitea_adapter.create_tag_protection("release-*")
        assert tp.id == 2
        assert tp.pattern == "release-*"
        req_body = json.loads(responses.calls[0].request.body)
        assert req_body["name_pattern"] == "release-*"

    @responses.activate
    def test_delete(self, gitea_adapter):
        responses.add(
            responses.DELETE,
            "https://gitea.example.com/api/v1/repos/test-owner/test-repo/tag_protections/1",
            status=204,
        )
        gitea_adapter.delete_tag_protection(1)

    @responses.activate
    def test_list_empty(self, gitea_adapter):
        responses.add(
            responses.GET,
            "https://gitea.example.com/api/v1/repos/test-owner/test-repo/tag_protections",
            json=[],
        )
        assert gitea_adapter.list_tag_protections() == []

    @responses.activate
    def test_list_404(self, gitea_adapter):
        responses.add(
            responses.GET,
            "https://gitea.example.com/api/v1/repos/test-owner/test-repo/tag_protections",
            status=404,
        )
        with pytest.raises(NotFoundError):
            gitea_adapter.list_tag_protections()

    @responses.activate
    def test_delete_403(self, gitea_adapter):
        responses.add(
            responses.DELETE,
            "https://gitea.example.com/api/v1/repos/test-owner/test-repo/tag_protections/1",
            status=403,
        )
        with pytest.raises(AuthenticationError):
            gitea_adapter.delete_tag_protection(1)


# --- Forgejo ---


class TestForgejoTagProtect:
    @responses.activate
    def test_list(self, forgejo_adapter):
        responses.add(
            responses.GET,
            "https://forgejo.example.com/api/v1/repos/test-owner/test-repo/tag_protections",
            json=[
                {"id": 1, "name_pattern": "v*", "whitelist_teams": ""},
            ],
        )
        tps = forgejo_adapter.list_tag_protections()
        assert len(tps) == 1
        assert tps[0].pattern == "v*"

    @responses.activate
    def test_create(self, forgejo_adapter):
        responses.add(
            responses.POST,
            "https://forgejo.example.com/api/v1/repos/test-owner/test-repo/tag_protections",
            json={"id": 2, "name_pattern": "release-*", "whitelist_teams": ""},
            status=201,
        )
        tp = forgejo_adapter.create_tag_protection("release-*")
        assert tp.id == 2

    @responses.activate
    def test_delete(self, forgejo_adapter):
        responses.add(
            responses.DELETE,
            "https://forgejo.example.com/api/v1/repos/test-owner/test-repo/tag_protections/1",
            status=204,
        )
        forgejo_adapter.delete_tag_protection(1)

    @responses.activate
    def test_list_empty(self, forgejo_adapter):
        responses.add(
            responses.GET,
            "https://forgejo.example.com/api/v1/repos/test-owner/test-repo/tag_protections",
            json=[],
        )
        assert forgejo_adapter.list_tag_protections() == []

    @responses.activate
    def test_list_404(self, forgejo_adapter):
        responses.add(
            responses.GET,
            "https://forgejo.example.com/api/v1/repos/test-owner/test-repo/tag_protections",
            status=404,
        )
        with pytest.raises(NotFoundError):
            forgejo_adapter.list_tag_protections()


# --- NotSupported ---


class TestTagProtectNotSupported:
    def test_azure_devops_list(self, azure_devops_adapter):
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.list_tag_protections()

    def test_azure_devops_create(self, azure_devops_adapter):
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.create_tag_protection("v*")

    def test_azure_devops_delete(self, azure_devops_adapter):
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.delete_tag_protection(1)

    def test_bitbucket_list(self, bitbucket_adapter):
        with pytest.raises(NotSupportedError):
            bitbucket_adapter.list_tag_protections()

    def test_bitbucket_create(self, bitbucket_adapter):
        with pytest.raises(NotSupportedError):
            bitbucket_adapter.create_tag_protection("v*")

    def test_bitbucket_delete(self, bitbucket_adapter):
        with pytest.raises(NotSupportedError):
            bitbucket_adapter.delete_tag_protection(1)

    def test_gogs_list(self, gogs_adapter):
        with pytest.raises(NotSupportedError):
            gogs_adapter.list_tag_protections()

    def test_gogs_create(self, gogs_adapter):
        with pytest.raises(NotSupportedError):
            gogs_adapter.create_tag_protection("v*")

    def test_gogs_delete(self, gogs_adapter):
        with pytest.raises(NotSupportedError):
            gogs_adapter.delete_tag_protection(1)

    def test_gitbucket_list(self, gitbucket_adapter):
        with pytest.raises(NotSupportedError):
            gitbucket_adapter.list_tag_protections()

    def test_gitbucket_create(self, gitbucket_adapter):
        with pytest.raises(NotSupportedError):
            gitbucket_adapter.create_tag_protection("v*")

    def test_gitbucket_delete(self, gitbucket_adapter):
        with pytest.raises(NotSupportedError):
            gitbucket_adapter.delete_tag_protection(1)

    def test_backlog_list(self, backlog_adapter):
        with pytest.raises(NotSupportedError):
            backlog_adapter.list_tag_protections()

    def test_backlog_create(self, backlog_adapter):
        with pytest.raises(NotSupportedError):
            backlog_adapter.create_tag_protection("v*")

    def test_backlog_delete(self, backlog_adapter):
        with pytest.raises(NotSupportedError):
            backlog_adapter.delete_tag_protection(1)
