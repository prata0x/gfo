# gfo Review Report — Round 32: commands strip 一貫性精査

## 概要

- **レビュー日**: 2026-03-09
- **対象**:
  - `src/gfo/commands/repo.py`
  - `src/gfo/commands/label.py`
  - `src/gfo/commands/issue.py`
  - `src/gfo/commands/pr.py`
  - `tests/test_commands/test_repo.py`
  - `tests/test_commands/test_label.py`
  - `tests/test_commands/test_issue.py`
  - `tests/test_commands/test_pr.py`

- **発見事項**: 新規 5 件（重大 0 / 中 4 / 軽微 1）

---

## エージェントレビューで誤報された項目（問題なし確認）

| 確認項目 | 結果 |
|---------|------|
| `repo.py` `handle_clone` `args.repo` が None になる | OK — `repo` は argparse の positional argument として必須定義されているため None にならない |
| `issue.py`/`pr.py` `handle_close`/`handle_merge` に出力なし | OK — 設計上の選択。`close_issue` / `merge_pull_request` / `close_pull_request` はアダプター側で完結する操作であり、呼び出し成功時は例外なく終了する仕様 |
| `label.py` `description` のホワイトスペーステストなし | OK — `description` は省略可能な補足情報であり、ホワイトスペースを含んでも API に渡す値として有効 |

---

## 新規発見事項

---

### [R32-01] 🟡 `repo.py` L92 — `_parse_repo_arg` がホワイトスペースのみの owner/name を通過させる

- **ファイル**: `src/gfo/commands/repo.py` L89-96
- **現在のコード**:
  ```python
  def _parse_repo_arg(repo_arg: str) -> tuple[str, str]:
      parts = repo_arg.split("/", 1)
      if len(parts) != 2 or not parts[0] or not parts[1]:
          raise ConfigError(...)
      return parts[0], parts[1]
  ```
- **説明**: `parts[0]` / `parts[1]` の空文字チェックは `not ""` で True になるが、`"   "` などホワイトスペースのみは falsy にならないため通過する。`" /repo"` → owner `" "` がそのままアダプターに渡る。
- **推奨修正**:
  ```python
  owner, name = parts[0].strip(), parts[1].strip()
  if not owner or not name:
      raise ConfigError(...)
  return owner, name
  ```

---

### [R32-02] 🟡 `label.py` L22/33 — strip 検証後に strip 前の `args.name` をアダプターに渡す

- **ファイル**: `src/gfo/commands/label.py` L22, L33
- **現在のコード**:
  ```python
  if not args.name.strip():
      raise ConfigError("name must not be empty.")
  ...
  label = adapter.create_label(
      name=args.name,   # strip 前の値
  ```
- **説明**: `" bug "` は `args.name.strip()` でチェックを通過するが、`adapter.create_label` には `" bug "` がそのまま渡される。R31-02 と同じパターン。
- **推奨修正**: `name = args.name.strip()` をチェック前に行い、以降は `name` を使う。

---

### [R32-03] 🟡 `issue.py` L26/38 — strip 検証後に strip 前の `args.title` をアダプターに渡す

- **ファイル**: `src/gfo/commands/issue.py` L26, L38
- **現在のコード**:
  ```python
  if not args.title or not args.title.strip():
      raise ConfigError("--title must not be empty.")
  ...
  issue = adapter.create_issue(
      title=args.title,   # strip 前の値
  ```
- **説明**: `"  Bug Report  "` は検証を通過するが、アダプターに前後空白付きのタイトルが渡される。
- **推奨修正**: `title = args.title.strip() if args.title else ""` をチェック前に行い、以降は `title` を使う。

---

### [R32-04] 🟡 `pr.py` L26/29 — strip 検証後に strip されていない `title` をアダプターに渡す

- **ファイル**: `src/gfo/commands/pr.py` L25-29
- **現在のコード**:
  ```python
  title = args.title or gfo.git_util.get_last_commit_subject()
  if not title or not title.strip():
      raise ConfigError("Could not determine PR title. Use --title option.")
  pr = adapter.create_pull_request(
      title=title,   # strip されていない
  ```
- **説明**: `get_last_commit_subject()` が前後に空白を含む文字列を返すと、または `args.title` に空白が含まれると、strip されていない値がアダプターに渡る。
- **推奨修正**: `title = (args.title or gfo.git_util.get_last_commit_subject() or "").strip()` にして検証後の `title` をそのまま渡す。

---

### [R32-05] 🟢 テスト — R32-01〜04 の修正確認テストなし

- **ファイル**: `tests/test_commands/test_repo.py`, `test_label.py`, `test_issue.py`, `test_pr.py`
- **説明**: 各 strip 修正に対応するテストが不足している。
- **推奨修正**: R32-01〜04 修正後に対応テストを追加する。

---

## 全問題サマリー（R32）

| ID | 重大度 | ファイル | 概要 | 状態 |
|----|--------|---------|------|------|
| **R32-01** | 🟡 中 | `repo.py` L92 | `_parse_repo_arg` 空白 owner/name 通過 | ✅ 修正済み |
| **R32-02** | 🟡 中 | `label.py` L22/33 | strip 前の name をアダプターに渡す | ✅ 修正済み |
| **R32-03** | 🟡 中 | `issue.py` L26/38 | strip 前の title をアダプターに渡す | ✅ 修正済み |
| **R32-04** | 🟡 中 | `pr.py` L25/29 | strip されていない title をアダプターに渡す | ✅ 修正済み |
| **R32-05** | 🟢 軽微 | テスト各種 | strip 動作確認テストなし | ✅ 修正済み |

---

## 推奨アクション（優先度順）

1. ~~**[R32-01]**~~ ✅ 修正済み
2. ~~**[R32-02]**~~ ✅ 修正済み
3. ~~**[R32-03]**~~ ✅ 修正済み
4. ~~**[R32-04]**~~ ✅ 修正済み
5. ~~**[R32-05]**~~ ✅ 修正済み

## 修正コミット（R32）

| コミット | 修正内容 |
|---------|---------|
| （次のコミット） | R32-01〜05 — strip 一貫性修正・テスト追加 |
