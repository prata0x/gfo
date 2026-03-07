# gfo - 統合Git Forge CLI 実装プラン

## Context

複数のGitホスティングサービス（GitHub, GitLab, Bitbucket Cloud, Azure DevOps, Gitea, Forgejo, Gogs, GitBucket, Backlog）を統一コマンドで操作するCLI「gfo」を新規作成する。既存の統合CLI（GCLI等）はBacklog・GitBucket・Bitbucket Cloud・Gogs・Azure DevOpsに未対応であり、この9サービスすべてをカバーするツールは存在しない。

**方式**: REST API 直接呼び出し（外部CLI依存なし）
**言語**: Python 3.11+、依存は `requests` のみ（TOML読み込みは標準ライブラリ `tomllib` を使用。credentials.toml への書き込みはシンプルな文字列フォーマットで行う）
**設定**: `git config --local` (プロジェクト) + `~/.config/gfo/` (ユーザー)

---

## プロジェクト構造

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
│   │   ├── base.py          # ABC + データクラス (PullRequest, Issue, Repository等)
│   │   ├── registry.py      # サービス種別 → アダプタークラス マッピング
│   │   ├── github.py        # GitHub API v3
│   │   ├── gitlab.py        # GitLab API v4
│   │   ├── gitea.py         # Gitea API v1
│   │   ├── forgejo.py       # Forgejo API v1 (Gitea継承)
│   │   ├── gogs.py          # Gogs API v1 (Gitea継承、PRなし)
│   │   ├── bitbucket.py     # Bitbucket Cloud API v2
│   │   ├── gitbucket.py     # GitBucket (GitHub API v3互換、GitHub継承)
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

---

## 設定管理 (3層構造)

### 層1: プロジェクト設定 → `git config --local`

`.git/config` に保存されるため**絶対にコミットされない**。`gfo init` で対話的に設定。

```ini
# .git/config に追加される
[gfo]
    type = gitlab
    host = gitlab.example.com
    api-url = https://gitlab.example.com/api/v4
    project-key = MYAPP
```

設定/取得:
```bash
$ gfo init                              # 対話的設定 (remote URLから自動検出 → 確認)
$ gfo init --non-interactive --type gitlab --host gitlab.example.com  # CI環境向け
$ git config --local gfo.type           # 読み取り
$ git config --local gfo.type gitlab    # 手動設定
```

### 層2: ユーザー設定 → `~/.config/gfo/config.toml`

ホスト別のデフォルト設定。新規クローン時に `gfo init` が参照。

```toml
[defaults]
output = "table"           # table | json | plain

[hosts."gitlab.example.com"]
type = "gitlab"
api_url = "https://gitlab.example.com/api/v4"

[hosts."myteam.backlog.com"]
type = "backlog"
api_url = "https://myteam.backlog.com/api/v2"
```

### 層3: 認証情報 → `~/.config/gfo/credentials.toml`

ホスト名をキーにトークン保存。ファイルパーミッション600。

```toml
[tokens]
"github.com" = "ghp_xxxx"
"gitlab.example.com" = "glpat-xxxx"
"bitbucket.org" = "user:app-password-xxxx"   # user:password 形式
"myteam.backlog.com" = "backlog-api-key-xxxx"
```

Bitbucket Cloud の App Password は `username:app-password` の形式で格納する。`auth.py` がコロンで分割し Basic Auth に渡す。

Windows: `%APPDATA%/gfo/` に配置。ファイル作成時に icacls で現在のユーザーのみにアクセス権を付与（ベストエフォート）。

### 設定解決の優先順位

```
git config --local gfo.* (プロジェクト固有)
  ↓ 未設定なら
~/.config/gfo/config.toml の hosts.{host} セクション
  ↓ 未設定なら
git remote URL からの自動検出 (detect.py)
```

### 未設定状態での動作

`gfo init` 未実施でも、git remote URL からの自動検出が成功すれば暗黙的に動作する。
`gfo init` は明示的にカスタム設定（api-url, project-key 等）が必要な場合のみ必要。
自動検出に失敗した場合は `gfo init` の実行を案内するエラーメッセージを表示。

### 環境変数フォールバック (トークン)

1. `credentials.toml` のホスト別トークン
2. サービス固有: `GITHUB_TOKEN`, `GITLAB_TOKEN`, `GITEA_TOKEN`, `BITBUCKET_APP_PASSWORD`, `BACKLOG_API_KEY`, `AZURE_DEVOPS_PAT`
3. `GFO_TOKEN` (汎用フォールバック)

