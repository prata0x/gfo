# GitHub 仕様メモ

gfo における GitHub アダプターの実装に関する仕様・挙動・注意事項をまとめる。

---

## 1. 基本情報

| 項目 | 値 |
|---|---|
| API バージョン | REST API（2022-11-28） |
| ベース URL | `https://api.github.com` |
| 認証方式 | Bearer Token（`Authorization: Bearer <token>`） |
| gfo 識別子 | `github` |
| 環境変数 | `GITHUB_TOKEN` |

---

## 2. 認証

### 形式

Fine-grained Personal Access Token（推奨）または Classic Personal Access Token を使用する。

```
Authorization: Bearer ghp_xxxxxxxxxxxx
```

または Fine-grained PAT の場合:

```
Authorization: Bearer github_pat_xxxxxxxxxxxx
```

`HttpClient` の `auth_header` として `{"Authorization": "Bearer <token>"}` 形式で渡す。

### credentials.toml への格納

```toml
[tokens]
"github.com" = "ghp_xxxxxxxxxxxx"
```

または Fine-grained PAT の場合:

```toml
[tokens]
"github.com" = "github_pat_xxxxxxxxxxxx"
```

### トークン発行

- Classic PAT: https://github.com/settings/tokens
- Fine-grained PAT: https://github.com/settings/tokens?type=beta

---

## 3. スコープ一覧

### Fine-grained PAT

Fine-grained PAT は Classic PAT の粗いスコープに替わり、リソースごとに読み取り・書き込みを個別に制御できる。

#### Repository permissions

リポジトリ単位またはオーガニゼーション単位のリソースへのアクセスを制御する。

| Permission | アクセスレベル | 説明 |
|---|---|---|
| **Actions** | read / write | GitHub Actions のワークフロー・実行・アーティファクトを管理する |
| **Administration** | read / write | リポジトリ設定・ブランチ保護・コラボレーターを管理する |
| **Artifact Metadata** | read / write | アーティファクトメタデータにアクセスする |
| **Attestations** | read / write | アーティファクトの attestation を管理する |
| **Code scanning alerts** | read / write | コードスキャンで検出されたセキュリティ脆弱性アラートを管理する |
| **Codespaces** | read / write | クラウド開発環境（Codespaces）を管理する |
| **Codespaces lifecycle admin** | read / write | Codespaces の作成・ライフサイクルを制御する |
| **Codespaces metadata** | read | Codespaces の情報を参照する（書き込み不可） |
| **Codespaces secrets** | write | Codespaces 用シークレットを管理する（読み取り不可） |
| **Commit statuses** | read / write | コミットステータスチェックを管理する |
| **Contents** | read / write | リポジトリコード・ファイル・コミット・ブランチ・タグにアクセスする |
| **Custom properties** | read / write | リポジトリのカスタムプロパティを管理する |
| **Dependabot alerts** | read / write | 依存関係の脆弱性アラートを管理する |
| **Dependabot secrets** | read / write | Dependabot 自動化用シークレットを管理する |
| **Deployments** | read / write | デプロイメントプロセスを制御する |
| **Discussions** | read / write | リポジトリディスカッションを管理する |
| **Environments** | read / write | デプロイメント環境を管理する |
| **Issues** | read / write | Issue の参照・作成・更新・クローズを行う |
| **Merge queues** | read / write | マージキュー操作を管理する |
| **Metadata** | read | リポジトリ基本情報（名前・説明・トピック等）を参照する（**常に付与**） |
| **Pages** | read / write | GitHub Pages サイトを管理する |
| **Pull requests** | read / write | PR の参照・作成・マージ・クローズを行う |
| **Repository security advisories** | read / write | セキュリティアドバイザリを管理する |
| **Secret scanning alerts** | read / write | 検出されたシークレットリークアラートを管理する |
| **Secrets** | read / write | リポジトリシークレットを管理する |
| **Variables** | read / write | リポジトリの Actions 変数を管理する |
| **Webhooks** | read / write | リポジトリ Webhook を設定する |
| **Workflows** | write | ワークフローファイルを変更する（読み取りは Contents で行う） |

#### Account permissions

