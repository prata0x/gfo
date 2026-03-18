# 認証ガイド

## トークンの設定方法

gfo はトークンを以下の優先順位で解決します:

1. `credentials.toml`（`gfo auth login` で保存）
2. サービス別環境変数
3. `GFO_TOKEN` 環境変数（全サービス共通のフォールバック）

### 方法 1: gfo auth login（推奨）

リポジトリ内で以下を実行するとトークンが `credentials.toml` に保存されます:

```bash
gfo auth login
```

ホストを明示的に指定する場合:

```bash
gfo auth login --host github.com
```

コマンドラインでトークンを直接渡す場合（スクリプト・CI 向け）:

```bash
gfo auth login --host github.com --token ghp_xxxx
```

設定済みのトークン一覧を確認:

```bash
gfo auth status
```

### 方法 2: credentials.toml を手動編集

**ファイルパス:**
- Windows: `%APPDATA%\gfo\credentials.toml`
- Linux / macOS: `~/.config/gfo/credentials.toml`

```toml
[tokens]
"github.com" = "ghp_xxxxxxxxxxxxxxxxxxxx"
"gitlab.com" = "glpat-xxxxxxxxxxxxxxxxxxxx"
"bitbucket.org" = "user@example.com:app-password"
"dev.azure.com" = "azure-pat-string"
"gitea.example.com" = "xxxxxxxxxxxxxxxxxxxxxxxx"
"myspace.backlog.com" = "backlog-api-key"
```

### 方法 3: 環境変数

| サービス | 環境変数 |
|---|---|
| GitHub | `GITHUB_TOKEN` |
| GitLab | `GITLAB_TOKEN` |
| Bitbucket Cloud | `BITBUCKET_TOKEN` |
| Azure DevOps | `AZURE_DEVOPS_PAT` |
| Gitea / Forgejo / Gogs | `GITEA_TOKEN` |
| GitBucket | `GITBUCKET_TOKEN` |
| Backlog | `BACKLOG_API_KEY` |
| 全サービス共通 | `GFO_TOKEN` |

---

## サービス別 トークン作成手順

### GitHub

**Fine-grained Personal Access Token（推奨）**

1. GitHub にログインし、右上のアイコン → **Settings** を開く
2. 左メニュー下部 **Developer settings** → **Personal access tokens** → **Fine-grained tokens** に進む
3. **Generate new token** をクリック
4. Token name、Expiration（有効期限）を設定
5. **Repository access** で対象リポジトリを選択
6. 必要な権限を付与:

   **Repository permissions:**

   | 権限 | アクセスレベル | 用途 |
   |------|---------------|------|
   | Contents | `Read and write` | `gfo repo`（ファイル操作）、`gfo release`（アセット） |
   | Issues | `Read and write` | `gfo issue` を使う場合 |
   | Pull requests | `Read and write` | `gfo pr` を使う場合 |
   | Metadata | `Read-only` | 自動付与 |
   | Commit statuses | `Read and write` | `gfo status` を使う場合 |
   | Webhooks | `Read and write` | `gfo webhook` を使う場合 |
   | Administration | `Read and write` | `gfo branch-protect`、`gfo repo delete` を使う場合 |
   | Secrets | `Read and write` | `gfo secret` を使う場合 |
   | Variables | `Read and write` | `gfo variable` を使う場合 |

   **Account permissions:**

   | 権限 | アクセスレベル | 用途 |
   |------|---------------|------|
   | Git SSH keys | `Read and write` | `gfo ssh-key` を使う場合 |

   **Organization permissions（組織リポジトリの場合）:**

   | 権限 | アクセスレベル | 用途 |
   |------|---------------|------|
   | Members | `Read-only` | `gfo org` を使う場合 |

7. **Generate token** をクリックしてトークンをコピー

> **注意**: `gfo notification` は Fine-grained Token では使用できません。Classic Token の `notifications` スコープが必要です。

```bash
gfo auth login --host github.com
# Token: ghp_xxxxxxxxxxxxxxxxxxxx
```

**Classic Personal Access Token**

- スコープ: `repo`（フルアクセス）、`notifications`（`gfo notification` 用）、`admin:public_key`（`gfo ssh-key` 用）、`read:org`（`gfo org` 用）
- Settings → Developer settings → Personal access tokens → Tokens (classic) から発行

---

### GitLab

