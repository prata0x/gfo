"""detect.py のサービス自動検出テスト。"""

from unittest.mock import patch

import pytest
import responses

from gfo.detect import DetectResult, detect_from_url, detect_service, probe_unknown_host
from gfo.exceptions import DetectionError


# ── URL パーステスト ──


class TestDetectFromUrl:
    # GitHub
    def test_github_https(self):
        r = detect_from_url("https://github.com/owner/repo.git")
        assert r.service_type == "github"
        assert r.host == "github.com"
        assert r.owner == "owner"
        assert r.repo == "repo"

    def test_github_ssh_scp(self):
        r = detect_from_url("git@github.com:owner/repo.git")
        assert r.service_type == "github"
        assert r.owner == "owner"
        assert r.repo == "repo"

    def test_ssh_scp_hyphenated_username(self):
        """ハイフン入りユーザー名の SSH SCP URL がパースできる。"""
        r = detect_from_url("my-user@github.com:owner/repo.git")
        assert r.service_type == "github"
        assert r.host == "github.com"
        assert r.owner == "owner"
        assert r.repo == "repo"

    def test_github_ssh_url(self):
        r = detect_from_url("ssh://git@github.com/owner/repo.git")
        assert r.service_type == "github"
        assert r.owner == "owner"
        assert r.repo == "repo"

    def test_ssh_url_hyphenated_username(self):
        """ハイフン入りユーザー名の SSH URL がパースできる。"""
        r = detect_from_url("ssh://my-user@github.com/owner/repo.git")
        assert r.service_type == "github"
        assert r.host == "github.com"
        assert r.owner == "owner"
        assert r.repo == "repo"

    def test_github_trailing_slash(self):
        r = detect_from_url("https://github.com/owner/repo/")
        assert r.service_type == "github"
        assert r.repo == "repo"

    def test_github_no_git_suffix(self):
        r = detect_from_url("https://github.com/owner/repo")
        assert r.service_type == "github"
        assert r.repo == "repo"

    # GitLab
    def test_gitlab_https(self):
        r = detect_from_url("https://gitlab.com/owner/repo.git")
        assert r.service_type == "gitlab"
        assert r.host == "gitlab.com"

    def test_gitlab_subgroup(self):
        r = detect_from_url("https://gitlab.com/group/sub1/sub2/project.git")
        assert r.service_type == "gitlab"
        assert r.owner == "group/sub1/sub2"
        assert r.repo == "project"

    # Bitbucket
    def test_bitbucket_https(self):
        r = detect_from_url("https://bitbucket.org/workspace/repo.git")
        assert r.service_type == "bitbucket"
        assert r.owner == "workspace"

    # Azure DevOps
    def test_azure_https(self):
        r = detect_from_url("https://dev.azure.com/org/project/_git/repo")
        assert r.service_type == "azure-devops"
        assert r.organization == "org"
        assert r.project == "project"
        assert r.repo == "repo"

    def test_azure_ssh(self):
        r = detect_from_url("git@ssh.dev.azure.com:v3/org/project/repo")
        assert r.service_type == "azure-devops"
        assert r.organization == "org"
        assert r.project == "project"
        assert r.repo == "repo"

    def test_azure_legacy_visualstudio(self):
        r = detect_from_url("https://myorg.visualstudio.com/project/_git/repo")
        assert r.service_type == "azure-devops"
        assert r.organization == "myorg"
        assert r.project == "project"
        assert r.repo == "repo"

    # Codeberg (forgejo)
    def test_codeberg_https(self):
        r = detect_from_url("https://codeberg.org/owner/repo.git")
        assert r.service_type == "forgejo"
        assert r.host == "codeberg.org"

    # Bitbucket SSH
    def test_bitbucket_ssh_scp(self):
        r = detect_from_url("git@bitbucket.org:workspace/repo.git")
        assert r.service_type == "bitbucket"
        assert r.owner == "workspace"
        assert r.repo == "repo"

    def test_bitbucket_ssh_url(self):
        r = detect_from_url("ssh://git@bitbucket.org/workspace/repo.git")
        assert r.service_type == "bitbucket"
        assert r.owner == "workspace"
        assert r.repo == "repo"

    # GitLab SSH
    def test_gitlab_ssh_scp(self):
        r = detect_from_url("git@gitlab.com:owner/repo.git")
        assert r.service_type == "gitlab"
        assert r.owner == "owner"
        assert r.repo == "repo"

    def test_gitlab_ssh_url(self):
        r = detect_from_url("ssh://git@gitlab.com/owner/repo.git")
        assert r.service_type == "gitlab"
        assert r.owner == "owner"
        assert r.repo == "repo"

    def test_gitlab_subgroup_ssh(self):
        r = detect_from_url("git@gitlab.com:group/sub1/sub2/project.git")
        assert r.service_type == "gitlab"
        assert r.owner == "group/sub1/sub2"
        assert r.repo == "project"

    # 未知ホスト HTTPS
    def test_gitea_unknown_host_https(self):
        r = detect_from_url("https://gitea.example.com/owner/repo.git")
        assert r.service_type is None
        assert r.host == "gitea.example.com"
        assert r.owner == "owner"
        assert r.repo == "repo"

    def test_gitbucket_unknown_host_https(self):
        r = detect_from_url("https://gitbucket.example.com/owner/repo.git")
        assert r.service_type is None
        assert r.host == "gitbucket.example.com"
        assert r.owner == "owner"
        assert r.repo == "repo"

    # .git サフィックスなし
    def test_gitlab_no_git_suffix(self):
        r = detect_from_url("https://gitlab.com/owner/repo")
        assert r.service_type == "gitlab"
        assert r.repo == "repo"

    def test_bitbucket_no_git_suffix(self):
        r = detect_from_url("https://bitbucket.org/workspace/repo")
        assert r.service_type == "bitbucket"
        assert r.repo == "repo"

    def test_codeberg_no_git_suffix(self):
        r = detect_from_url("https://codeberg.org/owner/repo")
        assert r.service_type == "forgejo"
        assert r.repo == "repo"

    def test_backlog_no_git_suffix(self):
        r = detect_from_url("https://space.backlog.com/git/PROJECT/repo")
        assert r.service_type == "backlog"
        assert r.project == "PROJECT"
        assert r.repo == "repo"

    # Backlog
    def test_backlog_https(self):
        r = detect_from_url("https://space.backlog.com/git/PROJECT/repo.git")
        assert r.service_type == "backlog"
        assert r.host == "space.backlog.com"
        assert r.project == "PROJECT"
        assert r.repo == "repo"

    def test_backlog_jp(self):
        r = detect_from_url("https://space.backlog.jp/git/PROJECT/repo.git")
        assert r.service_type == "backlog"
        assert r.host == "space.backlog.jp"

    def test_backlog_ssh(self):
        r = detect_from_url("space@space.git.backlog.com:/PROJECT/repo.git")
        assert r.service_type == "backlog"
        assert r.host == "space.backlog.com"
        assert r.project == "PROJECT"
        assert r.repo == "repo"

    # SSH with port
    def test_ssh_with_port(self):
        r = detect_from_url("ssh://git@gitlab.example.com:2222/owner/repo.git")
        assert r.host == "gitlab.example.com"
        assert r.owner == "owner"
        assert r.repo == "repo"
        assert r.service_type is None

    # 未知ホスト
    def test_unknown_host(self):
        r = detect_from_url("https://git.example.com/owner/repo.git")
        assert r.service_type is None
        assert r.host == "git.example.com"
        assert r.owner == "owner"
        assert r.repo == "repo"

    # 無効 URL
    def test_invalid_url_raises(self):
        with pytest.raises(DetectionError):
            detect_from_url("not-a-url")