---

## コマンド体系

```
gfo [--format table|json|plain] <command> <subcommand> [args]

gfo init [--non-interactive] [--type TYPE] [--host HOST]  # プロジェクト初期設定

gfo pr list       [--state open|closed|merged|all] [--limit N]  # --limit デフォルト: 30, 0で全件
gfo pr create     [--title T] [--body B] [--base BRANCH] [--head BRANCH] [--draft]
  --head 省略時: 現在のブランチを使用
  --base 省略時: リポジトリのデフォルトブランチを使用
  --title 省略時: 現在のブランチの最後のコミットメッセージ subject を使用
  --body 省略時: 空文字列
gfo pr view       <number>
gfo pr merge      <number> [--method merge|squash|rebase]
gfo pr close      <number>
gfo pr checkout   <number>

gfo issue list    [--state open|closed|all] [--assignee USER] [--label L] [--limit N]  # --limit デフォルト: 30, 0で全件
gfo issue create  [--title T] [--body B] [--assignee USER] [--label L]
gfo issue view    <number>
gfo issue close   <number>

gfo repo list     [--owner USER] [--limit N]  # --limit デフォルト: 30, 0で全件
gfo repo create   <name> [--private] [--description D]
gfo repo clone    <owner/name>
gfo repo view     [<owner/name>]

gfo release list  [--limit N]  # --limit デフォルト: 30, 0で全件
gfo release create <tag> [--title T] [--notes N] [--draft] [--prerelease]

gfo label list
gfo label create  <name> [--color HEX] [--description D]

gfo milestone list
gfo milestone create <title> [--description D] [--due DATE]

gfo auth login    [--host HOST] [--token TOKEN]
  --token 省略時: インタラクティブに入力を求める (getpass使用、エコーバック無し)
  --token 指定: CI環境向け (シェル履歴に残る旨を注意)
gfo auth status
```

---

## アダプター設計 (全サービス REST API 直接)

`GitServiceAdapter` ABC（抽象基底クラス）で共通インターフェースを定義。全アダプターが REST API を直接呼び出す。共通ロジック（URL構築、ページネーション呼び出し等）は基底クラスに実装。Forgejo→Gitea、GitBucket→GitHub の継承関係があるため、Protocol よりABCが適している。

| サービス | API | Base URL | 認証 | 継承 |
|---------|-----|----------|------|------|
| GitHub | v3 REST | `https://api.github.com` | `Authorization: Bearer {token}` | 基本実装 |
| GitLab | v4 REST | `{host}/api/v4` | `Private-Token: {token}` | 独立 |
| Bitbucket Cloud | v2 REST | `https://api.bitbucket.org/2.0` | Basic Auth | 独立 |
| Azure DevOps | v7.1 REST | `https://dev.azure.com/{org}/{project}/_apis` | Basic Auth (PAT) | 独立 |
| Gitea | v1 REST | `{host}/api/v1` | `Authorization: token {token}` | 独立 |
| Forgejo | v1 REST | `{host}/api/v1` | `Authorization: token {token}` | Gitea継承 |
| Gogs | v1 REST | `{host}/api/v1` | `Authorization: token {token}` | Gitea継承（PRなし） |
| GitBucket | v3 REST (GitHub互換) | `{host}/api/v3` | `Authorization: token {token}` | GitHub継承 |
| Backlog | v2 REST | `{host}/api/v2` | `?apiKey={key}` | 独立 |

---

## データクラス定義 (adapter/base.py)

全サービスの差異を `Optional` フィールドで吸収する。サービスが提供しない情報は `None`。

### PullRequest
| フィールド | 型 | 備考 |
|-----------|---|------|
| number | int | GitLab: iid, Azure DevOps: pullRequestId |
| title | str | |
| body | str \| None | |
| state | str | "open" \| "closed" \| "merged" に正規化 |
| author | str | ユーザー名/表示名 |
| source_branch | str | Azure DevOps: refs/heads/ を除去して格納 |
| target_branch | str | 同上 |
| draft | bool | 未対応サービスは False |
| url | str | Web URL |
| created_at | str | ISO 8601 |
| updated_at | str \| None | |

