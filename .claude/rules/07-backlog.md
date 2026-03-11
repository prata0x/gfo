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
