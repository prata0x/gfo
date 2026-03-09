# gfo Review Report — Round 21: gitlab / gitbucket / http / tests 精査

## 概要

- **レビュー日**: 2026-03-09
- **対象**:
  - `src/gfo/adapter/gitlab.py` — GitLab アダプター
  - `src/gfo/adapter/gitbucket.py` — GitBucket アダプター（GitHub アダプター継承）
  - `src/gfo/http.py` — HTTP クライアント・ページネーション関数
  - `tests/test_http.py` — HTTP テスト
  - `tests/test_adapters/test_gitlab.py` — GitLab テスト
  - `tests/test_adapters/test_gitbucket.py` — GitBucket テスト

- **発見事項**: 新規 7 件（重大 2 / 中 3 / 軽微 2）、既知課題 2 件の現状確認

---

## 既知残課題の現状確認

| ID | 状態 |
|----|------|
| R16-02 | `auth.py` `get_auth_status()` の env var エントリ host 形式が `"env:github"` と `"github.com"` 形式で不統一 — **継続中** |
| R13-03 | `gitea.py` `list_issues` フィルタ後に limit 未満になる問題 — **継続中（設計決定待ち）** |

---

## 修正済み・問題なし確認（OK）

| ファイル | 確認項目 | 結果 |
|---------|---------|------|
| `gitlab.py` | `_to_*` 変換メソッドのエラーハンドリング | OK — KeyError/TypeError を GfoError にラップ |
| `gitlab.py` | ページネーション（`paginate_page_param`）の利用 | OK — limit パラメータを正しく伝播 |
| `gitlab.py` | PR/Issue の state フィルタリング | OK — "opened" ↔ "open" 変換が正確 |
| `http.py` | ページネーション関数の limit=0 (無制限) | OK — すべての関数で正しく実装 |
| `test_http.py` | ページネーション limit テスト | OK — limit=0, limit=2 等複数パターンをカバー |
| `test_gitlab.py` | エラーハンドリング（404/401/500） | OK — NotFoundError/AuthenticationError/ServerError 検証 |

---

## 新規発見事項

---

### [R21-01] 🔴 `http.py` L188 — `_validate_same_origin` がポート番号をチェックしない

- **ファイル**: `src/gfo/http.py` L188-192
- **現在のコード**:
  ```python
  def _validate_same_origin(base_url: str, next_url: str) -> bool:
      base = urlparse(base_url)
      target = urlparse(next_url)
      return base.scheme == target.scheme and base.hostname == target.hostname
  ```
- **説明**: ポート番号のチェックがない。`https://api.example.com:8080` と `https://api.example.com:9000` が同一オリジンと判定される。また `https://api.example.com` (暗黙的 port 443) と `https://api.example.com:443` の比較も不整合になる可能性がある。
- **影響**: ページネーション時、ポートが異なるサーバーへのリクエストが通過するセキュリティリスク（低確率だが実在）。
- **推奨修正**:
  ```python
  def _validate_same_origin(base_url: str, next_url: str) -> bool:
      base = urlparse(base_url)
      target = urlparse(next_url)
      _DEFAULT_PORTS = {"http": 80, "https": 443}
      base_port = base.port or _DEFAULT_PORTS.get(base.scheme)
      target_port = target.port or _DEFAULT_PORTS.get(target.scheme)
      return (base.scheme == target.scheme
              and base.hostname == target.hostname
              and base_port == target_port)
  ```

---

### [R21-02] 🔴 `http.py` L229 — Link ヘッダーパーサーが RFC 5988 の順序バリエーションを処理できない

- **ファイル**: `src/gfo/http.py` L229
- **現在のコード**:
  ```python
  match = re.search(r'<([^>]+)>;\s*rel="next"', link, re.IGNORECASE)
  ```
- **説明**: RFC 5988/8288 の Link ヘッダーでは `rel` 以外のパラメータが先に来る場合がある（例：`<url>; title="Page 2"; rel="next"`）。現在の正規表現は URL 直後に `rel="next"` が来ることを前提としており、このような順序バリエーションを処理できない。
- **影響**: 一部のサーバーが返す非標準順序の Link ヘッダーでページネーションが中断される。
- **推奨修正**: エントリを `,` で分割し、各エントリで URL と `rel` を独立してパースする。
  ```python
  def _extract_next_url(link: str) -> str | None:
      for entry in link.split(","):
          url_match = re.match(r"\s*<([^>]+)>", entry)
          if url_match and re.search(r';\s*rel\s*=\s*"?next"?', entry, re.IGNORECASE):
              return url_match.group(1)
      return None
  ```

---

### [R21-03] 🟡 `gitlab.py` L158 — `merge_pull_request` の method パラメータ検証欠落

- **ファイル**: `src/gfo/adapter/gitlab.py` L158
- **現在のコード**:
  ```python
  elif method != "merge":
      payload["merge_method"] = method  # 任意の文字列が API に送られる
  ```
- **説明**: `method` に `"merge"`, `"squash"`, `"rebase"` 以外の値を渡すと、不正な値が API に送られて 400 Bad Request が返るが、エラーメッセージが不明確。
- **影響**: 呼び出し側が使える method の選択肢を事前に知ることができない。
- **推奨修正**: `allowed_methods = {"merge", "squash", "rebase"}` を事前チェックして `ValueError` を送出。

