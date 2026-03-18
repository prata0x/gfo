"""ServiceSpec / parse_service_spec / create_adapter_from_spec のテスト。"""

from __future__ import annotations

from dataclasses import asdict
from unittest.mock import MagicMock, patch

import pytest

from gfo.commands import ServiceSpec, create_adapter_from_spec, parse_service_spec
from gfo.exceptions import ConfigError

# ── parse_service_spec: SaaS デフォルトホスト解決 ──


class TestSaaSDefaultHost:
    def test_github(self):
        result = parse_service_spec("github:owner/repo")
        assert result == ServiceSpec(
            service_type="github", host="github.com", owner="owner", repo="repo"
        )

    def test_gitlab(self):
        result = parse_service_spec("gitlab:owner/repo")
        assert result == ServiceSpec(
            service_type="gitlab", host="gitlab.com", owner="owner", repo="repo"
        )

    def test_bitbucket(self):
        result = parse_service_spec("bitbucket:owner/repo")
        assert result == ServiceSpec(
            service_type="bitbucket", host="bitbucket.org", owner="owner", repo="repo"
        )


# ── parse_service_spec: セルフホスト型 host 明示 ──


class TestSelfHostedExplicitHost:
    def test_gitea(self):
        result = parse_service_spec("gitea:gitea.example.com:owner/repo")
        assert result == ServiceSpec(
            service_type="gitea", host="gitea.example.com", owner="owner", repo="repo"
        )

    def test_forgejo(self):
        result = parse_service_spec("forgejo:forgejo.example.com:owner/repo")
        assert result == ServiceSpec(
            service_type="forgejo", host="forgejo.example.com", owner="owner", repo="repo"
        )

    def test_gogs(self):
        result = parse_service_spec("gogs:gogs.example.com:owner/repo")
        assert result == ServiceSpec(
            service_type="gogs", host="gogs.example.com", owner="owner", repo="repo"
        )

    def test_gitbucket(self):
        result = parse_service_spec("gitbucket:gb.example.com:owner/repo")
        assert result == ServiceSpec(
            service_type="gitbucket", host="gb.example.com", owner="owner", repo="repo"
        )


# ── parse_service_spec: SaaS カスタムホスト ──


class TestSaaSCustomHost:
    def test_github_custom_host(self):
        result = parse_service_spec("github:gh.example.com:owner/repo")
        assert result == ServiceSpec(
            service_type="github", host="gh.example.com", owner="owner", repo="repo"
        )

    def test_gitlab_custom_host(self):
        result = parse_service_spec("gitlab:gl.example.com:owner/repo")
        assert result == ServiceSpec(
            service_type="gitlab", host="gl.example.com", owner="owner", repo="repo"
        )

    def test_bitbucket_custom_host(self):
        result = parse_service_spec("bitbucket:bb.example.com:owner/repo")
        assert result == ServiceSpec(
            service_type="bitbucket", host="bb.example.com", owner="owner", repo="repo"
        )


# ── parse_service_spec: Azure DevOps ──


class TestAzureDevOps:
    def test_default_host(self):
        result = parse_service_spec("azure-devops:myorg/myproject/myrepo")
        assert result == ServiceSpec(
            service_type="azure-devops",
            host="dev.azure.com",
            owner="myorg",
            repo="myrepo",
            organization="myorg",
            project_key="myproject",
        )

    def test_custom_host(self):
        result = parse_service_spec("azure-devops:custom.host:myorg/myproject/myrepo")
        assert result == ServiceSpec(
            service_type="azure-devops",
            host="custom.host",
            owner="myorg",
            repo="myrepo",
            organization="myorg",
            project_key="myproject",
        )


# ── parse_service_spec: Backlog ──


class TestBacklog:
    def test_backlog(self):
        result = parse_service_spec("backlog:team.backlog.com:PROJECT/repo")
        assert result == ServiceSpec(
            service_type="backlog",
            host="team.backlog.com",
            owner="PROJECT",
            repo="repo",
            project_key="PROJECT",
        )


# ── parse_service_spec: エラーケース ──


