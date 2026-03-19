# gfo 実装 TODO

`docs/issues.md` の課題を変更ファイル単位でグループ化した実装計画。

---

## 1. CLI 層のみ（アダプター変更なし）

**課題**: A1, B4-1, B1-1
**変更ファイル**: `cli.py`, `commands/pr.py`, `commands/release.py`, `commands/label.py`

### A1: `label edit --name` エイリアス

`cli.py` の `label edit` パーサーに `--name` を `--new-name` のエイリアスとして追加。

```python
# cli.py label edit セクション
label_edit.add_argument("--new-name", "--name", ...)
```

### B4-1: `release create --notes-file`

`cli.py` に `--notes-file` 引数追加。`commands/release.py` の `handle_create` でファイル読み込み→ `args.notes` に代入。

```python
# cli.py
release_create.add_argument("--notes-file", type=argparse.FileType("r"))

# commands/release.py handle_create()
if args.notes_file:
    args.notes = args.notes_file.read()
```

### B1-1: `pr merge --delete-branch`

`cli.py` に `--delete-branch` / `-d` フラグ追加。`commands/pr.py` の `handle_merge` でマージ成功後に `adapter.delete_branch()` を呼ぶ。

```python
# commands/pr.py handle_merge()
adapter.merge_pull_request(args.number, method=method)
if args.delete_branch:
    pr = adapter.get_pull_request(args.number)
    adapter.delete_branch(pr.head)  # head ブランチ名を取得して削除
```

**テスト**: `tests/test_commands/test_pr.py` に `--delete-branch` のテスト追加。`responses` で merge + delete_branch の 2 リクエストをモック。

---

## 2. `pr list` フィルタ拡張

**課題**: B5-1〜B5-7
**変更ファイル**: `adapter/base.py`, `adapter/*.py` (全 9), `commands/pr.py`, `cli.py`

### base.py シグネチャ変更

```python
# 現在
def list_pull_requests(self, *, state: str = "open", limit: int = 30) -> list[PullRequest]:

# 変更後
def list_pull_requests(
    self, *, state: str = "open", limit: int = 30,
    author: str | None = None,       # B5-1
    label: str | None = None,        # B5-2
    assignee: str | None = None,     # B5-3
    search: str | None = None,       # B5-4
    base: str | None = None,         # B5-5
    head: str | None = None,         # B5-6
    draft: bool | None = None,       # B5-7
) -> list[PullRequest]:
```

全パラメータをオプショナル (`None`) にし、既存アダプターはデフォルト値で後方互換を維持。

### 各アダプターの実装

| サービス | author | label | assignee | search | base | head | draft |
|---|---|---|---|---|---|---|---|
| GitHub | `?creator=` | `?labels=` | `?assignee=` | Search API | `?base=` | `?head=` | GraphQL のみ |
| GitLab | `?author_username=` | `?labels=` | `?assignee_username=` | `?search=` | `?target_branch=` | `?source_branch=` | `?wip=` |
| Bitbucket | `?q=author.username` | — | — | `?q=` | `?q=destination.branch` | `?q=source.branch` | — |
| Azure DevOps | `?searchCriteria.creatorId=` | `?searchCriteria.labelId=` | `?searchCriteria.reviewerId=` | — | `?searchCriteria.targetRefName=` | `?searchCriteria.sourceRefName=` | — |
| Gitea/Forgejo | `?poster=` | `?labels=` | `?assignee=` | `?q=` | `?base=` | `?head=` | — |
| Gogs | — | — | — | — | — | — | — |
| GitBucket | — | — | — | — | — | — | — |
| Backlog | — | — | — | — | — | — | — |

### cli.py 変更

```python
pr_list.add_argument("--author")
pr_list.add_argument("--label", "-l")
pr_list.add_argument("--assignee", "-a")
pr_list.add_argument("--search", "-S")
pr_list.add_argument("--base", "-B")
pr_list.add_argument("--head", "-H")
pr_list.add_argument("--draft", action="store_true", default=None)
```

**テスト**: 各アダプターの `test_list_pull_requests` に新パラメータのテストケース追加。`responses` でクエリパラメータ検証。

---

## 3. `issue list` / `issue create` フィルタ拡張

**課題**: B3-1〜B3-4
**変更ファイル**: `adapter/base.py`, `adapter/*.py` (全 9), `commands/issue.py`, `cli.py`

### base.py シグネチャ変更

```python
# list_issues: author, milestone, search を追加
def list_issues(
    self, *, state: str = "open", assignee: str | None = None,
    label: str | None = None, limit: int = 30,
    author: str | None = None,       # B3-1
    milestone: str | None = None,    # B3-2
    search: str | None = None,       # B3-3
) -> list[Issue]:

# create_issue: milestone を追加
def create_issue(
    self, *, title: str, body: str = "",
    assignee: str | None = None, label: str | None = None,
    milestone: str | None = None,    # B3-4
    **kwargs,
) -> Issue:
```

