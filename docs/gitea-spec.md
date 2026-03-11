# Gitea / Forgejo / Gogs 仕様メモ

gfo における Gitea・Forgejo・Gogs アダプターの実装に関する仕様・挙動・注意事項をまとめる。

---

## 1. 基本情報

| 項目 | Gitea | Forgejo | Gogs |
|---|---|---|---|
| API バージョン | REST API v1 | REST API v1（Gitea 互換） | REST API v1（Gitea 互換、一部未対応） |
| ベース URL | `http(s)://{host}/api/v1` | `http(s)://{host}/api/v1` | `http(s)://{host}/api/v1` |
| 認証方式 | `Authorization: token {token}` | `Authorization: token {token}` | `Authorization: token {token}` |
| gfo 識別子 | `gitea` | `forgejo` | `gogs` |
| 環境変数 | `GITEA_TOKEN` | `GITEA_TOKEN` | `GITEA_TOKEN` |

---

## 2. 継承関係

```
GiteaAdapter            (@register("gitea"))
├── ForgejoAdapter      (@register("forgejo"))  ← service_name のみオーバーライド
└── GogsAdapter         (@register("gogs"))     ← PR/Label/Milestone/Release を NotSupportedError でオーバーライド
```

### ForgejoAdapter（`adapter/forgejo.py`）

`GiteaAdapter` を完全継承し、`service_name = "Forgejo"` のみオーバーライドする。
API パス・認証・ページネーションはすべて Gitea と同一。

### GogsAdapter（`adapter/gogs.py`）

`GiteaAdapter` を継承するが、以下の操作を `NotSupportedError` でオーバーライドする。

- **PR 全操作**（`list_pull_requests` / `create_pull_request` / `get_pull_request` / `merge_pull_request` / `close_pull_request` / `get_pr_checkout_refspec`）
- **Label 全操作**（`list_labels` / `create_label` / `delete_label`）
- **Milestone 全操作**（`list_milestones` / `create_milestone` / `delete_milestone`）
- **Release 全操作**（`list_releases` / `create_release` / `delete_release`）

`NotSupportedError` に `web_url` を渡し、Web UI の代替 URL をユーザーに提示する。

---

## 3. 認証

### 形式

```
Authorization: token {ACCESS_TOKEN}
```

GitHub の `Bearer` 形式とは異なる点に注意。`registry.py` の `create_http_client` 内で設定される。

```python
# registry.py より
elif service_type in ("gitea", "forgejo", "gogs", "gitbucket"):
    return HttpClient(api_url, auth_header={"Authorization": f"token {token}"})
```

### credentials.toml への格納

```toml
[tokens]
"localhost:3000" = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
"codeberg.org"  = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

ホスト名はすべて小文字（`lower()`）で正規化される。

### トークン発行

| サービス | 発行場所 |
|---|---|
| Gitea | `Settings` → `Applications` → `Generate New Token` |
| Forgejo | `Settings` → `Applications` → `Generate New Token` |
| Gogs | `Your Settings` → `Applications` → `Generate New Token` |

API 経由での発行は `POST /users/{username}/tokens`（Basic Auth 必須）。

---

## 5. API エンドポイント

すべてのパスは `{base_url}/repos/{owner}/{repo}` を起点とする。
URL エンコードには `urllib.parse.quote(safe='')` を使用する。

### Pull Request

| 操作 | メソッド | パス |
|---|---|---|
| 一覧取得 | GET | `/repos/{owner}/{repo}/pulls` |
| 作成 | POST | `/repos/{owner}/{repo}/pulls` |
| 取得 | GET | `/repos/{owner}/{repo}/pulls/{number}` |
| マージ | POST | `/repos/{owner}/{repo}/pulls/{number}/merge` |
| クローズ | PATCH | `/repos/{owner}/{repo}/pulls/{number}` |

### Issue

| 操作 | メソッド | パス |
|---|---|---|
| 一覧取得 | GET | `/repos/{owner}/{repo}/issues` |
| 作成 | POST | `/repos/{owner}/{repo}/issues` |
| 取得 | GET | `/repos/{owner}/{repo}/issues/{number}` |
| クローズ | PATCH | `/repos/{owner}/{repo}/issues/{number}` |

### Repository

| 操作 | メソッド | パス |
|---|---|---|
| 一覧取得（自分） | GET | `/user/repos` |
| 一覧取得（指定ユーザー） | GET | `/users/{owner}/repos` |
| 作成 | POST | `/user/repos` |
| 取得 | GET | `/repos/{owner}/{repo}` |

### Release

| 操作 | メソッド | パス |
|---|---|---|
| 一覧取得 | GET | `/repos/{owner}/{repo}/releases` |
| 作成 | POST | `/repos/{owner}/{repo}/releases` |
| タグ → ID 解決 | GET | `/repos/{owner}/{repo}/releases/tags/{tag}` |
| 削除 | DELETE | `/repos/{owner}/{repo}/releases/{id}` |

### Label

| 操作 | メソッド | パス |
|---|---|---|
| 一覧取得 | GET | `/repos/{owner}/{repo}/labels` |
| 作成 | POST | `/repos/{owner}/{repo}/labels` |
| 名前 → ID 解決 | GET | `/repos/{owner}/{repo}/labels` |
| 削除 | DELETE | `/repos/{owner}/{repo}/labels/{id}` |

### Milestone

| 操作 | メソッド | パス |
|---|---|---|
| 一覧取得 | GET | `/repos/{owner}/{repo}/milestones` |
| 作成 | POST | `/repos/{owner}/{repo}/milestones` |
| 削除 | DELETE | `/repos/{owner}/{repo}/milestones/{number}` |

---

## 6. 状態マッピング

### PR 状態

gfo の `PullRequest.state` は `"open"` / `"closed"` / `"merged"` の 3 値を取る。

Gitea API の `state` フィールドは `"open"` / `"closed"` の 2 値。
マージ済みかどうかは `merged_at` フィールドの有無で判定する（GitHub と同仕様）。

```python
# base.py の _to_pull_request より
merged = data.get("merged_at") is not None
if data["state"] == "closed" and merged:
    state = "merged"
