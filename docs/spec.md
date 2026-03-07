# gfo 仕様書

## 1. 概要

### 1.1 プロダクト名

**gfo** — 統合 Git Forge CLI

### 1.2 目的

複数の Git ホスティングサービスを統一コマンドで操作する CLI ツール。既存の統合 CLI（GCLI 等）がカバーしていない Backlog・GitBucket・Bitbucket Cloud・Gogs・Azure DevOps を含む 9 サービスすべてに対応する。

### 1.3 対応サービス

| # | サービス | API バージョン |
|---|---------|---------------|
| 1 | GitHub | v3 REST |
| 2 | GitLab | v4 REST |
| 3 | Bitbucket Cloud | v2 REST |
| 4 | Azure DevOps | v7.1 REST |
| 5 | Gitea | v1 REST |
| 6 | Forgejo | v1 REST |
| 7 | Gogs | v1 REST |
| 8 | GitBucket | v3 REST (GitHub 互換) |
| 9 | Backlog | v2 REST |

### 1.4 技術スタック

- **言語**: Python 3.11+
- **依存ライブラリ**: `requests` のみ
- **TOML 読み込み**: 標準ライブラリ `tomllib`（Python 3.11+）
- **TOML 書き込み**: シンプルな文字列フォーマット（外部ライブラリ不使用）
- **方式**: REST API 直接呼び出し（外部 CLI 依存なし）

---

## 2. コマンド仕様

### 2.1 グローバルオプション

```
gfo [--format table|json|plain] [--version] <command> <subcommand> [args]
```

| オプション | 値 | デフォルト | 説明 |
|-----------|---|-----------|------|
| `--format` | `table` \| `json` \| `plain` | `table` | 出力フォーマット。`config.toml` の `defaults.output` で変更可 |
| `--version` | — | — | バージョン情報を表示して終了。`__init__.py` の `__version__` を参照 |

### 2.2 gfo init

プロジェクトの Git Forge 設定を `.git/config` に保存する。

```
gfo init [--non-interactive] [--type TYPE] [--host HOST] [--api-url URL] [--project-key KEY]
```

| オプション | 説明 |
|-----------|------|
| `--non-interactive` | 対話プロンプトを表示せず、引数のみで設定する（CI 環境向け） |
| `--type TYPE` | サービス種別を明示指定 |
| `--host HOST` | ホスト名を明示指定 |
| `--api-url URL` | API Base URL を明示指定。省略時は `config.toml` の `hosts` セクションから自動解決し、それも未設定ならサービス種別のデフォルトを使用 |
| `--project-key KEY` | プロジェクトキーを明示指定（Backlog 等で必要） |

**動作**:
- 対話モード（デフォルト）: git remote URL から自動検出した結果を表示し、確認を求める
- `--non-interactive`: 引数で指定された値をそのまま設定する

**保存先**: `.git/config` の `[gfo]` セクション

```ini
[gfo]
    type = gitlab
    host = gitlab.example.com
    api-url = https://gitlab.example.com/api/v4
    project-key = MYAPP
```

### 2.3 gfo auth

#### gfo auth login

トークンを `credentials.toml` に保存する。

```
gfo auth login [--host HOST] [--token TOKEN]
```

| オプション | 説明 |
|-----------|------|
| `--host HOST` | 対象ホスト。省略時は現在のリポジトリの git remote URL から自動検出する。リポジトリ外で省略した場合はエラー |
| `--token TOKEN` | トークン文字列。省略時はインタラクティブに入力を求める（`getpass` 使用、エコーバックなし） |

`--token` を指定した場合、シェル履歴にトークンが残る可能性がある旨を注意表示する。

#### gfo auth status

設定済みのホストとトークンの状態を表示する。

```
gfo auth status
```

### 2.4 gfo pr

Pull Request（Merge Request）の操作。

#### gfo pr list

```
gfo pr list [--state open|closed|merged|all] [--limit N]
```

| オプション | デフォルト | 説明 |
|-----------|-----------|------|
| `--state` | `open` | フィルタする状態 |
| `--limit` | `30` | 取得件数上限。`0` で全件取得 |

#### gfo pr create

```
gfo pr create [--title T] [--body B] [--base BRANCH] [--head BRANCH] [--draft]
```

| オプション | デフォルト | 説明 |
|-----------|-----------|------|
| `--title` | 現在のブランチの最後のコミットメッセージ subject | PR タイトル |
| `--body` | 空文字列 | PR 本文 |
| `--base` | リポジトリのデフォルトブランチ | マージ先ブランチ |
| `--head` | 現在のブランチ | マージ元ブランチ |
| `--draft` | `false` | ドラフト PR として作成 |

