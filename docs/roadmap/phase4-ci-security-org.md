# 第4弾: CI / セキュリティ / 組織

## TODO

1. [x] **GPG Key 管理** (#14) — GPG Key の list/create/delete。5サービス対応可能
2. [x] **CI trigger** (#15) — パイプラインの手動トリガー。6サービス対応可能
3. [x] **CI retry** (#16) — 失敗パイプラインの再実行。6サービス対応可能
4. [x] **CI logs** (#17) — パイプラインのログ取得。6サービス対応可能
5. [x] **Tag protections** (#43) — タグ保護ルールの管理。4サービス対応可能
6. [x] **Org create / delete** (#26) — 組織の作成・削除。8サービス対応可能
7. [x] **Repo migrate** (#24) — 外部リポジトリのインポート/移行。6サービス対応可能
8. [x] **Issue templates** (#50) — Issue テンプレートの一覧取得。5サービス対応可能

---

## GPG Key 管理 (#14)

GPG Key の一覧取得・作成・削除。SSH Key 管理と対になる機能。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | ○ | × | ○ | ○ | × | × | × |

### APIエンドポイント

- **GitHub**: `GET/POST /user/gpg_keys`, `DELETE /user/gpg_keys/{id}`
- **GitLab**: `GET/POST /user/gpg_keys`, `DELETE /user/gpg_keys/:id`
- **Bitbucket**: `GET/POST /users/{user}/gpg-keys`, `DELETE .../gpg-keys/{fingerprint}`
- **Azure DevOps**: GPG Key 管理 API なし
- **Gitea/Forgejo**: `GET/POST /user/gpg_keys`, `DELETE /user/gpg_keys/{id}`

### 実装詳細

- **adapter層**: `BaseAdapter` に `list_gpg_keys()` / `create_gpg_key(armored_public_key)` / `delete_gpg_key(key_id)` を追加。既存の SSH Key 管理（`ssh-key` コマンド）と同じパターン
- **command層**: `commands/gpg_key.py` を新規作成。`gfo gpg-key list/add/delete` サブコマンド

---

## CI trigger (#15)

パイプライン/ワークフローを手動でトリガーする。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | ○ | ○ | ○ | ○ | × | × | × |

### APIエンドポイント

- **GitHub**: `POST /actions/workflows/{id}/dispatches`（workflow_dispatch イベント）
- **GitLab**: `POST /projects/:id/pipeline` または `POST /trigger/pipeline`
- **Bitbucket**: `POST /pipelines/` に target 指定
- **Azure DevOps**: `POST /pipelines/{id}/runs` または `POST /build/builds`
- **Gitea**: `POST /actions/workflows/{workflowname}/dispatches`（Gitea 1.24+）
- **Forgejo**: 同上

### 実装詳細

- **adapter層**: `BaseAdapter` に `trigger_ci(workflow_id=None, ref=None, inputs=None)` を追加。GitHub/Gitea は workflow 指定、GitLab/Bitbucket/Azure DevOps は ref 指定
- **command層**: 既存の CI コマンドに `trigger` / `run` サブコマンドを追加。`--ref`, `--workflow`, `--input key=value` オプション

---

## CI retry (#16)

失敗したパイプラインを再実行する。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | △ | ○ | ○ | △ | × | × | × |

### APIエンドポイント

- **GitHub**: `POST /actions/runs/{id}/rerun` または `POST .../rerun-failed-jobs`
- **GitLab**: `POST /pipelines/:id/retry`
- **Bitbucket**: 新パイプライン作成で代用推奨。ステップ単位の rerun は限定的
- **Azure DevOps**: `PATCH /build/builds/{id}?retry=true`
- **Gitea**: `POST /actions/runs/{run}/rerun`
- **Forgejo**: rerun API の実装状況はバージョン依存

### 実装詳細

- **adapter層**: `BaseAdapter` に `retry_ci(run_id)` を追加
- **command層**: 既存の CI コマンドに `retry` サブコマンドを追加。`--failed-only` オプション（GitHub の `rerun-failed-jobs` に対応）

---

## CI logs (#17)

パイプラインのログを取得する。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | ○ | ○ | ○ | △ | × | × | × |

### APIエンドポイント

- **GitHub**: `GET /actions/runs/{id}/logs`（zip）または `GET /actions/jobs/{id}/logs`
- **GitLab**: `GET /jobs/:id/trace`（テキスト）
- **Bitbucket**: `GET /pipelines/{uuid}/steps/{uuid}/logs/{uuid}`
- **Azure DevOps**: `GET /build/builds/{id}/logs/{logId}`
- **Gitea**: `GET /actions/runs/{run}/jobs/{job_id}/logs`
- **Forgejo**: Gitea に準ずるがバージョン依存

### 実装詳細

- **adapter層**: `BaseAdapter` に `get_ci_logs(run_id, job_id=None)` を追加。GitHub は zip 形式なので展開処理が必要
- **command層**: 既存の CI コマンドに `logs` サブコマンドを追加。`--job` でジョブ指定、デフォルトは全ジョブのログ

---

## Tag protections (#43)

タグ保護ルールの管理（一覧・作成・削除・更新）。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| △ | ○ | × | × | ○ | ○ | × | × | × |

### APIエンドポイント

- **GitHub**: Tags Protection API あり。ただし 2024年8月に廃止予定、Repository Rulesets への移行推奨
- **GitLab**: `GET/POST/DELETE /projects/:id/protected_tags`
- **Gitea/Forgejo**: `GET/POST/DELETE/PATCH /repos/{owner}/{repo}/tag_protections`

### 実装方針

branch-protect と対になる機能。GitHub の廃止予定が懸念だが GitLab/Gitea/Forgejo では安定。

### 実装詳細

- **adapter層**: `BaseAdapter` に `list_tag_protections()` / `create_tag_protection(pattern, ...)` / `delete_tag_protection(id)` を追加
- **command層**: `commands/tag_protect.py` を新規作成。`gfo tag-protect list/create/delete` サブコマンド。既存の `branch-protect` コマンドと同様のパターン

---

## Org create / delete (#26)

組織の作成・削除。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| △ | ○ | △ | △ | ○ | ○ | ○ | ○ | × |

### APIエンドポイント

- **GitHub**: `POST /user/orgs` で作成可能だが、削除は `DELETE /orgs/{org}` で管理者権限が必要
- **GitLab**: `POST /groups`（作成）/ `DELETE /groups/:id`（削除）
- **Bitbucket**: `POST /teams`（旧API）/ Workspace は API では作成不可
- **Azure DevOps**: Organization は REST API での作成に制限あり
- **Gitea/Forgejo/Gogs**: `POST /orgs`（作成）/ `DELETE /orgs/{org}`（削除）
- **GitBucket**: `POST /orgs`（作成）/ `DELETE /orgs/{org}`（削除）

### 実装方針

gfo には既に `org list/view/members/repos` があるが、create/delete がない。Gitea ファミリーと GitLab では実装が容易。

### 実装詳細

- **adapter層**: `BaseAdapter` に `create_organization(name, description=None, ...)` / `delete_organization(org_name)` を追加
- **command層**: 既存の `commands/org.py`（あれば）に `create` / `delete` サブコマンドを追加。delete は確認プロンプト付き

---

## Repo migrate (#24)

外部リポジトリのインポート/移行。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | ○ | ○ | ○ | ○ | × | × | × |

### APIエンドポイント

- **GitHub**: `POST /repos/{owner}/import`（Source Import API）
- **GitLab**: `POST /projects/import`（Project Import API）
- **Bitbucket**: リポジトリ作成時に外部からのインポートオプションあり
- **Azure DevOps**: Import Requests API (`POST /git/repositories/{repositoryId}/importRequests`)
- **Gitea/Forgejo**: `POST /repos/migrate`（ソースサービス指定可。Issue/PR/Wiki/Label/Release も移行可能）

### 実装方針

Gitea/Forgejo の migrate API は Issue/PR/Release 等のメタデータも移行できる点で特に強力。マルチサービス対応の gfo ならではのサービス間移行支援に活用できる。

### 実装詳細

- **adapter層**: `BaseAdapter` に `migrate_repository(clone_url, repo_name, mirror=False, ...)` を追加。Gitea/Forgejo はメタデータ移行オプション対応
- **command層**: `commands/repo.py` に `migrate` サブコマンドを追加。`--from-url`, `--mirror`, `--issues`, `--labels` 等のオプション

---

## Issue templates (#50)

Issue テンプレートの一覧を取得する。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | × | ○ | ○ | ○ | × | × | × |

### APIエンドポイント

- **GitHub**: `.github/ISSUE_TEMPLATE/` をファイル API で取得、または Issue Forms API
- **GitLab**: `GET /projects/:id/templates/issues`（merge_request templates API も存在するが gfo コマンドとしては Issue テンプレートのみ対象）
- **Azure DevOps**: Work Item Types API でテンプレート情報取得可能
- **Gitea/Forgejo**: `GET /repos/{owner}/{repo}/issue_templates`

### 実装詳細

- **adapter層**: `BaseAdapter` に `list_issue_templates()` を追加。テンプレート名・説明・本文のリストを返す
- **command層**: `commands/issue.py` に `templates` サブコマンドを追加。Issue 作成時にテンプレートを選択できると便利
