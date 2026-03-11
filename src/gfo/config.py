"""3 層設定の解決ロジック。git config、TOML ユーザー設定、detect.py を統合する。"""

from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gfo.exceptions import ConfigError, DetectionError, GitCommandError


@dataclass(frozen=True)
class ProjectConfig:
    """解決済みプロジェクト設定。"""

    service_type: str
    host: str
    api_url: str
    owner: str
    repo: str
    organization: str | None = None  # Azure DevOps
    project_key: str | None = None  # Backlog / Azure DevOps


# ── パス ──


def get_config_dir() -> Path:
    """プラットフォーム別の設定ディレクトリパスを返す。"""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "").strip()
        if appdata:
            return Path(appdata) / "gfo"
        return Path.home() / "AppData" / "Roaming" / "gfo"
    return Path.home() / ".config" / "gfo"  # type: ignore[unreachable]


def get_config_path() -> Path:
    """config.toml のフルパスを返す。"""
    return get_config_dir() / "config.toml"


def get_credentials_path() -> Path:
    """credentials.toml のフルパスを返す。"""
    return get_config_dir() / "credentials.toml"


# ── TOML 読み込み ──


def load_user_config() -> dict:
    """config.toml を読み込み dict で返す。存在しなければ空 dict。"""
    path = get_config_path()
    if not path.exists():
        return {}
    try:
        with open(path, "rb") as f:
            try:
                return tomllib.load(f)
            except tomllib.TOMLDecodeError as e:
                raise ConfigError(f"Failed to parse config file {path}: {e}") from e
    except OSError as e:
        raise ConfigError(f"Failed to read config file {path}: {e}") from e


def get_default_output_format() -> str:
    """config.toml の defaults.output を返す。未設定なら "table"。"""
    cfg = load_user_config()
    defaults: dict[str, Any] = cfg.get("defaults", {})
    return str(defaults.get("output", "table"))


def get_default_host() -> str | None:
    """config.toml の defaults.host を返す。未設定なら None。"""
    cfg = load_user_config()
    defaults: dict[str, Any] = cfg.get("defaults", {})
    value = defaults.get("host")
    return str(value) if value is not None else None


def get_host_config(host: str) -> dict[str, Any] | None:
    """config.toml の hosts.{host} セクションを返す。未設定なら None。"""
    cfg = load_user_config()
    hosts: dict[str, Any] = cfg.get("hosts", {})
    result = hosts.get(host.lower()) or hosts.get(host)
    return result if isinstance(result, dict) else None


def get_hosts_config() -> dict[str, str]:
    """config.toml の hosts セクションから {host: service_type} マッピングを返す。

    detect.py から呼ばれる。各ホストの type フィールドを使用する。
    """
    cfg = load_user_config()
    hosts = cfg.get("hosts", {})
    result: dict[str, str] = {}
    for host_name, host_cfg in hosts.items():
        if isinstance(host_cfg, dict) and isinstance(host_cfg.get("type"), str):
            result[host_name.lower()] = host_cfg["type"]
    return result


# ── 設定解決 ──


