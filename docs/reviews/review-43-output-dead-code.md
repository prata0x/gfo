# gfo Review Report — Round 43: http / config / output / exceptions 精査

## 概要

- **レビュー日**: 2026-03-09
- **対象**:
  - `src/gfo/http.py`
  - `src/gfo/config.py`
  - `src/gfo/output.py`
  - `src/gfo/exceptions.py`
  - `tests/test_http.py`
  - `tests/test_config.py`
  - `tests/test_output.py`
  - `tests/test_commands/test_release.py`

- **発見事項**: 新規 3 件（重大 0 / 中 0 / 軽微 3）

---

## エージェントレビューで誤報された項目（問題なし確認）

| 確認項目 | 結果 |
|---------|------|
| `config.py` L119 `if saved_type and saved_host:` の条件が逆 | OK — saved_type と saved_host **両方** 設定済みなら remote URL から owner/repo を取得し、未設定なら detect_service() を呼ぶ正しい設計。コメントが略式なだけ |
| `test_config.py` `test_resolve_git_config_does_not_call_detect_service` がフォールスポジティブ | OK — テストが正しく実装を反映しており、実装も正しい |
| `exceptions.py` `AuthError.__init__` の `if message:` が空文字列に対して誤動作 | OK — 型注釈 `str \| None` での慣例的パターン。空文字エラーメッセージより明示的デフォルトが優先される設計 |
| `output.py` `_field_str()` が JSON フォーマットで使われず一貫性を欠く | OK — JSON では None を null にする仕様（RFC 準拠）、table/plain では空文字に変換する設計。明示的な差別化 |
| `http.py` `_parse_retry_after()` の HTTP-date タイムゾーン不整合リスク | OK — RFC 7231 では HTTP-date は常に GMT。実装は正しい |

---

## 新規発見事項

---

### [R43-01] 🟢 `output.py` L97-98 — `format_json` 内の不要な中間変数（dead assignment）

- **ファイル**: `src/gfo/output.py` L95-99
- **現在のコード**:
  ```python
  def format_json(items: list) -> str:
      """JSON 形式にフォーマットする。"""
      dicts = [dataclasses.asdict(item) for item in items]
      data = dicts                              # ← data = dicts は不要
      return json.dumps(data, indent=2, ensure_ascii=False, default=str)
  ```
- **説明**: `data` は `dicts` の単純なエイリアスで、中間変数としての意味がない。変数を一本化することでコードが簡潔になる。
- **推奨修正**:
  ```python
  def format_json(items: list) -> str:
      """JSON 形式にフォーマットする。"""
      dicts = [dataclasses.asdict(item) for item in items]
      return json.dumps(dicts, indent=2, ensure_ascii=False, default=str)
  ```

---

### [R43-02] 🟢 `tests/test_output.py` — empty list + plain フォーマットのテスト欠落と dead branch

- **ファイル**: `tests/test_output.py`
- **説明（テスト欠落）**: カバレッジレポートで `output.py` L53 が未カバー。これは `fmt="plain"` かつ `items=[]` のパスで実行される `pass` 文。テストが存在しない。
  ```python
  # output.py L49-56（L53 が未カバー）
  if not items:
      if fmt == "json":
          print("[]")
      elif fmt == "plain":
          pass  # ← L53 未カバー
      else:
          print("No results found.")
      return
  ```
- **説明（dead branch）**: L242 の `else` ブランチは実行されない。`format_json` は常に JSON 配列（リスト）を返すため、`isinstance(parsed, list)` は常に True になる。
  ```python
  # test_output.py L242（else ブランチが dead code）
  item = parsed[0] if isinstance(parsed, list) else parsed
  ```
- **推奨修正**: empty + plain テストを追加し、dead branch を整理する:
  ```python
  def test_empty_list_plain_no_output(self, capsys):
      """空リストを plain フォーマットで出力すると stdout は空になる。"""
      output([], fmt="plain")
      captured = capsys.readouterr()
      assert captured.out == ""
  ```

---

### [R43-03] 🟢 `tests/test_commands/test_release.py` L79-83 — JSON format テストの dead branch

- **ファイル**: `tests/test_commands/test_release.py` L73-83
- **現在のコード**:
  ```python
  def test_json_format(self, sample_config, capsys):
      args = make_args(limit=10)
      with _patch_all(sample_config, self.adapter):
          release_cmd.handle_list(args, fmt="json")

      out = capsys.readouterr().out
      data = json.loads(out)
      if isinstance(data, list):
          assert data[0]["tag"] == "v1.0.0"
      else:
          assert data["tag"] == "v1.0.0"   # ← ここは実行されない
  ```
- **説明**: `output()` → `format_json()` は常に JSON 配列を返すため、`else` ブランチは実行されない。R43-02 と同一パターン。
- **推奨修正**:
  ```python
  data = json.loads(out)
  assert isinstance(data, list)
  assert data[0]["tag"] == "v1.0.0"
  ```

---

## 全問題サマリー（R43）

| ID | 重大度 | ファイル | 概要 | 状態 |
|----|--------|---------|------|------|
| **R43-01** | 🟢 軽微 | `output.py` L97-98 | `format_json` 内の不要な中間変数 `data = dicts` | ✅ 修正済み |
| **R43-02** | 🟢 軽微 | `test_output.py` | empty list + plain フォーマットのテスト欠落・dead branch | ✅ 修正済み |
| **R43-03** | 🟢 軽微 | `test_release.py` | JSON format テストの dead branch | ✅ 修正済み |

---

## 推奨アクション（優先度順）

1. **[R43-01]** `output.py` の `data = dicts` を削除
2. **[R43-02]** `test_output.py` に empty + plain テスト追加、dead branch 整理
3. **[R43-03]** `test_release.py` の JSON テスト dead branch を整理

## 修正コミット（R43）

| コミット | 修正内容 |
|---------|---------|
| 64d6cd8 | R43-01〜03 — output.py dead assignment 除去・テスト dead branch 整理・テスト追加 |
