"""detect.py のサービス自動検出テスト。"""

from unittest.mock import patch

import pytest
import responses

from gfo.detect import detect_from_url, detect_service, get_known_service_type, probe_unknown_host
from gfo.exceptions import DetectionError

# ── URL パーステスト ──


class TestDetectFromUrl:
    # GitHub
    def test_github_https_uppercase_host(self):
        """URL のホスト名が大文字でも既知サービスとして検出される。"""
        r = detect_from_url("https://GITHUB.COM/owner/repo.git")
        assert r.service_type == "github"
        assert r.owner == "owner"

    def test_gitlab_https_uppercase_host(self):
        """GitLab 大文字ホストでも検出される。"""
        r = detect_from_url("https://GITLAB.COM/owner/repo.git")
        assert r.service_type == "gitlab"

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
        assert r.owner == "PROJECT"
        assert r.project == "PROJECT"
        assert r.repo == "repo"

    # Backlog
    def test_backlog_https(self):
        r = detect_from_url("https://space.backlog.com/git/PROJECT/repo.git")
        assert r.service_type == "backlog"
        assert r.host == "space.backlog.com"
        assert r.owner == "PROJECT"
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
        assert r.owner == "PROJECT"
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

    def test_unknown_host_unparseable_path_masks_apikey(self):
        """未知ホスト + apiKey を含むパース不可パスで DetectionError メッセージが apiKey をマスクする（R38-01）。"""
        # _GENERIC_PATH_RE は "/" が必要なため "items" 単体ではマッチしない → L196 が発火
        # 事前修正なしだと apiKey=secret がそのままエラーメッセージに含まれていた
        with pytest.raises(DetectionError) as exc_info:
            detect_from_url("https://git.example.com/items%3FapiKey%3Dsecret")
        assert "apiKey=secret" not in str(exc_info.value)

    def test_unknown_host_unparseable_path_error_message(self):
        """未知ホスト + パース不可パスで DetectionError が 'Cannot parse path' を含む（R38-01）。"""
        with pytest.raises(DetectionError, match="Cannot parse path"):
            detect_from_url("https://git.example.com/singlepart")

    def test_https_userinfo_host_extracted_correctly(self):
        """HTTPS URL に userinfo (user:pass@host) が含まれてもホストを正しく抽出する（R45修正確認）。"""
        r = detect_from_url("https://oauth2:token@github.com/owner/repo.git")
        assert r.host == "github.com"
        assert r.service_type == "github"
        assert r.owner == "owner"
        assert r.repo == "repo"

    def test_https_userinfo_only_user_host_extracted_correctly(self):
        """HTTPS URL に user@ 形式の userinfo が含まれてもホストを正しく抽出する。"""
        r = detect_from_url("https://mytoken@gitea.example.com/owner/repo.git")
        assert r.host == "gitea.example.com"
        assert r.owner == "owner"
        assert r.repo == "repo"


# ── get_known_service_type テスト ──


class TestGetKnownServiceType:
    def test_lowercase_known_host(self):
        assert get_known_service_type("github.com") == "github"

    def test_uppercase_host_normalized(self):
        """大文字ホストも小文字に正規化して既知テーブルを参照する。"""
        assert get_known_service_type("GitHub.COM") == "github"
        assert get_known_service_type("GITLAB.COM") == "gitlab"

    def test_unknown_host_returns_none(self):
        assert get_known_service_type("unknown.example.com") is None


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
    def test_non_dict_json_response_returns_none(self):
        """API が dict 以外の JSON を返したとき None を返す（TypeError 等が起きない）。"""
        responses.add(
            responses.GET,
            "https://git.example.com/api/v1/version",
            json=[{"version": "1.0"}],
            status=200,
        )
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


# ── 追加テスト（未カバー行） ──


class TestDetectFromUrlErrors:
    """detect_from_url の DetectionError パス。"""

    def test_backlog_invalid_path_raises(self):
        """Backlog ホストで不正パス → DetectionError。"""
        with pytest.raises(DetectionError, match="Cannot parse Backlog path"):
            detect_from_url("https://space.backlog.com/invalid")

    def test_azure_devops_invalid_path_raises(self):
        """Azure DevOps ホストで不正パス → DetectionError。"""
        with pytest.raises(DetectionError, match="Cannot parse Azure DevOps path"):
            detect_from_url("https://dev.azure.com/only-one-segment")

    def test_known_host_invalid_path_raises(self):
        """既知ホスト (github.com) でパース不可パス → DetectionError。"""
        with pytest.raises(DetectionError, match="Cannot parse path"):
            detect_from_url("https://github.com/singlepart")