class TestParseErrors:
    def test_selfhosted_without_host_gitea(self):
        with pytest.raises(ConfigError):
            parse_service_spec("gitea:owner/repo")

    def test_selfhosted_without_host_forgejo(self):
        with pytest.raises(ConfigError):
            parse_service_spec("forgejo:owner/repo")

    def test_selfhosted_without_host_gogs(self):
        with pytest.raises(ConfigError):
            parse_service_spec("gogs:owner/repo")

    def test_selfhosted_without_host_gitbucket(self):
        with pytest.raises(ConfigError):
            parse_service_spec("gitbucket:owner/repo")

    def test_empty_string(self):
        with pytest.raises(ConfigError):
            parse_service_spec("")

    def test_colon_only(self):
        with pytest.raises(ConfigError):
            parse_service_spec(":")

    def test_service_only(self):
        with pytest.raises(ConfigError):
            parse_service_spec("github:")

    def test_triple_colon(self):
        with pytest.raises(ConfigError):
            parse_service_spec(":::")

    def test_azure_devops_missing_project(self):
        """Azure DevOps で org/project/repo でなく org/repo の場合。"""
        with pytest.raises(ConfigError):
            parse_service_spec("azure-devops:myorg/myrepo")

    def test_azure_devops_single_segment(self):
        """Azure DevOps で単一セグメントの場合。"""
        with pytest.raises(ConfigError):
            parse_service_spec("azure-devops:myrepo")

    def test_azure_devops_empty_segments(self):
        """Azure DevOps で空セグメントがある場合。"""
        with pytest.raises(ConfigError):
            parse_service_spec("azure-devops:org//repo")

    def test_github_missing_repo(self):
        """owner のみで repo がない場合。"""
        with pytest.raises(ConfigError):
            parse_service_spec("github:owner")

    def test_github_trailing_slash(self):
        """owner/ でrepo が空の場合。"""
        with pytest.raises(ConfigError):
            parse_service_spec("github:owner/")

    def test_github_leading_slash(self):
        """/repo で owner が空の場合。"""
        with pytest.raises(ConfigError):
            parse_service_spec("github:/repo")

    def test_unknown_service_without_host(self):
        """未知のサービス（SaaS デフォルトホストなし）で host 省略の場合。"""
        with pytest.raises(ConfigError):
            parse_service_spec("unknown:owner/repo")

    def test_empty_host_in_three_part(self):
        """service::owner/repo の形式（空 host）。"""
        with pytest.raises(ConfigError):
            parse_service_spec("github::owner/repo")

    def test_empty_owner_repo_in_three_part(self):
        """service:host: の形式（空 owner/repo）。"""
        with pytest.raises(ConfigError):
            parse_service_spec("github:example.com:")

    def test_backlog_without_host(self):
        """Backlog はデフォルトホストがないため host 必須。"""
        with pytest.raises(ConfigError):
            parse_service_spec("backlog:PROJECT/repo")


# ── create_adapter_from_spec ──


