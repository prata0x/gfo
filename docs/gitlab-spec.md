# GitLab 仕様メモ

gfo における GitLab アダプターの実装に関する仕様・挙動・注意事項をまとめる。

---

## 1. 基本情報

| 項目 | 値 |
|---|---|
| API バージョン | REST API v4 |
| ベース URL | `https://gitlab.com/api/v4`（SaaS）/ `https://{host}/api/v4`（セルフホスト） |
| 認証方式 | `Private-Token` ヘッダー |
| gfo 識別子 | `gitlab` |
| 環境変数 | `GITLAB_TOKEN` |

---

## 3. 認証

### 形式

Personal Access Token を `Private-Token` ヘッダーで送信する。

```
Private-Token: <your-token>
```

`registry.py` の `create_http_client` で `HttpClient` に `auth_header={"Private-Token": token}` として渡す。

### credentials.toml への格納

```toml
[tokens]
"gitlab.com" = "glpat-xxxxxxxxxxxxxxxxxxxx"
```

セルフホストの場合はホスト名をキーにする。

```toml
[tokens]
"gitlab.example.com" = "glpat-xxxxxxxxxxxxxxxxxxxx"
```

ホスト名はすべて小文字（`lower()`）で正規化される（`auth.py`）。

### トークン発行

https://gitlab.com/-/user_settings/personal_access_tokens

セルフホスト: `https://{host}/-/user_settings/personal_access_tokens`

---

## 4. スコープ

### スコープ一覧

GitLab Personal Access Token で選択可能な全スコープ。

| スコープ | 説明 |
|---|---|
| `api` | API への完全な読み書きアクセス（全グループ・プロジェクト・コンテナレジストリ・Git 操作を含む） |
| `read_api` | API への読み取り専用アクセス（全グループ・プロジェクト・コンテナレジストリを含む） |
| `read_registry` | プライベートプロジェクトのコンテナレジストリイメージのプル |
| `write_registry` | プライベートプロジェクトのコンテナレジストリイメージのプッシュ |
| `read_virtual_registry` | Dependency Proxy 経由でのコンテナイメージの読み取り（プル） |
| `write_virtual_registry` | Dependency Proxy 経由でのコンテナイメージのプル・プッシュ・削除 |
| `read_repository` | プライベートプロジェクトのリポジトリへの Git-over-HTTP による読み取り（プル） |
| `write_repository` | Git 操作によるリポジトリへの読み書き（プル・プッシュ）。API は対象外 |
| `create_runner` | ランナーの作成 |
| `manage_runner` | ランナーの管理 |
| `admin_mode` | Admin Mode が有効な場合に API アクションを実行する権限 |
| `ai_features` | GitLab Duo・コード提案 API・チャット API へのアクセス |
| `k8s_proxy` | Kubernetes API コールの実行 |
| `self_rotate` | Personal Access Token API 経由でこのトークン自身をローテーションする権限 |
| `read_service_ping` | Service Ping ペイロードのダウンロード |
| `sudo` | システム内の任意のユーザーとして API アクションを実行する権限（管理者専用） |
| `read_user` | 認証済みユーザーのプロフィールへの読み取り専用アクセス |

### gfo で必要なスコープ

| gfo コマンド | 必要スコープ |
|---|---|
| `repo list` / `repo view` | `read_api` |
| `repo create` | `api` |
| `pr list` / `pr view` | `read_api` |
| `pr create` / `pr merge` / `pr close` | `api` |
| `pr checkout` | `read_api`（refspec 取得） + `read_repository`（git fetch） |
| `issue list` / `issue view` | `read_api` |
| `issue create` / `issue close` | `api` |
| `release list` | `read_api` |
| `release create` / `release delete` | `api` |
| `label list` | `read_api` |
| `label create` / `label delete` | `api` |
| `milestone list` | `read_api` |
| `milestone create` / `milestone delete` | `api` |

> 最小権限での運用: 読み取りのみであれば `read_api` のみで十分。書き込みを含む場合は `api` が必要。

---

## 5. API エンドポイント

### MR (Merge Request)

| 操作 | メソッド | エンドポイント |
|---|---|---|
| MR 一覧 | `GET` | `/projects/{id}/merge_requests` |
| MR 作成 | `POST` | `/projects/{id}/merge_requests` |
| MR 取得 | `GET` | `/projects/{id}/merge_requests/{iid}` |
| MR マージ | `PUT` | `/projects/{id}/merge_requests/{iid}/merge` |
| MR rebase | `PUT` | `/projects/{id}/merge_requests/{iid}/rebase` |
| MR クローズ | `PUT` | `/projects/{id}/merge_requests/{iid}` |

### Issue