class TestProbeUnknownHostRequestException:
    """probe_unknown_host で requests.RequestException が発生する場合。"""

    @responses.activate
    def test_gitea_endpoint_request_exception(self):
        """Gitea/Forgejo エンドポイントで接続エラー → 例外を握りつぶして次を試みる。"""
        import requests

        responses.add(
            responses.GET,
            "https://git.example.com/api/v1/version",
            body=requests.RequestException("connection error"),
        )
        responses.add(responses.GET, "https://git.example.com/api/v4/version", status=404)
        responses.add(responses.GET, "https://git.example.com/api/v3/", status=404)
        assert probe_unknown_host("git.example.com") is None

    @responses.activate
    def test_gitlab_endpoint_request_exception(self):
        """GitLab エンドポイントで接続エラー → 例外を握りつぶして次を試みる。"""
        import requests

        responses.add(responses.GET, "https://git.example.com/api/v1/version", status=404)
        responses.add(
            responses.GET,
            "https://git.example.com/api/v4/version",
            body=requests.RequestException("connection error"),
        )
        responses.add(responses.GET, "https://git.example.com/api/v3/", status=404)
        assert probe_unknown_host("git.example.com") is None

    @responses.activate
    def test_gitbucket_endpoint_request_exception(self):
        """GitBucket エンドポイントで接続エラー → 例外を握りつぶして None を返す。"""
        import requests

        responses.add(responses.GET, "https://git.example.com/api/v1/version", status=404)
        responses.add(responses.GET, "https://git.example.com/api/v4/version", status=404)
        responses.add(
            responses.GET,
            "https://git.example.com/api/v3/",
            body=requests.RequestException("connection error"),
        )
        assert probe_unknown_host("git.example.com") is None


class TestDetectServiceRemoteOverride:
    """--remote 指定時の detect_service() 動作。"""

    @patch("gfo.detect.get_remote_url", return_value="https://github.com/owner/repo.git")
    @patch("gfo.detect.git_config_get", return_value=None)
    def test_remote_override_uses_specified_remote(self, mock_config, mock_remote):
        """--remote 指定時に指定リモートの URL を使う。"""
        from gfo._context import cli_remote

        token = cli_remote.set("upstream")
        try:
            r = detect_service()
            mock_remote.assert_called_once_with(remote="upstream", cwd=None)
            assert r.service_type == "github"
        finally:
            cli_remote.reset(token)

    @patch("gfo.detect.get_remote_url", return_value="https://github.com/owner/repo.git")
    @patch("gfo.detect.git_config_get")
    def test_remote_override_skips_git_config_shortcut(self, mock_config, mock_remote):
        """--remote 指定時は git config ショートカット（gfo.type/gfo.host）をスキップする。"""
        from gfo._context import cli_remote

        def config_side(key, cwd=None):
            return {"gfo.type": "gitea", "gfo.host": "git.example.com"}.get(key)

        mock_config.side_effect = config_side

        token = cli_remote.set("upstream")
        try:
            r = detect_service()
            # git config の値ではなく URL から検出した値を使用
            assert r.service_type == "github"
            assert r.host == "github.com"
        finally:
            cli_remote.reset(token)


class TestDetectServiceHostsConfig:
    """detect_service で hosts config に一致するサービスが上書きされる。"""

    @patch("gfo.detect.probe_unknown_host", return_value=None)
    @patch("gfo.detect.get_remote_url", return_value="https://git.example.com/owner/repo.git")
    @patch("gfo.detect.git_config_get", return_value=None)
    def test_service_type_from_hosts_config(self, mock_config, mock_remote, mock_probe):
        """hosts config に一致ホストがある場合、その service_type が使用される。"""
        with patch("gfo.config.get_hosts_config", return_value={"git.example.com": "forgejo"}):
            r = detect_service()
        assert r.service_type == "forgejo"

    @patch("gfo.detect.probe_unknown_host", return_value=None)
    @patch("gfo.detect.get_remote_url", return_value="https://Git.Example.Com/owner/repo.git")
    @patch("gfo.detect.git_config_get", return_value=None)
    def test_service_type_from_hosts_config_mixed_case_host(
        self, mock_config, mock_remote, mock_probe
    ):
        """大文字混在のホスト名でも hosts config に一致する（R28修正確認）。"""
        with patch("gfo.config.get_hosts_config", return_value={"git.example.com": "forgejo"}):
            r = detect_service()
        assert r.service_type == "forgejo"

    @patch("gfo.detect.probe_unknown_host", return_value=None)
    @patch("gfo.detect.get_remote_url", return_value="https://git.example.com/owner/repo.git")
    @patch("gfo.detect.git_config_get", return_value=None)
    def test_hosts_config_attribute_error_ignored(self, mock_config, mock_remote, mock_probe):
        """hosts config の取得で AttributeError が発生しても DetectionError になる（握りつぶし確認）。"""
        with patch("gfo.config.get_hosts_config", side_effect=AttributeError("no attr")):
            with pytest.raises(DetectionError):
                detect_service()
