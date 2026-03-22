# Issues

ソースコードで再現を確認した課題の一覧。

## バグ / 規約違反

---

## I-1: `--jq ""` が複数箇所で無効入力として扱われず素通りする

Severity: **High**

該当箇所（`if jq:` で判定）:
- `src/gfo/commands/api.py:47`
- `src/gfo/commands/issue.py:323`
- `src/gfo/commands/pr.py:261`
- `src/gfo/commands/repo.py:276`
- `src/gfo/commands/repo.py:305`
- `src/gfo/commands/schema.py:487`
- `src/gfo/output.py:101`
- `src/gfo/output.py:116`

問題:
- 規約（`.claude/rules/09-config-auth.md`）では `if jq_expr is not None:` で判定し、空文字列は早期エラーにすることが求められている。
- `if jq:` だと空文字列が falsy で素通りし、jq フィルタが適用されない。
- `output.py` は全コマンドの出力パスなので影響範囲が広い。
- `collaborator.py` 等は正しく `if jq is not None:` を使っており、コードベース内で挙動が不統一。

---

## I-2: 書き込み / 削除ハンドラが成功時に何も出力しない

Severity: **High**

該当箇所（成功時の `print()` なし）:
- `src/gfo/commands/branch.py:32` — `handle_delete`
- `src/gfo/commands/ci.py:27` — `handle_cancel`
- `src/gfo/commands/collaborator.py:27` — `handle_add`
- `src/gfo/commands/collaborator.py:33` — `handle_remove`
- `src/gfo/commands/deploy_key.py:36` — `handle_delete`
- `src/gfo/commands/file.py:30` — `handle_put`
- `src/gfo/commands/file.py:49` — `handle_delete`
- `src/gfo/commands/tag.py:32` — `handle_delete`
- `src/gfo/commands/webhook.py:25` — `handle_delete`
- `src/gfo/commands/webhook.py:31` — `handle_test`

問題:
- 規約（`.claude/rules/02-adapter-common.md`）では、削除/書き込みハンドラは成功メッセージを `print()` することが求められている。
- CLI 利用者から見ると成功か無操作かを stdout で判別できない。
- 同じコマンド層内の `ci.py:handle_delete` や `_handle_workflow_enable/disable` は正しく出力しており不統一。

---

## I-3: `release list` の limit がフィルタ前に適用される

Severity: **Medium**

該当箇所:
- `src/gfo/commands/release.py:22`

問題:
- `adapter.list_releases(limit=args.limit)` で先に件数制限してから `draft` / `prerelease` フィルタを適用している。
- `gfo release list --limit 10 --draft` のように指定すると、10 件取得後にフィルタするため結果が 10 件未満になりうる。
- limit はフィルタ適用後に適用すべき。

---

## I-4: `argparse.FileType` が Python 3.14 で PendingDeprecationWarning を大量発生させている

Severity: **Medium**

該当箇所:
- `src/gfo/cli.py:208` — `--body-file`（pr create）
- `src/gfo/cli.py:356` — `--body-file`（issue create）
- `src/gfo/cli.py:620` — `--notes-file`（release create）
- `src/gfo/cli.py:650` — `--notes-file`（release edit）

問題:
- `type=argparse.FileType("r")` は Python 3.14 で deprecated。
- pytest 実行時に約 700 件の `PendingDeprecationWarning` が発生し、CI/開発時のノイズになっている。
- 将来の Python で削除された場合、CLI の引数定義が壊れる。

推奨:
- 引数ではファイルパス文字列を受け取り、パース後にハンドラ側で `open()` する形へ移行する。

---

## I-5: `file put` が `create_or_update_file()` の戻り値（commit SHA）を無視している

Severity: **Low**

該当箇所:
- `src/gfo/commands/file.py:40-46`

問題:
- `adapter.create_or_update_file()` は `str | None` を返す設計（commit SHA）だが、`handle_put` はこの戻り値を変数に代入していない。
- I-2 と合わせて対応すれば、成功メッセージに commit SHA を含められる。

---

## I-6: `GogsAdapter.create_or_update_file` の戻り値型が基底クラス契約より狭い

Severity: **Low**

該当箇所:
- `src/gfo/adapter/base.py:1139` — `-> str | None`
- `src/gfo/adapter/gogs.py:359-367` — `-> None`

問題:
- 基底クラスの `create_or_update_file` は `str | None` を返す契約だが、`GogsAdapter` では `-> None` に狭められている。
- 実装は `NotSupportedError` を送出するためランタイム障害には直結しにくいが、型契約としては不整合。
- 署名を基底クラスと同じ `str | None` に揃えるべき。

---

## 改善提案

### I-7: `_to_*` エラーハンドリングの共通化

Severity: **Medium**

該当箇所:
- `src/gfo/adapter/base.py` — `GitHubLikeAdapter` クラス内 17 メソッド

問題:
- `_to_pull_request`, `_to_issue`, `_to_repository` 等の変換メソッドで `try: ... except (KeyError, TypeError) as e: raise GfoError(...)` が 17 回同一パターンで重複している。

推奨:
- デコレータまたはヘルパーメソッドで例外ラップを自動化し、各 `_to_*` メソッドからボイラープレートを除去する。

---

### I-8: milestone 解決ロジックの重複

Severity: **Medium**

該当箇所:
- `src/gfo/adapter/github.py:156` — `_resolve_milestone_number()`
- `src/gfo/adapter/gitea.py:151` — `_resolve_milestone_id_by_title()`
- `src/gfo/adapter/gitlab.py:247` — `_resolve_milestone_id_by_title()`

問題:
- GitHub と Gitea は名前が異なるだけで実装ロジックが同一（`list_milestones()` をループしてタイトル一致を探索）。
- GitLab は API クエリ方式で異なるが、インターフェースは共通化可能。

推奨:
- `GitServiceAdapter` にデフォルト実装を追加し、GitLab のみオーバーライドする形に統一する。

---

### I-9: base.py の NotSupportedError デフォルト実装改善

Severity: **Medium**

該当箇所:
- `src/gfo/adapter/base.py` — 158 メソッドが NotSupportedError をデフォルトで raise
- `src/gfo/adapter/gogs.py` — 120 メソッドが NotSupportedError を重複して raise
- `src/gfo/adapter/gitbucket.py` — 72 メソッドが NotSupportedError を重複して raise

問題:
- base.py のデフォルト実装で既に NotSupportedError を raise するメソッドと、gogs.py / gitbucket.py で再定義しているメソッドの重複率が高い。
- gogs.py は 698 行中、大半が `raise NotSupportedError(...)` の 1 行メソッド。

推奨:
- base.py のデフォルト実装を整理し、サブクラスで再定義不要なメソッドを削減する。

---

### I-10: mypy strict モードの段階的導入

Severity: **Low**

該当箇所:
- `pyproject.toml` — `disallow_untyped_defs = false`

問題:
- 現在 mypy はパスしているが、型注釈のないメソッド定義がチェックされていない。
- `from __future__ import annotations` はほぼ全モジュール（62 中 58）で使用済みであり、strict 化の下地は整っている。未使用: `__init__.py`, `__main__.py`, `exceptions.py`, `adapter/__init__.py`。

推奨:
- `disallow_untyped_defs = true` に段階的に移行し、型安全性を向上させる。
