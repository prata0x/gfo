# Backlog 仕様メモ

gfo における Backlog アダプターの実装に関する仕様・挙動・注意事項をまとめる。

---

## 1. 基本情報

| 項目 | 値 |
|---|---|
| API バージョン | REST API v2 |
| ベース URL | `https://{space}.backlog.com/api/v2` または `https://{space}.backlog.jp/api/v2` |
| 認証方式 | クエリパラメータ `apiKey` |
| gfo 識別子 | `backlog` |
| 環境変数 | `BACKLOG_API_KEY` |

---

## 3. 認証

### 形式

Backlog は全リクエストのクエリパラメータに `apiKey` を付与する方式を採用する。
他サービスが使用する `Authorization` ヘッダーは使用しない。

```
GET https://{space}.backlog.com/api/v2/projects/MYPROJECT?apiKey=abcdefghijklmn
```

`registry.py` の `create_http_client()` 内で `HttpClient(api_url, auth_params={"apiKey": token})` として渡される。
`HttpClient` はすべてのリクエストにクエリパラメータとして自動付与する。

エラーログ・デバッグ出力では `apiKey` の値が `***` にマスクされる（`HttpClient._mask_api_key()`）。

### credentials.toml への格納

```toml
[tokens]
"your-space.backlog.com" = "your-api-key"
```

ホスト名は `lower()` で正規化して格納・参照される（`auth.py`）。

### トークン発行

1. Backlog スペースにログインする
2. 個人設定（アカウント設定）→「API」タブを開く
3. メモ欄に任意の名前を入力し「登録」をクリックする
4. 生成された API キーをコピーする

参考: https://support-ja.backlog.com/hc/ja/articles/360035641534

---

## 5. API エンドポイント

すべてのパスは `https://{space}.backlog.{com|jp}/api/v2` からの相対パス。

### Pull Request

| 操作 | メソッド | パス |
|---|---|---|
| 一覧取得 | `GET` | `/projects/{projectKey}/git/repositories/{repoName}/pullRequests` |
| 作成 | `POST` | `/projects/{projectKey}/git/repositories/{repoName}/pullRequests` |
| 詳細取得 | `GET` | `/projects/{projectKey}/git/repositories/{repoName}/pullRequests/{number}` |
| クローズ | `PATCH` | `/projects/{projectKey}/git/repositories/{repoName}/pullRequests/{number}` |

リポジトリ名は `urllib.parse.quote(name, safe='')` で URL エンコードされる。

### Issue

| 操作 | メソッド | パス |
|---|---|---|
| 一覧取得 | `GET` | `/issues` |
| 作成 | `POST` | `/issues` |
| 詳細取得 | `GET` | `/issues/{projectKey}-{number}` |
| クローズ | `PATCH` | `/issues/{projectKey}-{number}` |

Issue の詳細・クローズは `{projectKey}-{number}` 形式（例: `MYPROJ-42`）のキーで指定する。

### Repository

| 操作 | メソッド | パス |
|---|---|---|
| 一覧取得 | `GET` | `/projects/{projectKey}/git/repositories` |
| 作成 | `POST` | `/projects/{projectKey}/git/repositories` |
| 詳細取得 | `GET` | `/projects/{projectKey}/git/repositories/{repoName}` |

### プロジェクト・補助

| 操作 | メソッド | パス | 用途 |
|---|---|---|---|
| プロジェクト情報取得 | `GET` | `/projects/{projectKey}` | `project.id` の取得（Issue 操作に必要） |
| プロジェクトステータス一覧 | `GET` | `/projects/{projectKey}/statuses` | Merged 相当の `statusId` を動的解決 |
| 課題種別一覧取得 | `GET` | `/projects/{projectKey}/issueTypes` | Issue 作成時の `issueTypeId` 自動取得 |
| 優先度一覧取得 | `GET` | `/priorities` | Issue 作成時の `priorityId` 自動取得 |

---

## 6. 状態マッピング

### Issue 状態

Backlog の Issue ステータスは以下の固定 ID を持つ。