else:
    state = data["state"]
```

`state="merged"` で呼び出した場合、Gitea API には `merged` ステートが存在しないため、
`state="closed"` で API を叩き、返却された PR のうち `pr.state == "merged"` のものだけを返す。

```python
# gitea.py より
api_state = "closed" if state == "merged" else state
params = {"state": api_state}
results = paginate_link_header(...)
prs = [self._to_pull_request(r) for r in results]
if state == "merged":
    prs = [pr for pr in prs if pr.state == "merged"]
```

### Issue 状態

Gitea / Forgejo は `"open"` / `"closed"` の 2 値を返す。gfo はそのまま使用する。

---

## 7. 機能別仕様

### PR 仕様

#### マージ方法

Gitea の PR マージには `{"Do": method}` というリクエストボディを使用する。
GitHub の `merge_method` パラメータとは**フィールド名が異なる**点に注意。

```python
# gitea.py より
self._client.post(
    f"{self._repos_path()}/pulls/{number}/merge",
    json={"Do": method},
)
```

`method` には以下の文字列を指定できる（Gitea API 仕様）:

| 値 | 意味 |
|---|---|
| `merge` | マージコミットを作成（デフォルト） |
| `rebase` | リベースしてマージ |
| `rebase-merge` | リベース後にマージコミットを作成 |
| `squash` | スカッシュしてマージ |

### Issue 仕様

#### PR が Issue 一覧に混在する問題

Gitea / Forgejo では `GET /repos/{owner}/{repo}/issues` が Issue と PR の両方を返す場合がある。
`type=issues` クエリパラメータで絞り込むが、念のため `pull_request` フィールドでも除外フィルタを適用する。

```python
# gitea.py より
params: dict = {"state": state, "type": "issues"}
results = paginate_link_header(...)
return [self._to_issue(r) for r in results if not r.get("pull_request")]
```

レスポンス中の `pull_request` フィールドは、PR でない場合 `null` または省略される。
`not r.get("pull_request")` が `True` になるもの（`null` / 未存在 / `{}`）のみ Issue として扱う。

#### Issue / PR 共通フィールド（`_to_issue` で使用）

| API フィールド | gfo フィールド | 備考 |
|---|---|---|
| `number` | `number` | |
| `title` | `title` | |
| `body` | `body` | なければ `None` |
| `state` | `state` | `"open"` / `"closed"` |
| `user.login` | `author` | |
| `assignees[].login` | `assignees` | |
| `labels[].name` | `labels` | |
| `html_url` | `url` | なければ `""` |
| `created_at` | `created_at` | ISO 8601 |
| `updated_at` | `updated_at` | なければ `None` |

### Label 仕様

Gitea API の `DELETE /repos/{owner}/{repo}/labels/{id}` は **ID** を要求する。
gfo コマンドはラベル名で操作するため、名前 → ID の解決が必要。

```python
# gitea.py より
def delete_label(self, *, name: str) -> None:
    resp = self._client.get(f"{self._repos_path()}/labels")
    for label in resp.json():
        if label.get("name") == name:
            self._client.delete(f"{self._repos_path()}/labels/{label['id']}")
            return
    raise NotFoundError()