| 操作 | メソッド | エンドポイント |
|---|---|---|
| Issue 一覧 | `GET` | `/projects/{id}/issues` |
| Issue 作成 | `POST` | `/projects/{id}/issues` |
| Issue 取得 | `GET` | `/projects/{id}/issues/{iid}` |
| Issue クローズ | `PUT` | `/projects/{id}/issues/{iid}` |

### Repository

| 操作 | メソッド | エンドポイント |
|---|---|---|
| リポジトリ一覧（自分） | `GET` | `/projects?owned=true&membership=true` |
| リポジトリ一覧（ユーザー指定） | `GET` | `/users/{username}/projects` |
| リポジトリ作成 | `POST` | `/projects` |
| リポジトリ取得 | `GET` | `/projects/{id}` |

### Release

| 操作 | メソッド | エンドポイント |
|---|---|---|
| Release 一覧 | `GET` | `/projects/{id}/releases` |
| Release 作成 | `POST` | `/projects/{id}/releases` |
| Release 削除 | `DELETE` | `/projects/{id}/releases/{tag_name}` |

### Label

| 操作 | メソッド | エンドポイント |
|---|---|---|
| Label 一覧 | `GET` | `/projects/{id}/labels` |
| Label 作成 | `POST` | `/projects/{id}/labels` |
| Label 削除 | `DELETE` | `/projects/{id}/labels/{name}` |

### Milestone

| 操作 | メソッド | エンドポイント |
|---|---|---|
| Milestone 一覧 | `GET` | `/projects/{id}/milestones` |
| Milestone 作成 | `POST` | `/projects/{id}/milestones` |
| Milestone 削除 | `DELETE` | `/projects/{id}/milestones/{id}` |

> Milestone 削除の `{id}` はグローバル id（`iid` ではない）。詳細は §7 機能別仕様を参照。

---

## 6. 状態マッピング

### PR 状態

GitLab の MR 状態と gfo の正規化値のマッピング。

| GitLab API | gfo |
|---|---|
| `opened` | `open` |
| `closed` | `closed` |
| `merged` | `merged` |
| `locked` | `closed` |

`pr list --state` → API `state` パラメータのマッピング:

| gfo `--state` | GitLab API `state` |
|---|---|
| `open` | `opened` |
| `closed` | `closed`（そのまま） |
| `merged` | `merged`（そのまま） |
| `all` | パラメータなし |

### Issue 状態

| GitLab API | gfo |
|---|---|
| `opened` | `open` |
| `closed` | `closed`（そのまま） |

`issue list --state` → API `state` パラメータのマッピング:

| gfo `--state` | GitLab API `state` |
|---|---|
| `open` | `opened` |
| `closed` | `closed`（そのまま） |
| `all` | パラメータなし |

### Milestone 状態

| GitLab API | gfo |
|---|---|
| `active` | `open` |
| `closed` | `closed`（そのまま） |

---

## 7. 機能別仕様

### PR 仕様

#### MR と PR の対応

GitLab では Pull Request を「Merge Request（MR）」と呼ぶ。gfo は内部的に `PullRequest` データクラスで統一して扱い、`number` フィールドに MR の `iid`（プロジェクト内連番）を格納する。

#### フィールドマッピング

| gfo `PullRequest` フィールド | GitLab API フィールド |
|---|---|
| `number` | `iid`（プロジェクト内連番） |
| `title` | `title` |
| `body` | `description` |
| `state` | `state`（正規化後） |
| `author` | `author.username` |
| `source_branch` | `source_branch` |
| `target_branch` | `target_branch` |
| `draft` | `draft` |
| `url` | `web_url` |
| `created_at` | `created_at` |
| `updated_at` | `updated_at` |

#### checkout の refspec

GitLab は MR の fetch refspec として `refs/merge-requests/{iid}/head` を提供する。

```python
def get_pr_checkout_refspec(self, number: int, *, pr: PullRequest | None = None) -> str:
    return f"refs/merge-requests/{number}/head"
```

PR オブジェクトは不要（`number` のみで確定できる）。

#### マージ方法

`merge_pull_request` の `method` 引数に対応するエンドポイントと挙動:

| gfo `--method` | GitLab 動作 | エンドポイント |
|---|---|---|
| `merge` | 通常マージコミット（デフォルト） | `PUT /merge_requests/{iid}/merge` |
| `squash` | スカッシュマージ | `PUT /merge_requests/{iid}/merge`（`squash: true`） |
| `rebase` | リベース | `PUT /merge_requests/{iid}/rebase`（専用エンドポイント） |

`rebase` は `/merge` ではなく `/rebase` という別エンドポイントを使用する点に注意。

#### MR クローズ

`PUT /projects/{id}/merge_requests/{iid}` に `{"state_event": "close"}` を送信する。

