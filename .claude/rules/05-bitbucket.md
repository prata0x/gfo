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

## ブランチ保護・パイプライン変数

- **`get_branch_protection`**: `params={"kind": "push"}` でフィルタ禁止（全 kind を取得すること）
  - 過去バグ: kind フィルタで取得漏れが発生
- **`_find_pipeline_variable_uuid`**: `limit=0`（全件取得）を使うこと
  - 過去バグ: 100件上限だと変数が見つからない
- **`set_variable` / `set_secret`**: upsert パターン必須（GET で存在チェック → PUT/POST 使い分け）
  - 過去バグ: POST のみだと既存変数で API エラー

## 非対応機能

`NotSupportedError` でオーバーライド: `releases`, `labels`, `milestones`, コメント更新/削除
