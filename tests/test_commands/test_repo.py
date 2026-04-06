"""gfo.commands.repo のテスト。"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from gfo.adapter.base import CompareFile, CompareResult, Contributor, Repository
from gfo.commands import repo as repo_cmd
from gfo.exceptions import ConfigError
from tests.test_commands.conftest import make_args


@pytest.fixture
def sample_repo():
    return Repository(
        name="test-repo",
        full_name="test-owner/test-repo",
        description="A test repo",
        visibility="public",
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
        args = make_args(limit=30, archived=None)
        with _patch_all(sample_config, mock_adapter):
            repo_cmd.handle_list(args, fmt="table")

        mock_adapter.list_repositories.assert_called_once_with(
            owner=None, limit=30, archived=None, visibility=None
        )

    def test_passes_owner_to_adapter(self, sample_config, mock_adapter, capsys):
        """--owner 引数が adapter.list_repositories() に渡される（R39-01）。"""
        args = make_args(owner="other-user", limit=30, archived=None)
        with _patch_all(sample_config, mock_adapter):
            repo_cmd.handle_list(args, fmt="table")

        mock_adapter.list_repositories.assert_called_once_with(
            owner="other-user", limit=30, archived=None, visibility=None
        )

    def test_outputs_results(self, sample_config, mock_adapter, capsys):
        args = make_args(limit=30, archived=None)
        with _patch_all(sample_config, mock_adapter):
            repo_cmd.handle_list(args, fmt="table")

        out = capsys.readouterr().out
        assert "test-repo" in out

    def test_plain_format(self, sample_config, mock_adapter, capsys):
        args = make_args(limit=30, archived=None)
        with _patch_all(sample_config, mock_adapter):
            repo_cmd.handle_list(args, fmt="plain")

        out = capsys.readouterr().out
        assert "\t" in out
        assert "NAME" not in out
        assert "test-repo" in out

    def test_passes_archived_filter(self, sample_config, mock_adapter, capsys):
        """--archived フラグが adapter.list_repositories() に渡される。"""
        args = make_args(owner=None, limit=30, archived=True)
        with _patch_all(sample_config, mock_adapter):
            repo_cmd.handle_list(args, fmt="table")

        mock_adapter.list_repositories.assert_called_once_with(
            owner=None, limit=30, archived=True, visibility=None
        )

    def test_passes_visibility_filter(self, sample_config, mock_adapter, capsys):
        """--visibility フラグが adapter.list_repositories() に渡される。"""
        args = make_args(owner=None, limit=30, archived=None, visibility="private")
        with _patch_all(sample_config, mock_adapter):
            repo_cmd.handle_list(args, fmt="table")

        mock_adapter.list_repositories.assert_called_once_with(
            owner=None, limit=30, archived=None, visibility="private"
        )


class TestHandleContributors:
    def setup_method(self):
        self.contributors = [
            Contributor(username="alice", name="Alice", email="alice@example.com", commits=100),
            Contributor(username="bob", name="Bob", email="bob@example.com", commits=50),
        ]

    def test_calls_list_contributors(self, sample_config):
        adapter = MagicMock()
        adapter.list_contributors.return_value = self.contributors
        with _patch_all(sample_config, adapter):
            args = make_args(limit=30)
            repo_cmd.handle_contributors(args, fmt="table")
        adapter.list_contributors.assert_called_once_with(limit=30)

    def test_json_format(self, sample_config, capsys):
        adapter = MagicMock()
        adapter.list_contributors.return_value = self.contributors
        with _patch_all(sample_config, adapter):
            args = make_args(limit=30)
            repo_cmd.handle_contributors(args, fmt="json")
        data = json.loads(capsys.readouterr().out)
        assert len(data) == 2
        assert data[0]["username"] == "alice"
        assert data[0]["commits"] == 100

    def test_table_output(self, sample_config, capsys):
        adapter = MagicMock()
        adapter.list_contributors.return_value = self.contributors
        with _patch_all(sample_config, adapter):
            args = make_args(limit=30)
            repo_cmd.handle_contributors(args, fmt="table")
        out = capsys.readouterr().out
        assert "alice" in out
        assert "bob" in out

    def test_empty_contributors_list(self, sample_config, capsys):
        """コントリビューターが空の場合、空の JSON 配列が出力される。"""
        adapter = MagicMock()
        adapter.list_contributors.return_value = []
        with _patch_all(sample_config, adapter):
            args = make_args(limit=30)
            repo_cmd.handle_contributors(args, fmt="json")
        data = json.loads(capsys.readouterr().out)
        assert data == []


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


class TestParseCreateName:
    def test_simple_name(self):
        org, name = repo_cmd._parse_create_name("my-repo")
        assert org is None
        assert name == "my-repo"

    def test_org_name(self):
        org, name = repo_cmd._parse_create_name("my-org/my-repo")
        assert org == "my-org"
        assert name == "my-repo"

    def test_empty_org_raises(self):
        with pytest.raises(ConfigError, match="Invalid name format"):
            repo_cmd._parse_create_name("/my-repo")

    def test_empty_name_raises(self):
        with pytest.raises(ConfigError, match="Invalid name format"):
            repo_cmd._parse_create_name("my-org/")


class TestHandleCreate:
    def test_calls_create_repository(self, capsys):
        args = make_args(
            host="github.com", name="new-repo", visibility="public", description="", readme=False
        )
        mock_repo = Repository(
            name="new-repo",
            full_name="test-owner/new-repo",
            description="",
            visibility="public",
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
            visibility="public",
            description="",
            auto_init=False,
            organization=None,
        )

    def test_calls_create_with_readme(self, capsys):
        """--readme フラグが auto_init=True として渡される。"""
        args = make_args(
            host="github.com", name="new-repo", visibility="public", description="", readme=True
        )
        mock_repo = Repository(
            name="new-repo",
            full_name="test-owner/new-repo",
            description="",
            visibility="public",
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
            visibility="public",
            description="",
            auto_init=True,
            organization=None,
        )

    def test_outputs_created_repository(self, capsys):
        args = make_args(
            host="github.com",
            name="new-repo",
            visibility="private",
            description="desc",
            readme=False,
        )
        mock_repo = Repository(
            name="new-repo",
            full_name="test-owner/new-repo",
            description="desc",
            visibility="private",
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
            visibility="public",
            default_branch="main",
            clone_url="https://example.backlog.com/git/MY_PROJECT/new-repo.git",
            url="https://example.backlog.com/git/MY_PROJECT/new-repo",
        )
        mock_adapter = MagicMock()
        mock_adapter.create_repository.return_value = mock_repo
        mock_adapter_cls = MagicMock(return_value=mock_adapter)

        args = make_args(
            host="example.backlog.com", name="new-repo", visibility="public", description=""
        )

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

        args = make_args(
            host="example.backlog.com", name="new-repo", visibility="public", description=""
        )

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
        args = make_args(
            host="example.backlog.com", name="new-repo", visibility="public", description=""
        )

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
            visibility="private",
            default_branch="main",
            clone_url="https://dev.azure.com/my-org/my-project/_git/new-repo",
            url="https://dev.azure.com/my-org/my-project/_git/new-repo",
        )
        mock_adapter = MagicMock()
        mock_adapter.create_repository.return_value = mock_repo
        mock_adapter_cls = MagicMock(return_value=mock_adapter)

        args = make_args(host="dev.azure.com", name="new-repo", visibility="public", description="")

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

        args = make_args(host="dev.azure.com", name="new-repo", visibility="public", description="")

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

    def test_org_repo_creation(self, capsys):
        """org/name 形式で組織リポジトリを作成する。"""
        args = make_args(
            host="github.com",
            name="my-org/new-repo",
            visibility="private",
            description="",
            readme=False,
        )
        mock_repo = Repository(
            name="new-repo",
            full_name="my-org/new-repo",
            description="",
            visibility="private",
            default_branch="main",
            clone_url="https://github.com/my-org/new-repo.git",
            url="https://github.com/my-org/new-repo",
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
            visibility="private",
            description="",
            auto_init=False,
            organization="my-org",
        )

    def test_internal_requires_org(self):
        """--internal は org/name 形式が必要。"""
        args = make_args(
            host="github.com", name="solo-repo", visibility="internal", description="", readme=False
        )
        with pytest.raises(ConfigError, match="--internal requires an organization"):
            repo_cmd.handle_create(args, fmt="table")

    def test_internal_with_org(self, capsys):
        """--internal + org/name で成功する。"""
        args = make_args(
            host="github.com",
            name="my-org/new-repo",
            visibility="internal",
            description="",
            readme=False,
        )
        mock_repo = Repository(
            name="new-repo",
            full_name="my-org/new-repo",
            description="",
            visibility="internal",
            default_branch="main",
            clone_url="https://github.com/my-org/new-repo.git",
            url="https://github.com/my-org/new-repo",
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
            visibility="internal",
            description="",
            auto_init=False,
            organization="my-org",
        )


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
        mock_adapter.owner = "test-owner"
        mock_adapter.repo = "test-repo"
        with _patch_all(sample_config, mock_adapter):
            repo_cmd.handle_delete(args, fmt="table")

        mock_adapter.delete_repository.assert_called_once()
        out = capsys.readouterr().out
        assert "test-owner/test-repo" in out

    def test_delete_confirmation_yes(self, sample_config, mock_adapter, capsys):
        args = make_args(yes=False)
        mock_adapter.owner = "test-owner"
        mock_adapter.repo = "test-repo"
        with _patch_all(sample_config, mock_adapter), patch("builtins.input", return_value="y"):
            repo_cmd.handle_delete(args, fmt="table")

        mock_adapter.delete_repository.assert_called_once()

    def test_delete_confirmation_no(self, sample_config, mock_adapter, capsys):
        args = make_args(yes=False)
        mock_adapter.owner = "test-owner"
        mock_adapter.repo = "test-repo"
        with _patch_all(sample_config, mock_adapter), patch("builtins.input", return_value="n"):
            repo_cmd.handle_delete(args, fmt="table")

        mock_adapter.delete_repository.assert_not_called()
        out = capsys.readouterr().out
        assert "Aborted" in out

    def test_delete_prints_success_message(self, sample_config, mock_adapter, capsys):
        args = make_args(yes=True)
        mock_adapter.owner = "my-org"
        mock_adapter.repo = "my-repo"
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


class TestHandleEdit:
    def test_calls_update_repository(self, sample_config, sample_repo, capsys):
        adapter = MagicMock()
        adapter.update_repository.return_value = sample_repo
        args = make_args(name=None, description="new desc", private=True, default_branch="develop")
        with patch("gfo.commands.repo.get_adapter", return_value=adapter):
            repo_cmd.handle_edit(args, fmt="table")

        adapter.update_repository.assert_called_once_with(
            name=None,
            description="new desc",
            private=True,
            default_branch="develop",
            allow_merge_commit=None,
            allow_squash_merge=None,
            allow_rebase_merge=None,
            delete_branch_on_merge=None,
        )

    def test_json_format(self, sample_config, sample_repo, capsys):
        adapter = MagicMock()
        adapter.update_repository.return_value = sample_repo
        args = make_args(name=None, description=None, private=None, default_branch=None)
        with patch("gfo.commands.repo.get_adapter", return_value=adapter):
            repo_cmd.handle_edit(args, fmt="json")

        out = capsys.readouterr().out
        data = json.loads(out)
        assert data[0]["name"] == "test-repo"

    def test_passes_none_for_unset_args(self, sample_config, sample_repo):
        adapter = MagicMock()
        adapter.update_repository.return_value = sample_repo
        args = make_args(name=None, description=None, private=None, default_branch=None)
        with patch("gfo.commands.repo.get_adapter", return_value=adapter):
            repo_cmd.handle_edit(args, fmt="table")

        adapter.update_repository.assert_called_once_with(
            name=None,
            description=None,
            private=None,
            default_branch=None,
            allow_merge_commit=None,
            allow_squash_merge=None,
            allow_rebase_merge=None,
            delete_branch_on_merge=None,
        )

    def test_rename_shows_warning(self, sample_config, sample_repo, capsys):
        adapter = MagicMock()
        adapter.update_repository.return_value = sample_repo
        args = make_args(name="new-name", description=None, private=None, default_branch=None)
        with patch("gfo.commands.repo.get_adapter", return_value=adapter):
            repo_cmd.handle_edit(args, fmt="table")

        adapter.update_repository.assert_called_once_with(
            name="new-name",
            description=None,
            private=None,
            default_branch=None,
            allow_merge_commit=None,
            allow_squash_merge=None,
            allow_rebase_merge=None,
            delete_branch_on_merge=None,
        )
        err = capsys.readouterr().err
        assert "remote" in err.lower() or "renamed" in err.lower()

    def test_no_warning_without_name(self, sample_config, sample_repo, capsys):
        adapter = MagicMock()
        adapter.update_repository.return_value = sample_repo
        args = make_args(name=None, description="desc", private=None, default_branch=None)
        with patch("gfo.commands.repo.get_adapter", return_value=adapter):
            repo_cmd.handle_edit(args, fmt="table")

        err = capsys.readouterr().err
        assert err == ""


class TestHandleEditMergeStrategy:
    def test_merge_strategy_options_passed(self, sample_config, sample_repo):
        adapter = MagicMock()
        adapter.update_repository.return_value = sample_repo
        args = make_args(
            name=None,
            description=None,
            private=None,
            default_branch=None,
            allow_merge_commit=True,
            allow_squash_merge=False,
            allow_rebase_merge=None,
            delete_branch_on_merge=True,
        )
        with patch("gfo.commands.repo.get_adapter", return_value=adapter):
            repo_cmd.handle_edit(args, fmt="table")

        adapter.update_repository.assert_called_once_with(
            name=None,
            description=None,
            private=None,
            default_branch=None,
            allow_merge_commit=True,
            allow_squash_merge=False,
            allow_rebase_merge=None,
            delete_branch_on_merge=True,
        )

    def test_delete_branch_on_merge_false(self, sample_config, sample_repo):
        adapter = MagicMock()
        adapter.update_repository.return_value = sample_repo
        args = make_args(
            name=None,
            description=None,
            private=None,
            default_branch=None,
            allow_merge_commit=None,
            allow_squash_merge=None,
            allow_rebase_merge=None,
            delete_branch_on_merge=False,
        )
        with patch("gfo.commands.repo.get_adapter", return_value=adapter):
            repo_cmd.handle_edit(args, fmt="table")

        call_kwargs = adapter.update_repository.call_args.kwargs
        assert call_kwargs["delete_branch_on_merge"] is False

    def test_all_merge_options_none(self, sample_config, sample_repo):
        """全マージオプションが None の場合、adapter に None が渡される。"""
        adapter = MagicMock()
        adapter.update_repository.return_value = sample_repo
        args = make_args(
            name=None,
            description=None,
            private=None,
            default_branch=None,
            allow_merge_commit=None,
            allow_squash_merge=None,
            allow_rebase_merge=None,
            delete_branch_on_merge=None,
        )
        with patch("gfo.commands.repo.get_adapter", return_value=adapter):
            repo_cmd.handle_edit(args, fmt="table")

        call_kwargs = adapter.update_repository.call_args.kwargs
        assert call_kwargs["allow_merge_commit"] is None
        assert call_kwargs["allow_squash_merge"] is None
        assert call_kwargs["allow_rebase_merge"] is None
        assert call_kwargs["delete_branch_on_merge"] is None


class TestHandleArchive:
    def test_archive_with_yes_flag(self, sample_config, capsys):
        adapter = MagicMock()
        adapter.owner = "test-owner"
        adapter.repo = "test-repo"
        args = make_args(yes=True)
        with patch("gfo.commands.repo.get_adapter", return_value=adapter):
            repo_cmd.handle_archive(args, fmt="table")

        adapter.archive_repository.assert_called_once()
        out = capsys.readouterr().out
        assert "Archived" in out

    def test_archive_confirmation_no(self, sample_config, capsys):
        adapter = MagicMock()
        adapter.owner = "test-owner"
        adapter.repo = "test-repo"
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
        adapter.owner = "test-owner"
        adapter.repo = "test-repo"
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
            visibility="public",
            description="",
            mirror=False,
            auth_token=None,
        )
        with patch("gfo.commands.repo.get_adapter", return_value=adapter):
            repo_cmd.handle_migrate(args, fmt="table")

        adapter.migrate_repository.assert_called_once_with(
            "https://github.com/old-owner/old-repo.git",
            "new-repo",
            visibility="public",
            description="",
            mirror=False,
            auth_token=None,
            organization=None,
        )
        out = capsys.readouterr().out
        assert "test-repo" in out

    def test_json_format(self, sample_config, sample_repo, capsys):
        adapter = MagicMock()
        adapter.migrate_repository.return_value = sample_repo
        args = make_args(
            clone_url="https://github.com/old/repo.git",
            name="new-repo",
            visibility="private",
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
            visibility="public",
            description="",
            mirror=False,
            auth_token=None,
        )
        with patch("gfo.commands.repo.get_adapter", return_value=adapter):
            with pytest.raises(HttpError):
                repo_cmd.handle_migrate(args, fmt="table")

    def test_org_repo_migration(self, sample_config, sample_repo, capsys):
        """org/name 形式で組織にリポジトリを migrate する。"""
        adapter = MagicMock()
        adapter.migrate_repository.return_value = sample_repo
        args = make_args(
            clone_url="https://github.com/old/repo.git",
            name="my-org/new-repo",
            visibility="private",
            description="",
            mirror=False,
            auth_token=None,
        )
        with patch("gfo.commands.repo.get_adapter", return_value=adapter):
            repo_cmd.handle_migrate(args, fmt="table")

        adapter.migrate_repository.assert_called_once_with(
            "https://github.com/old/repo.git",
            "new-repo",
            visibility="private",
            description="",
            mirror=False,
            auth_token=None,
            organization="my-org",
        )

    def test_migrate_internal_requires_org(self, sample_config):
        """migrate で --internal は org/name 形式が必要。"""
        args = make_args(
            clone_url="https://github.com/old/repo.git",
            name="solo-repo",
            visibility="internal",
            description="",
            mirror=False,
            auth_token=None,
        )
        with pytest.raises(ConfigError, match="--internal requires an organization"):
            repo_cmd.handle_migrate(args, fmt="table")


# --- Phase 5: star / unstar / mirror / transfer ---


class TestHandleStar:
    def test_star_repository(self, sample_config, mock_adapter, capsys):
        mock_adapter.owner = "test-owner"
        mock_adapter.repo = "test-repo"
        with _patch_all(sample_config, mock_adapter):
            args = make_args()
            repo_cmd.handle_star(args, fmt="table")
        mock_adapter.star_repository.assert_called_once()

    def test_unstar_repository(self, sample_config, mock_adapter, capsys):
        mock_adapter.owner = "test-owner"
        mock_adapter.repo = "test-repo"
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
        mock_adapter.owner = "test-owner"
        mock_adapter.repo = "test-repo"
        with _patch_all(sample_config, mock_adapter):
            args = make_args(new_owner="new-owner", team_id=None, yes=True)
            repo_cmd.handle_transfer(args, fmt="table")
        mock_adapter.transfer_repository.assert_called_once_with("new-owner", team_ids=None)

    def test_transfer_confirmation_yes(self, sample_config, mock_adapter, capsys):
        """ "y" → transfer_repository() 呼び出し。"""
        mock_adapter.owner = "test-owner"
        mock_adapter.repo = "test-repo"
        with _patch_all(sample_config, mock_adapter), patch("builtins.input", return_value="y"):
            args = make_args(new_owner="new-owner", team_id=None, yes=False)
            repo_cmd.handle_transfer(args, fmt="table")
        mock_adapter.transfer_repository.assert_called_once_with("new-owner", team_ids=None)

    def test_transfer_confirmation_no(self, sample_config, mock_adapter, capsys):
        """ "n" → "Aborted." 出力、未呼び出し。"""
        mock_adapter.owner = "test-owner"
        mock_adapter.repo = "test-repo"
        with _patch_all(sample_config, mock_adapter), patch("builtins.input", return_value="n"):
            args = make_args(new_owner="new-owner", team_id=None, yes=False)
            repo_cmd.handle_transfer(args, fmt="table")
        mock_adapter.transfer_repository.assert_not_called()
        out = capsys.readouterr().out
        assert "Aborted" in out


class TestHandleViewWeb:
    def test_opens_browser(self, sample_config, mock_adapter):
        args = make_args(repo=None, web=True)
        with (
            _patch_all(sample_config, mock_adapter),
            patch("webbrowser.open") as mock_open,
        ):
            repo_cmd.handle_view(args, fmt="table")
        mock_adapter.get_web_url.assert_called_once_with("repo")
        mock_open.assert_called_once_with(mock_adapter.get_web_url.return_value)

    def test_does_not_call_api(self, sample_config, mock_adapter):
        args = make_args(repo=None, web=True)
        with (
            _patch_all(sample_config, mock_adapter),
            patch("webbrowser.open"),
        ):
            repo_cmd.handle_view(args, fmt="table")
        mock_adapter.get_repository.assert_not_called()

    def test_opens_browser_with_repo_arg(self, sample_config, mock_adapter):
        """--web + repo arg で指定リポジトリの URL を開く（#7）。"""
        args = make_args(repo="other-owner/other-repo", web=True)
        with (
            _patch_all(sample_config, mock_adapter),
            patch("webbrowser.open") as mock_open,
        ):
            repo_cmd.handle_view(args, fmt="table")
        mock_adapter.get_repository.assert_called_once_with("other-owner", "other-repo")
        mock_open.assert_called_once_with(mock_adapter.get_repository.return_value.url)


