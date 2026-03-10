# gfo – Git Forge Operator

複数の Git ホスティングサービスを **統一コマンド** で操作する CLI ツール。

## 対応サービス

| サービス | 識別子 | 認証環境変数 |
|---|---|---|
| GitHub | `github` | `GITHUB_TOKEN` |
| GitLab | `gitlab` | `GITLAB_TOKEN` |
| Bitbucket Cloud | `bitbucket` | `BITBUCKET_APP_PASSWORD` |
| Azure DevOps | `azure-devops` | `AZURE_DEVOPS_PAT` |
| Gitea | `gitea` | `GITEA_TOKEN` |
| Forgejo | `forgejo` | `GITEA_TOKEN` |
| Gogs | `gogs` | `GITEA_TOKEN` |
| GitBucket | `gitbucket` | `GITBUCKET_TOKEN` |
| Backlog | `backlog` | `BACKLOG_API_KEY` |

## インストール

```bash
pip install -e ".[dev]"
```

**動作要件**: Python 3.11 以上

## クイックスタート

```bash
# リポジトリ内で初期化（remote URL からサービスを自動検出）
gfo init

# 認証トークンを設定
gfo auth login --host github.com

# PR 一覧を表示
gfo pr list

# Issue を作成
gfo issue create --title "Bug report"
```

## コマンド一覧

| コマンド | サブコマンド | 説明 |
|---|---|---|
| `gfo init` | — | プロジェクト設定の初期化 |
| `gfo auth` | `login`, `status` | トークン保存・認証状態確認 |
| `gfo pr` | `list`, `create`, `view`, `merge`, `close`, `checkout` | プルリクエスト操作 |
| `gfo issue` | `list`, `create`, `view`, `close` | Issue 操作 |
| `gfo repo` | `list`, `create`, `clone`, `view` | リポジトリ操作 |
| `gfo release` | `list`, `create` | リリース操作 |
| `gfo label` | `list`, `create` | ラベル操作 |
| `gfo milestone` | `list`, `create` | マイルストーン操作 |

### グローバルオプション

- `--format {table,json,plain}` — 出力形式（デフォルト: `table`）
- `--version` — バージョン表示

## 設定

gfo は 3 層の設定解決を行います（優先度順）:

1. `git config --local`（リポジトリごと）
2. `~/.config/gfo/config.toml`（グローバル）
3. remote URL からの自動検出

認証トークンの解決順序:

1. `~/.config/gfo/credentials.toml`
2. サービス別環境変数（上記表を参照）
3. `GFO_TOKEN` 汎用環境変数

## 開発

```bash
# テスト実行（カバレッジ付き）
pytest

# 特定テストの実行
pytest tests/test_commands/test_pr.py
```

### 統合テスト

実サービスに対する統合テストも用意されている。

- **セルフホスト**（Gitea / Forgejo / Gogs / GitBucket）: Docker さえあれば自動実行可能
- **SaaS**（GitHub / GitLab / Bitbucket / Azure DevOps）: 各サービスのアカウントと API トークンが必要

詳細なセットアップ手順は [docs/integration-testing.md](docs/integration-testing.md) を参照。

```bash
# セルフホストテスト（Docker 自動起動・クリーンアップ込み）
bash tests/integration/run_selfhosted.sh

# SaaS テスト（.env にトークン設定後）
bash tests/integration/run_saas.sh
```

## ライセンス

MIT
