# gfo Review Report — Round 34: gogs / git_util 精査

## 概要

- **レビュー日**: 2026-03-09
- **対象**:
  - `src/gfo/adapter/gogs.py`
  - `src/gfo/git_util.py`
  - `tests/test_adapters/test_gogs.py`
  - `tests/test_git_util.py`

- **発見事項**: 新規 4 件（重大 0 / 中 2 / 軽微 2）

---

## エージェントレビューで誤報された項目（問題なし確認）

| 確認項目 | 結果 |
|---------|------|
| `detect.py` Azure DevOps の `org` が None になる | OK — `m.group("org") or ""` で空文字に正規化し、`not org` の場合は `host.split(".")[0]` でフォールバック。マッチ失敗時は L173 で `DetectionError` を送出 |
| `detect.py` `probe_unknown_host()` の例外握りつぶし | OK — `except requests.RequestException: pass` は設計上の選択。プローブは「失敗したら次を試す」仕様であり、ログなし・例外吸収は意図的 |
| `gogs.py` `_web_url()` の None 安全性 | OK — `self._client.base_url` は `HttpClient.__init__` で必須文字列として設定される。`parsed.scheme` / `parsed.hostname` が None になる入力は来ない |
| `git_util.py` `_mask_credentials` の不完全マスク | OK — git 自体は stderr に認証情報を出力しない。予防的実装として十分 |

---

## 新規発見事項

---

### [R34-01] 🟡 `gogs.py` L29-50 — `self._owner` / `self._repo` が URL エンコードなしで web_url に埋め込まれる

- **ファイル**: `src/gfo/adapter/gogs.py` L29-50
- **現在のコード**:
  ```python
  def list_pull_requests(self, *, state: str = "open", limit: int = 30) -> list[PullRequest]:
      raise NotSupportedError("Gogs", "pull request operations",
                              web_url=f"{self._web_url()}/{self._owner}/{self._repo}/pulls")
  ```
- **説明**: 親クラス `GiteaAdapter._repos_path()` では `quote(self._owner, safe='')` / `quote(self._repo, safe='')` でエンコードしているが、Gogs の `web_url` 構築では未エンコードの値を直接埋め込んでいる。owner/repo 名に特殊文字（スペース、非 ASCII 等）が含まれる場合、`NotSupportedError.web_url` が壊れた URL になる。
- **推奨修正**:
  ```python
  from urllib.parse import quote
  f"{self._web_url()}/{quote(self._owner, safe='')}/{quote(self._repo, safe='')}/pulls"
  ```

---

### [R34-02] 🟡 `git_util.py` L101-104 — `git_checkout_branch` がすべての `GitCommandError` を握りつぶして fallthrough する

- **ファイル**: `src/gfo/git_util.py` L97-104
- **現在のコード**:
  ```python
  def git_checkout_branch(branch: str, start: str = "FETCH_HEAD", cwd: str | None = None) -> None:
      try:
          run_git("checkout", "-b", branch, start, cwd=cwd)
      except GitCommandError:
          run_git("checkout", branch, cwd=cwd)
  ```
- **説明**: `checkout -b` が失敗する理由が「ブランチが既存」以外（例：dirty working directory、ディスク満杯、権限エラー）であっても、すべて `checkout branch` に fallthrough する。エラーが吸収されてユーザーには無関係なエラーメッセージが表示される可能性がある。
  - `fatal: A branch named 'xxx' already exists.` → fallthrough 正しい
  - `error: Your local changes to the following files...` → fallthrough は誤り
- **推奨修正**:
  ```python
  def git_checkout_branch(...) -> None:
      try:
          run_git("checkout", "-b", branch, start, cwd=cwd)
      except GitCommandError as e:
          if "already exists" in str(e).lower():
              run_git("checkout", branch, cwd=cwd)
          else:
              raise
  ```

---

### [R34-03] 🟢 `test_git_util.py` — `git_checkout_branch` のテストが完全に欠落

- **ファイル**: `tests/test_git_util.py`
- **説明**: `git_checkout_new_branch` はテスト済みだが、`git_checkout_branch`（R34-02 修正対象）のテストが一切ない。新規作成ケース・既存ブランチへのフォールバック・その他エラーの再送出を確認するテストが必要。
- **推奨修正**: R34-02 修正後にテストを追加する。

---

### [R34-04] 🟢 `test_gogs.py` — owner/repo に特殊文字を含む web_url のテストなし

- **ファイル**: `tests/test_adapters/test_gogs.py`
- **説明**: R34-01 修正（URL エンコード追加）に対応したテストが不足している。
- **推奨修正**: R34-01 修正後にテストを追加する。

---

## 全問題サマリー（R34）

| ID | 重大度 | ファイル | 概要 | 状態 |
|----|--------|---------|------|------|
| **R34-01** | 🟡 中 | `gogs.py` L29-50 | owner/repo が URL エンコードなしで web_url に埋め込まれる | ✅ 修正済み |
| **R34-02** | 🟡 中 | `git_util.py` L101-104 | `git_checkout_branch` がすべての GitCommandError を握りつぶす | ✅ 修正済み |
| **R34-03** | 🟢 軽微 | `test_git_util.py` | `git_checkout_branch` のテスト欠落 | ✅ 修正済み |
| **R34-04** | 🟢 軽微 | `test_gogs.py` | 特殊文字 owner/repo の web_url テストなし | ✅ 修正済み |

---

## 推奨アクション（優先度順）

1. ~~**[R34-01]**~~ ✅ 修正済み
2. ~~**[R34-02]**~~ ✅ 修正済み
3. ~~**[R34-03]**~~ ✅ 修正済み
4. ~~**[R34-04]**~~ ✅ 修正済み

## 修正コミット（R34）

| コミット | 修正内容 |
|---------|---------|
| （次のコミット） | R34-01〜04 — Gogs URL エンコード・git_checkout_branch エラー判定修正・テスト追加 |