| statusId | Backlog 標準ステータス名 | gfo での state |
|---|---|---|
| `1` | 未対応 | `open` |
| `2` | 処理中 | `open` |
| `3` | 処理済み | `open` |
| `4` | 完了 | `closed` |

`statusId == 4` のみ `state = "closed"` として扱い、それ以外はすべて `state = "open"` と判定する。

`issue list --state` → 送信する `statusId[]`:

| `state` 引数 | 送信する `statusId[]` |
|---|---|
| `"open"` | `[1, 2, 3]` |
| `"closed"` | `[4]` |
| `"all"` | 指定なし（全件取得） |

### PR 状態

PR の状態は `/projects/{projectKey}/statuses` エンドポイントから**動的に解決**する。
Backlog ではプロジェクトごとにカスタムステータスを設定できるため、"merged" に相当する `statusId` は固定されていない。

#### 動的解決ロジック（`_resolve_merged_status_id()`）

1. `GET /projects/{projectKey}/statuses` を呼び出す
2. ステータス名（`status["name"]`）に `"merged"` が含まれる（大文字小文字無視）エントリの `id` を使用する
3. 該当なしの場合は定数 `_STATUS_MERGED_ID = 5` をフォールバックとして使用する

`_resolve_merged_status_id()` の結果は `BacklogAdapter._merged_status_id` にキャッシュされ、同一インスタンス内で再利用される。

`pr list --state` → 送信する `statusId[]`:

| `state` 引数 | 送信する `statusId[]` |
|---|---|
| `"open"` | `[1, 2, 3]` |
| `"closed"` | `[4]` |
| `"merged"` | 動的解決した merged の `statusId` |
| `"all"` | 指定なし。ただし `_resolve_merged_status_id()` を呼び出して `merged_status_id` を確定する |

---

## 7. 機能別仕様

### Issue 仕様

#### Issue 作成の特殊処理

Backlog の `POST /issues` は `issueTypeId`（課題種別 ID）と `priorityId`（優先度 ID）が**必須パラメータ**。
他サービスでは省略可能なパラメータが多いのに対し、Backlog では未指定だとエラーになる。

**自動取得フロー**:

`create_issue()` の呼び出し時、`issue_type` または `priority` が `None` の場合は以下を実行する。

1. **issueTypeId の取得**
   - `GET /projects/{projectKey}/issueTypes` を呼び出す
   - レスポンス配列の先頭要素 `[0]["id"]` を使用する
   - 配列が空の場合は `GfoError` を送出する

2. **priorityId の取得**
   - `GET /priorities` を呼び出す
   - `name` に `"中"` を含む、または `"normal"` と一致するエントリを優先して選択する
   - 該当なしの場合は配列の先頭要素 `[0]["id"]` を使用する
   - 配列が空の場合は `GfoError` を送出する

**リクエストペイロード**:

```json
{
  "projectId": 12345,
  "summary": "Issue タイトル",
  "issueTypeId": 1,
  "priorityId": 3,
  "description": "本文（任意）",
  "assigneeUserId": "user01"
}
```

---

## 8. 固有仕様

### Project Key の扱い

Backlog のリポジトリは必ず特定プロジェクト配下に属する。
URL 構造が `git/{PROJECT_KEY}/{repo}` となっているため、`detect.py` の URL パース処理では `PROJECT_KEY` を `owner` として扱う。

```
https://myspace.backlog.com/git/MYPROJECT/myrepo.git
                                 ^^^^^^^^^
                              owner = project_key = "MYPROJECT"
```

`BacklogAdapter` のコンストラクタは `owner`（`ProjectConfig.owner`）と `project_key`（`ProjectConfig.project_key`）を両方受け取るが、実際の API リクエストにはすべて `project_key` を使用する。

`gfo init` の手動設定パスでも `project_key` の入力が求められる。
`git config --local gfo.project-key` に保存され、`config.py` の `resolve_project_config()` で読み込まれる。

---

## 9. ページネーション

