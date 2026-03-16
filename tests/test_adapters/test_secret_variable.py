"""全アダプターの Secret / Variable テスト。"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
import responses

from gfo.exceptions import AuthenticationError, NotFoundError, NotSupportedError

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
    def test_set_create(self, github_adapter):
        """変数が存在しない場合 POST で新規作成。"""
        responses.add(
            responses.GET,
            "https://api.github.com/repos/test-owner/test-repo/actions/variables/MY_VAR",
            status=404,
        )
        responses.add(
            responses.POST,
            "https://api.github.com/repos/test-owner/test-repo/actions/variables",
            status=201,
        )
        var = github_adapter.set_variable("MY_VAR", "new_val")
        assert var.name == "MY_VAR"
        assert var.value == "new_val"

    @responses.activate
    def test_set_update(self, github_adapter):
        """変数が存在する場合 PATCH で更新。"""
        responses.add(
            responses.GET,
            "https://api.github.com/repos/test-owner/test-repo/actions/variables/MY_VAR",
            json={"name": "MY_VAR", "value": "old"},
        )
        responses.add(
            responses.PATCH,
            "https://api.github.com/repos/test-owner/test-repo/actions/variables/MY_VAR",
            status=200,
        )
        var = github_adapter.set_variable("MY_VAR", "new_val")
        assert var.value == "new_val"

    @responses.activate
    def test_delete(self, github_adapter):
        responses.add(
            responses.DELETE,
            "https://api.github.com/repos/test-owner/test-repo/actions/variables/MY_VAR",
            status=204,
        )
        github_adapter.delete_variable("MY_VAR")

    @responses.activate
    def test_list_empty(self, github_adapter):
        responses.add(
            responses.GET,
            "https://api.github.com/repos/test-owner/test-repo/actions/variables",
            json={"total_count": 0, "variables": []},
        )
        assert github_adapter.list_variables() == []

    @responses.activate
    def test_get_404(self, github_adapter):
        responses.add(
            responses.GET,
            "https://api.github.com/repos/test-owner/test-repo/actions/variables/MISSING",
            status=404,
        )
        with pytest.raises(NotFoundError):
            github_adapter.get_variable("MISSING")

    @responses.activate
    def test_delete_403(self, github_adapter):
        responses.add(
            responses.DELETE,
            "https://api.github.com/repos/test-owner/test-repo/actions/variables/X",
            status=403,
        )
        with pytest.raises(AuthenticationError):
            github_adapter.delete_variable("X")


class TestGitHubSecretErrors:
    @responses.activate
    def test_list_empty(self, github_adapter):
        responses.add(
            responses.GET,
            "https://api.github.com/repos/test-owner/test-repo/actions/secrets",
            json={"total_count": 0, "secrets": []},
        )
        assert github_adapter.list_secrets() == []

    @responses.activate
    def test_delete_404(self, github_adapter):
        responses.add(
            responses.DELETE,
            "https://api.github.com/repos/test-owner/test-repo/actions/secrets/MISSING",
            status=404,
        )
        with pytest.raises(NotFoundError):
            github_adapter.delete_secret("MISSING")


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

    @responses.activate
    def test_set(self, gitlab_adapter):
        """set_secret は内部で set_variable(masked=True) を呼ぶ。"""
        # GET で既存チェック → 404 → POST
        responses.add(
            responses.GET,
            "https://gitlab.com/api/v4/projects/test-owner%2Ftest-repo/variables/MY_SECRET",
            status=404,
        )
        responses.add(
            responses.POST,
            "https://gitlab.com/api/v4/projects/test-owner%2Ftest-repo/variables",
            json={"key": "MY_SECRET", "value": "", "masked": True},
            status=201,
        )
        secret = gitlab_adapter.set_secret("MY_SECRET", "secret_val")
        assert secret.name == "MY_SECRET"
        body = json.loads(responses.calls[1].request.body)
        assert body["masked"] is True

    @responses.activate
    def test_list_empty(self, gitlab_adapter):
        responses.add(
            responses.GET,
            "https://gitlab.com/api/v4/projects/test-owner%2Ftest-repo/variables",
            json=[],
        )
        assert gitlab_adapter.list_secrets() == []

    @responses.activate
    def test_delete_404(self, gitlab_adapter):
        responses.add(
            responses.DELETE,
            "https://gitlab.com/api/v4/projects/test-owner%2Ftest-repo/variables/MISSING",
            status=404,
        )
        with pytest.raises(NotFoundError):
            gitlab_adapter.delete_secret("MISSING")


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
    def test_set_create(self, gitlab_adapter):
        """変数が存在しない場合 POST で新規作成。"""
        responses.add(
            responses.GET,
            "https://gitlab.com/api/v4/projects/test-owner%2Ftest-repo/variables/NEW_VAR",
            status=404,
        )
        responses.add(
            responses.POST,
            "https://gitlab.com/api/v4/projects/test-owner%2Ftest-repo/variables",
            json={"key": "NEW_VAR", "value": "val"},
            status=201,
        )
        var = gitlab_adapter.set_variable("NEW_VAR", "val")
        assert var.name == "NEW_VAR"
        assert var.value == "val"

    @responses.activate
    def test_set_update(self, gitlab_adapter):
        """変数が存在する場合 PUT で更新。"""
        responses.add(
            responses.GET,
            "https://gitlab.com/api/v4/projects/test-owner%2Ftest-repo/variables/VAR1",
            json={"key": "VAR1", "value": "old"},
        )
        responses.add(
            responses.PUT,
            "https://gitlab.com/api/v4/projects/test-owner%2Ftest-repo/variables/VAR1",
            json={"key": "VAR1", "value": "new"},
        )
        var = gitlab_adapter.set_variable("VAR1", "new")
        assert var.value == "new"

    @responses.activate
    def test_delete(self, gitlab_adapter):
        responses.add(
            responses.DELETE,
            "https://gitlab.com/api/v4/projects/test-owner%2Ftest-repo/variables/VAR1",
            status=204,
        )
        gitlab_adapter.delete_variable("VAR1")

    @responses.activate
    def test_list_empty(self, gitlab_adapter):
        responses.add(
            responses.GET,
            "https://gitlab.com/api/v4/projects/test-owner%2Ftest-repo/variables",
            json=[],
        )
        assert gitlab_adapter.list_variables() == []

    @responses.activate
    def test_get_404(self, gitlab_adapter):
        responses.add(
            responses.GET,
            "https://gitlab.com/api/v4/projects/test-owner%2Ftest-repo/variables/MISSING",
            status=404,
        )
        with pytest.raises(NotFoundError):
            gitlab_adapter.get_variable("MISSING")

    @responses.activate
    def test_delete_403(self, gitlab_adapter):
        responses.add(
            responses.DELETE,
            "https://gitlab.com/api/v4/projects/test-owner%2Ftest-repo/variables/X",
            status=403,
        )
        with pytest.raises(AuthenticationError):
            gitlab_adapter.delete_variable("X")


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
    def test_set_create(self, gitea_adapter):
        """変数が存在しない場合 POST で新規作成。"""
        responses.add(
            responses.GET,
            "https://gitea.example.com/api/v1/repos/test-owner/test-repo/actions/variables/NEW_VAR",
            status=404,
        )
        responses.add(
            responses.POST,
            "https://gitea.example.com/api/v1/repos/test-owner/test-repo/actions/variables",
            status=201,
        )
        var = gitea_adapter.set_variable("NEW_VAR", "val")
        assert var.name == "NEW_VAR"
        assert var.value == "val"

    @responses.activate
    def test_set_update(self, gitea_adapter):
        """変数が存在する場合 PUT で更新。"""
        responses.add(
            responses.GET,
            "https://gitea.example.com/api/v1/repos/test-owner/test-repo/actions/variables/MY_VAR",
            json={"name": "MY_VAR", "data": "old"},
        )
        responses.add(
            responses.PUT,
            "https://gitea.example.com/api/v1/repos/test-owner/test-repo/actions/variables/MY_VAR",
            status=200,
        )
        var = gitea_adapter.set_variable("MY_VAR", "new_val")
        assert var.value == "new_val"

    @responses.activate
    def test_delete(self, gitea_adapter):
        responses.add(
            responses.DELETE,
            "https://gitea.example.com/api/v1/repos/test-owner/test-repo/actions/variables/MY_VAR",
            status=204,
        )
        gitea_adapter.delete_variable("MY_VAR")

    @responses.activate
    def test_list_empty(self, gitea_adapter):
        responses.add(
            responses.GET,
            "https://gitea.example.com/api/v1/repos/test-owner/test-repo/actions/variables",
            json=[],
        )
        assert gitea_adapter.list_variables() == []

    @responses.activate
    def test_get_404(self, gitea_adapter):
        responses.add(
            responses.GET,
            "https://gitea.example.com/api/v1/repos/test-owner/test-repo/actions/variables/MISSING",
            status=404,
        )
        with pytest.raises(NotFoundError):
            gitea_adapter.get_variable("MISSING")


class TestGiteaSecretErrors:
    @responses.activate
    def test_list_empty(self, gitea_adapter):
        responses.add(
            responses.GET,
            "https://gitea.example.com/api/v1/repos/test-owner/test-repo/actions/secrets",
            json=[],
        )
        assert gitea_adapter.list_secrets() == []

    @responses.activate
    def test_delete_404(self, gitea_adapter):
        responses.add(
            responses.DELETE,
            "https://gitea.example.com/api/v1/repos/test-owner/test-repo/actions/secrets/MISSING",
            status=404,
        )
        with pytest.raises(NotFoundError):
            gitea_adapter.delete_secret("MISSING")


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

    @responses.activate
    def test_set_create(self, bitbucket_adapter):
        """シークレットが存在しない場合 POST で新規作成。"""
        # _find_pipeline_variable_uuid → 全件取得して名前検索 → 見つからない
        responses.add(
            responses.GET,
            "https://api.bitbucket.org/2.0/repositories/test-workspace/test-repo/pipelines_config/variables/",
            json={"values": [], "pagelen": 10},
        )
        responses.add(
            responses.POST,
            "https://api.bitbucket.org/2.0/repositories/test-workspace/test-repo/pipelines_config/variables/",
            json={"key": "NEW_SECRET", "secured": True},
            status=201,
        )
        secret = bitbucket_adapter.set_secret("NEW_SECRET", "secret_val")
        assert secret.name == "NEW_SECRET"

    @responses.activate
    def test_set_update(self, bitbucket_adapter):
        """シークレットが存在する場合 UUID で PUT 更新。"""
        responses.add(
            responses.GET,
            "https://api.bitbucket.org/2.0/repositories/test-workspace/test-repo/pipelines_config/variables/",
            json={
                "values": [{"key": "MY_SECRET", "uuid": "{uuid-1}", "secured": True}],
                "pagelen": 10,
            },
        )
        responses.add(
            responses.PUT,
            "https://api.bitbucket.org/2.0/repositories/test-workspace/test-repo/pipelines_config/variables/{uuid-1}",
            json={"key": "MY_SECRET", "secured": True},
        )
        secret = bitbucket_adapter.set_secret("MY_SECRET", "new_val")
        assert secret.name == "MY_SECRET"

    @responses.activate
    def test_delete(self, bitbucket_adapter):
        """UUID を検索してから DELETE。"""
        responses.add(
            responses.GET,
            "https://api.bitbucket.org/2.0/repositories/test-workspace/test-repo/pipelines_config/variables/",
            json={
                "values": [{"key": "S1", "uuid": "{uuid-s1}", "secured": True}],
                "pagelen": 10,
            },
        )
        responses.add(
            responses.DELETE,
            "https://api.bitbucket.org/2.0/repositories/test-workspace/test-repo/pipelines_config/variables/{uuid-s1}",
            status=204,
        )
        bitbucket_adapter.delete_secret("S1")

    @responses.activate
    def test_list_empty(self, bitbucket_adapter):
        responses.add(
            responses.GET,
            "https://api.bitbucket.org/2.0/repositories/test-workspace/test-repo/pipelines_config/variables/",
            json={"values": [], "pagelen": 10},
        )
        assert bitbucket_adapter.list_secrets() == []

    @responses.activate
    def test_list_403(self, bitbucket_adapter):
        responses.add(
            responses.GET,
            "https://api.bitbucket.org/2.0/repositories/test-workspace/test-repo/pipelines_config/variables/",
            status=403,
        )
        with pytest.raises(AuthenticationError):
            bitbucket_adapter.list_secrets()


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

    @responses.activate
    def test_get(self, bitbucket_adapter):
        """UUID を検索してから GET。"""
        responses.add(
            responses.GET,
            "https://api.bitbucket.org/2.0/repositories/test-workspace/test-repo/pipelines_config/variables/",
            json={
                "values": [{"key": "V1", "uuid": "{uuid-v1}", "value": "v", "secured": False}],
                "pagelen": 10,
            },
        )
        responses.add(
            responses.GET,
            "https://api.bitbucket.org/2.0/repositories/test-workspace/test-repo/pipelines_config/variables/{uuid-v1}",
            json={"key": "V1", "value": "v", "secured": False},
        )
        var = bitbucket_adapter.get_variable("V1")
        assert var.name == "V1"
        assert var.value == "v"

    @responses.activate
    def test_set_create(self, bitbucket_adapter):
        """変数が存在しない場合 POST で新規作成。"""
        responses.add(
            responses.GET,
            "https://api.bitbucket.org/2.0/repositories/test-workspace/test-repo/pipelines_config/variables/",
            json={"values": [], "pagelen": 10},
        )
        responses.add(
            responses.POST,
            "https://api.bitbucket.org/2.0/repositories/test-workspace/test-repo/pipelines_config/variables/",
            json={"key": "NEW_VAR", "value": "val", "secured": False},
            status=201,
        )
        var = bitbucket_adapter.set_variable("NEW_VAR", "val")
        assert var.name == "NEW_VAR"
        assert var.value == "val"

    @responses.activate
    def test_set_update(self, bitbucket_adapter):
        """変数が存在する場合 UUID で PUT 更新。"""
        responses.add(
            responses.GET,
            "https://api.bitbucket.org/2.0/repositories/test-workspace/test-repo/pipelines_config/variables/",
            json={
                "values": [{"key": "V1", "uuid": "{uuid-v1}", "value": "old", "secured": False}],
                "pagelen": 10,
            },
        )
        responses.add(
            responses.PUT,
            "https://api.bitbucket.org/2.0/repositories/test-workspace/test-repo/pipelines_config/variables/{uuid-v1}",
            json={"key": "V1", "value": "new", "secured": False},
        )
        var = bitbucket_adapter.set_variable("V1", "new")
        assert var.name == "V1"

    @responses.activate
    def test_delete(self, bitbucket_adapter):
        """UUID を検索してから DELETE。"""
        responses.add(
            responses.GET,
            "https://api.bitbucket.org/2.0/repositories/test-workspace/test-repo/pipelines_config/variables/",
            json={
                "values": [{"key": "V1", "uuid": "{uuid-v1}", "secured": False}],
                "pagelen": 10,
            },
        )
        responses.add(
            responses.DELETE,
            "https://api.bitbucket.org/2.0/repositories/test-workspace/test-repo/pipelines_config/variables/{uuid-v1}",
            status=204,
        )
        bitbucket_adapter.delete_variable("V1")

    @responses.activate
    def test_list_empty(self, bitbucket_adapter):
        responses.add(
            responses.GET,
            "https://api.bitbucket.org/2.0/repositories/test-workspace/test-repo/pipelines_config/variables/",
            json={"values": [], "pagelen": 10},
        )
        assert bitbucket_adapter.list_variables() == []

    @responses.activate
    def test_get_not_found(self, bitbucket_adapter):
        """存在しない変数の get_variable は NotFoundError。"""
        responses.add(
            responses.GET,
            "https://api.bitbucket.org/2.0/repositories/test-workspace/test-repo/pipelines_config/variables/",
            json={"values": [], "pagelen": 10},
        )
        with pytest.raises(NotFoundError):
            bitbucket_adapter.get_variable("MISSING")


# --- Forgejo / Gogs スモークテスト ---


class TestForgejoSecretVariable:
    """Forgejo は Gitea を継承するため、基本的な list のみスモークテスト。"""

    @responses.activate
    def test_list_secrets(self, forgejo_adapter):
        responses.add(
            responses.GET,
            "https://forgejo.example.com/api/v1/repos/test-owner/test-repo/actions/secrets",
            json=[{"name": "S1", "created_at": "2024-01-01"}],
        )
        secrets = forgejo_adapter.list_secrets()
        assert len(secrets) == 1

    @responses.activate
    def test_list_variables(self, forgejo_adapter):
        responses.add(
            responses.GET,
            "https://forgejo.example.com/api/v1/repos/test-owner/test-repo/actions/variables",
            json=[{"name": "V1", "data": "val"}],
        )
        variables = forgejo_adapter.list_variables()
        assert len(variables) == 1

    @responses.activate
    def test_list_secrets_empty(self, forgejo_adapter):
        responses.add(
            responses.GET,
            "https://forgejo.example.com/api/v1/repos/test-owner/test-repo/actions/secrets",
            json=[],
        )
        assert forgejo_adapter.list_secrets() == []

    @responses.activate
    def test_list_variables_empty(self, forgejo_adapter):
        responses.add(
            responses.GET,
            "https://forgejo.example.com/api/v1/repos/test-owner/test-repo/actions/variables",
            json=[],
        )
        assert forgejo_adapter.list_variables() == []


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
