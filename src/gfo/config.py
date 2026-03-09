"""3 層設定の解決ロジック。git config、TOML ユーザー設定、detect.py を統合する。"""

from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from gfo.exceptions import ConfigError


@dataclass
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
    return Path.home() / ".config" / "gfo"


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
    except PermissionError as e:
        raise ConfigError(f"Permission denied reading config file {path}: {e}") from e


def get_default_output_format() -> str:
    """config.toml の defaults.output を返す。未設定なら "table"。"""
    cfg = load_user_config()
    return cfg.get("defaults", {}).get("output", "table")


def get_default_host() -> str | None:
    """config.toml の defaults.host を返す。未設定なら None。"""
    cfg = load_user_config()
    return cfg.get("defaults", {}).get("host")


def get_host_config(host: str) -> dict | None:
    """config.toml の hosts.{host} セクションを返す。未設定なら None。"""
    cfg = load_user_config()
    hosts = cfg.get("hosts", {})
    return hosts.get(host)


def get_hosts_config() -> dict[str, str]:
    """config.toml の hosts セクションから {host: service_type} マッピングを返す。

    detect.py から呼ばれる。各ホストの type フィールドを使用する。
    """
    cfg = load_user_config()
    hosts = cfg.get("hosts", {})
    result: dict[str, str] = {}
    for host_name, host_cfg in hosts.items():
        if isinstance(host_cfg, dict) and "type" in host_cfg:
            result[host_name] = host_cfg["type"]
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

    # 1-2. git config から service_type / host を取得
    stype = gfo.git_util.git_config_get("gfo.type", cwd=cwd)
    shost = gfo.git_util.git_config_get("gfo.host", cwd=cwd)

    # 3. いずれも未設定なら detect_service() で自動検出
    if stype and shost:
        # remote URL が存在しない環境でも失敗しないよう任意解析にする
        try:
            remote_url = gfo.git_util.get_remote_url(cwd=cwd)
            detect_result = gfo.detect.detect_from_url(remote_url)
            owner = detect_result.owner
            repo = detect_result.repo
            organization = detect_result.organization
            project_key = detect_result.project
        except Exception:
            owner = ""
            repo = ""
            organization = None
            project_key = None
    else:
        detect_result = gfo.detect.detect_service(cwd=cwd)
        stype = stype or detect_result.service_type
        shost = shost or detect_result.host
        owner = detect_result.owner
        repo = detect_result.repo
        organization = detect_result.organization
        project_key = detect_result.project

    if not stype:
        raise ConfigError("Could not resolve service type.")
    if not shost:
        raise ConfigError("Could not resolve host.")

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
        host_cfg = get_host_config(shost)
        if host_cfg and "api_url" in host_cfg:
            api_url = host_cfg["api_url"]
    if not api_url:
        api_url = _build_default_api_url(stype, shost, organization, project_key)

    return ProjectConfig(
        service_type=stype,
        host=shost,
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
    if config.organization:
        gfo.git_util.git_config_set("gfo.organization", config.organization, cwd=cwd)
    if config.project_key:
        gfo.git_util.git_config_set("gfo.project-key", config.project_key, cwd=cwd)


# ── デフォルト API URL 構築 ──


def _build_default_api_url(
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
        if not organization or not project:
            raise ConfigError(
                "Azure DevOps requires organization and project_key."
            )
        return f"https://dev.azure.com/{organization}/{project}/_apis"
    if service_type in ("gitea", "forgejo", "gogs"):
        return f"https://{host}/api/v1"
    if service_type == "gitbucket":
        return f"https://{host}/api/v3"
    if service_type == "backlog":
        return f"https://{host}/api/v2"
    raise ConfigError(f"Unknown service type: {service_type}")
