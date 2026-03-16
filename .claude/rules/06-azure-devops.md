---
paths:
  - "**/azure_devops.py"
  - "**/test_azure_devops.py"
  - "src/gfo/commands/init.py"
  - "src/gfo/commands/repo.py"
---

# Azure DevOps アダプター固有ルール

## 必須パラメータ

- コンストラクタに `organization` と `project_key` が必要
- `gfo init` 手動設定パスで `organization` の追加入力フローがある
- URL 構築失敗時のエラーメッセージ: `'gfo init' を実行してください` を含めること

## 重要な実装パターン

- **connectionData**: 組織レベル URL + `api-version=7.1-preview` で呼ぶ
- **Content-Type**: `application/json-patch+json`（Work Items 操作時）
- **Issue 取得**: WIQL クエリ経由
- **ブランチ名**: `refs/heads/` プレフィックスを除去して返す
- **create_or_update_file**: `commits[0].commitId` を返す（pushes API レスポンス）
- **認証**: `AZURE_DEVOPS_PAT` を Basic 認証（username 空、password = PAT）

## 組織関連

- **`list_org_repos`**: `limit=0` で全件取得 → プロジェクト名フィルタ → `[:limit]` 適用
  - 過去バグ: フィルタ前に limit を適用して結果が過少になった
- **`_to_organization`**: `_links.web.href` 優先、フォールバック `https://dev.azure.com/{org}/{name}`
  - 過去バグ: API URL を返していた
- **`org members`**: `NotSupportedError`（Azure DevOps はチームベースのメンバー管理で組織メンバー一覧 API がない）

## コマンド側の注意

- `commands/repo.py` の `handle_create`: `organization` / `project_key` が `None` のチェック必須