### Issue 仕様

#### フィールドマッピング

| gfo `Issue` フィールド | GitLab API フィールド |
|---|---|
| `number` | `iid`（プロジェクト内連番） |
| `title` | `title` |
| `body` | `description` |
| `state` | `state`（正規化後） |
| `author` | `author.username` |
| `assignees` | `assignees[].username` の配列 |
| `labels` | `labels`（文字列配列） |
| `url` | `web_url` |
| `created_at` | `created_at` |
| `updated_at` | `updated_at` |

#### Issue 一覧のフィルタリング

GitLab の `/projects/{id}/issues` は Issue のみを返す（MR は含まれない）。
他サービス（Gitea 等）で必要な `pull_request` フィールドによる MR 除外フィルタは **不要**。

#### フィルタクエリパラメータ

| gfo 引数 | GitLab API パラメータ |
|---|---|
| `--assignee {username}` | `assignee_username={username}` |
| `--label {label}` | `labels={label}` |

複数ラベルはカンマ区切りで指定可能（`labels=bug,enhancement`）。

#### Issue クローズ

`PUT /projects/{id}/issues/{iid}` に `{"state_event": "close"}` を送信する。

#### Issue 作成時のアサイン

`assignee_username` フィールドでユーザー名を直接指定できる（`assignee_id` は不要）。

### Release 仕様

#### フィールドマッピング

| gfo `Release` フィールド | GitLab API フィールド |
|---|---|
| `tag` | `tag_name` |
| `title` | `name` |
| `body` | `description` |
| `draft` | 常に `False`（GitLab は draft release をサポートしない） |
| `prerelease` | `upcoming_release` |
| `url` | `_links.self` または `web_url` |
| `created_at` | `created_at` |

#### Release 作成時の注意

GitLab はタグが存在しない場合、`ref` フィールド（ブランチ名など）が必要。
gfo は `get_repository()` でデフォルトブランチを取得して `ref` に設定する。

```python
repo = self.get_repository()
payload["ref"] = repo.default_branch or "main"
```

`upcoming_release: True` を指定すると「予定リリース（Upcoming Release）」扱いになる。

#### Release 削除

`DELETE /projects/{id}/releases/{tag_name}` でタグ名を URL エンコードして送信する。

### Label 仕様

#### フィールドマッピング

| gfo `Label` フィールド | GitLab API フィールド |
|---|---|
| `name` | `name` |
| `color` | `color`（先頭 `#` を除去した 6 桁 hex） |
| `description` | `description` |

#### カラーコードの扱い

GitLab API はカラーコードを `#RRGGBB` 形式で返す。gfo は先頭の `#` を除去して `RRGGBB` 形式で格納する。

```python
color = data.get("color")
if color and color.startswith("#"):
    color = color[1:]
```

Label 作成時は逆変換が必要で `#` を付けて送信する:

```python
payload["color"] = f"#{color.lstrip('#')}"
```

Label 削除は `DELETE /projects/{id}/labels/{name}` でラベル名を URL エンコードして送信する。

### Milestone 仕様

#### iid とグローバル id の違い

GitLab の Milestone には 2 種類の ID が存在する:

| フィールド | 説明 |
|---|---|
| `iid` | プロジェクト内の連番（1, 2, 3, ...）。URL や UI で使われる値 |
| `id` | GitLab インスタンス全体でのグローバル ID |

gfo の `Milestone.number` には `iid` を格納する（ユーザーが認識する番号と一致させるため）。

#### Milestone 削除時の id 解決

`DELETE /projects/{id}/milestones/{milestone_id}` は **グローバル id** を要求する（`iid` は不可）。

gfo は `iid` でフィルタして一度リストを取得し、グローバル id を解決してから削除する:

```python
def delete_milestone(self, *, number: int) -> None:
    resp = self._client.get(f"{self._project_path()}/milestones", params={"iid[]": number})
    milestones = resp.json()
    if not milestones:
        raise NotFoundError(f"{self._project_path()}/milestones?iid[]={number}")
    global_id = milestones[0]["id"]
    self._client.delete(f"{self._project_path()}/milestones/{global_id}")
```

`?iid[]=` クエリパラメータで特定の iid に絞り込める。

#### フィールドマッピング

| gfo `Milestone` フィールド | GitLab API フィールド |
|---|---|
| `number` | `iid` |
| `title` | `title` |
| `description` | `description` |
| `state` | `state`（`active` → `open`、`closed` → `closed`） |
| `due_date` | `due_date` |

---

## 8. 固有仕様

### プロジェクト ID の扱い

GitLab API の `{id}` には数値 ID とパス（`owner/repo`）のどちらでも使用できる。
gfo は `owner%2Frepo` 形式の URL エンコードされたパスを使用する。