1. GitLab にログインし、右上のアイコン → **Edit profile** を開く
2. 左メニュー **Access Tokens** → **Add new token** をクリック
3. Token name、Expiration date を設定
4. スコープを選択:

   | スコープ | 用途 |
   |----------|------|
   | `api` | 全 gfo コマンド（読み書き両方） |
   | `read_api` | 読み取り専用（`gfo repo`、`gfo pr`、`gfo issue` の一覧・詳細のみ） |
   | `read_repository` | `gfo repo`（リポジトリのクローン・ファイル読み取り） |
   | `write_repository` | `gfo repo`（ファイル作成・更新・プッシュ） |
   | `read_user` | 認証ユーザー情報の取得 |

   > **推奨**: 書き込み操作（PR 作成・Issue 作成など）を行う場合は `api` スコープを選択してください。`api` は他のすべてのスコープを包含します。

5. **Create personal access token** をクリック

```bash
gfo auth login --host gitlab.com
# Token: glpat-xxxxxxxxxxxxxxxxxxxx
```

セルフホスト GitLab の場合:

```bash
gfo auth login --host gitlab.example.com
```

---

### Bitbucket Cloud

> **注意**: App Password は 2026 年 6 月に廃止予定です。Scoped API Token を使用してください。

**Scoped API Token の発行手順**

1. Bitbucket にログインし、右上のアイコン → **Settings** を開く
2. 左メニュー **Personal Bitbucket settings** の **Scoped API tokens** → **Create token** をクリック
3. Token label を設定
4. 必要なスコープを選択:
   | スコープ | 用途 |
   |---------|------|
   | `read:repository:bitbucket` | `gfo repo`（リポジトリ一覧・詳細・ファイル読み取り） |
   | `write:repository:bitbucket` | `gfo repo`（ファイル作成・更新） |
   | `admin:repository:bitbucket` | `gfo branch-protect` を使う場合 |
   | `read:pullrequest:bitbucket` | `gfo pr`（一覧・詳細） |
   | `write:pullrequest:bitbucket` | `gfo pr`（作成・マージ・クローズ） |
   | `read:issue:bitbucket` | `gfo issue`（一覧・詳細、Issue Tracker 使用時） |
   | `write:issue:bitbucket` | `gfo issue`（作成・状態変更、Issue Tracker 使用時） |
   | `read:pipeline:bitbucket` | `gfo secret` / `gfo variable` の一覧 |
   | `write:pipeline:bitbucket` | `gfo secret` / `gfo variable` の更新 |
   | `admin:pipeline:bitbucket` | `gfo secret` / `gfo variable` の作成・削除 |
   | `read:ssh-key:bitbucket` | SSH 鍵一覧（`gfo ssh-key` を使う場合） |
   | `write:ssh-key:bitbucket` | SSH 鍵作成・更新（`gfo ssh-key` を使う場合） |
   | `delete:ssh-key:bitbucket` | SSH 鍵削除（`gfo ssh-key` を使う場合） |
   | `read:workspace:bitbucket` | `gfo org` を使う場合 |
   | `read:user:bitbucket` | 全コマンド共通（認証確認） |

   > **注意**: `write` は `read` を含まないので、読み取りと書き込みの両方が必要な場合は両方のスコープを選択すること。
5. **Create** をクリックしてトークンをコピー

**トークン形式**: `メールアドレス:トークン` のコロン区切りで設定します。

```bash
export BITBUCKET_TOKEN="user@example.com:ATATT-xxxxxxxxxxxxxxxxxxxx"
```

または:

```bash
gfo auth login --host bitbucket.org
# Token: user@example.com:ATATT-xxxxxxxxxxxxxxxxxxxx
```

---

### Azure DevOps

1. Azure DevOps にログインし、右上のユーザーアイコン → **Personal access tokens** を開く
2. **New Token** をクリック
3. Name、Organization（対象の組織）、Expiration を設定
4. **Scopes** で必要な権限を付与:

   | スコープ | アクセスレベル | 用途 |
   |----------|---------------|------|
   | Code | `Read & write` | `gfo repo`、`gfo pr`、`gfo release` |
   | Work Items | `Read & write` | `gfo issue` を使う場合 |
   | Project and Team | `Read` | `gfo org` を使う場合 |

5. **Create** をクリックしてトークンをコピー

```bash
export AZURE_DEVOPS_PAT="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

または:

```bash
gfo auth login --host dev.azure.com
```

> `gfo init` 時に **Organization** と **Project** の入力が必要です。

---

### Backlog

1. Backlog にログインし、右上のアイコン → **個人設定** を開く
2. 左メニュー **API** に進む
3. メモ（任意）を入力し **登録** をクリック
4. 発行された API キーをコピー

> API キーはスコープ制御がなく、アカウントの全権限が付与されます。

```bash
export BACKLOG_API_KEY="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

または:

```bash
gfo auth login --host yourspace.backlog.com
```