### 各アダプターの実装

| サービス | author | milestone | search |
|---|---|---|---|
| GitHub | `?creator=` | `?milestone=` (番号) | Search API |
| GitLab | `?author_username=` | `?milestone=` (タイトル) | `?search=` |
| Bitbucket | — | — | `?q=` |
| Azure DevOps | — | — | — |
| Gitea/Forgejo | `?created_by=` | `?milestones=` (名前) | `?q=` |
| Gogs | — | — | — |
| GitBucket | — | — | — |
| Backlog | — | `?milestoneId[]=` | `?keyword=` |

**注意**: GitHub の milestone フィルタは番号指定。名前→番号変換が必要。`list_milestones()` で名前解決するヘルパーを検討。

---

## 4. `pr edit` / `issue edit` メタデータ拡張

**課題**: B2-1, B2-2, B2-4, B2-5, B2-6, B2-7
**変更ファイル**: `adapter/base.py`, `adapter/*.py` (全 9), `commands/pr.py`, `commands/issue.py`, `cli.py`

### base.py シグネチャ変更

```python
# update_pull_request: add_labels, remove_labels, add_assignees, remove_assignees, milestone を追加
def update_pull_request(
    self, number: int, *, title: str | None = None, body: str | None = None,
    base: str | None = None,
    add_labels: list[str] | None = None,        # B2-1
    remove_labels: list[str] | None = None,      # B2-1
    add_assignees: list[str] | None = None,      # B2-2
    remove_assignees: list[str] | None = None,   # B2-2
    milestone: str | None = None,                # B2-4
) -> PullRequest:

# update_issue: 同様
def update_issue(
    self, number: int, *, title: str | None = None, body: str | None = None,
    assignee: str | None = None, label: str | None = None,
    add_labels: list[str] | None = None,        # B2-5
    remove_labels: list[str] | None = None,      # B2-5
    add_assignees: list[str] | None = None,      # B2-6
    remove_assignees: list[str] | None = None,   # B2-6
    milestone: str | None = None,                # B2-7
) -> Issue:
```

### cli.py 変更

```python
# pr edit
pr_edit.add_argument("--add-label", action="append")
pr_edit.add_argument("--remove-label", action="append")
pr_edit.add_argument("--add-assignee", action="append")
pr_edit.add_argument("--remove-assignee", action="append")
pr_edit.add_argument("--milestone")

# issue edit — 同様
```

### 実装方針

ラベル操作は 2 パターンある:
1. **PATCH 一括更新** (GitHub/GitLab): `update_pull_request()` の body にラベル配列を含める
2. **個別 API** (Gitea/Forgejo): `POST /issues/{index}/labels` + `DELETE /issues/{index}/labels/{id}`

アダプターごとに最適な方式を選択。`add_labels`/`remove_labels` が指定された場合、まず現在のラベルを取得→差分計算→API 呼び出し。

---

## 5. `pr merge` コミットメッセージ

**課題**: B1-2
**変更ファイル**: `adapter/base.py`, `adapter/*.py` (全 9), `commands/pr.py`, `cli.py`

### base.py シグネチャ変更

```python
# 現在
def merge_pull_request(self, number: int, *, method: str = "merge") -> None:

# 変更後
def merge_pull_request(
    self, number: int, *, method: str = "merge",
    title: str | None = None,
    message: str | None = None,
) -> None:
```

### 各アダプターの実装

| サービス | title | message |
|---|---|---|
| GitHub | `commit_title` | `commit_message` |
| GitLab | `merge_commit_message` / `squash_commit_message` | 同上 |
| Bitbucket | `message` | — |
| Azure DevOps | — | `completionOptions.mergeCommitMessage` |
| Gitea/Forgejo | `merge_commit_id`? → `MergePullRequestOption.merge_message_field` | — |
| Gogs | — | — |
| GitBucket | — | — |
| Backlog | — | — |

### cli.py 変更

```python
pr_merge.add_argument("--subject", help=_("Merge commit title"))
pr_merge.add_argument("--body", help=_("Merge commit body"))
```

---

## 6. CRUD 一貫性: view 追加

**課題**: F1-1〜F1-5
**変更ファイル**: `adapter/base.py`, `adapter/*.py`, `commands/repo.py`, `cli.py`

### 6a. `branch view` (F1-1)

base.py に追加:
```python
def get_branch(self, name: str) -> Branch:
    raise NotSupportedError("branch view")
```

各アダプター: `GET /repos/{owner}/{repo}/branches/{branch}`

cli.py: `branch view NAME` サブコマンド登録

出力フィールド: `name`, `commit_sha`, `protected`

### 6b. `tag view` (F1-2)

