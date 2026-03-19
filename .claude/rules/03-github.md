---
paths:
  - "**/github.py"
  - "**/test_github.py"
---

# GitHub アダプター固有ルール

## 重要な実装パターン

- **list_issues**: PR を除外するため `"pull_request" not in r` でフィルタ
- **state="merged"**: GitHub API は `closed` で返すため、クライアント側でフィルタ
  ```python
  if state == "merged":
      items = [pr for pr in items if pr.merged_at is not None]
  ```
- **search_issues**: クエリに `is:issue` を自動付与（PR が混入しないよう）
- **create_or_update_file**: `commit.sha` を返す（ブランチ伝播遅延対策）
- **認証**: `Authorization: Bearer {token}` ヘッダ
- **Release 削除**: リリース削除ではタグは自動削除されない。タグも消すなら `DELETE /git/refs/tags/{tag}` を別途呼ぶ必要あり
- **Release 削除の ID 解決**: タグ名 → release id の 2 段階（`GET /releases/tags/{tag}` → `DELETE /releases/{id}`）