def resolve_project_config(cwd: str | None = None) -> ProjectConfig:
    """3 層の設定解決を実行し、ProjectConfig を返す。"""
    # 循環依存回避のため遅延インポートを使用。
    # config.py はモジュールレベルで detect.py / git_util.py を import できない:
    #   detect.py → detect_service() で gfo.config を遅延 import
    #   config.py → resolve_project_config() で gfo.detect を遅延 import
    # 両者が互いを参照するため、トップレベル import にすると循環 ImportError が発生する。
    import gfo.detect
    import gfo.git_util

    # 1-2. git config から service_type / host を取得（saved_type / saved_host: git config 保存値）
    saved_type = gfo.git_util.git_config_get("gfo.type", cwd=cwd)
    saved_host = gfo.git_util.git_config_get("gfo.host", cwd=cwd)

    # 3. git config で両方設定済みの場合は remote URL から owner/repo を検出
    #    いずれか未設定なら detect_service() で自動検出（else ブロック）
    if saved_type and saved_host:
        # remote URL が存在しない環境でも失敗しないよう任意解析にする
        try:
            remote_url = gfo.git_util.get_remote_url(cwd=cwd)
            detect_result = gfo.detect.detect_from_url(remote_url)
            owner = detect_result.owner
            repo = detect_result.repo
            organization = detect_result.organization
            project_key = detect_result.project
        except (DetectionError, ConfigError, GitCommandError, ValueError, OSError):
            # bare リポジトリや CI 環境向け: git config の gfo.owner/gfo.repo を使用
            owner = gfo.git_util.git_config_get("gfo.owner", cwd=cwd) or ""
            repo = gfo.git_util.git_config_get("gfo.repo", cwd=cwd) or ""
            organization = None
            project_key = None
    else:
        detect_result = gfo.detect.detect_service(cwd=cwd)
        saved_type = saved_type or detect_result.service_type
        saved_host = saved_host or detect_result.host
        owner = detect_result.owner
        repo = detect_result.repo
        organization = detect_result.organization
        project_key = detect_result.project

    if not saved_type:
        raise ConfigError("Could not resolve service type.")
    if not saved_host:
        raise ConfigError("Could not resolve host.")

    # git config から owner / repo を上書き（bare リポジトリや CI 環境向け）
    owner_override = gfo.git_util.git_config_get("gfo.owner", cwd=cwd)
    if owner_override:
        owner = owner_override
    repo_override = gfo.git_util.git_config_get("gfo.repo", cwd=cwd)
    if repo_override:
        repo = repo_override

    # git config から organization / project_key を上書き
    org_override = gfo.git_util.git_config_get("gfo.organization", cwd=cwd)
    if org_override:
        organization = org_override
    pk_override = gfo.git_util.git_config_get("gfo.project-key", cwd=cwd)
    if pk_override:
        project_key = pk_override

    # 4. api_url の解決
    api_url = gfo.git_util.git_config_get("gfo.api-url", cwd=cwd)
    if not api_url:
        host_cfg = get_host_config(saved_host)
        if host_cfg and "api_url" in host_cfg:
            api_url = host_cfg["api_url"]
    if not api_url:
        api_url = build_default_api_url(saved_type, saved_host, organization, project_key)

    return ProjectConfig(
        service_type=saved_type,
        host=saved_host,
        api_url=api_url,
        owner=owner,
        repo=repo,
        organization=organization,
        project_key=project_key,
    )


def save_project_config(config: ProjectConfig, cwd: str | None = None) -> None:
    """ProjectConfig を git config --local に保存する。"""
    import gfo.git_util

    gfo.git_util.git_config_set("gfo.type", config.service_type, cwd=cwd)
    gfo.git_util.git_config_set("gfo.host", config.host, cwd=cwd)
    gfo.git_util.git_config_set("gfo.api-url", config.api_url, cwd=cwd)
    gfo.git_util.git_config_set("gfo.owner", config.owner, cwd=cwd)
    gfo.git_util.git_config_set("gfo.repo", config.repo, cwd=cwd)
    if config.organization:
        gfo.git_util.git_config_set("gfo.organization", config.organization, cwd=cwd)
    if config.project_key:
        gfo.git_util.git_config_set("gfo.project-key", config.project_key, cwd=cwd)


# ── URL 構築ヘルパー ──


def build_clone_url(
    service_type: str, host: str, owner: str, name: str, *, project: str | None = None
) -> str:
    """サービス種別・ホスト・owner/name から clone 用 HTTPS URL を構築する。"""
    if not owner or not name:
        raise ConfigError(
            f"Invalid repo format. Both owner and name must be non-empty, got owner={owner!r}, name={name!r}."
        )
    if service_type in ("github", "bitbucket"):
        return f"https://{host}/{owner}/{name}.git"
    if service_type == "azure-devops":
        effective_project = project if project is not None else owner
        return f"https://{host}/{owner}/{effective_project}/_git/{name}"
    if service_type in ("gitlab", "gitea", "forgejo", "gogs"):
        return f"https://{host}/{owner}/{name}.git"
    if service_type in ("gitbucket", "backlog"):
        return f"https://{host}/git/{owner}/{name}.git"
    return f"https://{host}/{owner}/{name}.git"


def build_default_api_url(
    service_type: str,
    host: str,
    organization: str | None = None,
    project: str | None = None,
) -> str:
    """サービス種別とホスト名からデフォルト API Base URL を構築する。"""
    if service_type == "github":
        if host == "github.com":
            return "https://api.github.com"
        return f"https://{host}/api/v3"
    if service_type == "gitlab":
        return f"https://{host}/api/v4"
    if service_type == "bitbucket":
        return "https://api.bitbucket.org/2.0"
    if service_type == "azure-devops":
        if not organization:
            raise ConfigError(
                "Azure DevOps requires an organization. Run 'gfo init' first to configure."
            )
        if not project:
            raise ConfigError("Azure DevOps requires a project. Run 'gfo init' first to configure.")
        return f"https://{host}/{organization}/{project}/_apis"
    if service_type in ("gitea", "forgejo", "gogs"):
        return f"https://{host}/api/v1"
    if service_type == "gitbucket":
        return f"https://{host}/api/v3"
    if service_type == "backlog":
        return f"https://{host}/api/v2"
    raise ConfigError(f"Unknown service type: {service_type}")
