# 第2弾: PR操作の拡充（日常利用で需要大）

## TODO

1. [ ] **PR diff** (#3) — PR の差分をターミナルに表示。6サービス対応可能
2. [ ] **PR checks** (#4) — PR に紐づく CI ステータス一覧。7サービス対応可能
3. [ ] **PR files** (#30) — 変更ファイル一覧取得。6サービス対応可能
4. [ ] **PR commits** (#31) — PR のコミット一覧取得。6サービス対応可能
5. [ ] **PR requested reviewers** (#29) — レビュアーリクエスト。6サービス対応可能
6. [ ] **PR update branch** (#32) — ベースブランチを head にマージして最新化。4サービス対応可能
7. [ ] **PR auto-merge** (#47) — CI パス後の自動マージ設定。5サービス対応可能
8. [ ] **PR review dismiss** (#48) — レビューの却下/取り消し。4サービス対応可能
9. [ ] **PR ready** (#18) — ドラフト PR を通常 PR に変更。6サービス対応可能

---

## PR diff (#3)

PR の差分をターミナルに表示する。checkout 不要で差分確認が可能。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | ○ | △ | ○ | ○ | × | × | × |

### APIエンドポイント

- **GitHub**: `GET /pulls/{number}` に `Accept: application/vnd.github.diff` ヘッダー
- **GitLab**: `GET /merge_requests/:iid/diffs`
- **Bitbucket**: `GET /pullrequests/{id}/diff` で unified diff
- **Azure DevOps**: Iteration Changes API でファイル単位の変更メタデータ取得可能。行レベル unified diff は直接取得不可
- **Gitea/Forgejo**: `GET /pulls/{index}.diff`
- **Gogs**: PR API 未実装
- **GitBucket**: diff 取得 API なし
- **Backlog**: diff 取得 API なし

### 実装詳細

- **adapter層**: `BaseAdapter` に `get_pull_request_diff(number)` を追加。unified diff 形式の文字列を返す
- **command層**: `commands/pr.py` に `diff` サブコマンドを追加。出力はそのまま標準出力へ。`--color` オプションでシンタックスハイライト対応も検討

---

## PR checks (#4)

PR に紐づく CI ステータス一覧を表示する。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | ○ | ○ | ○ | ○ | × | ○ | × |

### APIエンドポイント

- **GitHub**: `GET /commits/{ref}/check-runs`（Check Runs API）+ `GET /commits/{ref}/status`
- **GitLab**: `GET /merge_requests/:iid/pipelines`
- **Bitbucket**: `GET /commit/{node}/statuses`
- **Azure DevOps**: `GET /pullRequests/{id}/statuses`
- **Gitea/Forgejo**: `GET /repos/{owner}/{repo}/statuses/{ref}`
- **Gogs**: CommitStatus API 未実装
- **GitBucket**: `GET /commits/{ref}/statuses`（GitHub 互換）
- **Backlog**: CI の概念なし

### 実装詳細

- **adapter層**: `BaseAdapter` に `get_pull_request_checks(number)` を追加。チェック名・ステータス・URL のリストを返す
- **command層**: `commands/pr.py` に `checks` サブコマンドを追加。テーブル形式で表示（名前、ステータス、結論、URL）

---

## PR files (#30)

PR の変更ファイル一覧を取得する。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | ○ | ○ | ○ | ○ | × | × | × |

### APIエンドポイント

- **GitHub**: `GET /repos/{owner}/{repo}/pulls/{number}/files`
- **GitLab**: `GET /projects/:id/merge_requests/:iid/changes`
- **Bitbucket**: `GET /repositories/{workspace}/{repo}/pullrequests/{id}/diffstat`
- **Azure DevOps**: `GET /pullrequests/{id}/iterations/{iterationId}/changes`
- **Gitea/Forgejo**: `GET /repos/{owner}/{repo}/pulls/{index}/files`

### 実装詳細

- **adapter層**: `BaseAdapter` に `list_pull_request_files(number)` を追加。ファイルパス・ステータス（added/modified/deleted）・変更行数のリストを返す
- **command層**: `commands/pr.py` に `files` サブコマンドを追加。PR diff (#3) と組み合わせて使用可能

---

## PR commits (#31)

PR のコミット一覧を取得する。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | ○ | ○ | ○ | ○ | × | × | × |

### APIエンドポイント

- **GitHub**: `GET /repos/{owner}/{repo}/pulls/{number}/commits`
- **GitLab**: `GET /projects/:id/merge_requests/:iid/commits`
- **Bitbucket**: `GET /repositories/{workspace}/{repo}/pullrequests/{id}/commits`
- **Azure DevOps**: `GET /pullrequests/{id}/commits`
- **Gitea/Forgejo**: `GET /repos/{owner}/{repo}/pulls/{index}/commits`

### 実装詳細

- **adapter層**: `BaseAdapter` に `list_pull_request_commits(number)` を追加。SHA・著者・日時・メッセージのリストを返す
- **command層**: `commands/pr.py` に `commits` サブコマンドを追加

---

## PR requested reviewers (#29)

レビュアーのリクエスト（追加・削除・一覧取得）。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | △ | △ | ○ | ○ | ○ | × | × | × |

### APIエンドポイント

- **GitHub**: `GET/POST/DELETE /repos/{owner}/{repo}/pulls/{number}/requested_reviewers`
- **GitLab**: MR 作成/更新時に `reviewer_ids` で設定。個別追加/削除は PUT で `reviewer_ids` 全体更新
- **Bitbucket**: PR 作成/更新時に `reviewers` 配列で設定。個別追加/削除の専用エンドポイントなし
- **Azure DevOps**: `GET/PUT/DELETE /pullrequests/{id}/reviewers/{reviewerId}`
- **Gitea/Forgejo**: `POST/DELETE /repos/{owner}/{repo}/pulls/{index}/requested_reviewers`

### 実装詳細

- **adapter層**: `BaseAdapter` に `request_reviewers(number, reviewers)` / `remove_reviewers(number, reviewers)` を追加
- **command層**: `commands/pr.py` の `create` / `update` に `--reviewer` オプションを追加、または独立した `pr reviewers add/remove/list` サブコマンドとして実装

---

## PR update branch (#32)

ベースブランチを head にマージして PR ブランチを最新化する。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | × | × | ○ | ○ | × | × | × |

### APIエンドポイント

- **GitHub**: `PUT /repos/{owner}/{repo}/pulls/{number}/update-branch`
- **GitLab**: `PUT /projects/:id/merge_requests/:iid/rebase`（rebase 方式）
- **Gitea/Forgejo**: `POST /repos/{owner}/{repo}/pulls/{index}/update`

### 実装詳細

- **adapter層**: `BaseAdapter` に `update_pull_request_branch(number)` を追加
- **command層**: `commands/pr.py` に `update-branch` サブコマンドを追加。GitLab の場合は rebase 方式である旨を出力に含める

---

## PR auto-merge (#47)

CI パス後の自動マージを設定する。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | × | ○ | ○ | ○ | × | × | × |

### APIエンドポイント

- **GitHub**: `PUT /repos/{owner}/{repo}/pulls/{number}/merge` の `merge_method` + GraphQL `enablePullRequestAutoMerge`
- **GitLab**: `PUT /projects/:id/merge_requests/:iid/merge` に `merge_when_pipeline_succeeds=true`
- **Azure DevOps**: PR の `autoCompleteSetBy` フィールドを設定
- **Gitea/Forgejo**: `POST /repos/{owner}/{repo}/pulls/{index}/merge` に `Do` + `merge_when_checks_succeed` パラメータ

### 実装方針

「CI が通ったら自動マージ」は日常的に使う機能。`gfo pr merge --auto` として実装可能。

### 実装詳細

- **adapter層**: `BaseAdapter` に `enable_auto_merge(number, merge_method=None)` を追加
- **command層**: 既存の `pr merge` コマンドに `--auto` フラグを追加。GitHub の場合は GraphQL mutation が必要な点に注意

---

## PR review dismiss (#48)

レビューの却下/取り消し。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | × | × | ○ | ○ | ○ | × | × | × |

### APIエンドポイント

- **GitHub**: `PUT /repos/{owner}/{repo}/pulls/{number}/reviews/{review_id}/dismissals`
- **Azure DevOps**: Reviewer の vote をリセット
- **Gitea/Forgejo**: `POST /repos/{owner}/{repo}/pulls/{index}/reviews/{id}/dismissals`

### 実装詳細

- **adapter層**: `BaseAdapter` に `dismiss_review(number, review_id, message=None)` を追加
- **command層**: 既存の review コマンドに `dismiss` サブコマンドを追加。引数は PR 番号とレビュー ID。`--message` で却下理由を指定可能

---

## PR ready (#18)

ドラフト PR を通常 PR に変更する。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| △ | ○ | ○ | △ | ○ | ○ | × | × | × |

### APIエンドポイント

- **GitHub**: REST API では不可。**GraphQL** の `markPullRequestReadyForReview` mutation が必要
- **GitLab**: タイトルから `Draft:` プレフィックスを除去する PUT で対応
- **Bitbucket**: `PUT /pullrequests/{id}` に `{"draft":false}`
- **Azure DevOps**: `isDraft` が公式の更新可能プロパティに含まれていない。CLI では対応しているため要検証
- **Gitea/Forgejo**: state 変更で対応可能。バージョンにより `unset_draft` が必要な場合あり

### 実装詳細

- **adapter層**: `BaseAdapter` に `mark_pull_request_ready(number)` を追加。GitHub は GraphQL が必要なため、`http.py` に GraphQL 呼び出し機能の追加が前提となる可能性あり
- **command層**: `commands/pr.py` に `ready` サブコマンドを追加。引数は PR 番号のみ
