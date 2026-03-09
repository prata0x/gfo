# gfo Review Report — Round 29: detect / config / cli / output / git_util 精査

## 概要

- **レビュー日**: 2026-03-09
- **対象**:
  - `src/gfo/detect.py`
  - `src/gfo/config.py`
  - `src/gfo/cli.py`
  - `src/gfo/output.py`
  - `src/gfo/git_util.py`
  - `tests/test_detect.py`
  - `tests/test_config.py`
  - `tests/test_output.py`
  - `tests/test_cli.py`

- **発見事項**: 新規 5 件（重大 0 / 中 1 / 軽微 4）

---

## エージェントレビューで誤報された項目（問題なし確認）

| 確認項目 | 結果 |
|---------|------|
| `_parse_url` のポート番号処理 | OK — `_SSH_URL_RE` の host グループが `[^/:]+` で `:` を除外するため `host` にポートは含まれない。`test_ssh_with_port` で検証済み |
| `git_checkout_branch` の 2 回目 checkout がサイレント失敗 | OK — 2 回目の `run_git` が失敗した場合の `GitCommandError` は呼び出し元に正常伝搬する |
| `resolve_project_config` の空文字列チェック | OK — `if not saved_type` は空文字列を正しく検出する |
| Azure DevOps エラーメッセージの不正確性 | 許容 — `if not organization or not project` は両方 None の場合も正しくエラーを送出する |

---

## 新規発見事項

---

### [R29-01] 🟡 `cli.py` L22-27 — `_positive_int` が非整数入力で不統一なエラーメッセージを出す

- **ファイル**: `src/gfo/cli.py` L22-27
- **現在のコード**:
  ```python
  def _positive_int(value: str) -> int:
      ivalue = int(value)           # "abc" → ValueError（未キャッチ）
      if ivalue <= 0:
          raise argparse.ArgumentTypeError(f"{value} is not a positive integer")
      return ivalue
  ```
- **説明**: `"abc"` のような非整数文字列を渡すと `int()` が `ValueError` を送出し、argparse は "invalid _positive_int value: 'abc'" という機械的なエラーを表示する。一方 `"0"` は `ArgumentTypeError` によりカスタムメッセージが表示される。入力種別によってエラーメッセージのスタイルが異なる。
- **推奨修正**: `int(value)` を try-except で囲み、`ValueError` を `ArgumentTypeError` として統一する。

---

### [R29-02] 🟢 `test_config.py` L416 — テスト関数名に typo `shost`

- **ファイル**: `tests/test_config.py` L416
- **現在のコード**:
  ```python
  def test_resolve_only_shost_in_git_config():
  ```
- **説明**: `shost` は `host` の typo。対応する `test_resolve_only_stype_in_git_config()` と命名が不揃い。
- **推奨修正**: `test_resolve_only_host_in_git_config` に改名する。

---

### [R29-03] 🟢 `config.py` L64 — `load_user_config` が `PermissionError` のみキャッチ

- **ファイル**: `src/gfo/config.py` L58-65
- **現在のコード**:
  ```python
  except PermissionError as e:
      raise ConfigError(f"Permission denied reading config file {path}: {e}") from e
  ```
- **説明**: `PermissionError` は `OSError` のサブクラスだが、`IsADirectoryError`（設定パスがディレクトリの場合）や他の `OSError` サブクラスはキャッチされず、未処理の OS 例外がユーザーに見える。
- **推奨修正**: `except PermissionError` を `except OSError` に広げ、エラーメッセージを汎化する。

---

### [R29-04] 🟢 `tests/test_detect.py` — Forgejo 旧版（source_url）の検出テストなし

- **ファイル**: `tests/test_detect.py`
- **説明**: `detect.py` L222-224 の旧版 Forgejo 検出（`"forgejo" in source_url.lower()`）に対するテストが存在しない。新しい `"forgejo"` キーを持つバージョンのテストはあるが、`source_url` パスは未テスト。
- **推奨修正**: `source_url` に "forgejo" を含む JSON を返すテストを追加する。

---

### [R29-05] 🟢 `tests/test_cli.py` — `_positive_int` のエラーパスのテストなし

- **ファイル**: `tests/test_cli.py`
- **説明**: `_positive_int` に対して `0`、負値、非整数文字列を渡した場合のエラー動作のテストがない。
- **推奨修正**: R29-01 の修正後にテストを追加する。

---

## 全問題サマリー（R29）

| ID | 重大度 | ファイル | 概要 | 状態 |
|----|--------|---------|------|------|
| **R29-01** | 🟡 中 | `cli.py` L22 | `_positive_int` 非整数入力でエラーメッセージ不統一 | ✅ 修正済み |
| **R29-02** | 🟢 軽微 | `test_config.py` L416 | テスト名 typo `shost` → `host` | ✅ 修正済み |
| **R29-03** | 🟢 軽微 | `config.py` L64 | `load_user_config` が `PermissionError` のみキャッチ | ✅ 修正済み |
| **R29-04** | 🟢 軽微 | `test_detect.py` | Forgejo 旧版 source_url 検出テストなし | ✅ 修正済み |
| **R29-05** | 🟢 軽微 | `test_cli.py` | `_positive_int` エラーパステストなし | ✅ 修正済み |

---

## 推奨アクション（優先度順）

1. ~~**[R29-01]**~~ ✅ 修正済み
2. ~~**[R29-02]**~~ ✅ 修正済み
3. ~~**[R29-03]**~~ ✅ 修正済み
4. ~~**[R29-04]**~~ ✅ 修正済み
5. ~~**[R29-05]**~~ ✅ 修正済み

## 修正コミット（R29）

| コミット | 修正内容 |
|---------|---------|
| （次のコミット） | R29-01〜05 — _positive_int エラー統一・load_user_config OSError・テスト追加 |