base.py に追加:
```python
def get_tag(self, name: str) -> Tag:
    raise NotSupportedError("tag view")
```

各アダプター: `GET /repos/{owner}/{repo}/tags/{tag}`

### 6c. `deploy-key view` (F1-3)

base.py に追加:
```python
def get_deploy_key(self, key_id: int) -> DeployKey:
    raise NotSupportedError("deploy-key view")
```

### 6d. `ssh-key view` (F1-4)

base.py に追加:
```python
def get_ssh_key(self, key_id: int) -> SSHKey:
    raise NotSupportedError("ssh-key view")
```

### 6e. `gpg-key view` (F1-5)

base.py に追加:
```python
def get_gpg_key(self, key_id: int) -> GPGKey:
    raise NotSupportedError("gpg-key view")
```

**テスト**: 各 `test_adapters/` に get テスト追加。`responses` で個別リソース取得をモック。

---

## 7. CRUD 一貫性: edit 追加

**課題**: F2-1〜F2-4
**変更ファイル**: `adapter/base.py`, `adapter/*.py`, `commands/webhook.py`, `commands/release.py`, `cli.py`

### 7a. `webhook edit` (F2-1)

base.py に追加:
```python
def update_webhook(
    self, hook_id: int, *,
    url: str | None = None,
    events: list[str] | None = None,
    secret: str | None = None,
    active: bool | None = None,
) -> Webhook:
    raise NotSupportedError("webhook edit")
```

各アダプター: `PATCH /repos/{owner}/{repo}/hooks/{id}`

cli.py:
```python
webhook_edit = webhook_sub.add_parser("edit")
webhook_edit.add_argument("id", type=int)
webhook_edit.add_argument("--url")
webhook_edit.add_argument("--event", action="append")
webhook_edit.add_argument("--secret")
webhook_edit.add_argument("--active", action="store_true", default=None)
webhook_edit.add_argument("--inactive", action="store_true")
```

### 7b. `org edit` (F2-2)

base.py に追加:
```python
def update_organization(
    self, name: str, *,
    display_name: str | None = None,
    description: str | None = None,
) -> Organization:
    raise NotSupportedError("org edit")
```

各アダプター: `PATCH /orgs/{org}`

cli.py:
```python
org_edit = org_sub.add_parser("edit")
org_edit.add_argument("name")
org_edit.add_argument("--display-name")
org_edit.add_argument("--description")
```

### 7c. `release asset edit` (F2-3)

base.py に追加:
```python
def update_release_asset(
    self, release_id: int, asset_id: int, *, name: str | None = None,
) -> ReleaseAsset:
    raise NotSupportedError("release asset edit")
```

### 7d. `tag-protect edit` (F2-4)

base.py に追加:
```python
def update_tag_protection(
    self, rule_id: int, *, pattern: str | None = None, access_level: str | None = None,
) -> TagProtection:
    raise NotSupportedError("tag-protect edit")
```

---

## 8. `pr status` 新規追加

**課題**: E1-1
**変更ファイル**: `commands/pr.py`, `cli.py`

既存の `list_pull_requests()` + `get_current_user()` を組み合わせて実装可能。新規アダプターメソッド不要。

```python
# commands/pr.py handle_status()
user = adapter.get_current_user()
username = user["login"]

created = adapter.list_pull_requests(state="open", author=username)      # B5-1 が前提
review_requested = adapter.list_pull_requests(state="open", search=f"review-requested:{username}")
assigned = adapter.list_pull_requests(state="open", assignee=username)   # B5-3 が前提
```

**依存**: TODO 2 (pr list フィルタ) の完了が前提。

---

## 9. PR/Issue lock/unlock

**課題**: E1-5, E1-6
**変更ファイル**: `adapter/base.py`, `adapter/*.py` (GitHub/GitLab/Gitea), `commands/pr.py`, `commands/issue.py`, `cli.py`

### base.py に追加

```python
def lock_issue(self, number: int, *, reason: str | None = None) -> None:
    raise NotSupportedError("issue lock")

def unlock_issue(self, number: int) -> None:
    raise NotSupportedError("issue unlock")
```

PR の lock/unlock は Issue と同じ API を使用するサービスが多い（GitHub/Gitea は Issue 番号 = PR 番号）。GitLab は MR 専用エンドポイント。

### 各アダプター

| サービス | lock | unlock |
|---|---|---|
| GitHub | `PUT /repos/{owner}/{repo}/issues/{number}/lock` (`lock_reason`) | `DELETE .../lock` |
| GitLab | `PUT /projects/{id}/issues/{iid}` (`discussion_locked: true`) | 同 `false` |
| Gitea | `PUT /repos/{owner}/{repo}/issues/{index}/lock` | `DELETE .../lock` |

---

## 10. CI 拡張

**課題**: E1-3, E1-4, E1-7, E1-8
**変更ファイル**: `adapter/base.py`, `adapter/*.py`, `commands/ci.py`, `cli.py`

