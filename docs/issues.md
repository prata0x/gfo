# gfo 改善課題一覧

`docs/cli-comparison.md` の比較分析に基づき、gfo が他ツール (gh/glab/tea/fj) と比べて不足している機能・命名の乖離を整理する。1 サービスのみ対応の固有機能は対象外。

---

## A. 命名の乖離

| # | 箇所 | gfo | 他ツールの多数派 | 対象ツール | 備考 |
|---|---|---|---|---|---|
| A1 | `label edit` のリネーム | `--new-name` | `--name` | gh/tea/fj (3/4) | gfo は位置引数で現在名を取るため `--name` でも動作上問題なし。gh も同方式 |

---

## B. 不足オプション・機能

### B1. pr merge 関連

| # | 機能 | 対応ツール | 実装難易度 | 備考 |
|---|---|---|---|---|
| B1-1 | `pr merge --delete-branch` | gh/glab/fj **(3/4)** | 低 | マージ後に `delete_branch` API を呼ぶ。アダプターに `delete_branch()` メソッドあり。tea は未対応 |
| B1-2 | `pr merge` コミットメッセージ指定 | gh/glab/tea/fj **(4/4)** | 中 | `merge_pull_request()` のシグネチャに `message`/`title` を追加。GitHub/GitLab/Gitea 系 API は対応 |

### B2. pr edit / issue edit のメタデータ変更

| # | 機能 | 対応ツール | 実装難易度 | 備考 |
|---|---|---|---|---|
| B2-1 | `pr edit` ラベル追加/削除 | gh/glab/tea/fj **(4/4)** | 中 | `update_pull_request()` にラベル操作を追加、または別途ラベル API を呼ぶ |
| B2-2 | `pr edit` 担当者追加/削除 | gh/glab/tea **(3/4)** | 中 | 同上 |
| B2-3 | `pr edit` レビュアー追加/削除 | gh/glab **(2/4)** | — | **対応不要**: gfo は `pr reviewers add/remove` で既にカバー |
| B2-4 | `pr edit` マイルストーン設定 | gh/glab/tea **(3/4)** | 中 | `update_pull_request()` にマイルストーンパラメータ追加 |
| B2-5 | `issue edit` ラベル追加/削除 | gh/glab/tea/fj **(4/4)** | 中 | `--add-label`/`--remove-label` の追加。現在は `--label` で置換のみ |
| B2-6 | `issue edit` 担当者追加/削除 | gh/glab/tea **(3/4)** | 中 | 同上。`--add-assignee`/`--remove-assignee` の追加 |
| B2-7 | `issue edit` マイルストーン設定 | gh/glab/tea **(3/4)** | 中 | `update_issue()` にマイルストーンパラメータ追加 |

### B3. issue list フィルタ拡張

| # | 機能 | 対応ツール | 実装難易度 | 備考 |
|---|---|---|---|---|
| B3-1 | `issue list --author` | gh/glab **(2/4)** | 低 | `list_issues()` に `author` パラメータ追加 |
| B3-2 | `issue list --milestone` | gh/glab/tea **(3/4)** | 低 | 同上 |
| B3-3 | `issue list --search` | gh/glab/tea **(3/4)** | 低〜中 | サービスによって検索 API の対応状況が異なる |
| B3-4 | `issue create --milestone` | gh/glab/tea **(3/4)** | 低 | `create_issue()` にマイルストーンパラメータ追加 |

### B4. release 関連

| # | 機能 | 対応ツール | 実装難易度 | 備考 |
|---|---|---|---|---|
| B4-1 | `release create --notes-file` | gh/glab **(2/4)** | 極低 | CLI 側でファイル読み込み→`--notes` に渡すだけ。アダプター変更不要 |

### B5. pr list フィルタ拡張

