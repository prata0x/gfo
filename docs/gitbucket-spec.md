# GitBucket 仕様メモ

gfo における GitBucket アダプターの実装に関する仕様・挙動・注意事項をまとめる。

---

## 1. 基本情報

| 項目 | 値 |
|---|---|
| API バージョン | GitHub API v3 互換（`/api/v3` プレフィックス） |
| ベース URL | `http://{host}:{port}/api/v3`（デフォルト: `http://localhost:3003/api/v3`） |
| 認証方式 | Bearer Token（`Authorization: token {token}` ヘッダー） |
| gfo 識別子 | `gitbucket` |
| 環境変数 | `GITBUCKET_TOKEN` |

---

## 2. 継承関係

`GitBucketAdapter` は `GitHubAdapter` を継承し、GitBucket 固有の非互換を補正するオーバーライドのみを定義する。

```
GitServiceAdapter (ABC)
└── GitHubLikeAdapter (Mixin)
    └── GitHubAdapter
        └── GitBucketAdapter   ← src/gfo/adapter/gitbucket.py
```

`GitHubLikeAdapter` が提供する `_to_*` 変換ヘルパー（`_to_pull_request`, `_to_issue`, `_to_repository`, `_to_release`, `_to_label`, `_to_milestone`）はそのまま継承する。ただし `_to_release` のみ GitBucket 固有フィールド欠落対応のためオーバーライドする。

### オーバーライドされたメソッド一覧

| メソッド | オーバーライド理由 |
|---|---|
| `create_pull_request()` | レスポンスが JSON 二重エンコード文字列のため `_parse_response()` を挟む |
| `close_issue()` | `PATCH /issues/{number}` 未実装のため Web UI エンドポイント経由に変更 |
| `_to_release()` | `created_at` / `html_url` フィールドが省略されるためフォールバック対応 |
| `create_release()` | レスポンスが JSON 二重エンコード文字列のため `_parse_response()` を挟む |
| `list_deploy_keys()` | deploy key API 未実装のため `NotSupportedError` を送出 |
| `create_deploy_key()` | 同上 |
| `delete_deploy_key()` | 同上 |

### GitBucket 固有ヘルパーメソッド

| メソッド | 役割 |
|---|---|
| `_parse_response(resp)` | `resp.json()` が `str` の場合に再度 `json.loads()` して `dict` を返す |
| `_web_base_url()` | `_client.base_url`（API URL）からポート番号を保持しつつ Web UI のベース URL を導出する |

---

## 3. 認証

### 形式

GitBucket は `Authorization: token {token}` ヘッダーで認証する（GitHub API v3 互換）。

```
Authorization: token <40桁の16進数文字列>
```

`registry.py` の `create_http_client()` が `auth_header={"Authorization": f"token {token}"}` として `HttpClient` に渡す。

### credentials.toml への格納

```toml
[tokens]
"localhost:3003" = "abcdef0123456789abcdef0123456789abcdef01"
```

ホスト名は `lower()` で正規化される（`auth.py`）。カスタムポートを使用する場合はホスト部分を `hostname:port` 形式で記述する。

### トークン発行

GitBucket は `POST /api/v3/authorizations` を実装していないため、Personal Access Token は **Web UI** 経由で取得する。

1. `http://{host}:{port}/signin` にログインする（デフォルト管理者: `root` / `root`）
2. `POST http://{host}:{port}/root/_personalToken` に `data={"note": "任意のメモ"}` を送信する
3. リダイレクト後に `http://{host}:{port}/root/_application` ページを GET する
4. HTML 内の `id="generated-token"` 属性を持つ input 要素から `value` を取得する（40桁の16進数）

`setup_services.py` の `setup_gitbucket()` 関数がこの手順を自動化している。

---

## 5. API エンドポイント

パス変数 `{owner}` / `{repo}` は URL エンコード済みの値を使用する（`_repos_path()` が `urllib.parse.quote` を適用）。

### Pull Request

| 操作 | メソッド | エンドポイント |
|---|---|---|
| PR 一覧 | `GET` | `/api/v3/repos/{owner}/{repo}/pulls` |
| PR 作成 | `POST` | `/api/v3/repos/{owner}/{repo}/pulls` |
| PR 取得 | `GET` | `/api/v3/repos/{owner}/{repo}/pulls/{number}` |
| PR マージ | `PUT` | `/api/v3/repos/{owner}/{repo}/pulls/{number}/merge` |
| PR クローズ | `PATCH` | `/api/v3/repos/{owner}/{repo}/pulls/{number}` |

### Issue

| 操作 | メソッド | エンドポイント |
|---|---|---|
| Issue 一覧 | `GET` | `/api/v3/repos/{owner}/{repo}/issues` |
| Issue 作成 | `POST` | `/api/v3/repos/{owner}/{repo}/issues` |
| Issue 取得 | `GET` | `/api/v3/repos/{owner}/{repo}/issues/{number}` |
| Issue クローズ | Web UI | `POST /{owner}/{repo}/issue_comments/state`（API 未実装） |

### Repository