### E1-7: `ci workflow list/enable/disable`

base.py に追加:
```python
def list_workflows(self, *, limit: int = 30) -> list[Workflow]:
    raise NotSupportedError("ci workflow list")
def enable_workflow(self, workflow_id) -> None:
    raise NotSupportedError("ci workflow enable")
def disable_workflow(self, workflow_id) -> None:
    raise NotSupportedError("ci workflow disable")
```

| サービス | list | enable/disable |
|---|---|---|
| GitHub | `GET /repos/{owner}/{repo}/actions/workflows` | `PUT .../workflows/{id}/enable` / `disable` |
| GitLab | `GET /projects/{id}/pipelines` (異なるモデル) | — |
| Gitea | `GET /repos/{owner}/{repo}/actions/workflows` | `PUT .../enable` / `disable` |

### E1-8 / E1-3: `ci artifact download` / `ci download`

base.py に追加:
```python
def download_artifact(self, run_id: int, artifact_id: int, *, output_dir: str = ".") -> str:
    raise NotSupportedError("ci artifact download")
def download_run_logs(self, run_id: int, *, job_id: int | None = None, output_dir: str = ".") -> str:
    raise NotSupportedError("ci download")
```

### E1-4: `ci watch`

ポーリングベースの実装。新規アダプターメソッドは不要（既存の `get_pipeline_run()` を繰り返し呼ぶ）。

```python
# commands/ci.py handle_watch()
import time
while True:
    run = adapter.get_pipeline_run(args.id)
    print(f"\r{run.status}", end="", flush=True)
    if run.status in ("completed", "success", "failure", "cancelled"):
        break
    time.sleep(args.interval)  # デフォルト 5 秒
```

---

## 11. Issue subscribe / Org scope secrets

**課題**: E1-9, E1-10
**変更ファイル**: `adapter/base.py`, `adapter/*.py`, `commands/issue.py`, `commands/secret.py`, `commands/variable.py`, `cli.py`

### E1-9: `issue subscribe` / `unsubscribe`

base.py に追加:
```python
def subscribe_issue(self, number: int) -> None:
    raise NotSupportedError("issue subscribe")
def unsubscribe_issue(self, number: int) -> None:
    raise NotSupportedError("issue unsubscribe")
```

| サービス | API |
|---|---|
| GitHub | `PUT /repos/{owner}/{repo}/issues/{number}/lock` → 違う。`PUT /repos/{owner}/{repo}/subscription` (repo watch) / Notification API |
| GitLab | `POST /projects/{id}/issues/{iid}/subscribe` / `unsubscribe` |
| Gitea/Forgejo | `PUT /repos/{owner}/{repo}/issues/{index}/subscriptions/{user}` / `DELETE ...` |

### E1-10: Org レベル `secret` / `variable`

既存の `set_secret()` / `delete_secret()` / `list_secrets()` に `scope` パラメータを追加、または別メソッド `set_org_secret()` 等を追加。

cli.py:
```python
secret_set.add_argument("--org", help=_("Organization scope"))
variable_set.add_argument("--org", help=_("Organization scope"))
```

| サービス | Org secrets API |
|---|---|
| GitHub | `GET/PUT/DELETE /orgs/{org}/actions/secrets/{name}` |
| GitLab | `GET/POST /groups/{id}/variables` |
| Gitea/Forgejo | `GET/PUT/DELETE /orgs/{org}/actions/secrets/{secretname}` |

---

## 12. `repo edit --name` (repo rename)

**課題**: E1-2
**変更ファイル**: `adapter/base.py`, `adapter/*.py`, `commands/repo.py`, `cli.py`

既存の `update_repository()` メソッドに `name` パラメータを追加するか、`repo edit` に `--name` オプションを追加。

```python
# cli.py
repo_edit.add_argument("--name", help=_("Rename repository"))
```

実装は `PATCH /repos/{owner}/{repo}` の `name` フィールドを送るだけ。全 6 サービスで同じパターン。

**注意**: リポジトリ名変更後は git remote の URL も変わるため、警告メッセージを表示。

---

## 13. `repo sync` (fork 同期)

**課題**: E2-1
**変更ファイル**: `adapter/base.py`, `adapter/*.py` (GitHub/Gitea/Forgejo), `commands/repo.py`, `cli.py`

base.py に追加:
```python
def sync_fork(self, *, branch: str | None = None) -> None:
    raise NotSupportedError("repo sync")
```

| サービス | API |
|---|---|
| GitHub | `POST /repos/{owner}/{repo}/merge-upstream` (`branch`) |
| Gitea | `POST /repos/{owner}/{repo}/merge-upstream` |
| Forgejo | `POST /repos/{owner}/{repo}/sync_fork` / `sync_fork/{branch}` |
