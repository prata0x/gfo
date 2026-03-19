"""トークン解決と credentials.toml 管理。"""

from __future__ import annotations

import getpass
import os
import re
import subprocess  # nosec B404
import sys
import tempfile
import tomllib
import warnings
from contextlib import suppress
from pathlib import Path

from gfo._context import cli_account
from gfo.config import get_config_dir, get_credentials_path
from gfo.exceptions import AuthError, ConfigError, GitCommandError

_SERVICE_ENV_MAP: dict[str, str] = {
    "github": "GITHUB_TOKEN",
    "gitlab": "GITLAB_TOKEN",
    "gitea": "GITEA_TOKEN",
    "forgejo": "GITEA_TOKEN",
    "gogs": "GITEA_TOKEN",
    "gitbucket": "GITBUCKET_TOKEN",
    "bitbucket": "BITBUCKET_TOKEN",
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
    1. credentials.toml の tokens.{host}.{resolved_account}
    2. _SERVICE_ENV_MAP[service_type] 環境変数
    3. GFO_TOKEN 環境変数
    4. すべて未設定なら AuthError
    """
    host = host.lower()
    # 1. credentials.toml
    tokens = load_tokens()
    host_accounts = tokens.get(host)
    if host_accounts:
        account_name = _resolve_account_name(host, host_accounts)
        token_val = host_accounts.get(account_name, "")
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


def save_token(host: str, token: str, account: str = "default") -> None:
    """credentials.toml にトークンを保存する。"""
    if account == "_default":
        raise ConfigError("'_default' is a reserved key and cannot be used as an account name.")
    if not token.strip():
        raise AuthError(host, "Token must not be empty.")
    host = host.lower()
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)

    tokens = load_tokens()
    host_accounts = tokens.get(host, {})
    host_accounts[account] = token
    # 新ホスト初回保存時に _default を設定
    if "_default" not in host_accounts:
        host_accounts["_default"] = account
    tokens[host] = host_accounts

    path = get_credentials_path()
    _write_credentials_toml(path, tokens)
    _set_credentials_permissions(path)


def switch_account(host: str, account: str) -> None:
    """アクティブアカウントを切り替える。"""
    if account == "_default":
        raise ConfigError("'_default' is a reserved key and cannot be used as an account name.")
    host = host.lower()
    tokens = load_tokens()
    host_accounts = tokens.get(host)
    if not host_accounts:
        raise ConfigError(f"No tokens configured for host: {host}")
    if account not in host_accounts:
        raise ConfigError(f"Account '{account}' not found for host: {host}")
    host_accounts["_default"] = account
    tokens[host] = host_accounts

    path = get_credentials_path()
    _write_credentials_toml(path, tokens)
    _set_credentials_permissions(path)


def list_accounts(host: str) -> list[str]:
    """ホストに登録済みのアカウント名一覧を返す（_default を除く）。"""
    host = host.lower()
    tokens = load_tokens()
    host_accounts = tokens.get(host, {})
    return [k for k in host_accounts if k != "_default"]


def remove_token(host: str, account: str | None = None) -> None:
    """トークンを削除する。account 指定時はそのアカウントのみ、None 時はホスト全体を削除。"""
    if account == "_default":
        raise ConfigError("'_default' is a reserved key and cannot be used as an account name.")
    host = host.lower()
    tokens = load_tokens()
    if host not in tokens:
        raise ConfigError(f"No tokens configured for host: {host}")

    if account is None:
        del tokens[host]
    else:
        host_accounts = tokens[host]
        if account not in host_accounts:
            raise ConfigError(f"Account '{account}' not found for host: {host}")
        del host_accounts[account]
        # _default が削除されたアカウントを指していた場合、残りの最初のアカウントに切り替え
        if host_accounts.get("_default") == account:
            remaining = [k for k in host_accounts if k != "_default"]
            if remaining:
                host_accounts["_default"] = remaining[0]
            else:
                del tokens[host]
        # _default のみ残った場合はホストごと削除
        if host in tokens and list(tokens[host].keys()) == ["_default"]:
            del tokens[host]

    path = get_credentials_path()
    _write_credentials_toml(path, tokens)
    _set_credentials_permissions(path)


def load_tokens() -> dict[str, dict[str, str]]:
    """credentials.toml の [tokens] セクションを dict で返す。"""
    path = get_credentials_path()
    try:
        with open(path, "rb") as f:
            try:
                data = tomllib.load(f)
            except tomllib.TOMLDecodeError as e:
                raise ConfigError(f"Failed to parse credentials file {path}: {e}") from e
    except FileNotFoundError:
        return {}
    except OSError as e:
        raise ConfigError(f"Failed to read credentials file {path}: {e}") from e
    tokens = data.get("tokens", {})
    old_format_hosts = [str(k) for k, v in tokens.items() if isinstance(v, str)]
    if old_format_hosts:
        warnings.warn(
            "credentials.toml contains old format entries for: "
            f"{', '.join(old_format_hosts)}. "
            "Run 'gfo auth login' to re-register.",
            stacklevel=2,
        )
    return {
        str(k): {str(ak): str(av) for ak, av in v.items()}
        for k, v in tokens.items()
        if isinstance(v, dict)
    }


def get_auth_status() -> list[dict[str, str]]:
    """全ホストのトークン状態を返す。トークン値は含めない。"""
    result: list[dict[str, str]] = []
    seen_hosts: set[str] = set()

    # credentials.toml のトークン
    tokens = load_tokens()
    for host, accounts in tokens.items():
        default_account = accounts.get("_default", "default")
        for acct in accounts:
            if acct == "_default":
                continue
            active = "*" if acct == default_account else ""
            result.append(
                {
                    "host": host,
                    "status": "configured",
                    "source": "credentials.toml",
                    "account": acct,
                    "active": active,
                }
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
            if display_host not in seen_hosts:
                result.append(
                    {
                        "host": display_host,
                        "status": "configured",
                        "source": f"env:{env_var}",
                        "account": "",
                        "active": "",
                    }
                )
                seen_hosts.add(display_host)

    # GFO_TOKEN 汎用フォールバック（resolve_token の最終手段）
    if os.environ.get("GFO_TOKEN"):
        host_key = "(all services)"
        if host_key not in seen_hosts:
            result.append(
                {
                    "host": host_key,
                    "status": "configured",
                    "source": "env:GFO_TOKEN",
                    "account": "",
                    "active": "",
                }
            )

    return result


# ── 内部ヘルパー ──


def _escape_toml_value(value: str) -> str:
    """TOML 値のエスケープ処理。"""
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
    return escaped


def _set_credentials_permissions(path: Path) -> None:
    """credentials.toml にパーミッションを設定する。"""
    if sys.platform != "win32":
        os.chmod(path, 0o600)
    else:
        try:
            username = getpass.getuser()
            result = subprocess.run(  # nosec B603 B607 - icacls is a fixed Windows system command
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


def _write_credentials_toml(path: Path, tokens: dict[str, dict[str, str]]) -> None:
    """credentials.toml を新形式で書き出す。"""
    lines: list[str] = []
    for host, accounts in tokens.items():
        lines.append(f'[tokens."{host}"]')
        for key, value in accounts.items():
            lines.append(f'"{key}" = "{_escape_toml_value(value)}"')
        lines.append("")
    content = "\n".join(lines) + "\n"
    try:
        fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp", prefix=".credentials_")
        try:
            os.write(fd, content.encode("utf-8"))
            os.close(fd)
            fd = -1
            os.replace(tmp_path, path)
        except BaseException:
            if fd != -1:
                os.close(fd)
            with suppress(OSError):
                os.unlink(tmp_path)
            raise
    except OSError as e:
        raise ConfigError(f"Failed to write credentials file {path}: {e}") from e


def _resolve_account_name(host: str, host_accounts: dict[str, str]) -> str:
    """アカウント名を解決する。

    優先順位:
    1. cli_account ContextVar (--account 経由)
    2. git config gfo.account
    3. config.toml の hosts.{host}.account
    4. tokens.{host}._default
    5. フォールバック: "default"
    """
    # 1. ContextVar
    cv = cli_account.get()
    if cv is not None:
        return cv

    # 2. git config
    try:
        import gfo.git_util

        git_account = gfo.git_util.git_config_get("gfo.account")
        if git_account:
            return git_account
    except (GitCommandError, OSError):
        pass

    # 3. config.toml
    try:
        import gfo.config

        host_cfg = gfo.config.get_host_config(host)
        if host_cfg and "account" in host_cfg:
            return str(host_cfg["account"])
    except (ConfigError, OSError):
        pass

    # 4. _default
    default = host_accounts.get("_default")
    if default:
        return default

    # 5. フォールバック
    return "default"
