# gfo 改善課題一覧

`docs/cli-comparison.md` の比較分析・Swagger API 調査・CRUD 一貫性分析に基づき、gfo の改善課題を整理する。実装計画は `docs/todo.md` を参照。

---

## A. 命名の乖離

| # | 箇所 | gfo | 他ツールの多数派 | 対象ツール | 備考 |
|---|---|---|---|---|---|
| A1 | `label edit` のリネーム | `--new-name` | `--name` | gh/tea/fj (3/4) | gfo は位置引数で現在名を取るため `--name` でも動作上問題なし。gh も同方式 |

---

## B. 不足オプション・機能（CLI 比較由来）

### B1. pr merge 関連

| # | 機能 | 対応ツール | 難易度 | 備考 |
|---|---|---|---|---|
| B1-1 | `pr merge --delete-branch` | gh/glab/fj **(3/4)** | 低 | マージ後に `delete_branch` API を呼ぶ。アダプターに `delete_branch()` メソッドあり |
| B1-2 | `pr merge` コミットメッセージ指定 | gh/glab/tea/fj **(4/4)** | 中 | `merge_pull_request()` に `message`/`title` パラメータ追加 |

### B2. pr edit / issue edit のメタデータ変更

| # | 機能 | 対応ツール | 難易度 | 備考 |
|---|---|---|---|---|
| B2-1 | `pr edit` ラベル追加/削除 | gh/glab/tea/fj **(4/4)** | 中 | `update_pull_request()` にラベル操作追加、または別途ラベル API |
| B2-2 | `pr edit` 担当者追加/削除 | gh/glab/tea **(3/4)** | 中 | 同上 |
| B2-4 | `pr edit` マイルストーン設定 | gh/glab/tea **(3/4)** | 中 | `update_pull_request()` にマイルストーンパラメータ追加 |
| B2-5 | `issue edit` ラベル追加/削除 | gh/glab/tea/fj **(4/4)** | 中 | `--add-label`/`--remove-label` 追加。現在は `--label` で置換のみ |
| B2-6 | `issue edit` 担当者追加/削除 | gh/glab/tea **(3/4)** | 中 | `--add-assignee`/`--remove-assignee` 追加 |
| B2-7 | `issue edit` マイルストーン設定 | gh/glab/tea **(3/4)** | 中 | `update_issue()` にマイルストーンパラメータ追加 |

> B2-3 (`pr edit` レビュアー追加/削除) は `pr reviewers add/remove` で既にカバーのため対応不要。

### B3. issue list / create フィルタ拡張

| # | 機能 | 対応ツール | 難易度 | 備考 |
|---|---|---|---|---|
| B3-1 | `issue list --author` | gh/glab **(2/4)** | 低 | `list_issues()` に `author` パラメータ追加 |
| B3-2 | `issue list --milestone` | gh/glab/tea **(3/4)** | 低 | 同上 |
| B3-3 | `issue list --search` | gh/glab/tea **(3/4)** | 低〜中 | サービスごとに検索 API 対応が異なる |
| B3-4 | `issue create --milestone` | gh/glab/tea **(3/4)** | 低 | `create_issue()` にマイルストーンパラメータ追加 |

### B4. release 関連

| # | 機能 | 対応ツール | 難易度 | 備考 |
|---|---|---|---|---|
| B4-1 | `release create --notes-file` | gh/glab **(2/4)** | 極低 | CLI 側でファイル読み込み→`--notes` に渡すだけ。アダプター変更不要 |

### B5. pr list フィルタ拡張

| # | 機能 | 対応ツール | 難易度 | 備考 |
|---|---|---|---|---|
| B5-1 | `pr list --author` | gh/glab/fj **(3/4)** | 低 | `list_pull_requests()` に `author` パラメータ追加 |
| B5-2 | `pr list --label` | gh/glab/fj **(3/4)** | 低 | 同上 |
| B5-3 | `pr list --assignee` | gh/glab/fj **(3/4)** | 低 | 同上 |
| B5-4 | `pr list --search` | gh/glab/fj **(3/4)** | 低〜中 | サービスごとに検索 API 対応が異なる |
| B5-5 | `pr list --base` | gh/glab **(2/4)** | 低 | ベースブランチフィルタ |
| B5-6 | `pr list --head` | gh/glab **(2/4)** | 低 | ヘッドブランチフィルタ |
| B5-7 | `pr list --draft` | gh/glab **(2/4)** | 低 | ドラフトフィルタ |

---

## E. API レベル調査で追加された課題

CLI ツール比較では見えないが、Swagger / API ドキュメント調査で複数サービスが対応している機能。

### E1. 実装推奨（API 3+ サービス対応）