トークンを発行したユーザー自身のアカウントリソースへのアクセスを制御する。

| Permission | アクセスレベル | 説明 |
|---|---|---|
| **Block another user** | read / write | ユーザーブロック機能を制御する |
| **Codespaces user secrets** | read / write | 個人の Codespaces シークレットを管理する |
| **Copilot Chat** | read | Copilot の会話機能にアクセスする |
| **Copilot Editor Context** | read | エディタコンテキストを Copilot に提供する |
| **Copilot requests** | write | Copilot リクエストを実行する（プレミアムリクエスト枠を消費する） |
| **Email addresses** | read / write | メールアドレス設定にアクセスする |
| **Events** | read | 個人アクティビティイベントを参照する |
| **Followers** | read / write | フォロワー関係を管理する |
| **GPG keys** | read / write | GPG 署名鍵を管理する |
| **Gists** | write | コードスニペット（Gist）を作成・管理する |
| **Git SSH keys** | read / write | SSH 認証鍵を管理する |
| **Interaction limits** | read / write | 会話制限（スパム対策）を設定する |
| **Knowledge bases** | read / write | 個人ナレッジベースにアクセスする |
| **Models** | read | AI モデル機能にアクセスする |
| **Plan** | read | アカウントのサブスクリプション情報を参照する |
| **Private repository invitations** | read | プライベートリポジトリへの招待を参照する |
| **Profile** | write | プロフィール情報を更新する |
| **SSH signing keys** | read / write | SSH コミット署名鍵を管理する |
| **Starring** | read / write | リポジトリのスターを管理する |
| **Watching** | read / write | リポジトリ通知設定（Watch）を管理する |

### Classic PAT スコープ（参考）

Classic PAT を使用する場合に gfo が必要とする主なスコープ:

| スコープ | 説明 |
|---|---|
| `repo` | プライベートリポジトリへの完全アクセス（PR・Issue・Contents 等を含む） |
| `public_repo` | パブリックリポジトリのみアクセスする場合の代替 |
| `read:user` | ユーザー情報の読み取り |

---

## 4. gfo で必要なスコープ

Fine-grained PAT を使用する場合の最小 permission 早見表。

| gfo コマンド | 必要 permission |
|---|---|
| `repo list` / `repo view` | `Metadata: read`（自動付与）, `Contents: read` |
| `repo create` | `Administration: write` |
| `repo delete` | `Administration: write` |
| `pr list` / `pr view` | `Pull requests: read` |
| `pr create` | `Pull requests: write`, `Contents: read`（ブランチ参照） |
| `pr merge` | `Pull requests: write` |
| `pr close` | `Pull requests: write` |
| `pr checkout` | `Contents: read`（ローカル git fetch） |
| `issue list` / `issue view` | `Issues: read` |
| `issue create` | `Issues: write` |
| `issue close` | `Issues: write` |
| `release list` | `Contents: read` |
| `release create` | `Contents: write`（タグ作成）, `Actions: read`（任意） |
| `release delete` | `Contents: write` |
| `label list` / `label create` / `label delete` | `Issues: read` / `Issues: write` |
| `milestone list` / `milestone create` / `milestone delete` | `Issues: read` / `Issues: write` |
| `create_commit_status` / `list_commit_statuses` | `Commit statuses: read / write` |
| `list_webhooks` / `create_webhook` / `delete_webhook` | `Webhooks: read / write` |
| 統合テスト用ファイルコミット（Contents API） | `Contents: write` |

> **統合テストの補足**: PR テストではマージ後にテストブランチに差分がなくなる。次回テスト実行前に Contents API（`PUT /repos/{owner}/{repo}/contents/{path}`）でマーカーファイルをコミットして差分を作る。この処理に `Contents: write` が必要。gfo 本体の機能としては不要。

---

## 5. API エンドポイント

ベース URL: `https://api.github.com`

エンドポイントの `{owner}` と `{repo}` は `urllib.parse.quote()` で URL エンコードする（`safe=''`）。

### Pull Request

