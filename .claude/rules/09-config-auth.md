---
paths:
  - "src/gfo/config.py"
  - "src/gfo/auth.py"
  - "src/gfo/detect.py"
  - "tests/test_config.py"
  - "tests/test_auth.py"
---

# 設定・認証ルール

## ホスト名の正規化（必須）

**すべてのホスト名は `lower()` で正規化すること。**
- `auth.py`: `resolve_token` / `save_token`
- `detect.py`: `get_known_service_type` / `_KNOWN_HOSTS`
- `config.py`: `get_host_config` / `get_hosts_config`

過去バグ: `GitHub.com` ≠ `github.com` でトークン解決に失敗

## 設定値の保存

- **空文字列でも `git_config_set` を実行すること**（`if value:` でスキップしない）
- 過去バグ: `save_project_config` で owner/repo が空文字列の場合にスキップされた

## 設定解決の優先度

1. `git config --local`（リポジトリ単位）
2. `~/.config/gfo/config.toml`（グローバル）
3. remote URL からの自動検出

## トークン解決の優先度

1. `~/.config/gfo/credentials.toml`
2. サービス別環境変数（例: `GITHUB_TOKEN`）
3. `GFO_TOKEN`（汎用フォールバック）

## `--jq` 空文字列チェック

- `if jq_expr:` ではなく `if jq_expr is not None:` でチェックすること
- 空文字列 `""` が渡された場合は早期エラーにすること
- 過去バグ: `if jq_expr:` だと空文字列が falsy で素通りした

## argparse `dest` 衝突回避

- Python 組み込み名（`all`, `type` 等）と衝突する場合は `dest="mark_all"` 等に変更すること
- 過去バグ: `--all` が `args.all` になり、組み込み `all()` と混同しやすかった

## 認証方式変更時の影響範囲

`auth.py`, `registry.py`, テストファイル, ドキュメントの4箇所に波及する。

## `--remote` グローバルオプション

- `cli.main()` で `contextvars.ContextVar`（`cli_remote`）に値を設定
- `detect_service()` / `resolve_project_config()` で ContextVar を参照
- 指定時 → git config ショートカット（`gfo.type`/`gfo.host`）をスキップ
- 指定リモートの URL で `get_remote_url(remote=...)` を呼ぶ
- `dest` は `global_remote`（`init --host` との衝突回避）

## `--repo` グローバルオプション

- `cli.main()` で `contextvars.ContextVar`（`cli_repo`）に値を設定
- `--remote` と排他（同時指定時は `ConfigError`）
- `detect_service()` 内の `_parse_repo_option()` で値をパース
- 受け付ける形式: HTTPS URL, SSH URL, SCP 形式, `HOST/OWNER/REPO`
- パース戦略: `detect_from_url(value)` → 失敗時 `detect_from_url(f"https://{value}")` → 両方失敗で `ConfigError`
- 指定時 → git config ショートカットをスキップし、URL からサービスを自動検出
- `dest` は `global_repo`

## リモート解決のフォールバック

- `get_remote_url()` / `get_default_branch()` のデフォルトリモート解決順: origin → 最初の非 origin リモート
- フォールバック時は `warnings.warn()` で通知（`get_remote_url` のみ）
- 明示的に `remote=` を渡した場合はフォールバックしない
