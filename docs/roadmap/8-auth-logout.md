# auth-logout

## 概要

`auth logout` サブコマンドを追加し、保存済みトークンを削除できるようにする。
gh / glab はいずれも `auth logout` を提供しており、gfo もこれに合わせる。

- **種別**: 機能追加
- **優先度**: Phase 2（独立して実施可能）

## 変更後

```
gfo auth logout               # git remote から自動検出したホストのトークンを削除
gfo auth logout --host github.com  # 指定ホストのトークンを削除
```

## 実装手順

### 1. 認証モジュール (`src/gfo/auth.py`)

`remove_token(host: str)` 関数を追加:

```python
def remove_token(host: str) -> bool:
    """credentials.toml から指定ホストのトークンエントリを削除する。

    Returns:
        True: 削除成功
        False: エントリが見つからなかった
    Raises:
        ConfigError: ファイル書き込みエラー
    """
    # credentials.toml のパスを取得
    # 指定ホストのセクションを削除
    # ファイルを書き戻す
```

- `credentials.toml` から指定ホストのトークンエントリを削除
- ファイルが存在しない場合やエントリがない場合はエラーメッセージ表示

### 2. CLI パーサー定義 (`src/gfo/cli.py`)

```python
auth_logout = auth_sub.add_parser("logout", help=_("Remove saved token"))
auth_logout.add_argument("--host", help=_("Host to logout from"))
```

### 3. コマンドハンドラー (`src/gfo/commands/auth_cmd.py`)

`handle_logout` 関数を追加:

```python
def handle_logout(args, *, fmt, jq=None):
    """gfo auth logout のハンドラ。"""
    host = getattr(args, "host", None)
    if not host:
        # git remote から自動検出（login と同じロジック）
        try:
            result = detect_service()
            host = result.host
        except (DetectionError, GitCommandError):
            raise ConfigError(_("Could not detect host. Use --host option."))

    from gfo.auth import remove_token
    if remove_token(host):
        print(_("Logged out from '{host}'.").format(host=host))
    else:
        print(_("No saved token for '{host}'.").format(host=host))
```

- `--host` 未指定時は git remote から自動検出（login と同じロジック）
- `gfo.auth.remove_token(host)` を呼び出し
- 成功メッセージ表示

### 4. ディスパッチマップ (`src/gfo/cli.py`)

```python
("auth", "logout"): gfo.commands.auth_cmd.handle_logout,
```

### 5. スキーマ定義 (`src/gfo/commands/schema.py`)

```python
("auth", "logout"): None,
```

### 6. テスト

- `tests/test_commands/test_auth.py` に logout テストを追加:
  - 正常系: credentials.toml にエントリがある場合の削除
  - 正常系: `--host` 指定あり/なし
  - 異常系: エントリが見つからない場合
  - 異常系: credentials.toml が存在しない場合

### 7. ドキュメント更新

- `docs/commands.md` / `.ja.md`: `auth` セクションに `logout` サブコマンドを追加
- `docs/cli-comparison.md`: 3.9 認証比較表で gfo 列に logout を追加
- `docs/cli-alignment.md`: 完了後にステータス更新
- `docs/authentication.md`: logout の使い方を追記