| 操作 | メソッド | エンドポイント |
|---|---|---|
| PR 一覧 | `GET` | `/repos/{owner}/{repo}/pulls` |
| PR 作成 | `POST` | `/repos/{owner}/{repo}/pulls` |
| PR 取得 | `GET` | `/repos/{owner}/{repo}/pulls/{number}` |
| PR マージ | `PUT` | `/repos/{owner}/{repo}/pulls/{number}/merge` |
| PR クローズ | `PATCH` | `/repos/{owner}/{repo}/pulls/{number}` |

### Issue

| 操作 | メソッド | エンドポイント |
|---|---|---|
| Issue 一覧 | `GET` | `/repos/{owner}/{repo}/issues` |
| Issue 作成 | `POST` | `/repos/{owner}/{repo}/issues` |
| Issue 取得 | `GET` | `/repos/{owner}/{repo}/issues/{number}` |
| Issue クローズ | `PATCH` | `/repos/{owner}/{repo}/issues/{number}` |

### Repository

| 操作 | メソッド | エンドポイント |
|---|---|---|
| リポジトリ一覧（認証済みユーザー） | `GET` | `/user/repos` |
| リポジトリ一覧（特定ユーザー） | `GET` | `/users/{owner}/repos` |
| リポジトリ作成 | `POST` | `/user/repos` |
| リポジトリ取得 | `GET` | `/repos/{owner}/{repo}` |

### Release

| 操作 | メソッド | エンドポイント |
|---|---|---|
| リリース一覧 | `GET` | `/repos/{owner}/{repo}/releases` |
| リリース作成 | `POST` | `/repos/{owner}/{repo}/releases` |
| タグからリリース取得（tag → id 解決） | `GET` | `/repos/{owner}/{repo}/releases/tags/{tag}` |
| リリース削除（id 指定） | `DELETE` | `/repos/{owner}/{repo}/releases/{id}` |

### Label

| 操作 | メソッド | エンドポイント |
|---|---|---|
| ラベル一覧 | `GET` | `/repos/{owner}/{repo}/labels` |
| ラベル作成 | `POST` | `/repos/{owner}/{repo}/labels` |
| ラベル削除 | `DELETE` | `/repos/{owner}/{repo}/labels/{name}` |

### Milestone

| 操作 | メソッド | エンドポイント |
|---|---|---|
| マイルストーン一覧 | `GET` | `/repos/{owner}/{repo}/milestones` |
| マイルストーン作成 | `POST` | `/repos/{owner}/{repo}/milestones` |
| マイルストーン削除 | `DELETE` | `/repos/{owner}/{repo}/milestones/{number}` |

---

## 6. 状態マッピング

### PR 状態

GitHub API は PR の `state` を `open` / `closed` の 2 値で返す。マージ済みかどうかは `merged_at` フィールドの有無で判定する。

| GitHub API `state` | `merged_at` | gfo |
|---|---|---|
| `open` | `null` | `open` |
| `closed` | `null` | `closed` |
| `closed` | タイムスタンプ | `merged` |

`pr list --state merged` の場合:

1. GitHub API に `state=closed` でリクエストする（`merged` というパラメータ値はない）
2. 取得したレスポンスをフィルタリングし `pr.state == "merged"` のものだけを返す

### Issue 状態

| GitHub API `state` | gfo |
|---|---|
| `open` | `open` |
| `closed` | `closed` |

Issue クローズ時は `PATCH /issues/{number}` に `{"state": "closed"}` を送信する。

---

## 7. PR 仕様

### checkout の refspec

GitHub は `refs/pull/{number}/head` という特別な refspec でどの PR のコードも fetch できる。

```python
def get_pr_checkout_refspec(self, number: int, *, pr: PullRequest | None = None) -> str:
    return f"refs/pull/{number}/head"
```

`gfo pr checkout` はこの refspec を使って `git fetch origin refs/pull/{number}/head` を実行し、ローカルにチェックアウトする。PR オブジェクトを別途取得する必要がなく、number だけで動作する。

### マージ戦略

`PUT /repos/{owner}/{repo}/pulls/{number}/merge` の `merge_method` パラメータに対応:

| gfo `--method` | GitHub `merge_method` |
|---|---|
| `merge` | `merge` |
| `squash` | `squash` |
| `rebase` | `rebase` |