| # | 機能 | 対応ツール | 実装難易度 | 備考 |
|---|---|---|---|---|
| B5-1 | `pr list --author` | gh/glab/fj **(3/4)** | 低 | `list_pull_requests()` に `author` パラメータ追加 |
| B5-2 | `pr list --label` | gh/glab/fj **(3/4)** | 低 | 同上 |
| B5-3 | `pr list --assignee` | gh/glab/fj **(3/4)** | 低 | 同上 |
| B5-4 | `pr list --search` | gh/glab/fj **(3/4)** | 低〜中 | サービスによって検索 API の対応状況が異なる |
| B5-5 | `pr list --base` | gh/glab **(2/4)** | 低 | ベースブランチフィルタ |
| B5-6 | `pr list --head` | gh/glab **(2/4)** | 低 | ヘッドブランチフィルタ |
| B5-7 | `pr list --draft` | gh/glab **(2/4)** | 低 | ドラフトフィルタ |

---

## C. 実装バッチ

変更するファイル群の重なりでグループ化し、コンテキスト効率を最大化する。

### Batch 1: CLI 層のみ（アダプター変更なし）

**変更ファイル**: `cli.py`, `commands/release.py`, `commands/pr.py`, `commands/label.py`

| # | 課題 | 対応ツール |
|---|---|---|
| B4-1 | `release create --notes-file` | gh/glab (2/4) |
| B1-1 | `pr merge --delete-branch` | gh/glab/fj (3/4) |
| A1 | `label edit --name` エイリアス追加 | gh/tea/fj (3/4) |

B4-1 はファイル読み込み→`--notes` に渡すだけ。B1-1 は `delete_branch()` が既にあるのでコマンド側のみ。A1 は `--new-name` を残しつつ `--name` を追加。

---

### Batch 2: `list_pull_requests` / `list_issues` シグネチャ拡張

**変更ファイル**: `adapter/base.py`, `adapter/*.py` (全 9 アダプター), `commands/pr.py`, `commands/issue.py`, `cli.py`

| # | 課題 | 対応ツール |
|---|---|---|
| B5-1 | `pr list --author` | gh/glab/fj (3/4) |
| B5-2 | `pr list --label` | gh/glab/fj (3/4) |
| B5-3 | `pr list --assignee` | gh/glab/fj (3/4) |
| B5-4 | `pr list --search` | gh/glab/fj (3/4) |
| B5-5 | `pr list --base` | gh/glab (2/4) |
| B5-6 | `pr list --head` | gh/glab (2/4) |
| B5-7 | `pr list --draft` | gh/glab (2/4) |
| B3-1 | `issue list --author` | gh/glab (2/4) |
| B3-2 | `issue list --milestone` | gh/glab/tea (3/4) |
| B3-3 | `issue list --search` | gh/glab/tea (3/4) |

`list_pull_requests()` と `list_issues()` のシグネチャにオプショナルパラメータを追加。既存アダプターはデフォルト値で後方互換。対応できるサービスから順次実装。

---

### Batch 3: `create_issue` / `update_pull_request` / `update_issue` シグネチャ拡張

**変更ファイル**: `adapter/base.py`, `adapter/*.py` (全 9 アダプター), `commands/pr.py`, `commands/issue.py`, `cli.py`

| # | 課題 | 対応ツール |
|---|---|---|
| B3-4 | `issue create --milestone` | gh/glab/tea (3/4) |
| B2-1 | `pr edit` ラベル追加/削除 | gh/glab/tea/fj (4/4) |
| B2-2 | `pr edit` 担当者追加/削除 | gh/glab/tea (3/4) |
| B2-4 | `pr edit` マイルストーン設定 | gh/glab/tea (3/4) |
| B2-5 | `issue edit` ラベル追加/削除 | gh/glab/tea/fj (4/4) |
| B2-6 | `issue edit` 担当者追加/削除 | gh/glab/tea (3/4) |
| B2-7 | `issue edit` マイルストーン設定 | gh/glab/tea (3/4) |

`create_issue()` にマイルストーンパラメータ追加。`update_pull_request()` / `update_issue()` にラベル・担当者・マイルストーン操作パラメータを追加。Batch 2 と同じファイル群だが、変更するメソッドが異なるため分離。

---

### Batch 4: `merge_pull_request` シグネチャ拡張

