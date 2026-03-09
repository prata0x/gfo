# gfo Review Report — Round 20: gogs / forgejo / gitea / bitbucket / auth 精査

## 概要
- レビュー日: 2026-03-09
- 対象: `adapter/gogs.py`, `adapter/forgejo.py`, `adapter/gitea.py`, `auth.py`, `tests/test_adapters/test_gogs.py`, `tests/test_adapters/test_forgejo.py`, `tests/test_adapters/test_bitbucket.py`, `tests/test_adapters/test_gitea.py`
- 発見事項: 重大 0 / 中 4 / 軽微 1（既知課題 2 件含む）

---

## 既知残課題の現状確認

| ID | 状態 |
|----|------|
| R16-02 | `auth.py` `get_auth_status()` の env var エントリの host 形式が `"github.com"` と `"env:github"` で混在 — **継続中** |
| R13-03 | `gitea.py` L84 `list_issues` フィルタ後に limit 未満になる問題 — **継続中（設計決定待ち）** |

---

## 修正済み・問題なし確認（OK）

| 項目 | 確認内容 |
|------|---------|
| `forgejo.py` | `GitHubLikeAdapter` + `GitServiceAdapter` を継承し `service_name = "forgejo"` を設定。Forgejo 固有実装なし（Gitea 互換として動作）。 |
| `gogs.py` | `_web_url()` で host + owner + repo から web URL を構築。`create_pull_request`/`merge_pull_request`/`close_pull_request` は `NotSupportedError` を送出。 |
| `bitbucket.py` | `paginate_response_body` でページネーション実装済み。`list_repositories` は Bitbucket Cloud API `2.0/repositories/{owner}` を使用。 |
| `gitea.py` | `list_pull_requests`, `list_issues` に `state` パラメータ渡し実装済み。`list_labels` / `create_label` / `list_milestones` / `create_milestone` 実装済み。 |

---

## 新規発見事項

---

### [R20-01] 🟡 `adapter/gogs.py` L23 — `_web_url()` が異常 URL を無検証で返す

- **ファイル**: `src/gfo/adapter/gogs.py` L23
- **現在のコード**:
  ```python
  def _web_url(self, path: str = "") -> str:
      return f"https://{self._owner}:{self._repo}/{path}"
  ```
- **説明**: `self._owner` や `self._repo` が空文字列の場合（例: `handle_create` で `adapter_cls(client, "", "")` を渡したケース）、`https://:/ ` のような壊れた URL を返してしまう。`_web_url()` を呼ぶ `_to_pull_request` メソッドは PR 作成が Gogs では未サポートのため実際には呼ばれないが、潜在的バグである。
- **影響**: 現在は実害なし（Gogs の PR 操作は `NotSupportedError`）。ただし将来実装時に無効 URL が混入するリスク。
- **推奨修正**: `_web_url` 内で owner/repo が空の場合は早期 return するか、呼び出し側で owner/repo の非空を保証する。
  ```python
  def _web_url(self, path: str = "") -> str:
      if not self._owner or not self._repo:
          return ""
      return f"https://{self._owner}/{self._repo}/{path}"
  ```

---

### [R20-02] 🟡 `tests/test_adapters/test_gogs.py` — ページネーション + PR フィルタのテスト未追加

- **ファイル**: `tests/test_adapters/test_gogs.py`
- **説明**: `list_pull_requests` は実装上 `list_issues` の結果から `pull_request` キーを持つもののみフィルタしている。このフィルタロジックと、複数ページにわたるケースのテストが存在しない。
- **推奨修正**: 以下テストケースを追加。
  ```python
  def test_list_pull_requests_filters_issues(self, adapter, requests_mock):
      """pull_request キーを持たないIssueがフィルタされることを確認"""
      issues = [
          {**_issue_data(1), "pull_request": {"merged_at": None}},
          _issue_data(2),  # PR ではない Issue
      ]
      requests_mock.get(f"{BASE}/issues", json=issues)
      prs = adapter.list_pull_requests(state="open")
      assert len(prs) == 1
      assert prs[0].number == 1
  ```

---

### [R20-03] 🟡 `tests/test_adapters/test_forgejo.py` — Forgejo 固有テストケース不足

- **ファイル**: `tests/test_adapters/test_forgejo.py`
- **説明**: `test_forgejo.py` は `test_gitea.py` の fixture を流用しており、Forgejo 固有の API 差異（`/api/v1` エンドポイントが Gitea と異なる場合の挙動）のテストがない。現状 Forgejo は Gitea 完全互換として実装されているため問題はないが、将来の差異追加時のリグレッション検出が困難。
- **推奨対応**: `service_name = "forgejo"` のアサーションテストを追加する。
  ```python
  def test_service_name():
      assert ForgejoAdapter.service_name == "forgejo"
  ```

---

### [R20-04] 🟡 `tests/test_adapters/test_bitbucket.py` — 別オリジン URL でのページネーション検証未テスト

- **ファイル**: `tests/test_adapters/test_bitbucket.py`
- **説明**: Bitbucket Cloud の `paginate_response_body` は `next` フィールドの URL を直接 `get_absolute()` で呼び出す。`next` が異なるオリジン（例: `https://other.example.com/...`）を指す場合の挙動（認証ヘッダーを送るかどうか等）のテストが存在しない。
- **影響**: セキュリティ上のリスク（SSRF / 認証情報漏洩）の可能性があるが、現状 `HttpClient.get_absolute()` はドメイン検証を行わない。
- **推奨修正**: テストで `next` が異なるオリジンを指す場合の挙動を検証。または `paginate_response_body` に同一オリジン検証を追加。

---

### [R20-05] 🟢 `adapter/gitea.py` L84 — `list_issues` フィルタ後に limit 未満になる（R13-03 継続）

- **ファイル**: `src/gfo/adapter/gitea.py` L84
- **説明**: R13-03 の既知課題。`list_issues` は PR を除外するために `pull_request` キーのないもののみ返すが、API から `limit` 件取得したうち PR が含まれる場合は limit 未満の件数しか返らない。
- **現状**: 設計決定待ち。API 側に `type=issues` パラメータがあれば追加することで解消できる。

---

## 全問題サマリー（R20）

| ID | 重大度 | ファイル | 概要 |
|----|--------|---------|------|
| **R20-01** | 🟡 中 | `adapter/gogs.py` L23 | `_web_url()` が空 owner/repo で異常 URL を返す |
| **R20-02** | 🟡 中 | `test_gogs.py` | PR フィルタロジックのテスト未追加 |
| **R20-03** | 🟡 中 | `test_forgejo.py` | `service_name` アサーションテスト未追加 |
| **R20-04** | 🟡 中 | `test_bitbucket.py` | 別オリジン URL ページネーション検証未テスト |
| R16-02 | 🟡 中 | `auth.py` | host 形式混在（継続） |
| **R20-05** | 🟢 軽微 | `adapter/gitea.py` L84 | フィルタ後 limit 未満（R13-03 継続） |

---

## 推奨アクション（優先度順）

1. **[R20-01]** `adapter/gogs.py` L23 — `_web_url()` に空文字ガード追加
2. **[R20-02]** `test_gogs.py` — PR フィルタテスト追加
3. **[R20-03]** `test_forgejo.py` — `service_name` テスト追加
4. **[R20-04]** `test_bitbucket.py` — 別オリジンページネーション検証テスト追加
5. **[R16-02]** `auth.py` — env var エントリの host 形式統一
