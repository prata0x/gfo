# gfo API 全機能実装計画

## Context

gfo は現在 PR/Issue/Repo/Release/Label/Milestone の基本 CRUD に対応している。
各 Git サービス API には他にも多くの機能が存在し、これらを段階的に実装してカバー範囲を広げる。

## 実装優先度

1. **実用上よく使われるもの** — 日常ワークフローで頻繁に使う操作
2. **主要サービス共通機能** — ほぼ全サービスが API 提供する基盤操作
3. **OSS 機能** — セルフホスト系で重要な管理操作
4. **無料サービス** — CI/CD・パッケージ等の付加機能
5. **Backlog 固有機能** — Backlog のみに存在する操作

---

## 実装パターン（共通）

新機能追加時の手順（既存コードのパターンに従う）:

1. `adapter/base.py`: データクラス追加 (`@dataclass(frozen=True, slots=True)`) + 抽象メソッド or デフォルト `NotSupportedError`
2. `adapter/base.py`: `GitHubLikeAdapter` に `_to_xxx()` 変換メソッド追加（GitHub/Gitea 共通の場合）
3. 各アダプター: メソッド実装（非対応サービスは `NotSupportedError`）
4. `commands/xxx.py`: ハンドラ作成 (`handle_xxx(args, *, fmt)`)
5. `cli.py`: サブパーサー + `_DISPATCH` 登録
6. テスト: `test_adapters/test_*.py` (responses モック) + `test_commands/test_*.py` (MagicMock)

---

## Phase 1: 実用上よく使われるもの

### P1-1: コメント操作 (`gfo comment`)

PR/Issue 両方のコメントを統一コマンドで操作する。

**データクラス**:
```python
@dataclass(frozen=True, slots=True)
class Comment:
    id: int
    body: str
    author: str
    url: str
    created_at: str
    updated_at: str | None = None
```

**アダプターメソッド** (`@abstractmethod`):
- `list_comments(resource: str, number: int, *, limit: int = 30) -> list[Comment]`
  - `resource`: `"pr"` or `"issue"`
- `create_comment(resource: str, number: int, *, body: str) -> Comment`

**アダプターメソッド** (デフォルト `NotSupportedError`):
- `update_comment(resource: str, comment_id: int, *, body: str) -> Comment`
- `delete_comment(resource: str, comment_id: int) -> None`

**コマンド**:
```
gfo comment list   <pr|issue> <number> [--limit N]
gfo comment create <pr|issue> <number> --body TEXT
gfo comment update <comment-id> --body TEXT --on <pr|issue>
gfo comment delete <comment-id> --on <pr|issue>
```

**サービス対応**:

| サービス | list | create | update | delete | 備考 |
|---|:---:|:---:|:---:|:---:|---|
| GitHub | o | o | o | o | PR/Issue 共通エンドポイント |
| GitLab | o | o | △ | △ | Notes API は URL に issue/MR 番号が必要（※1） |
| Bitbucket | o | o | o | o | PR: `/comments`, Issue: `/comments` |
| Azure DevOps | o | o | △ | △ | PR コメントは Thread API でスレッド ID が必要（※2） |
| Backlog | o | o | o | o | `/comments` |
| Gitea | o | o | o | o | GitHub 互換 |
| Forgejo | o | o | o | o | Gitea 継承 |
| Gogs | o | o | x | x | Issue コメントのみ |
| GitBucket | o | o | o | o | GitHub 互換 |

> **※1 GitLab**: `update_comment` / `delete_comment` は現在 `NotSupportedError`。
> GitLab の Notes API（`PUT /projects/:id/issues/:issue_iid/notes/:note_id`）は
> URL に issue/MR 番号が必要だが、本インターフェースは `comment_id` のみ受け取るため
> リソース番号を特定できない。対応するには `resource` と `number` をメソッドシグネチャに
> 追加する必要がある（将来の改善候補）。
>
> **※2 Azure DevOps**: `update_comment` / `delete_comment` は現在 `NotSupportedError`。
> PR コメントの更新・削除は Thread API（`PATCH /repos/.../threads/:threadId/comments/:commentId`）
> を使用し、スレッド ID が必要。本インターフェースは `comment_id` のみ受け取るため
> スレッド ID を特定できない（将来の改善候補）。

### P1-2: PR 更新 (`gfo pr update`)

既存の `commands/pr.py` に `handle_update` を追加。

**アダプターメソッド** (`@abstractmethod`):
- `update_pull_request(number: int, *, title: str | None = None, body: str | None = None, base: str | None = None) -> PullRequest`

**コマンド**:
```
gfo pr update <number> [--title TEXT] [--body TEXT] [--base BRANCH]
```

**サービス対応**: 全サービス o（Backlog は `merge_pull_request` 非対応だが update は可能）。Gogs は PR 自体が非対応のため x。