**変更ファイル**: `adapter/base.py`, `adapter/*.py` (全 9 アダプター), `commands/pr.py`, `cli.py`

| # | 課題 | 対応ツール |
|---|---|---|
| B1-2 | `pr merge` コミットメッセージ指定 | gh/glab/fj (3/4) |

`merge_pull_request()` に `title`/`message` パラメータを追加。

---

### Batch 5: PR/Issue lock/unlock 新規追加

**変更ファイル**: `adapter/base.py`, `adapter/*.py` (GitHub/GitLab/Gitea の 3 アダプター), `commands/pr.py`, `commands/issue.py`, `cli.py`

| # | 課題 | API 対応サービス |
|---|---|---|
| E1-5 | `pr lock` / `pr unlock` | GitHub/GitLab/Gitea (3) |
| E1-6 | `issue lock` / `issue unlock` | GitHub/GitLab/Gitea (3) |

基底クラスに `lock_issue()` / `unlock_issue()` を追加（PR は Issue API を共有するサービスが多い）。コマンド側で `pr lock`/`issue lock` を登録。

---

### Batch 6: repo rename + CI 拡張

**変更ファイル**: `adapter/base.py`, `adapter/*.py` (6 アダプター), `commands/repo.py`, `commands/ci.py`, `cli.py`

| # | 課題 | API 対応サービス |
|---|---|---|
| E1-2 | `repo rename` | GitHub/GitLab/Bitbucket/Azure DevOps/Gitea/Forgejo (6) |
| E1-3 | `ci download` | GitHub/GitLab/Bitbucket/Azure DevOps/Gitea/Forgejo (6) |
| E1-4 | `ci watch` | GitHub/GitLab/Bitbucket/Azure DevOps/Gitea/Forgejo (6) |

E1-2 は既存の `update_repository()` に `name` パラメータ追加、または `repo edit --name` として統合可能。E1-3/E1-4 は CI 関連のアダプターメソッド追加。

---

### Batch 7: pr status 新規追加

**変更ファイル**: `adapter/base.py`, `adapter/*.py` (8 アダプター), `commands/pr.py`, `cli.py`

| # | 課題 | API 対応サービス |
|---|---|---|
| E1-1 | `pr status` | GitHub/GitLab/Bitbucket/Azure DevOps/Gitea/Forgejo/GitBucket/Backlog (8) |

ほぼ全サービスの API が対応。自分が作成した PR・レビューリクエストされた PR・担当の PR を一覧表示。検索 API のフィルタで実現可能。

---

### Batch 8: CI workflow / artifact 拡張

**変更ファイル**: `adapter/base.py`, `adapter/*.py` (GitHub/GitLab/Gitea の 3 アダプター), `commands/ci.py`, `cli.py`

| # | 課題 | API 対応サービス |
|---|---|---|
| E1-7 | `ci workflow list` / `enable` / `disable` | GitHub/GitLab/Gitea (3) |
| E1-8 | `ci artifact download` | GitHub/GitLab/Gitea (3) |

E1-7 は `list_workflows()` / `enable_workflow()` / `disable_workflow()` メソッド追加。E1-8 は `download_artifact()` メソッド追加。

---

### Batch 9: Issue subscribe / Org scope secrets

**変更ファイル**: `adapter/base.py`, `adapter/*.py` (4 アダプター), `commands/issue.py`, `commands/secret.py`, `commands/variable.py`, `cli.py`

| # | 課題 | API 対応サービス |
|---|---|---|
| E1-9 | `issue subscribe` / `unsubscribe` | GitHub/GitLab/Gitea/Forgejo (4) |
| E1-10 | Org レベル `secret` / `variable` | GitHub/GitLab/Gitea/Forgejo (4) |

E1-9 は `subscribe_issue()` / `unsubscribe_issue()` メソッド追加。E1-10 は既存 secret/variable コマンドに `--org` スコープオプション追加。

---

## E. API レベル調査で追加された課題

CLI ツールでは gh のみの対応だが、API レベルでは複数サービスが対応している機能。gfo は 9 サービスを横断するため、API 対応数で判断する。