```

手順:
1. `GET /repos/{owner}/{repo}/labels` でラベル一覧を取得
2. `name` が一致するラベルの `id` を取得
3. `DELETE /repos/{owner}/{repo}/labels/{id}` で削除
4. 一致するラベルが存在しない場合は `NotFoundError` を送出

### Release 仕様

Gitea API の `DELETE /repos/{owner}/{repo}/releases/{id}` は **ID** を要求する。
gfo コマンドはタグ名で操作するため、タグ → ID の解決が必要。

```python
# gitea.py より
def delete_release(self, *, tag: str) -> None:
    resp = self._client.get(f"{self._repos_path()}/releases/tags/{quote(tag, safe='')}")
    release_id = resp.json()["id"]
    self._client.delete(f"{self._repos_path()}/releases/{release_id}")
```

手順:
1. `GET /repos/{owner}/{repo}/releases/tags/{tag}` でリリース情報を取得
2. レスポンスの `id` フィールドを取得
3. `DELETE /repos/{owner}/{repo}/releases/{id}` で削除

---

## 8. 固有仕様

### Milestone の `number` フィールド問題

Gitea 1.22 以降の一部バージョンでは、`GET /repos/{owner}/{repo}/milestones` のレスポンスに
`number` フィールドが含まれない場合がある。

`_to_milestone` ではフォールバックとして `id` を使用する。

```python
# base.py より
number=data.get("number") or data["id"],
```

`data.get("number")` が `None` または `0`（falsy）の場合に `data["id"]` を使用する。
Forgejo も同様の対応が必要。

### サービス自動検出

`detect.py` の `probe_unknown_host` 関数が `GET /api/v1/version` を試行し、
レスポンスの内容から Gitea / Forgejo / Gogs を識別する。

#### `/api/v1/version` レスポンスの違い

| サービス | レスポンス例 | 識別キー |
|---|---|---|
| Forgejo (>= 1.20) | `{"version": "...", "forgejo": "...", "go_version": "..."}` | `"forgejo"` キーの有無 |
| 旧版 Forgejo | `{"version": "...", "source_url": "...forgejo..."}` | `source_url` に `"forgejo"` を含む |
| Gitea | `{"version": "1.x.x", "go_version": "go1.x", ...}` | `"go_version"` または `"go-version"` キーの有無 |
| Gogs | `{"version": "0.x.x"}` | `"version"` のみ（`go_version` / `forgejo` なし） |

```python
# detect.py より（抜粋）
if "forgejo" in data:
    return "forgejo"
source_url = data.get("source_url", "")
if isinstance(source_url, str) and "forgejo" in source_url.lower():
    return "forgejo"
if "go-version" in data or "go_version" in data:
    return "gitea"
if "version" in data and "go-version" not in data and "go_version" not in data and "forgejo" not in data:
    return "gogs"
```

`codeberg.org` は `_KNOWN_HOSTS` に `"forgejo"` として登録済みのため、プローブなしで即時識別できる。

---

## 9. ページネーション

Gitea / Forgejo / Gogs は GitHub と同じ **Link ヘッダー** 方式を使用する。

```
Link: <https://host/api/v1/repos/owner/repo/pulls?limit=30&page=2>; rel="next",
      <https://host/api/v1/repos/owner/repo/pulls?limit=30&page=5>; rel="last"
