---
paths:
  - "**/backlog.py"
  - "**/test_backlog.py"
---

# Backlog アダプター固有ルール

## 認証

- `apiKey` クエリパラメータで送信（ヘッダではない）
- 環境変数: `BACKLOG_API_KEY`

## 重要な実装パターン

- **project_key 必須**: すべての操作に `project_key` が必要
- **issueKey 形式**: `PROJECT-123`（数値部分を `number` として扱う）
- **`_ensure_project_id`**: `project_key` → `project_id` の変換・キャッシュ
  - KeyError/TypeError は `GfoError` でラップ
- **`_resolve_merged_status_id`**: マージ済みステータス ID を動的解決
  - レスポンスが list であることを検証
  - KeyError はスキップして次の要素を試みる
- **`list_pull_requests`**: `params["statusId[]"] = [merged_id]`（リスト形式で渡す）
- **Issue statusId**: 標準4ステータス（1〜4）に加え、プロジェクトごとに ID 5 以降のカスタムステータスが追加され得る。`statusId == 4` のみ closed、それ以外（カスタム含む）は open
- **`--state open` の一覧フィルタ**: `_STATUS_CLOSED_ID`/`_STATUS_MERGED_ID` の固定リストで `statusId[]` を組み立てない。`_resolve_all_status_ids()`（`_fetch_statuses()` の結果をキャッシュ共有）で動的に全ステータス ID を取得し、closed（Issue）/ closed+merged（PR）を除いた ID を使うこと
  - 過去バグ: `statusId[] = [1, 2, 3]` を固定送信しており、カスタムステータスの課題・PR が `--state open`（省略時含む）の一覧から取りこぼされていた。個別取得（`get_issue`/`get_pull_request`）は `statusId != 4` で正しく open 判定するため、一覧と個別取得で挙動が矛盾していた

## Issue 作成の自動解決

- **issueTypeId**: `/projects/{projectKey}/issueTypes` の先頭要素を使用。空なら `GfoError`
- **priorityId**: `/priorities` から `"中"` or `"normal"` を含む要素を優先、なければ先頭要素
