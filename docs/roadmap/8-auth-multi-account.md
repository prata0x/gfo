# auth-multi-account

## 概要

同一ホストで複数アカウント（トークン）を使い分けられるようにする。
gh CLI の Named Accounts 方式を採用し、`credentials.toml` のフォーマットを破壊的に変更する。

- **種別**: 機能追加（破壊的変更）
- **優先度**: Phase 2（auth-logout より優先）

## 変更後

```
gfo auth login                             # "default" アカウントとして保存
gfo auth login --account work              # "work" アカウントとして保存
gfo auth switch work                       # _default を "work" に切り替え
gfo auth switch work --host github.com
gfo auth status                            # 全アカウント表示
gfo auth logout --account work             # 特定アカウント削除
gfo init --account work                    # .git/config に gfo.account = work
```

## credentials.toml フォーマット（破壊的変更）

旧フォーマットとの後方互換は持たせず、常にテーブル形式に統一する。

```toml
# 単一アカウント
[tokens."github.com"]
_default = "default"
default = "ghp_xxxx"

# 複数アカウント
[tokens."github.com"]
_default = "personal"
personal = "ghp_xxxx"
work = "ghp_yyyy"

[tokens."gitlab.example.com"]
_default = "default"
default = "glpat-xxxx"
```

- すべてのホストが `[tokens."{host}"]` テーブル
- アカウント名をキー、トークンを値
- `_default` でアクティブアカウントを指定
- `--account` 省略時は `"default"` をアカウント名として使用

## トークン解決順序

1. `.git/config` `gfo.account` → `tokens.{host}.{account}`
2. `config.toml` `hosts.{host}.account` → `tokens.{host}.{account}`
3. `tokens.{host}._default` → そのアカウント名のトークン
4. サービス別環境変数
5. `GFO_TOKEN`

## リポジトリ紐付け

```bash
gfo init --account work                    # .git/config に gfo.account = work
git config --local gfo.account work        # 手動でも可
```

## 実装手順

### 1. 認証モジュール (`src/gfo/auth.py`)

`credentials.toml` の読み書きを新フォーマットに対応:

- `save_token(host, token, account="default")`: アカウント名付きで保存
- `get_token(host, account=None)`: 解決順序に従いトークンを取得
- `switch_account(host, account)`: `_default` を切り替え
- `list_accounts(host)`: ホストの全アカウント一覧
- `remove_token(host, account=None)`: 特定アカウントのトークン削除

### 2. CLI パーサー定義 (`src/gfo/cli.py`)

```python
# auth login に --account 追加
auth_login.add_argument("--account", help=_("Account name"), default="default")

# auth switch サブコマンド追加
auth_switch = auth_sub.add_parser("switch", help=_("Switch active account"))
auth_switch.add_argument("account", help=_("Account name to switch to"))
auth_switch.add_argument("--host", help=_("Host"))

# auth logout に --account 追加
auth_logout.add_argument("--account", help=_("Account name to remove"))

# グローバルオプション
parser.add_argument("--account", help=_("Account name to use"))
```

### 3. コマンドハンドラー (`src/gfo/commands/auth_cmd.py`)

- `handle_login`: `--account` 対応
- `handle_switch`: 新規追加
- `handle_status`: 全アカウント表示対応
- `handle_logout`: `--account` 対応

### 4. 設定モジュール (`src/gfo/config.py`)

- `config.toml` の `hosts.{host}.account` 読み取り対応

### 5. スキーマ定義 (`src/gfo/commands/schema.py`)

```python
("auth", "switch"): None,
```

### 6. init コマンド (`src/gfo/commands/init.py`)

- `--account` オプション追加
- `.git/config` に `gfo.account` を設定

### 7. テスト

- `tests/test_commands/test_auth.py`:
  - login: `--account` 指定あり/なしでの保存
  - switch: `_default` 切り替え
  - status: 複数アカウント表示
  - logout: `--account` 指定での削除
- `tests/test_auth.py`:
  - 新フォーマットの読み書き
  - トークン解決順序の各パターン
  - `_default` 未設定時のフォールバック

### 8. ドキュメント更新

- `docs/commands.md` / `.ja.md`: `auth` セクションに `switch` サブコマンドと `--account` オプションを追加
- `docs/authentication.md`: マルチアカウントの使い方を追記
- `docs/cli-alignment.md`: 完了後にステータス更新
