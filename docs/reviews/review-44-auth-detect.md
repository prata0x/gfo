# gfo Review Report — Round 44: auth / detect 精査

## 概要

- **レビュー日**: 2026-03-09
- **対象**:
  - `src/gfo/auth.py`
  - `src/gfo/detect.py`
  - `tests/test_auth.py`
  - `tests/test_detect.py`

- **発見事項**: 新規 4 件（重大 0 / 中 1 / 軽微 3）

---

## エージェントレビューで誤報された項目（問題なし確認）

| 確認項目 | 結果 |
|---------|------|
| `detect.py` Azure DevOps org 抽出で `org = m.group("org") or ""` が曖昧 | OK — `not org` で None・空文字の両方を統一処理する意図的な設計。コメントあり |
| `detect.py` 正規表現で `port` がキャプチャされるが未使用 | OK — `port` は現行コードでは不要。パース精度向上のためキャプチャしているが利用しないことは問題ない |
| `detect.py` Backlog SSH で `path.lstrip("/")` が複数スラッシュを削除 | OK — SSH SCP URL では先頭スラッシュは一般的に 1 個であり、`lstrip` で複数を削除しても影響なし |
| `detect.py` `probe_unknown_host` で GitLab プローブが `ValueError` をキャッチしない | OK — `resp.json()` が失敗しても `status_code == 200` ブロック内で例外が伝播するのみ。その後の `except requests.RequestException` はキャッチせず次の分岐に進む設計 |
| `auth.py` `load_tokens` で `FileNotFoundError` と `OSError` の順序 | OK — `FileNotFoundError` は `OSError` のサブクラスであるため、先にキャッチする現実装は正しい |
| `auth.py` Unicode エスケープで `m.group()` vs `m.group(0)` | OK — どちらも同一。スタイルの問題でバグではない |
| `auth.py` `_write_credentials_toml` 小文字 `\u` | OK — TOML 仕様では `\u` は小文字 4 桁で定義。正しい |

---

## 新規発見事項

---

### [R44-01] 🟡 `auth.py` L152 — `get_auth_status()` で `seen_hosts` が env var 処理で未参照（重複エントリ発生）

- **ファイル**: `src/gfo/auth.py` L129-160
- **現在のコード**:
  ```python
  seen_hosts: set[str] = set()

  # credentials.toml のトークン
  for host in tokens:
      result.append({"host": host, ...})
      seen_hosts.add(host)          # ← 追加されるが...

  # 環境変数
  for service_type, env_var in _SERVICE_ENV_MAP.items():
      ...
      display_host = _SERVICE_DEFAULT_HOSTS.get(service_type, ...)
      result.append({"host": display_host, ...})  # ← seen_hosts を参照しない
  ```
- **説明**: `seen_hosts` は credentials.toml のホストを記録するために定義されているが、環境変数処理のループ内で参照されていない。例えば `github.com` が credentials.toml に存在し、かつ `GITHUB_TOKEN` 環境変数も設定されている場合、`get_auth_status()` が `github.com` エントリを2件返してしまう。
- **推奨修正**:
  ```python
  if display_host not in seen_hosts:
      result.append(
          {"host": display_host, "status": "configured", "source": f"env:{env_var}"}
      )
  ```

---

### [R44-02] 🟢 `auth.py` L71 — `save_token()` で二重 falsy チェック（冗長）

- **ファイル**: `src/gfo/auth.py` L71
- **現在のコード**:
  ```python
  if not token or not token.strip():
      raise AuthError(host, "Token must not be empty.")
  ```
- **説明**: `token` の型は `str`（`None` はありえない）。`not token` は `token == ""` と等価だが、`not token.strip()` だけで空文字・空白のみ両方をカバーできる。前半の `not token` は冗長。
- **推奨修正**:
  ```python
  if not token.strip():
      raise AuthError(host, "Token must not be empty.")
  ```

---

### [R44-03] 🟢 `tests/test_detect.py` L171-195 — Backlog テストで `owner` フィールドのアサート欠落

- **ファイル**: `tests/test_detect.py` L171-195
- **現在のコード**:
  ```python
  def test_backlog_no_git_suffix(self):
      r = detect_from_url("https://space.backlog.com/git/PROJECT/repo")
      assert r.service_type == "backlog"
      assert r.project == "PROJECT"   # owner をアサートしていない
      assert r.repo == "repo"

  def test_backlog_https(self):
      r = detect_from_url("https://space.backlog.com/git/PROJECT/repo.git")
      assert r.host == "space.backlog.com"
      assert r.project == "PROJECT"   # owner をアサートしていない
      assert r.repo == "repo"

  def test_backlog_ssh(self):
      r = detect_from_url("space@space.git.backlog.com:/PROJECT/repo.git")
      assert r.project == "PROJECT"   # owner をアサートしていない
      assert r.repo == "repo"
  ```
- **実装** (`detect.py` L134, L144): Backlog の両パスで `owner=project_key`（= `m.group("owner")`）を設定している。
- **説明**: `owner` が正しくセットされることを確認するアサートが欠落。
- **推奨修正**: 各テストに `assert r.owner == "PROJECT"` を追加。

---

### [R44-04] 🟢 テスト — R44-01 の修正確認テスト欠落

- **ファイル**: `tests/test_auth.py`
- **説明**: credentials.toml と環境変数に同一ホストが設定されている場合、重複エントリが発生しないことをテストするケースが存在しない。
- **推奨修正**: `test_get_auth_status_no_duplicate_when_env_and_file_overlap` テストを追加。

---

## 全問題サマリー（R44）

| ID | 重大度 | ファイル | 概要 | 状態 |
|----|--------|---------|------|------|
| **R44-01** | 🟡 中 | `auth.py` L152 | `get_auth_status()` で credentials.toml と env var の同一ホストが重複 | 未修正 |
| **R44-02** | 🟢 軽微 | `auth.py` L71 | `save_token()` で冗長な二重 falsy チェック | 未修正 |
| **R44-03** | 🟢 軽微 | `test_detect.py` L171-195 | Backlog テストで `owner` フィールドのアサート欠落 | 未修正 |
| **R44-04** | 🟢 軽微 | `test_auth.py` | R44-01 修正確認テスト欠落 | 未修正 |

---

## 推奨アクション（優先度順）

1. **[R44-01]** `auth.py` `get_auth_status()` で `seen_hosts` チェックを追加
2. **[R44-02]** `auth.py` `save_token()` の二重チェックを整理
3. **[R44-03]** `test_detect.py` Backlog テストに `owner` アサートを追加
4. **[R44-04]** `test_auth.py` に重複防止テストを追加

## 修正コミット（R44）

| コミット | 修正内容 |
|---------|---------|
| （次のコミット） | R44-01〜04 — get_auth_status 重複修正・save_token 簡略化・Backlog テスト補強 |