### E1. 新規追加（API 4+ サービス対応）

| # | 機能 | API 対応サービス | 備考 |
|---|---|---|---|
| E1-1 | `pr status` | GitHub/GitLab/Bitbucket/Azure DevOps/Gitea/Forgejo/GitBucket/Backlog **(8)** | 自分に関連する PR の一覧。検索 API のフィルタで実現可能 |
| E1-2 | `repo rename` | GitHub/GitLab/Bitbucket/Azure DevOps/Gitea/Forgejo **(6)** | `PATCH /repos/{owner}/{repo}` の `name` フィールド。`repo edit` に統合可能 |
| E1-3 | `ci download` | GitHub/GitLab/Bitbucket/Azure DevOps/Gitea/Forgejo **(6)** | ログ・アーティファクトのダウンロード |
| E1-4 | `ci watch` | GitHub/GitLab/Bitbucket/Azure DevOps/Gitea/Forgejo **(6)** | ステータスポーリングで実現。`ci view` の拡張 or 新サブコマンド |
| E1-5 | `pr lock` / `pr unlock` | GitHub/GitLab/Gitea **(3)** | Discussion のロック。Gitea は `PUT/DELETE /issues/{index}/lock`。Forgejo は現行版で未対応 |
| E1-6 | `issue lock` / `issue unlock` | GitHub/GitLab/Gitea **(3)** | E1-5 と同じ API 基盤 |
| E1-7 | `ci workflow list` / `enable` / `disable` | GitHub/GitLab/Gitea **(3)** | `GET /repos/{owner}/{repo}/actions/workflows` (Gitea)、`gh workflow list/enable/disable`、glab `ci` で部分対応 |
| E1-8 | `ci artifact download` | GitHub/GitLab/Gitea **(3)** | `GET /repos/{owner}/{repo}/actions/artifacts/{id}/zip` (Gitea Swagger 確認済み)。E1-3 の具体化 |
| E1-9 | `issue subscribe` / `unsubscribe` | GitHub/GitLab/Gitea/Forgejo **(4)** | `PUT/DELETE /repos/{owner}/{repo}/issues/{index}/subscriptions/{user}` (Swagger 確認済み) |
| E1-10 | Org レベル `secret` / `variable` | GitHub/GitLab/Gitea/Forgejo **(4)** | 現在の `secret`/`variable` はリポジトリスコープのみ。`GET/PUT/DELETE /orgs/{org}/actions/secrets` (Swagger 確認済み) |

### E2. 検討（API 2 サービス対応）

| # | 機能 | API 対応サービス | 備考 |
|---|---|---|---|
| E2-1 | `repo sync` (fork 同期) | GitHub/Gitea/Forgejo **(3)** | Gitea: `POST /repos/{owner}/{repo}/merge-upstream`、Forgejo: `POST /repos/{owner}/{repo}/sync_fork` (Swagger 確認済み)。→ E1 昇格候補 |
| E2-2 | Issue/コメント添付ファイル | Gitea/Forgejo **(2)** | `GET/POST /repos/{owner}/{repo}/issues/{index}/assets` (Swagger 確認済み) |
| E2-3 | `package link` / `unlink` | Gitea/Forgejo **(2)** | `POST /packages/{owner}/{type}/{name}/-/link/{repo_name}` (Swagger 確認済み) |

### E3. 見送り（API 1 サービスのみ）

| # | 機能 | API 対応サービス | 備考 |
|---|---|---|---|
| E3-1 | `pr revert` | Azure DevOps のみ (REST)。GitHub は GraphQL のみ | REST API 対応が 1 サービスでは費用対効果が低い |
| E3-2 | `issue transfer` | GitLab のみ (REST)。GitHub は GraphQL のみ | 同上 |
| E3-3 | `issue develop` | GitHub のみ (REST) | 1 サービスのみ |

### E4. 対応不要

| 項目 | 理由 |
|---|---|
| B2-3 `pr edit` レビュアー | `pr reviewers add/remove` で既にカバー。glab も `mr approvers` を専用コマンドで提供しており、gfo の方式は妥当 |
