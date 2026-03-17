# 第1弾: 既存コマンドの補完（実装コスト低・効果大）

## TODO

1. [ ] **PR reopen** (#1) — closed PR を再オープン。8サービス対応可能
2. [ ] **Issue reopen** (#2) — closed Issue を再オープン。7サービス対応可能
3. [ ] **Label update** (#9) — ラベル名・色・説明の変更。6サービス対応可能
4. [ ] **Milestone update** (#10) — マイルストーン情報の更新。7サービス対応可能
5. [ ] **Milestone view** (#11) — マイルストーン詳細取得。7サービス対応可能
6. [ ] **Release view** (#5) — リリース詳細取得。6サービス対応可能
7. [ ] **Release update** (#6) — リリース情報の更新。5サービス対応可能
8. [ ] **Milestone close / reopen** (#25) — マイルストーンの状態変更。7サービス対応可能
9. [ ] **Webhook test** (#42) — Webhook のテスト送信。5サービス対応可能

---

## PR reopen (#1)

closed PR を再オープンする。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | ○ | ○ | ○ | ○ | × | ○ | △ |

### APIエンドポイント

- **GitHub**: `PATCH /repos/{owner}/{repo}/pulls/{number}` に `{"state":"open"}`
- **GitLab**: `PUT /projects/:id/merge_requests/:iid` に `{"state_event":"reopen"}`
- **Bitbucket**: `PUT /2.0/repositories/{workspace}/{repo}/pullrequests/{id}` に `{"state":"OPEN"}`
- **Azure DevOps**: `PATCH /pullRequests/{id}` に `{"status":"active"}`
- **Gitea/Forgejo**: `PATCH /repos/{owner}/{repo}/pulls/{index}` に `{"state":"open"}`
- **Gogs**: PR API 自体が未実装
- **GitBucket**: GitHub 互換 `PATCH /pulls/{number}` に `{"state":"open"}`
- **Backlog**: `statusId` による変更は公式ドキュメント外だが既存実装で動作実績あり

### 実装方針

既存の `close_pull_request` と対になるメソッド。大半のサービスは update API で state を変更するだけ。

### 実装詳細

- **adapter層**: `BaseAdapter` に `reopen_pull_request(number)` を追加。各アダプターで既存の update/patch エンドポイントを使い state を変更
- **command層**: `commands/pr.py` に `reopen` サブコマンドを追加。引数は PR 番号のみ

---

## Issue reopen (#2)

closed Issue を再オープンする。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | △ | △ | ○ | ○ | △ | × | ○ |

### APIエンドポイント

- **GitHub**: `PATCH /repos/{owner}/{repo}/issues/{number}` に `{"state":"open"}`
- **GitLab**: `PUT /projects/:id/issues/:iid` に `{"state_event":"reopen"}`
- **Bitbucket**: Issue Tracker 有効化が前提。2026年8月に API 廃止予定
- **Azure DevOps**: Work Items の `System.State` を PATCH。遷移先がプロセステンプレートにより異なる
- **Gitea/Forgejo**: `PATCH /repos/{owner}/{repo}/issues/{index}` に `{"state":"open"}`
- **Gogs**: Issue PATCH は存在するが reopen の動作は未検証
- **GitBucket**: Issue PATCH 自体が未実装
- **Backlog**: `PATCH /issues/{issueIdOrKey}` に `statusId` パラメータで変更可能

### 実装詳細

- **adapter層**: `BaseAdapter` に `reopen_issue(number)` を追加。PR reopen と同様、update API で state 変更
- **command層**: `commands/issue.py` に `reopen` サブコマンドを追加

---

## Label update (#9)

ラベル名・色・説明の変更。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | × | △ | ○ | ○ | × | ○ | × |

### APIエンドポイント

- **GitHub**: `PATCH /labels/{name}`
- **GitLab**: `PUT /labels/:label_id`
- **Bitbucket**: ラベル機能なし
- **Azure DevOps**: Tags は名前のみ（色・説明なし）。`PATCH /wit/tags/{tagId}` で名前変更のみ可能
- **Gitea/Forgejo**: `PATCH /labels/{id}`（name, color, description 変更可）
- **Gogs**: Label API 未実装
- **GitBucket**: GitHub 互換 Label CRUD 実装済み

### 実装詳細

- **adapter層**: `BaseAdapter` に `update_label(label_id, name=None, color=None, description=None)` を追加
- **command層**: `commands/label.py` に `update` サブコマンドを追加。`--name`, `--color`, `--description` オプション

---

## Milestone update (#10)

マイルストーン情報の更新。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | × | ○ | ○ | ○ | × | ○ | ○ |

### APIエンドポイント

- **GitHub**: `PATCH /milestones/{number}`
- **GitLab**: `PUT /milestones/:milestone_id`
- **Bitbucket**: Milestone は読み取り専用。2026年8月に廃止予定
- **Azure DevOps**: `PATCH /wit/classificationnodes/Iterations/{path}`
- **Gitea/Forgejo**: `PATCH /milestones/{id}`
- **GitBucket**: Milestone CRUD 完全対応（v4.35.0+）
- **Backlog**: `PATCH /projects/{projectIdOrKey}/versions/{id}`

### 実装詳細

- **adapter層**: `BaseAdapter` に `update_milestone(milestone_id, title=None, description=None, due_date=None)` を追加
- **command層**: `commands/milestone.py` に `update` サブコマンドを追加

---

## Milestone view (#11)

マイルストーン詳細取得。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | × | ○ | ○ | ○ | × | ○ | △ |

### APIエンドポイント

- **Backlog**: 単一マイルストーン取得の専用エンドポイントがドキュメント未記載。リスト取得からフィルタで代用

### 実装詳細

- **adapter層**: `BaseAdapter` に `get_milestone(milestone_id)` を追加。大半のサービスは `GET /milestones/{id}` で取得可能
- **command層**: `commands/milestone.py` に `view` サブコマンドを追加。マイルストーン番号/ID を引数に取る

---

## Release view (#5)

リリース詳細取得。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | × | △ | ○ | ○ | × | △ | × |

### APIエンドポイント

- **GitHub**: `GET /releases/{id}` または `GET /releases/tags/{tag}`
- **GitLab**: `GET /releases/:tag_name`
- **Bitbucket**: リリース機能なし
- **Azure DevOps**: Release はデプロイメント定義であり GitHub Releases とはデータモデルが異なる
- **Gitea/Forgejo**: `GET /releases/{id}` および `GET /releases/tags/{tag}`
- **Gogs**: Release API 未実装
- **GitBucket**: `GET /releases` でリスト取得は可能。単一取得の明確なドキュメントなし
- **Backlog**: Release の概念なし

### 実装詳細

- **adapter層**: `BaseAdapter` に `get_release(tag_or_id)` を追加。タグ名でもID でも取得可能にする
- **command層**: `commands/release.py` に `view` サブコマンドを追加。引数はタグ名またはリリース ID

---

## Release update (#6)

リリース情報の更新。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | × | △ | ○ | ○ | × | × | × |

### APIエンドポイント

- **GitHub**: `PATCH /releases/{id}`（title, body, draft, prerelease 変更）
- **GitLab**: `PUT /releases/:tag_name`（name, description, milestones 変更）
- **Gitea/Forgejo**: `PATCH /releases/{id}`

### 実装詳細

- **adapter層**: `BaseAdapter` に `update_release(release_id, title=None, body=None, draft=None, prerelease=None)` を追加
- **command層**: `commands/release.py` に `update` サブコマンドを追加。`--title`, `--body`, `--draft`, `--prerelease` オプション

---

## Milestone close / reopen (#25)

マイルストーンの状態変更。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | × | ○ | ○ | ○ | × | ○ | ○ |

### APIエンドポイント

- **GitHub**: `PATCH /milestones/{number}` に `{"state":"open"}` / `{"state":"closed"}`
- **GitLab**: `PUT /milestones/:id` に `{"state_event":"close"}` / `{"state_event":"activate"}`
- **Gitea/Forgejo**: `PATCH /milestones/{id}` に `{"state":"open"}` / `{"state":"closed"}`
- **Azure DevOps**: Classification Nodes の属性で管理
- **GitBucket**: Milestone CRUD 対応（v4.35.0+）
- **Backlog**: `PATCH /versions/{id}` に `{"archived":true}` でアーカイブ（close 相当）

### 実装方針

gfo の既存 `milestone` コマンドに `close` / `reopen` サブコマンドを追加。

### 実装詳細

- **adapter層**: `BaseAdapter` に `close_milestone(milestone_id)` / `reopen_milestone(milestone_id)` を追加。または `update_milestone` の state パラメータで統一
- **command層**: `commands/milestone.py` に `close` / `reopen` サブコマンドを追加

---

## Webhook test (#42)

Webhook のテスト送信。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | × | × | ○ | ○ | ○ | × | × |

### APIエンドポイント

- **GitHub**: `POST /repos/{owner}/{repo}/hooks/{hook_id}/pings` / `POST .../tests`
- **GitLab**: `POST /projects/:id/hooks/:hook_id/test/:trigger`
- **Gitea/Forgejo/Gogs**: `POST /repos/{owner}/{repo}/hooks/{id}/tests`

### 実装詳細

- **adapter層**: `BaseAdapter` に `test_webhook(hook_id)` を追加
- **command層**: 既存の webhook コマンドに `test` サブコマンドを追加。引数は Webhook ID