#### gfo pr view

```
gfo pr view <number>
```

指定番号の PR の詳細を表示する。

#### gfo pr merge

```
gfo pr merge <number> [--method merge|squash|rebase]
```

| オプション | デフォルト | 説明 |
|-----------|-----------|------|
| `--method` | `merge` | マージ戦略 |

#### gfo pr close

```
gfo pr close <number>
```

指定番号の PR をクローズする。

#### gfo pr checkout

```
gfo pr checkout <number>
```

指定番号の PR のブランチをローカルにチェックアウトする。

**動作手順**:
1. API で PR 情報を取得し、ソースブランチ名を得る
2. `git fetch origin {refspec}` でリモートブランチを取得する
3. `git checkout -b {local_branch} FETCH_HEAD` でローカルブランチを作成してチェックアウトする

**ローカルブランチ命名規則**: ソースブランチ名をそのまま使用する（例: `feature/xxx`）。同名ブランチが既に存在する場合はエラーを表示する。

**サービス別 refspec**:
| サービス | refspec |
|---------|---------|
| GitHub / GitBucket | `pull/{number}/head` |
| GitLab | `merge-requests/{iid}/head` |
| Bitbucket Cloud | ソースブランチ名を直接 fetch |
| Azure DevOps | `pull/{id}/head`（`refs/pull/{id}/merge` も利用可能） |
| Gitea / Forgejo | `pull/{index}/head` |
| Gogs | `NotSupportedError`（PR API なし） |
| Backlog | ソースブランチ名を直接 fetch |

### 2.5 gfo issue

#### gfo issue list

```
gfo issue list [--state open|closed|all] [--assignee USER] [--label L] [--limit N]
```

| オプション | デフォルト | 説明 |
|-----------|-----------|------|
| `--state` | `open` | フィルタする状態 |
| `--assignee` | なし | 担当者でフィルタ |
| `--label` | なし | ラベルでフィルタ |
| `--limit` | `30` | 取得件数上限。`0` で全件取得 |

#### gfo issue create

```
gfo issue create [--title T] [--body B] [--assignee USER] [--label L] [--type TYPE] [--priority PRIORITY]
```

| オプション | デフォルト | 説明 |
|-----------|-----------|------|
| `--title` | なし（必須） | Issue タイトル。省略時はエラー終了: `Error: --title is required` |
| `--body` | 空文字列 | Issue 本文 |
| `--assignee` | なし | 担当者 |
| `--label` | なし | ラベル |
| `--type` | サービス依存 | Azure DevOps: `Task\|Bug\|"User Story"`（デフォルト: Task）。Backlog: プロジェクトの issueType。他サービスでは無視 |
| `--priority` | サービス依存 | Backlog: 優先度（priorityId）。他サービスでは無視 |

#### gfo issue view

```
gfo issue view <number>
```

#### gfo issue close

```
gfo issue close <number>
```

### 2.6 gfo repo

#### gfo repo list

```
gfo repo list [--owner USER] [--limit N]
```

| オプション | デフォルト | 説明 |
|-----------|-----------|------|
| `--owner` | なし | オーナーでフィルタ |
| `--limit` | `30` | 取得件数上限。`0` で全件取得 |

#### gfo repo create

```
gfo repo create <name> [--private] [--description D] [--host HOST]
```

| 引数/オプション | 説明 |
|---------------|------|
| `<name>` | リポジトリ名（必須） |
| `--private` | プライベートリポジトリとして作成 |
| `--description` | リポジトリの説明 |
| `--host HOST` | 作成先ホスト。省略時は現在のリポジトリの git remote URL から自動検出する。リポジトリ外で省略した場合は `config.toml` の `defaults.host` を使用。いずれも未設定ならエラー |

#### gfo repo clone

```
gfo repo clone <owner/name> [--host HOST]
```

| オプション | デフォルト | 説明 |
|-----------|-----------|------|
| `--host` | `config.toml` の `defaults.host` | クローン元ホスト。省略時はユーザー設定のデフォルトホストを使用。未設定ならエラー |

#### gfo repo view

```
gfo repo view [<owner/name>]
```

引数省略時は現在のリポジトリの情報を表示する。

### 2.7 gfo release

#### gfo release list

```
gfo release list [--limit N]
```

| オプション | デフォルト | 説明 |
|-----------|-----------|------|
| `--limit` | `30` | 取得件数上限。`0` で全件取得 |

#### gfo release create

```
gfo release create <tag> [--title T] [--notes N] [--draft] [--prerelease]
```

