# rename-update-to-edit

## 概要

全 8 コマンドの `update` サブコマンドを `edit` にリネームする。
gh / glab / tea / fj はすべて `edit` を使用しており、gfo もこれに合わせる。

- **種別**: 破壊的変更
- **優先度**: Phase 1（最初に実施、他タスクの前提）
- **対象コマンド**: pr, issue, repo, release, label, milestone, comment, wiki

## 実装手順

### 1. CLI パーサー定義 (`src/gfo/cli.py`)

以下 8 箇所の `add_parser("update", ...)` を `add_parser("edit", ...)` に変更:

| 行（目安） | 変数名 | 変更前 | 変更後 |
|---|---|---|---|
| 449 | `pr_update` | `add_parser("update", ...)` | `add_parser("edit", ...)` |
| 456 | `issue_update` | 同上 | 同上 |
| 265 | `repo_update` | 同上 | 同上 |
| 333 | `release_update` | 同上 | 同上 |
| 378 | `label_update` | 同上 | 同上 |
| 398 | `milestone_update` | 同上 | 同上 |
| 428 | `comment_update` | 同上 | 同上 |
| 667 | `wiki_update` | 同上 | 同上 |

変数名も `*_update` → `*_edit` に変更。help テキスト "Update ..." → "Edit ..." に変更。

### 2. ディスパッチマップ (`src/gfo/cli.py`)

`_DISPATCH` 辞書の 8 エントリのキーを変更:

```
("pr", "update")        → ("pr", "edit")
("issue", "update")     → ("issue", "edit")
("repo", "update")      → ("repo", "edit")
("release", "update")   → ("release", "edit")
("label", "update")     → ("label", "edit")
("milestone", "update") → ("milestone", "edit")
("comment", "update")   → ("comment", "edit")
("wiki", "update")      → ("wiki", "edit")
```

### 3. スキーマ定義 (`src/gfo/commands/schema.py`)

`_OUTPUT_MAP` の 8 エントリのキーを同様に変更:

```python
("pr", "update")        → ("pr", "edit")
("issue", "update")     → ("issue", "edit")
("repo", "update")      → ("repo", "edit")
("release", "update")   → ("release", "edit")
("label", "update")     → ("label", "edit")
("milestone", "update") → ("milestone", "edit")
("comment", "update")   → ("comment", "edit")
("wiki", "update")      → ("wiki", "edit")
```

### 4. コマンドハンドラー

各ファイルの `handle_update` 関数を `handle_edit` にリネーム:

| ファイル | 関数名変更 |
|---|---|
| `src/gfo/commands/pr.py` | `handle_update` → `handle_edit` |
| `src/gfo/commands/issue.py` | `handle_update` → `handle_edit` |
| `src/gfo/commands/repo.py` | `handle_update` → `handle_edit` |
| `src/gfo/commands/release.py` | `handle_update` → `handle_edit` |
| `src/gfo/commands/label.py` | `handle_update` → `handle_edit` |
| `src/gfo/commands/milestone.py` | `handle_update` → `handle_edit` |
| `src/gfo/commands/comment.py` | `handle_update` → `handle_edit` |
| `src/gfo/commands/wiki.py` | `handle_update` → `handle_edit` |

**注意**: アダプター層の `update_*` メソッド名は変更しない（API メソッド名は内部実装であり CLI 名と一致させる必要なし）。

### 5. テストファイル

以下のテストファイルで `make_args(subcommand="update")` 等の参照を `"edit"` に変更:

- `tests/test_commands/test_pr_update.py`
- `tests/test_commands/test_issue_update.py`
- `tests/test_commands/test_release.py`
- `tests/test_commands/test_label.py`
- `tests/test_commands/test_milestone.py`
- `tests/test_commands/test_comment.py`
- `tests/test_commands/test_repo.py`
- `tests/test_commands/test_wiki.py`

テストクラス名 `TestHandleUpdate` → `TestHandleEdit` にリネーム。
`handle_update` の呼び出しを `handle_edit` に変更。

### 6. ドキュメント更新

- `docs/commands.md`: 8 箇所の `gfo <cmd> update` セクションを `gfo <cmd> edit` に変更
- `docs/commands.ja.md`: 同上の日本語版
- `docs/cli-comparison.md`: 3.1〜3.6 の比較表で gfo 列を `Y (edit)` に更新。セクション 4 の独自コマンド表も更新
- `docs/cli-alignment.md`: 完了後に gfo (現在) 列を `edit` に更新
- `docs/integration-testing.md` / `.ja.md`: `repo update` 等の記載を更新
- `docs/spec.md`: `update` → `edit` の記載を更新