```

`http.py` の `paginate_link_header` 関数を使用する（GitHub と共用）。

Gitea は `per_page` ではなく `limit` パラメータでページサイズを指定する。

```python
# gitea.py より
paginate_link_header(
    self._client,
    f"{self._repos_path()}/pulls",
    params=params,
    limit=limit,
    per_page_key="limit",  # GitHub は "per_page"、Gitea は "limit"
)
```

---

## 10. URL パターン

### HTTPS

```
https://gitea.example.com/{owner}/{repo}.git
https://codeberg.org/{owner}/{repo}.git
```

### SSH（SCP 形式）

```
git@gitea.example.com:{owner}/{repo}.git
```

### SSH（URL 形式）

```
ssh://git@gitea.example.com:22/{owner}/{repo}.git
```

URL パース後、`owner` と `repo` は `_GENERIC_PATH_RE`（`^(?P<owner>.+)/(?P<repo>[^/]+)$`）で抽出される。

---

## 11. 非対応機能

### Gogs の非対応機能

Gogs は GitHub 互換の API を持つが、以下の操作は API レベルで未実装または実用性が低い。
gfo では `NotSupportedError` を送出し、Web UI の代替 URL を提示する。

| 操作 | gfo の挙動 | Web UI の代替 URL |
|---|---|---|
| PR 一覧 | `NotSupportedError` | `{web_url}/{owner}/{repo}/pulls` |
| PR 作成 | `NotSupportedError` | `{web_url}/{owner}/{repo}/compare` |
| PR 取得 | `NotSupportedError` | `{web_url}/{owner}/{repo}/pulls/{number}` |
| PR マージ | `NotSupportedError` | `{web_url}/{owner}/{repo}/pulls/{number}` |
| PR クローズ | `NotSupportedError` | `{web_url}/{owner}/{repo}/pulls/{number}` |
| Label 全操作 | `NotSupportedError` | なし |
| Milestone 全操作 | `NotSupportedError` | なし |
| Release 全操作 | `NotSupportedError` | なし |

Issue の取得・作成・クローズは Gogs でも動作する（GiteaAdapter から継承）。

---

## 12. 統合テスト

### 環境変数

`tests/integration/.env` に設定する。セルフホストテストでは `setup_services.py` 実行時に自動追記される。

| 変数名 | 説明 | 例 |
|---|---|---|
| `GFO_TEST_GITEA_TOKEN` | Gitea アクセストークン | （`setup_services.py` が自動設定） |
| `GFO_TEST_GITEA_HOST` | Gitea ホスト（ポート含む） | `localhost:3000` |
| `GFO_TEST_GITEA_OWNER` | テスト用ユーザー名 | `gfo-admin` |
| `GFO_TEST_GITEA_REPO` | テスト用リポジトリ名 | `gfo-integration-test` |
| `GFO_TEST_FORGEJO_TOKEN` | Forgejo アクセストークン | （`setup_services.py` が自動設定） |
| `GFO_TEST_FORGEJO_HOST` | Forgejo ホスト（ポート含む） | `localhost:3001` |
| `GFO_TEST_FORGEJO_OWNER` | テスト用ユーザー名 | `gfo-admin` |
| `GFO_TEST_FORGEJO_REPO` | テスト用リポジトリ名 | `gfo-integration-test` |
| `GFO_TEST_GOGS_TOKEN` | Gogs アクセストークン | （`setup_services.py` が自動設定） |
| `GFO_TEST_GOGS_HOST` | Gogs ホスト（ポート含む） | `localhost:3002` |
| `GFO_TEST_GOGS_OWNER` | テスト用ユーザー名 | `gfo-admin` |
| `GFO_TEST_GOGS_REPO` | テスト用リポジトリ名 | `gfo-integration-test` |
| `GFO_TEST_{SERVICE}_DEFAULT_BRANCH` | デフォルトブランチ名 | `main`（Gogs は `master` の場合あり） |

### サービス固有の注意事項

#### Docker Compose ポート

| サービス | イメージ | HTTP ポート | SSH ポート |
|---|---|---|---|
| Gitea 1.22 | `gitea/gitea:1.22` | `3000` | `2222` |
| Forgejo 9 | `codeberg.org/forgejo/forgejo:9` | `3001` | `2223` |
| Gogs 0.13 | `gogs/gogs:0.13` | `3002` | `2224` |
| GitBucket (latest) | `gitbucket/gitbucket:latest` | `3003` | `2225` |

Forgejo イメージは公式レジストリ `codeberg.org/forgejo/forgejo` から取得する（Docker Hub は非公式）。

#### Gitea 1.22
- Milestone レスポンスに `number` フィールドがない → `id` でフォールバック（`_to_milestone`）
- Issue 一覧レスポンスに `pull_request: null` が含まれる → `not r.get("pull_request")` でフィルタ
- PR マージに `merge_method` ではなく `Do` パラメータを使用
- `docker exec` はコンテナ内ユーザーとして `-u git` を指定する必要がある

#### Forgejo 9
- Gitea と同じ非互換事項が適用される
- イメージは `codeberg.org/forgejo/forgejo:9` を使用（公式レジストリ指定必須）

#### Gogs 0.13
- PR / Label / Milestone / Release は API 未サポート → `NotSupportedError`
- リポジトリ作成時に `auto_init: True` に加えて `readme: "Default"` が必要
- `html_url` フィールドなし → `data.get("html_url") or ""` で空文字列にフォールバック
