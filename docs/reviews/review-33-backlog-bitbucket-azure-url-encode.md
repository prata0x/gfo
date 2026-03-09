# gfo Review Report — Round 33: backlog / bitbucket / azure_devops URL エンコード精査

## 概要

- **レビュー日**: 2026-03-09
- **対象**:
  - `src/gfo/adapter/backlog.py`
  - `src/gfo/adapter/bitbucket.py`
  - `src/gfo/adapter/azure_devops.py`
  - `tests/test_adapters/test_backlog.py`
  - `tests/test_adapters/test_bitbucket.py`
  - `tests/test_adapters/test_azure_devops.py`

- **発見事項**: 新規 4 件（重大 0 / 中 3 / 軽微 1）

---

## エージェントレビューで誤報された項目（問題なし確認）

| 確認項目 | 結果 |
|---------|------|
| `backlog.py` `create_issue` で `label` パラメータが無視される | OK — Backlog API は issue 作成時に category/label を別エンドポイントで管理する設計。`label` は `list_issues` の `keyword` 検索には利用しており、create では現状 API 仕様上サポート外 |
| `bitbucket.py` `create_issue` で `label` パラメータが無視される | OK — Bitbucket Cloud issue には component/kind フィールドがあるが、基底クラスの `label` パラメータとの対応は現状未実装で設計上の許容範囲 |
| `backlog.py` `paginate_offset` の `limit=0` 処理 | OK — `0 < limit < count` が False になることで `count` はデフォルト (20) のまま全ページをループする。動作として正しい |
| `azure_devops.py` WIQL `$top` の `limit=0` 処理 | OK — `wiql_params = {"$top": limit} if limit > 0 else {}` で正しく全件取得モードを実装している |
| `bitbucket.py` `_repos_path` owner/repo エンコード | OK — Bitbucket Cloud の workspace slug と repo slug は英数字・ハイフン・アンダースコアのみ許容（URL セーフ）。ただし一貫性のため対象外とした |

---

## 新規発見事項

---

### [R33-01] 🟡 `backlog.py` L280 — `get_repository()` が URL エンコードなし（`_pr_path()` との非対称性）

- **ファイル**: `src/gfo/adapter/backlog.py` L277-281
- **現在のコード**:
  ```python
  def _pr_path(self) -> str:
      return f"/projects/{self._project_key}/git/repositories/{urllib.parse.quote(self._repo, safe='')}/pullRequests"

  def get_repository(self, owner: str | None = None, name: str | None = None) -> Repository:
      n = name if name is not None else self._repo
      resp = self._client.get(f"/projects/{self._project_key}/git/repositories/{n}")  # エンコードなし
  ```
- **説明**: `_pr_path()` では `urllib.parse.quote(self._repo, safe='')` でエンコードしているが、同じパス構造を使う `get_repository()` ではエンコードしていない。非 ASCII 文字やスペースを含むリポジトリ名で `get_repository()` が失敗する。
- **推奨修正**: `f"/projects/{self._project_key}/git/repositories/{urllib.parse.quote(n, safe='')}"`

---

### [R33-02] 🟡 `azure_devops.py` L54/277 — `_git_path()` と `get_repository()` が URL エンコードなし

- **ファイル**: `src/gfo/adapter/azure_devops.py` L53-54, L274-278
- **現在のコード**:
  ```python
  def _git_path(self) -> str:
      return f"/git/repositories/{self._repo}"   # エンコードなし

  def get_repository(self, owner: str | None = None, name: str | None = None) -> Repository:
      n = name if name is not None else self._repo
      resp = self._client.get(f"/git/repositories/{n}")  # エンコードなし
  ```
- **説明**: Azure DevOps のリポジトリ名はスペースを含むことができる（例: "My Project Repo"）。エンコードなしでは API 呼び出しが失敗する。
- **推奨修正**:
  ```python
  from urllib.parse import quote

  def _git_path(self) -> str:
      return f"/git/repositories/{quote(self._repo, safe='')}"

  def get_repository(self, ...):
      resp = self._client.get(f"/git/repositories/{quote(n, safe='')}")
  ```

---

### [R33-03] 🟡 `bitbucket.py` L24 — `_repos_path()` が URL エンコードなし

- **ファイル**: `src/gfo/adapter/bitbucket.py` L23-24
- **現在のコード**:
  ```python
  def _repos_path(self) -> str:
      return f"/repositories/{self._owner}/{self._repo}"  # エンコードなし
  ```
- **説明**: Bitbucket Cloud の workspace slug と repo slug は通常 URL セーフだが、`get_repository(owner, name)` の引数で任意の文字列が渡される可能性がある。他アダプターとの一貫性のためエンコードを追加する。
- **推奨修正**: `f"/repositories/{quote(self._owner, safe='')}/{quote(self._repo, safe='')}"`

---

### [R33-04] 🟢 テスト — R33-01〜03 の URL エンコード確認テストなし

- **ファイル**: `tests/test_adapters/test_backlog.py`, `test_azure_devops.py`, `test_bitbucket.py`
- **説明**: 各 `get_repository()` に非 ASCII / スペース含む名前を渡したときに URL が正しくエンコードされることを確認するテストがない。
- **推奨修正**: R33-01〜03 修正後に対応テストを追加する。

---

## 全問題サマリー（R33）

| ID | 重大度 | ファイル | 概要 | 状態 |
|----|--------|---------|------|------|
| **R33-01** | 🟡 中 | `backlog.py` L280 | `get_repository` URL エンコードなし | ✅ 修正済み |
| **R33-02** | 🟡 中 | `azure_devops.py` L54/277 | `_git_path`/`get_repository` URL エンコードなし | ✅ 修正済み |
| **R33-03** | 🟡 中 | `bitbucket.py` L24 | `_repos_path` URL エンコードなし | ✅ 修正済み |
| **R33-04** | 🟢 軽微 | テスト各種 | URL エンコード確認テストなし | ✅ 修正済み |

---

## 推奨アクション（優先度順）

1. ~~**[R33-01]**~~ ✅ 修正済み
2. ~~**[R33-02]**~~ ✅ 修正済み
3. ~~**[R33-03]**~~ ✅ 修正済み
4. ~~**[R33-04]**~~ ✅ 修正済み

## 修正コミット（R33）

| コミット | 修正内容 |
|---------|---------|
| （次のコミット） | R33-01〜04 — URL エンコード修正・テスト追加 |
