# gfo - 統合Git Forge CLI 実装プラン

## Context

複数のGitホスティングサービス（GitHub, GitLab, Bitbucket, Gitea, Forgejo, GitBucket, Backlog）を統一コマンドで操作するCLI「gfo」を新規作成する。既存の統合CLI（GCLI等）はBacklog・GitBucket・Bitbucketに未対応であり、この7サービスすべてをカバーするツールは存在しない。

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
│   │   ├── bitbucket.py     # Bitbucket Cloud API v2
│   │   ├── gitbucket.py     # GitBucket (GitHub API v3互換、GitHub継承)
│   │   └── backlog.py       # Backlog API v2
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
"bitbucket.org" = "app-password-xxxx"
"myteam.backlog.com" = "backlog-api-key-xxxx"
```

Windows: `%APPDATA%/gfo/` に配置。ファイル作成時に icacls で現在のユーザーのみにアクセス権を付与（ベストエフォート）。

### 設定解決の優先順位

```
git config --local gfo.* (プロジェクト固有)
  ↓ 未設定なら
~/.config/gfo/config.toml の hosts.{host} セクション
  ↓ 未設定なら
git remote URL からの自動検出 (detect.py)
```

### 環境変数フォールバック (トークン)

1. `credentials.toml` のホスト別トークン
2. `GFO_TOKEN` (汎用)
3. サービス固有: `GITHUB_TOKEN`, `GITLAB_TOKEN`, `GITEA_TOKEN`, `BITBUCKET_APP_PASSWORD`, `BACKLOG_API_KEY`

---

## コマンド体系

```
gfo [--format table|json|plain] <command> <subcommand> [args]

gfo init [--non-interactive] [--type TYPE] [--host HOST]  # プロジェクト初期設定

gfo pr list       [--state open|closed|merged|all] [--limit N]
gfo pr create     [--title T] [--body B] [--base BRANCH] [--head BRANCH] [--draft]
gfo pr view       <number>
gfo pr merge      <number> [--method merge|squash|rebase]
gfo pr close      <number>
gfo pr checkout   <number>

gfo issue list    [--state open|closed|all] [--assignee USER] [--label L] [--limit N]
gfo issue create  [--title T] [--body B] [--assignee USER] [--label L]
gfo issue view    <number>
gfo issue close   <number>

gfo repo list     [--owner USER] [--limit N]
gfo repo create   <name> [--private] [--description D]
gfo repo clone    <owner/name>
gfo repo view     [<owner/name>]

gfo release list  [--limit N]
gfo release create <tag> [--title T] [--notes N] [--draft] [--prerelease]

gfo label list
gfo label create  <name> [--color HEX] [--description D]

gfo milestone list
gfo milestone create <title> [--description D] [--due DATE]

gfo auth login    [--host HOST] [--token TOKEN]
gfo auth status
```

---

## アダプター設計 (全サービス REST API 直接)

`GitServiceAdapter` ABC（抽象基底クラス）で共通インターフェースを定義。全アダプターが REST API を直接呼び出す。共通ロジック（URL構築、ページネーション呼び出し等）は基底クラスに実装。Forgejo→Gitea、GitBucket→GitHub の継承関係があるため、Protocol よりABCが適している。

| サービス | API | Base URL | 認証 | 継承 |
|---------|-----|----------|------|------|
| GitHub | v3 REST | `https://api.github.com` | `Authorization: Bearer {token}` | 基本実装 |
| GitLab | v4 REST | `{host}/api/v4` | `Private-Token: {token}` | 独立 |
| Gitea | v1 REST | `{host}/api/v1` | `Authorization: token {token}` | 独立 |
| Forgejo | v1 REST | `{host}/api/v1` | `Authorization: token {token}` | Gitea継承 |
| Bitbucket | v2 REST | `https://api.bitbucket.org/2.0` | Basic Auth | 独立 |
| GitBucket | v3 REST (GitHub互換) | `{host}/api/v3` | `Authorization: token {token}` | GitHub継承 |
| Backlog | v2 REST | `{host}/api/v2` | `?apiKey={key}` | 独立 |

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

**Gitea / Forgejo**:
- PR一覧: `GET /repos/{owner}/{repo}/pulls`
- PR作成: `POST /repos/{owner}/{repo}/pulls`
- PRマージ: `POST /repos/{owner}/{repo}/pulls/{index}/merge`
- Issue一覧: `GET /repos/{owner}/{repo}/issues`

**Bitbucket Cloud**:
- PR一覧: `GET /repositories/{workspace}/{repo}/pullrequests`
- PR作成: `POST /repositories/{workspace}/{repo}/pullrequests`
- PRマージ: `POST /repositories/{workspace}/{repo}/pullrequests/{id}/merge`
- Issue一覧: `GET /repositories/{workspace}/{repo}/issues`

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
| Gitea/Forgejo | Link header (GitHub互換) | `page` + `limit` パラメータ |
| Bitbucket | `next` URL in response body | JSON内の `next` フィールド |
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
3. 既知ホストテーブル (`github.com`→github, `gitlab.com`→gitlab, `codeberg.org`→forgejo, `bitbucket.org`→bitbucket)
4. Backlog特殊パターン (`*.backlog.com`, `*.backlog.jp`)
5. 未知ホスト → APIエンドポイントプローブ:
   - `GET /api/v1/version` → Gitea/Forgejo (レスポンス内容で区別)
   - `GET /api/v4/version` → GitLab
   - `GET /api/v3/` → GitBucket

---

## Backlog固有の対応

- **PRマージ**: APIなし → `gfo pr merge` はWeb URLを表示して案内
- **Issue作成**: `issueTypeId`, `priorityId` が必須 → `gfo issue create` 時にプロジェクト情報を自動取得しデフォルト選択。`--type`, `--priority` オプションで指定も可
- **URL形式**: `https://<space>.backlog.com/git/<PROJECT>/<REPO>.git`
- **認証**: APIキーをクエリパラメータに付与 (`?apiKey={key}`)

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
26. `adapter/bitbucket.py` + テスト
27. `commands/release.py`, `commands/label.py`, `commands/milestone.py` の各アダプター対応

### Phase 3: 残りサービス
28. `adapter/gitbucket.py` (GitHub継承、base_url変更)
29. `adapter/backlog.py` + テスト (最も特殊)

---

## 検証方法

1. `pip install -e .` でローカルインストール
2. `gfo auth login --host github.com --token $GITHUB_TOKEN` でトークン設定
3. `gfo init` でプロジェクト設定 (自動検出確認)
4. `git config --local gfo.type` で設定保存確認
5. `gfo pr list`, `gfo issue list` 動作確認
6. `gfo --format json pr list` でJSON出力確認
7. `pytest tests/` で単体テスト実行 (responsesライブラリでAPIモック)
