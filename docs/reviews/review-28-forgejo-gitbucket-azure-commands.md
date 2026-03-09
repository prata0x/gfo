# gfo Review Report — Round 28: forgejo / gitbucket / azure_devops / commands 精査

## 概要

- **レビュー日**: 2026-03-09
- **対象**:
  - `src/gfo/adapter/forgejo.py`
  - `src/gfo/adapter/gitbucket.py`
  - `src/gfo/adapter/azure_devops.py`
  - `src/gfo/commands/issue.py`
  - `src/gfo/commands/pr.py`
  - `src/gfo/commands/label.py`
  - `src/gfo/commands/milestone.py`
  - `tests/test_adapters/test_forgejo.py`
  - `tests/test_adapters/test_gitbucket.py`
  - `tests/test_adapters/test_azure_devops.py`
  - `tests/test_commands/test_issue.py`
  - `tests/test_commands/test_pr.py`
  - `tests/test_commands/test_label.py`

- **発見事項**: 新規 6 件（重大 0 / 中 1 / 軽微 5）

---

## エージェントレビューで誤報された項目（問題なし確認）

| 確認項目 | 結果 |
|---------|------|
| WIQL API の `$top` をクエリパラメータで渡している | OK — Azure DevOps WIQL API は `$top` をクエリパラメータとして受け付ける仕様。現実装は正しい |
| `paginate_top_skip` の `limit=0` が 30 件上限になる | OK — `if limit > 0` 条件による早期終了がスキップされ、最終ページに達するまで全件収集される。`limit=0` は正しく全件取得として動作する |
| `if not args.title or not args.title.strip()` の AttributeError リスク | OK — 短絡評価により `args.title` が None/偽の場合 `.strip()` は呼ばれない |

---

## 新規発見事項

---

### [R28-01] 🟡 `commands/label.py` L26 — `lstrip("#")` が複数の `#` を削除するバグ

- **ファイル**: `src/gfo/commands/label.py` L26
- **現在のコード**:
  ```python
  color = color.lstrip("#")
  if not re.fullmatch(r"[0-9a-fA-F]{6}", color):
  ```
- **説明**: `str.lstrip(chars)` は文字列先頭から指定文字が続く限り全て削除する。`"##ff0000".lstrip("#")` は `"ff0000"` を返すため、`##ff0000` が有効な色として誤って受け入れられる。
- **影響**: `##ff0000` など `#` を複数持つ入力が不正にパスされ、アダプター側に `ff0000` として渡される。動作上は大きな問題にはならないが、バリデーションの意図と異なる。
- **推奨修正**: `removeprefix("#")` に変更（Python 3.9+。`#` が 1 つだけ取り除かれる）。

---

### [R28-02] 🟢 `adapter/azure_devops.py` L95-105 — `_to_issue()` に `updated_at` フィールドなし

- **ファイル**: `src/gfo/adapter/azure_devops.py` L95-105
- **説明**: R27-05 で `Issue` dataclass に `updated_at: str | None = None` を追加したが、`AzureDevOpsAdapter._to_issue()` はこれを設定していない。Azure DevOps の Work Items は `System.ChangedDate` フィールドで更新日時を返す。
- **影響**: 軽微。`updated_at` は `None` のままになる。他アダプターとの一貫性が欠ける。
- **推奨修正**: `updated_at=fields.get("System.ChangedDate")` を追加する。

---

### [R28-03] 🟢 `tests/test_commands/test_label.py` — color バリデーションテストなし

- **ファイル**: `tests/test_commands/test_label.py`
- **説明**: `handle_create` の color バリデーション（`label.py` L24-30）に対するテストが存在しない。以下のケースが未テスト：
  - 不正なカラーコード（例：`xyz123` → ConfigError）
  - `#` なしの有効 hex（例：`ff0000` → OK）
  - R28-01 の修正後: `##ff0000` → ConfigError
- **推奨修正**: バリデーションテストを追加する。

---

### [R28-04] 🟢 `tests/test_commands/test_issue.py` — 空タイトルのバリデーションテストなし

- **ファイル**: `tests/test_commands/test_issue.py`
- **説明**: `handle_create` の空タイトルチェック（`issue.py` L26-27）のテストがない。`None`、`""`、`"   "` のいずれも未テスト。
- **推奨修正**: 空・空白タイトルで ConfigError が送出されることを確認するテストを追加する。

---

### [R28-05] 🟢 `tests/test_commands/test_pr.py` — 空タイトルのバリデーションテストなし

- **ファイル**: `tests/test_commands/test_pr.py`
- **説明**: `handle_create` で `args.title=None` かつ `get_last_commit_subject()` が `""` を返した場合の ConfigError テストがない。
- **推奨修正**: git のコミット履歴からもタイトルを取得できない場合に ConfigError が送出されることを確認するテストを追加する。

---

### [R28-06] 🟢 `tests/test_adapters/test_azure_devops.py` — `_to_issue` の `updated_at` 検証なし

- **ファイル**: `tests/test_adapters/test_azure_devops.py`
- **説明**: R28-02 の修正（`updated_at` 追加）後に対応するテストが必要。`System.ChangedDate` が `updated_at` に正しくマッピングされることを確認するテストがない。
- **推奨修正**: R28-02 修正後にテストを追加する。

---

## 全問題サマリー（R28）

| ID | 重大度 | ファイル | 概要 | 状態 |
|----|--------|---------|------|------|
| **R28-01** | 🟡 中 | `label.py` L26 | `lstrip("#")` が複数 `#` を削除（バリデーション抜け） | 未修正 |
| **R28-02** | 🟢 軽微 | `azure_devops.py` L104 | `_to_issue()` の `updated_at` 未設定 | 未修正 |
| **R28-03** | 🟢 軽微 | `test_label.py` | color バリデーションテストなし | 未修正 |
| **R28-04** | 🟢 軽微 | `test_issue.py` | 空タイトルバリデーションテストなし | 未修正 |
| **R28-05** | 🟢 軽微 | `test_pr.py` | 空タイトルバリデーションテストなし | 未修正 |
| **R28-06** | 🟢 軽微 | `test_azure_devops.py` | `_to_issue` の `updated_at` テストなし | 未修正 |

---

## 推奨アクション（優先度順）

1. **[R28-01]** `label.py` — `lstrip("#")` を `removeprefix("#")` に修正
2. **[R28-02]** `azure_devops.py` — `_to_issue()` に `updated_at` を追加
3. **[R28-03]** `test_label.py` — color バリデーションテストを追加（R28-01 修正後）
4. **[R28-04/05]** テストカバレッジ追加（空タイトルバリデーション）
5. **[R28-06]** `test_azure_devops.py` — `updated_at` テストを追加（R28-02 修正後）