### Issue
| フィールド | 型 | 備考 |
|-----------|---|------|
| number | int | Azure DevOps: Work Item ID |
| title | str | |
| body | str \| None | |
| state | str | "open" \| "closed" に正規化 |
| author | str | |
| assignees | list[str] | |
| labels | list[str] | Azure DevOps: Tags |
| url | str | Web URL |
| created_at | str | |

### Repository
| フィールド | 型 | 備考 |
|-----------|---|------|
| name | str | |
| full_name | str | owner/repo 形式に統一 (Azure DevOps: project/repo) |
| description | str \| None | |
| private | bool | |
| default_branch | str \| None | |
| clone_url | str | HTTPS URL |
| url | str | Web URL |

### Release
| フィールド | 型 | 備考 |
|-----------|---|------|
| tag | str | |
| title | str | |
| body | str \| None | |
| draft | bool | |
| prerelease | bool | |
| url | str | |
| created_at | str | |

### Label
| フィールド | 型 | 備考 |
|-----------|---|------|
| name | str | |
| color | str \| None | HEX |
| description | str \| None | |

### Milestone
| フィールド | 型 | 備考 |
|-----------|---|------|
| number | int | |
| title | str | |
| description | str \| None | |
| state | str | "open" \| "closed" |
| due_date | str \| None | |

---

### 主要APIエンドポイント

**GitHub / GitBucket** (GitBucketはサブセット):
- PR一覧: `GET /repos/{owner}/{repo}/pulls`
- PR作成: `POST /repos/{owner}/{repo}/pulls`
- PRマージ: `PUT /repos/{owner}/{repo}/pulls/{n}/merge`
- Issue一覧: `GET /repos/{owner}/{repo}/issues`
- Issue作成: `POST /repos/{owner}/{repo}/issues`

**GitLab** (プロジェクトIDは `owner%2Frepo` で代用):
- MR一覧: `GET /projects/{id}/merge_requests`
- MR作成: `POST /projects/{id}/merge_requests`
- MRマージ: `PUT /projects/{id}/merge_requests/{iid}/merge`
- Issue一覧: `GET /projects/{id}/issues`

**Bitbucket Cloud**:
- PR一覧: `GET /repositories/{workspace}/{repo}/pullrequests`
- PR作成: `POST /repositories/{workspace}/{repo}/pullrequests`
- PRマージ: `POST /repositories/{workspace}/{repo}/pullrequests/{id}/merge`
- Issue一覧: `GET /repositories/{workspace}/{repo}/issues`

**Azure DevOps** (v7.1):
- PR一覧: `GET /_apis/git/repositories/{repoId}/pullrequests?api-version=7.1`
  - フィルタ: `searchCriteria.status` (active/abandoned/completed/all)
  - ページネーション: `$top` + `$skip`
- PR作成: `POST /_apis/git/repositories/{repoId}/pullrequests?api-version=7.1`
  - Body: `{ "sourceRefName": "refs/heads/xxx", "targetRefName": "refs/heads/main", "title": "...", "description": "..." }`
- PR取得: `GET /_apis/git/repositories/{repoId}/pullrequests/{pullRequestId}?api-version=7.1`
- PRマージ: `PATCH /_apis/git/repositories/{repoId}/pullrequests/{pullRequestId}?api-version=7.1`
  - Body: `{ "status": "completed", "completionOptions": { "mergeStrategy": "squash|noFastForward|rebase|rebaseMerge" } }`
- PRクローズ: `PATCH ...` + `{ "status": "abandoned" }`
- Work Item検索 (Issue相当): `POST /_apis/wit/wiql?api-version=7.1` (WIQL クエリ言語)
- Work Item作成: `POST /_apis/wit/workitems/$Task?api-version=7.1` (JSON Patch形式, Content-Type: `application/json-patch+json`)
- Work Item取得: `GET /_apis/wit/workitems/{id}?api-version=7.1`
- Work Item更新: `PATCH /_apis/wit/workitems/{id}?api-version=7.1` (JSON Patch形式)
- Repo一覧: `GET /_apis/git/repositories?api-version=7.1`

**Gitea / Forgejo**:
- PR一覧: `GET /repos/{owner}/{repo}/pulls`
- PR作成: `POST /repos/{owner}/{repo}/pulls`
- PRマージ: `POST /repos/{owner}/{repo}/pulls/{index}/merge`
- Issue一覧: `GET /repos/{owner}/{repo}/issues`