### P1-3: Issue 更新 (`gfo issue update`)

既存の `commands/issue.py` に `handle_update` を追加。

**アダプターメソッド** (`@abstractmethod`):
- `update_issue(number: int, *, title: str | None = None, body: str | None = None, assignee: str | None = None, label: str | None = None) -> Issue`

**コマンド**:
```
gfo issue update <number> [--title TEXT] [--body TEXT] [--assignee USER] [--label LABEL]
```

**サービス対応**: 全サービス o。

### P1-4: PR レビュー (`gfo review`)

**データクラス**:
```python
@dataclass(frozen=True, slots=True)
class Review:
    id: int
    state: str          # "approved", "changes_requested", "commented"
    body: str
    author: str
    url: str
    submitted_at: str | None = None
```

**アダプターメソッド** (デフォルト `NotSupportedError`):
- `list_reviews(number: int) -> list[Review]`
- `create_review(number: int, *, state: str, body: str = "") -> Review`

**コマンド**:
```
gfo review list   <number>
gfo review create <number> --approve|--request-changes|--comment [--body TEXT]
```

**サービス対応**:

| サービス | list | create | 備考 |
|---|:---:|:---:|---|
| GitHub | o | o | Reviews API |
| GitLab | o | o | Approvals API + Notes |
| Bitbucket | o | o | `/approve`, `/request-changes` |
| Azure DevOps | o | o | Reviewers API |
| Gitea | o | o | GitHub 互換 Reviews API |
| Forgejo | o | o | Gitea 継承 |
| Gogs | x | x | PR 非対応 |
| GitBucket | x | x | Reviews API なし |
| Backlog | x | x | レビュー機能なし |

---

## Phase 2: 主要サービス共通機能

### P2-1: ブランチ操作 (`gfo branch`)

**データクラス**:
```python
@dataclass(frozen=True, slots=True)
class Branch:
    name: str
    sha: str
    protected: bool
    url: str
```

**アダプターメソッド** (`@abstractmethod`):
- `list_branches(*, limit: int = 30) -> list[Branch]`
- `create_branch(*, name: str, ref: str) -> Branch`

**アダプターメソッド** (デフォルト `NotSupportedError`):
- `delete_branch(*, name: str) -> None`

**コマンド**:
```
gfo branch list   [--limit N]
gfo branch create <name> --ref <sha-or-branch>
gfo branch delete <name>
```

**サービス対応**: GitHub/GitLab/Bitbucket/Azure DevOps/Gitea/Forgejo o、Gogs o（list/create のみ）、GitBucket o（GitHub 互換）、Backlog o。

### P2-2: タグ操作 (`gfo tag`)

**データクラス**:
```python
@dataclass(frozen=True, slots=True)
class Tag:
    name: str
    sha: str
    message: str
    url: str
```

**アダプターメソッド** (デフォルト `NotSupportedError`):
- `list_tags(*, limit: int = 30) -> list[Tag]`
- `create_tag(*, name: str, ref: str, message: str = "") -> Tag`
- `delete_tag(*, name: str) -> None`

**コマンド**:
```
gfo tag list   [--limit N]
gfo tag create <name> --ref <sha-or-branch> [--message TEXT]
gfo tag delete <name>
```

**サービス対応**: GitHub/GitLab/Gitea/Forgejo o、Bitbucket o（list/create）、Azure DevOps o、Gogs △（list のみ）、Backlog x、GitBucket o。

### P2-3: コミットステータス (`gfo status`)

CI/CD のビルド結果をコミットに紐付ける。

**データクラス**:
```python
@dataclass(frozen=True, slots=True)
class CommitStatus:
    state: str          # "success", "failure", "pending", "error"
    context: str        # e.g. "ci/build"
    description: str
    target_url: str
    created_at: str
```

**アダプターメソッド** (デフォルト `NotSupportedError`):
- `list_commit_statuses(ref: str, *, limit: int = 30) -> list[CommitStatus]`
- `create_commit_status(ref: str, *, state: str, context: str = "", description: str = "", target_url: str = "") -> CommitStatus`

**コマンド**:
```
gfo status list   <ref>
gfo status create <ref> --state <success|failure|pending|error> [--context TEXT] [--description TEXT] [--url URL]
```

**サービス対応**: GitHub/GitLab/Bitbucket/Gitea/Forgejo o、Azure DevOps o（policy status として）、Gogs x、GitBucket o、Backlog x。

### P2-4: ファイル操作 (`gfo file`)

リポジトリ内ファイルの CRUD（Web API 経由）。

