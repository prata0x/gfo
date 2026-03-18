# move-comment-to-subcommand

## 概要

独立 `comment` コマンドを廃止し、`pr comment` / `issue comment` サブコマンドに移動する。
gh / glab はいずれも `pr comment` / `issue comment` としてコメント操作を提供しており、gfo もこれに合わせる。

- **種別**: 破壊的変更
- **優先度**: Phase 1（タスク 1 `rename-update-to-edit` の後に実施）
- **前提**: タスク 1 の `edit` リネームが完了していること

## 現在の構造

```
gfo comment list <resource> <number>
gfo comment create <resource> <number> --body <body>
gfo comment update <comment_id> --body TEXT --on <resource>
gfo comment delete <comment_id> --on <resource>
```

## 変更後の構造

```
gfo pr comment list <number>
gfo pr comment create <number> --body <body>
gfo pr comment edit <comment_id> --body <body>
gfo pr comment delete <comment_id>

gfo issue comment list <number>
gfo issue comment create <number> --body <body>
gfo issue comment edit <comment_id> --body <body>
gfo issue comment delete <comment_id>
```

## 実装手順

### 1. CLI パーサー定義 (`src/gfo/cli.py`)

- トップレベルの `comment` パーサー定義（行 410-447 付近）を削除
- `subparser_map` から `"comment"` エントリを削除
- `pr_sub` に `comment` サブパーサーを追加（`pr reviewers` と同じネストパターン）:

```python
# gfo pr comment → サブサブコマンド
pr_comment = pr_sub.add_parser("comment", help=_("Manage PR comments"))
pr_comment_sub = pr_comment.add_subparsers(dest="comment_action")
pr_comment_list = pr_comment_sub.add_parser("list", help=_("List comments"))
pr_comment_list.add_argument("number", type=int, help=_("PR number"))
pr_comment_list.add_argument("--limit", type=_positive_int, default=30, help=_("Maximum number of results"))
pr_comment_create = pr_comment_sub.add_parser("create", help=_("Create comment"))
pr_comment_create.add_argument("number", type=int, help=_("PR number"))
pr_comment_create.add_argument("--body", required=True, help=_("Body"))
pr_comment_edit = pr_comment_sub.add_parser("edit", help=_("Edit comment"))
pr_comment_edit.add_argument("comment_id", type=int, help=_("Comment ID"))
pr_comment_edit.add_argument("--body", required=True, help=_("Body"))
pr_comment_delete = pr_comment_sub.add_parser("delete", help=_("Delete comment"))
pr_comment_delete.add_argument("comment_id", type=int, help=_("Comment ID"))
```

- `issue_sub` にも同様に `comment` サブパーサーを追加
- `resource` 引数は不要（親コマンドから "pr" / "issue" が確定）
- `--on` オプションも不要（同上）

### 2. ディスパッチマップ (`src/gfo/cli.py`)

削除:
```python
("comment", "list"), ("comment", "create"), ("comment", "edit"), ("comment", "delete")
```

追加（`pr reviewers` と同じネストパターンを踏襲）:
```python
("pr", "comment"): gfo.commands.comment.handle_pr_comment,
("issue", "comment"): gfo.commands.comment.handle_issue_comment,
```

または個別のディスパッチキーにする場合:
```python
("pr", "comment list"), ("pr", "comment create"), ("pr", "comment edit"), ("pr", "comment delete")
("issue", "comment list"), ("issue", "comment create"), ("issue", "comment edit"), ("issue", "comment delete")
```

※ 既存の `pr reviewers list/add/remove` の実装パターンを確認して決定する。

### 3. コマンドハンドラー (`src/gfo/commands/comment.py`)

ハンドラー関数はそのまま再利用可能。ただし `resource` 引数の取得方法を変更:

**案 A**: ディスパッチ時に `args.resource` をセットする
```python
# cli.py のディスパッチで
args.resource = "pr"  # or "issue"
```

**案 B**: 統合ハンドラーを作成
```python
def handle_pr_comment(args, *, fmt, jq=None):
    args.resource = "pr"
    _dispatch_comment(args, fmt=fmt, jq=jq)

def handle_issue_comment(args, *, fmt, jq=None):
    args.resource = "issue"
    _dispatch_comment(args, fmt=fmt, jq=jq)
```

- `handle_update` → `handle_edit` にリネーム（タスク 1 と連動）
- `--on` オプション参照を削除（`args.on` → `args.resource`）

### 4. スキーマ定義 (`src/gfo/commands/schema.py`)

`_OUTPUT_MAP` のキーを変更:
```python
# 削除
("comment", "list"), ("comment", "create"), ("comment", "edit"), ("comment", "delete")

# 追加（実際のディスパッチキー構造に合わせる）
("pr", "comment"): list[Comment],  # or 個別のキーに分割
("issue", "comment"): list[Comment],
```

### 5. テスト (`tests/test_commands/test_comment.py`)

- テストを `pr comment` / `issue comment` の構造に合わせて更新
- `make_args(resource="pr", ...)` → `make_args(number=42, ...)` のように引数構造を変更
- `--on` オプションのテストを削除
- `resource` 引数のテストを削除

### 6. ドキュメント更新

- `docs/commands.md`: `## comment` セクションを削除し、`## pr` セクション内に `### pr comment` を追加。`## issue` セクション内にも同様
- `docs/commands.ja.md`: 同上
- `docs/cli-comparison.md`:
  - メインコマンド一覧比較表: `comment` 行を削除し、`pr` / `issue` の行に注記を追加
  - 3.1 PR サブコマンド対応表に `comment` 行を追加（`list/create/edit/delete`）
  - 3.2 Issue サブコマンド対応表に `comment` 行を追加
  - セクション 4 独自コマンド表から `comment` を削除
- `docs/cli-alignment.md`: 完了後にステータス更新
- `docs/spec.md`: コマンド構造の記載を更新
