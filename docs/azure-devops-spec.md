# Azure DevOps 仕様メモ

gfo における Azure DevOps アダプターの実装に関する仕様・挙動・注意事項をまとめる。

---

## 1. 基本情報

| 項目 | 値 |
|---|---|
| API バージョン | REST API v7.1 |
| ベース URL | `https://dev.azure.com/{org}/{project}/_apis` |
| 認証方式 | Basic Auth（ユーザー名は空、パスワードに PAT） |
| gfo 識別子 | `azure-devops` |
| 環境変数 | `AZURE_DEVOPS_PAT` |

全リクエストに `api-version=7.1` クエリパラメータを自動付与する。

---

## 2. 認証

### 形式

Personal Access Token（PAT）を Basic Auth で送信する。

```
Authorization: Basic base64(:PAT)
```

ユーザー名は空文字列、パスワード位置に PAT を設定する。

### credentials.toml への格納

```toml
[tokens]
"dev.azure.com" = "xxxxxxxxxxxx"
```

### PAT 発行

1. Azure DevOps 右上のユーザーアイコン → **Personal access tokens**
2. **New Token** をクリック
3. Organization: テスト対象の組織を選択
4. Scopes: **Custom defined** で必要スコープのみ選択（推奨）

---

## 3. スコープ一覧

Azure DevOps PAT で選択可能な全スコープ。

### Advanced Security
コード内のセキュリティ脆弱性の検出とアラート

| スコープ | 説明 |
|---|---|
| Read | 読み取り |
| Read & write | 読み取り・書き込み |
| Read, write, & manage | 読み取り・書き込み・管理 |

### Agent Pools
エージェントプールとエージェントの管理

| スコープ | 説明 |
|---|---|
| Read | 読み取り |
| Read & manage | 読み取り・管理 |

### Analytics
分析サービスからのデータ読み取り

| スコープ | 説明 |
|---|---|
| Read | 読み取り |

### Auditing
監査ログイベントの読み取り、ストリームの管理・削除

| スコープ | 説明 |
|---|---|
| Read Audit Log | 監査ログの読み取り |
| Manage Audit Streams | 監査ストリームの管理 |

### Build
アーティファクト、定義、リクエスト、ビルドのキューと更新

| スコープ | 説明 |
|---|---|
| Read | 読み取り |
| Read & execute | 読み取り・実行 |

### Code
ソースコード、リポジトリ、プルリクエスト、通知

| スコープ | 説明 |
|---|---|
| Read | 読み取り |
| Read & write | 読み取り・書き込み |
| Read, write, & manage | 読み取り・書き込み・管理 |
| Full | フルアクセス |
| Status | ステータス |

### Connected server

| スコープ | 説明 |
|---|---|
| Access endpoints | エンドポイントへのアクセス |
| Connected server | 接続済みサーバー |

### Deployment Groups
デプロイメントグループとデプロイメントプールの管理

| スコープ | 説明 |
|---|---|
| Read & manage | 読み取り・管理 |

### Entitlements
エンタイトルメント

| スコープ | 説明 |
|---|---|
| Read | 読み取り |

### Environment
環境の読み取りと管理

| スコープ | 説明 |
|---|---|
| Read & manage | 読み取り・管理 |

### Extension Data
拡張機能データの読み取りと書き込み

| スコープ | 説明 |
|---|---|
| Read | 読み取り |
| Read & write | 読み取り・書き込み |

### Extensions
拡張機能の読み取り、インストール、アンインストール、データ書き込み

| スコープ | 説明 |
|---|---|
| Read | 読み取り |
| Read & manage | 読み取り・管理 |

### GitHub Connections
GitHub 接続の読み取りと管理

| スコープ | 説明 |
|---|---|
| Read | 読み取り |
| Read & manage | 読み取り・管理 |

### Graph
読み取り、グループ化、スコープ設定、追加

| スコープ | 説明 |
|---|---|
| Read | 読み取り |
| Read & manage | 読み取り・管理 |

### Identity
ID とグループ

| スコープ | 説明 |
|---|---|
| Read | 読み取り |
| Read & manage | 読み取り・管理 |