**Gogs** (Gitea互換、ただしPR APIなし):
- Issue一覧: `GET /repos/{owner}/{repo}/issues`
- Issue作成: `POST /repos/{owner}/{repo}/issues`
- Repo一覧: `GET /user/repos`
- Release一覧: `GET /repos/{owner}/{repo}/releases`
- **PR操作**: APIなし → `gfo pr *` はすべてWeb URLを表示して案内

**Backlog**:
- PR一覧: `GET /projects/{key}/git/repositories/{repo}/pullRequests`
- PR作成: `POST /projects/{key}/git/repositories/{repo}/pullRequests`
- PRマージ: **APIなし** → Web URLを表示して案内
- Issue一覧: `GET /issues?projectId[]={id}`
- Issue作成: `POST /issues` (issueTypeId, priorityId 必須 → 事前自動取得)

---

## ページネーション

`--limit N` で取得件数を制御。各サービスのページネーション方式:

| サービス | 方式 | 詳細 |
|---------|------|------|
| GitHub | Link header | `rel="next"` URL をパース |
| GitLab | X-Page / X-Total-Pages header | ページ番号ベース |
| Bitbucket Cloud | `next` URL in response body | JSON内の `next` フィールド |
| Azure DevOps | `$top` + `$skip` パラメータ | クエリパラメータベース |
| Gitea/Forgejo | Link header (GitHub互換) | `page` + `limit` パラメータ |
| GitBucket | Link header (GitHub互換) | GitHub同様 |
| Backlog | `count` + `offset` パラメータ | オフセットベース |

`http.py` に共通ページネーションヘルパーを実装:
- `paginate_link_header()` — GitHub/Gitea/GitBucket用
- `paginate_offset()` — Backlog用
- 各アダプターで適切なヘルパーを使用

---

## エラーハンドリング

### http.py の責務
- **HTTPステータスコード別処理**:
  - 401/403: 認証エラー → トークンの再設定を案内するメッセージ表示
  - 404: リソース未発見 → 明確なエラーメッセージ
  - 429: レート制限 → Retry-After ヘッダーを尊重して待機（最大1回リトライ）
  - 5xx: サーバーエラー → リトライなし、エラーメッセージ表示
- **リトライ**: レート制限(429)のみ自動リトライ。それ以外はリトライしない
- **タイムアウト**: requests のデフォルト30秒
- **URLログ出力時のマスキング**: Backlog の `?apiKey=xxx` をログ・エラーメッセージから `?apiKey=***` に置換して出力

---

## サービス自動検出 (detect.py)

git remote URL をパースしてサービス種別を判定:

1. `git config --local gfo.type` があればそれを使用
2. `config.toml` の `hosts` セクションとホスト照合
3. 既知ホストテーブル (`github.com`→github, `gitlab.com`→gitlab, `bitbucket.org`→bitbucket, `dev.azure.com`→azure-devops, `codeberg.org`→forgejo)
4. 特殊パターン:
   - `*.backlog.com`, `*.backlog.jp` → backlog
   - `*.visualstudio.com` → azure-devops（旧URL形式）
   - `dev.azure.com` → azure-devops
5. 未知ホスト → APIエンドポイントプローブ:
   - `GET /api/v1/version` → Gitea/Forgejo/Gogs (レスポンス内容で区別)
   - `GET /api/v4/version` → GitLab
   - `GET /api/v3/` → GitBucket

### 対応する remote URL パターン

| サービス | HTTPS | SSH |
|---------|-------|-----|
| GitHub | `https://github.com/{owner}/{repo}.git` | `git@github.com:{owner}/{repo}.git` |
| GitLab | `https://gitlab.com/{group}[/{sub}]/{project}.git` | `git@gitlab.com:{group}[/{sub}]/{project}.git` |
| Bitbucket | `https://bitbucket.org/{workspace}/{repo}.git` | `git@bitbucket.org:{workspace}/{repo}.git` |
| Azure DevOps | `https://dev.azure.com/{org}/{project}/_git/{repo}` | `git@ssh.dev.azure.com:v3/{org}/{project}/{repo}` |
| Azure DevOps (旧) | `https://{org}.visualstudio.com/{project}/_git/{repo}` | — |
| Gitea/Forgejo/Gogs | `https://{host}/{owner}/{repo}.git` | `git@{host}:{owner}/{repo}.git` |
| GitBucket | `https://{host}/git/{owner}/{repo}.git` | `git@{host}:{owner}/{repo}.git` |
| Backlog | `https://{space}.backlog.com/git/{PROJECT}/{repo}.git` | `{space}@{space}.git.backlog.com:/{PROJECT}/{repo}.git` |