Backlog は `count` + `offset` のオフセットベースのページネーションを採用する。

```
GET /issues?projectId[]=1&count=20&offset=0
GET /issues?projectId[]=1&count=20&offset=20
GET /issues?projectId[]=1&count=20&offset=40
...
```

`http.py` の `paginate_offset()` で実装されており、以下の条件でループを終了する。

- レスポンス配列が空
- レスポンスの要素数が `count` より少ない（最終ページ）
- 取得件数が `limit` に到達した

| パラメータ | 型 | 説明 |
|---|---|---|
| `count` | int | 1 回のリクエストで取得する最大件数（1〜100、デフォルト 20） |
| `offset` | int | 取得開始位置（0 以上の整数） |

---

## 10. URL パターン

Backlog のスペース URL は 2 種類のドメインが存在する。

| ドメイン | 例 |
|---|---|
| `{space}.backlog.com` | `https://myspace.backlog.com` |
| `{space}.backlog.jp` | `https://myspace.backlog.jp` |

### 自動検出ロジック（`detect.py`）

`detect_from_url()` は remote URL のホスト名を検査し、以下のいずれかに一致すれば Backlog と判定する。

- ホストが `.backlog.com` で終わる
- ホストが `.backlog.jp` で終わる

SSH の場合はホスト名が `{space}.git.backlog.com` / `{space}.git.backlog.jp` になるため、
`.git.backlog.{com,jp}` サフィックスを除去して `.backlog.{com,jp}` に正規化する。

### clone URL パターン

```
https://{space}.backlog.com/git/{projectKey}/{repo}.git
```

`config.py` の `build_default_api_url()` では以下のように API URL を構築する。

```python
f"https://{host}/api/v2"
# 例: "https://myspace.backlog.com/api/v2"
```

---

## 11. 非対応機能

以下の操作は `NotSupportedError` を送出する。

| 操作 | 理由 |
|---|---|
| `list_releases` / `create_release` | Backlog REST API v2 にリリース管理 API が存在しない |
| `list_labels` / `create_label` | Backlog の「カテゴリー」は Issue のラベルに相当するが、gfo の label API に対応する CRUD エンドポイントがない |
| `list_milestones` / `create_milestone` | Backlog の「マイルストーン」は参照・更新 API があるが、gfo の統一インターフェース（`list_milestones` / `create_milestone`）に相当する実装が現時点で未対応 |
| `merge_pull_request` | Backlog REST API v2 に PR マージのエンドポイントが存在しない。Web UI URL を含むエラーメッセージを提示する |

`merge_pull_request` はエラーメッセージに Web URL を含む:

```
https://{space}.backlog.com/git/{projectKey}/{repoName}/pullRequests/{number}
```

ユーザーが Web ブラウザから手動でマージできるよう誘導する。

---

## 12. 統合テスト

### 環境変数

Backlog は有料サービスのため、デフォルトではスキップされる。アカウント保有者が以下の環境変数を設定した場合のみ実行される。
`tests/integration/.env` に設定する（`.gitignore` に含まれるためコミットされない）。

| 環境変数 | 説明 | 例 |
|---|---|---|
| `GFO_TEST_BACKLOG_API_KEY` | API キー | `abcdefghijklmn` |
| `GFO_TEST_BACKLOG_HOST` | スペースのホスト名 | `your-space.backlog.com` |
| `GFO_TEST_BACKLOG_OWNER` | プロジェクトキー（owner として扱う） | `MYPROJECT` |
| `GFO_TEST_BACKLOG_REPO` | テスト対象リポジトリ名 | `gfo-integration-test` |
| `GFO_TEST_BACKLOG_PROJECT_KEY` | プロジェクトキー | `MYPROJECT` |

### サービス固有の注意事項

- `GFO_TEST_BACKLOG_OWNER` には Backlog のプロジェクトキー（大文字英字）を設定する
- pr merge / release / label / milestone テストは自動スキップ（§11 参照）
- テスト実行: `pytest tests/integration/test_backlog.py -v`
