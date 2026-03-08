"""gfo.commands.repo のテスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gfo.adapter.base import Repository
from gfo.commands import repo as repo_cmd
from gfo.exceptions import ConfigError
from tests.test_commands.conftest import make_args


@pytest.fixture
def sample_repo():
    return Repository(
        name="test-repo",
        full_name="test-owner/test-repo",
        description="A test repo",
        private=False,
        default_branch="main",
        clone_url="https://github.com/test-owner/test-repo.git",
        url="https://github.com/test-owner/test-repo",
    )


@pytest.fixture
def mock_adapter(sample_repo):
    adapter = MagicMock()
    adapter.list_repositories.return_value = [sample_repo]
    adapter.create_repository.return_value = sample_repo
    adapter.get_repository.return_value = sample_repo
    return adapter


def _patch_all(sample_config, mock_adapter):
    """resolve_project_config と create_adapter をまとめてパッチするコンテキスト。"""
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        with patch("gfo.commands.repo.resolve_project_config", return_value=sample_config), \
             patch("gfo.commands.repo.create_adapter", return_value=mock_adapter):
            yield

    return _ctx()


class TestHandleList:
    def test_calls_list_repositories(self, sample_config, mock_adapter, capsys):
        args = make_args(limit=30)
        with _patch_all(sample_config, mock_adapter):
            repo_cmd.handle_list(args, fmt="table")

        mock_adapter.list_repositories.assert_called_once_with(limit=30)

    def test_outputs_results(self, sample_config, mock_adapter, capsys):
        args = make_args(limit=30)
        with _patch_all(sample_config, mock_adapter):
            repo_cmd.handle_list(args, fmt="table")

        out = capsys.readouterr().out
        assert "test-repo" in out


class TestResolveHostWithoutRepo:
    def test_uses_args_host_when_provided(self):
        with patch("gfo.commands.repo.get_host_config", return_value={"type": "github"}):
            host, stype = repo_cmd._resolve_host_without_repo("github.com")

        assert host == "github.com"
        assert stype == "github"

    def test_falls_back_to_detect_service(self):
        detect_result = MagicMock()
        detect_result.host = "gitlab.com"
        with patch("gfo.commands.repo.detect_service", return_value=detect_result), \
             patch("gfo.commands.repo.get_host_config", return_value={"type": "gitlab"}):
            host, stype = repo_cmd._resolve_host_without_repo(None)

        assert host == "gitlab.com"
        assert stype == "gitlab"

    def test_falls_back_to_default_host_when_detection_fails(self):
        from gfo.exceptions import DetectionError
        with patch("gfo.commands.repo.detect_service", side_effect=DetectionError("no git")), \
             patch("gfo.commands.repo.get_default_host", return_value="github.com"), \
             patch("gfo.commands.repo.get_host_config", return_value={"type": "github"}):
            host, stype = repo_cmd._resolve_host_without_repo(None)

        assert host == "github.com"
        assert stype == "github"

    def test_raises_config_error_when_no_host(self):
        from gfo.exceptions import DetectionError
        with patch("gfo.commands.repo.detect_service", side_effect=DetectionError("no git")), \
             patch("gfo.commands.repo.get_default_host", return_value=None):
            with pytest.raises(ConfigError):
                repo_cmd._resolve_host_without_repo(None)

    def test_resolves_service_type_from_known_hosts(self):
        with patch("gfo.commands.repo.get_host_config", return_value=None), \
             patch("gfo.commands.repo.probe_unknown_host", return_value=None):
            host, stype = repo_cmd._resolve_host_without_repo("github.com")

        assert host == "github.com"
        assert stype == "github"


class TestHandleCreate:
    def test_calls_create_repository(self, capsys):
        args = make_args(host="github.com", name="new-repo", private=False, description="")
        mock_repo = Repository(
            name="new-repo",
            full_name="test-owner/new-repo",
            description="",
            private=False,
            default_branch="main",
            clone_url="https://github.com/test-owner/new-repo.git",
            url="https://github.com/test-owner/new-repo",
        )
        mock_adapter = MagicMock()
        mock_adapter.create_repository.return_value = mock_repo
        mock_adapter_cls = MagicMock(return_value=mock_adapter)

        with patch("gfo.commands.repo._resolve_host_without_repo", return_value=("github.com", "github")), \
             patch("gfo.commands.repo.resolve_token", return_value="test-token"), \
             patch("gfo.commands.repo._build_default_api_url", return_value="https://api.github.com"), \
             patch("gfo.commands.repo.HttpClient"), \
             patch("gfo.commands.repo.get_adapter_class", return_value=mock_adapter_cls):
            repo_cmd.handle_create(args, fmt="table")

        mock_adapter.create_repository.assert_called_once_with(
            name="new-repo",
            private=False,
            description="",
        )

    def test_outputs_created_repository(self, capsys):
        args = make_args(host="github.com", name="new-repo", private=True, description="desc")
        mock_repo = Repository(
            name="new-repo",
            full_name="test-owner/new-repo",
            description="desc",
            private=True,
            default_branch="main",
            clone_url="https://github.com/test-owner/new-repo.git",
            url="https://github.com/test-owner/new-repo",
        )
        mock_adapter = MagicMock()
        mock_adapter.create_repository.return_value = mock_repo
        mock_adapter_cls = MagicMock(return_value=mock_adapter)

        with patch("gfo.commands.repo._resolve_host_without_repo", return_value=("github.com", "github")), \
             patch("gfo.commands.repo.resolve_token", return_value="test-token"), \
             patch("gfo.commands.repo._build_default_api_url", return_value="https://api.github.com"), \
             patch("gfo.commands.repo.HttpClient"), \
             patch("gfo.commands.repo.get_adapter_class", return_value=mock_adapter_cls):
            repo_cmd.handle_create(args, fmt="table")

        out = capsys.readouterr().out
        assert "new-repo" in out


class TestHandleClone:
    def test_github_url(self):
        args = make_args(host="github.com", repo="owner/myrepo")
        with patch("gfo.commands.repo._resolve_host_without_repo", return_value=("github.com", "github")), \
             patch("gfo.commands.repo.git_clone") as mock_clone:
            repo_cmd.handle_clone(args, fmt="table")

        mock_clone.assert_called_once_with("https://github.com/owner/myrepo.git")

    def test_gitlab_url(self):
        args = make_args(host="gitlab.example.com", repo="owner/myrepo")
        with patch("gfo.commands.repo._resolve_host_without_repo", return_value=("gitlab.example.com", "gitlab")), \
             patch("gfo.commands.repo.git_clone") as mock_clone:
            repo_cmd.handle_clone(args, fmt="table")

        mock_clone.assert_called_once_with("https://gitlab.example.com/owner/myrepo.git")

    def test_bitbucket_url(self):
        args = make_args(host="bitbucket.org", repo="owner/myrepo")
        with patch("gfo.commands.repo._resolve_host_without_repo", return_value=("bitbucket.org", "bitbucket")), \
             patch("gfo.commands.repo.git_clone") as mock_clone:
            repo_cmd.handle_clone(args, fmt="table")

        mock_clone.assert_called_once_with("https://bitbucket.org/owner/myrepo.git")

    def test_gitbucket_url(self):
        args = make_args(host="gitbucket.example.com", repo="owner/myrepo")
        with patch("gfo.commands.repo._resolve_host_without_repo", return_value=("gitbucket.example.com", "gitbucket")), \
             patch("gfo.commands.repo.git_clone") as mock_clone:
            repo_cmd.handle_clone(args, fmt="table")

        mock_clone.assert_called_once_with("https://gitbucket.example.com/git/owner/myrepo.git")

    def test_backlog_url(self):
        args = make_args(host="example.backlog.com", repo="PROJECT/myrepo")
        with patch("gfo.commands.repo._resolve_host_without_repo", return_value=("example.backlog.com", "backlog")), \
             patch("gfo.commands.repo.git_clone") as mock_clone:
            repo_cmd.handle_clone(args, fmt="table")

        mock_clone.assert_called_once_with("https://example.backlog.com/git/PROJECT/myrepo.git")

    def test_gitea_url(self):
        args = make_args(host="gitea.example.com", repo="owner/myrepo")
        with patch("gfo.commands.repo._resolve_host_without_repo", return_value=("gitea.example.com", "gitea")), \
             patch("gfo.commands.repo.git_clone") as mock_clone:
            repo_cmd.handle_clone(args, fmt="table")

        mock_clone.assert_called_once_with("https://gitea.example.com/owner/myrepo.git")

    def test_invalid_repo_format_raises_config_error(self):
        args = make_args(host="github.com", repo="invalidformat")
        with patch("gfo.commands.repo._resolve_host_without_repo", return_value=("github.com", "github")):
            with pytest.raises(ConfigError):
                repo_cmd.handle_clone(args, fmt="table")


class TestHandleView:
    def test_calls_get_repository_without_args(self, sample_config, mock_adapter, capsys):
        args = make_args(repo=None)
        with _patch_all(sample_config, mock_adapter):
            repo_cmd.handle_view(args, fmt="table")

        mock_adapter.get_repository.assert_called_once_with(None, None)

    def test_calls_get_repository_with_owner_name(self, sample_config, mock_adapter, capsys):
        args = make_args(repo="other-owner/other-repo")
        with _patch_all(sample_config, mock_adapter):
            repo_cmd.handle_view(args, fmt="table")

        mock_adapter.get_repository.assert_called_once_with("other-owner", "other-repo")

    def test_outputs_repository(self, sample_config, mock_adapter, capsys):
        args = make_args(repo=None)
        with _patch_all(sample_config, mock_adapter):
            repo_cmd.handle_view(args, fmt="table")

        out = capsys.readouterr().out
        assert "test-repo" in out
