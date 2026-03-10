"""adapter/registry.py のテスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gfo.adapter.base import GitServiceAdapter
from gfo.adapter.registry import (
    _REGISTRY,
    create_adapter,
    create_http_client,
    get_adapter_class,
    register,
)
from gfo.config import ProjectConfig
from gfo.exceptions import ConfigError, UnsupportedServiceError


class TestRegister:
    def setup_method(self):
        self._backup = dict(_REGISTRY)

    def teardown_method(self):
        _REGISTRY.clear()
        _REGISTRY.update(self._backup)

    def test_register_and_get(self):
        @register("test-service")
        class TestAdapter(GitServiceAdapter):
            service_name = "test"

        assert get_adapter_class("test-service") is TestAdapter

    def test_get_unregistered_raises(self):
        with pytest.raises(UnsupportedServiceError):
            get_adapter_class("nonexistent-service")


def _make_config(service_type: str, **overrides) -> ProjectConfig:
    defaults = dict(
        service_type=service_type,
        host="example.com",
        api_url="https://api.example.com",
        owner="owner",
        repo="repo",
    )
    defaults.update(overrides)
    return ProjectConfig(**defaults)


class TestCreateAdapter:
    def setup_method(self):
        self._backup = dict(_REGISTRY)
        self._mock_cls = MagicMock()
        self._mock_cls.return_value = MagicMock(spec=GitServiceAdapter)

    def teardown_method(self):
        _REGISTRY.clear()
        _REGISTRY.update(self._backup)

    def _register(self, stype: str):
        _REGISTRY[stype] = self._mock_cls

    @patch("gfo.auth.resolve_token", return_value="ghp_token123")
    @patch("gfo.http.HttpClient")
    def test_github_bearer(self, MockHttpClient, mock_resolve):
        self._register("github")
        config = _make_config("github")
        create_adapter(config)
        MockHttpClient.assert_called_once_with(
            config.api_url,
            auth_header={"Authorization": "Bearer ghp_token123"},
        )

    @patch("gfo.auth.resolve_token", return_value="glpat-xxx")
    @patch("gfo.http.HttpClient")
    def test_gitlab_private_token(self, MockHttpClient, mock_resolve):
        self._register("gitlab")
        config = _make_config("gitlab")
        create_adapter(config)
        MockHttpClient.assert_called_once_with(
            config.api_url,
            auth_header={"Private-Token": "glpat-xxx"},
        )

    @patch("gfo.auth.resolve_token", return_value="user:app-pw")
    @patch("gfo.http.HttpClient")
    def test_bitbucket_basic_auth(self, MockHttpClient, mock_resolve):
        self._register("bitbucket")
        config = _make_config("bitbucket")
        create_adapter(config)
        MockHttpClient.assert_called_once_with(
            config.api_url,
            basic_auth=("user", "app-pw"),
        )

    @patch("gfo.auth.resolve_token", return_value="no-colon-token")
    def test_bitbucket_no_colon_raises(self, mock_resolve):
        self._register("bitbucket")
        config = _make_config("bitbucket")
        with pytest.raises(ConfigError, match="email:api-token"):
            create_adapter(config)

    @patch("gfo.auth.resolve_token", return_value="azure-pat")
    @patch("gfo.http.HttpClient")
    def test_azure_devops(self, MockHttpClient, mock_resolve):
        self._register("azure-devops")
        config = _make_config(
            "azure-devops",
            organization="myorg",
            project_key="myproject",
        )
        create_adapter(config)
        MockHttpClient.assert_called_once_with(
            config.api_url,
            basic_auth=("", "azure-pat"),
            default_params={"api-version": "7.1"},
        )
        self._mock_cls.assert_called_once_with(
            MockHttpClient.return_value,
            "owner",
            "repo",
            organization="myorg",
            project_key="myproject",
        )

    @patch("gfo.auth.resolve_token", return_value="backlog-key")
    @patch("gfo.http.HttpClient")
    def test_backlog_auth_params(self, MockHttpClient, mock_resolve):
        self._register("backlog")
        config = _make_config("backlog", project_key="PROJ")
        create_adapter(config)
        MockHttpClient.assert_called_once_with(
            config.api_url,
            auth_params={"apiKey": "backlog-key"},
        )
        self._mock_cls.assert_called_once_with(
            MockHttpClient.return_value,
            "owner",
            "repo",
            project_key="PROJ",
        )

    @pytest.mark.parametrize("stype", ["gitea", "forgejo", "gogs", "gitbucket"])
    @patch("gfo.auth.resolve_token", return_value="tok123")
    @patch("gfo.http.HttpClient")
    def test_token_auth_services(self, MockHttpClient, mock_resolve, stype):
        self._register(stype)
        config = _make_config(stype)
        create_adapter(config)
        MockHttpClient.assert_called_once_with(
            config.api_url,
            auth_header={"Authorization": "token tok123"},
        )

    @patch("gfo.auth.resolve_token", return_value="tok")
    def test_unsupported_service_raises(self, mock_resolve):
        config = _make_config("unknown-service")
        with pytest.raises(UnsupportedServiceError):
            create_adapter(config)


class TestCreateHttpClient:
    @patch("gfo.http.HttpClient")
    def test_github(self, MockHttpClient):
        create_http_client("github", "https://api.github.com", "ghp_tok")
        MockHttpClient.assert_called_once_with(
            "https://api.github.com",
            auth_header={"Authorization": "Bearer ghp_tok"},
        )

    @patch("gfo.http.HttpClient")
    def test_gitlab(self, MockHttpClient):
        create_http_client("gitlab", "https://gitlab.com/api/v4", "glpat-xxx")
        MockHttpClient.assert_called_once_with(
            "https://gitlab.com/api/v4",
            auth_header={"Private-Token": "glpat-xxx"},
        )

    @patch("gfo.http.HttpClient")
    def test_bitbucket(self, MockHttpClient):
        create_http_client("bitbucket", "https://api.bitbucket.org/2.0", "user:pw")
        MockHttpClient.assert_called_once_with(
            "https://api.bitbucket.org/2.0",
            basic_auth=("user", "pw"),
        )

    def test_bitbucket_invalid_token_raises(self):
        with pytest.raises(ConfigError, match="email:api-token"):
            create_http_client("bitbucket", "https://api.bitbucket.org/2.0", "nocolon")

    @patch("gfo.http.HttpClient")
    def test_azure_devops(self, MockHttpClient):
        create_http_client("azure-devops", "https://dev.azure.com", "pat")
        MockHttpClient.assert_called_once_with(
            "https://dev.azure.com",
            basic_auth=("", "pat"),
            default_params={"api-version": "7.1"},
        )

    @patch("gfo.http.HttpClient")
    def test_backlog(self, MockHttpClient):
        create_http_client("backlog", "https://example.backlog.com/api/v2", "apikey")
        MockHttpClient.assert_called_once_with(
            "https://example.backlog.com/api/v2",
            auth_params={"apiKey": "apikey"},
        )

    @pytest.mark.parametrize("stype", ["gitea", "forgejo", "gogs", "gitbucket"])
    @patch("gfo.http.HttpClient")
    def test_token_auth_services(self, MockHttpClient, stype):
        create_http_client(stype, "https://example.com/api/v1", "tok123")
        MockHttpClient.assert_called_once_with(
            "https://example.com/api/v1",
            auth_header={"Authorization": "token tok123"},
        )

    def test_unsupported_service_raises(self):
        with pytest.raises(UnsupportedServiceError):
            create_http_client("unknown-service", "https://example.com", "tok")
