# gfo 方針

## Context

複数のGitホスティングサービス（GitHub, GitLab, Bitbucket Cloud, Azure DevOps, Gitea, Forgejo, Gogs, GitBucket, Backlog）を統一コマンドで操作するCLI「gfo」を新規作成する。既存の統合CLI（GCLI等）はBacklog・GitBucket・Bitbucket Cloud・Gogs・Azure DevOpsに未対応であり、この9サービスすべてをカバーするツールは存在しない。

**方式**: REST API 直接呼び出し（外部CLI依存なし）
**言語**: Python 3.11+、依存は `requests` のみ（TOML読み込みは標準ライブラリ `tomllib` を使用。credentials.toml への書き込みはシンプルな文字列フォーマットで行う）
**設定**: `git config --local` (プロジェクト) + `~/.config/gfo/` (ユーザー)

---

## ドキュメント体系

| ドキュメント | レイヤー | 内容 |
|---|---|---|
| plan.md（本書） | 方針 | フェーズ計画・検証戦略・完了条件 |
| spec.md | 仕様 | コマンド仕様・データモデル・サービス固有仕様 |
| design.md | 詳細設計 | モジュール設計・クラス設計・テスト設計 |

---

## プロジェクト構造

プロジェクト構造の詳細は spec.md §9 を参照。

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
"bitbucket.org" = "email:api-token-xxxx"   # email:api-token 形式
"myteam.backlog.com" = "backlog-api-key-xxxx"
```

Bitbucket Cloud の API Token は `email:api-token` の形式で格納する。`auth.py` がコロンで分割し Basic Auth に渡す。

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
2. サービス固有: `GITHUB_TOKEN`, `GITLAB_TOKEN`, `GITEA_TOKEN`, `BITBUCKET_TOKEN`, `BACKLOG_API_KEY`, `AZURE_DEVOPS_PAT`
3. `GFO_TOKEN` (汎用フォールバック)

---

## コマンド体系

コマンド仕様の詳細は spec.md §2 を参照。

```
gfo [--format table|json|plain] <command> <subcommand> [args]

gfo init        # プロジェクト初期設定
gfo auth        # login/status
gfo pr          # create/list/view/merge/close/checkout
gfo issue       # create/list/view/close
gfo repo        # create/clone/list/view
gfo release     # create/list
gfo label       # create/list
gfo milestone   # create/list
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

各サービスの API エンドポイントは spec.md §6.3 を参照。ページネーション方式の詳細は spec.md §6.4 を参照。エラーハンドリングの詳細は spec.md §8 を参照。サービス自動検出の詳細は spec.md §4 を参照。各サービスの固有仕様は spec.md §7 を参照。データモデルの詳細は spec.md §5 を参照。

---

## プラットフォーム対応メモ

- **設定パス**: Linux/macOS は `~/.config/gfo/`、Windows は `%APPDATA%/gfo/`
  → `pathlib.Path` + `os` モジュールで判定分岐を config.py に実装（外部依存なし）
- **git config のパス**: git 自体がパス解決するため特別な対応不要
- **MINGW64 環境**: subprocess での git 呼び出しは通常通り動作

---

## 実装フェーズ

各モジュールの詳細設計は design.md を参照。

> **Phase 分割基準**: Phase 2 は独立実装が必要な主要サービス、Phase 3 は継承ベース（GitBucket）または特殊な API 体系（Backlog, Azure DevOps）を持つサービス。GitBucket は GitHub 継承で実装は容易だが、検証に Docker 環境が必要なため Phase 3 に配置。

### Phase 1a: 基盤モジュール (概算: 2-3日)

1. `pyproject.toml` / プロジェクト構造作成
   - scripts エントリポイント (`gfo = "gfo.cli:main"`)、Python バージョン指定 (`requires-python = ">=3.11"`)、依存関係 (`dependencies = ["requests"]`) を含む。詳細は design.md 付録 B を参照
2. `adapter/base.py` - ABC + データクラス定義 (PullRequest, Issue, Repository)
3. `exceptions.py` - カスタム例外定義
4. `git_util.py` - remote URL取得、ブランチ名取得
5. `detect.py` - git remote URL パース + サービス自動検出
6. `config.py` - git config読み取り + TOML設定読み書き + 設定解決ロジック
7. `auth.py` - トークン管理
8. `http.py` - requests ラッパー (認証ヘッダー付与・エラーハンドリング・ページネーション)
9. `output.py` - table/json/plain フォーマッター
10. `__main__.py` - `python -m gfo` エントリポイント
11. テスト (detect, config, output)

