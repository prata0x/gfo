[English](README.md)

# gfo – Git Forge Operator

複数の Git ホスティングサービスを **統一コマンド** で操作する CLI ツール。

- 9 サービスを同じコマンドで操作（GitHub, GitLab, Bitbucket, Azure DevOps, Backlog, Gitea, Forgejo, Gogs, GitBucket）
- remote URL からサービスを自動検出
- 依存は `requests` のみ、軽量
- `table` / `json` / `plain` の出力形式に対応

## 対応サービス

| サービス | 識別子 | 認証環境変数 |
|---|---|---|
| GitHub | `github` | `GITHUB_TOKEN` |
| GitLab | `gitlab` | `GITLAB_TOKEN` |
| Bitbucket Cloud | `bitbucket` | `BITBUCKET_TOKEN`（`email:api-token` 形式） |
| Azure DevOps | `azure-devops` | `AZURE_DEVOPS_PAT` |
| Gitea | `gitea` | `GITEA_TOKEN` |
| Forgejo | `forgejo` | `GITEA_TOKEN` |
| Gogs | `gogs` | `GITEA_TOKEN` |
| GitBucket | `gitbucket` | `GITBUCKET_TOKEN` |
| Backlog | `backlog` | `BACKLOG_API_KEY` |

## インストール

```bash
pip install gfo
```

**動作要件**: Python 3.11 以上

## クイックスタート

```bash
# 1. リポジトリ内で初期化（remote URL からサービスを自動検出）
gfo init

# 2. 認証トークンを設定
gfo auth login

# 3. PR 一覧を表示
gfo pr list

# 4. Issue を作成
gfo issue create --title "Bug report"

# 5. リポジトリをクローン
gfo repo clone alice/my-project
```

## 認証

トークンの解決順序:

1. `credentials.toml`（`gfo auth login` で保存）
2. サービス別環境変数（上記表を参照）
3. `GFO_TOKEN` 汎用環境変数（全サービス共通フォールバック）

**ファイルパス:**
- Windows: `%APPDATA%\gfo\credentials.toml`
- Linux / macOS: `~/.config/gfo/credentials.toml`

```bash
# インタラクティブにトークンを設定
gfo auth login --host github.com

# 環境変数で設定
export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx

# 設定状態を確認
gfo auth status
```

各サービスのトークン作成手順（必要なスコープ・権限）は [docs/authentication.ja.md](docs/authentication.ja.md) を参照してください。

## コマンド一覧

| コマンド | サブコマンド | 説明 |
|---|---|---|
| `gfo init` | — | プロジェクト設定の初期化 |
| `gfo auth` | `login`, `status` | トークン保存・認証状態確認 |
| `gfo pr` | `list`, `create`, `view`, `merge`, `close`, `reopen`, `checkout`, `update`, `diff`, `checks`, `files`, `commits`, `reviewers`, `update-branch`, `ready` | プルリクエスト操作 |
| `gfo issue` | `list`, `create`, `view`, `close`, `reopen`, `delete`, `update` | Issue 操作 |
| `gfo repo` | `list`, `create`, `clone`, `view`, `delete`, `fork`, `update`, `archive`, `languages`, `topics`, `compare` | リポジトリ操作 |
| `gfo release` | `list`, `create`, `view`, `update`, `delete`, `asset` | リリース管理 |
| `gfo label` | `list`, `create`, `update`, `delete` | ラベル管理 |
| `gfo milestone` | `list`, `create`, `view`, `update`, `close`, `reopen`, `delete` | マイルストーン管理 |
| `gfo comment` | `list`, `create`, `update`, `delete` | PR / Issue コメント操作 |
| `gfo review` | `list`, `create`, `dismiss` | PR レビュー操作 |
| `gfo branch` | `list`, `create`, `delete` | ブランチ操作 |
| `gfo tag` | `list`, `create`, `delete` | タグ操作 |
| `gfo status` | `list`, `create` | コミットステータス操作 |
| `gfo file` | `get`, `put`, `delete` | リポジトリ内ファイル操作 |
| `gfo webhook` | `list`, `create`, `delete`, `test` | Webhook 管理 |
| `gfo deploy-key` | `list`, `create`, `delete` | デプロイキー管理 |
| `gfo collaborator` | `list`, `add`, `remove` | コラボレーター管理 |
| `gfo ci` | `list`, `view`, `cancel` | CI/CD ジョブ操作 |
| `gfo user` | `whoami` | 認証ユーザー情報表示 |
| `gfo search` | `repos`, `issues` | リポジトリ・Issue 検索 |
| `gfo wiki` | `list`, `view`, `create`, `update`, `delete` | Wiki 操作 |
| `gfo browse` | — | リポジトリをブラウザで開く |
| `gfo branch-protect` | `list`, `view`, `set`, `remove` | ブランチ保護ルール管理 |
| `gfo notification` | `list`, `read` | 通知管理 |
| `gfo org` | `list`, `view`, `members`, `repos` | 組織管理 |
| `gfo ssh-key` | `list`, `create`, `delete` | SSH 鍵管理 |
| `gfo secret` | `list`, `set`, `delete` | CI/CD シークレット管理 |
| `gfo variable` | `list`, `set`, `get`, `delete` | CI/CD 変数管理 |
| `gfo api` | `METHOD`, `PATH` | 任意の API エンドポイント呼び出し |
| `gfo schema` | `--list`, `[command] [subcommand]` | コマンドの JSON Schema を表示（AI エージェント向け） |

各コマンドの詳細なオプション・使用例は [docs/commands.ja.md](docs/commands.ja.md) を参照してください。

### グローバルオプション