| 引数/オプション | デフォルト | 説明 |
|---------------|-----------|------|
| `<tag>` | — | タグ名（必須） |
| `--title` | タグ名と同じ | リリースタイトル |
| `--notes` | 空文字列 | リリースノート |
| `--draft` | `false` | ドラフトリリースとして作成 |
| `--prerelease` | `false` | プレリリースとしてマーク |

### 2.8 gfo label

#### gfo label list

```
gfo label list
```

#### gfo label create

```
gfo label create <name> [--color HEX] [--description D]
```

| 引数/オプション | 説明 |
|---------------|------|
| `<name>` | ラベル名（必須） |
| `--color` | HEX カラーコード |
| `--description` | ラベルの説明 |

### 2.9 gfo milestone

#### gfo milestone list

```
gfo milestone list
```

#### gfo milestone create

```
gfo milestone create <title> [--description D] [--due DATE]
```

| 引数/オプション | 説明 |
|---------------|------|
| `<title>` | マイルストーン名（必須） |
| `--description` | マイルストーンの説明 |
| `--due` | 期日 |

---

## 3. 設定管理

### 3.1 3 層構造

gfo の設定は以下の 3 層で管理される。

| 層 | 保存先 | 用途 |
|---|--------|------|
| プロジェクト設定 | `.git/config`（`git config --local`） | リポジトリ固有の設定 |
| ユーザー設定 | `~/.config/gfo/config.toml` | ホスト別のデフォルト設定 |
| 認証情報 | `~/.config/gfo/credentials.toml` | ホスト別のトークン |

**キー命名規則**: `.git/config` はハイフン区切り（`api-url`、git config の慣習）、TOML ファイルはアンダースコア区切り（`api_url`、Python/TOML の慣習）を使用する。

### 3.2 プロジェクト設定

`.git/config` の `[gfo]` セクションに保存される。`.git/` 配下のため**コミットされない**。`gfo init` で対話的に設定する。

```ini
[gfo]
    type = gitlab
    host = gitlab.example.com
    api-url = https://gitlab.example.com/api/v4
    project-key = MYAPP
```

手動での読み書きも可能:
```bash
git config --local gfo.type           # 読み取り
git config --local gfo.type gitlab    # 書き込み
```

### 3.3 ユーザー設定

ホスト別のデフォルト設定を保持する。新規クローン時に `gfo init` が参照する。

```toml
[defaults]
output = "table"           # table | json | plain
host = "github.com"        # gfo repo clone 等でホスト省略時に使用

[hosts."gitlab.example.com"]
type = "gitlab"
api_url = "https://gitlab.example.com/api/v4"

[hosts."myteam.backlog.com"]
type = "backlog"
api_url = "https://myteam.backlog.com/api/v2"
```

### 3.4 認証情報

ホスト名をキーにトークンを保存する。ファイルパーミッションは 600 に設定する。

```toml
[tokens]
"github.com" = "ghp_xxxx"
"gitlab.example.com" = "glpat-xxxx"
"bitbucket.org" = "user:app-password-xxxx"   # user:password 形式
"myteam.backlog.com" = "backlog-api-key-xxxx"
```

Bitbucket Cloud の App Password は `username:app-password` の形式で格納する。`auth.py` がコロンで分割し Basic Auth に渡す。

### 3.5 設定解決の優先順位

```
git config --local gfo.* (プロジェクト固有)
  ↓ 未設定なら
~/.config/gfo/config.toml の hosts.{host} セクション
  ↓ 未設定なら
git remote URL からの自動検出 (detect.py)
```

### 3.6 環境変数フォールバック（トークン）

トークンの解決順序:

1. `credentials.toml` のホスト別トークン
2. サービス固有の環境変数:
   | サービス | 環境変数 |
   |---------|---------|
   | GitHub | `GITHUB_TOKEN` |
   | GitLab | `GITLAB_TOKEN` |
   | Gitea / Forgejo / Gogs | `GITEA_TOKEN` |
   | GitBucket | `GITBUCKET_TOKEN` |
   | Bitbucket Cloud | `BITBUCKET_APP_PASSWORD` |
   | Backlog | `BACKLOG_API_KEY` |
   | Azure DevOps | `AZURE_DEVOPS_PAT` |
3. `GFO_TOKEN`（汎用フォールバック）

### 3.7 プラットフォーム別パス

| プラットフォーム | 設定ディレクトリ |
|----------------|-----------------|
| Linux / macOS | `~/.config/gfo/` |
| Windows | `%APPDATA%/gfo/` |

パスの判定は `pathlib.Path` + `os` モジュールで行う（外部依存なし）。

Windows 環境では、ファイル作成時に `icacls` で現在のユーザーのみにアクセス権を付与する（ベストエフォート）。

### 3.8 未設定状態での動作