class TestCreateAdapterFromSpec:
    def test_github_adapter(self):
        spec = ServiceSpec(service_type="github", host="github.com", owner="owner", repo="repo")
        mock_adapter_cls = MagicMock()
        mock_client = MagicMock()

        with (
            patch(
                "gfo.config.build_default_api_url", return_value="https://api.github.com"
            ) as mock_build,
            patch("gfo.auth.resolve_token", return_value="test-token") as mock_token,
            patch("gfo.adapter.registry.create_http_client", return_value=mock_client) as mock_http,
            patch(
                "gfo.adapter.registry.get_adapter_class", return_value=mock_adapter_cls
            ) as mock_cls,
        ):
            create_adapter_from_spec(spec)

            mock_build.assert_called_once_with("github", "github.com", None, None)
            mock_token.assert_called_once_with("github.com", "github")
            mock_http.assert_called_once_with("github", "https://api.github.com", "test-token")
            mock_cls.assert_called_once_with("github")
            mock_adapter_cls.assert_called_once_with(mock_client, "owner", "repo")

    def test_backlog_adapter_with_project_key(self):
        spec = ServiceSpec(
            service_type="backlog",
            host="team.backlog.com",
            owner="PROJECT",
            repo="repo",
            project_key="PROJECT",
        )
        mock_adapter_cls = MagicMock()
        mock_client = MagicMock()

        with (
            patch(
                "gfo.config.build_default_api_url", return_value="https://team.backlog.com/api/v2"
            ),
            patch("gfo.auth.resolve_token", return_value="test-token"),
            patch("gfo.adapter.registry.create_http_client", return_value=mock_client),
            patch("gfo.adapter.registry.get_adapter_class", return_value=mock_adapter_cls),
        ):
            create_adapter_from_spec(spec)

            mock_adapter_cls.assert_called_once_with(
                mock_client, "PROJECT", "repo", project_key="PROJECT"
            )

    def test_azure_devops_adapter(self):
        spec = ServiceSpec(
            service_type="azure-devops",
            host="dev.azure.com",
            owner="myorg",
            repo="myrepo",
            organization="myorg",
            project_key="myproject",
        )
        mock_adapter_cls = MagicMock()
        mock_client = MagicMock()

        with (
            patch(
                "gfo.config.build_default_api_url",
                return_value="https://dev.azure.com/myorg/myproject/_apis",
            ) as mock_build,
            patch("gfo.auth.resolve_token", return_value="test-token"),
            patch("gfo.adapter.registry.create_http_client", return_value=mock_client),
            patch("gfo.adapter.registry.get_adapter_class", return_value=mock_adapter_cls),
        ):
            create_adapter_from_spec(spec)

            mock_build.assert_called_once_with(
                "azure-devops", "dev.azure.com", "myorg", "myproject"
            )
            mock_adapter_cls.assert_called_once_with(
                mock_client, "myorg", "myrepo", organization="myorg", project_key="myproject"
            )

    def test_gitea_adapter(self):
        spec = ServiceSpec(
            service_type="gitea", host="gitea.example.com", owner="owner", repo="repo"
        )
        mock_adapter_cls = MagicMock()
        mock_client = MagicMock()

        with (
            patch(
                "gfo.config.build_default_api_url", return_value="https://gitea.example.com/api/v1"
            ),
            patch("gfo.auth.resolve_token", return_value="test-token"),
            patch("gfo.adapter.registry.create_http_client", return_value=mock_client),
            patch("gfo.adapter.registry.get_adapter_class", return_value=mock_adapter_cls),
        ):
            create_adapter_from_spec(spec)

            mock_adapter_cls.assert_called_once_with(mock_client, "owner", "repo")


# ── ServiceSpec: asdict による辞書化 ──


class TestServiceSpecAsDict:
    def test_basic(self):
        spec = ServiceSpec(service_type="github", host="github.com", owner="owner", repo="repo")
        d = asdict(spec)
        assert d == {
            "service_type": "github",
            "host": "github.com",
            "owner": "owner",
            "repo": "repo",
            "organization": None,
            "project_key": None,
        }

    def test_with_optional_fields(self):
        spec = ServiceSpec(
            service_type="azure-devops",
            host="dev.azure.com",
            owner="myorg",
            repo="myrepo",
            organization="myorg",
            project_key="myproject",
        )
        d = asdict(spec)
        assert d == {
            "service_type": "azure-devops",
            "host": "dev.azure.com",
            "owner": "myorg",
            "repo": "myrepo",
            "organization": "myorg",
            "project_key": "myproject",
        }

    def test_backlog_with_project_key(self):
        spec = ServiceSpec(
            service_type="backlog",
            host="team.backlog.com",
            owner="PROJECT",
            repo="repo",
            project_key="PROJECT",
        )
        d = asdict(spec)
        assert d == {
            "service_type": "backlog",
            "host": "team.backlog.com",
            "owner": "PROJECT",
            "repo": "repo",
            "organization": None,
            "project_key": "PROJECT",
        }


# ── ServiceSpec: frozen 性の検証 ──


class TestServiceSpecFrozen:
    def test_immutable(self):
        spec = ServiceSpec(service_type="github", host="github.com", owner="owner", repo="repo")
        with pytest.raises(AttributeError):
            spec.host = "other.com"  # type: ignore[misc]
