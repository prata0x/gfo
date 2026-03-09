"""config.py のテスト。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from gfo.config import (
    ProjectConfig,
    build_default_api_url,
    get_config_dir,
    get_config_path,
    get_credentials_path,
    get_default_host,
    get_default_output_format,
    get_host_config,
    get_hosts_config,
    load_user_config,
    resolve_project_config,
    save_project_config,
)
from gfo.exceptions import ConfigError


# ── get_config_dir ──


def test_get_config_dir_windows():
    with patch("gfo.config.sys") as mock_sys, patch.dict(
        "os.environ", {"APPDATA": r"C:\Users\test\AppData\Roaming"}
    ):
        mock_sys.platform = "win32"
        result = get_config_dir()
        assert result == Path(r"C:\Users\test\AppData\Roaming\gfo")


def test_get_config_dir_windows_no_appdata():
    home = Path.home()
    with patch("gfo.config.sys") as mock_sys, patch.dict(
        "os.environ", {"APPDATA": ""}, clear=False
    ):
        mock_sys.platform = "win32"
        result = get_config_dir()
        assert result == home / "AppData" / "Roaming" / "gfo"


def test_get_config_dir_unix():
    with patch("gfo.config.sys") as mock_sys:
        mock_sys.platform = "linux"
        result = get_config_dir()
        assert result == Path.home() / ".config" / "gfo"


# ── get_config_path / get_credentials_path ──


def test_get_config_path():
    with patch("gfo.config.get_config_dir", return_value=Path("/tmp/gfo")):
        assert get_config_path() == Path("/tmp/gfo/config.toml")


def test_get_credentials_path():
    with patch("gfo.config.get_config_dir", return_value=Path("/tmp/gfo")):
        assert get_credentials_path() == Path("/tmp/gfo/credentials.toml")


# ── load_user_config ──


def test_load_user_config_no_file(tmp_path):
    with patch("gfo.config.get_config_path", return_value=tmp_path / "config.toml"):
        assert load_user_config() == {}


def test_load_user_config_permission_error(tmp_path):
    """PermissionError が ConfigError に変換される。"""
    config_file = tmp_path / "config.toml"
    config_file.write_text("")
    with (
        patch("gfo.config.get_config_path", return_value=config_file),
        patch("builtins.open", side_effect=PermissionError("Permission denied")),
    ):
        with pytest.raises(ConfigError, match="Permission denied"):
            load_user_config()


def test_load_user_config_valid(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[defaults]\noutput = "json"\nhost = "github.com"\n\n'
        '[hosts."gitlab.example.com"]\ntype = "gitlab"\napi_url = "https://gitlab.example.com/api/v4"\n'
    )
    with patch("gfo.config.get_config_path", return_value=config_file):
        cfg = load_user_config()
        assert cfg["defaults"]["output"] == "json"
        assert cfg["defaults"]["host"] == "github.com"


# ── get_default_output_format / get_default_host ──


def test_get_default_output_format_default():
    with patch("gfo.config.load_user_config", return_value={}):
        assert get_default_output_format() == "table"


def test_get_default_output_format_configured():
    with patch(
        "gfo.config.load_user_config",
        return_value={"defaults": {"output": "json"}},
    ):
        assert get_default_output_format() == "json"


def test_get_default_output_format_plain():
    """output = "plain" に設定した場合 "plain" が返る。"""
    with patch(
        "gfo.config.load_user_config",
        return_value={"defaults": {"output": "plain"}},
    ):
        assert get_default_output_format() == "plain"


def test_get_default_host_none():
    with patch("gfo.config.load_user_config", return_value={}):
        assert get_default_host() is None


def test_get_default_host_configured():
    with patch(
        "gfo.config.load_user_config",
        return_value={"defaults": {"host": "github.com"}},
    ):
        assert get_default_host() == "github.com"


# ── get_host_config ──


def test_get_host_config_found():
    cfg = {"hosts": {"gitlab.example.com": {"type": "gitlab", "api_url": "https://x"}}}
    with patch("gfo.config.load_user_config", return_value=cfg):
        result = get_host_config("gitlab.example.com")
        assert result == {"type": "gitlab", "api_url": "https://x"}


def test_get_host_config_not_found():
    with patch("gfo.config.load_user_config", return_value={}):
        assert get_host_config("unknown.com") is None


# ── get_hosts_config ──


def test_get_hosts_config():
    cfg = {
        "hosts": {
            "gitlab.example.com": {"type": "gitlab"},
            "gitea.local": {"type": "gitea"},
            "bad": "not-a-dict",
            "missing-type": {"api_url": "https://x"},
        }
    }
    with patch("gfo.config.load_user_config", return_value=cfg):
        result = get_hosts_config()
        assert result == {
            "gitlab.example.com": "gitlab",
            "gitea.local": "gitea",
        }


# ── build_default_api_url ──


def test_build_github_com():
    assert build_default_api_url("github", "github.com") == "https://api.github.com"


def test_build_github_enterprise():
    assert (
        build_default_api_url("github", "ghe.example.com")
        == "https://ghe.example.com/api/v3"
    )


def test_build_gitlab():
    assert (
        build_default_api_url("gitlab", "gitlab.com") == "https://gitlab.com/api/v4"
    )


def test_build_bitbucket():
    assert (
        build_default_api_url("bitbucket", "bitbucket.org")
        == "https://api.bitbucket.org/2.0"
    )


def test_build_azure_devops():
    assert (
        build_default_api_url("azure-devops", "dev.azure.com", "myorg", "myproj")
        == "https://dev.azure.com/myorg/myproj/_apis"
    )


def test_build_azure_devops_missing_org():
    with pytest.raises(ConfigError, match="organization"):
        build_default_api_url("azure-devops", "dev.azure.com")


def test_build_azure_devops_missing_project():
    """organization あり・project なしの場合も ConfigError。"""
    with pytest.raises(ConfigError, match="organization"):
        build_default_api_url("azure-devops", "dev.azure.com", organization="myorg")


def test_build_gitea():
    assert (
        build_default_api_url("gitea", "gitea.local") == "https://gitea.local/api/v1"
    )


def test_build_forgejo():
    assert (
        build_default_api_url("forgejo", "codeberg.org")
        == "https://codeberg.org/api/v1"
    )


def test_build_gogs():
    assert (
        build_default_api_url("gogs", "gogs.local") == "https://gogs.local/api/v1"
    )


def test_build_gitbucket():
    assert (
        build_default_api_url("gitbucket", "gb.local")
        == "https://gb.local/api/v3"
    )


def test_build_backlog():
    assert (
        build_default_api_url("backlog", "space.backlog.com")
        == "https://space.backlog.com/api/v2"
    )


def test_build_unknown_service():
    with pytest.raises(ConfigError, match="Unknown service type"):
        build_default_api_url("unknown", "example.com")


# ── resolve_project_config ──


def _mock_git_config(mapping: dict[str, str | None]):
    """git_config_get のモックを返す。"""

    def _get(key, cwd=None):
        return mapping.get(key)

    return _get


def test_resolve_with_git_config():
    """git config に全情報がある場合。"""
    git_cfg = {
        "gfo.type": "github",
        "gfo.host": "github.com",
        "gfo.api-url": "https://api.github.com",
        "gfo.organization": None,
        "gfo.project-key": None,
    }
    with (
        patch("gfo.git_util.git_config_get", side_effect=_mock_git_config(git_cfg)),
        patch(
            "gfo.git_util.get_remote_url",
            return_value="https://github.com/owner/repo.git",
        ),
    ):
        cfg = resolve_project_config()
        assert cfg.service_type == "github"
        assert cfg.host == "github.com"
        assert cfg.api_url == "https://api.github.com"
        assert cfg.owner == "owner"
        assert cfg.repo == "repo"


def test_resolve_with_detect():
    """git config に設定がなく、detect_service で解決する場合。"""
    from gfo.detect import DetectResult

    detect_result = DetectResult(
        service_type="gitlab",
        host="gitlab.com",
        owner="user",
        repo="project",
    )
    git_cfg = {
        "gfo.type": None,
        "gfo.host": None,
        "gfo.api-url": None,
        "gfo.organization": None,
        "gfo.project-key": None,
    }
    with (
        patch("gfo.git_util.git_config_get", side_effect=_mock_git_config(git_cfg)),
        patch("gfo.detect.detect_service", return_value=detect_result),
    ):
        cfg = resolve_project_config()
        assert cfg.service_type == "gitlab"
        assert cfg.host == "gitlab.com"
        assert cfg.api_url == "https://gitlab.com/api/v4"
        assert cfg.owner == "user"
        assert cfg.repo == "project"


def test_resolve_api_url_from_host_config():
    """api_url が config.toml の hosts セクションから取得される場合。"""
    from gfo.detect import DetectResult

    detect_result = DetectResult(
        service_type="gitlab",
        host="gitlab.example.com",
        owner="user",
        repo="project",
    )
    git_cfg = {
        "gfo.type": None,
        "gfo.host": None,
        "gfo.api-url": None,
        "gfo.organization": None,
        "gfo.project-key": None,
    }
    host_cfg = {"type": "gitlab", "api_url": "https://gitlab.example.com/custom/api"}
    with (
        patch("gfo.git_util.git_config_get", side_effect=_mock_git_config(git_cfg)),
        patch("gfo.detect.detect_service", return_value=detect_result),
        patch("gfo.config.get_host_config", return_value=host_cfg),
    ):
        cfg = resolve_project_config()
        assert cfg.api_url == "https://gitlab.example.com/custom/api"


def test_resolve_azure_devops():
    """Azure DevOps の解決 (organization + project_key)。"""
    from gfo.detect import DetectResult

    detect_result = DetectResult(
        service_type="azure-devops",
        host="dev.azure.com",
        owner="myorg",
        repo="myrepo",
        organization="myorg",
        project="myproj",
    )
    git_cfg = {
        "gfo.type": None,
        "gfo.host": None,
        "gfo.api-url": None,
        "gfo.organization": None,
        "gfo.project-key": None,
    }
    with (
        patch("gfo.git_util.git_config_get", side_effect=_mock_git_config(git_cfg)),
        patch("gfo.detect.detect_service", return_value=detect_result),
    ):
        cfg = resolve_project_config()
        assert cfg.service_type == "azure-devops"
        assert cfg.organization == "myorg"
        assert cfg.project_key == "myproj"
        assert cfg.api_url == "https://dev.azure.com/myorg/myproj/_apis"


def test_resolve_raises_when_service_type_unresolvable():
    """detect_service が空の service_type を返した場合に ConfigError が発生する。"""
    from gfo.detect import DetectResult

    detect_result = DetectResult(service_type="", host="", owner="u", repo="r")
    git_cfg = {k: None for k in [
        "gfo.type", "gfo.host", "gfo.api-url", "gfo.organization", "gfo.project-key"
    ]}
    with (
        patch("gfo.git_util.git_config_get", side_effect=_mock_git_config(git_cfg)),
        patch("gfo.detect.detect_service", return_value=detect_result),
    ):
        with pytest.raises(ConfigError, match="service type"):
            resolve_project_config()


def test_resolve_git_config_does_not_call_detect_service():
    """git config に type/host があれば detect_service は呼ばれない。"""
    git_cfg = {
        "gfo.type": "github",
        "gfo.host": "github.com",
        "gfo.api-url": None,
        "gfo.organization": None,
        "gfo.project-key": None,
    }
    with (
        patch("gfo.git_util.git_config_get", side_effect=_mock_git_config(git_cfg)),
        patch(
            "gfo.git_util.get_remote_url",
            return_value="https://github.com/owner/repo.git",
        ),
        patch("gfo.detect.detect_service") as mock_detect,
    ):
        resolve_project_config()
    mock_detect.assert_not_called()


def test_resolve_only_shost_in_git_config():
    """git config に host のみある場合 → detect_service() が呼ばれ stype が補完される。"""
    from gfo.detect import DetectResult

    detect_result = DetectResult(
        service_type="github", host="github.com", owner="user", repo="repo"
    )
    git_cfg = {
        "gfo.type": None,
        "gfo.host": "github.com",
        "gfo.api-url": None,
        "gfo.organization": None,
        "gfo.project-key": None,
    }
    with (
        patch("gfo.git_util.git_config_get", side_effect=_mock_git_config(git_cfg)),
        patch(
            "gfo.detect.detect_service", return_value=detect_result
        ) as mock_detect,
    ):
        cfg = resolve_project_config()
    mock_detect.assert_called_once()
    assert cfg.host == "github.com"
    assert cfg.service_type == "github"


def test_resolve_only_stype_in_git_config():
    """git config に type のみある場合 → detect_service() が呼ばれる。"""
    from gfo.detect import DetectResult

    detect_result = DetectResult(
        service_type="github", host="github.com", owner="user", repo="repo"
    )
    git_cfg = {
        "gfo.type": "github",
        "gfo.host": None,
        "gfo.api-url": None,
        "gfo.organization": None,
        "gfo.project-key": None,
    }
    with (
        patch("gfo.git_util.git_config_get", side_effect=_mock_git_config(git_cfg)),
        patch(
            "gfo.detect.detect_service", return_value=detect_result
        ) as mock_detect,
    ):
        cfg = resolve_project_config()
    mock_detect.assert_called_once()
    assert cfg.service_type == "github"


def test_resolve_git_config_org_override():
    """git config の gfo.organization が detect 結果を上書きする。"""
    from gfo.detect import DetectResult

    detect_result = DetectResult(
        service_type="azure-devops",
        host="dev.azure.com",
        owner="org",
        repo="repo",
        organization="original-org",
        project="proj",
    )
    git_cfg = {
        "gfo.type": None,
        "gfo.host": None,
        "gfo.api-url": None,
        "gfo.organization": "override-org",
        "gfo.project-key": None,
    }
    with (
        patch("gfo.git_util.git_config_get", side_effect=_mock_git_config(git_cfg)),
        patch("gfo.detect.detect_service", return_value=detect_result),
    ):
        cfg = resolve_project_config()
    assert cfg.organization == "override-org"


# ── save_project_config ──


def test_save_project_config():
    cfg = ProjectConfig(
        service_type="github",
        host="github.com",
        api_url="https://api.github.com",
        owner="owner",
        repo="repo",
    )
    with patch("gfo.git_util.git_config_set") as mock_set:
        save_project_config(cfg)
        assert mock_set.call_count == 5  # type, host, api-url, owner, repo
        mock_set.assert_any_call("gfo.type", "github", cwd=None)
        mock_set.assert_any_call("gfo.host", "github.com", cwd=None)
        mock_set.assert_any_call("gfo.api-url", "https://api.github.com", cwd=None)
        mock_set.assert_any_call("gfo.owner", "owner", cwd=None)
        mock_set.assert_any_call("gfo.repo", "repo", cwd=None)


def test_save_project_config_with_org():
    cfg = ProjectConfig(
        service_type="azure-devops",
        host="dev.azure.com",
        api_url="https://dev.azure.com/org/proj/_apis",
        owner="org",
        repo="repo",
        organization="org",
        project_key="proj",
    )
    with patch("gfo.git_util.git_config_set") as mock_set:
        save_project_config(cfg)
        assert mock_set.call_count == 7  # type, host, api-url, owner, repo, organization, project-key
        mock_set.assert_any_call("gfo.organization", "org", cwd=None)
        mock_set.assert_any_call("gfo.project-key", "proj", cwd=None)


def test_resolve_remote_url_failure_falls_back_to_git_config_owner_repo():
    """remote URL が取れない場合、git config の gfo.owner / gfo.repo を使う。"""
    from gfo.exceptions import GitCommandError

    git_cfg = {
        "gfo.type": "github",
        "gfo.host": "github.com",
        "gfo.api-url": None,
        "gfo.owner": "ci-owner",
        "gfo.repo": "ci-repo",
        "gfo.organization": None,
        "gfo.project-key": None,
    }
    with (
        patch("gfo.git_util.git_config_get", side_effect=_mock_git_config(git_cfg)),
        patch(
            "gfo.git_util.get_remote_url",
            side_effect=GitCommandError("no remote"),
        ),
    ):
        cfg = resolve_project_config()
    assert cfg.owner == "ci-owner"
    assert cfg.repo == "ci-repo"


def test_resolve_owner_repo_git_config_override():
    """gfo.owner / gfo.repo の git config が remote URL 解析結果を上書きする。"""
    git_cfg = {
        "gfo.type": "github",
        "gfo.host": "github.com",
        "gfo.api-url": None,
        "gfo.owner": "override-owner",
        "gfo.repo": "override-repo",
        "gfo.organization": None,
        "gfo.project-key": None,
    }
    with (
        patch("gfo.git_util.git_config_get", side_effect=_mock_git_config(git_cfg)),
        patch(
            "gfo.git_util.get_remote_url",
            return_value="https://github.com/original-owner/original-repo.git",
        ),
    ):
        cfg = resolve_project_config()
    assert cfg.owner == "override-owner"
    assert cfg.repo == "override-repo"
