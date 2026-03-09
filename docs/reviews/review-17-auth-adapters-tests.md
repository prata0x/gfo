# gfo Review Report — Round 17: auth / adapter(GitHub,GitLab) / tests 品質

## 概要
- レビュー日: 2026-03-09
- 対象: `auth.py`, `auth_cmd.py`, `adapter/base.py`, `adapter/github.py`, `adapter/gitlab.py`, `adapter/registry.py`, `adapter/backlog.py`, `tests/test_auth.py`, `tests/test_adapters/test_github.py`, `tests/test_adapters/test_gitlab.py`
- 発見事項: 新規 4 件（重大 1 / 中 1 / 軽微 2）、既知課題 2 件の現状確認

---

## 既知課題の現状確認

| ID | 現在の実装 | 状態 |
|----|-----------|------|
| R12-06 | `backlog.py` L254-258: `items[:limit]` スライスのみ、`paginate_offset` 未使用 | **未修正** |
| R16-02 | `auth.py` L126: `{"host": host, ...}` と L140: `{"host": f"env:{service_type}", ...}` が混在 | **未修正** |

---

## 新規発見事項

---

### [R17-01] 🔴 `backlog.py` L254-258 — `list_repositories` ページネーション未使用（R12-06 詳細）

- **ファイル**: `src/gfo/adapter/backlog.py` L254-258
- **現在のコード**:
  ```python
  def list_repositories(self, *, owner: str | None = None, limit: int = 30) -> list[Repository]:
      resp = self._client.get(f"/projects/{self._project_key}/git/repositories")
      items = resp.json()
      return [self._to_repository(r) for r in items[:limit]]
  ```
- **問題**: `list_pull_requests`（L144）と `list_issues`（L195）は `paginate_offset` を正しく使用しているのに、`list_repositories` のみ単一 GET + スライス。API が複数ページを返す場合にリポジトリの一部しか得られない。
- **推奨修正**:
  ```python
  def list_repositories(self, *, owner: str | None = None, limit: int = 30) -> list[Repository]:
      results = paginate_offset(
          self._client,
          f"/projects/{self._project_key}/git/repositories",
          limit=limit,
      )
      return [self._to_repository(r) for r in results]
  ```

---

### [R17-02] 🟡 `auth.py` L152-171 — TOML 書き込みに `tomllib` を使わず手書きエスケープ

- **ファイル**: `src/gfo/auth.py` L152-171
- **現在のコード**:
  ```python
  def _write_credentials_toml(tokens: dict[str, str]) -> str:
      lines = ["# gfo credentials — do not share\n\n[tokens]\n"]
      for host, token in tokens.items():
          safe_host = host.replace("\\", "\\\\").replace('"', '\\"')
          safe_token = ...  # 制御文字の手動エスケープ
          lines.append(f'"{safe_host}" = "{safe_token}"\n')
      return "".join(lines)
  ```
- **問題**: Python 標準の `tomllib` は読み込み専用（PEP 680）。書き込みには別ライブラリが必要だが、手書きでエスケープを実装している。TOML の複雑な仕様（キー内の特殊文字、多バイト文字、制御文字）を手動で全て正しく処理するのは困難。
- **現状の影響**: 通常の ASCII ホスト名・トークンでは問題なし。ホスト名に TOML 特殊文字（`[`, `]`, `=` 等）が含まれる場合は不正な TOML が生成される。
- **推奨修正**: `tomli_w` パッケージ（`tomllib` の書き込み版）を依存関係に追加するか、キー名のエスケープを強化する（ブラケット、等号等も処理する）。

---

### [R17-03] 🟢 `tests/test_auth.py` L184 — Windows パーミッションテストのモック対象が誤り

- **ファイル**: `tests/test_auth.py` L184
- **現在のコード**:
  ```python
  monkeypatch.setattr("gfo.auth.os.getlogin", lambda: "testuser")
  ```
- **実装側** (`auth.py` L78):
  ```python
  username = getpass.getuser()  # ← getpass.getuser() を使用
  ```
- **問題**: テストは `os.getlogin` をモックしているが、実装は `getpass.getuser()` を呼び出しているため、このモックは無効。テストが実際に有効な検証をしていない可能性がある。
- **推奨修正**:
  ```python
  monkeypatch.setattr("gfo.auth.getpass.getuser", lambda: "testuser")
  ```

---

### [R17-04] 🟢 `adapter/github.py` L38-39 — merged フィルタリング理由がコメントなし

- **ファイル**: `src/gfo/adapter/github.py` L38-39
- **現在のコード**:
  ```python
  if state == "merged":
      api_state = "closed"  # コメントなし
  ```
- **説明**: GitHub API では `state=closed` で closed と merged の両方が返される仕様のため、`state=merged` を `closed` に変換して取得後にフィルタリングしている。対比として GitLab は `state=merged` パラメータを直接 API に渡せる。意図が不明瞭で保守時に誤解される可能性がある。
- **推奨修正**: インラインコメントを追加。
  ```python
  if state == "merged":
      api_state = "closed"  # GitHub API に merged パラメータはなく closed で代用
  ```

---

## 良好な実装（記録）

| ファイル | 評価 |
|---------|------|
| `auth.py` | トークン解決の優先度順序（credentials.toml > サービス別環境変数 > GFO_TOKEN）が明確。パーミッション設定（POSIX/Windows）の両対応。 |
| `adapter/base.py` | `GitHubLikeAdapter` で GitHub/Gitea/GitBucket/Forgejo 系の共通変換コードを集約。DRY 原則に従った設計。 |
| `adapter/registry.py` | `@register("github")` デコレータパターンでアダプター登録を自動化。 |
| `test_auth.py` | パーミッション設定（POSIX chmod、Windows icacls）のテストカバレッジが充実。 |
| `test_github.py` / `test_gitlab.py` | 変換メソッド、CRUD、ページネーション、エラーハンドリングを網羅。 |

---

## 全問題サマリー（R17 現在）

| ID | 重大度 | ファイル | 概要 |
|----|--------|---------|------|
| **R17-01/R12-06** | 🔴 重大 | `backlog.py` L254 | `list_repositories` ページネーション未使用 |
| **R17-02** | 🟡 中 | `auth.py` L152 | TOML 書き込みに手書きエスケープ（仕様不完全） |
| R16-02 | 🟡 中 | `auth.py` L117 | `get_auth_status()` の host 形式混在 |
| **R17-03** | 🟢 軽微 | `test_auth.py` L184 | Windows パーミッションテストのモック対象が誤り |
| **R17-04** | 🟢 軽微 | `adapter/github.py` L38 | merged フィルタリング理由のコメント欠落 |

---

## 推奨アクション（優先度順）

1. **[R17-01/R12-06]** `backlog.py` L254 — `paginate_offset` を使うよう変更（数行修正）
2. **[R17-03]** `test_auth.py` L184 — `os.getlogin` → `getpass.getuser` にモック対象を修正
3. **[R17-04]** `adapter/github.py` L38 — インラインコメント追加（1行）
4. **[R17-02]** `auth.py` — TOML 書き込みの堅牢化（`tomli_w` 導入 or エスケープ強化）
5. **[R16-02]** `auth.py` — host 形式の統一（設計変更が必要）