**アダプターメソッド** (デフォルト `NotSupportedError`):
- `get_file_content(path: str, *, ref: str | None = None) -> tuple[str, str]`  # (content, sha)
- `create_or_update_file(path: str, *, content: str, message: str, sha: str | None = None, branch: str | None = None) -> None`
- `delete_file(path: str, *, sha: str, message: str, branch: str | None = None) -> None`

**コマンド**:
```
gfo file get    <path> [--ref REF]
gfo file put    <path> --message TEXT [--branch BRANCH] < content
gfo file delete <path> --message TEXT [--branch BRANCH]
```

**サービス対応**: GitHub/GitLab/Gitea/Forgejo/GitBucket o、Bitbucket o（src エンドポイント）、Azure DevOps o（pushes API）、Backlog o（git API）、Gogs o。

### P2-5: Fork 操作

既存の `commands/repo.py` に `handle_fork` を追加。

**アダプターメソッド** (デフォルト `NotSupportedError`):
- `fork_repository(*, organization: str | None = None) -> Repository`

**コマンド**:
```
gfo repo fork [--org ORGANIZATION]
```

**サービス対応**: GitHub/GitLab/Bitbucket/Gitea/Forgejo o、Azure DevOps o（fork API）、Gogs o、GitBucket x、Backlog x。

---

## Phase 3: OSS 機能

### P3-1: Webhook 操作 (`gfo webhook`)

**データクラス**:
```python
@dataclass(frozen=True, slots=True)
class Webhook:
    id: int
    url: str
    events: tuple[str, ...]
    active: bool
```

**アダプターメソッド** (デフォルト `NotSupportedError`):
- `list_webhooks(*, limit: int = 30) -> list[Webhook]`
- `create_webhook(*, url: str, events: list[str], secret: str | None = None) -> Webhook`
- `delete_webhook(*, hook_id: int) -> None`

**コマンド**:
```
gfo webhook list   [--limit N]
gfo webhook create --url URL --event EVENT [--event EVENT ...] [--secret TEXT]
gfo webhook delete <id>
```

**サービス対応**: GitHub/GitLab/Bitbucket/Gitea/Forgejo o、Azure DevOps o（Service Hooks）、Gogs o、GitBucket o、Backlog o。

### P3-2: Deploy Keys 操作 (`gfo deploy-key`)

**データクラス**:
```python
@dataclass(frozen=True, slots=True)
class DeployKey:
    id: int
    title: str
    key: str
    read_only: bool
```

**アダプターメソッド** (デフォルト `NotSupportedError`):
- `list_deploy_keys(*, limit: int = 30) -> list[DeployKey]`
- `create_deploy_key(*, title: str, key: str, read_only: bool = True) -> DeployKey`
- `delete_deploy_key(*, key_id: int) -> None`

**コマンド**:
```
gfo deploy-key list   [--limit N]
gfo deploy-key create --title TEXT --key TEXT [--read-write]
gfo deploy-key delete <id>
```

**サービス対応**: GitHub/GitLab/Bitbucket/Gitea/Forgejo o、Gogs o、GitBucket o、Azure DevOps x（SSH policy が異なる）、Backlog o。

### P3-3: コラボレーター操作 (`gfo collaborator`)

**アダプターメソッド** (デフォルト `NotSupportedError`):
- `list_collaborators(*, limit: int = 30) -> list[str]`
- `add_collaborator(*, username: str, permission: str = "write") -> None`
- `remove_collaborator(*, username: str) -> None`

**コマンド**:
```
gfo collaborator list   [--limit N]
gfo collaborator add    <username> [--permission read|write|admin]
gfo collaborator remove <username>
```

**サービス対応**: GitHub/GitLab/Gitea/Forgejo o、Bitbucket o（workspace members）、Azure DevOps △（permissions API が複雑）、Gogs o、GitBucket o、Backlog o（project members）。

---

## Phase 4: 無料サービス CI/CD・付加機能

### P4-1: CI/CD パイプライン (`gfo ci`)

サービスごとに大きく異なるため、共通の最小インターフェースを定義。

**データクラス**:
```python
@dataclass(frozen=True, slots=True)
class Pipeline:
    id: int | str
    status: str         # "success", "failure", "running", "pending", "cancelled"
    ref: str            # branch or tag
    url: str
    created_at: str
```

**アダプターメソッド** (デフォルト `NotSupportedError`):
- `list_pipelines(*, ref: str | None = None, limit: int = 30) -> list[Pipeline]`
- `get_pipeline(pipeline_id: int | str) -> Pipeline`
- `cancel_pipeline(pipeline_id: int | str) -> None`

**コマンド**:
```
gfo ci list   [--ref BRANCH] [--limit N]
gfo ci view   <id>
gfo ci cancel <id>
```

**サービス対応**:

| サービス | list | view | cancel | 備考 |
|---|:---:|:---:|:---:|---|
| GitHub | o | o | o | Actions Workflow Runs API |
| GitLab | o | o | o | Pipelines API |
| Bitbucket | o | o | o | Pipelines API |
| Azure DevOps | o | o | o | Build API |
| Gitea | o | o | o | Actions API (1.19+) |
| Forgejo | o | o | o | Gitea 継承 |
| Gogs | x | x | x | CI なし |
| GitBucket | x | x | x | CI なし |
| Backlog | x | x | x | CI なし |

### P4-2: ユーザー情報 (`gfo user`)

**コマンド**:
```
gfo user whoami
```

**アダプターメソッド** (デフォルト `NotSupportedError`):
- `get_current_user() -> dict`  # サービスごとにフィールドが異なるため dict

**サービス対応**: 全サービス o。

### P4-3: 検索 (`gfo search`)

**コマンド**:
```
gfo search repos  <query> [--limit N]
gfo search issues <query> [--limit N]
```

**アダプターメソッド** (デフォルト `NotSupportedError`):
- `search_repositories(query: str, *, limit: int = 30) -> list[Repository]`
- `search_issues(query: str, *, limit: int = 30) -> list[Issue]`

**サービス対応**: GitHub/GitLab/Gitea/Forgejo o、Bitbucket o（search API）、Azure DevOps △（WIQL で代替）、Gogs x、GitBucket x、Backlog o。

---

## Phase 5: Backlog 固有機能

### P5-1: Wiki (`gfo wiki`)

**データクラス**:
```python
@dataclass(frozen=True, slots=True)
class WikiPage:
    id: int
    title: str
    content: str
    url: str
    updated_at: str | None = None
```

**アダプターメソッド** (デフォルト `NotSupportedError`):
- `list_wiki_pages(*, limit: int = 30) -> list[WikiPage]`
- `get_wiki_page(page_id: int | str) -> WikiPage`
- `create_wiki_page(*, title: str, content: str) -> WikiPage`
- `update_wiki_page(page_id: int | str, *, title: str | None = None, content: str | None = None) -> WikiPage`
- `delete_wiki_page(page_id: int | str) -> None`

**コマンド**:
```
gfo wiki list   [--limit N]
gfo wiki view   <id>
gfo wiki create --title TEXT --content TEXT
gfo wiki update <id> [--title TEXT] [--content TEXT]
gfo wiki delete <id>
```

**サービス対応**: GitLab/Gitea/Forgejo/Backlog o、GitHub x（Wiki API は GitHub Enterprise のみ）、他 x。

---

## サービス対応サマリ

| 機能 | GitHub | GitLab | BB | AzDO | Backlog | Gitea | Forgejo | Gogs | GitBucket |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **P1 comment** | o | o | o | o | o | o | o | △ | o |
| **P1 pr update** | o | o | o | o | o | o | o | x | o |
| **P1 issue update** | o | o | o | o | o | o | o | o | o |
| **P1 review** | o | o | o | o | x | o | o | x | x |
| **P2 branch** | o | o | o | o | o | o | o | o | o |
| **P2 tag** | o | o | o | o | x | o | o | △ | o |
| **P2 status** | o | o | o | o | x | o | o | x | o |
| **P2 file** | o | o | o | o | o | o | o | o | o |
| **P2 fork** | o | o | o | o | x | o | o | o | x |
| **P3 webhook** | o | o | o | o | o | o | o | o | o |
| **P3 deploy-key** | o | o | o | x | o | o | o | o | o |
| **P3 collaborator** | o | o | o | △ | o | o | o | o | o |
| **P4 ci** | o | o | o | o | x | o | o | x | x |
| **P4 user** | o | o | o | o | o | o | o | o | o |
| **P4 search** | o | o | o | △ | o | o | o | x | x |
| **P5 wiki** | x | o | x | x | o | o | o | x | x |

## 実装タスク見積もり

| Phase | タスク数 | 新コマンド | 新データクラス | 新メソッド |
|---|---|---|---|---|
| P1 | 4 | 2 (comment, review) | 2 | 8 |
| P2 | 5 | 4 (branch, tag, status, file) | 4 | 12 |
| P3 | 3 | 3 (webhook, deploy-key, collaborator) | 2 | 9 |
| P4 | 3 | 2 (ci, search) + 拡張1 (user) | 1 | 6 |
| P5 | 1 | 1 (wiki) | 1 | 5 |
| **合計** | **16** | **12 + 拡張 2** | **10** | **40** |

## 検証方法

各タスクの完了後:
1. `pytest` で全テストが pass（既存 1058+ テスト含む）
2. `ruff check src/gfo/` で lint pass
3. `mypy src/gfo/` で型チェック pass
4. 統合テスト（Docker Compose）で Gitea/Forgejo/Gogs/GitBucket 動作確認
