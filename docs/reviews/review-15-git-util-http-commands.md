# gfo Review Report — Round 15: git_util / http / commands / adapter 品質

## 概要
- レビュー日: 2026-03-09
- 対象: `git_util.py`, `http.py`, `commands/pr.py`, `commands/issue.py`, `commands/init.py`, `auth_cmd.py`, `adapter/gogs.py`, `adapter/forgejo.py`, `tests/test_azure_devops.py`
- 発見事項: 重大 0 / 中 6 / 軽微 5

---

## 既知課題の現状

| ID | 状態 | 現在の実装 |
|----|------|-----------|
| R11-01+R9-07 | **未修正** | `git_util.py` L14-16, `detect.py` L19-21 に同一関数 |
| R11-02 | **未修正** | `http.py` `request()` と `get_absolute()` でリトライループ重複 |
| R11-03 | **未修正** | `commands/pr.py` L63 `git_checkout_new_branch` でブランチ既存時エラー |
| R14-01 | **未修正** | `commands/init.py` L122 対話モードで `service_type` 無検証 |

---

## 新規発見事項

---

### [R15-01] 🟡 `commands/issue.py` — `handle_create` が `resolve_project_config()` を二重呼び出し

- **ファイル**: `src/gfo/commands/issue.py` L26-47
- **説明**: `handle_list` 等は `get_adapter()` を使うが、`handle_create` は `resolve_project_config()` と `create_adapter(config)` を直接呼び出している。`get_adapter()` が内部で `resolve_project_config()` を呼ぶため、設定解決が重複。また他のハンドラとスタイルが不一統一。
- **影響**: 設定解決が冗長に実行される。コードの一貫性が低下。
- **推奨修正**: `get_adapter()` のシグネチャを変えずに `handle_create` も `get_adapter()` + 直接 config 参照に統一する（または `get_adapter_with_config()` ヘルパーを追加）。

---

### [R15-02] 🟡 `commands/init.py` L122 — 対話モードで `service_type` を検証しない（R14-01 詳細）

- **ファイル**: `src/gfo/commands/init.py` L122-124
- **現在のコード**:
  ```python
  service_type = input("Service type (github/gitlab/bitbucket/...): ").strip()
  if not service_type:
      raise ConfigError("service_type cannot be empty.")
  # ← 有効値チェックなし
  ```
- **非インタラクティブモード** (L38-42) では `_VALID_SERVICE_TYPES` チェックが実装済み。
- **推奨修正**:
  ```python
  service_type = input("Service type (github/gitlab/bitbucket/...): ").strip()
  if not service_type:
      raise ConfigError("service_type cannot be empty.")
  if service_type not in _VALID_SERVICE_TYPES:
      valid = ", ".join(sorted(_VALID_SERVICE_TYPES))
      raise ConfigError(f"Unknown service type {service_type!r}. Valid: {valid}")
  ```

---

### [R15-03] 🟡 `http.py` L169-182 — `Retry-After` の RFC 7231 日時形式を無視

- **ファイル**: `src/gfo/http.py` L169-182
- **現在のコード**:
  ```python
  try:
      result = int(value)
  except ValueError:
      return default  # 日時形式は default 60 秒を返す
  ```
- **影響**: `Retry-After: Mon, 09 Mar 2026 15:30:00 GMT` 形式のレスポンスに対して 60 秒待機してしまい、過長または過短な待機になる。
- **推奨修正**: `email.utils.parsedate_to_datetime()` を使って RFC 7231 日時をパースし、現在時刻との差分を待機秒数にする。

---

### [R15-04] 🟡 `git_util.py` L14-16 / `detect.py` L19-21 — `_mask_credentials` 重複定義（R11-01+R9-07 詳細）

- **ファイル**: `src/gfo/git_util.py` L14-16, `src/gfo/detect.py` L19-21
- **現在の状態**: 完全に同一のコードが 2 箇所に存在。正規表現 `r"://[^@\s]+@"` は `@` を含むパスワード（例: `user:p@ss@host`）で最初の `@` でマッチが終わり、パスワードの残りが露出。
- **推奨修正**:
  1. `detect.py` の `_mask_credentials` を削除し、`git_util.py` からインポートする
  2. 正規表現を `r"://[^/\s]*@"` に改善（パスの直前・空白の前まで貪欲にマッチ）

---

### [R15-05] 🟡 `commands/pr.py` L63 — PR checkout でブランチ既存時クラッシュ（R11-03 詳細）

- **ファイル**: `src/gfo/commands/pr.py` L63, `src/gfo/git_util.py` L90-94
- **現在のコード**:
  ```python
  gfo.git_util.git_checkout_new_branch(pr.source_branch)
  # git checkout -b {branch} FETCH_HEAD → ブランチ既存で GitCommandError
  ```
