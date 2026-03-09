"""auth.py のテスト。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from gfo.auth import (
    _SERVICE_ENV_MAP,
    _write_credentials_toml,
    get_auth_status,
    load_tokens,
    resolve_token,
    save_token,
)
from gfo.exceptions import AuthError, ConfigError


# ── resolve_token ──


def test_resolve_token_from_credentials(tmp_path, monkeypatch):
    """credentials.toml からトークンを取得できる。"""
    creds = tmp_path / "credentials.toml"
    creds.write_text('[tokens]\n"github.com" = "ghp_abc123"\n', encoding="utf-8")
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)

    assert resolve_token("github.com", "github") == "ghp_abc123"


def test_resolve_token_env_fallback(tmp_path, monkeypatch):
    """credentials.toml なし → サービス別環境変数フォールバック。"""
    creds = tmp_path / "credentials.toml"  # 存在しない
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_from_env")

    assert resolve_token("github.com", "github") == "ghp_from_env"


def test_resolve_token_gfo_token_fallback(tmp_path, monkeypatch):
    """サービス別環境変数なし → GFO_TOKEN フォールバック。"""
    creds = tmp_path / "credentials.toml"
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("GFO_TOKEN", "gfo_universal")

    assert resolve_token("github.com", "github") == "gfo_universal"


def test_resolve_token_auth_error(tmp_path, monkeypatch):
    """全未設定 → AuthError。"""
    creds = tmp_path / "credentials.toml"
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GFO_TOKEN", raising=False)

    with pytest.raises(AuthError):
        resolve_token("github.com", "github")


def test_resolve_token_credentials_takes_priority(tmp_path, monkeypatch):
    """credentials.toml は環境変数より優先される。"""
    creds = tmp_path / "credentials.toml"
    creds.write_text('[tokens]\n"github.com" = "from_file"\n', encoding="utf-8")
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)
    monkeypatch.setenv("GITHUB_TOKEN", "from_env")

    assert resolve_token("github.com", "github") == "from_file"


# ── save_token ──


def test_save_token_empty_raises_auth_error(tmp_path, monkeypatch):
    """空のトークンを渡すと AuthError を送出する。"""
    config_dir = tmp_path / "config"
    monkeypatch.setattr("gfo.auth.get_config_dir", lambda: config_dir)
    monkeypatch.setattr(
        "gfo.auth.get_credentials_path", lambda: config_dir / "credentials.toml"
    )
    with pytest.raises(AuthError, match="Token must not be empty"):
        save_token("github.com", "")

    with pytest.raises(AuthError, match="Token must not be empty"):
        save_token("github.com", "   ")


def test_save_token_new_file(tmp_path, monkeypatch):
    """新規ファイル作成。"""
    config_dir = tmp_path / "config"
    monkeypatch.setattr("gfo.auth.get_config_dir", lambda: config_dir)
    monkeypatch.setattr(
        "gfo.auth.get_credentials_path", lambda: config_dir / "credentials.toml"
    )

    save_token("github.com", "ghp_new")

    assert (config_dir / "credentials.toml").exists()
    tokens = _load_raw_tokens(config_dir / "credentials.toml")
    assert tokens["github.com"] == "ghp_new"


def test_save_token_append_existing(tmp_path, monkeypatch):
    """既存ファイルに追加（既存トークン保持）。"""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    creds = config_dir / "credentials.toml"
    creds.write_text('[tokens]\n"github.com" = "ghp_old"\n', encoding="utf-8")
    monkeypatch.setattr("gfo.auth.get_config_dir", lambda: config_dir)
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)

    save_token("gitlab.com", "glpat_new")

    tokens = _load_raw_tokens(creds)
    assert tokens["github.com"] == "ghp_old"
    assert tokens["gitlab.com"] == "glpat_new"


def test_save_token_creates_directory(tmp_path, monkeypatch):
    """ディレクトリ自動作成。"""
    config_dir = tmp_path / "deep" / "nested" / "config"
    monkeypatch.setattr("gfo.auth.get_config_dir", lambda: config_dir)
    monkeypatch.setattr(
        "gfo.auth.get_credentials_path", lambda: config_dir / "credentials.toml"
    )

    save_token("github.com", "ghp_test")

    assert config_dir.exists()
    assert (config_dir / "credentials.toml").exists()


def test_save_token_posix_permission(tmp_path, monkeypatch):
    """POSIX パーミッション設定 (os.chmod が 0o600 で呼ばれる)。"""
    config_dir = tmp_path / "config"
    monkeypatch.setattr("gfo.auth.get_config_dir", lambda: config_dir)
    monkeypatch.setattr(
        "gfo.auth.get_credentials_path", lambda: config_dir / "credentials.toml"
    )
    monkeypatch.setattr("gfo.auth.sys.platform", "linux")

    chmod_calls = []
    original_chmod = os.chmod

    def mock_chmod(path, mode):
        chmod_calls.append((path, mode))
        original_chmod(path, mode)

    monkeypatch.setattr("gfo.auth.os.chmod", mock_chmod)

    save_token("github.com", "ghp_test")

    assert len(chmod_calls) == 1
    assert chmod_calls[0][1] == 0o600


def test_save_token_windows_icacls(tmp_path, monkeypatch):
    """Windows では icacls をベストエフォートで呼ぶ。"""
    config_dir = tmp_path / "config"
    monkeypatch.setattr("gfo.auth.get_config_dir", lambda: config_dir)
    monkeypatch.setattr(
        "gfo.auth.get_credentials_path", lambda: config_dir / "credentials.toml"
    )
    monkeypatch.setattr("gfo.auth.sys.platform", "win32")

    calls = []

    def mock_run(cmd, **kwargs):
        calls.append(cmd)
        result = type("CP", (), {"returncode": 0})()
        return result

    monkeypatch.setattr("gfo.auth.subprocess.run", mock_run)
    monkeypatch.setattr("gfo.auth.getpass.getuser", lambda: "testuser")

    save_token("github.com", "ghp_test")

    assert len(calls) == 1
    assert calls[0][0] == "icacls"
    assert "testuser:F" in calls[0]


def test_save_token_windows_icacls_oserror_ignored(tmp_path, monkeypatch):
    """Windows icacls が OSError を投げても伝播しない。"""
    config_dir = tmp_path / "config"
    monkeypatch.setattr("gfo.auth.get_config_dir", lambda: config_dir)
    monkeypatch.setattr(
        "gfo.auth.get_credentials_path", lambda: config_dir / "credentials.toml"
    )
    monkeypatch.setattr("gfo.auth.sys.platform", "win32")

    def mock_run_raises(cmd, **kwargs):
        raise OSError("icacls not found")

    monkeypatch.setattr("gfo.auth.subprocess.run", mock_run_raises)
    monkeypatch.setattr("gfo.auth.getpass.getuser", lambda: "testuser")

    # OSError が伝播せず、トークンは保存される
    save_token("github.com", "ghp_test")

    assert (config_dir / "credentials.toml").exists()
    tokens = _load_raw_tokens(config_dir / "credentials.toml")
    assert tokens["github.com"] == "ghp_test"


# ── load_tokens ──


def test_load_tokens_no_file(tmp_path, monkeypatch):
    """ファイルなし → 空dict。"""
    creds = tmp_path / "credentials.toml"
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)

    assert load_tokens() == {}


def test_load_tokens_permission_error(tmp_path, monkeypatch):
    """PermissionError → ConfigError（R35-01）。"""
    creds = tmp_path / "credentials.toml"
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)

    def _raise(*args, **kwargs):
        raise PermissionError("Permission denied")

    monkeypatch.setattr("builtins.open", _raise)
    with pytest.raises(ConfigError, match="Failed to read credentials file"):
        load_tokens()


def test_load_tokens_success(tmp_path, monkeypatch):
    """正常読み込み。"""
    creds = tmp_path / "credentials.toml"
    creds.write_text(
        '[tokens]\n"github.com" = "ghp_abc"\n"gitlab.com" = "glpat_xyz"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)

    tokens = load_tokens()
    assert tokens == {"github.com": "ghp_abc", "gitlab.com": "glpat_xyz"}


# ── get_auth_status ──


def _clear_service_env_vars(monkeypatch, keep: str | None = None) -> None:
    """全サービス env var をクリアする（keep で指定した env var は残す）。"""
    for env_var in _SERVICE_ENV_MAP.values():
        if keep is None or env_var != keep:
            monkeypatch.delenv(env_var, raising=False)


def test_get_auth_status_credentials_and_env(tmp_path, monkeypatch):
    """credentials.toml + 環境変数の両方を列挙。"""
    creds = tmp_path / "credentials.toml"
    creds.write_text('[tokens]\n"github.com" = "ghp_abc"\n', encoding="utf-8")
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)
    monkeypatch.setenv("GITLAB_TOKEN", "glpat_env")
    _clear_service_env_vars(monkeypatch, keep="GITLAB_TOKEN")

    status = get_auth_status()

    hosts = [s["host"] for s in status]
    assert "github.com" in hosts
    # GitLab はクラウドサービスなので実ホスト名 "gitlab.com" を使用
    assert "gitlab.com" in hosts

    cred_entry = next(s for s in status if s["host"] == "github.com")
    assert cred_entry["source"] == "credentials.toml"
    assert cred_entry["status"] == "configured"

    env_entry = next(s for s in status if s["host"] == "gitlab.com")
    assert env_entry["source"] == "env:GITLAB_TOKEN"


def test_get_auth_status_no_duplicate_when_env_and_file_overlap(tmp_path, monkeypatch):
    """credentials.toml と env var に同一ホストがある場合、重複エントリが発生しない（R44-01）。"""
    creds = tmp_path / "credentials.toml"
    creds.write_text('[tokens]\n"github.com" = "ghp_from_file"\n', encoding="utf-8")
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_from_env")
    _clear_service_env_vars(monkeypatch, keep="GITHUB_TOKEN")

    status = get_auth_status()

    github_entries = [s for s in status if s["host"] == "github.com"]
    assert len(github_entries) == 1
    assert github_entries[0]["source"] == "credentials.toml"


def test_get_auth_status_no_token_values(tmp_path, monkeypatch):
    """トークン値が含まれないことを確認。"""
    creds = tmp_path / "credentials.toml"
    creds.write_text('[tokens]\n"github.com" = "ghp_secret"\n', encoding="utf-8")
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)
    _clear_service_env_vars(monkeypatch)

    status = get_auth_status()

    for entry in status:
        assert "ghp_secret" not in str(entry.values())
        assert "token" not in entry  # トークン値のキーがない


# ── _write_credentials_toml ──


def test_write_credentials_toml_escape(tmp_path):
    """エスケープ処理の検証。"""
    path = tmp_path / "credentials.toml"
    tokens = {"example.com": 'val"with\\special\nchars\there'}
    _write_credentials_toml(path, tokens)

    content = path.read_text(encoding="utf-8")
    assert '"example.com"' in content
    assert '\\"' in content
    assert "\\\\" in content
    assert "\\n" in content
    assert "\\t" in content

    # tomllib でパースして元の値に戻ることを確認
    import tomllib

    with open(path, "rb") as f:
        data = tomllib.load(f)
    assert data["tokens"]["example.com"] == 'val"with\\special\nchars\there'


def test_write_credentials_toml_multiple_keys(tmp_path):
    """複数キーの書き出し。"""
    path = tmp_path / "credentials.toml"
    tokens = {"github.com": "ghp_abc", "gitlab.com": "glpat_xyz"}
    _write_credentials_toml(path, tokens)

    import tomllib

    with open(path, "rb") as f:
        data = tomllib.load(f)
    assert data["tokens"] == tokens


# ── ヘルパー ──


def _load_raw_tokens(path: Path) -> dict[str, str]:
    """テスト用: credentials.toml を直接読む。"""
    import tomllib

    with open(path, "rb") as f:
        data = tomllib.load(f)
    return data.get("tokens", {})
