# gfo Review Report — Round 25: azure_devops / http / gitea / base 精査

## 概要

- **レビュー日**: 2026-03-09
- **対象**:
  - `src/gfo/adapter/azure_devops.py`
  - `src/gfo/adapter/base.py`
  - `src/gfo/adapter/gitea.py`
  - `src/gfo/adapter/forgejo.py`
  - `src/gfo/adapter/gitbucket.py`
  - `src/gfo/git_util.py`
  - `src/gfo/http.py`
  - `src/gfo/__init__.py`, `src/gfo/__main__.py`
  - `tests/test_adapters/test_azure_devops.py`
  - `tests/test_adapters/test_gitea.py`

- **発見事項**: 新規 8 件（重大 0 / 中 4 / 軽微 4）、既知課題 2 件の現状確認

---

## 既知残課題の現状確認

| ID | 状態 |
|----|------|
| R13-03 | `gitea.py` `list_issues` フィルタ後 limit 未満 — **継続中（設計決定待ち）** |
| R24-06 | `http.py` `paginate_link_header` の JSON 型チェック不備 — **継続中** |

---

## 新規発見事項

---

### [R25-01] 🟡 `adapter/azure_devops.py` L89 — `_to_issue` の assignee `uniqueName` KeyError リスク

- **ファイル**: `src/gfo/adapter/azure_devops.py` L88-89
- **現在のコード**:
  ```python
  assigned_to = fields.get("System.AssignedTo")
  assignees = [assigned_to["uniqueName"]] if assigned_to else []
  ```
- **説明**: `assigned_to` が空でない dict の場合 truthy チェックを通過するが、`uniqueName` キーが存在しない場合（`{"displayName": "someone"}` など）は `KeyError` が発生する。外側の `try-except (KeyError, TypeError)` でキャッチされて `GfoError` に変換されるが、エラーメッセージが不明瞭になる。
- **影響**: Azure DevOps が `uniqueName` なしの assignee オブジェクトを返した場合に不明瞭な GfoError が発生する。
- **推奨修正**: `assigned_to.get("uniqueName")` を使用して安全にアクセスする。

---

### [R25-02] 🔴 `adapter/azure_devops.py` L198,216 — `list_issues` の `limit=0` バグ

- **ファイル**: `src/gfo/adapter/azure_devops.py` L198, L216
- **現在のコード**:
  ```python
  params={"$top": limit},  # limit=0 → "$top": 0
  ...
  return results[:limit]   # limit=0 → results[:0] = []
  ```
- **説明**: `limit=0` は「制限なし（全件取得）」を意味するが（http.py の全ページネーション関数との一貫性）、`list_issues` では `$top=0` を WIQL に渡し、`results[:0]` で空リストを返してしまう。`list_pull_requests` は `paginate_top_skip` を使用しており `limit=0` を正しく処理しているが、`list_issues` だけ独自実装のため処理が異なる。
- **影響**: `list_issues(limit=0)` が常に空リストを返す。
- **推奨修正**: `limit > 0` の場合のみ `$top` と スライスを適用する。

---

### [R25-03] 🟡 `http.py` L240-241 — `paginate_link_header` の `resp.json()` 例外処理なし

- **ファイル**: `src/gfo/http.py` L240
- **説明**: `resp.json()` は `requests.exceptions.JSONDecodeError`（`ValueError` のサブクラス）を送出する可能性があるが、キャッチされていない。通常、`HttpClient.get()` が非 200 レスポンスで `HTTPError` を送出するため実際には発生しにくいが、200 で非 JSON レスポンスを返すサーバーでは問題が発生する。
- **影響**: API が 200 で非 JSON を返した場合に `ValueError` が伝播する。
- **推奨修正**: `try-except ValueError` で囲むか、空リストにフォールバックする。

---

### [R25-04] 🟡 `adapter/azure_devops.py` L206-214 — バッチループの早期終了なし

