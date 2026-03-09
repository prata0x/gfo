# gfo Review Report — Round 22: github / backlog / azure-devops / auth 精査

## 概要

- **レビュー日**: 2026-03-09
- **対象**:
  - `src/gfo/adapter/github.py` — GitHub アダプター
  - `src/gfo/adapter/backlog.py` — Backlog アダプター
  - `src/gfo/adapter/azure_devops.py` — Azure DevOps アダプター
  - `src/gfo/auth.py` — 認証機能
  - `tests/test_adapters/test_github.py` — GitHub テスト
  - `tests/test_adapters/test_backlog.py` — Backlog テスト

- **発見事項**: 新規 10 件（重大 0 / 中 5 / 軽微 5）、既知課題 2 件の現状確認

---

## 既知残課題の現状確認

| ID | 状態 |
|----|------|
| R16-02 | `auth.py` `get_auth_status()` の env var エントリ host 形式が `"env:github"` と `"github.com"` で不統一 — **継続中** |
| R13-03 | `gitea.py` `list_issues` フィルタ後に limit 未満になる問題 — **継続中（設計決定待ち）** |

---

## 修正済み・問題なし確認（OK）

| ファイル | 確認項目 | 結果 |
|---------|---------|------|
| `github.py` | `_repos_path()` の URL エンコード | OK — `quote()` で適切にエンコード済み |
| `github.py` | `list_issues` の PR フィルタ | OK — `"pull_request" not in r` でフィルタ実装済み |
| `azure_devops.py` | PR URL 構築 (`repository.webUrl` + `pullRequestId`) | OK — R12-03 修正済み |
| `backlog.py` | `close_issue` のパス修正 (`-{number}` 形式) | OK — R12-01 修正済み |

---

## 新規発見事項

---

### [R22-01] 🟡 `azure_devops.py` — `list_issues` に PR タイプの Work Item 除外ロジックなし

- **ファイル**: `src/gfo/adapter/azure_devops.py`
- **説明**: Azure DevOps では Pull Request も Work Item として扱われる場合がある。`list_issues` の WIQL クエリに `WorkItemType` フィルタがないため、PR タイプの Work Item が Issue として混入する可能性がある。
- **影響**: `list_issues` の結果に PR が含まれる可能性。
- **推奨修正**: WIQL クエリに `AND [System.WorkItemType] NOT IN ('Pull Request')` を追加するか、取得後に除外する。

---

### [R22-02] 🟡 `backlog.py` L157 — `create_pull_request` が `merged_status_id` を渡さない

- **ファイル**: `src/gfo/adapter/backlog.py` L157
- **現在のコード**:
  ```python
  resp = self._client.post(self._pr_path(), json=payload)
  return self._to_pull_request(resp.json())  # merged_status_id 未指定
  ```
- **説明**: `_to_pull_request(data, merged_status_id=None)` を呼ぶ際、`merged_status_id` を渡していない。`merged_status_id` が `None` の場合、`_STATUS_MERGED_ID = 5` と一致した PR が意図せず merged として分類される可能性がある。
- **影響**: 現在は実務影響低い（新規作成直後の PR は通常 open status）が、将来のリグレッションリスクあり。
- **推奨修正**: `return self._to_pull_request(resp.json(), self._resolve_merged_status_id())` に変更。

---

### [R22-03] 🟢 `azure_devops.py` L108 — `_to_repository` の `project` パラメータ使われ方が不統一

- **ファイル**: `src/gfo/adapter/azure_devops.py` L108-120
- **説明**: `full_name` の構築に引数 `project` を使う一方、`description` は `data["project"]["description"]` から取得。API レスポンスの `project` フィールドと引数 `project` が異なる場合に不整合の可能性がある。
- **影響**: 軽微。実務では通常同一 project 内での操作なので問題なし。
- **推奨修正**: コメント追加で意図を明示。

---

### [R22-04] 🟡 `backlog.py` L100 — `_to_issue` の `issueKey` パース時に ValueError 未処理

- **ファイル**: `src/gfo/adapter/backlog.py` L100
- **現在のコード**:
  ```python
  number=int(data["issueKey"].split("-")[-1]) if isinstance(data.get("issueKey"), str) else data["id"],
  ```
- **説明**: `issueKey` が `"TEST"` のように `-` を含まない場合、`split("-")[-1]` = `"TEST"` となり `int("TEST")` で `ValueError` が発生する。この例外は上位の `except (KeyError, TypeError, ValueError)` でキャッチされるが、`data["id"]` へのフォールバックが行われない（例外として扱われ `GfoError` が発生）。
- **影響**: 不正な issueKey フォーマットで、本来フォールバックできる場面で GfoError になる。
- **推奨修正**:
  ```python
  try:
      number = int(data["issueKey"].split("-")[-1])
  except (ValueError, AttributeError):
      number = data.get("id", 0)
  ```

---

### [R22-05] 🟡 `github.py`, `backlog.py`, `azure_devops.py` — `create_issue` の `**kwargs` が使われない

- **ファイル**: 複数アダプター `create_issue(..., **kwargs)`
- **説明**: `**kwargs` を受け取るシグネチャを持つが、実装内で使用されていない。読者が何を `kwargs` に渡せるのか不明確。
- **影響**: 軽微。ただし将来の混乱の元になる可能性。
- **推奨修正**: 不要であれば削除。Backlog/Azure DevOps の固有パラメータは既に明示的な引数で実装済み。

---

### [R22-06] 🟢 `github.py` L25 — `_repos_path` の制御文字エッジケース

