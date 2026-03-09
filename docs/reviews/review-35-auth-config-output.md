# gfo Review Report — Round 35: auth / config / output 精査

## 概要

- **レビュー日**: 2026-03-09
- **対象**:
  - `src/gfo/auth.py`
  - `src/gfo/config.py`
  - `src/gfo/output.py`
  - `src/gfo/exceptions.py`
  - `src/gfo/cli.py`
  - `tests/test_auth.py`
  - `tests/test_config.py`
  - `tests/test_output.py`

- **発見事項**: 新規 4 件（重大 0 / 中 3 / 軽微 1）

---

## エージェントレビューで誤報された項目（問題なし確認）

| 確認項目 | 結果 |
|---------|------|
| `auth.py` トークン値がログに漏洩するリスク | OK — `get_auth_status()` はトークン値を返さない（`"status": "configured"` のみ）。resolve_token の戻り値は呼び出し元で HTTP ヘッダーに設定されるのみで、ログ出力なし |
| `auth.py` credentials.toml パスがエラーメッセージに露出 | OK — ファイルパス（`~/.config/gfo/credentials.toml`）はデバッグに有用な情報。秘密情報ではない |
| `config.py` `resolve_project_config` の条件ロジックが「逆」 | OK — `saved_type and saved_host` が True の場合にリモート URL 解析を試みる設計は正しい。コメントは補足説明として正確 |
| `cli.py` `NotSupportedError.web_url` が stdout に出力される | OK — 設計上の選択。web_url はユーザーが直接クリックできる URL として stdout に出力する意図 |
| `exceptions.py` `AuthError.host` が属性に格納されない | OK — `host` は `__init__` で使用するのみで `self.host` に格納する必要はない。キャッチ側で host を知る必要がある場合は message からパースできる |
| `auth.py` `_write_credentials_toml` の非 BMP 文字エスケープ | OK — Python の `str` は Unicode スカラー値を直接保持する。`\u{04x}` は BMP 内の制御文字のエスケープ用であり、BMP 外の文字（絵文字等）はそのまま UTF-8 で書き出して問題ない（TOML 1.0 は UTF-8 文字を raw で許可） |

---

## 新規発見事項

---

### [R35-01] 🟡 `auth.py` L116-123 — `load_tokens()` の `open()` が `OSError` を未捕捉

- **ファイル**: `src/gfo/auth.py` L113-123
- **現在のコード**:
  ```python
  def load_tokens() -> dict[str, str]:
      path = get_credentials_path()
      if not path.exists():
          return {}
      with open(path, "rb") as f:           # OSError が未捕捉
          try:
              data = tomllib.load(f)
          except tomllib.TOMLDecodeError as e:
              raise ConfigError(...) from e
      return data.get("tokens", {})
  ```
- **説明**: `path.exists()` で確認した後 `open()` するまでの間に TOCTOU 競合がある。また `PermissionError` など `OSError` 系の例外が unhandled でスタックトレースのまま伝播する。同様の問題は `config.py` の `load_user_config()` で R29-03 として修正済み（`except OSError`）だが `auth.py` では未修正。
- **推奨修正**:
  ```python
  def load_tokens() -> dict[str, str]:
      path = get_credentials_path()
      try:
          with open(path, "rb") as f:
              try:
                  data = tomllib.load(f)
              except tomllib.TOMLDecodeError as e:
                  raise ConfigError(f"Failed to parse credentials file {path}: {e}") from e
      except FileNotFoundError:
          return {}
      except OSError as e:
          raise ConfigError(f"Failed to read credentials file {path}: {e}") from e
      return data.get("tokens", {})
  ```

---

### [R35-02] 🟡 `config.py` L242 — `build_default_api_url` エラーメッセージの引数名が誤り

- **ファイル**: `src/gfo/config.py` L240-243
- **現在のコード**:
  ```python
  if not organization or not project:
      raise ConfigError(
          "Azure DevOps requires organization and project_key."
      )
  ```
- **説明**: エラーメッセージに `project_key` とあるが、この関数の引数名は `project`（`project_key` ではない）。ユーザーがエラーを見て `--project-key` オプションを探すが、実際の CLI 引数は `--project` となり混乱を招く。また、`organization` のみ欠けた場合と `project` のみ欠けた場合で同じメッセージが出るため、どちらを直すべきか分からない。
- **推奨修正**:
  ```python
  if not organization:
      raise ConfigError("Azure DevOps requires --organization.")
  if not project:
      raise ConfigError("Azure DevOps requires --project.")
  ```

---

### [R35-03] 🟡 `output.py` L71 — `None` フィールドが table/plain 形式で `"None"` と出力される

- **ファイル**: `src/gfo/output.py` L71
- **現在のコード**:
  ```python
  rows.append([_sanitize_for_table(str(d.get(f, ""))) for f in fields])
  ```
- **説明**: `d.get(f, "")` はフィールドが辞書に存在しない場合のみ `""` を返す。フィールドが存在して値が `None`（例：`Issue.updated_at`、`PullRequest.body`）の場合は `None` を返し、`str(None)` → `"None"` がテーブルに表示される。JSON 形式では `null` として正しく処理されているが（`json.dumps(..., default=str)` ではなく通常の JSON シリアライズ）、table/plain では統一されていない。
- **推奨修正**: `str(d.get(f) or "")` または `"" if val is None else str(val)` のヘルパーを使う。

---

### [R35-04] 🟢 テスト — R35-01〜03 の修正確認テストなし

- **ファイル**: `tests/test_auth.py`, `tests/test_config.py`, `tests/test_output.py`
- **説明**: 各修正に対応するテストが不足している。
  - R35-01: `load_tokens()` で `PermissionError` → `ConfigError` となることのテスト
  - R35-02: `organization` のみ欠けた場合と `project` のみ欠けた場合で異なるメッセージになることのテスト
  - R35-03: `None` フィールドを持つオブジェクトを table 形式で出力したとき空文字列になることのテスト
- **推奨修正**: R35-01〜03 修正後に対応テストを追加する。

---

## 全問題サマリー（R35）

| ID | 重大度 | ファイル | 概要 | 状態 |
|----|--------|---------|------|------|
| **R35-01** | 🟡 中 | `auth.py` L116-123 | `load_tokens()` の `OSError` 未捕捉 | 未修正 |
| **R35-02** | 🟡 中 | `config.py` L242 | エラーメッセージの引数名 `project_key` が誤り | 未修正 |
| **R35-03** | 🟡 中 | `output.py` L71 | `None` フィールドが table で `"None"` と出力 | 未修正 |
| **R35-04** | 🟢 軽微 | テスト各種 | R35-01〜03 の修正確認テストなし | 未修正 |

---

## 推奨アクション（優先度順）

1. **[R35-01]** `auth.py` — `load_tokens()` を `try/except FileNotFoundError / OSError` で包む
2. **[R35-02]** `config.py` — エラーメッセージを `organization` と `project` の個別チェックに分割
3. **[R35-03]** `output.py` — `str(d.get(f, ""))` を `None` セーフな変換に修正
4. **[R35-04]** テストを追加する（R35-01〜03 修正後）