- `gfo init` 未実施でも、git remote URL からの自動検出が成功すれば**暗黙的に動作する**
- `gfo init` は明示的にカスタム設定（`api-url`, `project-key` 等）が必要な場合のみ必要
- 自動検出に失敗した場合は `gfo init` の実行を案内するエラーメッセージを表示する

---

## 4. サービス自動検出

### 4.1 検出フロー

以下の順序で検出を試みる。先にマッチした結果を採用する。

1. **プロジェクト設定**: `git config --local gfo.type` があればその値を使用
2. **ユーザー設定**: `config.toml` の `hosts` セクションとホスト名を照合
3. **既知ホストテーブル**:
   | ホスト | サービス |
   |-------|---------|
   | `github.com` | github |
   | `gitlab.com` | gitlab |
   | `bitbucket.org` | bitbucket |
   | `dev.azure.com` | azure-devops |
   | `codeberg.org` | forgejo |
4. **特殊パターン**:
   - `*.backlog.com`, `*.backlog.jp` → backlog
   - `*.visualstudio.com` → azure-devops（旧 URL 形式）
5. **API エンドポイントプローブ**（未知ホストの場合）:
   | エンドポイント | 判定結果 |
   |--------------|---------|
   | `GET /api/v1/version` | Gitea / Forgejo / Gogs（レスポンス内容で区別） |
   | `GET /api/v4/version` | GitLab |
   | `GET /api/v3/` | GitBucket |

### 4.2 対応 remote URL パターン

| サービス | HTTPS | SSH |
|---------|-------|-----|
| GitHub | `https://github.com/{owner}/{repo}.git` | `git@github.com:{owner}/{repo}.git` |
| GitLab | `https://gitlab.com/{group}[/{sub}]/{project}.git` | `git@gitlab.com:{group}[/{sub}]/{project}.git` |
| Bitbucket Cloud | `https://bitbucket.org/{workspace}/{repo}.git` | `git@bitbucket.org:{workspace}/{repo}.git` |
| Azure DevOps | `https://dev.azure.com/{org}/{project}/_git/{repo}` | `git@ssh.dev.azure.com:v3/{org}/{project}/{repo}` |
| Azure DevOps (旧) | `https://{org}.visualstudio.com/{project}/_git/{repo}` | — |
| Gitea / Forgejo / Gogs | `https://{host}/{owner}/{repo}.git` | `git@{host}:{owner}/{repo}.git` |
| GitBucket | `https://{host}/git/{owner}/{repo}.git` | `git@{host}:{owner}/{repo}.git` |
| Backlog | `https://{space}.backlog.com/git/{PROJECT}/{repo}.git` | `{space}@{space}.git.backlog.com:/{PROJECT}/{repo}.git` |

**共通ルール**:
- `.git` サフィックスは有無両方に対応
- SSH は `git@host:path` 形式と `ssh://git@host/path` 形式の両方に対応
- ポート指定（`ssh://git@host:2222/path`）にも対応

---

## 5. データモデル

全サービスの差異は `Optional` フィールドで吸収する。サービスが提供しない情報は `None` とする。

### 5.1 PullRequest

| フィールド | 型 | 備考 |
|-----------|---|------|
| `number` | `int` | GitLab: `iid`、Azure DevOps: `pullRequestId` |
| `title` | `str` | |
| `body` | `str \| None` | |
| `state` | `str` | `"open"` \| `"closed"` \| `"merged"` に正規化 |
| `author` | `str` | ユーザー名または表示名 |
| `source_branch` | `str` | Azure DevOps: `refs/heads/` を除去して格納 |
| `target_branch` | `str` | 同上 |
| `draft` | `bool` | 未対応サービスは `False` |
| `url` | `str` | Web URL |
| `created_at` | `str` | ISO 8601 |
| `updated_at` | `str \| None` | |

### 5.2 Issue

| フィールド | 型 | 備考 |
|-----------|---|------|
| `number` | `int` | Azure DevOps: Work Item ID |
| `title` | `str` | |
| `body` | `str \| None` | |
| `state` | `str` | `"open"` \| `"closed"` に正規化 |
| `author` | `str` | |
| `assignees` | `list[str]` | |
| `labels` | `list[str]` | Azure DevOps: Tags |
| `url` | `str` | Web URL |
| `created_at` | `str` | |

### 5.3 Repository

| フィールド | 型 | 備考 |
|-----------|---|------|
| `name` | `str` | |
| `full_name` | `str` | `owner/repo` 形式に統一（Azure DevOps: `project/repo`） |
| `description` | `str \| None` | |
| `private` | `bool` | |
| `default_branch` | `str \| None` | |
| `clone_url` | `str` | HTTPS URL |
| `url` | `str` | Web URL |