### Marketplace
アイテムとパブリッシャーの読み取り、公開、更新、管理

| スコープ | 説明 |
|---|---|
| Read | 読み取り |
| Acquire | 取得 |
| Publish | 公開 |
| Manage | 管理 |

### Member Entitlement Management
ユーザーの読み取りと管理

| スコープ | 説明 |
|---|---|
| Read | 読み取り |
| Read & write | 読み取り・書き込み |

### Notifications
通知の読み取り、書き込み、管理、公開

| スコープ | 説明 |
|---|---|
| Read | 読み取り |
| Read & write | 読み取り・書き込み |
| Read, write, & manage | 読み取り・書き込み・管理 |
| Diagnostics | 診断 |

### Packaging
フィードとパッケージの作成・読み取り・更新・削除

| スコープ | 説明 |
|---|---|
| Read | 読み取り |
| Read & write | 読み取り・書き込み |
| Read, write, & manage | 読み取り・書き込み・管理 |

### Pipeline Resources
パイプラインリソースへのパイプライン実行アクセスの管理

| スコープ | 説明 |
|---|---|
| Use | 使用 |
| Use and manage | 使用・管理 |

### Project and Team
プロジェクトとチームの作成・読み取り・更新・削除

| スコープ | 説明 |
|---|---|
| Read | 読み取り |
| Read & write | 読み取り・書き込み |
| Read, write, & manage | 読み取り・書き込み・管理 |

### Pull Request Threads
プルリクエストコメントスレッドの読み取りと書き込み

| スコープ | 説明 |
|---|---|
| Read & write | 読み取り・書き込み |

### Release
リリース、リリースパイプライン、ステージの読み取り・更新・削除

| スコープ | 説明 |
|---|---|
| Read | 読み取り |
| Read, write, & execute | 読み取り・書き込み・実行 |
| Read, write, execute, & manage | 読み取り・書き込み・実行・管理 |

### Secure Files
セキュアファイルの読み取り、作成、管理

| スコープ | 説明 |
|---|---|
| Read | 読み取り |
| Read & create | 読み取り・作成 |
| Read, create, & manage | 読み取り・作成・管理 |

### Security
セキュリティの読み取り、書き込み、管理

| スコープ | 説明 |
|---|---|
| Manage | 管理 |

### Service Connections
サービス接続の読み取り、クエリ、管理

| スコープ | 説明 |
|---|---|
| Read | 読み取り |
| Read & query | 読み取り・クエリ |
| Read, query, & manage | 読み取り・クエリ・管理 |

### Symbols
シンボルの読み取り、書き込み、管理

| スコープ | 説明 |
|---|---|
| Read | 読み取り |
| Read & write | 読み取り・書き込み |
| Read, write, & manage | 読み取り・書き込み・管理 |

### Task Groups
タスクグループの読み取り、作成、管理

| スコープ | 説明 |
|---|---|
| Read | 読み取り |
| Read & create | 読み取り・作成 |
| Read, create, & manage | 読み取り・作成・管理 |

### Team Dashboard
チームダッシュボードの読み取りと管理

| スコープ | 説明 |
|---|---|
| Read | 読み取り |
| Read & manage | 読み取り・管理 |

### Test Management
テストプラン、ケース、結果の読み取り・作成・更新

| スコープ | 説明 |
|---|---|
| Read | 読み取り |
| Read & write | 読み取り・書き込み |

### Token Administration
トークンの読み取りと失効

| スコープ | 説明 |
|---|---|
| Read & manage | 読み取り・管理 |

### Tokens
トークンの読み取り、更新、失効

| スコープ | 説明 |
|---|---|
| Read & manage | 読み取り・管理 |

### User Profile
プロフィールへの書き込み

| スコープ | 説明 |
|---|---|
| Read | 読み取り |
| Read & write | 読み取り・書き込み |

### Variable Groups
変数グループの読み取り、作成、管理

| スコープ | 説明 |
|---|---|
| Read | 読み取り |
| Read & create | 読み取り・作成 |
| Read, create, & manage | 読み取り・作成・管理 |

