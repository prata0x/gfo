"""全アダプターの Secret / Variable テスト。"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
import responses

from gfo.exceptions import NotSupportedError

# --- GitHub ---


class TestGitHubSecret:
    @responses.activate
    def test_list(self, github_adapter):
        responses.add(
            responses.GET,
            "https://api.github.com/repos/test-owner/test-repo/actions/secrets",
            json={
                "total_count": 1,
                "secrets": [
                    {"name": "MY_SECRET", "created_at": "2024-01-01", "updated_at": "2024-01-02"}
                ],
            },
        )
        secrets = github_adapter.list_secrets()
        assert len(secrets) == 1
        assert secrets[0].name == "MY_SECRET"

    @responses.activate
    def test_set(self, github_adapter):
        responses.add(
            responses.GET,
            "https://api.github.com/repos/test-owner/test-repo/actions/secrets/public-key",
            json={"key_id": "k1", "key": "AAAA"},
        )
        responses.add(
            responses.PUT,
            "https://api.github.com/repos/test-owner/test-repo/actions/secrets/MY_SECRET",
            status=201,
        )
        responses.add(
            responses.GET,
            "https://api.github.com/repos/test-owner/test-repo/actions/secrets/MY_SECRET",
            json={"name": "MY_SECRET", "created_at": "2024-01-01", "updated_at": "2024-01-02"},
        )
        with patch.object(
            type(github_adapter), "_encrypt_secret", staticmethod(lambda k, v: "encrypted==")
        ):
            secret = github_adapter.set_secret("MY_SECRET", "value")
        assert secret.name == "MY_SECRET"
        body = json.loads(responses.calls[1].request.body)
        assert body["encrypted_value"] == "encrypted=="
        assert body["key_id"] == "k1"

    @responses.activate
    def test_delete(self, github_adapter):
        responses.add(
            responses.DELETE,
            "https://api.github.com/repos/test-owner/test-repo/actions/secrets/MY_SECRET",
            status=204,
        )
        github_adapter.delete_secret("MY_SECRET")


class TestGitHubVariable:
    @responses.activate
    def test_list(self, github_adapter):
        responses.add(
            responses.GET,
            "https://api.github.com/repos/test-owner/test-repo/actions/variables",
            json={
                "total_count": 1,
                "variables": [
                    {
                        "name": "MY_VAR",
                        "value": "val",
                        "created_at": "2024-01-01",
                        "updated_at": "2024-01-02",
                    }
                ],
            },
        )
        variables = github_adapter.list_variables()
        assert len(variables) == 1
        assert variables[0].value == "val"

    @responses.activate
    def test_get(self, github_adapter):
        responses.add(
            responses.GET,
            "https://api.github.com/repos/test-owner/test-repo/actions/variables/MY_VAR",
            json={"name": "MY_VAR", "value": "val", "created_at": "", "updated_at": ""},
        )
        var = github_adapter.get_variable("MY_VAR")
        assert var.value == "val"

    @responses.activate
    def test_delete(self, github_adapter):
        responses.add(
            responses.DELETE,
            "https://api.github.com/repos/test-owner/test-repo/actions/variables/MY_VAR",
            status=204,
        )
        github_adapter.delete_variable("MY_VAR")


# --- GitLab ---


class TestGitLabSecret:
    @responses.activate
    def test_list(self, gitlab_adapter):
        responses.add(
            responses.GET,
            "https://gitlab.com/api/v4/projects/test-owner%2Ftest-repo/variables",
            json=[
                {"key": "SECRET1", "value": "", "masked": True},
                {"key": "VAR1", "value": "v", "masked": False},
            ],
        )
        secrets = gitlab_adapter.list_secrets()
        assert len(secrets) == 1
        assert secrets[0].name == "SECRET1"


class TestGitLabVariable:
    @responses.activate
    def test_list(self, gitlab_adapter):
        responses.add(
            responses.GET,
            "https://gitlab.com/api/v4/projects/test-owner%2Ftest-repo/variables",
            json=[{"key": "VAR1", "value": "v", "masked": False}],
        )
        variables = gitlab_adapter.list_variables()
        assert len(variables) == 1
        assert variables[0].name == "VAR1"

    @responses.activate
    def test_get(self, gitlab_adapter):
        responses.add(
            responses.GET,
            "https://gitlab.com/api/v4/projects/test-owner%2Ftest-repo/variables/VAR1",
            json={"key": "VAR1", "value": "v"},
        )
        var = gitlab_adapter.get_variable("VAR1")
        assert var.value == "v"

    @responses.activate
    def test_delete(self, gitlab_adapter):
        responses.add(
            responses.DELETE,
            "https://gitlab.com/api/v4/projects/test-owner%2Ftest-repo/variables/VAR1",
            status=204,
        )
        gitlab_adapter.delete_variable("VAR1")


# --- Gitea ---


class TestGiteaSecret:
    @responses.activate
    def test_list(self, gitea_adapter):
        responses.add(
            responses.GET,
            "https://gitea.example.com/api/v1/repos/test-owner/test-repo/actions/secrets",
            json=[{"name": "MY_SECRET", "created_at": "2024-01-01"}],
        )
        secrets = gitea_adapter.list_secrets()
        assert len(secrets) == 1

    @responses.activate
    def test_set(self, gitea_adapter):
        responses.add(
            responses.PUT,
            "https://gitea.example.com/api/v1/repos/test-owner/test-repo/actions/secrets/MY_SECRET",
            status=201,
        )
        secret = gitea_adapter.set_secret("MY_SECRET", "value")
        assert secret.name == "MY_SECRET"

    @responses.activate
    def test_delete(self, gitea_adapter):
        responses.add(
            responses.DELETE,
            "https://gitea.example.com/api/v1/repos/test-owner/test-repo/actions/secrets/MY_SECRET",
            status=204,
        )
        gitea_adapter.delete_secret("MY_SECRET")


class TestGiteaVariable:
    @responses.activate
    def test_list(self, gitea_adapter):
        responses.add(
            responses.GET,
            "https://gitea.example.com/api/v1/repos/test-owner/test-repo/actions/variables",
            json=[{"name": "MY_VAR", "data": "val"}],
        )
        variables = gitea_adapter.list_variables()
        assert len(variables) == 1
        assert variables[0].value == "val"

    @responses.activate
    def test_get(self, gitea_adapter):
        responses.add(
            responses.GET,
            "https://gitea.example.com/api/v1/repos/test-owner/test-repo/actions/variables/MY_VAR",
            json={"name": "MY_VAR", "data": "val"},
        )
        var = gitea_adapter.get_variable("MY_VAR")
        assert var.value == "val"

    @responses.activate
    def test_delete(self, gitea_adapter):
        responses.add(
            responses.DELETE,
            "https://gitea.example.com/api/v1/repos/test-owner/test-repo/actions/variables/MY_VAR",
            status=204,
        )
        gitea_adapter.delete_variable("MY_VAR")


# --- Bitbucket ---


class TestBitbucketSecret:
    @responses.activate
    def test_list(self, bitbucket_adapter):
        responses.add(
            responses.GET,
            "https://api.bitbucket.org/2.0/repositories/test-workspace/test-repo/pipelines_config/variables/",
            json={
                "values": [
                    {"key": "S1", "secured": True},
                    {"key": "V1", "secured": False, "value": "v"},
                ],
                "pagelen": 10,
            },
        )
        secrets = bitbucket_adapter.list_secrets()
        assert len(secrets) == 1
        assert secrets[0].name == "S1"


class TestBitbucketVariable:
    @responses.activate
    def test_list(self, bitbucket_adapter):
        responses.add(
            responses.GET,
            "https://api.bitbucket.org/2.0/repositories/test-workspace/test-repo/pipelines_config/variables/",
            json={"values": [{"key": "V1", "value": "v", "secured": False}], "pagelen": 10},
        )
        variables = bitbucket_adapter.list_variables()
        assert len(variables) == 1
        assert variables[0].name == "V1"


# --- NotSupported ---


class TestSecretVariableNotSupported:
    def test_azure_devops_secret(self, azure_devops_adapter):
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.list_secrets()

    def test_azure_devops_variable(self, azure_devops_adapter):
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.list_variables()

    def test_gogs_secret(self, gogs_adapter):
        with pytest.raises(NotSupportedError):
            gogs_adapter.list_secrets()

    def test_gogs_variable(self, gogs_adapter):
        with pytest.raises(NotSupportedError):
            gogs_adapter.list_variables()

    def test_gitbucket_secret(self, gitbucket_adapter):
        with pytest.raises(NotSupportedError):
            gitbucket_adapter.list_secrets()

    def test_gitbucket_variable(self, gitbucket_adapter):
        with pytest.raises(NotSupportedError):
            gitbucket_adapter.list_variables()

    def test_backlog_secret(self, backlog_adapter):
        with pytest.raises(NotSupportedError):
            backlog_adapter.list_secrets()

    def test_backlog_variable(self, backlog_adapter):
        with pytest.raises(NotSupportedError):
            backlog_adapter.list_variables()
