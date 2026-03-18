# pr-create-options

## 概要

`pr create` に `--reviewer`, `--assignee`, `--label`, `--milestone`, `--fill` オプションを追加する。
gh / glab はいずれも PR 作成時にこれらのオプションを提供しており、gfo もこれに合わせる。

- **種別**: 機能追加
- **優先度**: Phase 2（独立して実施可能）

## 変更後

```
gfo pr create --title "Fix bug" --reviewer alice --reviewer bob --label bug --milestone v1.0
gfo pr create --fill                    # 最後のコミットから title/body を自動設定
gfo pr create --fill --reviewer alice   # 組み合わせ可能
```

## 実装手順

### 1. アダプター基底クラス (`src/gfo/adapter/base.py`)

`create_pull_request` のシグネチャを拡張:

```python
def create_pull_request(
    self, *, title: str, body: str = "", base: str, head: str, draft: bool = False,
    reviewers: list[str] | None = None,
    assignees: list[str] | None = None,
    labels: list[str] | None = None,
    milestone: str | None = None,
) -> PullRequest: ...
```

### 2. 各アダプター実装

新パラメータを API リクエストに反映:

| サービス | reviewers | assignees | labels | milestone |
|---|---|---|---|---|
| GitHub | POST requested_reviewers | `assignees` フィールド | `labels` フィールド | milestone number 解決 |
| GitLab | `reviewer_ids`（ユーザー名→ID 解決） | `assignee_ids` | `labels`（カンマ区切り） | `milestone_id` |
| Gitea | `assignees` | `assignees` | `labels`（ID 解決必要） | `milestone` |
| Bitbucket | `reviewers` | 未サポート | 未サポート | 未サポート |
| Azure DevOps | `reviewers` API | 未サポート | 未サポート | 未サポート |
| 他 | 未サポートのパラメータは無視（エラーにしない） |

### 3. CLI パーサー定義 (`src/gfo/cli.py`)

```python
pr_create.add_argument("--reviewer", action="append", help=_("Reviewer username (repeatable)"))
pr_create.add_argument("--assignee", action="append", help=_("Assignee username (repeatable)"))
pr_create.add_argument("--label", action="append", help=_("Label name (repeatable)"))
pr_create.add_argument("--milestone", help=_("Milestone name or ID"))
pr_create.add_argument("--fill", action="store_true", help=_("Use commit info for title and body"))
```

### 4. コマンドハンドラー (`src/gfo/commands/pr.py`)

`handle_create` を拡張:

```python
def handle_create(args, *, fmt, jq=None):
    adapter = get_adapter()
    head = args.head or gfo.git_util.get_current_branch()
    base = args.base or gfo.git_util.get_default_branch()

    # --fill: コミットメッセージから title/body を自動設定
    if getattr(args, "fill", False):
        title = args.title or gfo.git_util.get_last_commit_subject() or ""
        body = args.body or gfo.git_util.get_last_commit_body() or ""
    else:
        title = args.title or gfo.git_util.get_last_commit_subject() or ""
        body = args.body or ""

    title = title.strip()
    if not title:
        raise ConfigError(_("Could not determine PR title. Use --title option."))

    pr = adapter.create_pull_request(
        title=title,
        body=body,
        base=base,
        head=head,
        draft=args.draft,
        reviewers=getattr(args, "reviewer", None),
        assignees=getattr(args, "assignee", None),
        labels=getattr(args, "label", None),
        milestone=getattr(args, "milestone", None),
    )
    output(pr, fmt=fmt, jq=jq)
```

**注意**: `--fill` は既存の title 自動検出ロジックとほぼ同じだが、body も含めて自動設定する点が異なる。`get_last_commit_body()` が `git_util` に存在しない場合は追加が必要。

### 5. テスト

- `tests/test_commands/test_pr.py` に新オプションのテストを追加
- 各アダプターのテストで新パラメータの API マッピングを確認
- `--fill` オプションのテスト（`git_util` をモック）

### 6. ドキュメント更新

- `docs/commands.md` / `.ja.md`: `pr create` のオプション一覧を更新
- `docs/cli-comparison.md`: 3.1 の create オプション比較表で gfo 列を Y に更新
- `docs/cli-alignment.md`: 完了後にステータス更新
