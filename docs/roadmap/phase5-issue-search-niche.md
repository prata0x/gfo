# 第5弾: Issue拡張 / 検索 / ニッチ機能

## TODO

1. [ ] **Issue reactions** (#33) — リアクション/絵文字の追加・削除。4サービス対応可能
2. [ ] **Issue dependencies** (#41) — Issue 間の依存関係管理。4サービス対応可能
3. [ ] **Issue timeline** (#44) — Issue のイベントタイムライン取得。5サービス対応可能
4. [ ] **Issue pin / unpin** (#40) — Issue のピン留め。3サービス対応可能
5. [ ] **Search PRs** (#20) — PR 検索。6サービス対応可能
6. [ ] **Search commits** (#21) — コミット検索。4サービス対応可能
7. [ ] **Label clone** (#19) — 他リポジトリからラベルをコピー。6サービス対応可能
8. [ ] **Package management** (#39) — パッケージの一覧・詳細・削除。5サービス対応可能
9. [ ] **タイムトラッキング** (#23) — Issue の作業時間記録。5サービス対応可能
10. [ ] **Push mirrors** (#45) — リポジトリのプッシュミラー管理。3サービス対応可能
11. [ ] **Repo mirror sync** (#53) — ミラーリポジトリの同期トリガー。3サービス対応可能
12. [ ] **Repo transfer** (#38) — リポジトリの所有権移譲。4サービス対応可能
13. [ ] **Repo star / unstar** (#28) — リポジトリのスター操作。5サービス対応可能
14. [ ] **Wiki revisions** (#46) — Wiki ページのリビジョン履歴取得。2サービス対応可能

---

## Issue reactions (#33)

Issue やコメントにリアクション（絵文字）を追加・削除する。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | × | × | ○ | ○ | × | × | × |

### APIエンドポイント

- **GitHub**: `GET/POST/DELETE /repos/{owner}/{repo}/issues/{number}/reactions`
- **GitLab**: Award Emoji API: `GET/POST/DELETE /projects/:id/issues/:iid/award_emoji`
- **Gitea/Forgejo**: `GET/POST/DELETE /repos/{owner}/{repo}/issues/{index}/reactions`

### 実装詳細

- **adapter層**: `BaseAdapter` に `list_issue_reactions(number)` / `add_issue_reaction(number, reaction)` / `remove_issue_reaction(number, reaction)` を追加。コメントのリアクションにも対応
- **command層**: `commands/issue.py` に `reaction add/remove/list` サブコマンドを追加

---

## Issue dependencies (#41)

Issue 間の依存関係（depends on / blocks）を管理する。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| × | △ | × | ○ | ○ | ○ | × | × | × |

### APIエンドポイント

- **GitLab**: Issue Links API: `GET/POST/DELETE /projects/:id/issues/:iid/links`（Premium 以上）
- **Azure DevOps**: Work Item Links で dependency 関係を設定
- **Gitea/Forgejo**: `GET/POST/DELETE /repos/{owner}/{repo}/issues/{index}/dependencies` + `/blocks`

### 実装詳細

- **adapter層**: `BaseAdapter` に `list_issue_dependencies(number)` / `add_issue_dependency(number, depends_on)` / `remove_issue_dependency(number, depends_on)` を追加
- **command層**: `commands/issue.py` に `depends add/remove/list` サブコマンドを追加

---

## Issue timeline (#44)

Issue のイベントタイムライン（ラベル変更、担当者変更、状態変更等）を取得する。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | △ | × | ○ | ○ | ○ | × | × | × |

### APIエンドポイント

- **GitHub**: `GET /repos/{owner}/{repo}/issues/{number}/timeline`
- **GitLab**: 統一タイムラインなし。`resource_state_events`, `resource_label_events` 等が個別に存在
- **Azure DevOps**: Work Item Updates: `GET /wit/workitems/{id}/updates`
- **Gitea/Forgejo**: `GET /repos/{owner}/{repo}/issues/{index}/timeline`

### 実装詳細

- **adapter層**: `BaseAdapter` に `get_issue_timeline(number)` を追加。イベント種別・日時・ユーザー・詳細のリストを返す
- **command層**: `commands/issue.py` に `timeline` サブコマンドを追加。時系列順でイベントを表示

---

## Issue pin / unpin (#40)

Issue をピン留め/解除する。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | × | × | × | ○ | ○ | × | × | × |

### APIエンドポイント

- **GitHub**: `POST/DELETE /repos/{owner}/{repo}/issues/{number}/pin`
- **Gitea/Forgejo**: `POST/DELETE /repos/{owner}/{repo}/issues/{index}/pin` + 位置変更 API

### 実装詳細

- **adapter層**: `BaseAdapter` に `pin_issue(number)` / `unpin_issue(number)` を追加
- **command層**: `commands/issue.py` に `pin` / `unpin` サブコマンドを追加

---

## Search PRs (#20)

PR を検索する。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | △ | ○ | ○ | ○ | × | × | △ |

### APIエンドポイント

- **GitHub**: `GET /search/issues?q=type:pr+{query}`
- **GitLab**: `GET /merge_requests?search={query}`
- **Bitbucket**: `q` パラメータ（Bitbucket Query Language）でフィルタ可能。全文検索不可
- **Azure DevOps**: `searchCriteria` パラメータでフィルタリング検索
- **Gitea/Forgejo**: `GET /pulls` に state, labels, milestone 等でフィルタ
- **Backlog**: `statusId[]`, `assigneeId[]` 等でフィルタ可能。キーワード検索なし

### 実装詳細

- **adapter層**: `BaseAdapter` に `search_pull_requests(query, state=None, labels=None, ...)` を追加
- **command層**: 既存の search コマンドに `prs` サブコマンドを追加。`gfo search prs "keyword"` の形式

---

## Search commits (#21)

コミットを検索する。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | △ | △ | △ | △ | × | × | × |

### APIエンドポイント

- **GitHub**: `GET /search/commits?q={query}`
- **GitLab**: `GET /repository/commits?search={query}`（メッセージ検索）
- **Bitbucket**: コミット一覧取得のみ。メッセージ検索パラメータは限定的
- **Azure DevOps**: author, fromDate, toDate, itemPath でフィルタ可能。メッセージテキスト検索なし
- **Gitea/Forgejo**: コミット一覧取得可能だがメッセージ全文検索の専用パラメータなし

### 実装詳細

- **adapter層**: `BaseAdapter` に `search_commits(query=None, author=None, since=None, until=None)` を追加
- **command層**: 既存の search コマンドに `commits` サブコマンドを追加

---

## Label clone (#19)

他リポジトリからラベルをコピーする。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | × | △ | ○ | ○ | × | △ | × |

### 実装方針

専用 API はどのサービスにもない。**list + create** の組み合わせで gfo コマンド層に実装。Azure DevOps の Tags は名前のみ（色・説明なし）かつプロジェクト単位共有。GitBucket は Label List/Create API があるため組み合わせで可能。

### 実装詳細

- **adapter層**: 新規メソッド不要。既存の `list_labels()` + `create_label()` を組み合わせ
- **command層**: `commands/label.py` に `clone` サブコマンドを追加。`gfo label clone --from owner/repo` の形式。重複ラベルはスキップまたは `--overwrite` オプション

---

## Package management (#39)

パッケージの一覧・詳細・削除。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | × | ○ | ○ | ○ | × | × | × |

### APIエンドポイント

- **GitHub**: `GET/DELETE /orgs/{org}/packages/{type}/{name}` 等
- **GitLab**: `GET/DELETE /projects/:id/packages/:package_id` 等
- **Azure DevOps**: Azure Artifacts API: `GET /packaging/feeds/{feedId}/packages` 等
- **Gitea/Forgejo**: `GET /packages/{owner}`, `GET/DELETE /packages/{owner}/{type}/{name}/{version}`

### 実装詳細

- **adapter層**: `BaseAdapter` に `list_packages(type=None)` / `get_package(type, name, version=None)` / `delete_package(type, name, version)` を追加
- **command層**: `commands/package.py` を新規作成。`gfo package list/view/delete` サブコマンド

---

## タイムトラッキング (#23)

Issue の作業時間記録。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| × | ○ | × | △ | ○ | ○ | × | × | ○ |

### APIエンドポイント

- **GitLab**: `POST /projects/:id/issues/:iid/add_spent_time`, `GET /projects/:id/issues/:iid/time_stats`
- **Azure DevOps**: Work Item の `Completed Work` / `Remaining Work` フィールドで管理。専用タイマーAPIはない
- **Gitea/Forgejo**: `GET/POST/DELETE /repos/{owner}/{repo}/issues/{index}/times`
- **Backlog**: `GET /issues/{issueIdOrKey}/actualHours`（実績工数）等で管理可能

### 実装詳細

- **adapter層**: `BaseAdapter` に `list_time_entries(issue_number)` / `add_time_entry(issue_number, duration)` / `delete_time_entry(issue_number, entry_id)` を追加
- **command層**: `commands/issue.py` に `time list/add/delete` サブコマンドを追加。`gfo issue time add 42 1h30m` の形式

---

## Push mirrors (#45)

リポジトリのプッシュミラーを管理する。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| × | ○ | × | × | ○ | ○ | × | × | × |

### APIエンドポイント

- **GitLab**: `GET/POST/PUT/DELETE /projects/:id/remote_mirrors`
- **Gitea/Forgejo**: `GET/POST /repos/{owner}/{repo}/push_mirrors`, `DELETE /push_mirrors/{name}`, `POST /push_mirrors-sync`

### 実装詳細

- **adapter層**: `BaseAdapter` に `list_push_mirrors()` / `create_push_mirror(remote_url, ...)` / `delete_push_mirror(mirror_id)` を追加
- **command層**: `commands/repo.py` に `mirror list/add/remove/sync` サブコマンドグループを追加

---

## Repo mirror sync (#53)

ミラーリポジトリの同期をトリガーする。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| × | ○ | × | × | ○ | ○ | × | × | × |

### APIエンドポイント

- **GitLab**: `POST /projects/:id/mirror/pull`（プルミラー同期）
- **Gitea/Forgejo**: `POST /repos/{owner}/{repo}/mirror-sync`

### 実装方針

#45 Push mirrors と合わせてミラー管理機能として実装。3 サービスで対応可能。

### 実装詳細

- **adapter層**: `BaseAdapter` に `sync_mirror()` を追加
- **command層**: #45 の `mirror sync` サブコマンドとして実装

---

## Repo transfer (#38)

リポジトリの所有権を移譲する。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | × | × | ○ | ○ | × | × | × |

### APIエンドポイント

- **GitHub**: `POST /repos/{owner}/{repo}/transfer`
- **GitLab**: `PUT /projects/:id/transfer`
- **Gitea/Forgejo**: `POST /repos/{owner}/{repo}/transfer` + accept/reject エンドポイント

### 実装詳細

- **adapter層**: `BaseAdapter` に `transfer_repository(new_owner, team_ids=None)` を追加。Forgejo は accept/reject の明示的な API を持つ
- **command層**: `commands/repo.py` に `transfer` サブコマンドを追加。確認プロンプト付き

---

## Repo star / unstar (#28)

リポジトリのスター操作。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | × | × | ○ | ○ | ○ | × | × |

### APIエンドポイント

- **GitHub**: `PUT /user/starred/{owner}/{repo}` / `DELETE /user/starred/{owner}/{repo}`
- **GitLab**: `POST /projects/:id/star` / `POST /projects/:id/unstar`
- **Gitea/Forgejo/Gogs**: `PUT /user/starred/{owner}/{repo}` / `DELETE /user/starred/{owner}/{repo}`

### 実装詳細

- **adapter層**: `BaseAdapter` に `star_repository()` / `unstar_repository()` を追加
- **command層**: `commands/repo.py` に `star` / `unstar` サブコマンドを追加

---

## Wiki revisions (#46)

Wiki ページのリビジョン履歴を取得する。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| × | × | × | × | ○ | ○ | × | × | × |

### APIエンドポイント

- **Gitea/Forgejo**: `GET /repos/{owner}/{repo}/wiki/revisions/{pageName}`

### 実装詳細

- **adapter層**: `BaseAdapter` に `list_wiki_revisions(page_name)` を追加
- **command層**: 既存の wiki コマンドに `revisions` サブコマンドを追加。Gitea/Forgejo のみ対応
