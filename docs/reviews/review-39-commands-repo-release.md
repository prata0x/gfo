# gfo Review Report — Round 39: commands 精査（repo / release）

## 概要

- **レビュー日**: 2026-03-09
- **対象**:
  - `src/gfo/commands/repo.py`
  - `src/gfo/commands/release.py`
  - `src/gfo/commands/` 配下すべて（issue / label / milestone / pr / auth_cmd / init）
  - `src/gfo/cli.py`（引数定義確認）
  - `src/gfo/exceptions.py`、`src/gfo/http.py`（追加確認）

- **発見事項**: 新規 3 件（重大 0 / 中 1 / 軽微 2）

---

## エージェントレビューで誤報された項目（問題なし確認）

| 確認項目 | 結果 |
|---------|------|
| `issue.py` L26 `(args.title or "")` が冗長 | OK — `--title` は required=True だが、防御的プログラミングとして許容 |
| `git_checkout_branch` ローカライズ問題（R34 修正済み） | OK — `str(e).lower()` で大文字小文字を無視済み。英語 git メッセージを前提とする設計 |
| `backlog.py` `create_issue()` 内の API 呼び出し効率 | OK — `_project_id` キャッシュ機構が既に存在。実問題なし |
| `NotSupportedError.web_url` 空文字チェック | OK — 実コードでは常に非空文字列が渡される。設計上問題なし |
| `init.py` owner/repo 空文字設定 | OK — リポジトリ検出失敗時のデフォルト。設定後に実際のコマンドが実行される想定 |
| `http.py` `paginate_top_skip` の `result_key="value"` | OK — Azure DevOps のみが使用するため問題なし |

---

## 新規発見事項

---

### [R39-01] 🟡 `repo.py` L25 — `handle_list` が `--owner` 引数を無視

- **ファイル**: `src/gfo/commands/repo.py` L22-26
- **現在のコード**:
  ```python
  def handle_list(args: argparse.Namespace, *, fmt: str) -> None:
      """gfo repo list のハンドラ。"""
      adapter = get_adapter()
      repos = adapter.list_repositories(limit=args.limit)   # ← owner を渡していない
      output(repos, fmt=fmt, fields=["name", "full_name", "private", "description"])
  ```
- **CLI 定義** (`cli.py` L109):
  ```python
  repo_list.add_argument("--owner")   # 定義済みだが未使用
  ```
- **説明**: `gfo repo list --owner <owner>` とオプションが定義されているにもかかわらず、ハンドラが `args.owner` を `adapter.list_repositories()` に渡していない。`--owner` を指定しても自分のリポジトリ一覧が返され、機能しない。`GitServiceAdapter.list_repositories()` の基底クラス定義には `owner: str | None = None` がある。
- **推奨修正**:
  ```python
  def handle_list(args: argparse.Namespace, *, fmt: str) -> None:
      """gfo repo list のハンドラ。"""
      adapter = get_adapter()
      repos = adapter.list_repositories(
          owner=getattr(args, "owner", None),
          limit=args.limit,
      )
      output(repos, fmt=fmt, fields=["name", "full_name", "private", "description"])
  ```

---

### [R39-02] 🟢 `release.py` L23 — エラーメッセージが `--tag` と表記されているが positional 引数

- **ファイル**: `src/gfo/commands/release.py` L21-23
- **現在のコード**:
  ```python
  tag = (args.tag or "").strip()
  if not tag:
      raise ConfigError("--tag is required. Use --tag <tag> to specify a release tag.")
  ```
- **CLI 定義** (`cli.py` L128):
  ```python
  release_create.add_argument("tag")   # positional 引数（--tag ではない）
  ```
- **説明**: `tag` は `--tag` フラグではなく positional 引数（`gfo release create <tag>`）として定義されている。エラーメッセージの `"--tag is required. Use --tag <tag>..."` はユーザーを誤解させる。空文字 `""` を渡した場合にのみ発生するエッジケース。
- **推奨修正**:
  ```python
  tag = (args.tag or "").strip()
  if not tag:
      raise ConfigError("tag must not be empty. Use 'gfo release create <tag>'.")
  ```

---

### [R39-03] 🟢 テスト — R39-01〜02 の修正確認テストなし

- **ファイル**: `tests/test_adapters/` 配下、`tests/test_cli.py`
- **説明**:
  - R39-01: `handle_list` に `owner` が渡されることを確認するテスト
  - R39-02: 空文字 `tag` でのエラーメッセージが正しいことのテスト
- **推奨修正**: R39-01〜02 修正後に対応テストを追加する。

---

## 全問題サマリー（R39）

| ID | 重大度 | ファイル | 概要 | 状態 |
|----|--------|---------|------|------|
| **R39-01** | 🟡 中 | `repo.py` L25 | `handle_list` が `--owner` を無視 | ✅ 修正済み |
| **R39-02** | 🟢 軽微 | `release.py` L23 | エラーメッセージが `--tag` と誤表記 | ✅ 修正済み |
| **R39-03** | 🟢 軽微 | テスト各種 | R39-01〜02 の修正確認テストなし | ✅ 修正済み |

---

## 推奨アクション（優先度順）

1. ~~**[R39-01]**~~ ✅ 修正済み
2. ~~**[R39-02]**~~ ✅ 修正済み
3. ~~**[R39-03]**~~ ✅ 修正済み

## 修正コミット（R39）

| コミット | 修正内容 |
|---------|---------|
| （R39-01/02 修正コミット） | src/gfo/commands/repo.py — handle_list に owner 引数追加 |
| （R39-01/02 修正コミット） | src/gfo/commands/release.py — エラーメッセージ修正 |
| 7eeaae6 | R39-03 — repo list --owner テストと release 空タグエラーメッセージテストを追加 |
