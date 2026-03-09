# gfo Review Report — Round 42: Bitbucket / Backlog / Azure DevOps アダプター精査

## 概要

- **レビュー日**: 2026-03-09
- **対象**:
  - `src/gfo/adapter/bitbucket.py`
  - `src/gfo/adapter/backlog.py`
  - `src/gfo/adapter/azure_devops.py`
  - `tests/test_adapters/test_bitbucket.py`
  - `tests/test_adapters/test_backlog.py`
  - `tests/test_adapters/test_azure_devops.py`

- **発見事項**: 新規 2 件（重大 0 / 中 1 / 軽微 1）

---

## エージェントレビューで誤報された項目（問題なし確認）

| 確認項目 | 結果 |
|---------|------|
| `azure_devops.py` / `backlog.py` の `list_repositories(owner=...)` が owner を無視 | OK — Azure DevOps・Backlog はプロジェクト単位の API 設計であり、user-level のリポジトリ一覧概念がない。設計通り |
| `backlog.py` `create_repository` / `get_repository` の URL エンコード | OK — `get_repository` は `urllib.parse.quote(n, safe='')` を使用済み（L282）。`create_repository` は名前を POST body に含めるため不要 |
| `azure_devops.py` `_to_repository` の `project.description` フィールド | OK — Azure DevOps API のリポジトリレスポンスは `project` オブジェクトを含む場合があり、`get()` チェーンのため None 安全 |
| `bitbucket.py` `get_repository()` の既存テスト（スペース含む owner）がパス | OK — `requests` ライブラリがスペースを自動エンコードするためパスするが、スラッシュ等は自動エンコードされないため修正が必要 |
| Backlog / Azure DevOps create_pull_request の branch バリデーション欠落 | 設計判断 — 入力バリデーションはコマンドハンドラ側の責務。アダプターは API に委ねる設計 |
| `azure_devops.py` list_issues limit=0 → $top=20000 で 20000 件超が取れない | OK — R38-02 で修正済みの設計。Azure DevOps WIQL の最大ページサイズは 20000 件が公式最大値 |

---

## 新規発見事項

---

### [R42-01] 🟡 `bitbucket.py` L189, L196, L203 — repository 3 メソッドで `quote()` が欠落

- **ファイル**: `src/gfo/adapter/bitbucket.py`
- **現在のコード**:
  ```python
  # list_repositories L189（owner が未エンコード）
  results = paginate_response_body(
      self._client, f"/repositories/{o}", limit=limit,
  )

  # create_repository L196（owner・name が未エンコード）
  resp = self._client.post(f"/repositories/{self._owner}/{name}", json=payload)

  # get_repository L203（owner・name が未エンコード）
  resp = self._client.get(f"/repositories/{o}/{n}")
  ```
- **正しくエンコードしている箇所（対比）**:
  ```python
  # _repos_path() L26（正しい）
  return f"/repositories/{quote(self._owner, safe='')}/{quote(self._repo, safe='')}"
  ```
- **説明**: `_repos_path()` では `quote(safe='')` でエンコードしているが、`list_repositories`・`create_repository`・`get_repository` では同じ owner/name パス構築に `quote()` を使っていない。`requests` ライブラリはスペースを自動エンコードするため既存テストはパスするが、スラッシュ（`/`）を含む owner/name では URL が余分なパスセグメントに分割され、誤ったエンドポイントを叩く。R41 で github.py / gitea.py / gitlab.py を修正した同一パターン。
- **推奨修正**:
  ```python
  # list_repositories
  results = paginate_response_body(
      self._client, f"/repositories/{quote(o, safe='')}", limit=limit,
  )

  # create_repository
  resp = self._client.post(f"/repositories/{quote(self._owner, safe='')}/{quote(name, safe='')}", json=payload)

  # get_repository
  resp = self._client.get(f"/repositories/{quote(o, safe='')}/{quote(n, safe='')}")
  ```

---

### [R42-02] 🟢 テスト — `list_repositories` / `create_repository` / `get_repository` のスラッシュ含む owner/name テスト欠落

- **ファイル**: `tests/test_adapters/test_bitbucket.py`
- **説明**:
  - 既存の `test_repos_path_is_url_encoded`（R33-03）はスペースのみをテストしており、`requests` 自動エンコードで通過する
  - スラッシュ（`/`）など `requests` が自動エンコードしない文字での URL エンコードテストが欠落
  - R42-01 修正後の確認用テストが必要
- **推奨修正**:
  ```python
  def test_list_repositories_owner_with_slash_is_encoded(self, mock_responses, ...):
      """list_repositories(owner="org/sub") でスラッシュが URL エンコードされる（R42-01）。"""
      mock_responses.add(
          responses.GET, f"{BASE}/repositories/org%2Fsub",
          json={"values": [_repo_data()]}, status=200,
      )
      bitbucket_adapter.list_repositories(owner="org/sub")
      assert "%2F" in mock_responses.calls[0].request.url

  def test_create_repository_owner_name_with_slash_is_encoded(self, mock_responses, ...):
      """create_repository で owner・name のスラッシュが URL エンコードされる（R42-01）。"""
      ...
  ```

---

## 全問題サマリー（R42）

| ID | 重大度 | ファイル | 概要 | 状態 |
|----|--------|---------|------|------|
| **R42-01** | 🟡 中 | `bitbucket.py` L189/196/203 | `list_repositories` / `create_repository` / `get_repository` の owner/name に `quote()` 欠落 | 未修正 |
| **R42-02** | 🟢 軽微 | `test_bitbucket.py` | スラッシュ含む owner/name の URL エンコードテスト欠落 | 未修正 |

---

## 推奨アクション（優先度順）

1. **[R42-01]** `bitbucket.py` の 3 メソッドに `quote(o, safe='')` / `quote(n, safe='')` を追加
2. **[R42-02]** テスト追加

## 修正コミット（R42）

| コミット | 修正内容 |
|---------|---------|
| （次のコミット） | R42-01〜02 — Bitbucket repository メソッドの URL エンコード修正・テスト追加 |