class TestHandleSyncFork:
    def test_sync_fork(self, sample_config, mock_adapter, capsys):
        with _patch_all(sample_config, mock_adapter):
            args = make_args(branch=None)
            repo_cmd.handle_sync_fork(args, fmt="table")
        mock_adapter.sync_fork.assert_called_once_with(branch=None)
        out = capsys.readouterr().out
        assert "sync" in out.lower()

    def test_sync_fork_with_branch(self, sample_config, mock_adapter, capsys):
        with _patch_all(sample_config, mock_adapter):
            args = make_args(branch="main")
            repo_cmd.handle_sync_fork(args, fmt="table")
        mock_adapter.sync_fork.assert_called_once_with(branch="main")

    def test_sync_fork_json(self, sample_config, mock_adapter, capsys):
        with _patch_all(sample_config, mock_adapter):
            args = make_args(branch=None)
            repo_cmd.handle_sync_fork(args, fmt="json")
        mock_adapter.sync_fork.assert_called_once_with(branch=None)


class TestHandleUnarchive:
    def test_calls_update_repository_with_archived_false(self, sample_config, sample_repo, capsys):
        adapter = MagicMock()
        adapter.owner = "test-owner"
        adapter.repo = "test-repo"
        adapter.update_repository.return_value = sample_repo
        args = make_args()
        with patch("gfo.commands.repo.get_adapter", return_value=adapter):
            repo_cmd.handle_unarchive(args, fmt="table")

        adapter.update_repository.assert_called_once_with(archived=False)

    def test_prints_success_message(self, sample_config, sample_repo, capsys):
        adapter = MagicMock()
        adapter.owner = "my-org"
        adapter.repo = "my-repo"
        adapter.update_repository.return_value = sample_repo
        args = make_args()
        with patch("gfo.commands.repo.get_adapter", return_value=adapter):
            repo_cmd.handle_unarchive(args, fmt="table")

        out = capsys.readouterr().out
        assert "Unarchived" in out
        assert "my-org/my-repo" in out

    def test_error_propagation(self, sample_config):
        from gfo.exceptions import NotSupportedError

        adapter = MagicMock()
        adapter.owner = "test-owner"
        adapter.repo = "test-repo"
        adapter.update_repository.side_effect = NotSupportedError("Gogs", "repo update")
        args = make_args()
        with patch("gfo.commands.repo.get_adapter", return_value=adapter):
            with pytest.raises(NotSupportedError):
                repo_cmd.handle_unarchive(args, fmt="table")