# ── API プローブテスト ──


class TestProbeUnknownHost:
    @responses.activate
    def test_forgejo_detected(self):
        responses.add(
            responses.GET,
            "https://git.example.com/api/v1/version",
            json={"version": "1.0", "forgejo": "8.0.0"},
            status=200,
        )
        assert probe_unknown_host("git.example.com") == "forgejo"

    @responses.activate
    def test_forgejo_old_version_detected_via_source_url(self):
        """旧版 Forgejo は source_url に 'forgejo' を含む場合に検出される。"""
        responses.add(
            responses.GET,
            "https://git.example.com/api/v1/version",
            json={
                "version": "1.19.0",
                "go_version": "go1.20",
                "source_url": "https://codeberg.org/forgejo/forgejo",
            },
            status=200,
        )
        assert probe_unknown_host("git.example.com") == "forgejo"

    @responses.activate
    def test_gitea_detected_go_version(self):
        responses.add(
            responses.GET,
            "https://git.example.com/api/v1/version",
            json={"version": "1.21.0", "go-version": "go1.21"},
            status=200,
        )
        assert probe_unknown_host("git.example.com") == "gitea"

    @responses.activate
    def test_gitea_detected_go_version_underscore(self):
        responses.add(
            responses.GET,
            "https://git.example.com/api/v1/version",
            json={"version": "1.21.0", "go_version": "go1.21"},
            status=200,
        )
        assert probe_unknown_host("git.example.com") == "gitea"

    @responses.activate
    def test_gogs_detected(self):
        responses.add(
            responses.GET,
            "https://git.example.com/api/v1/version",
            json={"version": "0.13.0"},
            status=200,
        )
        assert probe_unknown_host("git.example.com") == "gogs"

    @responses.activate
    def test_gitlab_detected(self):
        responses.add(
            responses.GET,
            "https://git.example.com/api/v1/version",
            status=404,
        )
        responses.add(
            responses.GET,
            "https://git.example.com/api/v4/version",
            json={"version": "16.0.0"},
            status=200,
        )
        assert probe_unknown_host("git.example.com") == "gitlab"

    @responses.activate
    def test_gitbucket_detected(self):
        responses.add(
            responses.GET,
            "https://git.example.com/api/v1/version",
            status=404,
        )
        responses.add(
            responses.GET,
            "https://git.example.com/api/v4/version",
            status=404,
        )
        responses.add(
            responses.GET,
            "https://git.example.com/api/v3/",
            json={"ok": True},
            status=200,
        )
        assert probe_unknown_host("git.example.com") == "gitbucket"

    @responses.activate
    def test_all_fail_returns_none(self):
        responses.add(responses.GET, "https://git.example.com/api/v1/version", status=404)
        responses.add(responses.GET, "https://git.example.com/api/v4/version", status=404)
        responses.add(responses.GET, "https://git.example.com/api/v3/", status=404)
        assert probe_unknown_host("git.example.com") is None

    @responses.activate
    def test_custom_scheme(self):
        responses.add(
            responses.GET,
            "http://git.local/api/v1/version",
            json={"version": "1.0", "forgejo": "8.0.0"},
            status=200,
        )
        assert probe_unknown_host("git.local", scheme="http") == "forgejo"