- **ファイル**: `src/gfo/adapter/github.py` L25
- **説明**: `quote()` は制御文字を `%XX` にエンコードするが、owner/repo に改行・タブが含まれた場合 API リクエストが失敗する。通常は発生しないが、ユーザー入力がそのまま渡された場合のバリデーションがない。
- **影響**: 非常に低い実務リスク。
- **推奨修正**: CLI 引数受け取り時点でバリデーションを追加。

---

### [R22-07] 🟡 `azure_devops.py` — `list_issues` のバッチ処理でエラー時にそれまでのデータが失われる

- **ファイル**: `src/gfo/adapter/azure_devops.py`
- **説明**: Work Item の ID 取得後、200件ずつバッチ取得する際、途中のバッチで HTTP エラーが発生すると例外が直伝播し、それまでの `results` が返されない。
- **影響**: 大量の issue 取得時に途中エラーで全データ損失。
- **推奨修正**: バッチ処理全体を適切にエラーハンドリングするか、ページネーション関数の利用を検討。

---

### [R22-08] 🟢 `backlog.py` — `_to_issue` の `assignee` 空オブジェクト未チェック

- **ファイル**: `src/gfo/adapter/backlog.py`
- **現在のコード**:
  ```python
  assignee = data.get("assignee")
  assignees = [assignee["userId"]] if assignee else []
  ```
- **説明**: `assignee` が `{}` の場合、`assignee["userId"]` で `KeyError` が発生。
- **影響**: API が空オブジェクトを返した場合にクラッシュ。
- **推奨修正**: `assignee.get("userId")` を使う。
  ```python
  assignees = [assignee["userId"]] if assignee and "userId" in assignee else []
  ```

---

### [R22-09] 🟡 テストカバレッジ不足 — エッジケース・エラーハンドリング

- **ファイル**: `tests/test_adapters/test_backlog.py`, `tests/test_adapters/test_azure_devops.py`
- **不足内容**:
  - Backlog: `issueKey` に `-` がない場合の `_to_issue` 動作
  - Backlog: `assignee` が `{}` の場合
  - Azure DevOps: Work Item Type = "Pull Request" が `list_issues` から除外されるか
  - Azure DevOps: バッチ処理中エラーの動作

---

### [R22-10] 🟢 `auth.py` L164 — `_write_credentials_toml` のユニコードエスケープが TOML 非対応形式

- **ファイル**: `src/gfo/auth.py` L164
- **現在のコード**:
  ```python
  escaped = re.sub(
      r"[\x00-\x08\x0b\x0c\x0e-\x1f]",
      lambda m: f"\\u{ord(m.group()):04x}",
      escaped,
  )
  ```
- **説明**: TOML では `\uXXXX`（4桁）形式のエスケープをサポートしているが、実際に生成されるのは `\\u00XX` のようなリテラル文字列（バックスラッシュ + `uXXXX`）で TOML パーサーが正しく処理できない可能性がある。
- **影響**: 制御文字を含む稀なトークンで保存・読み込みが失敗する可能性。
- **推奨修正**: Python の `\uXXXX` ではなく文字列に埋め込む形で確認が必要。または `tomllib` でパースして確認するテストを追加。

---

## 全問題サマリー（R22）

| ID | 重大度 | ファイル | 概要 |
|----|--------|---------|------|
| **R22-01** | 🟡 中 | `azure_devops.py` | `list_issues` に PR タイプ除外なし |
| **R22-02** | 🟡 中 | `backlog.py` L157 | `create_pull_request` が `merged_status_id` 未渡し |
| **R22-03** | 🟢 軽微 | `azure_devops.py` L108 | `_to_repository` の `project` 使われ方不統一 |
| **R22-04** | 🟡 中 | `backlog.py` L100 | `issueKey` パース時 `ValueError` 未処理 |
| **R22-05** | 🟡 中 | 複数 | `create_issue` の `**kwargs` が使われない |
| **R22-06** | 🟢 軽微 | `github.py` L25 | `_repos_path` の制御文字エッジケース |
| **R22-07** | 🟡 中 | `azure_devops.py` | バッチ処理エラー時データ損失 |
| **R22-08** | 🟢 軽微 | `backlog.py` | `assignee` 空オブジェクト未チェック |
| **R22-09** | 🟡 中 | テスト全般 | エッジケーステストカバレッジ不足 |
| **R22-10** | 🟢 軽微 | `auth.py` L164 | ユニコードエスケープが TOML 非対応形式の可能性 |
| R16-02 | 🟡 中 | `auth.py` | host 形式不統一（継続） |

---

## 推奨アクション（優先度順）

1. **[R22-04]** `backlog.py` L100 — `issueKey` パース例外を try-catch で処理
2. **[R22-08]** `backlog.py` — `assignee` 空オブジェクトチェック強化
3. **[R22-02]** `backlog.py` L157 — `create_pull_request` に `merged_status_id` を渡す
4. **[R22-01]** `azure_devops.py` — `list_issues` に PR タイプ除外ロジック追加
5. **[R22-05]** 各アダプター — 不要な `**kwargs` を削除
6. **[R22-09]** テスト追加 — Backlog issueKey エッジケース・Azure DevOps バッチエラー
7. **[R22-03]** `azure_devops.py` — コメント追加
8. **[R22-07]** `azure_devops.py` — バッチエラーハンドリング改善
9. **[R16-02]** `auth.py` — env var エントリ host 形式統一
10. **[R22-10]** `auth.py` — エスケープ形式の TOML 互換性テスト追加