### Wiki
Wiki の読み取り、作成、更新

| スコープ | 説明 |
|---|---|
| Read | 読み取り |
| Read & write | 読み取り・書き込み |

### Work Items
作業項目、クエリ、バックログ、プラン、メタデータ

| スコープ | 説明 |
|---|---|
| Read | 読み取り |
| Read & write | 読み取り・書き込み |
| Read, write, & manage | 読み取り・書き込み・管理 |

---

## 4. gfo で必要なスコープ

| gfo コマンド | 必要スコープ |
|---|---|
| `repo list` / `repo view` | **Code**: Read |
| `repo create` | **Code**: Read & write |
| `repo delete` | **Code**: Read, write, & manage |
| `pr list` / `pr view` | **Code**: Read |
| `pr create` / `pr merge` / `pr close` | **Code**: Read & write |
| `issue list` / `issue view` | **Work Items**: Read |
| `issue create` / `issue close` | **Work Items**: Read & write |
| `issue delete` | **Work Items**: Read, write, & manage |
| `create_review` / `get_current_user` | **Member Entitlement Management**: Read |

統合テスト用の最小構成:

```
Code:                          Read, write, & manage
Work Items:                    Read, write, & manage
Member Entitlement Management: Read
```

---

## 5. 階層構造

Organization > Project > Repository の 3 階層で構成される。

```
https://dev.azure.com/{organization}/{project}/_apis/...
```

| 項目 | gfo での扱い |
|---|---|
| Organization | `gfo.organization`（git config）に保存 |
| Project | `gfo.project-key`（git config）に保存 |
| Repository | `gfo.repo`（git config）に保存 |

```ini
# .git/config
[gfo]
    type = azure-devops
    host = dev.azure.com
    organization = myorg
    project-key = myproject
```

---

## 6. API エンドポイント

### Pull Request（Code スコープ）

| 操作 | メソッド | エンドポイント |
|---|---|---|
| PR 一覧 | `GET` | `/git/repositories/{repo}/pullrequests` |
| PR 作成 | `POST` | `/git/repositories/{repo}/pullrequests` |
| PR 取得 | `GET` | `/git/repositories/{repo}/pullrequests/{id}` |
| PR マージ | `PATCH` | `/git/repositories/{repo}/pullrequests/{id}` |
| PR クローズ | `PATCH` | `/git/repositories/{repo}/pullrequests/{id}` |

### Work Item / Issue（Work Items スコープ）

| 操作 | メソッド | エンドポイント |
|---|---|---|
| Issue 検索（WIQL） | `POST` | `/wit/wiql` |
| Issue バッチ取得 | `GET` | `/wit/workitems?ids={id1,id2,...}` |
| Issue 取得 | `GET` | `/wit/workitems/{id}` |
| Issue 作成 | `POST` | `/wit/workitems/${type}` |
| Issue クローズ | `PATCH` | `/wit/workitems/{id}` |

### Repository（Code スコープ）

| 操作 | メソッド | エンドポイント |
|---|---|---|
| リポジトリ一覧 | `GET` | `/git/repositories` |
| リポジトリ作成 | `POST` | `/git/repositories` |
| リポジトリ取得 | `GET` | `/git/repositories/{repo}` |

---

## 7. PR 仕様

### 状態マッピング

| gfo | Azure DevOps |
|---|---|
| `open` | `active` |
| `closed` | `abandoned` |
| `merged` | `completed` |

`pr list --state all` の場合は `searchCriteria.status` パラメータを省略する。

### マージ戦略マッピング

| gfo `--method` | `completionOptions.mergeStrategy` |
|---|---|
| `merge` | `noFastForward` |
| `squash` | `squash` |
| `rebase` | `rebase` |

マージ時には事前に PR を GET して `lastMergeSourceCommit` を取得する必要がある。

### ブランチ名の処理

| 方向 | 変換 |
|---|---|
| PR 作成時（gfo → API） | ブランチ名に `refs/heads/` を自動付与 |
| PR 取得時（API → gfo） | `refs/heads/` プレフィックスを除去してデータモデルに格納 |

### PR checkout の refspec