```python
from urllib.parse import quote

def _project_path(self) -> str:
    return f"/projects/{quote(self._owner + '/' + self._repo, safe='')}"
    # 例: /projects/myorg%2Fmyrepo
```

`urllib.parse.quote` で `safe=''` を指定することで `/` を `%2F` に変換する。

### サブグループ対応

GitLab はサブグループをサポートするため、`owner` 部分が `group/subgroup` になる場合がある。

```
owner = "mygroup/subgroup"
repo  = "myrepo"
→ /projects/mygroup%2Fsubgroup%2Fmyrepo
```

`quote(self._owner + '/' + self._repo, safe='')` の実装により、パス区切り文字もすべてエンコードされるためサブグループが自動的に扱われる。

---

## 9. ページネーション

GitLab は `X-Next-Page` レスポンスヘッダーでページネーションを制御する。
gfo では `paginate_page_param`（`http.py`）を使用する。

### 動作フロー

1. 初回リクエストに `page=1&per_page={n}` を付与
2. レスポンスの `X-Next-Page` ヘッダーを読み取る
3. 値が空文字または存在しない場合はページネーション終了
4. 値を次の `page` パラメータとして使用してリクエストを繰り返す

```
GET /projects/{id}/merge_requests?state=opened&page=1&per_page=20
→ X-Next-Page: 2

GET /projects/{id}/merge_requests?state=opened&page=2&per_page=20
→ X-Next-Page:   ← 空 = 最終ページ
```

### 関連ヘッダー

| ヘッダー | 説明 |
|---|---|
| `X-Next-Page` | 次ページ番号（空の場合は最終ページ） |
| `X-Page` | 現在のページ番号 |
| `X-Per-Page` | 1 ページあたりの件数 |
| `X-Total` | 全件数 |
| `X-Total-Pages` | 全ページ数 |

gfo は `X-Next-Page` のみを使用する（他ヘッダーは参照しない）。

`paginate_page_param` のデフォルト `per_page` は 20。GitLab API の最大値は 100。

---

## 10. URL パターン

### HTTPS

```
https://gitlab.com/{owner}/{repo}.git
https://{host}/{owner}/{repo}.git
```

サブグループを含む場合:

```
https://gitlab.com/{group}/{subgroup}/{repo}.git
```

### SSH (SCP 形式)

```
git@gitlab.com:{owner}/{repo}.git
```

### SSH (ssh:// 形式)

```
ssh://git@gitlab.com/{owner}/{repo}.git
```

### remote URL からの自動検出

`detect.py` の `_KNOWN_HOSTS` に `"gitlab.com": "gitlab"` が登録されている。
セルフホスト GitLab インスタンスは `probe_unknown_host` によって `/api/v4/version` エンドポイントへの HTTP 200 レスポンスで判定される。

---

## 11. 非対応機能

以下の操作は GitLab API の制約により `NotSupportedError` を返す。

| メソッド | 理由 |
|---|---|
| `update_comment` | GitLab の Notes API は更新時に issue/MR の `iid` が必要（`PUT /projects/{id}/issues/{iid}/notes/{note_id}`）だが、gfo の `update_comment` シグネチャは `comment_id` のみを受け取るため実装不可 |
| `delete_comment` | 同上（`DELETE /projects/{id}/issues/{iid}/notes/{note_id}`） |

> **補足**: gfo の `update_comment(resource, comment_id, *, body)` / `delete_comment(resource, comment_id)` シグネチャは issue/MR の番号を受け取らない設計のため、GitLab の Notes エンドポイントに必要なパスパラメータを組み立てられない。

---

## 12. 統合テスト

### 環境変数

SaaS（gitlab.com）を対象とした統合テストで使用する環境変数。
`tests/integration/.env` に設定する。

| 環境変数 | 説明 |
|---|---|
| `GFO_TEST_GITLAB_TOKEN` | Personal Access Token（`api` スコープ必須） |
| `GFO_TEST_GITLAB_OWNER` | テスト用リポジトリのオーナー（ユーザー名またはグループ名） |
| `GFO_TEST_GITLAB_REPO` | テスト用リポジトリ名 |
| `GFO_TEST_GITLAB_HOST` | セルフホストの場合のホスト名（省略時は `gitlab.com`） |
| `GFO_TEST_GITLAB_API_URL` | セルフホストの場合の API ベース URL（省略時は自動構築） |

### サービス固有の注意事項

- `GFO_TEST_GITLAB_OWNER` には GitLab のユーザー名またはグループ名を設定する
- サブグループ配下のリポジトリをテストする場合は `owner` を `group/subgroup` 形式で設定する