- **ファイル**: `src/gfo/adapter/azure_devops.py` L206-214
- **説明**: WIQL の `$top=limit` で ID 件数が制限されているため、バッチループが limit を超えることは通常ない。しかし `limit=0`（修正後）やエラー時に念のためのガードとして、バッチループ内で `len(results) >= limit` の早期終了チェックがあると安全。
- **影響**: 軽微。通常の使用では問題なし。
- **推奨修正**: R25-02 の修正に含めてバッチループに早期終了を追加。

---

### [R25-05] 🟢 `http.py` L241 — 空リストの扱いに関するコメント不足

- **ファイル**: `src/gfo/http.py` L241
- **説明**: `paginate_link_header` で `not page_data`（空リスト）をループ終了条件としているが、「最後のページが空リストを返す場合はループを終了」という設計意図がコメントで説明されていない。他のページネーション関数との一貫性を確認するコメントがあると良い。
- **影響**: 軽微。動作上問題なし。

---

### [R25-06] 🟡 `adapter/azure_devops.py` — `list_issues` の limit=0 時 `$top` 処理と `paginate_top_skip` 動作の非一貫性（R25-02 関連）

同 R25-02 を参照。

---

### [R25-07] 🟢 `git_util.py` — `_mask_credentials` の URL エンコード文字を含むケースのテスト不足

- **ファイル**: `src/gfo/git_util.py`
- **説明**: `_mask_credentials()` は `://[^/\s]*@` で認証情報をマスクする。URL エンコード文字（`%3A` など）を含む URL も正しく処理されるが、これに対するテストケースがない。
- **影響**: 軽微。マスク機能自体は動作する。

---

### [R25-08] 🟢 `adapter/gitea.py` / `adapter/github.py` — `state="merged"` 時のフィルタリング後 limit 不足問題（R13-03 継続）

- **説明**: `state="merged"` 指定時に API に `closed` を渡し、返却後にクライアント側でフィルタリングする設計のため、`limit` 個の merged PR が取得できない場合がある。
- **現状**: 既知課題 R13-03 の継続。GitHub/Gitea の仕様上、merged 状態を API 側でフィルタリングする方法がないため、現設計はトレードオフ。
- **推奨**: ドキュメントに「merged は近似値」と明記する。

---

## 全問題サマリー（R25）

| ID | 重大度 | ファイル | 概要 | 状態 |
|----|--------|---------|------|------|
| **R25-01** | 🟡 中 | `azure_devops.py` L89 | `_to_issue` assignee `uniqueName` KeyError リスク | |
| **R25-02** | 🔴 重大 | `azure_devops.py` L198,216 | `list_issues` の `limit=0` バグ（空リスト返却） | |
| **R25-03** | 🟡 中 | `http.py` L240 | `paginate_link_header` の `resp.json()` 例外処理なし | |
| **R25-04** | 🟡 中 | `azure_devops.py` L206-214 | バッチループの早期終了なし | |
| **R25-05** | 🟢 軽微 | `http.py` L241 | 空リストの設計意図コメント不足 | |
| **R25-07** | 🟢 軽微 | `git_util.py` | `_mask_credentials` URL エンコードケースのテスト不足 | |
| **R25-08** | 🟢 軽微 | `gitea.py`/`github.py` | `merged` フィルタ後 limit 不足（R13-03 継続） | 継続中 |
| R13-03 | 🟡 中 | `gitea.py` | フィルタ後 limit 未満（継続） | 継続中 |
| R24-06 | 🟡 中 | `http.py` | `paginate_link_header` JSON 例外処理（R25-03 と重複） | |

---

## 推奨アクション（優先度順）

1. **[R25-02]** `azure_devops.py` — `list_issues` の `limit=0` バグを修正
2. **[R25-01]** `azure_devops.py` — `_to_issue` assignee を `get()` で安全アクセスに変更
3. **[R25-03/R24-06]** `http.py` — `paginate_link_header` の `resp.json()` に try-except を追加
4. **[R25-04]** `azure_devops.py` — バッチループに早期終了を追加
5. **[R25-05/07]** 軽微な問題（低優先度）
