# gfo Review Report — Round 26: github / gitlab / bitbucket / backlog / http 精査

## 概要

- **レビュー日**: 2026-03-09
- **対象**:
  - `src/gfo/adapter/github.py`
  - `src/gfo/adapter/gitlab.py`
  - `src/gfo/adapter/backlog.py`
  - `src/gfo/adapter/bitbucket.py`
  - `src/gfo/http.py`
  - `tests/test_adapters/test_github.py`
  - `tests/test_adapters/test_gitlab.py`
  - `tests/test_adapters/test_backlog.py`
  - `tests/test_adapters/test_bitbucket.py`

- **発見事項**: 新規 8 件（重大 1 / 中 2 / 軽微 5）

---

## 修正済み・問題なし確認（OK）

| 確認項目 | 結果 |
|---------|------|
| `github.py` `merged_at` による merged 状態判定 | OK — GitHub API は常に `merged_at` フィールドを返す（null または日時文字列）。現実装で正確 |
| `http.py` `paginate_page_param` の `int()` 変換 | OK — L294-297 の try-except ValueError で既に対応済み |
| `http.py` `paginate_link_header` の JSON 例外 | OK — R25-03 で修正済み |

---

## 新規発見事項

---

### [R26-01] 🔴 `adapter/gitlab.py` L165-166 — `merge_pull_request` の `method="rebase"` が誤った API エンドポイントを呼び出す

- **ファイル**: `src/gfo/adapter/gitlab.py` L165-166
- **現在のコード**:
  ```python
  elif method == "rebase":
      payload["merge_method"] = "rebase_merge"
  ```
- **説明**: `method="rebase"` の場合、GitLab API では **`/merge_requests/:iid/merge`** エンドポイントに `merge_method=rebase_merge` を送るのではなく、別エンドポイント **`/merge_requests/:iid/rebase`** を `PUT` で呼び出す。`merge_method` は GitLab のマージリクエスト設定（project level）であり、個別マージ操作のパラメータではない。
- **影響**: `method="rebase"` を指定すると `merge_method: rebase_merge` がマージ API に送信されるが、GitLab は不明パラメータを無視してデフォルト merge を実行する（または 400 エラーになる）。rebase ではなく通常 merge が行われる。
- **推奨修正**: `method="rebase"` の場合は `/rebase` エンドポイントを呼び出す。

---

### [R26-02] 🟡 `adapter/bitbucket.py` L63 — `_to_issue` assignee の nickname が空文字の場合にリストへ追加

- **ファイル**: `src/gfo/adapter/bitbucket.py` L63
- **現在のコード**:
  ```python
  assignees = [assignee.get("nickname", "")] if assignee else []
  ```
- **説明**: `assignee` が `{"displayName": "user"}` など `nickname` キーなしのオブジェクトの場合、`get("nickname", "")` は `""` を返し `[""]` が assignees に格納される。
- **影響**: assignees フィールドに空文字列が入り、API 利用側でのフィルタリングやユーザー名検証に影響する。
- **推奨修正**: `nickname` の値が truthy な場合のみリストに追加する。

---

### [R26-03] 🟡 `adapter/gitlab.py` — `merge_pull_request` の `method="merge"` のリクエストボディにテストなし

- **ファイル**: `tests/test_adapters/test_gitlab.py` TestMergePullRequest
- **説明**: `test_merge_squash` では `squash: true` の検証があるが、`test_merge`（デフォルト `method="merge"`）はリクエストボディが検証されていない。`method="merge"` の場合、payload は空 dict `{}` で送信されることが設計上の意図だが、テストで確認されていない。
- **影響**: リグレッション検出能力の不足。
- **推奨修正**: `test_merge` にリクエストボディが `{}` であることの検証を追加する。

---

### [R26-04] 🟢 `http.py` L241 — `paginate_link_header` の非 JSON break が無言で終了