### 5.4 Release

| フィールド | 型 | 備考 |
|-----------|---|------|
| `tag` | `str` | |
| `title` | `str` | |
| `body` | `str \| None` | |
| `draft` | `bool` | |
| `prerelease` | `bool` | |
| `url` | `str` | |
| `created_at` | `str` | |

### 5.5 Label

| フィールド | 型 | 備考 |
|-----------|---|------|
| `name` | `str` | |
| `color` | `str \| None` | HEX |
| `description` | `str \| None` | |

### 5.6 Milestone

| フィールド | 型 | 備考 |
|-----------|---|------|
| `number` | `int` | |
| `title` | `str` | |
| `description` | `str \| None` | |
| `state` | `str` | `"open"` \| `"closed"` |
| `due_date` | `str \| None` | |

---

## 6. アダプター仕様

### 6.1 共通インターフェース

`GitServiceAdapter` 抽象基底クラス（ABC）で以下のメソッドを定義する。共通ロジック（URL 構築、ページネーション呼び出し等）は基底クラスに実装する。

Forgejo → Gitea、GitBucket → GitHub の継承関係があるため、Protocol より ABC を採用する。

**PR 操作**:
| メソッド | 説明 |
|---------|------|
| `list_pull_requests(state, limit)` | PR 一覧取得 |
| `create_pull_request(title, body, base, head, draft)` | PR 作成 |
| `get_pull_request(number)` | PR 詳細取得 |
| `merge_pull_request(number, method)` | PR マージ |
| `close_pull_request(number)` | PR クローズ |

**Issue 操作**:
| メソッド | 説明 |
|---------|------|
| `list_issues(state, assignee, label, limit)` | Issue 一覧取得 |
| `create_issue(title, body, assignee, label)` | Issue 作成 |
| `get_issue(number)` | Issue 詳細取得 |
| `close_issue(number)` | Issue クローズ |

**Repository 操作**:
| メソッド | 説明 |
|---------|------|
| `list_repositories(owner, limit)` | リポジトリ一覧取得 |
| `create_repository(name, private, description)` | リポジトリ作成 |
| `get_repository(owner, name)` | リポジトリ詳細取得 |

**Release 操作**:
| メソッド | 説明 |
|---------|------|
| `list_releases(limit)` | リリース一覧取得 |
| `create_release(tag, title, notes, draft, prerelease)` | リリース作成 |

**Label 操作**:
| メソッド | 説明 |
|---------|------|
| `list_labels()` | ラベル一覧取得 |
| `create_label(name, color, description)` | ラベル作成 |

**Milestone 操作**:
| メソッド | 説明 |
|---------|------|
| `list_milestones()` | マイルストーン一覧取得 |
| `create_milestone(title, description, due_date)` | マイルストーン作成 |

### 6.2 サービス別仕様

| サービス | Base URL | 認証方式 | 継承元 |
|---------|----------|---------|--------|
| GitHub | `https://api.github.com` | `Authorization: Bearer {token}` | — |
| GitLab | `{host}/api/v4` | `Private-Token: {token}` | — |
| Bitbucket Cloud | `https://api.bitbucket.org/2.0` | Basic Auth | — |
| Azure DevOps | `https://dev.azure.com/{org}/{project}/_apis` | Basic Auth（PAT） | — |
| Gitea | `{host}/api/v1` | `Authorization: token {token}` | — |
| Forgejo | `{host}/api/v1` | `Authorization: token {token}` | Gitea |
| Gogs | `{host}/api/v1` | `Authorization: token {token}` | Gitea |
| GitBucket | `{host}/api/v3` | `Authorization: token {token}` | GitHub |
| Backlog | `{host}/api/v2` | `?apiKey={key}`（クエリパラメータ） | — |

### 6.3 主要 API エンドポイント

#### GitHub / GitBucket

GitBucket は GitHub のサブセット。

| 操作 | メソッド | エンドポイント |
|------|---------|--------------|
| PR 一覧 | `GET` | `/repos/{owner}/{repo}/pulls` |
| PR 作成 | `POST` | `/repos/{owner}/{repo}/pulls` |
| PR マージ | `PUT` | `/repos/{owner}/{repo}/pulls/{n}/merge` |
| Issue 一覧 | `GET` | `/repos/{owner}/{repo}/issues` |
| Issue 作成 | `POST` | `/repos/{owner}/{repo}/issues` |

#### GitLab

プロジェクト ID は `owner%2Frepo`（URL エンコード）で代用する。サブグループが複数階層ある場合も同様にエンコードする（例: `group%2Fsub1%2Fsub2%2Fproject`）。