- `.git` サフィックスは有無両方に対応
- SSH は `git@host:path` 形式と `ssh://git@host/path` 形式の両方に対応
- ポート指定 (`ssh://git@host:2222/path`) にも対応

---

## Azure DevOps固有の対応

- **3階層構造**: Organization > Project > Repository
  - git remote URLからパース: `https://dev.azure.com/{org}/{project}/_git/{repo}` または `https://{org}.visualstudio.com/{project}/_git/{repo}`
  - git config: `gfo.organization` キーを追加
- **認証**: Basic Auth (`Authorization: Basic base64(:{PAT})`) — ユーザー名は空文字
- **Work Items → Issue マッピング**:
  - `gfo issue create` 時にデフォルト type=Task、`--type Bug|Task|"User Story"` オプションで変更可
  - 一覧取得にはWIQL検索が必須（ID一覧取得 → バッチ取得の2段階）
  - 作成・更新は `application/json-patch+json` Content-Type（JSON Patch形式）
- **PRマージ戦略**: `--method` オプションを `completionOptions.mergeStrategy` にマッピング
  - `merge` → `noFastForward`、`squash` → `squash`、`rebase` → `rebase`
- **ブランチ名の `refs/heads/` prefix**: PR作成時にsource/target ブランチ名に自動付与
- **State正規化**: プロセステンプレートにより完了状態の名前が異なる (Agile: Closed, Scrum: Done, Basic: Done)。
  `gfo issue list --state open` は WIQL で `State NOT IN ('Closed', 'Done', 'Removed')` を使用。
  `--state closed` は `State IN ('Closed', 'Done')` を使用。

### 設定例

```ini
# .git/config
[gfo]
    type = azure-devops
    host = dev.azure.com
    organization = myorg
```

### gfoコマンドとのマッピング

| gfo コマンド | Azure DevOps API | 備考 |
|-------------|-----------------|------|
| `gfo pr list` | GET pullrequests | status: open→active, closed→abandoned, merged→completed |
| `gfo pr create` | POST pullrequests | sourceRefName に `refs/heads/` prefix 自動付与 |
| `gfo pr view` | GET pullrequests/{id} | |
| `gfo pr merge` | PATCH pullrequests/{id} (status=completed) | `--method` → mergeStrategy マッピング |
| `gfo pr close` | PATCH pullrequests/{id} (status=abandoned) | |
| `gfo pr checkout` | git fetch + checkout（ローカル操作） | |
| `gfo issue list` | POST wiql (WIQL検索) | デフォルト: State != 'Closed' |
| `gfo issue create` | POST workitems/$Task | デフォルト type=Task、`--type` で変更可 |
| `gfo issue view` | GET workitems/{id} | |
| `gfo issue close` | PATCH workitems/{id} (State→Closed) | JSON Patch形式 |
| `gfo repo list` | GET repositories | project内のリポジトリ一覧 |
| `gfo repo create` | POST repositories | |
| `gfo repo view` | GET repositories/{id} | |

---

## Gogs固有の対応

- **PR操作**: APIなし → `gfo pr list/create/view/merge/close/checkout` はすべて `NotSupportedError` を発生させ、Web URLを案内（Backlogの `pr merge` と同じパターン）
- **Issue/Repo/Release**: Gitea互換APIで動作（GogsがGiteaの前身であり、エンドポイントパスが同一）
- **アダプター実装**: `adapter/gogs.py` は `GiteaAdapter` を継承し、PR関連メソッドのみオーバーライド
- **自動検出**: `/api/v1/version` のレスポンス内容でGitea/Forgejo/Gogsを区別

---

## Backlog固有の対応

- **PRマージ**: APIなし → `gfo pr merge` はWeb URLを表示して案内
- **Issue作成**: `issueTypeId`, `priorityId` が必須 → `gfo issue create` 時にプロジェクト情報を自動取得しデフォルト選択。`--type`, `--priority` オプションで指定も可
- **URL形式**: `https://<space>.backlog.com/git/<PROJECT>/<REPO>.git`
- **認証**: APIキーをクエリパラメータに付与 (`?apiKey={key}`)

---

## サービス非対応機能の動作

