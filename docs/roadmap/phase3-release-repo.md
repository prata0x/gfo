# 第3弾: Release / Repo 管理の拡充

## TODO

1. [x] **Release download** (#7) — リリースアセットのダウンロード。5サービス対応可能
2. [x] **Release upload** (#8) — リリースアセットのアップロード。4サービス対応可能
3. [x] **Release assets 管理** (#27) — アセットの list/delete。4サービス対応可能
4. [x] **Release latest** (#37) — 最新リリースの取得。5サービス対応可能
5. [x] **Raw API call** (#22) — 任意の API エンドポイント呼び出し。全9サービス対応可能
6. [x] **Repo update** (#12) — リポジトリ設定変更。8サービス対応可能
7. [x] **Repo archive** (#13) — リポジトリのアーカイブ。6サービス対応可能
8. [x] **Repo compare** (#35) — ブランチ/コミット間の比較情報取得。6サービス対応可能
9. [x] **Repo topics** (#34) — リポジトリのトピック/タグ管理。4サービス対応可能
10. [x] **Repo languages** (#36) — リポジトリの言語統計取得。4サービス対応可能

---

## Release download (#7)

リリースアセットをダウンロードする。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | △ | △ | ○ | ○ | × | × | × |

### APIエンドポイント

- **GitHub**: `GET /releases/assets/{id}` に `Accept: application/octet-stream`
- **GitLab**: Release Links API で URL 取得 → ダウンロード
- **Bitbucket**: リリース機能なし。Downloads セクション (`GET /downloads/{filename}`) は利用可能だがリリースと紐付け不可
- **Azure DevOps**: Build Artifacts API でビルド成果物のダウンロードは可能だが Release とのマッピングに工夫必要
- **Gitea/Forgejo**: `GET /releases/{id}/assets/{attachment_id}`

### 実装詳細

- **adapter層**: `BaseAdapter` に `download_release_asset(release_id, asset_id, output_path)` を追加。バイナリストリーミングでファイルに書き出す
- **command層**: `commands/release.py` に `download` サブコマンドを追加。`--tag`, `--pattern`（ファイル名パターン）, `--dir`（出力先）オプション

---

## Release upload (#8)

リリースアセットをアップロードする。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | △ | △ | △ | ○ | ○ | × | × | × |

### APIエンドポイント

- **GitHub**: `POST /releases/{id}/assets?name={name}` でバイナリアップロード
- **GitLab**: Project Uploads API → Release Links API の 2 段階方式
- **Bitbucket**: Downloads セクションへのアップロードのみ（リリース紐付け不可）
- **Gitea/Forgejo**: `POST /releases/{id}/assets?name={filename}`（multipart/form-data）

### 実装詳細

- **adapter層**: `BaseAdapter` に `upload_release_asset(release_id, file_path, name=None)` を追加。GitLab は 2 段階アップロードをアダプター内で吸収
- **command層**: `commands/release.py` に `upload` サブコマンドを追加。引数はタグ名とファイルパス

---

## Release assets 管理 (#27)

リリースアセットの一覧取得・削除。#7 download / #8 upload と合わせて `release asset` サブコマンドグループとして実装。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | × | △ | ○ | ○ | × | × | × |

### APIエンドポイント

- **GitHub**: `GET/POST/DELETE /repos/{owner}/{repo}/releases/{id}/assets`
- **GitLab**: Release Links API (`GET/POST/DELETE /projects/:id/releases/:tag_name/assets/links`)
- **Gitea/Forgejo**: `GET/POST/DELETE /repos/{owner}/{repo}/releases/{id}/assets`

### 実装方針

#7 Release download / #8 Release upload と合わせて `release asset` サブコマンドグループとして実装。list + upload + download + delete の 4 操作をまとめる。

### 実装詳細

- **adapter層**: `BaseAdapter` に `list_release_assets(release_id)` / `delete_release_asset(release_id, asset_id)` を追加
- **command層**: `commands/release.py` に `asset list`, `asset upload`, `asset download`, `asset delete` サブコマンドグループを追加

---

## Release latest (#37)

最新リリースを取得する。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | △ | × | × | ○ | ○ | × | △ | × |

### APIエンドポイント

- **GitHub**: `GET /repos/{owner}/{repo}/releases/latest`
- **GitLab**: 専用エンドポイントなし。一覧取得で先頭を返す形で代替可能
- **Gitea/Forgejo**: `GET /repos/{owner}/{repo}/releases/latest`
- **GitBucket**: 一覧取得して先頭を返す形で代替

### 実装方針

#5 Release view と合わせて `release view --latest` オプションとして実装するのが自然。

### 実装詳細

- **adapter層**: `BaseAdapter` に `get_latest_release()` を追加。専用エンドポイントがないサービスは `list_releases(limit=1)` で代替
- **command層**: `commands/release.py` の `view` サブコマンドに `--latest` フラグを追加

---

## Raw API call (#22)

任意の API エンドポイントを呼び出す。未サポート操作のエスケープハッチ。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ |

### 実装方針

gfo の既存 HTTP クライアント（`http.py`）と認証情報を流用して任意のエンドポイントを呼び出すコマンドを追加。**全サービスで実装可能**（API の有無に依存しないため）。

### 実装詳細

- **adapter層**: アダプター層は経由しない。`http.py` の `HttpClient` を直接利用
- **command層**: `commands/api.py` を新規作成。`gfo api GET /repos/{owner}/{repo}` の形式。`--method`, `--data`, `--header`, `--jq`（JSONフィルタ）オプション

---

## Repo update (#12)

リポジトリ設定変更（description, private, default_branch 等）。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | ○ | ○ | ○ | ○ | △ | × | △ |

### APIエンドポイント

- **GitHub**: `PATCH /repos/{owner}/{repo}`（description, private, default_branch 等）
- **GitLab**: `PUT /projects/:id`（description, visibility, default_branch 等）
- **Bitbucket**: `PUT /repositories/{workspace}/{repo}`（description, is_private 等）
- **Azure DevOps**: `PATCH /git/repositories/{repositoryId}`（名前、デフォルトブランチ）
- **Gitea/Forgejo**: `PATCH /repos/{owner}/{repo}`
- **Gogs**: `PATCH /repos/{owner}/{repo}` は存在するが変更可能フィールドが限定的
- **GitBucket**: リポジトリ設定変更 API なし
- **Backlog**: プロジェクト単位の設定変更のみ。リポジトリ個別の設定変更 API なし

### 実装詳細

- **adapter層**: `BaseAdapter` に `update_repository(description=None, private=None, default_branch=None, ...)` を追加
- **command層**: `commands/repo.py` に `update` サブコマンドを追加。`--description`, `--private`, `--default-branch` 等のオプション

---

## Repo archive (#13)

リポジトリをアーカイブする。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | × | ○ | ○ | ○ | × | × | △ |

### APIエンドポイント

- **GitHub**: `PATCH /repos/{owner}/{repo}` に `{"archived":true}`
- **GitLab**: `POST /projects/:id/archive`（専用エンドポイント）
- **Bitbucket**: アーカイブ API なし
- **Azure DevOps**: `PATCH /git/repositories/{repositoryId}` に `{"isDisabled":true}`
- **Gitea/Forgejo**: `PATCH /repos/{owner}/{repo}` に `{"archived":true}`
- **Backlog**: プロジェクト単位で `archived: true` のみ

### 実装詳細

- **adapter層**: `BaseAdapter` に `archive_repository()` を追加。GitLab は専用エンドポイント、他は update API で `archived: true` を設定
- **command層**: `commands/repo.py` に `archive` サブコマンドを追加。確認プロンプト付き（不可逆操作のため）

---

## Repo compare (#35)

ブランチ/コミット間の比較情報を取得する。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | ○ | ○ | ○ | ○ | × | × | × |

### APIエンドポイント

- **GitHub**: `GET /repos/{owner}/{repo}/compare/{basehead}`
- **GitLab**: `GET /projects/:id/repository/compare?from=X&to=Y`
- **Bitbucket**: `GET /repositories/{workspace}/{repo}/diff/{spec}` + `GET .../diffstat/{spec}`
- **Azure DevOps**: `GET /git/repositories/{repo}/diffs/commits?baseVersion=X&targetVersion=Y`
- **Gitea/Forgejo**: `GET /repos/{owner}/{repo}/compare/{basehead}`

### 実装詳細

- **adapter層**: `BaseAdapter` に `compare(base, head)` を追加。コミット差分・変更ファイル一覧を含むレスポンスを返す
- **command層**: `commands/repo.py` に `compare` サブコマンドを追加。`gfo repo compare main...feature` の形式

---

## Repo topics (#34)

リポジトリのトピック/タグを管理する。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | △ | × | × | ○ | ○ | × | × | × |

### APIエンドポイント

- **GitHub**: `GET/PUT /repos/{owner}/{repo}/topics`（PUT で全件置換）
- **GitLab**: `PUT /projects/:id` の `topics` パラメータで設定
- **Gitea/Forgejo**: `GET/PUT /repos/{owner}/{repo}/topics`, `PUT/DELETE .../topics/{topic}`（個別追加/削除も可能）

### 実装詳細

- **adapter層**: `BaseAdapter` に `list_topics()` / `set_topics(topics)` / `add_topic(topic)` / `remove_topic(topic)` を追加
- **command層**: `commands/repo.py` に `topics list/add/remove/set` サブコマンドグループを追加

---

## Repo languages (#36)

リポジトリの言語統計を取得する。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | × | × | ○ | ○ | × | × | × |

### APIエンドポイント

- **GitHub**: `GET /repos/{owner}/{repo}/languages`
- **GitLab**: `GET /projects/:id/languages`
- **Gitea/Forgejo**: `GET /repos/{owner}/{repo}/languages`

### 実装詳細

- **adapter層**: `BaseAdapter` に `get_languages()` を追加。言語名→バイト数（またはパーセンテージ）の辞書を返す
- **command層**: `commands/repo.py` に `languages` サブコマンドを追加。または `repo view` の表示情報に言語統計を含める
