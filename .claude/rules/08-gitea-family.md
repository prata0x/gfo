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
- **マイルストーン**: `number` フィールドなし → `id` でフォールバック（`github_like.py: _to_milestone`）
- **review state**（`github_like.py: _to_review`）: Gitea の実際の API 値（`go-gitea/gitea` の `ReviewStateType`）は GitHub と異なる文字列を使う。`state_map` は両方の値を含めること
  - `COMMENT`（Gitea）≠ `COMMENTED`（GitHub）
  - `REQUEST_CHANGES`（Gitea）≠ `CHANGES_REQUESTED`（GitHub）
  - `REQUEST_REVIEW`（Gitea 固有。レビュー依頼のみで未提出）→ `pending` へ正規化
  - 過去バグ（#187）: GitHub の値のみを map しており、Gitea 側は map に一致せず `raw_state.lower()` のフォールバックで非正規化文字列（`comment`/`request_changes`）になっていた。既存テスト（`test_gitea.py`）も GitHub 風の値でしかテストしておらず、この不一致に気づけていなかった
- **`visibility`**（`github_like.py: _to_repository`）: GitHub は `visibility` フィールド（`"public"`/`"private"`/`"internal"`）を直接返すが、Gitea/Forgejo にはこのフィールドが無く、代わりに独立した `private`（bool）と `internal`（bool）の2フィールドを持つ。フォールバック判定は `private` だけでなく `internal` も見ること
  - 過去バグ（#205）: フォールバックが `private` しか見ておらず、Gitea の internal リポジトリ（`private: False, internal: True`）が常に `"public"` と誤判定されていた
- **issue dependency（`add_issue_dependency` / `remove_issue_dependency`）**: リクエスト body は `{"index": ..., "owner": ..., "repo": ...}`（`IssueMeta` 構造体のフィールド名）。`{"id": ...}` ではない
  - 過去バグ: `id` フィールドを送っており Go 側の JSON バインドで全フィールドがゼロ値になっていた
- **commit status "warning"**（`github_like.py: _to_check_run`）: Gitea の commit status API は `pending`/`success`/`error`/`failure`/`warning` の5値を返す。`CheckRun.status` は `"success" | "failure" | "pending" | "running"` の契約のみを許すため、GitHub には存在しない `warning` は `status_map` で明示的に `failure` へ正規化すること（severity 的には failure より軽いが、フォールバックで生の `"warning"` を契約外のまま漏らすよりは安全側に倒す）
  - 過去バグ（#227）: `status_map` に `warning` のマッピングが無く、`.get(state, state)` のフォールバックで生値 `"warning"` がそのまま `CheckRun.status` に漏れていた

## Gogs 固有

- `html_url` フィールドなし → `data.get("html_url") or ""`
- リリース API 未サポート → `NotSupportedError` でオーバーライド
- deploy key API 未サポート → `NotSupportedError`（`list/create/delete_deploy_key`）
- リポジトリ作成: `auto_init: True` に加えて `readme: "Default"` が必要
- `create_or_update_file`: `NotSupportedError`

## GitBucket 固有

- **継承元**: `GitHubAdapter` のサブクラス（`GiteaAdapter` ではない）
- **JSON 二重エンコード**: PR create / release create のレスポンスが JSON 文字列 → `_parse_response()` でパース（create 系のみ発生、list/get は正常）
- **close_issue**: PATCH /issues/{number} 未実装 → Web UI `POST /{owner}/{repo}/issue_comments/state` 経由
- **ブランチ作成**: POST /git/refs が 500 → git clone + push で代替
- **デフォルトブランチ**: `master`（GitHub の `main` とは異なる）
- **`_to_release()` オーバーライド**: `created_at` / `html_url` なし対応
- **deploy key API**: エンドポイント未実装（HTTP 500）→ `NotSupportedError`
