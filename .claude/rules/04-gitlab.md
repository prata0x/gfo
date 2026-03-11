---
paths:
  - "**/gitlab.py"
  - "**/test_gitlab.py"
---

# GitLab アダプター固有ルール

## 重要な実装パターン

- **iid vs global id**: GitLab は `iid`（プロジェクト内連番）と `id`（グローバル）が別物
  - `delete_milestone` 等で iid → global id の解決が必要
- **state マッピング**: GitLab `opened` → gfo `open` に変換
- **リポジトリ識別**: `name` ではなく `path`（URL セーフ）を使う
- **ラベル color**: GitLab は `#RRGGBB` 形式。追加/除去時に `#` プレフィックスの処理に注意
- **merge_pull_request**: `method="rebase"` の場合は `/rebase` エンドポイントを使用
- **create_or_update_file**: `None` を返す（GitLab files API は SHA を返さない）
- **認証**: `PRIVATE-TOKEN: {token}` ヘッダ