| 操作 | メソッド | エンドポイント |
|---|---|---|
| リポジトリ一覧（自分） | `GET` | `/api/v3/user/repos` |
| リポジトリ一覧（ユーザー指定） | `GET` | `/api/v3/users/{owner}/repos` |
| リポジトリ作成 | `POST` | `/api/v3/user/repos` |
| リポジトリ取得 | `GET` | `/api/v3/repos/{owner}/{repo}` |

### Release

| 操作 | メソッド | エンドポイント |
|---|---|---|
| リリース一覧 | `GET` | `/api/v3/repos/{owner}/{repo}/releases` |
| リリース作成 | `POST` | `/api/v3/repos/{owner}/{repo}/releases` |
| リリース削除 | `GET` + `DELETE` | `/api/v3/repos/{owner}/{repo}/releases/tags/{tag}` → `/api/v3/repos/{owner}/{repo}/releases/{id}` |

### Label

| 操作 | メソッド | エンドポイント |
|---|---|---|
| ラベル一覧 | `GET` | `/api/v3/repos/{owner}/{repo}/labels` |
| ラベル作成 | `POST` | `/api/v3/repos/{owner}/{repo}/labels` |
| ラベル削除 | `DELETE` | `/api/v3/repos/{owner}/{repo}/labels/{name}` |

### Milestone

| 操作 | メソッド | エンドポイント |
|---|---|---|
| マイルストーン一覧 | `GET` | `/api/v3/repos/{owner}/{repo}/milestones` |
| マイルストーン作成 | `POST` | `/api/v3/repos/{owner}/{repo}/milestones` |
| マイルストーン削除 | `DELETE` | `/api/v3/repos/{owner}/{repo}/milestones/{number}` |

---

## 6. 状態マッピング

GitBucket は GitHub API v3 互換のため、状態マッピングは GitHub と同一（`github-spec.md §6` を参照）。

PR の `state` は `open` / `closed` の 2 値。マージ済みかどうかは `merged_at` フィールドの有無で判定する。

---

## 7. 機能別仕様

GitBucket は GitHub API v3 互換のため、基本的な機能仕様は GitHub と同一（`github-spec.md §7` を参照）。

GitBucket 固有の非互換点・特殊対応は §8 を参照。

---

## 8. 固有仕様

### PR create / Release create: JSON 二重エンコード

`POST /pulls` および `POST /releases` のレスポンスボディが `dict` ではなく **JSON 文字列（文字列として JSON が埋め込まれた形式）** で返ってくる場合がある。

```python
# GitBucket が返すレスポンス例（Content-Type: application/json）
"{\\"number\\":1,\\"title\\":\\"...\\",...}"
# resp.json() の戻り値が str になる
```

`_parse_response(resp)` メソッドがこれを吸収する:

```python
def _parse_response(self, resp) -> dict:
    data = resp.json()
    if isinstance(data, str):
        data = json.loads(data)
    if not isinstance(data, dict):
        raise GfoError(f"GitBucket: unexpected response type: {type(data)}")
    return data
```

`create_pull_request()` と `create_release()` は `resp.json()` の代わりに `self._parse_response(resp)` を使用する。`list_*` / `get_*` 系メソッドは GitHub から継承したまま（二重エンコードは create 系のみで発生）。

### Issue close: PATCH /issues/{number} 未実装

GitHub API では Issue クローズに `PATCH /repos/{owner}/{repo}/issues/{number}` を使用するが、GitBucket はこのエンドポイントを実装していない。

代替として **Web UI エンドポイント** `POST /{owner}/{repo}/issue_comments/state` を使用する。

#### close_issue() の実装フロー

```python
def close_issue(self, number: int) -> None:
    web_url = self._web_base_url()  # API URL から Web UI ベース URL を導出
    session = requests.Session()

    # 1. Web UI にログイン
    session.post(
        f"{web_url}/signin",
        data={"userName": "root", "password": "root"},
        allow_redirects=True,
        timeout=10,
    )

    # 2. issue_comments/state エンドポイントで Issue をクローズ
    session.post(
        f"{web_url}/{self._owner}/{self._repo}/issue_comments/state",
        data={"issueId": str(number), "action": "close"},
        allow_redirects=False,
        timeout=10,
    )
```

- ログインは GitBucket のデフォルト管理者 `root` / `root` を使用する（統合テスト環境前提）
- `_web_base_url()` は `_client.base_url`（例: `http://localhost:3003/api/v3`）をパースし、ポート番号を保持した Web UI URL（例: `http://localhost:3003`）を返す
- ポート 80 / 443 は省略する

#### _web_base_url() の実装

```python
def _web_base_url(self) -> str:
    parsed = urllib.parse.urlparse(self._client.base_url)
    port_str = f":{parsed.port}" if parsed.port and parsed.port not in (80, 443) else ""
    return f"{parsed.scheme}://{parsed.hostname}{port_str}"
```

### Release: created_at / html_url フィールドの欠落