| 操作 | メソッド | エンドポイント |
|------|---------|--------------|
| MR 一覧 | `GET` | `/projects/{id}/merge_requests` |
| MR 作成 | `POST` | `/projects/{id}/merge_requests` |
| MR マージ | `PUT` | `/projects/{id}/merge_requests/{iid}/merge` |
| Issue 一覧 | `GET` | `/projects/{id}/issues` |

#### Bitbucket Cloud

| 操作 | メソッド | エンドポイント |
|------|---------|--------------|
| PR 一覧 | `GET` | `/repositories/{workspace}/{repo}/pullrequests` |
| PR 作成 | `POST` | `/repositories/{workspace}/{repo}/pullrequests` |
| PR マージ | `POST` | `/repositories/{workspace}/{repo}/pullrequests/{id}/merge` |
| Issue 一覧 | `GET` | `/repositories/{workspace}/{repo}/issues` |

#### Azure DevOps (v7.1)

全リクエストに `api-version=7.1` クエリパラメータを付与する。

| 操作 | メソッド | エンドポイント | 備考 |
|------|---------|--------------|------|
| PR 一覧 | `GET` | `/_apis/git/repositories/{repoId}/pullrequests` | `searchCriteria.status` でフィルタ。`$top` + `$skip` でページネーション |
| PR 作成 | `POST` | `/_apis/git/repositories/{repoId}/pullrequests` | Body: `sourceRefName`, `targetRefName`（`refs/heads/` prefix 付き）, `title`, `description` |
| PR 取得 | `GET` | `/_apis/git/repositories/{repoId}/pullrequests/{id}` | |
| PR マージ | `PATCH` | `/_apis/git/repositories/{repoId}/pullrequests/{id}` | `status: "completed"` + `completionOptions.mergeStrategy` |
| PR クローズ | `PATCH` | `/_apis/git/repositories/{repoId}/pullrequests/{id}` | `status: "abandoned"` |
| Work Item 検索 | `POST` | `/_apis/wit/wiql` | WIQL クエリ言語。ID 一覧取得 → バッチ取得の 2 段階 |
| Work Item 作成 | `POST` | `/_apis/wit/workitems/$Task` | JSON Patch 形式。Content-Type: `application/json-patch+json` |
| Work Item 取得 | `GET` | `/_apis/wit/workitems/{id}` | |
| Work Item 更新 | `PATCH` | `/_apis/wit/workitems/{id}` | JSON Patch 形式 |
| Repo 一覧 | `GET` | `/_apis/git/repositories` | |

#### Gitea / Forgejo

| 操作 | メソッド | エンドポイント |
|------|---------|--------------|
| PR 一覧 | `GET` | `/repos/{owner}/{repo}/pulls` |
| PR 作成 | `POST` | `/repos/{owner}/{repo}/pulls` |
| PR マージ | `POST` | `/repos/{owner}/{repo}/pulls/{index}/merge` |
| Issue 一覧 | `GET` | `/repos/{owner}/{repo}/issues` |

#### Gogs

Gitea 互換だが **PR API なし**。

| 操作 | メソッド | エンドポイント |
|------|---------|--------------|
| Issue 一覧 | `GET` | `/repos/{owner}/{repo}/issues` |
| Issue 作成 | `POST` | `/repos/{owner}/{repo}/issues` |
| Repo 一覧 | `GET` | `/user/repos` |
| Release 一覧 | `GET` | `/repos/{owner}/{repo}/releases` |
| PR 操作 | — | API なし。Web URL を表示して案内 |

#### Backlog

| 操作 | メソッド | エンドポイント | 備考 |
|------|---------|--------------|------|
| PR 一覧 | `GET` | `/projects/{key}/git/repositories/{repo}/pullRequests` | |
| PR 作成 | `POST` | `/projects/{key}/git/repositories/{repo}/pullRequests` | |
| PR マージ | — | API なし | Web URL を表示して案内 |
| Issue 一覧 | `GET` | `/issues?projectId[]={id}` | |
| Issue 作成 | `POST` | `/issues` | `issueTypeId`, `priorityId` 必須（事前自動取得） |

### 6.4 ページネーション方式

| サービス | 方式 | 詳細 |
|---------|------|------|
| GitHub | Link header | `rel="next"` URL をパース |
| GitLab | ヘッダーベース | `page` + `per_page` クエリパラメータで要求し、レスポンスの `X-Next-Page` ヘッダーで次ページの有無を判定 |
| Bitbucket Cloud | レスポンスボディ | JSON 内の `next` フィールド |
| Azure DevOps | クエリパラメータ | `$top` + `$skip` |
| Gitea / Forgejo | Link header | GitHub 互換。`page` + `limit` パラメータ |
| Gogs | Link header | Gitea 互換 |
| GitBucket | Link header | GitHub 互換 |
| Backlog | オフセットベース | `count` + `offset` パラメータ |