サービスが対応していない機能（Gogs の PR操作、Backlog の PRマージ等）:
- 終了コード **1** で終了
- stderr: `Error: {service} does not support {operation}. Use the web interface instead.`
- stdout: 該当操作の Web URL（パイプで利用可能にするため）

---

## プラットフォーム対応メモ

- **設定パス**: Linux/macOS は `~/.config/gfo/`、Windows は `%APPDATA%/gfo/`
  → `pathlib.Path` + `os` モジュールで判定分岐を config.py に実装（外部依存なし）
- **git config のパス**: git 自体がパス解決するため特別な対応不要
- **MINGW64 環境**: subprocess での git 呼び出しは通常通り動作

---

## 実装フェーズ

### Phase 1a: 基盤モジュール
1. `pyproject.toml` / プロジェクト構造作成
2. `adapter/base.py` - ABC + データクラス定義 (PullRequest, Issue, Repository)
3. `git_util.py` - remote URL取得、ブランチ名取得
4. `detect.py` - git remote URL パース + サービス自動検出
5. `config.py` - git config読み取り + TOML設定読み書き + 設定解決ロジック
6. `auth.py` - トークン管理
7. `http.py` - requests ラッパー (認証ヘッダー付与・エラーハンドリング・ページネーション)
8. `output.py` - table/json/plain フォーマッター
9. `__main__.py` - `python -m gfo` エントリポイント
10. テスト (detect, config, output)

```toml
# pyproject.toml の開発依存
[project.optional-dependencies]
dev = ["pytest", "responses"]
```

### Phase 1b: GitHub アダプター + 主要コマンド
11. `adapter/registry.py` - アダプター登録
12. `adapter/github.py` - GitHub REST API v3 実装
13. `cli.py` - argparse 全サブコマンド定義 + ディスパッチ
14. `commands/init.py` - `gfo init` (対話的 + --non-interactive)
15. `commands/auth_cmd.py` - `gfo auth login/status`
16. `commands/pr.py` - PR操作 (create/list/view/merge/close/checkout)
17. `commands/issue.py` - Issue操作
18. テスト (GitHub adapter)

### Phase 1c: 残りコマンド
19. `commands/repo.py` - Repo操作
20. `commands/release.py` - Release操作
21. `commands/label.py` - Label操作
22. `commands/milestone.py` - Milestone操作

### Phase 2: 主要サービス追加
23. `adapter/gitlab.py` + テスト
24. `adapter/gitea.py` + テスト
25. `adapter/forgejo.py` (Gitea継承)
26. `adapter/gogs.py` (Gitea継承、PR操作は `NotSupportedError`) + テスト
27. `adapter/bitbucket.py` (Bitbucket Cloud) + テスト
28. `commands/release.py`, `commands/label.py`, `commands/milestone.py` の各アダプター対応

### Phase 3: 残りサービス
29. `adapter/gitbucket.py` (GitHub継承、base_url変更)
30. `adapter/backlog.py` + テスト (最も特殊)
31. `adapter/azure_devops.py` + テスト (3階層構造、Work Items、JSON Patch、WIQL)

---

## 検証方法

1. `pip install -e .` でローカルインストール
2. `gfo auth login --host github.com --token $GITHUB_TOKEN` でトークン設定
3. `gfo init` でプロジェクト設定 (自動検出確認)
4. `git config --local gfo.type` で設定保存確認
5. `gfo pr list`, `gfo issue list` 動作確認
6. `gfo --format json pr list` でJSON出力確認
7. `pytest tests/` で単体テスト実行 (responsesライブラリでAPIモック)

### テスト層の分離
- **アダプター層**: `responses` でHTTP応答をモック、APIレスポンス→データクラス変換を検証
- **コマンド層**: アダプターABCをモック（`unittest.mock`）、コマンドロジックを検証
- **detect層**: `subprocess` 出力をモック、URL パースの全パターンを検証

### ページネーション テストケース
- 2ページ以上の取得
- 空の結果（0件）
- limit が1ページ分より少ない
- limit=0（全件取得）
8. Gogs: Giteaアダプターのテストを流用 (Issue/Repo/Release) + PR操作の `NotSupportedError` テスト
9. Azure DevOps: responsesライブラリでREST API v7.1のモックテスト
   - PR CRUD + マージ (completionOptions.mergeStrategy指定)
   - Work Item作成 (JSON Patch形式) + WIQL検索
   - Basic Auth ヘッダーの正しいエンコーディング