- **推奨修正**: `git_util.py` にフォールバック付き関数を追加:
  ```python
  def git_checkout_branch(branch: str, start: str = "FETCH_HEAD", cwd: str | None = None) -> None:
      """ブランチが存在しなければ新規作成、存在すれば既存ブランチにスイッチ。"""
      try:
          run_git("checkout", "-b", branch, start, cwd=cwd)
      except GitCommandError:
          run_git("checkout", branch, cwd=cwd)
  ```
  `commands/pr.py` L63 を `git_checkout_branch` に変更。

---

### [R15-06] 🟡 `adapter/gogs.py` L20-23 — `_web_url()` がAPIパスを含むベースURLを想定していない

- **ファイル**: `src/gfo/adapter/gogs.py` L20-23
- **現在のコード**:
  ```python
  parsed = urllib.parse.urlparse(self._client.base_url)
  return f"{parsed.scheme}://{parsed.hostname}" + (f":{parsed.port}" if parsed.port else "")
  ```
  `base_url` が `https://gogs.example.com/api/v1` の場合、`hostname` = `gogs.example.com`、パスは無視されるため `https://gogs.example.com` が返り正しく機能する。ただしコメントがなく意図が不明瞭。
- **影響**: 機能上は問題ない。ただし `base_url` が変則的な形式の場合に誤動作の可能性。
- **推奨修正**: コメントで意図を明示する。

---

### [R15-07] 🟢 `adapter/forgejo.py` — 実装が `service_name` のみでコメントなし

- **ファイル**: `src/gfo/adapter/forgejo.py`
- **推奨**: Forgejo が Gitea の fork であり API 互換性が高いためこの継承構造であることをモジュール docstring に記載。

---

### [R15-08] 🟢 `test_azure_devops.py` — fixture の依存が暗黙的（軽微）

- conftest.py で定義された `azure_devops_adapter` が暗黙的に使用されている。機能上は問題ない。

---

### [R15-09] 🟢 `auth_cmd.py` L60 — 区切り線長さ

- `print("-" * len(header))` は文字数ベースのため、全角文字を含む header では視覚的に幅が合わない可能性があるが、現状の header は ASCII のみのため実害なし。

---

### [R15-10] 🟢 `detect.py` — `_mask_credentials()` 二重マスクの可能性（軽微）

- エラーメッセージが一度マスク済みの場合、再度 `_mask_credentials()` を通すと `://***@` が `://***@` のままになり問題なし（冪等）。実害なし。

---

## 全問題サマリー（R15 新規）

| ID | 重大度 | ファイル | 概要 |
|----|--------|---------|------|
| **R15-01** | 🟡 中 | `commands/issue.py` | `handle_create` で設定解決が二重 |
| **R15-02** | 🟡 中 | `commands/init.py` L122 | 対話モード `service_type` 無検証 |
| **R15-03** | 🟡 中 | `http.py` L169-182 | Retry-After RFC 日時形式を無視 |
| **R15-04** | 🟡 中 | `git_util.py` + `detect.py` | `_mask_credentials` 重複・正規表現不完全 |
| **R15-05** | 🟡 中 | `commands/pr.py` L63 | ブランチ既存時 PR checkout クラッシュ |
| **R15-06** | 🟡 中 | `adapter/gogs.py` L20 | `_web_url()` 意図不明瞭 |
| **R15-07** | 🟢 軽微 | `adapter/forgejo.py` | docstring 欠落 |
| **R15-08** | 🟢 軽微 | `test_azure_devops.py` | fixture 依存が暗黙的 |
| **R15-09** | 🟢 軽微 | `auth_cmd.py` L60 | 区切り線長さが全角非対応 |
| **R15-10** | 🟢 軽微 | `detect.py` | `_mask_credentials` 二重マスク（冪等で実害なし） |

---

## 推奨アクション（優先度順）

### 即時対応

1. **[R15-04/R11-01+R9-07]** `detect.py` の `_mask_credentials` を削除し `git_util.py` からインポート。正規表現を `r"://[^/\s]*@"` に改善。
2. **[R15-05/R11-03]** `git_util.py` に `git_checkout_branch()` 追加、`commands/pr.py` で使用。
3. **[R15-02/R14-01]** `commands/init.py` L122 に `_VALID_SERVICE_TYPES` チェック追加。

### 設計変更

4. **[R15-03]** `http.py` — Retry-After の RFC 日時形式対応（`email.utils` 使用）。
5. **[R11-02]** `http.py` — リトライループを共通メソッドに抽出。
6. **[R15-01]** `commands/issue.py` — `handle_create` を `get_adapter()` パターンに統一。