> `gfo init` 時に **プロジェクトキー**（例: `MYPROJECT`）の入力が必要です。

---

### Gitea

1. Gitea にログインし、右上のアイコン → **Settings** を開く
2. 左メニュー **Applications** → **Manage Access Tokens** に進む
3. **Token Name** を入力し、必要なスコープのアクセスレベルを設定:

   | スコープ | アクセスレベル | 用途 |
   |----------|---------------|------|
   | `repository` | 読み取り | `gfo repo`（リポジトリ一覧・詳細・ファイル読み取り） |
   | `repository` | 読み取りと書き込み | `gfo repo`（ファイル作成・更新）、`gfo pr`、`gfo release`、`gfo branch-protect` |
   | `issue` | 読み取り | `gfo issue`（一覧・詳細）、`gfo label`、`gfo milestone` |
   | `issue` | 読み取りと書き込み | `gfo issue`（作成・更新・削除）、`gfo label`、`gfo milestone` |
   | `organization` | 読み取り | `gfo org`（組織一覧・詳細・メンバー） |
   | `user` | 読み取り | 認証ユーザー情報の取得 |
   | `user` | 読み取りと書き込み | `gfo ssh-key`（SSH 鍵管理） |
   | `notification` | 読み取り | `gfo notification`（通知一覧） |
   | `notification` | 読み取りと書き込み | `gfo notification`（既読マーク） |

4. **Generate Token** をクリック

```bash
gfo auth login --host gitea.example.com
```

---

### Forgejo

Gitea と同じ手順・スコープ体系です。

1. Forgejo にログインし、右上のアイコン → **Settings** を開く
2. **Applications** → **Manage Access Tokens** に進む
3. Token Name を入力し、**許可の選択** で必要なスコープのアクセスレベルを設定:

   | スコープ | アクセスレベル | 用途 |
   |----------|---------------|------|
   | `repository` | 読み取り | `gfo repo`（リポジトリ一覧・詳細・ファイル読み取り） |
   | `repository` | 読み取りと書き込み | `gfo repo`（ファイル作成・更新）、`gfo pr`、`gfo release`、`gfo branch-protect` |
   | `issue` | 読み取り | `gfo issue`（一覧・詳細）、`gfo label`、`gfo milestone` |
   | `issue` | 読み取りと書き込み | `gfo issue`（作成・更新・削除）、`gfo label`、`gfo milestone` |
   | `organization` | 読み取り | `gfo org`（組織一覧・詳細・メンバー） |
   | `user` | 読み取り | 認証ユーザー情報の取得 |
   | `user` | 読み取りと書き込み | `gfo ssh-key`（SSH 鍵管理） |
   | `notification` | 読み取り | `gfo notification`（通知一覧） |
   | `notification` | 読み取りと書き込み | `gfo notification`（既読マーク） |

4. **Generate Token** をクリック

```bash
gfo auth login --host forgejo.example.com
```

> [Codeberg](https://codeberg.org) は Forgejo ベースのため、同じ手順でトークンを発行できます。

---

### Gogs

1. Gogs にログインし、右上のアイコン → **Your Settings** を開く
2. 左メニュー **Applications** → **Generate New Token** をクリック
3. Token Name を入力し **Generate Token** をクリック

> トークンにスコープ制御はなく、アカウントの全権限が付与されます。
> Gogs は PR・ラベル・マイルストーン・リリース API を未サポートです。

```bash
gfo auth login --host gogs.example.com
```

---

### GitBucket

1. GitBucket にログインし、右上のアイコン → **Account Settings** を開く
2. **Personal access token** → **Generate new token** をクリック
3. Note を入力し **Generate** をクリック

> トークンにスコープ制御はなく、アカウントの全権限が付与されます。
> トークンは Web UI からのみ発行可能です（API 経由での発行は非対応）。

```bash
gfo auth login --host gitbucket.example.com:8080
```

ポート番号込みのホスト名を指定してください。

---

## クロスサービスコマンドでの認証

`gfo issue migrate` や `gfo batch pr create` など、複数のサービスを同時に操作するコマンドでは、`service:owner/repo` 形式でリポジトリを指定します。

各サービスのトークンは、通常のコマンドと同じ優先順位（credentials.toml → 環境変数 → GFO_TOKEN）で解決されます。

```bash
# 例: GitHub から Gitea への Issue 移行
# GitHub のトークンと Gitea のトークンの両方が必要
gfo auth login --host github.com --token ghp_xxxx
gfo auth login --host gitea.example.com --token your-gitea-token

gfo issue migrate --from github:owner/repo --to gitea:gitea.example.com:owner/repo --number 42
```