### Draft PR

`POST /repos/{owner}/{repo}/pulls` の `draft: true` フラグで draft PR を作成できる。`gfo pr create --draft` で利用可能。

---

## 8. Issue 仕様

### PR が混在するレスポンスのフィルタリング

GitHub の `/repos/{owner}/{repo}/issues` エンドポイントは Issue と PR の両方を返す。PR を含むエントリには `pull_request` キーが存在するため、gfo はこれを除外する。

```python
return [self._to_issue(r) for r in results if "pull_request" not in r]
```

### assignee・label フィルタ

- `assignee` パラメータ: `?assignee={login}` で担当者フィルタ
- `label` パラメータ: `?labels={label}` でラベルフィルタ（カンマ区切りで複数指定可能だが gfo は単一のみ）

### Issue 作成時のフィールドマッピング

| gfo パラメータ | GitHub API フィールド |
|---|---|
| `assignee` | `assignees: [login]`（配列形式） |
| `label` | `labels: [name]`（配列形式） |

---

## 9. Release 仕様

### tag → id 解決

GitHub の Release 削除 API は `id`（数値）でリリースを指定する必要がある。タグ名からリリースを削除する場合は 2 ステップの処理が必要:

1. `GET /repos/{owner}/{repo}/releases/tags/{tag}` でリリース情報を取得し `id` を得る
2. `DELETE /repos/{owner}/{repo}/releases/{id}` でリリースを削除する

```python
def delete_release(self, *, tag: str) -> None:
    resp = self._client.get(f"{self._repos_path()}/releases/tags/{quote(tag, safe='')}")
    release_id = resp.json()["id"]
    self._client.delete(f"{self._repos_path()}/releases/{release_id}")
```

### git タグの残留

Release を削除しても関連する git タグは自動では削除されない。テスト後のクリーンアップでは以下のエンドポイントで個別削除が必要:

```
DELETE /repos/{owner}/{repo}/git/refs/tags/{tag}
```

### リリース作成フィールド

| gfo パラメータ | GitHub API フィールド |
|---|---|
| `tag` | `tag_name` |
| `title` | `name` |
| `notes` | `body` |
| `draft` | `draft` |
| `prerelease` | `prerelease` |

---

## 10. Label 仕様

### ラベル削除

`DELETE /repos/{owner}/{repo}/labels/{name}` でラベル名を URL パスに直接指定する。名前は `urllib.parse.quote(name, safe='')` でエンコードする。

### ラベル作成フィールド

| gfo パラメータ | GitHub API フィールド | 必須 |
|---|---|---|
| `name` | `name` | 必須 |
| `color` | `color` | 任意（16 進数 6 桁、`#` なし） |
| `description` | `description` | 任意 |

---

## 11. Milestone 仕様

### マイルストーン削除

`DELETE /repos/{owner}/{repo}/milestones/{number}` でマイルストーン番号を指定する。

### マイルストーン作成フィールド

| gfo パラメータ | GitHub API フィールド | 必須 |
|---|---|---|
| `title` | `title` | 必須 |
| `description` | `description` | 任意 |
| `due_date` | `due_on` | 任意（ISO 8601 形式） |

---

## 12. ページネーション

### Link ヘッダー方式

GitHub は RFC 5988 準拠の `Link` レスポンスヘッダーで次ページ URL を通知する。

```
Link: <https://api.github.com/repos/owner/repo/issues?page=2>; rel="next",
      <https://api.github.com/repos/owner/repo/issues?page=5>; rel="last"
```

gfo は `paginate_link_header()`（`http.py`）でこのヘッダーを解析し、`rel="next"` の URL を追跡して全ページを取得する。

### SSRF 防止

`next_url` が `base_url` と同一オリジン（scheme + host + port）であることを検証する。別オリジンを指す場合はページネーションを中断する。

### per_page パラメータ

初回リクエストに `per_page=30` を付与する（デフォルト値）。`limit` パラメータが `per_page` より小さい場合は `per_page` を `limit` に合わせる。

---

## 13. URL パターン

### HTTPS（clone URL）