`http.py` に共通ページネーションヘルパーを実装する:
- `paginate_link_header()` — GitHub / Gitea / GitBucket 用
- `paginate_offset()` — Backlog 用
- 各アダプターで適切なヘルパーを使用する

---

## 7. サービス固有仕様

### 7.1 Azure DevOps

#### 3 階層構造

Organization > Project > Repository の 3 階層で構成される。

- git remote URL からパース: `https://dev.azure.com/{org}/{project}/_git/{repo}` または `https://{org}.visualstudio.com/{project}/_git/{repo}`
- git config に `gfo.organization` キーを追加で保存する

```ini
[gfo]
    type = azure-devops
    host = dev.azure.com
    organization = myorg
    project = myproject
```

#### 認証

Basic Auth を使用する。ユーザー名は空文字、パスワードに PAT を使用する。

```
Authorization: Basic base64(:{PAT})
```

#### Work Items（Issue マッピング）

| gfo コマンド | Azure DevOps API | 備考 |
|-------------|-----------------|------|
| `gfo issue list` | `POST wiql`（WIQL 検索） | デフォルト: State != 'Closed' |
| `gfo issue create` | `POST workitems/$Task` | デフォルト type=Task。`--type Bug\|Task\|"User Story"` で変更可 |
| `gfo issue view` | `GET workitems/{id}` | |
| `gfo issue close` | `PATCH workitems/{id}` | State → Closed（JSON Patch 形式） |

#### PR マージ戦略マッピング

| `--method` | `completionOptions.mergeStrategy` |
|-----------|-----------------------------------|
| `merge` | `noFastForward` |
| `squash` | `squash` |
| `rebase` | `rebase` |

#### ブランチ名の処理

PR 作成時に `sourceRefName` / `targetRefName` に `refs/heads/` prefix を自動付与する。
PR 取得時に `refs/heads/` prefix を除去してデータモデルに格納する。

#### State 正規化

プロセステンプレートにより完了状態の名前が異なる（Agile: Closed, Scrum: Done, Basic: Done）。

| `--state` | WIQL 条件 |
|-----------|----------|
| `open` | `State NOT IN ('Closed', 'Done', 'Removed')` |
| `closed` | `State IN ('Closed', 'Done')` |

#### PR 状態マッピング

| gfo | Azure DevOps |
|-----|-------------|
| `open` | `active` |
| `closed` | `abandoned` |
| `merged` | `completed` |

### 7.2 Backlog

- **PR マージ**: API なし。`gfo pr merge` は Web URL を表示して案内する
- **Issue 作成**: `issueTypeId` と `priorityId` が必須。`gfo issue create` 時にプロジェクト情報を自動取得しデフォルト選択する。`--type` / `--priority` オプションでの指定も可能
- **URL 形式**: `https://<space>.backlog.com/git/<PROJECT>/<REPO>.git`
- **認証**: API キーをクエリパラメータに付与する（`?apiKey={key}`）

### 7.3 Gogs

- **PR 操作**: API なし。`gfo pr list/create/view/merge/close/checkout` はすべて `NotSupportedError` を発生させ、Web URL を案内する
- **対応リソース**: Issue, Repository, Release は Gitea 互換 API で動作する（Gogs が Gitea の前身であり、エンドポイントパスが同一）。Label と Milestone は Gogs API に存在しないため `NotSupportedError` とする
- **アダプター実装**: `GiteaAdapter` を継承し、PR / Label / Milestone 関連メソッドをオーバーライドする
- **自動検出**: `/api/v1/version` のレスポンス内容で Gitea / Forgejo / Gogs を区別する

### 7.4 PR `--state merged` のサービス別マッピング

| サービス | マッピング方法 |
|---------|--------------|
| GitHub / GitBucket | `state=closed` で取得後、`merged_at` の有無で判別 |
| GitLab | `state=merged` がネイティブに存在 |
| Bitbucket Cloud | `state=MERGED` |
| Azure DevOps | `searchCriteria.status=completed` |
| Gitea / Forgejo | `state=closed` で取得後、`merged` フィールドで判別 |
| Gogs | PR API なし（`NotSupportedError`） |
| Backlog | `GET /projects/{key}/statuses` で PR ステータス一覧を取得し、`Merged` 相当のステータス ID を動的に判定して `statusId[]` に指定 |

### 7.5 Bitbucket Cloud

- **認証**: App Password 形式。`username:app-password` を `credentials.toml` に格納し、コロンで分割して Basic Auth に渡す

---

## 8. エラーハンドリング

### 8.1 HTTP ステータスコード別処理

