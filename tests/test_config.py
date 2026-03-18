"""config.py のテスト。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from gfo.config import (
    ProjectConfig,
    build_clone_url,
    build_default_api_url,
    get_config_dir,
    get_config_path,
    get_configured_output_format,
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
    with (
        patch("gfo.config.sys") as mock_sys,
        patch.dict("os.environ", {"APPDATA": r"C:\Users\test\AppData\Roaming"}),
    ):
        mock_sys.platform = "win32"
        result = get_config_dir()
        assert result == Path(r"C:\Users\test\AppData\Roaming\gfo")


def test_get_config_dir_windows_no_appdata():
    home = Path.home()
    with (
        patch("gfo.config.sys") as mock_sys,
        patch.dict("os.environ", {"APPDATA": ""}, clear=False),
    ):
        mock_sys.platform = "win32"
        result = get_config_dir()
        assert result == home / "AppData" / "Roaming" / "gfo"


def test_get_config_dir_unix():
    with patch("gfo.config.sys") as mock_sys:
        mock_sys.platform = "linux"
        result = get_config_dir()
        assert result == Path.home() / ".config" / "gfo"


def test_get_config_dir_unix_xdg_config_home():
    """XDG_CONFIG_HOME が設定されている場合はそのパスを使う。"""
    with (
        patch("gfo.config.sys") as mock_sys,
        patch.dict("os.environ", {"XDG_CONFIG_HOME": "/custom/path"}),
    ):
        mock_sys.platform = "linux"
        result = get_config_dir()
        assert result == Path("/custom/path") / "gfo"


def test_get_config_dir_unix_xdg_config_home_empty():
    """XDG_CONFIG_HOME が空文字のときはデフォルトの ~/.config/gfo にフォールバックする。"""
    with (
        patch("gfo.config.sys") as mock_sys,
        patch.dict("os.environ", {"XDG_CONFIG_HOME": ""}),
    ):
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
    """PermissionError（OSError の一種）が ConfigError に変換される。"""
    config_file = tmp_path / "config.toml"
    config_file.write_text("")
    with (
        patch("gfo.config.get_config_path", return_value=config_file),
        patch("builtins.open", side_effect=PermissionError("Permission denied")),
    ):
        with pytest.raises(ConfigError, match="Failed to read config file"):
            load_user_config()


def test_load_user_config_toml_decode_error(tmp_path):
    """不正な TOML → ConfigError（TOMLDecodeError）。"""
    config_file = tmp_path / "config.toml"
    config_file.write_text("invalid toml [[[\n")
    with patch("gfo.config.get_config_path", return_value=config_file):
        with pytest.raises(ConfigError, match="Failed to parse config file"):
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


# ── get_configured_output_format ──


def test_get_configured_output_format_none():
    """未設定時に None を返す。"""
    with patch("gfo.config.load_user_config", return_value={}):
        assert get_configured_output_format() is None


def test_get_configured_output_format_json():
    """設定時に値を返す。"""
    with patch(
        "gfo.config.load_user_config",
        return_value={"defaults": {"output": "json"}},
    ):
        assert get_configured_output_format() == "json"


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


def test_get_host_config_uppercase_host_normalized():
    """大文字ホストで検索しても小文字キーの設定が見つかる。"""
    cfg = {"hosts": {"gitlab.example.com": {"type": "gitlab"}}}
    with patch("gfo.config.load_user_config", return_value=cfg):
        result = get_host_config("GITLAB.EXAMPLE.COM")
        assert result == {"type": "gitlab"}


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
    assert build_default_api_url("github", "ghe.example.com") == "https://ghe.example.com/api/v3"


def test_build_gitlab():
    assert build_default_api_url("gitlab", "gitlab.com") == "https://gitlab.com/api/v4"


def test_build_bitbucket():
    assert build_default_api_url("bitbucket", "bitbucket.org") == "https://api.bitbucket.org/2.0"


def test_build_azure_devops():
    assert (
        build_default_api_url("azure-devops", "dev.azure.com", "myorg", "myproj")
        == "https://dev.azure.com/myorg/myproj/_apis"
    )


def test_build_azure_devops_missing_org():
    with pytest.raises(ConfigError, match="organization"):
        build_default_api_url("azure-devops", "dev.azure.com")


def test_build_azure_devops_missing_project():
    """organization あり・project なしの場合は "project" を含む ConfigError（R35-02）。"""
    with pytest.raises(ConfigError, match="project"):
        build_default_api_url("azure-devops", "dev.azure.com", organization="myorg")


def test_build_gitea():
    assert build_default_api_url("gitea", "gitea.local") == "https://gitea.local/api/v1"


def test_build_forgejo():
    assert build_default_api_url("forgejo", "codeberg.org") == "https://codeberg.org/api/v1"


def test_build_gogs():
    assert build_default_api_url("gogs", "gogs.local") == "https://gogs.local/api/v1"


def test_build_gitbucket():
    assert build_default_api_url("gitbucket", "gb.local") == "https://gb.local/api/v3"


def test_build_backlog():
    assert (
        build_default_api_url("backlog", "space.backlog.com") == "https://space.backlog.com/api/v2"
    )


def test_build_unknown_service():
    with pytest.raises(ConfigError, match="Unknown service type"):
        build_default_api_url("unknown", "example.com")


# ── build_clone_url ──


def test_build_clone_url_github():
    url = build_clone_url("github", "github.com", "owner", "repo")
    assert url == "https://github.com/owner/repo.git"


def test_build_clone_url_github_enterprise():
    """GHE ホストで clone URL にホスト名が使われる（R36修正確認）。"""
    url = build_clone_url("github", "ghe.example.com", "owner", "repo")
    assert url == "https://ghe.example.com/owner/repo.git"


def test_build_clone_url_bitbucket():
    url = build_clone_url("bitbucket", "bitbucket.org", "owner", "repo")
    assert url == "https://bitbucket.org/owner/repo.git"


def test_build_clone_url_azure_devops():
    """project 未指定時は owner にフォールバック。"""
    url = build_clone_url("azure-devops", "dev.azure.com", "myorg", "repo")
    assert url == "https://dev.azure.com/myorg/myorg/_git/repo"


def test_build_clone_url_azure_devops_with_project():
    """project を明示指定した場合は正しく反映される。"""
    url = build_clone_url("azure-devops", "dev.azure.com", "myorg", "repo", project="myproj")
    assert url == "https://dev.azure.com/myorg/myproj/_git/repo"


def test_build_clone_url_azure_devops_custom_host():
    """非既定ホストでも host がそのまま URL に使われる。"""
    url = build_clone_url("azure-devops", "azure.example.com", "myorg", "repo", project="myproj")
    assert url == "https://azure.example.com/myorg/myproj/_git/repo"


def test_build_default_api_url_azure_devops_custom_host():
    """非既定ホストでも host がそのまま API URL に使われる。"""
    url = build_default_api_url("azure-devops", "azure.example.com", "myorg", "myproj")
    assert url == "https://azure.example.com/myorg/myproj/_apis"


def test_build_clone_url_gitlab():
    url = build_clone_url("gitlab", "gitlab.com", "owner", "repo")
    assert url == "https://gitlab.com/owner/repo.git"


def test_build_clone_url_gitbucket():
    url = build_clone_url("gitbucket", "gb.local", "owner", "repo")
    assert url == "https://gb.local/git/owner/repo.git"


def test_build_clone_url_backlog():
    url = build_clone_url("backlog", "space.backlog.com", "owner", "repo")
    assert url == "https://space.backlog.com/git/owner/repo.git"


def test_build_clone_url_unknown_service_default():
    """未知のサービスはデフォルトの HTTPS URL を返す。"""
    url = build_clone_url("unknown-svc", "example.com", "owner", "repo")
    assert url == "https://example.com/owner/repo.git"


def test_build_clone_url_empty_owner_raises():
    """owner が空のとき ConfigError。"""
    with pytest.raises(ConfigError, match="owner and name must be non-empty"):
        build_clone_url("github", "github.com", "", "repo")


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
    git_cfg = {
        k: None
        for k in ["gfo.type", "gfo.host", "gfo.api-url", "gfo.organization", "gfo.project-key"]
    }
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


def test_resolve_only_host_in_git_config():
    """git config に host のみある場合 → detect_service() が呼ばれ type が補完される。"""
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
        patch("gfo.detect.detect_service", return_value=detect_result) as mock_detect,
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
        patch("gfo.detect.detect_service", return_value=detect_result) as mock_detect,
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
        assert (
            mock_set.call_count == 7
        )  # type, host, api-url, owner, repo, organization, project-key
        mock_set.assert_any_call("gfo.organization", "org", cwd=None)
        mock_set.assert_any_call("gfo.project-key", "proj", cwd=None)


def test_save_project_config_empty_owner_repo():
    """owner/repo が空文字列でも git_config_set が呼ばれる（既存値を上書きする）。"""
    cfg = ProjectConfig(
        service_type="github",
        host="github.com",
        api_url="https://api.github.com",
        owner="",
        repo="",
    )
    with patch("gfo.git_util.git_config_set") as mock_set:
        save_project_config(cfg)
        mock_set.assert_any_call("gfo.owner", "", cwd=None)
        mock_set.assert_any_call("gfo.repo", "", cwd=None)


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


def test_resolve_raises_when_no_host():
    """gfo.host が未設定かつ detect_service も host を返さない → ConfigError。"""
    from gfo.detect import DetectResult

    git_cfg = {
        "gfo.type": None,
        "gfo.host": None,
        "gfo.api-url": None,
        "gfo.owner": None,
        "gfo.repo": None,
        "gfo.organization": None,
        "gfo.project-key": None,
    }
    detect_result = DetectResult(
        service_type="github",
        host="",  # 空文字 = falsy
        owner="owner",
        repo="repo",
    )
    with (
        patch("gfo.git_util.git_config_get", side_effect=_mock_git_config(git_cfg)),
        patch("gfo.detect.detect_service", return_value=detect_result),
    ):
        with pytest.raises(ConfigError, match="Could not resolve host"):
            resolve_project_config()


def test_resolve_project_key_git_config_override():
    """gfo.project-key の git config が project_key を上書きする。"""
    git_cfg = {
        "gfo.type": "backlog",
        "gfo.host": "space.backlog.com",
        "gfo.api-url": None,
        "gfo.owner": None,
        "gfo.repo": None,
        "gfo.organization": None,
        "gfo.project-key": "MY-PROJECT",
    }
    with (
        patch("gfo.git_util.git_config_get", side_effect=_mock_git_config(git_cfg)),
        patch(
            "gfo.git_util.get_remote_url",
            return_value="https://space.backlog.com/git/owner/repo.git",
        ),
    ):
        cfg = resolve_project_config()
    assert cfg.project_key == "MY-PROJECT"


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


# ── --remote override 時の resolve_project_config ──


def test_resolve_remote_override_skips_git_config_shortcut():
    """--remote 指定時は git config ショートカットをスキップして detect_service() を通す。"""
    from gfo._context import cli_remote
    from gfo.detect import DetectResult

    git_cfg = {
        "gfo.type": "gitea",
        "gfo.host": "gitea.local",
        "gfo.api-url": None,
        "gfo.organization": None,
        "gfo.project-key": None,
        "gfo.owner": None,
        "gfo.repo": None,
    }
    detect_result = DetectResult(
        service_type="github", host="github.com", owner="owner", repo="repo"
    )
    token = cli_remote.set("upstream")
    try:
        with (
            patch("gfo.git_util.git_config_get", side_effect=_mock_git_config(git_cfg)),
            patch("gfo.detect.detect_service", return_value=detect_result) as mock_detect,
        ):
            cfg = resolve_project_config()
        mock_detect.assert_called_once()
        assert cfg.service_type == "github"
        assert cfg.host == "github.com"
    finally:
        cli_remote.reset(token)


def test_resolve_no_override_still_uses_git_config_shortcut():
    """override 未指定時は従来通り git config ショートカットが動作する。"""
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
        patch("gfo.detect.detect_service") as mock_detect,
    ):
        cfg = resolve_project_config()
    mock_detect.assert_not_called()
    assert cfg.service_type == "github"


# ── --repo override 時の resolve_project_config ──


def test_resolve_repo_override_skips_git_config_shortcut():
    """--repo 指定時は git config ショートカットをスキップして detect_service() を通す。"""
    from gfo._context import cli_repo
    from gfo.detect import DetectResult

    git_cfg = {
        "gfo.type": "gitea",
        "gfo.host": "gitea.local",
        "gfo.api-url": None,
        "gfo.organization": None,
        "gfo.project-key": None,
        "gfo.owner": None,
        "gfo.repo": None,
    }
    detect_result = DetectResult(
        service_type="github", host="github.com", owner="owner", repo="repo"
    )
    token = cli_repo.set("github.com/owner/repo")
    try:
        with (
            patch("gfo.git_util.git_config_get", side_effect=_mock_git_config(git_cfg)),
            patch("gfo.detect.detect_service", return_value=detect_result) as mock_detect,
        ):
            cfg = resolve_project_config()
        mock_detect.assert_called_once()
        assert cfg.service_type == "github"
        assert cfg.host == "github.com"
    finally:
        cli_repo.reset(token)
