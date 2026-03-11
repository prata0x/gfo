# Bitbucket Cloud 仕様メモ

gfo における Bitbucket Cloud アダプターの実装に関する仕様・挙動・注意事項をまとめる。

---

## 1. 基本情報

| 項目 | 値 |
|---|---|
| API バージョン | REST API v2 |
| ベース URL | `https://api.bitbucket.org/2.0` |
| 認証方式 | Basic Auth（`email:api-token` 形式） |
| gfo 識別子 | `bitbucket` |
| 環境変数 | `BITBUCKET_TOKEN` |

---

## 2. 認証

### 形式

スコープ付き API Token を使用する。App Password は **2026 年 6 月に完全廃止予定**。

```
Authorization: Basic base64(email:api-token)
```

- **email**: Atlassian アカウントのログインメールアドレス
- **api-token**: Atlassian の管理画面で発行したスコープ付き API Token（`ATATT-...` で始まる）

### credentials.toml への格納

```toml
[tokens]
"bitbucket.org" = "your@email.com:ATATT-xxxxxxxxxxxx"
```

`auth.py` がコロンで分割し、タプル `(email, api-token)` として `HttpClient` の `basic_auth` に渡す。

### トークン発行

https://id.atlassian.com/manage-profile/security/api-tokens

---

## 3. スコープ一覧

Bitbucket Scoped API Token で選択可能な全スコープ。スコープ名は `action:resource:bitbucket` 形式。

### Account / User

| スコープ | 説明 |
|---|---|
| `read:account` *(classic)* | View user profiles |
| `read:me` *(classic)* | View the profile details for the currently logged-in user |
| `read:user:bitbucket` | View user info |
| `write:user:bitbucket` | Modify user info |

### Workspace

| スコープ | 説明 |
|---|---|
| `read:workspace:bitbucket` | View your workspaces |
| `admin:workspace:bitbucket` | Administer your workspaces |
| `manage:org` | — |

### Repository

| スコープ | 説明 |
|---|---|
| `read:repository:bitbucket` | View your repositories |
| `write:repository:bitbucket` | Modify your repositories |
| `admin:repository:bitbucket` | Administer your repositories |
| `delete:repository:bitbucket` | Delete your repositories |

### Pull Request

| スコープ | 説明 |
|---|---|
| `read:pullrequest:bitbucket` | View your pull requests |
| `write:pullrequest:bitbucket` | Modify your pull requests |

> **注意**: `write:pullrequest:bitbucket` は読み取り権限を**含まない**。PR の読み取りには `read:pullrequest:bitbucket` が別途必要。

### Issue

| スコープ | 説明 |
|---|---|
| `read:issue:bitbucket` | View your issues |
| `write:issue:bitbucket` | Modify your issues |
| `delete:issue:bitbucket` | Delete your issues |

> **注意**: write/delete も read を**含まない**。読み取りには `read:issue:bitbucket` が別途必要。

### Project

| スコープ | 説明 |
|---|---|
| `read:project:bitbucket` | View your projects |
| `admin:project:bitbucket` | Administer your projects |

### Pipeline

| スコープ | 説明 |
|---|---|
| `read:pipeline:bitbucket` | View your pipelines |
| `write:pipeline:bitbucket` | Modify your pipelines |
| `admin:pipeline:bitbucket` | Administer your pipelines |

### Runner

| スコープ | 説明 |
|---|---|
| `read:runner:bitbucket` | View your workspaces/repositories' runners |
| `write:runner:bitbucket` | Modify your workspaces/repositories' runners |

### Webhook

| スコープ | 説明 |
|---|---|
| `read:webhook:bitbucket` | View your webhooks |
| `write:webhook:bitbucket` | Modify your webhooks |
| `delete:webhook:bitbucket` | Delete your webhooks |

### Snippet

| スコープ | 説明 |
|---|---|
| `read:snippet:bitbucket` | View your snippets |
| `write:snippet:bitbucket` | Modify your snippets |
| `delete:snippet:bitbucket` | Delete your snippets |

### Wiki

| スコープ | 説明 |
|---|---|
| `read:wiki:bitbucket` | View wikis |
| `write:wiki:bitbucket` | Modify wikis |
| `delete:wiki:bitbucket` | Delete wikis |

### SSH Key

| スコープ | 説明 |
|---|---|
| `read:ssh-key:bitbucket` | View your SSH keys |
| `write:ssh-key:bitbucket` | Modify your SSH keys |
| `delete:ssh-key:bitbucket` | Delete your SSH keys |

