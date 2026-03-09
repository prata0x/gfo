# gfo Review Report — Round 31: commands / base / exceptions 精査

## 概要

- **レビュー日**: 2026-03-09
- **対象**:
  - `src/gfo/commands/__init__.py`
  - `src/gfo/commands/release.py`
  - `src/gfo/commands/milestone.py`
  - `src/gfo/commands/repo.py`
  - `src/gfo/adapter/base.py`
  - `src/gfo/exceptions.py`
  - `tests/test_commands/test_release.py`
  - `tests/test_commands/test_milestone.py`
  - `tests/test_commands/test_repo.py`

- **発見事項**: 新規 4 件（重大 0 / 中 2 / 軽微 2）

---

## エージェントレビューで誤報された項目（問題なし確認）

| 確認項目 | 結果 |
|---------|------|
| `repo.py` `handle_view()` の `get_repository(None, None)` | OK — 設計上 `None` はデフォルト（`self._owner`/`self._repo` を使用）の意味であり意図的 |
| `base.py` `__init__` の `**kwargs` | OK — `BacklogAdapter`・`AzureDevOpsAdapter` などが `super().__init__()` に余分なキーを渡す際の吸収用として設計上必要 |
| `test_repo.py` のパッチパターン | 許容 — スタイル的な好みの問題で機能的問題なし |

---

## 新規発見事項

---

### [R31-01] 🟡 `commands/release.py` L25 — 空白のみの `title` が検証を通過する

- **ファイル**: `src/gfo/commands/release.py` L25
- **現在のコード**:
  ```python
  tag = (args.tag or "").strip()   # tag は strip 済み
  ...
  title = args.title or tag        # args.title = "   " は truthy → "   " がそのまま使われる
  ```
- **説明**: `args.title` が `"   "` （空白のみ）の場合、`or` の左辺が truthy となり `title = "   "` になる。アダプターに空白のみのタイトルが送信される。`tag` は `strip()` してから使うのに `title` は同等の処理がない。
- **推奨修正**: `title = (args.title or "").strip() or tag`

---

### [R31-02] 🟡 `commands/milestone.py` L21-25 — 空白チェック後に strip されていない `args.title` をアダプターに渡す

- **ファイル**: `src/gfo/commands/milestone.py` L21-25
- **現在のコード**:
  ```python
  if not args.title.strip():          # "  v1.0  " は通過
      raise ConfigError("title must not be empty.")
  adapter.create_milestone(
      title=args.title,               # "  v1.0  " がそのまま送信される
  ```
- **説明**: 空白チェックに `strip()` を使っているが、検証通過後のアダプター呼び出しでは元の `args.title`（strip 前）を使っている。`"  v1.0  "` のような前後に空白を持つタイトルがそのまま API に送信される。
- **推奨修正**: `title = args.title.strip()` をチェック前に行い、その `title` を使う。

---

### [R31-03] 🟢 `tests/test_commands/test_release.py` — 空白のみ `title` のテストなし

- **ファイル**: `tests/test_commands/test_release.py`
- **説明**: `args.title = "   "` のとき `title = "   "` になる問題（R31-01）のテストがない。
- **推奨修正**: R31-01 修正後にテストを追加する。

---

### [R31-04] 🟢 `tests/test_commands/test_milestone.py` — 空白 `title` の strip テストなし

- **ファイル**: `tests/test_commands/test_milestone.py`
- **説明**: R31-02 の修正（strip 後の値をアダプターに渡す）を確認するテストがない。
- **推奨修正**: `title="  v1.0  "` を渡した場合にアダプターへ `title="v1.0"` として渡されることを確認するテストを追加する。

---

## 全問題サマリー（R31）

| ID | 重大度 | ファイル | 概要 | 状態 |
|----|--------|---------|------|------|
| **R31-01** | 🟡 中 | `release.py` L25 | 空白のみ title が通過 | ✅ 修正済み |
| **R31-02** | 🟡 中 | `milestone.py` L25 | strip 前の title をアダプターに渡す | ✅ 修正済み |
| **R31-03** | 🟢 軽微 | `test_release.py` | 空白 title テストなし | ✅ 修正済み |
| **R31-04** | 🟢 軽微 | `test_milestone.py` | strip 動作確認テストなし | ✅ 修正済み |

---

## 推奨アクション（優先度順）

1. ~~**[R31-01]**~~ ✅ 修正済み
2. ~~**[R31-02]**~~ ✅ 修正済み
3. ~~**[R31-03/04]**~~ ✅ 修正済み

## 修正コミット（R31）

| コミット | 修正内容 |
|---------|---------|
| （次のコミット） | R31-01〜04 — title strip 修正・テスト追加 |
