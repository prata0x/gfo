---
paths:
  - "**/bitbucket.py"
  - "**/test_bitbucket.py"
---

# Bitbucket アダプター固有ルール

## 認証

- トークン形式: `email:api-token`（コロン区切り）
- Basic 認証で送信（`Authorization: Basic {base64(email:api-token)}`）
- 環境変数: `BITBUCKET_TOKEN`

## 重要な実装パターン

- **list_issues ラベルフィルタ**: `component.name="{label}"` クエリパラメータ
  - 過去バグ: パラメータが未使用のまま放置されていた
- **state**: 大文字形式 `OPEN`, `MERGED`, `DECLINED`
- **コラボレーター取得**: `permissions-config/users` エンドポイントを使用
  - 過去バグ: workspace members を使っていたが誤り
- **assignee チェック**: `isinstance(assignee, dict)` を必ず確認
  - 過去バグ: dict でない場合に KeyError が発生
- **create_or_update_file**: `None` を返す（Bitbucket API は SHA を返さない）

## 非対応機能

`NotSupportedError` でオーバーライド: `releases`, `labels`, `milestones`, コメント更新/削除