### GPG Key

| スコープ | 説明 |
|---|---|
| `read:gpg-key:bitbucket` | View your GPG keys |
| `write:gpg-key:bitbucket` | Modify your GPG keys |
| `delete:gpg-key:bitbucket` | Delete your GPG keys |

### Permission

| スコープ | 説明 |
|---|---|
| `read:permission:bitbucket` | View permissions |
| `write:permission:bitbucket` | Modify permissions |
| `delete:permission:bitbucket` | Delete permissions |

### Package / Test

| スコープ | 説明 |
|---|---|
| `read:package:bitbucket` | — |
| `write:package:bitbucket` | — |
| `read:test:bitbucket` | View your workspaces/repositories' test data |
| `write:test:bitbucket` | Modify your workspaces/repositories' test data |

---

## 4. gfo で必要なスコープ

| gfo コマンド | 必要スコープ |
|---|---|
| `repo list` / `repo view` | `read:repository:bitbucket` |
| `repo create` | `write:repository:bitbucket` |
| `repo delete` | `delete:repository:bitbucket` |
| `pr list` / `pr view` | `read:pullrequest:bitbucket` |
| `pr create` / `pr merge` / `pr close` | `write:pullrequest:bitbucket` |
| `issue list` / `issue view` | `read:issue:bitbucket` |
| `issue create` / `issue close` | `write:issue:bitbucket` |
| `issue delete` | `delete:issue:bitbucket` |
| `list_webhooks` | `read:webhook:bitbucket` |
| `create_webhook` / `update_webhook` | `write:webhook:bitbucket` |
| `delete_webhook` | `delete:webhook:bitbucket` |
| `list_deploy_keys` | `read:ssh-key:bitbucket` |
| `create_deploy_key` / `update_deploy_key` | `write:ssh-key:bitbucket` |
| `delete_deploy_key` | `delete:ssh-key:bitbucket` |
| `get_current_user` | `read:user:bitbucket` |
| `list_collaborators` | `read:repository:bitbucket` |
| 統合テスト用コミット（Src API） | `write:repository:bitbucket` |

> **統合テストの補足**: PR テストではマージ後に `gfo-test-branch` と `main` の差分がなくなる。次回テスト実行前に Bitbucket Src API（`POST /repositories/{ws}/{repo}/src`）でマーカーファイルをコミットして差分を作る。この処理に `write:repository:bitbucket` が必要。gfo 本体の機能としては不要。

---

## 5. API エンドポイント

### Pull Request

| 操作 | メソッド | エンドポイント |
|---|---|---|
| PR 一覧 | `GET` | `/repositories/{workspace}/{repo}/pullrequests` |
| PR 作成 | `POST` | `/repositories/{workspace}/{repo}/pullrequests` |
| PR 取得 | `GET` | `/repositories/{workspace}/{repo}/pullrequests/{id}` |
| PR マージ | `POST` | `/repositories/{workspace}/{repo}/pullrequests/{id}/merge` |
| PR クローズ | `POST` | `/repositories/{workspace}/{repo}/pullrequests/{id}/decline` |

### Issue

| 操作 | メソッド | エンドポイント |
|---|---|---|
| Issue 一覧 | `GET` | `/repositories/{workspace}/{repo}/issues` |
| Issue 作成 | `POST` | `/repositories/{workspace}/{repo}/issues` |
| Issue 取得 | `GET` | `/repositories/{workspace}/{repo}/issues/{id}` |
| Issue クローズ | `PUT` | `/repositories/{workspace}/{repo}/issues/{id}` |
| Issue 削除 | `DELETE` | `/repositories/{workspace}/{repo}/issues/{id}` |

### Repository

| 操作 | メソッド | エンドポイント |
|---|---|---|
| リポジトリ一覧 | `GET` | `/repositories/{workspace}` |
| リポジトリ作成 | `POST` | `/repositories/{workspace}/{repo}` |
| リポジトリ取得 | `GET` | `/repositories/{workspace}/{repo}` |

### その他（gfo 未実装）

| 操作 | メソッド | エンドポイント |
|---|---|---|
| ファイルコミット（Src API） | `POST` | `/repositories/{workspace}/{repo}/src` |

---

## 6. 状態マッピング

### PR 状態

Bitbucket の PR 状態は大文字。gfo は小文字に正規化する。

| Bitbucket | gfo |
|---|---|
| `OPEN` | `open` |
| `DECLINED` | `closed` |
| `SUPERSEDED` | `closed` |
| `MERGED` | `merged` |