```
https://github.com/{owner}/{repo}.git
```

### SSH

```
git@github.com:{owner}/{repo}.git
```

### detect.py による自動検出

`github.com` を含むリモート URL から自動的に `github` サービス識別子を判定する。

---

## 14. File 操作の注意点

### エンドポイント

```
PUT /repos/{owner}/{repo}/contents/{path}
```

新規作成・既存更新ともに同じエンドポイントを使用する。既存ファイル更新時は `sha`（blob SHA）が必須。

### レスポンスから commit SHA を取得する

```json
{
  "commit": { "sha": "abc123..." },
  "content": { "sha": "blob-sha..." }
}
```

`commit.sha` はコミット SHA、`content.sha` は blob SHA（ファイルの SHA）。
`create_or_update_file()` は `commit.sha` を返す。

### 読み書き整合性（ブランチ伝播遅延）

ファイル書き込み直後に `GET /contents/{path}?ref={branch}` で読み返すと、
GitHub の CDN キャッシュ／ブランチ HEAD 解決の遅延により**古いコンテンツが返ることがある**。

回避策: `create_or_update_file()` が返す commit SHA を `ref` に指定して読み返す。

```python
commit_sha = adapter.create_or_update_file("file.txt", content="updated", sha=old_sha)
# commit SHA を ref に使えばブランチキャッシュを完全にバイパスできる
content, _ = adapter.get_file_content("file.txt", ref=commit_sha)
```

ブランチ参照（`ref=branch`）では整合性が保証されないため、更新内容を即座に検証する場合は
必ず commit SHA を使うこと。

---

## 15. 非対応機能

以下の操作は GitHub REST API が対応していないため `NotSupportedError` を返す。

| メソッド | 理由 |
|---|---|
| `delete_issue` | GitHub REST API に Issue 削除エンドポイントが存在しない（GraphQL API でのみ可能） |
| `list_wiki_pages` | GitHub REST API は Wiki 読み取り API を提供しない |
| `get_wiki_page` | 同上 |
| `create_wiki_page` | 同上 |
| `update_wiki_page` | 同上 |
| `delete_wiki_page` | 同上 |

Wiki 操作を行う場合は、リポジトリの Wiki を git clone して直接操作する必要がある:

```bash
git clone https://github.com/{owner}/{repo}.wiki.git
```

---

## 16. 統合テスト環境変数

`tests/integration/.env` に設定する（`.env.example` を参照）。

| 環境変数 | 説明 | 例 |
|---|---|---|
| `GFO_TEST_GITHUB_TOKEN` | Fine-grained PAT または Classic PAT | `ghp_xxxxxxxxxxxx` |
| `GFO_TEST_GITHUB_OWNER` | テスト用リポジトリのオーナー（ユーザー名またはオーガニゼーション名） | `your-username` |
| `GFO_TEST_GITHUB_REPO` | テスト用リポジトリ名 | `gfo-integration-test` |
| `GFO_TEST_GITHUB_DEFAULT_BRANCH` | デフォルトブランチ名（省略時 `main`） | `main` |

### テスト用リポジトリの前提条件

- `gfo-test-branch` ブランチが存在すること（`main` からの差分がある状態）
- Issue トラッカーが有効であること
- テストを実行するトークンが当該リポジトリへのアクセス権を持つこと

### 必要な permission（統合テスト用 Fine-grained PAT）

| Permission | レベル | 用途 |
|---|---|---|
| `Contents` | read / write | ブランチ参照・テスト用ファイルコミット |
| `Issues` | read / write | Issue 作成・参照・クローズ |
| `Pull requests` | read / write | PR 作成・参照・マージ |
| `Administration` | read / write | `repo delete` に必要 |
| `Commit statuses` | read / write | コミットステータスの作成・一覧 |
| `Webhooks` | read / write | Webhook CRUD テスト |
| `Metadata` | read | リポジトリ情報参照（自動付与） |

リリース・ラベル・マイルストーンのテストも実行する場合は以下も追加:

| Permission | レベル | 用途 |
|---|---|---|
| `Contents` | write | リリース用タグ・git refs 削除 |