| ステータス | 処理 |
|-----------|------|
| 401 / 403 | 認証エラー → トークンの再設定を案内するメッセージ表示 |
| 404 | リソース未発見 → 明確なエラーメッセージ |
| 429 | レート制限 → `Retry-After` ヘッダーを尊重して待機（最大 1 回リトライ） |
| 5xx | サーバーエラー → リトライなし、エラーメッセージ表示 |

### 8.2 リトライポリシー

- レート制限（429）のみ自動リトライする（最大 1 回）
- それ以外の HTTP エラーはリトライしない

### 8.3 タイムアウト

全リクエストに `timeout=30` を明示指定する（`requests` のデフォルトは None＝無制限のため）。

### 8.4 非対応機能の動作

サービスが対応していない機能（Gogs の PR 操作、Backlog の PR マージ等）を実行した場合:

- **終了コード**: `1`
- **stderr**: `Error: {service} does not support {operation}. Use the web interface instead.`
- **stdout**: 該当操作の Web URL（パイプで利用可能にするため）

### 8.5 API キーマスキング

Backlog の `?apiKey=xxx` をログ・エラーメッセージから `?apiKey=***` に置換して出力する。

---

## 9. プロジェクト構造

```
gfo/
├── pyproject.toml
├── src/gfo/
│   ├── __init__.py          # __version__
│   ├── __main__.py          # python -m gfo エントリポイント
│   ├── cli.py               # argparse メインパーサー + ディスパッチ
│   ├── config.py            # 設定解決 (git config → user config → 自動検出)
│   ├── auth.py              # トークン管理 (credentials.toml + 環境変数)
│   ├── detect.py            # git remote URL → サービス自動検出
│   ├── output.py            # table/json/plain フォーマッター
│   ├── git_util.py          # git コマンドユーティリティ
│   ├── http.py              # requests ラッパー (認証ヘッダー付与・エラーハンドリング・ページネーション)
│   ├── adapter/
│   │   ├── __init__.py
│   │   ├── base.py          # ABC + データクラス (PullRequest, Issue, Repository 等)
│   │   ├── registry.py      # サービス種別 → アダプタークラス マッピング
│   │   ├── github.py        # GitHub API v3
│   │   ├── gitlab.py        # GitLab API v4
│   │   ├── gitea.py         # Gitea API v1
│   │   ├── forgejo.py       # Forgejo API v1 (Gitea 継承)
│   │   ├── gogs.py          # Gogs API v1 (Gitea 継承、PR なし)
│   │   ├── bitbucket.py     # Bitbucket Cloud API v2
│   │   ├── gitbucket.py     # GitBucket (GitHub API v3 互換、GitHub 継承)
│   │   ├── backlog.py       # Backlog API v2
│   │   └── azure_devops.py  # Azure DevOps REST API v7.1 (独立実装)
│   └── commands/
│       ├── __init__.py
│       ├── init.py          # gfo init (対話的 + --non-interactive)
│       ├── pr.py            # gfo pr create/list/view/merge/close/checkout
│       ├── issue.py         # gfo issue create/list/view/close
│       ├── repo.py          # gfo repo create/clone/list/view
│       ├── release.py       # gfo release create/list
│       ├── label.py         # gfo label create/list
│       ├── milestone.py     # gfo milestone create/list
│       └── auth_cmd.py      # gfo auth login/status
└── tests/
    ├── conftest.py
    ├── test_detect.py
    ├── test_config.py
    ├── test_output.py
    └── test_adapters/
        ├── test_github.py
        └── ...
```

### モジュール責務一覧

| モジュール | 責務 |
|-----------|------|
| `__init__.py` | バージョン定義 |
| `__main__.py` | `python -m gfo` エントリポイント |
| `cli.py` | argparse による全サブコマンド定義とディスパッチ |
| `config.py` | 3 層設定の解決ロジック。git config 読み取り、TOML 設定読み書き |
| `auth.py` | トークン管理。`credentials.toml` + 環境変数フォールバック |
| `detect.py` | git remote URL パースとサービス自動検出 |
| `output.py` | `table` / `json` / `plain` フォーマッター |
| `git_util.py` | git コマンド呼び出しユーティリティ（remote URL 取得、ブランチ名取得） |
| `http.py` | `requests` ラッパー。認証ヘッダー付与、エラーハンドリング、ページネーションヘルパー |
| `adapter/base.py` | `GitServiceAdapter` ABC + データクラス定義 |
| `adapter/registry.py` | サービス種別文字列からアダプタークラスへのマッピング |
| `adapter/*.py` | 各サービスのアダプター実装 |
| `commands/*.py` | 各サブコマンドの実装 |