GitBucket のリリースレスポンスには `created_at` と `html_url` フィールドが省略される場合がある。`GitHubLikeAdapter._to_release()` は `created_at` を必須フィールドとして参照するため、`GitBucketAdapter._to_release()` でオーバーライドし `.get()` によるフォールバックを適用する。

```python
@staticmethod
def _to_release(data: dict) -> Release:
    return Release(
        tag=data["tag_name"],
        title=data.get("name") or "",
        body=data.get("body"),
        draft=data.get("draft", False),
        prerelease=data.get("prerelease", False),
        url=data.get("html_url") or "",       # html_url がない場合は空文字列
        created_at=data.get("created_at") or "",  # created_at がない場合は空文字列
    )
```

### ブランチ作成: POST /git/refs 未サポート

GitBucket は `POST /api/v3/repos/{owner}/{repo}/git/refs` が正常に動作しない（HTTP 500 を返す）。

統合テストのブランチ作成には **git clone + push** 方式を使用する:

```bash
git clone http://root:root@localhost:3003/git/{owner}/{repo}.git /tmp/repo
git -C /tmp/repo checkout -b gfo-test-branch
# ファイルを追加してコミット
git -C /tmp/repo push origin gfo-test-branch
```

`setup_services.py` の `setup_gitbucket()` がこの手順を自動化している。

---

## 9. ページネーション

GitBucket は GitHub 互換の **RFC 5988 `Link` ヘッダー** 方式のページネーションをサポートする。

```
Link: <http://localhost:3003/api/v3/repos/root/test/issues?page=2>; rel="next",
      <http://localhost:3003/api/v3/repos/root/test/issues?page=5>; rel="last"
```

`http.py` の `paginate_link_header()` を使用する（GitHub と同じ関数）。

- `next` の URL が別オリジンを指す場合はページネーションを中断する（SSRF 防止）
- `per_page` クエリパラメータに件数を指定する
- `limit` が 0 の場合は全件取得する

---

## 10. URL パターン

### API URL

```
http://{host}:{port}/api/v3
```

統合テストのデフォルト: `http://localhost:3003/api/v3`

### Git clone URL

```
http://{user}:{password}@{host}:{port}/git/{owner}/{repo}.git
```

### Web UI URL

```
http://{host}:{port}
```

### デフォルトブランチ

GitBucket のデフォルトブランチは `master`（GitHub や Gitea の `main` とは異なる）。

統合テストでは環境変数 `GFO_TEST_GITBUCKET_DEFAULT_BRANCH=master` を設定することで明示する。`setup_gitbucket()` はリポジトリ作成後に `GET /api/v3/repos/{owner}/{repo}` で `default_branch` を確認し `.env` に書き出す。

---

## 11. 非対応機能

以下の操作は GitBucket API の制約により `NotSupportedError` を返す。

| メソッド | 理由 |
|---|---|
| `list_deploy_keys()` | `/api/v3/repos/{owner}/{repo}/keys` エンドポイントが未実装（HTTP 500 を返す） |
| `create_deploy_key()` | 同上 |
| `delete_deploy_key()` | 同上 |

---

## 12. 統合テスト

### 環境変数

`tests/integration/.env` に設定する。`setup_services.py` 実行時に自動追記される。

| 変数名 | 内容 | 例 |
|---|---|---|
| `GFO_TEST_GITBUCKET_TOKEN` | Personal Access Token（40桁の16進数） | `abcdef01...` |
| `GFO_TEST_GITBUCKET_HOST` | ホスト名（ポート含む） | `localhost:3003` |
| `GFO_TEST_GITBUCKET_OWNER` | リポジトリオーナー | `root` |
| `GFO_TEST_GITBUCKET_REPO` | テスト用リポジトリ名 | `gfo-integration-test` |
| `GFO_TEST_GITBUCKET_DEFAULT_BRANCH` | デフォルトブランチ名 | `master` |

### サービス固有の注意事項

#### Docker Compose ポート

| コンテナ名 | イメージ | ホストポート | コンテナポート | 用途 |
|---|---|---|---|---|
| `gfo-gitbucket` | `gitbucket/gitbucket:latest` | `3003` | `8080` | HTTP API / Web UI |
| `gfo-gitbucket` | `gitbucket/gitbucket:latest` | `2225` | `29418` | SSH（Gerrit 互換） |

ヘルスチェック: `curl -sf -o /dev/null http://localhost:8080/`

#### テスト実行方法

```bash
# ワンショット実行
bash tests/integration/run_selfhosted.sh

# 個別実行
docker compose -f tests/integration/docker-compose.yml up -d
python tests/integration/setup_services.py
pytest tests/integration/test_gitbucket.py -v -m "integration and selfhosted"
```

#### テストマーク

```python
pytestmark = [
    pytest.mark.integration,
    pytest.mark.selfhosted,
    pytest.mark.skipif(CONFIG is None, reason="GitBucket credentials not configured"),
]
```

`GFO_TEST_GITBUCKET_TOKEN` / `GFO_TEST_GITBUCKET_OWNER` / `GFO_TEST_GITBUCKET_REPO` のいずれかが未設定の場合はテストをスキップする。