`refs/pull/{number}/head` を fetch する（GitHub 互換）。

---

## 8. Issue（Work Item）仕様

Azure DevOps の Issue は **Work Item** として扱われる。

### 状態マッピング

プロセステンプレートにより完了状態の名前が異なる。

| gfo | Work Item State |
|---|---|
| `open` | `Closed` / `Done` / `Removed` 以外すべて |
| `closed` | `Closed`, `Done`, `Removed` |

| プロセス | 完了状態名 |
|---|---|
| Agile | `Closed` |
| Scrum | `Done` |
| Basic | `Done` |

### Issue の label フィルタ

Azure DevOps には「ラベル」がなく、**System.Tags**（セミコロン区切り）で代替する。

- `issue list --label bug` → WIQL: `[System.Tags] CONTAINS 'bug'`
- `issue create --label bug` → `System.Tags = "bug"`

### Work Item Type（`--type`）

| `gfo issue create --type` | Azure DevOps Work Item Type |
|---|---|
| 省略 | `Task`（デフォルト） |
| `Bug` | `Bug` |
| `User Story` | `User Story` |
| その他任意文字列 | そのまま使用 |

### Issue 作成の Content-Type

Work Item 作成・更新は **JSON Patch 形式**を使用する。

```
Content-Type: application/json-patch+json
```

```json
[
  {"op": "add", "path": "/fields/System.Title", "value": "タイトル"},
  {"op": "add", "path": "/fields/System.Description", "value": "本文"},
  {"op": "add", "path": "/fields/System.AssignedTo", "value": "user@example.com"}
]
```

### Issue 一覧の 2 段階取得

1. **WIQL クエリ**（`POST /wit/wiql`）で Work Item ID 一覧を取得（`$top` で件数制限）
2. **バッチ取得**（`GET /wit/workitems?ids=...`）で詳細を取得（1 回最大 200 件）

```
limit ≤ 200 の場合: WIQL の $top に limit を指定 → 1 回のバッチ取得
limit > 200 の場合: バッチ取得を複数回に分けて実行
```

---

## 9. Repository 仕様

### `--owner` フィルタ非対応

リポジトリは Project にスコープされるため、`gfo repo list --owner` は `NotSupportedError` を返す。

### `full_name` の形式

```
{project}/{repo}
```

GitHub 互換の `owner/repo` ではなく、`project/repo` 形式となる。

---

## 10. ページネーション

`$top` + `$skip` クエリパラメータによるオフセット方式。

```
GET /git/repositories/{repo}/pullrequests?$top=30&$skip=0&api-version=7.1
```

---

## 11. 非対応機能

以下は Azure DevOps API の対応状況から `NotSupportedError` を返す。

| gfo コマンド | 理由 |
|---|---|
| `release list/create/delete` | Azure DevOps に Git タグベースの Release 機能なし（Azure Pipelines の Release とは別物） |
| `label list/create/delete` | 独立した Label リソースなし（Work Item Tags で代替） |
| `milestone list/create/delete` | Iteration Path に相当するが API マッピングが複雑なため v1 未実装 |

---

## 12. URL パターン

### HTTPS

```
https://dev.azure.com/{org}/{project}/_git/{repo}
```

### SSH

```
git@ssh.dev.azure.com:v3/{org}/{project}/{repo}
```

### 旧形式（Visual Studio）

```
https://{org}.visualstudio.com/{project}/_git/{repo}
```

いずれも gfo の自動検出で `azure-devops` と判定される。

---

## 13. 統合テスト環境変数

```bash
GFO_TEST_AZURE_DEVOPS_PAT=xxxxxxxxxxxx
GFO_TEST_AZURE_DEVOPS_ORG=your-organization-name
GFO_TEST_AZURE_DEVOPS_PROJECT=gfo-integration-test
GFO_TEST_AZURE_DEVOPS_REPO=gfo-integration-test
```

- `ORG`: `dev.azure.com/{ORG}` の組織名部分
- `PROJECT`: Azure DevOps プロジェクト名
- `REPO`: リポジトリ名（プロジェクト名と同じことが多い）
