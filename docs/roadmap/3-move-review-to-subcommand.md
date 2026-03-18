# move-review-to-subcommand

## 概要

独立 `review` コマンドを廃止し、`pr review` サブコマンドに移動する。
gh / glab はいずれも `pr review` としてレビュー操作を提供しており、gfo もこれに合わせる。

- **種別**: 破壊的変更
- **優先度**: Phase 1（タスク 1 の後に実施）

## 現在の構造

```
gfo review list <number>
gfo review create <number> --approve/--request-changes/--comment [--body]
gfo review dismiss <number> <review_id> [--message]
```

## 変更後の構造

```
gfo pr review list <number>
gfo pr review create <number> --approve/--request-changes/--comment [--body]
gfo pr review dismiss <number> <review_id> [--message]
```

## 実装手順

### 1. CLI パーサー定義 (`src/gfo/cli.py`)

- トップレベルの `review` パーサー定義（行 468-486 付近）を削除
- `subparser_map` から `"review"` エントリを削除
- `pr_sub` に `review` サブパーサーを追加（`pr reviewers` と同じネストパターン）:

```python
# gfo pr review → サブサブコマンド
pr_review = pr_sub.add_parser("review", help=_("Manage PR reviews"))
pr_review_sub = pr_review.add_subparsers(dest="review_action")
pr_review_list = pr_review_sub.add_parser("list", help=_("List reviews"))
pr_review_list.add_argument("number", type=int, help=_("PR number"))
pr_review_create = pr_review_sub.add_parser("create", help=_("Create review"))
pr_review_create.add_argument("number", type=int, help=_("PR number"))
_review_group = pr_review_create.add_mutually_exclusive_group(required=True)
_review_group.add_argument("--approve", action="store_true", help=_("Approve"))
_review_group.add_argument("--request-changes", dest="request_changes", action="store_true", help=_("Request changes"))
_review_group.add_argument("--comment", action="store_true", help=_("Comment only"))
pr_review_create.add_argument("--body", default="", help=_("Body"))
pr_review_dismiss = pr_review_sub.add_parser("dismiss", help=_("Dismiss review"))
pr_review_dismiss.add_argument("number", type=int, help=_("PR number"))
pr_review_dismiss.add_argument("review_id", type=int, help=_("Review ID"))
pr_review_dismiss.add_argument("--message", default="", help=_("Message"))
```

引数定義は現行のまま（number, --approve/--request-changes/--comment, --body, review_id, --message）。

### 2. ディスパッチマップ (`src/gfo/cli.py`)

削除:
```python
("review", "list"), ("review", "create"), ("review", "dismiss")
```

追加（`pr reviewers` と同じネストパターンを踏襲）:
```python
("pr", "review"): gfo.commands.review.handle_review,
```

または個別のディスパッチキーにする場合:
```python
("pr", "review list"), ("pr", "review create"), ("pr", "review dismiss")
```

※ `pr reviewers` の実装パターンを確認して決定する。

### 3. コマンドハンドラー (`src/gfo/commands/review.py`)

- ハンドラー関数はそのまま再利用（引数構造に変更なし）
- ファイル自体は残す（`src/gfo/commands/review.py`）
- ディスパッチ方法に合わせて統合ハンドラーを追加する場合:

```python
def handle_review(args, *, fmt, jq=None):
    action = getattr(args, "review_action", None)
    if action == "list":
        handle_list(args, fmt=fmt, jq=jq)
    elif action == "create":
        handle_create(args, fmt=fmt, jq=jq)
    elif action == "dismiss":
        handle_dismiss(args, fmt=fmt, jq=jq)
```

### 4. スキーマ定義 (`src/gfo/commands/schema.py`)

`_OUTPUT_MAP` のキーを変更:
```python
# 削除
("review", "list"), ("review", "create"), ("review", "dismiss")

# 追加（実際のディスパッチキー構造に合わせる）
("pr", "review"): list[Review],  # or 個別のキーに分割
```

### 5. テスト (`tests/test_commands/test_review.py`)

- ディスパッチキーの変更に合わせてテストを更新
- `make_args()` の `command` / `subcommand` を `pr review` に変更

### 6. ドキュメント更新

- `docs/commands.md`: `## review` セクションを削除し、`## pr` セクション内に `### pr review` を追加
- `docs/commands.ja.md`: 同上
- `docs/cli-comparison.md`:
  - メインコマンド一覧比較表: `review` 行を削除し、`pr` の行に注記追加
  - 3.1 PR サブコマンド対応表に `review` 行を追加（`list/create/dismiss`）
  - セクション 4 独自コマンド表から `review` を削除
- `docs/cli-alignment.md`: 完了後にステータス更新
- `docs/spec.md`: コマンド構造の記載を更新
