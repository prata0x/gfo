"""git_util.py のテスト。subprocess.run をモックして検証する。"""

from __future__ import annotations

from unittest.mock import patch, MagicMock
import subprocess

import pytest

from gfo.exceptions import GitCommandError
from gfo import git_util


def _mock_result(stdout: str = "", stderr: str = "", returncode: int = 0):
    """subprocess.run の戻り値を生成するヘルパー。"""
    r = MagicMock(spec=subprocess.CompletedProcess)
    r.stdout = stdout
    r.stderr = stderr
    r.returncode = returncode
    return r


class TestRunGit:
    @patch("gfo.git_util.subprocess.run")
    def test_success_returns_stripped_stdout(self, mock_run):
        mock_run.return_value = _mock_result(stdout="  hello world  \n")
        assert git_util.run_git("status") == "hello world"
        mock_run.assert_called_once_with(
            ["git", "status"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
            cwd=None,
            shell=False,
        )

    @patch("gfo.git_util.subprocess.run")
    def test_failure_raises_git_command_error(self, mock_run):
        mock_run.return_value = _mock_result(stderr="  fatal: bad  \n", returncode=1)
        with pytest.raises(GitCommandError, match="fatal: bad"):
            git_util.run_git("status")


class TestGetRemoteUrl:
    @patch("gfo.git_util.subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = _mock_result(stdout="https://github.com/user/repo.git\n")
        assert git_util.get_remote_url() == "https://github.com/user/repo.git"

    @patch("gfo.git_util.subprocess.run")
    def test_remote_not_found(self, mock_run):
        mock_run.return_value = _mock_result(stderr="fatal: not found", returncode=2)
        with pytest.raises(GitCommandError):
            git_util.get_remote_url("upstream")


class TestGetCurrentBranch:
    @patch("gfo.git_util.subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = _mock_result(stdout="feature/xyz\n")
        assert git_util.get_current_branch() == "feature/xyz"

    @patch("gfo.git_util.subprocess.run")
    def test_detached_head(self, mock_run):
        mock_run.return_value = _mock_result(
            stderr="fatal: ref HEAD is not a symbolic ref", returncode=128
        )
        with pytest.raises(GitCommandError):
            git_util.get_current_branch()


class TestGetLastCommitSubject:
    @patch("gfo.git_util.subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = _mock_result(stdout="feat: add something\n")
        assert git_util.get_last_commit_subject() == "feat: add something"


class TestGetDefaultBranch:
    @patch("gfo.git_util.subprocess.run")
    def test_success_strips_prefix(self, mock_run):
        mock_run.return_value = _mock_result(stdout="refs/remotes/origin/develop\n")
        assert git_util.get_default_branch() == "develop"

    @patch("gfo.git_util.subprocess.run")
    def test_fallback_to_main(self, mock_run):
        mock_run.return_value = _mock_result(
            stderr="fatal: ref not found", returncode=1
        )
        assert git_util.get_default_branch() == "main"


class TestGitConfigGet:
    @patch("gfo.git_util.subprocess.run")
    def test_value_exists(self, mock_run):
        mock_run.return_value = _mock_result(stdout="some-value\n")
        assert git_util.git_config_get("gfo.service") == "some-value"

    @patch("gfo.git_util.subprocess.run")
    def test_not_set_returns_none(self, mock_run):
        mock_run.return_value = _mock_result(stderr="", returncode=1)
        assert git_util.git_config_get("gfo.missing") is None


class TestGitConfigSet:
    @patch("gfo.git_util.subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = _mock_result()
        git_util.git_config_set("gfo.service", "github")
        mock_run.assert_called_once_with(
            ["git", "config", "--local", "gfo.service", "github"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
            cwd=None,
            shell=False,
        )


class TestGitFetch:
    @patch("gfo.git_util.subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = _mock_result()
        git_util.git_fetch("origin", "refs/pull/42/head")
        mock_run.assert_called_once_with(
            ["git", "fetch", "origin", "refs/pull/42/head"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
            cwd=None,
            shell=False,
        )


class TestGitCheckoutNewBranch:
    @patch("gfo.git_util.subprocess.run")
    def test_default_start(self, mock_run):
        mock_run.return_value = _mock_result()
        git_util.git_checkout_new_branch("pr-42")
        mock_run.assert_called_once_with(
            ["git", "checkout", "-b", "pr-42", "FETCH_HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
            cwd=None,
            shell=False,
        )

    @patch("gfo.git_util.subprocess.run")
    def test_custom_start(self, mock_run):
        mock_run.return_value = _mock_result()
        git_util.git_checkout_new_branch("pr-42", start="origin/main")
        mock_run.assert_called_once_with(
            ["git", "checkout", "-b", "pr-42", "origin/main"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
            cwd=None,
            shell=False,
        )


class TestGitClone:
    @patch("gfo.git_util.subprocess.run")
    def test_with_dest(self, mock_run):
        mock_run.return_value = _mock_result()
        git_util.git_clone("https://github.com/user/repo.git", dest="repo")
        mock_run.assert_called_once_with(
            ["git", "clone", "https://github.com/user/repo.git", "repo"],
            capture_output=True,
            text=True,
            check=False,
            timeout=None,
            cwd=None,
            shell=False,
        )

    @patch("gfo.git_util.subprocess.run")
    def test_without_dest(self, mock_run):
        mock_run.return_value = _mock_result()
        git_util.git_clone("https://github.com/user/repo.git")
        mock_run.assert_called_once_with(
            ["git", "clone", "https://github.com/user/repo.git"],
            capture_output=True,
            text=True,
            check=False,
            timeout=None,
            cwd=None,
            shell=False,
        )

    @patch("gfo.git_util.subprocess.run")
    def test_timeout_is_none(self, mock_run):
        mock_run.return_value = _mock_result()
        git_util.git_clone("https://github.com/user/repo.git")
        call_kwargs = mock_run.call_args
        assert call_kwargs.kwargs["timeout"] is None
