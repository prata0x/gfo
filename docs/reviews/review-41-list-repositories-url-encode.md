# gfo Review Report — Round 41: list_repositories URL エンコード・GitBucket テスト認証

## 概要

- **レビュー日**: 2026-03-09
- **対象**:
  - `src/gfo/adapter/github.py`
  - `src/gfo/adapter/gitea.py`
  - `src/gfo/adapter/gitlab.py`
  - `src/gfo/adapter/forgejo.py`（GiteaAdapter 継承）
  - `src/gfo/adapter/gitbucket.py`（GitHubAdapter 継承）
  - `src/gfo/adapter/gogs.py`（GiteaAdapter 継承）
  - `src/gfo/adapter/registry.py`
  - `tests/test_adapters/conftest.py`
  - `tests/test_adapters/test_github.py`
  - `tests/test_adapters/test_gitea.py`
  - `tests/test_adapters/test_gitlab.py`

- **発見事項**: 新規 3 件（重大 0 / 中 2 / 軽微 1）

---

## エージェントレビューで誤報された項目（問題なし確認）

| 確認項目 | 結果 |
|---------|------|
| paginate_link_header limit=0 が next_url でパラメータを無視 | OK — RFC 5988 準拠。Link ヘッダー URL は完全。設計通り |
| gogs.py NotSupportedError の web_url が PR vs Label で非対称 | OK — PR には web_url を提供し、label/milestone には不要という設計 |
| gitbucket テストの per_page パラメータが不明確 | OK — GitBucket は GitHub API v3 互換で `per_page` を使う |

---

## 新規発見事項

---

### [R41-01] 🟡 `list_repositories(owner=...)` の owner が URL エンコードされていない

- **ファイル**: 以下の 3 ファイル（6 アダプターに影響）
  - `src/gfo/adapter/github.py` L113
  - `src/gfo/adapter/gitea.py` L112
  - `src/gfo/adapter/gitlab.py` L233
- **現在のコード**:
  ```python
  # github.py / gitea.py（同一構造）
  def list_repositories(self, *, owner: str | None = None,
                        limit: int = 30) -> list[Repository]:
      if owner is not None:
          path = f"/users/{owner}/repos"   # ← owner が URL エンコードされていない

  # gitlab.py
  def list_repositories(self, *, owner: str | None = None,
                        limit: int = 30) -> list[Repository]:
      if owner is not None:
          path = f"/users/{owner}/projects"  # ← 同上
  ```
- **影響アダプター**:
  - `github.py` → `GitHubAdapter`、`GitBucketAdapter`（継承）
  - `gitea.py` → `GiteaAdapter`、`ForgejoAdapter`（継承）、`GogsAdapter`（継承）
  - `gitlab.py` → `GitLabAdapter`
- **説明**: 同じファイル内の `_repos_path()` と `get_repository()` では `quote(owner, safe='')` を使用しているが、`list_repositories()` の owner パスが URL エンコードされていない。owner 名にスペースやスラッシュ等を含む場合にリクエスト URL が不正になる。
  ```python
  # 同ファイル内で正しくエンコードしている箇所（対比）
  def _repos_path(self) -> str:
      return f"/repos/{quote(self._owner, safe='')}/{quote(self._repo, safe='')}"
  def get_repository(self, owner, name):
      resp = self._client.get(f"/repos/{quote(o, safe='')}/{quote(n, safe='')}")
  ```
- **推奨修正**:
  ```python
  # github.py / gitea.py
  if owner is not None:
      path = f"/users/{quote(owner, safe='')}/repos"

  # gitlab.py
  if owner is not None:
      path = f"/users/{quote(owner, safe='')}/projects"
  ```

---

### [R41-02] 🟡 `tests/test_adapters/conftest.py` L116 — GitBucket テストフィクスチャの認証ヘッダーが誤り

- **ファイル**: `tests/test_adapters/conftest.py` L114-116
- **現在のコード**:
  ```python
  @pytest.fixture
  def gitbucket_client():
      return HttpClient(GITBUCKET_BASE_URL, auth_header={"Authorization": "Bearer test-token"})
  ```
- **実際の認証方式** (`src/gfo/adapter/registry.py` L53-54):
  ```python
  elif service_type in ("gitea", "forgejo", "gogs", "gitbucket"):
      return HttpClient(api_url, auth_header={"Authorization": f"token {token}"})
  ```
- **説明**: GitBucket は `token <token>` 形式を使用するが、テストフィクスチャは `Bearer test-token` を使っている。GitHub は `Bearer` 形式を使用するため、GitBucketAdapter が GitHubAdapter を継承しているという混同から生じた誤りと考えられる。テストが実際のランタイム動作と異なるヘッダーで動作しているため、テストの信頼性を損なう。
- **推奨修正**:
  ```python
  @pytest.fixture
  def gitbucket_client():
      return HttpClient(GITBUCKET_BASE_URL, auth_header={"Authorization": "token test-token"})
  ```

---

### [R41-03] 🟢 テスト — `list_repositories(owner=...)` の URL エンコードテスト欠落

- **ファイル**: `tests/test_adapters/test_github.py`、`tests/test_adapters/test_gitea.py`、`tests/test_adapters/test_gitlab.py`
- **説明**:
  - `TestListRepositories` クラスに `owner` 引数の URL エンコードをアサートするテストが存在しない
  - R41-01 修正後の動作確認に必要
- **推奨修正**: 各テストファイルの `TestListRepositories` に以下を追加:
  ```python
  def test_owner_with_special_chars_is_encoded(self, mock_responses, github_adapter):
      """list_repositories(owner="...") で特殊文字が URL エンコードされる（R41-01）。"""
      mock_responses.add(
          responses.GET, f"{BASE}/users/org%2Fsub/repos",
          json=[_repo_data()], status=200,
      )
      github_adapter.list_repositories(owner="org/sub")
      assert "%2F" in mock_responses.calls[0].request.url
  ```

---

## 全問題サマリー（R41）

| ID | 重大度 | ファイル | 概要 | 状態 |
|----|--------|---------|------|------|
| **R41-01** | 🟡 中 | `github.py` / `gitea.py` / `gitlab.py` | `list_repositories` owner URL エンコード漏れ | ✅ 修正済み |
| **R41-02** | 🟡 中 | `tests/test_adapters/conftest.py` | GitBucket フィクスチャが `Bearer` 形式（正しくは `token`） | ✅ 修正済み |
| **R41-03** | 🟢 軽微 | `test_github.py` / `test_gitea.py` / `test_gitlab.py` | `list_repositories` owner URL エンコードテスト欠落 | ✅ 修正済み |

---

## 推奨アクション（優先度順）

1. **[R41-01]** `github.py`・`gitea.py`・`gitlab.py` の `list_repositories` owner パスに `quote()` を追加
2. **[R41-02]** `conftest.py` GitBucket フィクスチャを `token` 形式に修正
3. **[R41-03]** 各テストファイルに URL エンコードテストを追加

## 修正コミット（R41）

| コミット | 修正内容 |
|---------|---------|
| 5d28ac6 | R41-01〜03 — list_repositories owner URL エンコード修正・GitBucket テスト認証修正・テスト追加 |