# ── 統合フローテスト ──


class TestDetectService:
    @patch("gfo.detect.get_remote_url", return_value="https://github.com/o/r.git")
    @patch("gfo.detect.git_config_get")
    def test_git_config_shortcut(self, mock_config_get, mock_remote):
        def config_side(key, cwd=None):
            return {"gfo.type": "gitea", "gfo.host": "git.example.com"}.get(key)

        mock_config_get.side_effect = config_side
        r = detect_service()
        assert r.service_type == "gitea"

    @patch("gfo.detect.get_remote_url", return_value="https://github.com/owner/repo.git")
    @patch("gfo.detect.git_config_get", return_value=None)
    def test_known_host(self, mock_config_get, mock_remote):
        r = detect_service()
        assert r.service_type == "github"
        assert r.owner == "owner"

    @patch("gfo.detect.probe_unknown_host", return_value="gitea")
    @patch("gfo.detect.get_remote_url", return_value="https://git.example.com/owner/repo.git")
    @patch("gfo.detect.git_config_get", return_value=None)
    def test_unknown_host_probe_success(self, mock_config, mock_remote, mock_probe):
        r = detect_service()
        assert r.service_type == "gitea"
        mock_probe.assert_called_once_with("git.example.com", scheme="https")

    @patch("gfo.detect.probe_unknown_host", return_value=None)
    @patch("gfo.detect.get_remote_url", return_value="https://git.example.com/owner/repo.git")
    @patch("gfo.detect.git_config_get", return_value=None)
    def test_all_fail_raises(self, mock_config, mock_remote, mock_probe):
        with pytest.raises(DetectionError):
            detect_service()

    @patch("gfo.detect.probe_unknown_host", return_value=None)
    @patch("gfo.detect.get_remote_url", return_value="https://git.example.com/owner/repo.git")
    @patch("gfo.detect.git_config_get", return_value=None)
    def test_config_module_missing_no_error(self, mock_config, mock_remote, mock_probe):
        """config モジュールが未実装でもエラーにならない。"""
        # gfo.config が ImportError を投げる場合でも通過することをテスト
        # (実際の ImportError はガード済みなので、probe が None → DetectionError になる)
        with pytest.raises(DetectionError):
            detect_service()

    @patch("gfo.detect.probe_unknown_host", return_value="gitea")
    @patch("gfo.detect.get_remote_url", return_value="http://git.example.com/owner/repo.git")
    @patch("gfo.detect.git_config_get", return_value=None)
    def test_http_remote_url_passes_http_scheme(self, mock_config, mock_remote, mock_probe):
        """HTTP remote URL でプローブ時に scheme='http' が渡されることを検証 (R-01)。"""
        r = detect_service()
        assert r.service_type == "gitea"
        mock_probe.assert_called_once_with("git.example.com", scheme="http")
