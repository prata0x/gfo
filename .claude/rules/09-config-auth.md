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

## 認証方式変更時の影響範囲

`auth.py`, `registry.py`, テストファイル, ドキュメントの4箇所に波及する。
