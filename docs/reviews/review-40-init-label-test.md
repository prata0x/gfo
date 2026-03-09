# gfo Review Report — Round 40: init / label / テスト精査

## 概要

- **レビュー日**: 2026-03-09
- **対象**:
  - `src/gfo/commands/init.py`
  - `src/gfo/commands/label.py`
  - `src/gfo/commands/milestone.py`
  - `src/gfo/commands/issue.py`
  - `src/gfo/commands/pr.py`
  - `src/gfo/commands/auth_cmd.py`
  - `src/gfo/cli.py`（引数定義確認）
  - `tests/test_commands/test_label.py`
  - `tests/test_commands/test_init.py`
  - `tests/test_commands/test_issue.py`
  - `tests/test_commands/conftest.py`

- **発見事項**: 新規 3 件（重大 0 / 中 1 / 軽微 2）

---

## エージェントレビューで誤報された項目（問題なし確認）

| 確認項目 | 結果 |
|---------|------|
| `label.py` L30 — `{args.color}` vs `{color}` 表示 | OK — 元の入力値を表示する方がユーザーにとって分かりやすい。args.color は意図通り |
| `test_label.py` L191-192 内部インポートが冗長 | NG → R40-02 で修正（ファイル先頭に `pytest`/`ConfigError` がなく必要なのは本物）|
| `handle_list`（label/milestone）に `limit` 未渡し | OK — cli.py で `label list`/`milestone list` に `--limit` 未定義のため args.limit がない。設計通り |
| `pr.py` handle_merge/close に出力なし | OK — 成功した場合に例外を投げないのが仕様。追加出力は設計判断事項でバグではない |
| `auth_cmd.py` handle_status で `fmt` 未使用 | OK — auth status は固定フォーマット出力の設計。意図通り |
| `init.py` L99 service_type の None ガード冗長 | OK — 型注釈上の絞り込みとして許容 |

---

## 新規発見事項

---

### [R40-01] 🟡 `init.py` L51-55 — 存在しない `--owner/--repo` オプションをエラーメッセージで案内

- **ファイル**: `src/gfo/commands/init.py` L51-55
- **現在のコード**:
  ```python
  except (GitCommandError, DetectionError) as e:
      raise ConfigError(
          f"Could not detect repository from remote URL: {e} "
          "Please ensure you're in a git repository with an origin remote configured, "
          "or use --owner/--repo options."
      ) from e
  ```
- **CLI 定義** (`cli.py` L48-53):
  ```python
  init_parser.add_argument("--non-interactive", action="store_true")
  init_parser.add_argument("--type")
  init_parser.add_argument("--host")
  init_parser.add_argument("--api-url")
  init_parser.add_argument("--project-key")
  # --owner / --repo は定義されていない
  ```
- **説明**: エラーメッセージが `--owner/--repo options` を使うよう案内しているが、`gfo init` にこれらのオプションは定義されていない。ユーザーが案内通りに `gfo init --non-interactive --type github --host github.com --owner foo` と実行すると `error: unrecognized arguments: --owner` になる。
- **推奨修正**:
  ```python
  except (GitCommandError, DetectionError) as e:
      raise ConfigError(
          f"Could not detect repository from remote URL: {e} "
          "Please ensure you're in a git repository with an origin remote configured."
      ) from e
  ```

---

### [R40-02] 🟢 `test_label.py` L191-192, L200-201 — テスト関数内の非標準インポート

- **ファイル**: `tests/test_commands/test_label.py` L189-205
- **現在のコード**:
  ```python
  def test_invalid_color_raises_config_error(self, sample_config):
      from gfo.exceptions import ConfigError
      import pytest
      args = make_args(name="bug", color="xyz123", description=None)
      with _patch_all(sample_config, self.adapter), \
           pytest.raises(ConfigError, match="Invalid color"):
          label_cmd.handle_create(args, fmt="table")

  def test_double_hash_color_raises_config_error(self, sample_config):
      from gfo.exceptions import ConfigError
      import pytest
      args = make_args(name="bug", color="##ff0000", description=None)
      with _patch_all(sample_config, self.adapter), \
           pytest.raises(ConfigError, match="Invalid color"):
          label_cmd.handle_create(args, fmt="table")
  ```
- **説明**: `pytest` と `ConfigError` がファイルの先頭に import されておらず、2つのテスト関数内でローカルインポートしている。Python の慣例ではモジュールレベルでインポートすべき。
- **推奨修正**: `test_label.py` 先頭に以下を追加し、関数内インポートを削除する:
  ```python
  import pytest
  from gfo.exceptions import ConfigError
  ```

---

### [R40-03] 🟢 テスト — R40-01〜02 の修正確認テスト欠落

- **ファイル**: `tests/test_commands/test_init.py`
- **説明**:
  - R40-01: `_handle_non_interactive` でリモート URL 取得失敗時のエラーメッセージに `--owner` が含まれないことの確認テスト
- **推奨修正**: R40-01 修正後に対応テストを追加する。

---

## 全問題サマリー（R40）

| ID | 重大度 | ファイル | 概要 | 状態 |
|----|--------|---------|------|------|
| **R40-01** | 🟡 中 | `init.py` L51-55 | 存在しない `--owner/--repo` をエラーメッセージで案内 | ✅ 修正済み |
| **R40-02** | 🟢 軽微 | `test_label.py` L191-201 | テスト関数内の非標準インポート | ✅ 修正済み |
| **R40-03** | 🟢 軽微 | `test_init.py` | R40-01 の修正確認テストなし | ✅ 修正済み |

---

## 推奨アクション（優先度順）

1. **[R40-01]** `init.py` エラーメッセージから `--owner/--repo options` を削除
2. **[R40-02]** `test_label.py` インポートをファイル先頭に移動
3. **[R40-03]** エラーメッセージ確認テストを追加

## 修正コミット（R40）

| コミット | 修正内容 |
|---------|---------|
| 53a06bd | R40-01〜03 — init エラーメッセージ修正・test_label インポート整理・テスト追加 |
