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

- **BQL（Bitbucket Query Language）へ値を埋め込む箇所は必ず `_escape_bql_string()` を通すこと**: `q=` クエリパラメータへ文字列を `f'field="{value}"'` の形で埋め込む箇所（`list_issues`/`list_pull_requests`/`search_repositories` 等）は、直接値を渡す分岐も含めて漏れなくエスケープすること
  - 過去バグ（#174/#180/#183）: `author`/`base`/`head`（PR一覧）、`state` の直接値指定分岐（issue 一覧）が未エスケープのままリテラルに埋め込まれており、値に `"` を含めるとリテラルが早期終端し、後続の BQL 式が注入されうる状態だった。修正時は新規追加箇所だけでなく既存の類似分岐も横断的に確認すること（#183 は #180 のレビュー中に発見された "同じクラスだが見落とされていた" 分岐）
- **list_issues ラベルフィルタ**: `component.name="{label}"` クエリパラメータ
  - 過去バグ: パラメータが未使用のまま放置されていた
- **state**: 大文字形式 `OPEN`, `MERGED`, `DECLINED`
- **コラボレーター取得**: `permissions-config/users` エンドポイントを使用
  - 過去バグ: workspace members を使っていたが誤り
- **assignee チェック**: `isinstance(assignee, dict)` を必ず確認
  - 過去バグ: dict でない場合に KeyError が発生
- **create_or_update_file**: `None` を返す（Bitbucket API は SHA を返さない）
- **`create_commit_status` の `url`**: Bitbucket の Build Status API は `url` を必須とする。`--url` 省略時のフォールバックは `{_web_base_url()}/{owner}/{repo}/commits/{ref}`（対象コミットの実際の Web UI ページ）を使うこと
  - 過去バグ（#179）: フォールバックが無関係なダミー値 `https://example.com` 固定で、Bitbucket UI 上のステータスリンクが IANA の予約ドメインに誘導されていた

## ブランチ保護・パイプライン変数

- **`get_branch_protection`**: `params={"kind": "push"}` でフィルタ禁止（全 kind を取得すること）
  - 過去バグ: kind フィルタで取得漏れが発生
- **`_find_pipeline_variable_uuid`**: `limit=0`（全件取得）を使うこと
  - 過去バグ: 100件上限だと変数が見つからない
- **`_find_pipeline_variable_uuid`**: secret（`secured: True`）と variable（`secured: False`）は同一コレクションを共有するため、名前だけでなく `secured` フラグも引数で指定して絞り込むこと
  - 過去バグ: `secured` フラグで絞り込んでいなかったため、既存 secret と同名で `variable set` すると secret 側が `secured: False` で上書きされ平文化していた
- **`set_variable` / `set_secret`**: upsert パターン必須（GET で存在チェック → PUT/POST 使い分け）
  - 過去バグ: POST のみだと既存変数で API エラー

## PR checkout

- **refspec はブランチ名**: GitHub の `refs/pull/{number}/head` とは異なり、ソースブランチ名をそのまま返す

## ファイル操作

- **multipart/form-data**: `create_or_update_file` は JSON ではなく `multipart/form-data` で送信

## 非対応機能

`NotSupportedError` でオーバーライド: `releases`, `labels`, `milestones`, コメント更新/削除

## Deploy Key

- **`create_deploy_key`**: Bitbucket Cloud の Access Key（Deploy Key）は API レベルで read-only 固定であり、read/write を選択するパラメータ自体が存在しない（Bitbucket **Server**（オンプレミス版）にのみある機能で、Cloud には無い）。`read_only=False`（`--read-write` 相当）が渡された場合は payload に何も追加せず、`warnings.warn` で明示的に警告すること
  - `_warn_unsupported_params` の truthy チェックは通せない（`read_only=False` は falsy なので検知できない）ため、`if not read_only:` の明示チェックで個別に警告する必要がある（#200）

## SSH Key / GPG Key

- **`{selected_user}` は認証済みユーザーの UUID を使う**: `/users/{selected_user}/ssh-keys`・`/users/{selected_user}/gpg-keys` は個人アカウント専用のエンドポイントで、`{selected_user}` にはワークスペース slug ではなく認証済みユーザー自身の UUID（または Atlassian Account ID）を渡す必要がある。`_current_user_uuid()`（`get_current_user()["uuid"]`）を使うこと
  - 過去バグ（#216）: リポジトリ spec の owner セグメント（`self._owner`）をそのまま `{selected_user}` に埋め込んでおり、個人アカウント所有リポジトリでは偶然 owner=本人のユーザー名と一致するため動作しうるが、ワークスペース（チーム）所有リポジトリでは owner がワークスペース slug になり、個人アカウント識別子として不正な値になっていた
