"""トークン解決と credentials.toml 管理。"""

from __future__ import annotations

import getpass
import os
import re
import subprocess
import sys
import tomllib
import warnings
from pathlib import Path

from gfo.config import get_config_dir, get_credentials_path
from gfo.exceptions import AuthError, ConfigError

_SERVICE_ENV_MAP: dict[str, str] = {
    "github": "GITHUB_TOKEN",
    "gitlab": "GITLAB_TOKEN",
    "gitea": "GITEA_TOKEN",
    "forgejo": "GITEA_TOKEN",
    "gogs": "GITEA_TOKEN",
    "gitbucket": "GITBUCKET_TOKEN",
    "bitbucket": "BITBUCKET_APP_PASSWORD",
    "backlog": "BACKLOG_API_KEY",
    "azure-devops": "AZURE_DEVOPS_PAT",
}

# 固定ホスト名を持つクラウドサービスのデフォルトホスト
_SERVICE_DEFAULT_HOSTS: dict[str, str] = {
    "github": "github.com",
    "gitlab": "gitlab.com",
    "bitbucket": "bitbucket.org",
    "azure-devops": "dev.azure.com",
}


def resolve_token(host: str, service_type: str) -> str:
    """トークンを解決する。

    解決順序:
    1. credentials.toml の tokens.{host}
    2. _SERVICE_ENV_MAP[service_type] 環境変数
    3. GFO_TOKEN 環境変数
    4. すべて未設定なら AuthError
    """
    # 1. credentials.toml
    tokens = load_tokens()
    token_val = tokens.get(host, "")
    if token_val and token_val.strip():
        return token_val

    # 2. サービス別環境変数
    env_var = _SERVICE_ENV_MAP.get(service_type)
    if env_var:
        val = os.environ.get(env_var)
        if val:
            return val

    # 3. GFO_TOKEN
    gfo_token = os.environ.get("GFO_TOKEN")
    if gfo_token:
        return gfo_token

    # 4. 未設定
    raise AuthError(host)


def save_token(host: str, token: str) -> None:
    """credentials.toml にトークンを保存する。"""
    if not token or not token.strip():
        raise AuthError(host, "Token must not be empty.")
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)

    tokens = load_tokens()
    tokens[host] = token

    path = get_credentials_path()
    _write_credentials_toml(path, tokens)

    # パーミッション設定
    if sys.platform != "win32":
        os.chmod(path, 0o600)
    else:
        try:
            username = getpass.getuser()
            result = subprocess.run(
                [
                    "icacls",
                    str(path),
                    "/inheritance:r",
                    "/grant:r",
                    f"{username}:F",
                ],
                capture_output=True,
                check=False,
            )
            if result.returncode != 0:
                warnings.warn(
                    "Could not set file permissions on credentials file "
                    f"(icacls exited with code {result.returncode}).",
                    stacklevel=2,
                )
        except OSError:
            warnings.warn(
                "Could not set file permissions on credentials file "
                "(getpass.getuser() failed, possibly in CI/Docker environment).",
                stacklevel=2,
            )


def load_tokens() -> dict[str, str]:
    """credentials.toml の [tokens] セクションを dict で返す。"""
    path = get_credentials_path()
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        try:
            data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ConfigError(f"Failed to parse credentials file {path}: {e}") from e
    return data.get("tokens", {})


def get_auth_status() -> list[dict[str, str]]:
    """全ホストのトークン状態を返す。トークン値は含めない。"""
    result: list[dict[str, str]] = []
    seen_hosts: set[str] = set()

    # credentials.toml のトークン
    tokens = load_tokens()
    for host in tokens:
        result.append(
            {"host": host, "status": "configured", "source": "credentials.toml"}
        )
        seen_hosts.add(host)

    # 環境変数で設定されているトークン（env_var ごとに 1 エントリ、重複を避ける）
    seen_env_vars: set[str] = set()
    for service_type, env_var in _SERVICE_ENV_MAP.items():
        if env_var in seen_env_vars:
            continue
        val = os.environ.get(env_var)
        if val:
            seen_env_vars.add(env_var)
            # クラウドサービスは実ホスト名を使用、自己ホスト型は "(env) service" 形式
            display_host = _SERVICE_DEFAULT_HOSTS.get(service_type, f"(env) {service_type}")
            result.append(
                {
                    "host": display_host,
                    "status": "configured",
                    "source": f"env:{env_var}",
                }
            )

    return result


# ── 内部ヘルパー ──


def _write_credentials_toml(path: Path, tokens: dict[str, str]) -> None:
    """credentials.toml を書き出す。"""
    lines = ["[tokens]"]
    for key, value in tokens.items():
        escaped = (
            value.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")
        )
        # \x00-\x1f のうち上記以外の制御文字をユニコードエスケープに変換
        escaped = re.sub(
            r"[\x00-\x08\x0b\x0c\x0e-\x1f]",
            lambda m: f"\\u{ord(m.group()):04x}",
            escaped,
        )
        lines.append(f'"{key}" = "{escaped}"')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