`pr list --state` → API `state` パラメータのマッピング:

| gfo `--state` | Bitbucket API `state` |
|---|---|
| `open` | `OPEN` |
| `closed` | `DECLINED` |
| `merged` | `MERGED` |
| `all` | パラメータなし（`ALL` は無効値のため省略） |

### Issue 状態

Bitbucket の Issue 状態は細分化されている。gfo は open / closed の 2 値に正規化する。

| Bitbucket | gfo |
|---|---|
| `new`, `open` | `open` |
| `resolved`, `on hold`, `invalid`, `duplicate`, `wontfix`, `closed` | `closed` |

`issue list --state` → API クエリパラメータ `q` のマッピング:

| gfo `--state` | Bitbucket `q` フィルタ |
|---|---|
| `open` | `(state="new" OR state="open")` |
| `closed` | `(state != "new" AND state != "open")` |
| `all` | フィルタなし |
| その他 | `state="{state}"` をそのまま使用 |

Issue クローズ時は `PUT /issues/{id}` に `{"state": "resolved"}` を送信する。

---

## 7. Issue API の注意事項

### links フィールド

PR レスポンスには `links.html` があるが、**Issue レスポンスには `links.html` がなく `links.self` のみ**存在する。

```python
# gfo の実装（bitbucket.py）
url=(
    (data["links"].get("html") or data["links"].get("self") or {}).get("href", "")
),
```

### label フィルタ

Bitbucket の Issue には GitHub 的な「ラベル」がなく、代わりに「コンポーネント」が対応する。

- Issue 作成時: `payload["component"] = {"name": label}`
- Issue 一覧の label フィルタ: `q` パラメータに `component.name="{label}"` を追加
- Issue レスポンスの `component` フィールドを `labels` リストに変換

### Issue 削除

`DELETE /repositories/{workspace}/{repo}/issues/{id}` で削除可能（HTTP 204 を返す）。
`delete:issue:bitbucket` スコープが必要。

---

## 8. PR の checkout

Bitbucket は GitHub のような `refs/pull/{number}/head` refspec をサポートしない。
代わりにソースブランチ名を直接 fetch する。

```python
def get_pr_checkout_refspec(self, number: int, *, pr: PullRequest | None = None) -> str:
    if pr is None:
        pr = self.get_pull_request(number)
    return pr.source_branch  # ブランチ名をそのまま返す
```

---

## 9. ページネーション

Bitbucket はレスポンス JSON 内の `next` フィールドで次ページ URL を示す。

```json
{
  "values": [...],
  "next": "https://api.bitbucket.org/2.0/repositories/.../issues?page=2"
}
```

`next` が存在しない、または別オリジンを指す場合はページネーションを中断する（SSRF 防止）。

---

## 10. PR マージ戦略

| gfo `--method` | Bitbucket `merge_strategy` |
|---|---|
| `merge` | `merge_commit` |
| `squash` | `squash` |
| `rebase` | `fast_forward` |

---

## 11. 非対応機能

以下は Bitbucket Cloud API が提供していないため `NotSupportedError` を返す。

| gfo コマンド | 理由 |
|---|---|
| `release list/create/delete` | Bitbucket に Release 機能なし |
| `label list/create/delete` | Bitbucket に独立した Label 機能なし（Issue の component とは別物） |
| `milestone list/create/delete` | Bitbucket に Milestone 機能なし |

---

## 12. Issue トラッカーの前提

Bitbucket の Issue API は、リポジトリの Issue トラッカーが有効になっている場合のみ利用できる。

設定場所: リポジトリ設定 > Features > Issue tracker を有効化

トラッカーが無効な状態で API を叩くと HTTP 404 が返る。

---

## 13. Src API（ファイルコミット）

統合テストで PR テストの差分を確保するために使用するマルチパート API。通常の JSON API とは異なる。

```
POST /repositories/{workspace}/{repo}/src
Content-Type: multipart/form-data
```

フォームフィールド:
- `message`: コミットメッセージ（文字列）
- `branch`: コミット先ブランチ名（文字列）
- `{filename}`: ファイルコンテンツ（バイナリ）

```python
# requests での呼び出し例
session.post(
    f"{base_url}/repositories/{workspace}/{repo}/src",
    data={
        "message": "test: update marker",
        "branch": "gfo-test-branch",
    },
    files={"test-pr-marker.txt": ("test-pr-marker.txt", content.encode(), "text/plain")},
)
```

必要スコープ: `write:repository:bitbucket`