- **ファイル**: `src/gfo/http.py` L242-244（R25-03 で追加した処理）
- **説明**: 非 JSON レスポンスで `ValueError` をキャッチした場合、コメントはあるが呼び出し側に情報が伝わらない。デバッグ時に気づきにくい。
- **影響**: 軽微。設計上意図的な動作（安全フォールバック）。
- **推奨修正**: 現状維持で問題なし。

---

### [R26-05] 🟢 `adapter/bitbucket.py` `list_issues` — state バリデーションなし

- **ファイル**: `src/gfo/adapter/bitbucket.py`
- **説明**: `list_issues` の `state` パラメータに対して有効値チェックがない。不正な値が Bitbucket API にそのまま送信される。GitHub・GitLab では CLI layer で検証されているため、アダプター層で検証しなくても実用上問題は少ない。
- **影響**: 不正な state 値を渡すと Bitbucket API が 400 を返す（アダプター内でのフレンドリーなエラーメッセージなし）。
- **推奨修正**: 必要に応じてバリデーションを追加（低優先度）。

---

### [R26-06] 🟢 `tests/test_adapters/test_github.py` — Link ヘッダーに `per_page` なし

- **ファイル**: `tests/test_adapters/test_github.py`
- **説明**: `test_pagination` の Link ヘッダーが `?page=2` のみで `per_page` パラメータがない。実際の GitHub API Link ヘッダーは `?per_page=30&page=2` 形式。機能上の問題はないが、テストが実際の API 形式から乖離している。
- **影響**: 軽微。

---

### [R26-07] 🟢 `adapter/backlog.py` — `_to_issue` のエラーメッセージのコンテキスト不足

- **ファイル**: `src/gfo/adapter/backlog.py`
- **説明**: `_to_issue` 内の issueKey パース処理で `AttributeError` が発生した場合、外側の `try-except (KeyError, TypeError, ValueError)` でキャッチされず `GfoError` に変換されない。R22-04 で修正済みの範囲内での動作は正しいが、エラーメッセージが冗長になる可能性がある。
- **影響**: 軽微。現状の機能に問題はない。

---

### [R26-08] 🟢 `tests/test_adapters/test_gitlab.py` — `merge_pull_request` の rebase テストなし

- **ファイル**: `tests/test_adapters/test_gitlab.py`
- **説明**: R26-01 の修正（rebase → `/rebase` エンドポイント）に対応したテストが不足している。
- **推奨修正**: R26-01 の修正と同時にテストを追加。

---

## 全問題サマリー（R26）

| ID | 重大度 | ファイル | 概要 |
|----|--------|---------|------|
| **R26-01** | 🔴 重大 | `gitlab.py` L165 | `merge_pull_request` の `method="rebase"` が誤った API エンドポイント |
| **R26-02** | 🟡 中 | `bitbucket.py` L63 | `_to_issue` assignee nickname 空文字問題 |
| **R26-03** | 🟡 中 | `test_gitlab.py` | `test_merge` のリクエストボディ検証不足 |
| **R26-04** | 🟢 軽微 | `http.py` | 非 JSON break が無言（R25-03 設計上の選択） |
| **R26-05** | 🟢 軽微 | `bitbucket.py` | `list_issues` state バリデーションなし |
| **R26-06** | 🟢 軽微 | `test_github.py` | Link ヘッダーに `per_page` なし |
| **R26-07** | 🟢 軽微 | `backlog.py` | `_to_issue` エラーメッセージのコンテキスト不足 |
| **R26-08** | 🟢 軽微 | `test_gitlab.py` | `merge_pull_request` rebase テストなし |

---

## 推奨アクション（優先度順）

1. **[R26-01]** `gitlab.py` — `method="rebase"` を `/rebase` エンドポイントに修正
2. **[R26-02]** `bitbucket.py` — assignee nickname 空文字チェックを追加
3. **[R26-03/08]** `test_gitlab.py` — `test_merge` ボディ検証・rebase テストを追加
4. **[R26-05/06/07]** 軽微な問題（低優先度）
