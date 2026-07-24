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
- **merge_pull_request**: `method="rebase"` の場合、GitLab の `/rebase` エンドポイントは対象ブランチへの rebase のみを行いマージはしない。`/rebase` → `include_rebase_in_progress=true` での `GET` ポーリング（`rebase_in_progress` が `false` になるまで。`merge_error` があれば失敗として送出）→ `/merge` の3段階で実マージする
  - 過去バグ: `/rebase` を呼んで即 return していたため、MR が rebase されるだけでマージされず open のまま残っていた（例外は出ないため成功したように見えた）
- **create_or_update_file**: `None` を返す（GitLab files API は SHA を返さない）
- **認証**: `PRIVATE-TOKEN: {token}` ヘッダ
- **プロジェクト ID の URL エンコード**: `owner/repo` を `%2F` エンコード（`urllib.parse.quote(path, safe='')`）。サブグループ `group/sub/repo` も同様に処理される
- **ページネーション**: `X-Next-Page` ヘッダが空文字 = 最終ページ。`per_page` デフォルト 20、最大 100
- **URL エンコード必須のパス**: Release タグ名・ラベル名の DELETE でタグ名/ラベル名を URL エンコードすること
- **`remove_issue_reaction`**: `list_issue_reactions` の結果を `content` だけで絞り込まず、`get_current_username()` で自分自身のリアクションに限定してから削除対象の ID を決定すること（GitHub の同種修正 #161 と同じバグクラス）
  - 過去バグ: content の一致だけで最初の1件を削除しており、他ユーザーの同種リアクションを削除しうる状態だった
- **`set_variable`**: GitLab は `gfo secret` と `gfo variable` が同一の CI/CD variables コレクションを `masked` フラグで共有する。既存レコードを GET した際は `masked` を読み、呼び出し元の `masked` との論理和（OR）で PUT すること（Bitbucket の `secured` フラグ絞り込み #138 と同じ根本原因）
  - 過去バグ: 既存の `masked: True`（secret）を確認せず呼び出し元の既定値 `masked: False` で無条件 PUT しており、`gfo variable set` が既存 secret を平文へ格下げしていた
- **`list_pull_request_checks` の pipeline status**（`CheckRun.status`）: GitLab CI パイプラインの `status` は `created`/`waiting_for_resource`/`preparing`/`pending`/`running`/`success`/`failed`/`canceled`/`skipped`/`manual`/`scheduled` の11値を公式に取りうる。`status_map` はこの全値をカバーすること（未マップの値は `.get(status, status)` のフォールバックで契約外の生値が `CheckRun.status` に漏れる）
  - 過去バグ（#230）: `waiting_for_resource`（`resource_group` 使用時）・`preparing`・`scheduled`（delayed job）が `status_map` に無く、生値のまま漏れていた。いずれも `"pending"` へ正規化して解決
- **`remove_issue_dependency`**: GitLab の Issue Links API は削除に内部の `issue_link_id` が必要で `depends_on`（対象 issue の iid）から直接指定できないため、一覧取得 → `iid` 一致検索 → 一致したリンクを DELETE、という手順を踏む。一致するリンクが1件も見つからなかった場合は `NotFoundError` を送出すること（黙って正常終了しない）
  - 過去バグ（#218）: 一致が見つからない場合のフォールバックが無く、`for` ループを抜けて暗黙に `None` を返して正常終了していた。CLI 層（`handle_depends`）は戻り値を確認せず常に成功メッセージを出すため、既に存在しない依存関係を指定しても「削除しました」と表示されていた。Azure DevOps にも同じバグクラスがあり #242 で追跡中