| # | 機能 | API 対応サービス | 備考 |
|---|---|---|---|
| E1-1 | `pr status` | GitHub/GitLab/Bitbucket/Azure DevOps/Gitea/Forgejo/GitBucket/Backlog **(8)** | 自分に関連する PR の一覧。検索 API のフィルタで実現可能 |
| E1-2 | `repo rename` | GitHub/GitLab/Bitbucket/Azure DevOps/Gitea/Forgejo **(6)** | `PATCH /repos/{owner}/{repo}` の `name` フィールド。`repo edit --name` に統合可能 |
| E1-3 | `ci download` | GitHub/GitLab/Bitbucket/Azure DevOps/Gitea/Forgejo **(6)** | ログ・アーティファクトのダウンロード |
| E1-4 | `ci watch` | GitHub/GitLab/Bitbucket/Azure DevOps/Gitea/Forgejo **(6)** | ステータスポーリング。`ci view` の拡張 or 新サブコマンド |
| E1-5 | `pr lock` / `pr unlock` | GitHub/GitLab/Gitea **(3)** | Discussion のロック。Forgejo は現行版で未対応 |
| E1-6 | `issue lock` / `issue unlock` | GitHub/GitLab/Gitea **(3)** | E1-5 と同じ API 基盤 |
| E1-7 | `ci workflow list` / `enable` / `disable` | GitHub/GitLab/Gitea **(3)** | Gitea Swagger: `GET /repos/{owner}/{repo}/actions/workflows` |
| E1-8 | `ci artifact download` | GitHub/GitLab/Gitea **(3)** | Gitea Swagger: `GET /actions/artifacts/{id}/zip`。E1-3 の具体化 |
| E1-9 | `issue subscribe` / `unsubscribe` | GitHub/GitLab/Gitea/Forgejo **(4)** | Swagger: `PUT/DELETE /issues/{index}/subscriptions/{user}` |
| E1-10 | Org レベル `secret` / `variable` | GitHub/GitLab/Gitea/Forgejo **(4)** | 現在はリポジトリスコープのみ。Swagger: `/orgs/{org}/actions/secrets` |

### E2. 検討（API 2〜3 サービス対応）

| # | 機能 | API 対応サービス | 備考 |
|---|---|---|---|
| E2-1 | `repo sync` (fork 同期) | GitHub/Gitea/Forgejo **(3)** | Gitea: `merge-upstream`、Forgejo: `sync_fork`。E1 昇格候補 |
| E2-2 | Issue/コメント添付ファイル | Gitea/Forgejo **(2)** | Swagger: `/issues/{index}/assets` |
| E2-3 | `package link` / `unlink` | Gitea/Forgejo **(2)** | Swagger: `/packages/{owner}/{type}/{name}/-/link/{repo_name}` |

### E3. 見送り（API 1 サービスのみ）

| # | 機能 | API 対応サービス | 備考 |
|---|---|---|---|
| E3-1 | `pr revert` | Azure DevOps のみ (REST) | GitHub は GraphQL のみ |
| E3-2 | `issue transfer` | GitLab のみ (REST) | GitHub は GraphQL のみ |
| E3-3 | `issue develop` | GitHub のみ (REST) | 1 サービスのみ |

---

## F. CRUD 一貫性の課題

gfo はリソースごとに CRUD (list/create/view/edit/delete) の一貫性を保つ設計。以下は現状のギャップ。

### F1. view がない（list/create/delete はある）

| # | コマンド | API 対応サービス | API パス |
|---|---|---|---|
| F1-1 | `branch view` | GitHub/GitLab/Bitbucket/Azure DevOps/Gitea/Forgejo/Gogs/GitBucket **(8)** | `GET /repos/{owner}/{repo}/branches/{branch}` |
| F1-2 | `tag view` | GitHub/GitLab/Gitea/Forgejo **(4)** | `GET /repos/{owner}/{repo}/tags/{tag}` |
| F1-3 | `deploy-key view` | GitHub/GitLab/Bitbucket/Gitea/Forgejo/Gogs **(6)** | `GET /repos/{owner}/{repo}/keys/{id}` |
| F1-4 | `ssh-key view` | GitHub/GitLab/Bitbucket/Gitea/Forgejo/Gogs **(6)** | `GET /user/keys/{id}` |
| F1-5 | `gpg-key view` | GitHub/GitLab/Bitbucket/Gitea/Forgejo **(5)** | `GET /user/gpg_keys/{id}` |

### F2. edit がない（create/delete はある）

| # | コマンド | API 対応サービス | API パス |
|---|---|---|---|
| F2-1 | `webhook edit` | GitHub/GitLab/Bitbucket/Backlog/Gitea/Forgejo/Gogs/GitBucket **(8)** | `PATCH /repos/{owner}/{repo}/hooks/{id}` |
| F2-2 | `org edit` | GitHub/GitLab/Gitea/Forgejo/Gogs **(5)** | `PATCH /orgs/{org}` |
| F2-3 | `release asset edit` | GitHub/GitLab/Gitea/Forgejo **(4)** | `PATCH /releases/{id}/assets/{id}` |
| F2-4 | `tag-protect edit` | GitLab/Gitea/Forgejo **(3)** | `PATCH /repos/{owner}/{repo}/tag_protections/{id}` |

### F3. 設計上の理由で対応不要

| コマンド | 理由 |
|---|---|
| `secret view` | シークレットは暗号化済みで読み取り不可（全サービス共通仕様） |
| `status edit` | コミットステータスは追記モデル（GitHub/GitLab 共通） |
| `pr review edit` | 投稿済みレビュー本文の編集 API が全サービスで未提供 |
| `issue time edit` | 時間エントリの修正 API が未提供。delete → re-add で代替 |
| `notification delete` | 通知の削除 API が未提供。mark-read のみ（全サービス共通） |
| `collaborator edit` | `collaborator add` の再実行で権限変更可能。専用 edit は不要 |