| オプション | 説明 | デフォルト |
|---|---|---|
| `--format {table,json,plain}` | 出力形式 | `table` |
| `--jq EXPRESSION` | JSON 出力に jq フィルタを適用（`--format json` を暗黙有効化） | — |
| `--version` | バージョン表示 | — |

## 設定

gfo は 3 層の設定解決を行います（優先度順）:

1. `git config --local`（リポジトリごと、`gfo init` で保存）
2. `~/.config/gfo/config.toml`（グローバル）
3. remote URL からの自動検出

**config.toml のサンプル:**

```toml
[defaults]
output = "table"          # デフォルト出力形式（table / json / plain）
host = "github.com"       # デフォルトホスト（省略可）

[hosts."gitea.example.com"]
type = "gitea"
api_url = "https://gitea.example.com/api/v1"

[hosts."gitlab.example.com"]
type = "gitlab"
api_url = "https://gitlab.example.com/api/v4"
```

**ファイルパス:**
- Windows: `%APPDATA%\gfo\config.toml`
- Linux / macOS: `~/.config/gfo/config.toml`

## サービス別機能対応表

| 機能 | GitHub | GitLab | Bitbucket | Azure DevOps | Backlog | Gitea | Forgejo | Gogs | GitBucket |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| PR / MR | ○ | ○ | ○ | ○ | ○ | ○ | ○ | × | ○ |
| PR マージ | ○ | ○ | ○ | ○ | × | ○ | ○ | × | ○ |
| Issue | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ |
| Release | ○ | ○ | × | × | × | ○ | ○ | × | ○ |
| Release Asset | ○ | ○ | × | × | × | ○ | ○ | × | × |
| Repo Update | ○ | ○ | ○ | ○ | × | ○ | ○ | × | × |
| Repo Archive | ○ | ○ | × | ○ | × | ○ | ○ | × | × |
| Repo Languages | ○ | ○ | × | × | × | ○ | ○ | × | × |
| Repo Topics | ○ | ○ | × | × | × | ○ | ○ | × | × |
| Repo Compare | ○ | ○ | ○ | ○ | × | ○ | ○ | × | × |
| Raw API | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ |
| Label | ○ | ○ | × | × | × | ○ | ○ | × | ○ |
| Milestone | ○ | ○ | × | × | × | ○ | ○ | × | ○ |
| PR Diff | ○ | ○ | ○ | × | × | ○ | ○ | × | × |
| PR Checks | ○ | ○ | ○ | ○ | × | ○ | ○ | × | × |
| PR Files | ○ | ○ | ○ | ○ | × | ○ | ○ | × | × |
| PR Commits | ○ | ○ | ○ | ○ | × | ○ | ○ | × | × |
| PR Reviewers | ○ | ○ | △ | ○ | × | ○ | ○ | × | × |
| PR Update Branch | ○ | ○ | × | × | × | ○ | ○ | × | × |
| PR Auto Merge | × | ○ | × | ○ | × | ○ | ○ | × | × |
| PR Ready | × | ○ | × | ○ | × | ○ | ○ | × | × |
| Review | ○ | ○ | × | × | × | × | × | × | × |
| Review Dismiss | ○ | × | × | ○ | × | ○ | ○ | × | × |
| Wiki | × | ○ | × | × | × | ○ | ○ | × | × |
| CI/CD | ○ | ○ | × | × | × | ○ | ○ | × | × |
| Search | ○ | ○ | × | × | × | × | × | × | × |
| Browse | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ |
| Branch Protect | ○ | ○ | ○ | × | × | ○ | ○ | × | × |
| Notification | ○ | ○ | × | × | ○ | ○ | ○ | × | × |
| Org | ○ | ○ | ○ | ○ | × | ○ | ○ | ○ | × |
| SSH Key | ○ | ○ | ○ | × | × | ○ | ○ | ○ | × |
| Secret | ○ | ○ | ○ | × | × | ○ | ○ | × | × |
| Variable | ○ | ○ | ○ | × | × | ○ | ○ | × | × |

> ×: 非対応（`NotSupportedError` を返します）
>
> **補足**:
> - PR Reviewers（Bitbucket）: `list` のみ対応（`add` / `remove` は非対応）。
> - Branch Protect（Bitbucket）: 強制プッシュと削除の制御のみ対応。レビュー要件・ステータスチェック・管理者への適用は非対応。
> - Org（Azure DevOps）: `list`, `view`, `repos` のみ対応。`members` は非対応（メンバー管理には Teams を使用）。

## 開発

```bash
# テスト実行（カバレッジ付き）
pytest

# 特定テストの実行
pytest tests/test_commands/test_pr.py
```

### 統合テスト

実サービスに対する統合テストも用意されています。

- **セルフホスト**（Gitea / Forgejo / Gogs / GitBucket）: Docker さえあれば自動実行可能
- **SaaS**（GitHub / GitLab / Bitbucket / Azure DevOps）: 各サービスのアカウントと API トークンが必要

詳細なセットアップ手順は [docs/integration-testing.ja.md](docs/integration-testing.ja.md) を参照してください。

```bash
# セルフホストテスト（Docker 自動起動・クリーンアップ込み）
bash tests/integration/run_selfhosted.sh

# SaaS テスト（.env にトークン設定後）
bash tests/integration/run_saas.sh
```

## コントリビューション

このプロジェクトは 0BSD ライセンスで提供しています。Issue の報告は歓迎しますが、対応・修正を保証するものではありません。Pull Request は受け付けていません。自由にフォークしてご利用ください。

## 変更履歴

[CHANGELOG.ja.md](CHANGELOG.ja.md) を参照してください。

## ライセンス

0BSD
