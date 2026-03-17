"""gfo.commands.api のテスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gfo.commands import api as api_cmd
from gfo.config import ProjectConfig
from gfo.exceptions import ConfigError
from tests.test_commands.conftest import make_args


@pytest.fixture
def sample_config():
    return ProjectConfig(
        service_type="github",
        host="github.com",
        api_url="https://api.github.com",
        owner="test-owner",
        repo="test-repo",
    )


@pytest.fixture
def mock_client():
    client = MagicMock()
    resp = MagicMock()
    resp.text = '{"id": 1, "name": "test"}'
    client.request.return_value = resp
    return client


def _patch_all(config, client):
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        with (
            patch("gfo.commands.api.resolve_project_config", return_value=config),
            patch("gfo.commands.api.resolve_token", return_value="test-token"),
            patch("gfo.commands.api.create_http_client", return_value=client),
        ):
            yield

    return _ctx()


class TestHandleApi:
    def test_get_request(self, sample_config, mock_client, capsys):
        args = make_args(method="GET", path="/repos/owner/repo", data=None, header=None)
        with _patch_all(sample_config, mock_client):
            api_cmd.handle_api(args, fmt="json")

        mock_client.request.assert_called_once_with(
            "GET",
            "/repos/owner/repo",
            json=None,
            headers={},
        )
        out = capsys.readouterr().out
        assert '"id": 1' in out

    def test_post_with_data(self, sample_config, mock_client, capsys):
        args = make_args(
            method="post",
            path="/repos/owner/repo/issues",
            data='{"title": "test"}',
            header=None,
        )
        with _patch_all(sample_config, mock_client):
            api_cmd.handle_api(args, fmt="json")

        mock_client.request.assert_called_once_with(
            "POST",
            "/repos/owner/repo/issues",
            json={"title": "test"},
            headers={},
        )

    def test_with_headers(self, sample_config, mock_client, capsys):
        args = make_args(
            method="GET",
            path="/test",
            data=None,
            header=["Accept: application/json", "X-Custom: value"],
        )
        with _patch_all(sample_config, mock_client):
            api_cmd.handle_api(args, fmt="json")

        mock_client.request.assert_called_once_with(
            "GET",
            "/test",
            json=None,
            headers={"Accept": "application/json", "X-Custom": "value"},
        )

    def test_invalid_header_format(self, sample_config, mock_client):
        args = make_args(method="GET", path="/test", data=None, header=["invalid-header"])
        with _patch_all(sample_config, mock_client):
            with pytest.raises(ConfigError):
                api_cmd.handle_api(args, fmt="json")

    def test_method_uppercased(self, sample_config, mock_client, capsys):
        args = make_args(method="patch", path="/test", data='{"x": 1}', header=None)
        with _patch_all(sample_config, mock_client):
            api_cmd.handle_api(args, fmt="json")

        mock_client.request.assert_called_once_with(
            "PATCH",
            "/test",
            json={"x": 1},
            headers={},
        )

    def test_jq_filter(self, sample_config, mock_client, capsys):
        args = make_args(method="GET", path="/test", data=None, header=None)
        with _patch_all(sample_config, mock_client):
            with patch("gfo.commands.api.apply_jq_filter", return_value='"test"') as mock_jq:
                api_cmd.handle_api(args, fmt="json", jq=".name")
                mock_jq.assert_called_once()


class TestParseHeaders:
    def test_empty(self):
        assert api_cmd._parse_headers(None) == {}
        assert api_cmd._parse_headers([]) == {}

    def test_valid(self):
        result = api_cmd._parse_headers(["Content-Type: application/json"])
        assert result == {"Content-Type": "application/json"}

    def test_invalid(self):
        with pytest.raises(ConfigError):
            api_cmd._parse_headers(["no-colon"])
