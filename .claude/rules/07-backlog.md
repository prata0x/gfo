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
- **`list_issues` の `--state open` フィルタ**: 固定リストで `statusId[]` を組み立てない。`_resolve_all_status_ids()`（`_fetch_statuses()` の結果をキャッシュ共有）で `/projects/{projectKey}/statuses`（Issue 用ステータス一覧）から動的に全ステータス ID を取得し、closed を除いた ID を使うこと
  - 過去バグ（#191）: `statusId[] = [1, 2, 3]` を固定送信しており、カスタムステータスの課題が `--state open`（省略時含む）の一覧から取りこぼされていた。個別取得（`get_issue`）は `statusId != 4` で正しく open 判定するため、一覧と個別取得で挙動が矛盾していた
- **`list_pull_requests` の `--state open` フィルタは `_PR_OPEN_STATUS_IDS = [1, 2, 3]` 固定のままにすること**。`/projects/{projectKey}/statuses` は Issue 用ステータス一覧であり、PR のステータス空間が Issue と同一かどうかは未確認（公式ドキュメントにも明記なし）。`list_issues` と同じ動的解決を PR にも適用しない
  - 過去バグ（#194）: #191 で PR 側にも `_resolve_all_status_ids()` を適用してしまい、Issue 用カスタムステータス ID（例: id=6）が PR 一覧の `statusId[]` フィルタにそのまま流用されていた
  - `_resolve_merged_status_id()`（`state="merged"`/`"all"` で使用）も同じ Issue 用エンドポイントで名前に "merged" を含むステータスを検索しているが、この動的解決が実際に機能しているか（Issue ステータス名に "merged" が含まれるケースが実サービスに存在するか）は未検証。常にハードコードされた `_STATUS_MERGED_ID = 5` へのフォールバックになっている可能性がある（未確定・要実サービス検証）

## Issue 作成の自動解決

- **issueTypeId**: `/projects/{projectKey}/issueTypes` の先頭要素を使用。空なら `GfoError`
- **priorityId**: `/priorities` から `"中"` or `"normal"` を含む要素を優先、なければ先頭要素
