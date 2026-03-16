---
paths:
  - "**/gitea.py"
  - "**/forgejo.py"
  - "**/gogs.py"
  - "**/gitbucket.py"
  - "**/test_gitea.py"
  - "**/test_forgejo.py"
  - "**/test_gogs.py"
  - "**/test_gitbucket.py"
---

# Gitea ファミリー固有ルール

## 共通パターン（Gitea / Forgejo / Gogs / GitBucket）

- **`_to_organization`**: `data.get("website")` ではなく `{base_url}/{org_name}` で組織ページ URL を構築すること
  - 過去バグ: `website` フィールドは外部サイト URL であり、組織ページ URL ではない
- **PR merge**: `Do` パラメータ（GitHub の `merge_method` とは異なる）
- **list_issues**: `type: "issues"` + `not r.get("pull_request")` でフィルタ
  - Gitea はissueレスポンスに `pull_request: null` が含まれる
- **ページネーション**: `per_page_key="limit"`
- **マイルストーン**: `number` フィールドなし → `id` でフォールバック（`base.py: _to_milestone`）

## Gogs 固有

- `html_url` フィールドなし → `data.get("html_url") or ""`
- リリース API 未サポート → `NotSupportedError` でオーバーライド
- リポジトリ作成: `auto_init: True` に加えて `readme: "Default"` が必要
- `create_or_update_file`: `NotSupportedError`

## GitBucket 固有

- **継承元**: `GitHubAdapter` のサブクラス（`GiteaAdapter` ではない）
- **JSON 二重エンコード**: PR create / release create のレスポンスが JSON 文字列 → `_parse_response()` でパース
- **close_issue**: PATCH /issues/{number} 未実装 → Web UI `POST /{owner}/{repo}/issue_comments/state` 経由
- **ブランチ作成**: POST /git/refs が 500 → git clone + push で代替
- **デフォルトブランチ**: `master`（GitHub の `main` とは異なる）
- **`_to_release()` オーバーライド**: `created_at` / `html_url` なし対応
