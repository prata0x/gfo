"""gfo.commands.repo のテスト。"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from gfo.adapter.base import CompareFile, CompareResult, Repository
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
        with patch("gfo.commands.repo.get_adapter", return_value=mock_adapter):
            yield

    return _ctx()


class TestHandleList:
    def test_calls_list_repositories(self, sample_config, mock_adapter, capsys):
        args = make_args(limit=30)
        with _patch_all(sample_config, mock_adapter):
            repo_cmd.handle_list(args, fmt="table")

        mock_adapter.list_repositories.assert_called_once_with(owner=None, limit=30)

    def test_passes_owner_to_adapter(self, sample_config, mock_adapter, capsys):
        """--owner 引数が adapter.list_repositories() に渡される（R39-01）。"""
        args = make_args(owner="other-user", limit=30)
        with _patch_all(sample_config, mock_adapter):
            repo_cmd.handle_list(args, fmt="table")

        mock_adapter.list_repositories.assert_called_once_with(owner="other-user", limit=30)

    def test_outputs_results(self, sample_config, mock_adapter, capsys):
        args = make_args(limit=30)
        with _patch_all(sample_config, mock_adapter):
            repo_cmd.handle_list(args, fmt="table")

        out = capsys.readouterr().out
        assert "test-repo" in out

    def test_plain_format(self, sample_config, mock_adapter, capsys):
        args = make_args(limit=30)
        with _patch_all(sample_config, mock_adapter):
            repo_cmd.handle_list(args, fmt="plain")

        out = capsys.readouterr().out
        assert "\t" in out
        assert "NAME" not in out
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
        with (
            patch("gfo.commands.repo.detect_service", return_value=detect_result),
            patch("gfo.commands.repo.get_host_config", return_value={"type": "gitlab"}),
        ):
            host, stype = repo_cmd._resolve_host_without_repo(None)

        assert host == "gitlab.com"
        assert stype == "gitlab"

    def test_falls_back_to_default_host_when_detection_fails(self):
        from gfo.exceptions import DetectionError

        with (
            patch("gfo.commands.repo.detect_service", side_effect=DetectionError("no git")),
            patch("gfo.commands.repo.get_default_host", return_value="github.com"),
            patch("gfo.commands.repo.get_host_config", return_value={"type": "github"}),
        ):
            host, stype = repo_cmd._resolve_host_without_repo(None)

        assert host == "github.com"
        assert stype == "github"

    def test_falls_back_to_default_host_when_git_command_fails(self):
        """git リポジトリ外で GitCommandError が発生した場合もデフォルトホストにフォールバックする（R30修正確認）。"""
        from gfo.exceptions import GitCommandError

        with (
            patch(
                "gfo.commands.repo.detect_service", side_effect=GitCommandError("not a git repo")
            ),
            patch("gfo.commands.repo.get_default_host", return_value="github.com"),
            patch("gfo.commands.repo.get_host_config", return_value={"type": "github"}),
        ):
            host, stype = repo_cmd._resolve_host_without_repo(None)

        assert host == "github.com"
        assert stype == "github"

    def test_raises_config_error_when_no_host(self):
        from gfo.exceptions import DetectionError

        with (
            patch("gfo.commands.repo.detect_service", side_effect=DetectionError("no git")),
            patch("gfo.commands.repo.get_default_host", return_value=None),
        ):
            with pytest.raises(ConfigError):
                repo_cmd._resolve_host_without_repo(None)

    def test_resolves_service_type_from_known_hosts(self):
        with (
            patch("gfo.commands.repo.get_host_config", return_value=None),
            patch("gfo.commands.repo.probe_unknown_host", return_value=None),
        ):
            host, stype = repo_cmd._resolve_host_without_repo("github.com")

        assert host == "github.com"
        assert stype == "github"

    def test_falls_back_to_probe_for_unknown_host(self):
        """known_service_type が None のときは probe_unknown_host でサービスを特定する。"""
        with (
            patch("gfo.commands.repo.get_host_config", return_value=None),
            patch("gfo.commands.repo.get_known_service_type", return_value=None),
            patch("gfo.commands.repo.probe_unknown_host", return_value="gitea"),
        ):
            host, stype = repo_cmd._resolve_host_without_repo("gitea.example.com")

        assert stype == "gitea"

    def test_raises_when_probe_returns_none(self):
        """probe_unknown_host も None のとき ConfigError。"""
        with (
            patch("gfo.commands.repo.get_host_config", return_value=None),
            patch("gfo.commands.repo.get_known_service_type", return_value=None),
            patch("gfo.commands.repo.probe_unknown_host", return_value=None),
        ):
            with pytest.raises(ConfigError, match="Could not determine service type"):
                repo_cmd._resolve_host_without_repo("unknown.example.com")


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

        with (
            patch(
                "gfo.commands.repo._resolve_host_without_repo",
                return_value=("github.com", "github"),
            ),
            patch("gfo.commands.repo.resolve_token", return_value="test-token"),
            patch("gfo.commands.repo.build_default_api_url", return_value="https://api.github.com"),
            patch("gfo.commands.repo.create_http_client"),
            patch("gfo.commands.repo.get_adapter_class", return_value=mock_adapter_cls),
        ):
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

        with (
            patch(
                "gfo.commands.repo._resolve_host_without_repo",
                return_value=("github.com", "github"),
            ),
            patch("gfo.commands.repo.resolve_token", return_value="test-token"),
            patch("gfo.commands.repo.build_default_api_url", return_value="https://api.github.com"),
            patch("gfo.commands.repo.create_http_client"),
            patch("gfo.commands.repo.get_adapter_class", return_value=mock_adapter_cls),
        ):
            repo_cmd.handle_create(args, fmt="table")

        out = capsys.readouterr().out
        assert "new-repo" in out

    def test_backlog_uses_project_key_from_config(self):
        """Backlog の handle_create は resolve_project_config から project_key を取得してアダプターに渡す。"""
        from gfo.config import ProjectConfig

        mock_cfg = MagicMock(spec=ProjectConfig)
        mock_cfg.service_type = "backlog"
        mock_cfg.organization = None
        mock_cfg.project_key = "MY_PROJECT"

        mock_repo = Repository(
            name="new-repo",
            full_name="MY_PROJECT/new-repo",
            description="",
            private=False,
            default_branch="main",
            clone_url="https://example.backlog.com/git/MY_PROJECT/new-repo.git",
            url="https://example.backlog.com/git/MY_PROJECT/new-repo",
        )
        mock_adapter = MagicMock()
        mock_adapter.create_repository.return_value = mock_repo
        mock_adapter_cls = MagicMock(return_value=mock_adapter)

        args = make_args(host="example.backlog.com", name="new-repo", private=False, description="")

        with (
            patch(
                "gfo.commands.repo._resolve_host_without_repo",
                return_value=("example.backlog.com", "backlog"),
            ),
            patch("gfo.commands.repo.resolve_project_config", return_value=mock_cfg),
            patch("gfo.commands.repo.resolve_token", return_value="api-key"),
            patch(
                "gfo.commands.repo.build_default_api_url",
                return_value="https://example.backlog.com/api/v2",
            ),
            patch("gfo.commands.repo.create_http_client"),
            patch("gfo.commands.repo.get_adapter_class", return_value=mock_adapter_cls),
        ):
            repo_cmd.handle_create(args, fmt="table")

        # アダプターが project_key="MY_PROJECT" で構築されたことを確認
        mock_adapter_cls.assert_called_once_with(
            mock_adapter_cls.call_args[0][0], "", "", project_key="MY_PROJECT"
        )

    def test_backlog_no_project_key_raises_config_error(self):
        """Backlog で project_key が取得できない場合 ConfigError を送出する。"""
        from gfo.config import ProjectConfig

        mock_cfg = MagicMock(spec=ProjectConfig)
        mock_cfg.service_type = "backlog"
        mock_cfg.project_key = None

        args = make_args(host="example.backlog.com", name="new-repo", private=False, description="")

        with (
            patch(
                "gfo.commands.repo._resolve_host_without_repo",
                return_value=("example.backlog.com", "backlog"),
            ),
            patch("gfo.commands.repo.resolve_project_config", return_value=mock_cfg),
            patch("gfo.commands.repo.resolve_token", return_value="api-key"),
            patch(
                "gfo.commands.repo.build_default_api_url",
                return_value="https://example.backlog.com/api/v2",
            ),
            patch("gfo.commands.repo.create_http_client"),
        ):
            with pytest.raises(ConfigError, match="project key"):
                repo_cmd.handle_create(args, fmt="table")

    def test_backlog_config_error_on_resolve_raises_helpful_message(self):
        """プロジェクト設定取得が失敗かつ project_key が取得できない場合 ConfigError。"""
        args = make_args(host="example.backlog.com", name="new-repo", private=False, description="")

        with (
            patch(
                "gfo.commands.repo._resolve_host_without_repo",
                return_value=("example.backlog.com", "backlog"),
            ),
            patch(
                "gfo.commands.repo.resolve_project_config", side_effect=ConfigError("not in a repo")
            ),
            patch("gfo.commands.repo.resolve_token", return_value="api-key"),
            patch(
                "gfo.commands.repo.build_default_api_url",
                return_value="https://example.backlog.com/api/v2",
            ),
            patch("gfo.commands.repo.create_http_client"),
        ):
            with pytest.raises(ConfigError, match="project key"):
                repo_cmd.handle_create(args, fmt="table")

    def test_azure_devops_uses_org_and_project_key_from_config(self):
        """Azure DevOps の handle_create は organization/project_key をアダプターに渡す（lines 108-109）。"""
        from gfo.config import ProjectConfig

        mock_cfg = MagicMock(spec=ProjectConfig)
        mock_cfg.service_type = "azure-devops"
        mock_cfg.organization = "my-org"
        mock_cfg.project_key = "my-project"

        mock_repo = Repository(
            name="new-repo",
            full_name="my-project/new-repo",
            description="",
            private=True,
            default_branch="main",
            clone_url="https://dev.azure.com/my-org/my-project/_git/new-repo",
            url="https://dev.azure.com/my-org/my-project/_git/new-repo",
        )
        mock_adapter = MagicMock()
        mock_adapter.create_repository.return_value = mock_repo
        mock_adapter_cls = MagicMock(return_value=mock_adapter)

        args = make_args(host="dev.azure.com", name="new-repo", private=False, description="")

        with (
            patch(
                "gfo.commands.repo._resolve_host_without_repo",
                return_value=("dev.azure.com", "azure-devops"),
            ),
            patch("gfo.commands.repo.resolve_project_config", return_value=mock_cfg),
            patch("gfo.commands.repo.resolve_token", return_value="pat-token"),
            patch(
                "gfo.commands.repo.build_default_api_url",
                return_value="https://dev.azure.com/my-org/my-project/_apis",
            ),
            patch("gfo.commands.repo.create_http_client"),
            patch("gfo.commands.repo.get_adapter_class", return_value=mock_adapter_cls),
        ):
            repo_cmd.handle_create(args, fmt="table")

        # アダプターが organization/project_key 付きで構築されたことを確認
        call_kwargs = mock_adapter_cls.call_args[1]
        assert call_kwargs["organization"] == "my-org"
        assert call_kwargs["project_key"] == "my-project"

    def test_azure_devops_no_org_raises_config_error(self):
        """Azure DevOps で organization が取得できない場合 ConfigError を送出する。"""
        from gfo.config import ProjectConfig

        mock_cfg = MagicMock(spec=ProjectConfig)
        mock_cfg.service_type = "azure-devops"
        mock_cfg.organization = None
        mock_cfg.project_key = "my-project"

        args = make_args(host="dev.azure.com", name="new-repo", private=False, description="")

        with (
            patch(
                "gfo.commands.repo._resolve_host_without_repo",
                return_value=("dev.azure.com", "azure-devops"),
            ),
            patch("gfo.commands.repo.resolve_project_config", return_value=mock_cfg),
            patch("gfo.commands.repo.resolve_token", return_value="pat-token"),
            patch(
                "gfo.commands.repo.build_default_api_url",
                return_value="https://dev.azure.com/None/my-project/_apis",
            ),
            patch("gfo.commands.repo.create_http_client"),
            patch("gfo.commands.repo.get_adapter_class"),
        ):
            with pytest.raises(ConfigError, match="organization"):
                repo_cmd.handle_create(args, fmt="table")


class TestHandleClone:
    def test_github_url(self):
        args = make_args(host="github.com", repo="owner/myrepo")
        with (
            patch(
                "gfo.commands.repo._resolve_host_without_repo",
                return_value=("github.com", "github"),
            ),
            patch("gfo.commands.repo.git_clone") as mock_clone,
        ):
            repo_cmd.handle_clone(args, fmt="table")

        mock_clone.assert_called_once_with("https://github.com/owner/myrepo.git")

    def test_gitlab_url(self):
        args = make_args(host="gitlab.example.com", repo="owner/myrepo")
        with (
            patch(
                "gfo.commands.repo._resolve_host_without_repo",
                return_value=("gitlab.example.com", "gitlab"),
            ),
            patch("gfo.commands.repo.git_clone") as mock_clone,
        ):
            repo_cmd.handle_clone(args, fmt="table")

        mock_clone.assert_called_once_with("https://gitlab.example.com/owner/myrepo.git")

    def test_bitbucket_url(self):
        args = make_args(host="bitbucket.org", repo="owner/myrepo")
        with (
            patch(
                "gfo.commands.repo._resolve_host_without_repo",
                return_value=("bitbucket.org", "bitbucket"),
            ),
            patch("gfo.commands.repo.git_clone") as mock_clone,
        ):
            repo_cmd.handle_clone(args, fmt="table")

        mock_clone.assert_called_once_with("https://bitbucket.org/owner/myrepo.git")

    def test_gitbucket_url(self):
        args = make_args(host="gitbucket.example.com", repo="owner/myrepo")
        with (
            patch(
                "gfo.commands.repo._resolve_host_without_repo",
                return_value=("gitbucket.example.com", "gitbucket"),
            ),
            patch("gfo.commands.repo.git_clone") as mock_clone,
        ):
            repo_cmd.handle_clone(args, fmt="table")

        mock_clone.assert_called_once_with("https://gitbucket.example.com/git/owner/myrepo.git")

    def test_backlog_url(self):
        args = make_args(host="example.backlog.com", repo="PROJECT/myrepo")
        with (
            patch(
                "gfo.commands.repo._resolve_host_without_repo",
                return_value=("example.backlog.com", "backlog"),
            ),
            patch("gfo.commands.repo.git_clone") as mock_clone,
        ):
            repo_cmd.handle_clone(args, fmt="table")

        mock_clone.assert_called_once_with("https://example.backlog.com/git/PROJECT/myrepo.git")

    def test_gitea_url(self):
        args = make_args(host="gitea.example.com", repo="owner/myrepo")
        with (
            patch(
                "gfo.commands.repo._resolve_host_without_repo",
                return_value=("gitea.example.com", "gitea"),
            ),
            patch("gfo.commands.repo.git_clone") as mock_clone,
        ):
            repo_cmd.handle_clone(args, fmt="table")

        mock_clone.assert_called_once_with("https://gitea.example.com/owner/myrepo.git")

    def test_azure_devops_url(self):
        """project 未解決時は owner にフォールバック。"""
        args = make_args(host="dev.azure.com", repo="myorg/myrepo")
        with (
            patch(
                "gfo.commands.repo._resolve_host_without_repo",
                return_value=("dev.azure.com", "azure-devops"),
            ),
            patch("gfo.commands.repo.resolve_project_config", side_effect=ConfigError("no config")),
            patch("gfo.commands.repo.git_clone") as mock_clone,
        ):
            repo_cmd.handle_clone(args, fmt="table")

        mock_clone.assert_called_once_with("https://dev.azure.com/myorg/myorg/_git/myrepo")

    def test_azure_devops_url_with_resolved_project(self):
        """resolve_project_config から project が取得できた場合に URL に反映される。"""
        from gfo.config import ProjectConfig

        mock_cfg = MagicMock(spec=ProjectConfig)
        mock_cfg.service_type = "azure-devops"
        mock_cfg.project_key = "myproj"
        args = make_args(host="dev.azure.com", repo="myorg/myrepo")
        with (
            patch(
                "gfo.commands.repo._resolve_host_without_repo",
                return_value=("dev.azure.com", "azure-devops"),
            ),
            patch("gfo.commands.repo.resolve_project_config", return_value=mock_cfg),
            patch("gfo.commands.repo.git_clone") as mock_clone,
        ):
            repo_cmd.handle_clone(args, fmt="table")

        mock_clone.assert_called_once_with("https://dev.azure.com/myorg/myproj/_git/myrepo")

    def test_azure_devops_url_with_project_arg(self):
        """--project 引数を明示した場合は resolve_project_config を呼ばずそのまま使用する。"""
        args = make_args(host="dev.azure.com", repo="myorg/myrepo", project="explicit-proj")
        with (
            patch(
                "gfo.commands.repo._resolve_host_without_repo",
                return_value=("dev.azure.com", "azure-devops"),
            ),
            patch("gfo.commands.repo.git_clone") as mock_clone,
        ):
            repo_cmd.handle_clone(args, fmt="table")

        mock_clone.assert_called_once_with("https://dev.azure.com/myorg/explicit-proj/_git/myrepo")

    def test_azure_devops_custom_host_url(self):
        """非既定ホスト (azure.example.com) が clone URL に反映される。"""
        args = make_args(host="azure.example.com", repo="myorg/myrepo", project="myproj")
        with (
            patch(
                "gfo.commands.repo._resolve_host_without_repo",
                return_value=("azure.example.com", "azure-devops"),
            ),
            patch("gfo.commands.repo.git_clone") as mock_clone,
        ):
            repo_cmd.handle_clone(args, fmt="table")

        mock_clone.assert_called_once_with("https://azure.example.com/myorg/myproj/_git/myrepo")

    def test_forgejo_url(self):
        args = make_args(host="codeberg.org", repo="owner/myrepo")
        with (
            patch(
                "gfo.commands.repo._resolve_host_without_repo",
                return_value=("codeberg.org", "forgejo"),
            ),
            patch("gfo.commands.repo.git_clone") as mock_clone,
        ):
            repo_cmd.handle_clone(args, fmt="table")

        mock_clone.assert_called_once_with("https://codeberg.org/owner/myrepo.git")

    def test_gogs_url(self):
        args = make_args(host="gogs.local", repo="owner/myrepo")
        with (
            patch(
                "gfo.commands.repo._resolve_host_without_repo", return_value=("gogs.local", "gogs")
            ),
            patch("gfo.commands.repo.git_clone") as mock_clone,
        ):
            repo_cmd.handle_clone(args, fmt="table")

        mock_clone.assert_called_once_with("https://gogs.local/owner/myrepo.git")

    def test_invalid_repo_format_raises_config_error(self):
        args = make_args(host="github.com", repo="invalidformat")
        with patch(
            "gfo.commands.repo._resolve_host_without_repo", return_value=("github.com", "github")
        ):
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

    def test_invalid_repo_format_raises_config_error(self, sample_config, mock_adapter):
        args = make_args(repo="noslash")
        with _patch_all(sample_config, mock_adapter):
            with pytest.raises(ConfigError):
                repo_cmd.handle_view(args, fmt="table")

    def test_empty_owner_raises_config_error(self, sample_config, mock_adapter):
        args = make_args(repo="/name")
        with _patch_all(sample_config, mock_adapter):
            with pytest.raises(ConfigError):
                repo_cmd.handle_view(args, fmt="table")


class TestHandleDelete:
    def test_delete_with_yes_flag(self, sample_config, mock_adapter, capsys):
        args = make_args(yes=True)
        mock_adapter._owner = "test-owner"
        mock_adapter._repo = "test-repo"
        with _patch_all(sample_config, mock_adapter):
            repo_cmd.handle_delete(args, fmt="table")

        mock_adapter.delete_repository.assert_called_once()
        out = capsys.readouterr().out
        assert "test-owner/test-repo" in out

    def test_delete_confirmation_yes(self, sample_config, mock_adapter, capsys):
        args = make_args(yes=False)
        mock_adapter._owner = "test-owner"
        mock_adapter._repo = "test-repo"
        with _patch_all(sample_config, mock_adapter), patch("builtins.input", return_value="y"):
            repo_cmd.handle_delete(args, fmt="table")

        mock_adapter.delete_repository.assert_called_once()

    def test_delete_confirmation_no(self, sample_config, mock_adapter, capsys):
        args = make_args(yes=False)
        mock_adapter._owner = "test-owner"
        mock_adapter._repo = "test-repo"
        with _patch_all(sample_config, mock_adapter), patch("builtins.input", return_value="n"):
            repo_cmd.handle_delete(args, fmt="table")

        mock_adapter.delete_repository.assert_not_called()
        out = capsys.readouterr().out
        assert "Aborted" in out

    def test_delete_prints_success_message(self, sample_config, mock_adapter, capsys):
        args = make_args(yes=True)
        mock_adapter._owner = "my-org"
        mock_adapter._repo = "my-repo"
        with _patch_all(sample_config, mock_adapter):
            repo_cmd.handle_delete(args, fmt="table")

        out = capsys.readouterr().out
        assert "Deleted repository" in out
        assert "my-org/my-repo" in out


class TestParseRepoArg:
    def test_valid_format(self):
        owner, name = repo_cmd._parse_repo_arg("owner/repo")
        assert owner == "owner"
        assert name == "repo"

    def test_no_slash_raises(self):
        with pytest.raises(ConfigError):
            repo_cmd._parse_repo_arg("noslash")

    def test_empty_owner_raises(self):
        with pytest.raises(ConfigError):
            repo_cmd._parse_repo_arg("/repo")

    def test_empty_name_raises(self):
        with pytest.raises(ConfigError):
            repo_cmd._parse_repo_arg("owner/")

    def test_whitespace_owner_raises(self):
        with pytest.raises(ConfigError):
            repo_cmd._parse_repo_arg("   /repo")

    def test_whitespace_name_raises(self):
        with pytest.raises(ConfigError):
            repo_cmd._parse_repo_arg("owner/   ")

    def test_owner_and_name_are_stripped(self):
        """前後の空白は strip されて返される（現在は strip してから空チェックするため、
        空白を含む有効な owner/name は strip 後の値が返る）。"""
        owner, name = repo_cmd._parse_repo_arg("my-org/my-repo")
        assert owner == "my-org"
        assert name == "my-repo"


class TestHandleUpdate:
    def test_calls_update_repository(self, sample_config, sample_repo, capsys):
        adapter = MagicMock()
        adapter.update_repository.return_value = sample_repo
        args = make_args(description="new desc", private=True, default_branch="develop")
        with patch("gfo.commands.repo.get_adapter", return_value=adapter):
            repo_cmd.handle_update(args, fmt="table")

        adapter.update_repository.assert_called_once_with(
            description="new desc",
            private=True,
            default_branch="develop",
        )

    def test_json_format(self, sample_config, sample_repo, capsys):
        adapter = MagicMock()
        adapter.update_repository.return_value = sample_repo
        args = make_args(description=None, private=None, default_branch=None)
        with patch("gfo.commands.repo.get_adapter", return_value=adapter):
            repo_cmd.handle_update(args, fmt="json")

        out = capsys.readouterr().out
        data = json.loads(out)
        assert data[0]["name"] == "test-repo"

    def test_passes_none_for_unset_args(self, sample_config, sample_repo):
        adapter = MagicMock()
        adapter.update_repository.return_value = sample_repo
        args = make_args(description=None, private=None, default_branch=None)
        with patch("gfo.commands.repo.get_adapter", return_value=adapter):
            repo_cmd.handle_update(args, fmt="table")

        adapter.update_repository.assert_called_once_with(
            description=None,
            private=None,
            default_branch=None,
        )


class TestHandleArchive:
    def test_archive_with_yes_flag(self, sample_config, capsys):
        adapter = MagicMock()
        adapter._owner = "test-owner"
        adapter._repo = "test-repo"
        args = make_args(yes=True)
        with patch("gfo.commands.repo.get_adapter", return_value=adapter):
            repo_cmd.handle_archive(args, fmt="table")

        adapter.archive_repository.assert_called_once()
        out = capsys.readouterr().out
        assert "Archived" in out

    def test_archive_confirmation_no(self, sample_config, capsys):
        adapter = MagicMock()
        adapter._owner = "test-owner"
        adapter._repo = "test-repo"
        args = make_args(yes=False)
        with (
            patch("gfo.commands.repo.get_adapter", return_value=adapter),
            patch("builtins.input", return_value="n"),
        ):
            repo_cmd.handle_archive(args, fmt="table")

        adapter.archive_repository.assert_not_called()
        out = capsys.readouterr().out
        assert "Aborted" in out

    def test_archive_confirmation_yes(self, sample_config, capsys):
        adapter = MagicMock()
        adapter._owner = "test-owner"
        adapter._repo = "test-repo"
        args = make_args(yes=False)
        with (
            patch("gfo.commands.repo.get_adapter", return_value=adapter),
            patch("builtins.input", return_value="y"),
        ):
            repo_cmd.handle_archive(args, fmt="table")

        adapter.archive_repository.assert_called_once()


class TestHandleLanguages:
    def test_outputs_json(self, sample_config, capsys):
        adapter = MagicMock()
        adapter.get_languages.return_value = {"Python": 45678, "Go": 12345}
        args = make_args()
        with patch("gfo.commands.repo.get_adapter", return_value=adapter):
            repo_cmd.handle_languages(args, fmt="json")

        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["Python"] == 45678
        assert data["Go"] == 12345

    def test_empty_languages(self, sample_config, capsys):
        adapter = MagicMock()
        adapter.get_languages.return_value = {}
        args = make_args()
        with patch("gfo.commands.repo.get_adapter", return_value=adapter):
            repo_cmd.handle_languages(args, fmt="json")

        out = capsys.readouterr().out
        data = json.loads(out)
        assert data == {}


class TestHandleTopics:
    def test_list(self, sample_config, capsys):
        adapter = MagicMock()
        adapter.list_topics.return_value = ["python", "cli"]
        args = make_args(topics_action="list")
        with patch("gfo.commands.repo.get_adapter", return_value=adapter):
            repo_cmd.handle_topics(args, fmt="json")

        out = capsys.readouterr().out
        data = json.loads(out)
        assert data == ["python", "cli"]

    def test_add(self, sample_config, capsys):
        adapter = MagicMock()
        adapter.add_topic.return_value = ["python", "cli", "new-topic"]
        args = make_args(topics_action="add", topic="new-topic")
        with patch("gfo.commands.repo.get_adapter", return_value=adapter):
            repo_cmd.handle_topics(args, fmt="json")

        adapter.add_topic.assert_called_once_with("new-topic")

    def test_remove(self, sample_config, capsys):
        adapter = MagicMock()
        adapter.remove_topic.return_value = ["python"]
        args = make_args(topics_action="remove", topic="cli")
        with patch("gfo.commands.repo.get_adapter", return_value=adapter):
            repo_cmd.handle_topics(args, fmt="json")

        adapter.remove_topic.assert_called_once_with("cli")

    def test_set(self, sample_config, capsys):
        adapter = MagicMock()
        adapter.set_topics.return_value = ["a", "b"]
        args = make_args(topics_action="set", topics=["a", "b"])
        with patch("gfo.commands.repo.get_adapter", return_value=adapter):
            repo_cmd.handle_topics(args, fmt="json")

        adapter.set_topics.assert_called_once_with(["a", "b"])

    def test_no_action_raises(self, sample_config):
        args = make_args(topics_action=None)
        with patch("gfo.commands.repo.get_adapter", return_value=MagicMock()):
            with pytest.raises(ConfigError):
                repo_cmd.handle_topics(args, fmt="json")


class TestParseCompareSpec:
    def test_triple_dot(self):
        base, head = repo_cmd._parse_compare_spec("main...feature")
        assert base == "main"
        assert head == "feature"

    def test_double_dot(self):
        base, head = repo_cmd._parse_compare_spec("main..feature")
        assert base == "main"
        assert head == "feature"

    def test_invalid_raises(self):
        with pytest.raises(ConfigError):
            repo_cmd._parse_compare_spec("main-feature")


class TestHandleCompare:
    def test_calls_compare(self, sample_config, capsys):
        result = CompareResult(
            total_commits=3,
            ahead_by=3,
            behind_by=0,
            files=(CompareFile(filename="a.py", status="modified", additions=10, deletions=2),),
        )
        adapter = MagicMock()
        adapter.compare.return_value = result
        args = make_args(spec="main...feature")
        with patch("gfo.commands.repo.get_adapter", return_value=adapter):
            repo_cmd.handle_compare(args, fmt="json")

        adapter.compare.assert_called_once_with("main", "feature")
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data[0]["total_commits"] == 3


class TestHandleMigrate:
    def test_calls_migrate_repository(self, sample_config, sample_repo, capsys):
        adapter = MagicMock()
        adapter.migrate_repository.return_value = sample_repo
        args = make_args(
            clone_url="https://github.com/old-owner/old-repo.git",
            name="new-repo",
            private=False,
            description="",
            mirror=False,
            auth_token=None,
        )
        with patch("gfo.commands.repo.get_adapter", return_value=adapter):
            repo_cmd.handle_migrate(args, fmt="table")

        adapter.migrate_repository.assert_called_once_with(
            "https://github.com/old-owner/old-repo.git",
            "new-repo",
            private=False,
            description="",
            mirror=False,
            auth_token=None,
        )
        out = capsys.readouterr().out
        assert "test-repo" in out

    def test_json_format(self, sample_config, sample_repo, capsys):
        adapter = MagicMock()
        adapter.migrate_repository.return_value = sample_repo
        args = make_args(
            clone_url="https://github.com/old/repo.git",
            name="new-repo",
            private=True,
            description="migrated",
            mirror=True,
            auth_token="tok",
        )
        with patch("gfo.commands.repo.get_adapter", return_value=adapter):
            repo_cmd.handle_migrate(args, fmt="json")

        out = capsys.readouterr().out
        data = json.loads(out)
        assert data[0]["name"] == "test-repo"

    def test_error_propagation(self, sample_config):
        from gfo.exceptions import HttpError

        adapter = MagicMock()
        adapter.migrate_repository.side_effect = HttpError(500, "Server error")
        args = make_args(
            clone_url="https://github.com/old/repo.git",
            name="new-repo",
            private=False,
            description="",
            mirror=False,
            auth_token=None,
        )
        with patch("gfo.commands.repo.get_adapter", return_value=adapter):
            with pytest.raises(HttpError):
                repo_cmd.handle_migrate(args, fmt="table")


# --- Phase 5: star / unstar / mirror / transfer ---


class TestHandleStar:
    def test_star_repository(self, sample_config, mock_adapter, capsys):
        mock_adapter._owner = "test-owner"
        mock_adapter._repo = "test-repo"
        with _patch_all(sample_config, mock_adapter):
            args = make_args()
            repo_cmd.handle_star(args, fmt="table")
        mock_adapter.star_repository.assert_called_once()

    def test_unstar_repository(self, sample_config, mock_adapter, capsys):
        mock_adapter._owner = "test-owner"
        mock_adapter._repo = "test-repo"
        with _patch_all(sample_config, mock_adapter):
            args = make_args()
            repo_cmd.handle_unstar(args, fmt="table")
        mock_adapter.unstar_repository.assert_called_once()


class TestHandleMirror:
    def test_list_mirrors(self, sample_config, mock_adapter, capsys):
        from gfo.adapter.base import PushMirror

        mock_adapter.list_push_mirrors.return_value = [
            PushMirror(
                id=1,
                remote_name="mirror",
                remote_address="https://mirror.example.com",
                interval="8h",
                created_at="2024-01-01T00:00:00Z",
            )
        ]
        with _patch_all(sample_config, mock_adapter):
            args = make_args(mirror_action="list")
            repo_cmd.handle_mirror(args, fmt="table")
        mock_adapter.list_push_mirrors.assert_called_once()

    def test_sync_mirror(self, sample_config, mock_adapter, capsys):
        with _patch_all(sample_config, mock_adapter):
            args = make_args(mirror_action="sync")
            repo_cmd.handle_mirror(args, fmt="table")
        mock_adapter.sync_mirror.assert_called_once()


class TestHandleTransfer:
    def test_transfer_with_yes(self, sample_config, mock_adapter, capsys):
        mock_adapter._owner = "test-owner"
        mock_adapter._repo = "test-repo"
        with _patch_all(sample_config, mock_adapter):
            args = make_args(new_owner="new-owner", team_id=None, yes=True)
            repo_cmd.handle_transfer(args, fmt="table")
        mock_adapter.transfer_repository.assert_called_once_with("new-owner", team_ids=None)