---

### [R21-04] 🟡 `gitlab.py` L270, L288 — `list_labels` / `list_milestones` が `limit` パラメータを受け取らない

- **ファイル**: `src/gfo/adapter/gitlab.py` L270, L288
- **現在のコード**:
  ```python
  def list_labels(self) -> list[Label]:
      results = paginate_page_param(self._client, f"{self._project_path()}/labels")
      return [self._to_label(r) for r in results]

  def list_milestones(self) -> list[Milestone]:
      results = paginate_page_param(self._client, f"{self._project_path()}/milestones")
      return [self._to_milestone(r) for r in results]
  ```
- **説明**: `list_pull_requests`, `list_issues` は `limit` を受け取り `paginate_page_param` に渡すが、`list_labels`/`list_milestones` はデフォルト 30 件固定。GitHubLikeAdapter の抽象基底クラスで `list_labels()` のシグネチャに `limit` がないため、全アダプターで統一が取れていない。
- **影響**: ラベルやマイルストーンが 30 件超の場合、呼び出し側から件数を制御できない。
- **推奨修正**: シグネチャを `def list_labels(self, *, limit: int = 30)` に変更し、`paginate_page_param` に `limit=limit` を渡す。`base.py` の抽象メソッドのシグネチャも合わせて変更が必要。

---

### [R21-05] 🟡 `test_http.py` — `_validate_same_origin` テストがゼロ

- **ファイル**: `tests/test_http.py`
- **説明**: セキュリティクリティカルな `_validate_same_origin` 関数のテストケースが一切ない。異なるホスト・スキーム・ポートの場合の動作が未検証。
- **推奨修正**: 以下のケースをテスト追加：
  - 同一オリジン（正常ケース）
  - 異なるホスト名（SSRF 防止）
  - 異なるスキーム（http vs https）
  - 異なるポート（:8080 vs :9000）
  - サブドメイン違い（api.example.com vs example.com）

---

### [R21-06] 🟢 `http.py` L176 — `_parse_retry_after` の例外キャッチが過度に broad

- **ファイル**: `src/gfo/http.py` L176-180
- **現在のコード**:
  ```python
  except Exception:
      return default
  ```
- **説明**: `email.utils.parsedate_to_datetime` が失敗する例外は `ValueError`/`TypeError` に限定される。`Exception` で全てをキャッチすると予期しないバグが隠蔽される。
- **推奨修正**: `except (ValueError, TypeError):` に変更。

---

### [R21-07] 🟢 `test_gitlab.py` L197 — ページネーション limit 切り詰めテストが不十分

- **ファイル**: `tests/test_adapters/test_gitlab.py` L197
- **説明**: 既存の `test_pagination` は `limit=10` を指定しているが、実際に limit で切り詰められることを検証していない。`limit=2` で 3 件取得しようとした場合に 2 件で止まることのテストがない。
- **推奨修正**: `limit=2` のテストケースを追加し、2 ページ目にリクエストが飛ばないことを確認。

---

## 全問題サマリー（R21）

| ID | 重大度 | ファイル | 概要 |
|----|--------|---------|------|
| **R21-01** | 🔴 重大 | `http.py` L188 | `_validate_same_origin` がポート番号をチェックしない |
| **R21-02** | 🔴 重大 | `http.py` L229 | Link ヘッダーパーサーが RFC 5988 の順序バリエーションを処理できない |
| **R21-03** | 🟡 中 | `gitlab.py` L158 | `merge_pull_request` の method パラメータ検証欠落 |
| **R21-04** | 🟡 中 | `gitlab.py` L270/L288 | `list_labels`/`list_milestones` が `limit` パラメータを受け取らない |
| R16-02 | 🟡 中 | `auth.py` | host 形式が混在（継続） |
| **R21-05** | 🟡 中 | `test_http.py` | `_validate_same_origin` テスト欠落 |
| R13-03 | 🟡 中 | `gitea.py` | フィルタ後 limit 未満（継続） |
| **R21-06** | 🟢 軽微 | `http.py` L176 | `_parse_retry_after` の Exception キャッチが過度に broad |
| **R21-07** | 🟢 軽微 | `test_gitlab.py` L197 | ページネーション limit 切り詰めテストが不十分 |

---

## 推奨アクション（優先度順）

1. **[R21-01]** `http.py` L188 — `_validate_same_origin` にポート番号チェックを追加
2. **[R21-02]** `http.py` L229 — Link ヘッダーパーサーを RFC 5988 準拠に改善
3. **[R21-05]** `test_http.py` — `_validate_same_origin` テストケースを追加
4. **[R21-03]** `gitlab.py` L158 — `merge_pull_request` に method 事前検証を追加
5. **[R21-04]** `gitlab.py` L270/L288 — `list_labels`/`list_milestones` に `limit` パラメータを追加
6. **[R21-07]** `test_gitlab.py` L197 — ページネーション limit 切り詰めテストを追加
7. **[R21-06]** `http.py` L176 — 例外キャッチを `(ValueError, TypeError)` に限定
