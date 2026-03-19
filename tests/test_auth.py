"""auth.py のテスト。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from gfo.auth import (
    _SERVICE_ENV_MAP,
    _escape_toml_value,
    _write_credentials_toml,
    get_auth_status,
    list_accounts,
    load_tokens,
    remove_token,
    resolve_token,
    save_token,
    switch_account,
)
from gfo.exceptions import AuthError, ConfigError


def _new_format_toml(host: str, token: str, account: str = "default") -> str:
    """新形式の credentials.toml 文字列を生成するヘルパー。"""
    return f'[tokens."{host}"]\n_default = "{account}"\n{account} = "{token}"\n'


def _multi_host_toml(*entries: tuple[str, str, str]) -> str:
    """複数ホストの新形式 credentials.toml を生成するヘルパー。"""
    parts = []
    for host, token, account in entries:
        parts.append(f'[tokens."{host}"]\n_default = "{account}"\n{account} = "{token}"\n')
    return "\n".join(parts)


# ── resolve_token ──


def test_resolve_token_from_credentials(tmp_path, monkeypatch):
    """credentials.toml からトークンを取得できる。"""
    creds = tmp_path / "credentials.toml"
    creds.write_text(_new_format_toml("github.com", "ghp_abc123"), encoding="utf-8")
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
    creds.write_text(_new_format_toml("github.com", "from_file"), encoding="utf-8")
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)
    monkeypatch.setenv("GITHUB_TOKEN", "from_env")

    assert resolve_token("github.com", "github") == "from_file"


def test_resolve_token_uppercase_host_normalized(tmp_path, monkeypatch):
    """ホスト名が大文字で渡されても小文字に正規化して検索する。"""
    creds = tmp_path / "credentials.toml"
    creds.write_text(_new_format_toml("github.com", "my-token"), encoding="utf-8")
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)

    # 大文字ホストで検索しても見つかる
    assert resolve_token("GitHub.COM", "github") == "my-token"


def test_save_token_uppercase_host_normalized(tmp_path, monkeypatch):
    """save_token はホスト名を小文字に正規化して保存する。"""
    config_dir = tmp_path / "config"
    monkeypatch.setattr("gfo.auth.get_config_dir", lambda: config_dir)
    creds = config_dir / "credentials.toml"
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)

    save_token("GitHub.COM", "my-token")

    tokens = load_tokens()
    assert "github.com" in tokens
    assert "GitHub.COM" not in tokens


# ── resolve_token アカウント解決 ──


def test_resolve_token_contextvar_account(tmp_path, monkeypatch):
    """ContextVar (--account) でアカウントを指定して解決する。"""
    from gfo._context import cli_account

    creds = tmp_path / "credentials.toml"
    creds.write_text(
        '[tokens."github.com"]\n_default = "default"\ndefault = "tok-default"\nwork = "tok-work"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)

    token = cli_account.set("work")
    try:
        assert resolve_token("github.com", "github") == "tok-work"
    finally:
        cli_account.reset(token)


def test_resolve_token_git_config_account(tmp_path, monkeypatch):
    """git config gfo.account でアカウントを解決する。"""
    creds = tmp_path / "credentials.toml"
    creds.write_text(
        '[tokens."github.com"]\n_default = "default"\ndefault = "tok-default"\nci = "tok-ci"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)
    monkeypatch.setattr(
        "gfo.git_util.git_config_get", lambda key, cwd=None: "ci" if key == "gfo.account" else None
    )

    assert resolve_token("github.com", "github") == "tok-ci"


def test_resolve_token_config_toml_account(tmp_path, monkeypatch):
    """config.toml の hosts.{host}.account でアカウントを解決する。"""
    creds = tmp_path / "credentials.toml"
    creds.write_text(
        '[tokens."github.com"]\n_default = "default"\ndefault = "tok-default"\nbot = "tok-bot"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)
    monkeypatch.setattr("gfo.git_util.git_config_get", lambda key, cwd=None: None)
    monkeypatch.setattr("gfo.config.get_host_config", lambda host: {"account": "bot"})

    assert resolve_token("github.com", "github") == "tok-bot"


def test_resolve_token_default_key_account(tmp_path, monkeypatch):
    """_default キーでアカウントを解決する。"""
    creds = tmp_path / "credentials.toml"
    creds.write_text(
        '[tokens."github.com"]\n_default = "personal"\npersonal = "tok-personal"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)
    monkeypatch.setattr("gfo.git_util.git_config_get", lambda key, cwd=None: None)
    monkeypatch.setattr("gfo.config.get_host_config", lambda host: None)

    assert resolve_token("github.com", "github") == "tok-personal"


def test_resolve_token_priority_contextvar_over_git_config(tmp_path, monkeypatch):
    """ContextVar > git config > config.toml > _default の優先度テスト。"""
    from gfo._context import cli_account

    creds = tmp_path / "credentials.toml"
    creds.write_text(
        '[tokens."github.com"]\n_default = "default"\ndefault = "tok-default"\ncv = "tok-cv"\ngit = "tok-git"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)
    monkeypatch.setattr(
        "gfo.git_util.git_config_get", lambda key, cwd=None: "git" if key == "gfo.account" else None
    )

    # ContextVar が最優先
    token = cli_account.set("cv")
    try:
        assert resolve_token("github.com", "github") == "tok-cv"
    finally:
        cli_account.reset(token)


# ── save_token ──


def test_save_token_empty_raises_auth_error(tmp_path, monkeypatch):
    """空のトークンを渡すと AuthError を送出する。"""
    config_dir = tmp_path / "config"
    monkeypatch.setattr("gfo.auth.get_config_dir", lambda: config_dir)
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: config_dir / "credentials.toml")
    with pytest.raises(AuthError, match="Token must not be empty"):
        save_token("github.com", "")

    with pytest.raises(AuthError, match="Token must not be empty"):
        save_token("github.com", "   ")


def test_save_token_new_file(tmp_path, monkeypatch):
    """新規ファイル作成。"""
    config_dir = tmp_path / "config"
    monkeypatch.setattr("gfo.auth.get_config_dir", lambda: config_dir)
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: config_dir / "credentials.toml")

    save_token("github.com", "ghp_new")

    assert (config_dir / "credentials.toml").exists()
    tokens = _load_raw_tokens(config_dir / "credentials.toml")
    assert tokens["github.com"]["default"] == "ghp_new"
    assert tokens["github.com"]["_default"] == "default"


def test_save_token_append_existing(tmp_path, monkeypatch):
    """既存ファイルに追加（既存トークン保持）。"""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    creds = config_dir / "credentials.toml"
    creds.write_text(_new_format_toml("github.com", "ghp_old"), encoding="utf-8")
    monkeypatch.setattr("gfo.auth.get_config_dir", lambda: config_dir)
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)

    save_token("gitlab.com", "glpat_new")

    tokens = _load_raw_tokens(creds)
    assert tokens["github.com"]["default"] == "ghp_old"
    assert tokens["gitlab.com"]["default"] == "glpat_new"


def test_save_token_with_account(tmp_path, monkeypatch):
    """account パラメータ指定でトークンを保存する。"""
    config_dir = tmp_path / "config"
    monkeypatch.setattr("gfo.auth.get_config_dir", lambda: config_dir)
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: config_dir / "credentials.toml")

    save_token("github.com", "tok-work", account="work")

    tokens = _load_raw_tokens(config_dir / "credentials.toml")
    assert tokens["github.com"]["work"] == "tok-work"
    assert tokens["github.com"]["_default"] == "work"


def test_save_token_second_account_keeps_default(tmp_path, monkeypatch):
    """2 つ目のアカウント追加時に _default は変更されない。"""
    config_dir = tmp_path / "config"
    monkeypatch.setattr("gfo.auth.get_config_dir", lambda: config_dir)
    creds = config_dir / "credentials.toml"
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)

    save_token("github.com", "tok-first", account="first")
    save_token("github.com", "tok-second", account="second")

    tokens = _load_raw_tokens(creds)
    assert tokens["github.com"]["_default"] == "first"
    assert tokens["github.com"]["second"] == "tok-second"


def test_save_token_creates_directory(tmp_path, monkeypatch):
    """ディレクトリ自動作成。"""
    config_dir = tmp_path / "deep" / "nested" / "config"
    monkeypatch.setattr("gfo.auth.get_config_dir", lambda: config_dir)
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: config_dir / "credentials.toml")

    save_token("github.com", "ghp_test")

    assert config_dir.exists()
    assert (config_dir / "credentials.toml").exists()


def test_save_token_posix_permission(tmp_path, monkeypatch):
    """POSIX パーミッション設定 (os.chmod が 0o600 で呼ばれる)。"""
    config_dir = tmp_path / "config"
    monkeypatch.setattr("gfo.auth.get_config_dir", lambda: config_dir)
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: config_dir / "credentials.toml")
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
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: config_dir / "credentials.toml")
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


def test_save_token_windows_icacls_nonzero_warns(tmp_path, monkeypatch):
    """Windows icacls が非ゼロ終了コードを返しても警告のみで伝播しない。"""
    import warnings

    config_dir = tmp_path / "config"
    monkeypatch.setattr("gfo.auth.get_config_dir", lambda: config_dir)
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: config_dir / "credentials.toml")
    monkeypatch.setattr("gfo.auth.sys.platform", "win32")

    def mock_run(cmd, **kwargs):
        return type("CP", (), {"returncode": 5})()

    monkeypatch.setattr("gfo.auth.subprocess.run", mock_run)
    monkeypatch.setattr("gfo.auth.getpass.getuser", lambda: "testuser")

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        save_token("github.com", "ghp_test")

    assert any("icacls exited with code" in str(warning.message) for warning in w)
    assert (config_dir / "credentials.toml").exists()


def test_save_token_windows_icacls_oserror_ignored(tmp_path, monkeypatch):
    """Windows icacls が OSError を投げても伝播しない。"""
    config_dir = tmp_path / "config"
    monkeypatch.setattr("gfo.auth.get_config_dir", lambda: config_dir)
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: config_dir / "credentials.toml")
    monkeypatch.setattr("gfo.auth.sys.platform", "win32")

    def mock_run_raises(cmd, **kwargs):
        raise OSError("icacls not found")

    monkeypatch.setattr("gfo.auth.subprocess.run", mock_run_raises)
    monkeypatch.setattr("gfo.auth.getpass.getuser", lambda: "testuser")

    # OSError が伝播せず、トークンは保存される
    save_token("github.com", "ghp_test")

    assert (config_dir / "credentials.toml").exists()
    tokens = _load_raw_tokens(config_dir / "credentials.toml")
    assert tokens["github.com"]["default"] == "ghp_test"


# ── load_tokens ──


def test_load_tokens_toml_decode_error(tmp_path, monkeypatch):
    """不正な TOML → ConfigError。"""
    creds = tmp_path / "credentials.toml"
    creds.write_text("invalid toml content [[[\n", encoding="utf-8")
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)

    with pytest.raises(ConfigError, match="Failed to parse credentials file"):
        load_tokens()


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
    """正常読み込み（新形式）。"""
    creds = tmp_path / "credentials.toml"
    creds.write_text(
        _multi_host_toml(
            ("github.com", "ghp_abc", "default"),
            ("gitlab.com", "glpat_xyz", "default"),
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)

    tokens = load_tokens()
    assert tokens["github.com"]["default"] == "ghp_abc"
    assert tokens["gitlab.com"]["default"] == "glpat_xyz"


def test_load_tokens_ignores_flat_values(tmp_path, monkeypatch):
    """旧形式のフラット値（文字列）は無視される。"""
    creds = tmp_path / "credentials.toml"
    creds.write_text('[tokens]\n"github.com" = "ghp_old_format"\n', encoding="utf-8")
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)

    tokens = load_tokens()
    assert tokens == {}


# ── switch_account ──


def test_switch_account_success(tmp_path, monkeypatch):
    """switch_account で _default が切り替わる。"""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    creds = config_dir / "credentials.toml"
    creds.write_text(
        '[tokens."github.com"]\n_default = "default"\ndefault = "tok-default"\nwork = "tok-work"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("gfo.auth.get_config_dir", lambda: config_dir)
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)

    switch_account("github.com", "work")

    tokens = _load_raw_tokens(creds)
    assert tokens["github.com"]["_default"] == "work"


def test_switch_account_unknown_host(tmp_path, monkeypatch):
    """存在しないホスト → ConfigError。"""
    creds = tmp_path / "credentials.toml"
    creds.write_text("", encoding="utf-8")
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)
    monkeypatch.setattr("gfo.auth.get_config_dir", lambda: tmp_path)

    with pytest.raises(ConfigError, match="No tokens configured"):
        switch_account("unknown.com", "default")


def test_switch_account_unknown_account(tmp_path, monkeypatch):
    """存在しないアカウント → ConfigError。"""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    creds = config_dir / "credentials.toml"
    creds.write_text(_new_format_toml("github.com", "tok"), encoding="utf-8")
    monkeypatch.setattr("gfo.auth.get_config_dir", lambda: config_dir)
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)

    with pytest.raises(ConfigError, match="Account 'nonexistent' not found"):
        switch_account("github.com", "nonexistent")


# ── list_accounts ──


def test_list_accounts(tmp_path, monkeypatch):
    """list_accounts は _default を除いたアカウント一覧を返す。"""
    creds = tmp_path / "credentials.toml"
    creds.write_text(
        '[tokens."github.com"]\n_default = "default"\ndefault = "tok1"\nwork = "tok2"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)

    accounts = list_accounts("github.com")
    assert sorted(accounts) == ["default", "work"]


def test_list_accounts_no_host(tmp_path, monkeypatch):
    """存在しないホスト → 空リスト。"""
    creds = tmp_path / "credentials.toml"
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)

    assert list_accounts("nonexistent.com") == []


# ── remove_token ──


def test_remove_token_specific_account(tmp_path, monkeypatch):
    """特定アカウントのみ削除する。"""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    creds = config_dir / "credentials.toml"
    creds.write_text(
        '[tokens."github.com"]\n_default = "default"\ndefault = "tok1"\nwork = "tok2"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("gfo.auth.get_config_dir", lambda: config_dir)
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)

    remove_token("github.com", "work")

    tokens = _load_raw_tokens(creds)
    assert "work" not in tokens["github.com"]
    assert tokens["github.com"]["default"] == "tok1"


def test_remove_token_host_all(tmp_path, monkeypatch):
    """ホスト全体を削除する。"""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    creds = config_dir / "credentials.toml"
    creds.write_text(_new_format_toml("github.com", "tok"), encoding="utf-8")
    monkeypatch.setattr("gfo.auth.get_config_dir", lambda: config_dir)
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)

    remove_token("github.com")

    tokens = _load_raw_tokens(creds)
    assert "github.com" not in tokens


def test_remove_token_default_shifts(tmp_path, monkeypatch):
    """_default が削除されたアカウントを指していた場合、残りの最初のアカウントに切り替わる。"""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    creds = config_dir / "credentials.toml"
    creds.write_text(
        '[tokens."github.com"]\n_default = "a"\na = "tok-a"\nb = "tok-b"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("gfo.auth.get_config_dir", lambda: config_dir)
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)

    remove_token("github.com", "a")

    tokens = _load_raw_tokens(creds)
    assert tokens["github.com"]["_default"] == "b"
    assert "a" not in tokens["github.com"]


def test_remove_token_last_account_removes_host(tmp_path, monkeypatch):
    """最後のアカウントを削除するとホスト全体が削除される。"""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    creds = config_dir / "credentials.toml"
    creds.write_text(_new_format_toml("github.com", "tok"), encoding="utf-8")
    monkeypatch.setattr("gfo.auth.get_config_dir", lambda: config_dir)
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)

    remove_token("github.com", "default")

    tokens = _load_raw_tokens(creds)
    assert "github.com" not in tokens


def test_remove_token_unknown_host(tmp_path, monkeypatch):
    """存在しないホスト → ConfigError。"""
    creds = tmp_path / "credentials.toml"
    creds.write_text("", encoding="utf-8")
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)
    monkeypatch.setattr("gfo.auth.get_config_dir", lambda: tmp_path)

    with pytest.raises(ConfigError, match="No tokens configured"):
        remove_token("unknown.com")


def test_remove_token_unknown_account(tmp_path, monkeypatch):
    """存在しないアカウント → ConfigError。"""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    creds = config_dir / "credentials.toml"
    creds.write_text(_new_format_toml("github.com", "tok"), encoding="utf-8")
    monkeypatch.setattr("gfo.auth.get_config_dir", lambda: config_dir)
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)

    with pytest.raises(ConfigError, match="Account 'nonexistent' not found"):
        remove_token("github.com", "nonexistent")


# ── get_auth_status ──


def _clear_service_env_vars(monkeypatch, keep: str | None = None) -> None:
    """全サービス env var をクリアする（keep で指定した env var は残す）。"""
    for env_var in _SERVICE_ENV_MAP.values():
        if keep is None or env_var != keep:
            monkeypatch.delenv(env_var, raising=False)
    monkeypatch.delenv("GFO_TOKEN", raising=False)


def test_get_auth_status_credentials_and_env(tmp_path, monkeypatch):
    """credentials.toml + 環境変数の両方を列挙。"""
    creds = tmp_path / "credentials.toml"
    creds.write_text(_new_format_toml("github.com", "ghp_abc"), encoding="utf-8")
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
    assert cred_entry["account"] == "default"
    assert cred_entry["active"] == "*"

    env_entry = next(s for s in status if s["host"] == "gitlab.com")
    assert env_entry["source"] == "env:GITLAB_TOKEN"
    assert env_entry["account"] == ""


def test_get_auth_status_no_duplicate_when_env_and_file_overlap(tmp_path, monkeypatch):
    """credentials.toml と env var に同一ホストがある場合、重複エントリが発生しない（R44-01）。"""
    creds = tmp_path / "credentials.toml"
    creds.write_text(_new_format_toml("github.com", "ghp_from_file"), encoding="utf-8")
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_from_env")
    _clear_service_env_vars(monkeypatch, keep="GITHUB_TOKEN")

    status = get_auth_status()

    github_entries = [s for s in status if s["host"] == "github.com"]
    assert len(github_entries) == 1
    assert github_entries[0]["source"] == "credentials.toml"


def test_get_auth_status_shared_env_var_no_duplicate(tmp_path, monkeypatch):
    """GITEA_TOKEN など複数サービスが共有する env_var はエントリが重複しない（R44-01 seen_env_vars）。"""
    creds = tmp_path / "credentials.toml"
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)
    _clear_service_env_vars(monkeypatch, keep="GITEA_TOKEN")
    monkeypatch.setenv("GITEA_TOKEN", "token_gitea")

    status = get_auth_status()

    # gitea/forgejo/gogs は同じ GITEA_TOKEN を使うが、エントリは1件のみ
    gitea_entries = [s for s in status if s["source"] == "env:GITEA_TOKEN"]
    assert len(gitea_entries) == 1


def test_get_auth_status_no_token_values(tmp_path, monkeypatch):
    """トークン値が含まれないことを確認。"""
    creds = tmp_path / "credentials.toml"
    creds.write_text(_new_format_toml("github.com", "ghp_secret"), encoding="utf-8")
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)
    _clear_service_env_vars(monkeypatch)

    status = get_auth_status()

    for entry in status:
        assert "ghp_secret" not in str(entry.values())
        assert "token" not in entry  # トークン値のキーがない


def test_get_auth_status_gfo_token_shown(tmp_path, monkeypatch):
    """GFO_TOKEN が設定されている場合、auth status に表示される（resolve_token との整合）。"""
    creds = tmp_path / "credentials.toml"
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)
    _clear_service_env_vars(monkeypatch)
    monkeypatch.setenv("GFO_TOKEN", "universal-token")

    status = get_auth_status()

    assert any(s["source"] == "env:GFO_TOKEN" for s in status)
    entry = next(s for s in status if s["source"] == "env:GFO_TOKEN")
    assert entry["status"] == "configured"
    assert entry["host"] == "(all services)"
    assert entry["account"] == ""


def test_get_auth_status_gfo_token_not_shown_when_unset(tmp_path, monkeypatch):
    """GFO_TOKEN が未設定の場合、auth status に表示されない。"""
    creds = tmp_path / "credentials.toml"
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)
    _clear_service_env_vars(monkeypatch)

    status = get_auth_status()

    assert not any(s["source"] == "env:GFO_TOKEN" for s in status)


def test_get_auth_status_multiple_accounts(tmp_path, monkeypatch):
    """複数アカウントの場合、各アカウントが個別エントリとして表示される。"""
    creds = tmp_path / "credentials.toml"
    creds.write_text(
        '[tokens."github.com"]\n_default = "default"\ndefault = "tok1"\nwork = "tok2"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("gfo.auth.get_credentials_path", lambda: creds)
    _clear_service_env_vars(monkeypatch)

    status = get_auth_status()

    github_entries = [s for s in status if s["host"] == "github.com"]
    assert len(github_entries) == 2
    accounts = {e["account"] for e in github_entries}
    assert accounts == {"default", "work"}
    active_entry = next(e for e in github_entries if e["active"] == "*")
    assert active_entry["account"] == "default"


# ── _write_credentials_toml ──


def test_write_credentials_toml_escape(tmp_path):
    """エスケープ処理の検証。"""
    path = tmp_path / "credentials.toml"
    tokens = {"example.com": {"default": 'val"with\\special\nchars\there'}}
    _write_credentials_toml(path, tokens)

    content = path.read_text(encoding="utf-8")
    assert '[tokens."example.com"]' in content
    assert '\\"' in content
    assert "\\\\" in content
    assert "\\n" in content
    assert "\\t" in content

    # tomllib でパースして元の値に戻ることを確認
    import tomllib

    with open(path, "rb") as f:
        data = tomllib.load(f)
    assert data["tokens"]["example.com"]["default"] == 'val"with\\special\nchars\there'


def test_write_credentials_toml_multiple_keys(tmp_path):
    """複数キーの書き出し。"""
    path = tmp_path / "credentials.toml"
    tokens = {
        "github.com": {"default": "ghp_abc"},
        "gitlab.com": {"default": "glpat_xyz"},
    }
    _write_credentials_toml(path, tokens)

    import tomllib

    with open(path, "rb") as f:
        data = tomllib.load(f)
    assert data["tokens"]["github.com"]["default"] == "ghp_abc"
    assert data["tokens"]["gitlab.com"]["default"] == "glpat_xyz"


# ── _escape_toml_value ──


def test_escape_toml_value():
    """_escape_toml_value のテスト。"""
    assert _escape_toml_value("simple") == "simple"
    assert _escape_toml_value('has"quote') == 'has\\"quote'
    assert _escape_toml_value("has\\backslash") == "has\\\\backslash"
    assert _escape_toml_value("has\nnewline") == "has\\nnewline"


# ── ヘルパー ──


def _load_raw_tokens(path: Path) -> dict[str, dict[str, str]]:
    """テスト用: credentials.toml を直接読む（新形式）。"""
    import tomllib

    with open(path, "rb") as f:
        data = tomllib.load(f)
    return data.get("tokens", {})