```toml
# pyproject.toml の開発依存
[project.optional-dependencies]
dev = ["pytest", "responses"]
```

**Definition of Done**: 全基盤モジュールの単体テストが通り、`pytest tests/test_detect.py tests/test_config.py tests/test_output.py` が全パス。

### Phase 1b: GitHub アダプター + 主要コマンド (概算: 3-4日)

12. `adapter/registry.py` - アダプター登録
13. `adapter/github.py` - GitHub REST API v3 実装
14. `cli.py` - argparse 全サブコマンド定義 + ディスパッチ
15. `commands/init.py` - `gfo init` (対話的 + --non-interactive)
16. `commands/auth_cmd.py` - `gfo auth login/status`
17. `commands/pr.py` - PR操作 (create/list/view/merge/close/checkout)
18. `commands/issue.py` - Issue操作
19. テスト (GitHub adapter)
20. 統合テスト導入 — `responses` で HTTP をモックし、CLI エントリポイント (`main()`) から実行する統合テスト

**Definition of Done**: GitHub アダプター経由で PR/Issue の CRUD が `responses` モックテストで全パス、`gfo pr list` が手動で動作確認済み。GitHub Actions で pytest を自動実行する CI を導入済み。

### Phase 1c: 残りコマンド (概算: 1-2日)

21. `commands/repo.py` - Repo操作
22. `commands/release.py` - Release操作
23. `commands/label.py` - Label操作
24. `commands/milestone.py` - Milestone操作
25. テスト (release/label/milestone — GitHub adapter)

**Definition of Done**: release/label/milestone コマンドが GitHub アダプターで動作、テスト全パス。

### Phase 2: 主要サービス追加 (概算: 5-7日)

26. `adapter/gitlab.py` + テスト
27. `adapter/gitea.py` + テスト
28. `adapter/forgejo.py` (Gitea継承)
29. `adapter/gogs.py` (Gitea継承、PR操作は `NotSupportedError`) + テスト
30. `adapter/bitbucket.py` (Bitbucket Cloud) + テスト
31. Phase 2 追加サービス（GitLab, Gitea, Forgejo, Gogs, Bitbucket）での release/label/milestone テスト追加

> Phase 2/3 のセルフホスト型サービス（Gitea, GitBucket 等）は Docker Compose で検証環境を構築する。docker-compose.yml は tests/fixtures/ に配置。

**Definition of Done**: 追加5サービスのアダプターテスト全パス。

### Phase 3: 残りサービス (概算: 5-7日)

32. `adapter/gitbucket.py` (GitHub継承、base_url変更)
33. `adapter/backlog.py` + テスト (最も特殊)
34. `adapter/azure_devops.py` + テスト (3階層構造、Work Items、JSON Patch、WIQL)

**Definition of Done**: 全9サービスのアダプターテスト全パス、全コマンドの手動検証完了。

---

## CI/CD

Phase 1b 完了時に GitHub Actions で pytest を自動実行する CI を導入する。詳細な CI 構成は Phase 1b の完了条件に含める。

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

### 統合テスト戦略

コマンド → アダプター → HTTP の全レイヤーを通した統合テストを Phase 1b 完了時に導入する。`responses` ライブラリで HTTP をモックし、CLI エントリポイント (`main()`) から実行する統合テストにより、レイヤー間の結合を検証する。

### ページネーション テストケース
- 2ページ以上の取得
- 空の結果（0件）
- limit が1ページ分より少ない
- limit=0（全件取得）

### Windows 環境

CI で windows-latest マトリクスを追加し、パス区切り・icacls 等のプラットフォーム固有処理を検証する。

### サービス固有の検証
8. Gogs: Giteaアダプターのテストを流用 (Issue/Repo/Release) + PR操作の `NotSupportedError` テスト
9. Azure DevOps: responsesライブラリでREST API v7.1のモックテスト
   - PR CRUD + マージ (completionOptions.mergeStrategy指定)
   - Work Item作成 (JSON Patch形式) + WIQL検索
   - Basic Auth ヘッダーの正しいエンコーディング
