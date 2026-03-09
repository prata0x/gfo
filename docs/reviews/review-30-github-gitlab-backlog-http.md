# gfo Review Report — Round 30: github / gitlab / backlog / http 精査

## 概要

- **レビュー日**: 2026-03-09
- **対象**:
  - `src/gfo/adapter/github.py`
  - `src/gfo/adapter/gitea.py`（get_repository の一貫性）
  - `src/gfo/adapter/gitlab.py`
  - `src/gfo/adapter/backlog.py`
  - `src/gfo/http.py`
  - `tests/test_adapters/test_github.py`
  - `tests/test_adapters/test_backlog.py`
  - `tests/test_http.py`

- **発見事項**: 新規 4 件（重大 0 / 中 2 / 軽微 2）

---

## エージェントレビューで誤報された項目（問題なし確認）

| 確認項目 | 結果 |
|---------|------|
| `backlog.py` `statusId[]` のリスト形式エラー | OK — `requests` ライブラリはリスト値を `statusId[]=1&statusId[]=2&statusId[]=3` に正しく展開する |
| `http.py` `_parse_retry_after` の負秒数処理 | OK — `max(1, min(diff, _MAX_RETRY_AFTER))` で負値は 1 秒にクランプされる |

---

## 新規発見事項

---

### [R30-01] 🟡 `github.py` L129 / `gitea.py` L128 — `get_repository()` が URL エンコードなし

- **ファイル**: `src/gfo/adapter/github.py` L129、`src/gfo/adapter/gitea.py` L128
- **現在のコード**:
  ```python
  # github.py / gitea.py 共通パターン
  resp = self._client.get(f"/repos/{o}/{n}")
  ```
- **説明**: `_repos_path()` は `quote(self._owner, safe='')` / `quote(self._repo, safe='')` で URL エンコードを行うが、`get_repository(owner, name)` では `o` / `n` をエンコードせずに f-string に直接埋め込む。owner/name にスペースや非 ASCII 文字が含まれる場合に API 呼び出しが失敗する可能性がある。
- **影響**: 自己ホスト型インスタンスで特殊文字を含む owner/repo 名を持つケースで `get_repository()` が失敗する。
- **推奨修正**: `f"/repos/{quote(o, safe='')}/{quote(n, safe='')}"` に変更する。

---

### [R30-02] 🟡 `gitlab.py` L277 / L296 — `list_labels` / `list_milestones` のデフォルト `limit=30` で全件取得不可

- **ファイル**: `src/gfo/adapter/gitlab.py` L277、L296
- **現在のコード**:
  ```python
  def list_labels(self, *, limit: int = 30) -> list[Label]:
  def list_milestones(self, *, limit: int = 30) -> list[Milestone]:
  ```
- **説明**: R27-02/03 で Gitea の同様の問題を修正（`limit=0` で全件取得）したが、GitLab も同じ問題を持つ。`paginate_page_param` に `limit=30` を渡すため、30 件超のラベル/マイルストーンが取得できない。また `base.py` の抽象メソッドは `limit` パラメータを持たない（GitLab だけ異なるシグネチャ）。
- **影響**: 31 件以上のラベル/マイルストーンを持つ GitLab リポジトリで全件取得できない。
- **推奨修正**: デフォルトを `limit=0`（無制限）に変更する。

---

### [R30-03] 🟢 `tests/test_http.py` — `_parse_retry_after()` の直接テストなし

- **ファイル**: `tests/test_http.py`
- **説明**: `HttpClient._parse_retry_after()` は単体テストされていない。テストは `TestRateLimit` クラスを通じて間接的にのみ確認される。HTTP-date 形式（`Mon, 09 Mar 2026 15:30:00 GMT` など）、`None`、不正値のケースが未テスト。
- **推奨修正**: `_parse_retry_after()` の直接テストを追加する。

---

### [R30-04] 🟢 `tests/test_adapters/test_github.py` / `test_gitea.py` — `get_repository()` の URL エンコードテストなし

- **ファイル**: `tests/test_adapters/test_github.py`、`tests/test_adapters/test_gitea.py`
- **説明**: R30-01 の修正（URL エンコード追加）に対応したテストが不足している。
- **推奨修正**: R30-01 修正後にテストを追加する。

---

## 全問題サマリー（R30）

| ID | 重大度 | ファイル | 概要 | 状態 |
|----|--------|---------|------|------|
| **R30-01** | 🟡 中 | `github.py` L129 / `gitea.py` L128 | `get_repository()` に URL エンコードなし | ✅ 修正済み |
| **R30-02** | 🟡 中 | `gitlab.py` L277/L296 | `list_labels`/`list_milestones` の limit=30 上限 | ✅ 修正済み |
| **R30-03** | 🟢 軽微 | `test_http.py` | `_parse_retry_after()` 直接テストなし | ✅ 修正済み |
| **R30-04** | 🟢 軽微 | `test_github.py`/`test_gitea.py` | `get_repository()` URL エンコードテストなし | ✅ 修正済み |

---

## 推奨アクション（優先度順）

1. ~~**[R30-01]**~~ ✅ 修正済み
2. ~~**[R30-02]**~~ ✅ 修正済み
3. ~~**[R30-03]**~~ ✅ 修正済み
4. ~~**[R30-04]**~~ ✅ 修正済み

## 修正コミット（R30）

| コミット | 修正内容 |
|---------|---------|
| （次のコミット） | R30-01〜04 — URL エンコード修正・limit=0 対応・テスト追加 |
