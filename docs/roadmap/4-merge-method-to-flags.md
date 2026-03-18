# merge-method-to-flags

## 概要

`pr merge --method merge/squash/rebase` を `pr merge --merge/--squash/--rebase` の個別フラグに変更する。
gh / glab / tea はいずれも個別フラグ方式を採用しており、gfo もこれに合わせる。

- **種別**: 破壊的変更
- **優先度**: Phase 1

## 現在の実装

```
gfo pr merge <number> --method merge   # デフォルト
gfo pr merge <number> --method squash
gfo pr merge <number> --method rebase
```

- CLI: `--method` choices=["merge", "squash", "rebase"] default="merge"
- ハンドラー: `args.method` で文字列取得 → `adapter.merge_pull_request(number, method=method)`
- auto-merge: `adapter.enable_auto_merge(number, merge_method=method)`

## 変更後

```
gfo pr merge <number>           # デフォルト: merge
gfo pr merge <number> --merge   # 明示的
gfo pr merge <number> --squash
gfo pr merge <number> --rebase
```

- CLI: `--merge`, `--squash`, `--rebase` の 3 フラグ（相互排他グループ、いずれも未指定時はデフォルト `merge`）
- ハンドラー: フラグから method 文字列を決定 → アダプター呼び出しは変更なし

## 実装手順

### 1. CLI パーサー定義 (`src/gfo/cli.py`)

```python
# 変更前
pr_merge.add_argument("--method", choices=["merge", "squash", "rebase"], default="merge", help=...)

# 変更後
_merge_method = pr_merge.add_mutually_exclusive_group()
_merge_method.add_argument("--merge", action="store_true", help=_("Create a merge commit"))
_merge_method.add_argument("--squash", action="store_true", help=_("Squash and merge"))
_merge_method.add_argument("--rebase", action="store_true", help=_("Rebase and merge"))
```

### 2. コマンドハンドラー (`src/gfo/commands/pr.py`)

`handle_merge` の method 取得ロジックを変更:

```python
# 変更前
method = args.method

# 変更後
if getattr(args, "squash", False):
    method = "squash"
elif getattr(args, "rebase", False):
    method = "rebase"
else:
    method = "merge"
```

アダプター呼び出し (`merge_pull_request`, `enable_auto_merge`) は変更なし。

### 3. テスト (`tests/test_commands/test_pr.py`)

- `TestHandleMerge`: `make_args(method="merge")` → `make_args(merge=False, squash=False, rebase=False)` 等に変更
- `TestHandleMergeAuto`: 同様に引数構造を変更
- squash / rebase フラグ指定時のテストケースを追加

### 4. ドキュメント更新

- `docs/commands.md`: `pr merge` セクションのオプション説明を更新
- `docs/commands.ja.md`: 同上
- `docs/cli-comparison.md`: 3.1 の merge オプション比較表で gfo 列を更新
- `docs/cli-alignment.md`: 完了後にステータス更新
