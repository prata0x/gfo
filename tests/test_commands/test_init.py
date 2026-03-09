"""gfo.commands.init のテスト。"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from gfo.commands import init as init_cmd
from gfo.config import ProjectConfig
from gfo.detect import DetectResult
from gfo.exceptions import ConfigError, DetectionError, GitCommandError
from tests.test_commands.conftest import make_args


def _make_detect_result(
    service_type: str = "github",
    host: str = "github.com",
    owner: str = "test-owner",
    repo: str = "test-repo",
) -> DetectResult:
    return DetectResult(
        service_type=service_type,
        host=host,
        owner=owner,
        repo=repo,
    )


class TestHandleInteractive:
    """対話モードのテスト。"""

    def test_detect_success_approved(self):
        """検出成功 → Y で承認 → save_project_config が呼ばれる。"""
        detect_result = _make_detect_result()
        args = make_args(non_interactive=False)

        with patch("gfo.commands.init.detect_service", return_value=detect_result), \
             patch("gfo.commands.init.save_project_config") as mock_save, \
             patch("builtins.input", return_value="y"):
            init_cmd.handle(args, fmt="table")

        mock_save.assert_called_once()
        saved: ProjectConfig = mock_save.call_args[0][0]
        assert saved.service_type == "github"
        assert saved.host == "github.com"

    def test_detect_success_approved_default_enter(self):
        """検出成功 → Enter (デフォルト Y) で承認。"""
        detect_result = _make_detect_result()
        args = make_args(non_interactive=False)

        with patch("gfo.commands.init.detect_service", return_value=detect_result), \
             patch("gfo.commands.init.save_project_config") as mock_save, \
             patch("builtins.input", return_value=""):
            init_cmd.handle(args, fmt="table")

        mock_save.assert_called_once()

    def test_detect_success_rejected_manual_input(self):
        """検出成功 → n で拒否 → 手動入力 → save_project_config が呼ばれる。"""
        detect_result = _make_detect_result()
        args = make_args(non_interactive=False)

        # 入力順: [Y/n] 確認 → type → host → api_url → project_key
        inputs = iter(["n", "gitlab", "gitlab.example.com", "https://gitlab.example.com/api/v4", ""])

        with patch("gfo.commands.init.detect_service", return_value=detect_result), \
             patch("gfo.commands.init.save_project_config") as mock_save, \
             patch("gfo.commands.init.get_remote_url", return_value="https://gitlab.example.com/owner/repo.git"), \
             patch("builtins.input", side_effect=inputs):
            init_cmd.handle(args, fmt="table")

        mock_save.assert_called_once()
        saved: ProjectConfig = mock_save.call_args[0][0]
        assert saved.service_type == "gitlab"
        assert saved.host == "gitlab.example.com"
        assert saved.api_url == "https://gitlab.example.com/api/v4"

    def test_detect_failure_falls_back_to_manual(self):
        """検出失敗 → 手動入力にフォールバック → save_project_config が呼ばれる。"""
        args = make_args(non_interactive=False)

        # 入力順: type → host → api_url → project_key
        inputs = iter(["github", "github.com", "", ""])

        with patch("gfo.commands.init.detect_service", side_effect=DetectionError("test")), \
             patch("gfo.commands.init.save_project_config") as mock_save, \
             patch("gfo.commands.init.get_remote_url", return_value="https://github.com/owner/repo.git"), \
             patch("builtins.input", side_effect=inputs):
            init_cmd.handle(args, fmt="table")

        mock_save.assert_called_once()
        saved: ProjectConfig = mock_save.call_args[0][0]
        assert saved.service_type == "github"
        assert saved.host == "github.com"

    def test_detect_failure_manual_no_remote_url(self):
        """手動入力時に get_remote_url が失敗 → owner/repo は空文字。"""
        args = make_args(non_interactive=False)
        inputs = iter(["github", "github.com", "", ""])

        with patch("gfo.commands.init.detect_service", side_effect=DetectionError()), \
             patch("gfo.commands.init.get_remote_url",
                   side_effect=GitCommandError("not a git repo")), \
             patch("gfo.commands.init.save_project_config") as mock_save, \
             patch("builtins.input", side_effect=inputs):
            init_cmd.handle(args, fmt="table")

        saved = mock_save.call_args[0][0]
        assert saved.owner == ""
        assert saved.repo == ""

    def test_detect_success_azure_devops_needs_org_input(self):
        """Azure DevOps 検出 → organization 不足 → 手動入力してから保存。"""
        from gfo.detect import DetectResult
        detect_result = DetectResult(
            service_type="azure-devops",
            host="dev.azure.com",
            owner="",
            repo="test-repo",
            organization=None,
            project=None,
        )
        args = make_args(non_interactive=False)
        # 入力: [Y/n] 確認 → organization → project_key
        inputs = iter(["y", "my-org", "my-project"])

        with patch("gfo.commands.init.detect_service", return_value=detect_result), \
             patch("gfo.commands.init.save_project_config") as mock_save, \
             patch("builtins.input", side_effect=inputs):
            init_cmd.handle(args, fmt="table")

        mock_save.assert_called_once()
        saved: ProjectConfig = mock_save.call_args[0][0]
        assert saved.service_type == "azure-devops"
        assert "my-org" in saved.api_url
        assert "my-project" in saved.api_url

    def test_detect_failure_manual_empty_service_type_raises(self):
        """手動入力で service_type が空 → ConfigError。"""
        args = make_args(non_interactive=False)
        inputs = iter(["", "github", "github.com", "", ""])

        with patch("gfo.commands.init.detect_service", side_effect=DetectionError()), \
             patch("gfo.commands.init.get_remote_url", return_value="https://github.com/o/r.git"), \
             patch("builtins.input", side_effect=inputs):
            with pytest.raises(ConfigError, match="service_type cannot be empty"):
                init_cmd.handle(args, fmt="table")

    def test_detect_failure_manual_invalid_service_type_raises(self):
        """手動入力で無効な service_type → ConfigError。"""
        args = make_args(non_interactive=False)
        inputs = iter(["unknown-svc", "github.com", "", ""])

        with patch("gfo.commands.init.detect_service", side_effect=DetectionError()), \
             patch("builtins.input", side_effect=inputs):
            with pytest.raises(ConfigError, match="Unknown service type"):
                init_cmd.handle(args, fmt="table")

    def test_detect_failure_manual_empty_host_raises(self):
        """手動入力で host が空 → ConfigError。"""
        args = make_args(non_interactive=False)
        inputs = iter(["github", "", "", ""])

        with patch("gfo.commands.init.detect_service", side_effect=DetectionError()), \
             patch("builtins.input", side_effect=inputs):
            with pytest.raises(ConfigError, match="host cannot be empty"):
                init_cmd.handle(args, fmt="table")

    def test_detect_failure_manual_uses_default_api_url(self):
        """検出失敗 → 手動入力で api_url 空白 → デフォルト URL が使われる。"""
        args = make_args(non_interactive=False)

        inputs = iter(["gitlab", "gitlab.com", "", ""])

        with patch("gfo.commands.init.detect_service", side_effect=DetectionError()), \
             patch("gfo.commands.init.save_project_config") as mock_save, \
             patch("gfo.commands.init.get_remote_url", return_value="https://gitlab.com/owner/repo.git"), \
             patch("builtins.input", side_effect=inputs):
            init_cmd.handle(args, fmt="table")

        saved: ProjectConfig = mock_save.call_args[0][0]
        assert saved.api_url == "https://gitlab.com/api/v4"


class TestHandleNonInteractive:
    """--non-interactive モードのテスト。"""

    def test_type_and_host_specified_saves_config(self):
        """type + host 指定 → 正常に save_project_config が呼ばれる。"""
        args = make_args(
            non_interactive=True,
            type="github",
            host="github.com",
            api_url=None,
            project_key=None,
        )

        with patch("gfo.commands.init.get_remote_url", return_value="https://github.com/owner/repo.git"), \
             patch("gfo.commands.init.save_project_config") as mock_save:
            init_cmd.handle(args, fmt="table")

        mock_save.assert_called_once()
        saved: ProjectConfig = mock_save.call_args[0][0]
        assert saved.service_type == "github"
        assert saved.host == "github.com"
        assert saved.owner == "owner"
        assert saved.repo == "repo"

    def test_missing_type_raises_config_error(self):
        """type 未指定 → ConfigError。"""
        args = make_args(
            non_interactive=True,
            type=None,
            host="github.com",
            api_url=None,
            project_key=None,
        )

        with pytest.raises(ConfigError, match="--type"):
            init_cmd.handle(args, fmt="table")

    def test_invalid_type_raises_config_error(self):
        """無効な service_type → ConfigError。"""
        args = make_args(
            non_interactive=True,
            type="unknown-service",
            host="example.com",
            api_url=None,
            project_key=None,
        )

        with pytest.raises(ConfigError, match="Unknown service type"):
            init_cmd.handle(args, fmt="table")

    def test_missing_host_raises_config_error(self):
        """host 未指定 → ConfigError。"""
        args = make_args(
            non_interactive=True,
            type="github",
            host=None,
            api_url=None,
            project_key=None,
        )

        with pytest.raises(ConfigError, match="--host"):
            init_cmd.handle(args, fmt="table")

    def test_explicit_api_url_is_used(self):
        """api-url 指定 → その値が api_url に使われる。"""
        args = make_args(
            non_interactive=True,
            type="github",
            host="github.example.com",
            api_url="https://github.example.com/api/v3",
            project_key=None,
        )

        with patch("gfo.commands.init.get_remote_url", return_value="https://github.example.com/owner/repo.git"), \
             patch("gfo.commands.init.save_project_config") as mock_save:
            init_cmd.handle(args, fmt="table")

        saved: ProjectConfig = mock_save.call_args[0][0]
        assert saved.api_url == "https://github.example.com/api/v3"

    def test_api_url_from_host_config(self):
        """api_url 未指定かつ get_host_config に値あり → そちらが使われる。"""
        args = make_args(
            non_interactive=True,
            type="gitea",
            host="gitea.example.com",
            api_url=None,
            project_key=None,
        )
        host_cfg = {"type": "gitea", "api_url": "https://gitea.example.com/api/v1"}

        with patch("gfo.commands.init.get_remote_url", return_value="https://gitea.example.com/owner/repo.git"), \
             patch("gfo.commands.init.get_host_config", return_value=host_cfg), \
             patch("gfo.commands.init.save_project_config") as mock_save:
            init_cmd.handle(args, fmt="table")

        saved: ProjectConfig = mock_save.call_args[0][0]
        assert saved.api_url == "https://gitea.example.com/api/v1"

    def test_default_api_url_when_not_specified(self):
        """api_url 未指定、host_config なし → _build_default_api_url が使われる。"""
        args = make_args(
            non_interactive=True,
            type="gitlab",
            host="gitlab.com",
            api_url=None,
            project_key=None,
        )

        with patch("gfo.commands.init.get_remote_url", return_value="https://gitlab.com/owner/repo.git"), \
             patch("gfo.commands.init.get_host_config", return_value=None), \
             patch("gfo.commands.init.save_project_config") as mock_save:
            init_cmd.handle(args, fmt="table")

        saved: ProjectConfig = mock_save.call_args[0][0]
        assert saved.api_url == "https://gitlab.com/api/v4"

    def test_remote_url_detection_failure_error_message(self):
        """リモート URL 取得失敗時のエラーメッセージに --owner/--repo を含まない（R40-01）。"""
        args = make_args(
            non_interactive=True,
            type="github",
            host="github.com",
            api_url=None,
            project_key=None,
        )

        with patch("gfo.commands.init.get_remote_url", side_effect=GitCommandError("not a git repo")):
            with pytest.raises(ConfigError) as exc_info:
                init_cmd.handle(args, fmt="table")

        assert "--owner" not in str(exc_info.value)
        assert "--repo" not in str(exc_info.value)
        assert "origin remote" in str(exc_info.value)
