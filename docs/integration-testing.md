# 統合テストガイド

gfo の各 Git ホスティングサービスに対する統合テストの実行手順。

## 概要

| カテゴリ | サービス | 方式 |
|---|---|---|
| セルフホスト | Gitea, Forgejo, Gogs, GitBucket | Docker Compose（自動セットアップ） |
| SaaS | GitHub, GitLab, Bitbucket, Azure DevOps | 無料プラン（手動セットアップ必要） |
| 有料 | Backlog | 条件付きスキップ（アカウント保有者のみ） |

## 前提条件

- Python 3.11 以上
- `pip install -e ".[dev]"` でインストール済み
- セルフホストテスト: Docker Desktop（Docker Compose v2）
- SaaS テスト: 各サービスのアカウントと API トークン

---

## セルフホストテスト（Docker）

セルフホストテストは **完全自動** で実行できる。ユーザーによる事前設定は不要。

### ワンショット実行

```bash
bash tests/integration/run_selfhosted.sh
```

このスクリプトは以下を自動実行する:
1. Docker Compose で 4 サービス（Gitea / Forgejo / Gogs / GitBucket）を起動
2. 各サービスのヘルスチェック待機
3. `setup_services.py` でユーザー作成・トークン生成・テストリポジトリ作成
4. pytest で統合テストを実行
5. Docker コンテナ・ボリュームをクリーンアップ

### 手動実行

```bash
# 1. サービス起動
docker compose -f tests/integration/docker-compose.yml up -d

# 2. 各サービスが healthy になるまで待機
docker compose -f tests/integration/docker-compose.yml ps

# 3. 初期セットアップ（ユーザー・トークン・リポジトリ作成）
python tests/integration/setup_services.py

# 4. テスト実行
pytest tests/integration/ -m selfhosted -v --no-cov

# 5. 特定サービスのみ
pytest tests/integration/test_gitea.py -v --no-cov

# 6. クリーンアップ
docker compose -f tests/integration/docker-compose.yml down -v
```

### ポート割り当て

| サービス | Web UI | SSH |
|---|---|---|
| Gitea | http://localhost:3000 | 2222 |
| Forgejo | http://localhost:3001 | 2223 |
| Gogs | http://localhost:3002 | 2224 |
| GitBucket | http://localhost:3003 | 2225 |

### セットアップで作成されるリソース

`setup_services.py` が以下を自動作成し、`tests/integration/.env` に書き出す:

- 管理者ユーザー: `gfo-admin` / `gfo-test-pass123`
  - GitBucket のみ: `root` / `root`（デフォルト管理者）
- テストリポジトリ: `gfo-integration-test`
- テストブランチ: `gfo-test-branch`（PR テスト用、ファイル追加済み）
- API トークン: サービスごとに生成

---

## SaaS テスト

SaaS テストは **各サービスのアカウント取得・トークン設定が必要**。以下の手順で準備する。

### 全サービス共通の手順

#### Step 1: テスト用リポジトリの作成

各サービスで `gfo-integration-test` という名前のリポジトリを作成する。
**README で初期化**（空リポジトリは不可。初期コミットが必要）。

#### Step 2: テスト用ブランチの作成

PR テストのために `gfo-test-branch` ブランチを作成し、デフォルトブランチから差分を追加する。

```bash
# リポジトリをクローン後
git checkout -b gfo-test-branch
echo "test" > test-branch-file.txt
git add test-branch-file.txt
git commit -m "test: add branch file for integration test"
git push origin gfo-test-branch
```

#### Step 3: 環境変数の設定

```bash
cp tests/integration/.env.example tests/integration/.env
# .env を編集して各トークンを設定
```

#### Step 4: テスト実行

```bash
# 全 SaaS テスト
bash tests/integration/run_saas.sh

# 特定サービスのみ
pytest tests/integration/test_github.py -v --no-cov
```

---

### GitHub

#### リポジトリ作成

1. https://github.com/new でリポジトリ作成
   - Repository name: `gfo-integration-test`
   - **Add a README file** にチェック
2. `gfo-test-branch` ブランチを上記 Step 2 の手順で作成

#### API トークン取得

1. GitHub.com > Settings > Developer settings > Personal access tokens > **Fine-grained tokens**
2. **Generate new token** をクリック
3. Repository access: **All repositories** （`repo create/delete` テストで新規リポジトリへのアクセスが必要）
4. Permissions:
   - Contents: **Read and write**
   - Issues: **Read and write**
   - Pull requests: **Read and write**
   - Administration: **Read and write** （`repo delete` に必要）
   - Metadata: **Read** （必須、自動付与）
5. Generate token してコピー

#### 環境変数

```bash
GFO_TEST_GITHUB_TOKEN=github_pat_xxxxxxxxxxxx
GFO_TEST_GITHUB_OWNER=your-github-username
GFO_TEST_GITHUB_REPO=gfo-integration-test
```

---

### GitLab

#### リポジトリ作成

1. https://gitlab.com/projects/new でプロジェクト作成
   - Project name: `gfo-integration-test`
   - **Initialize repository with a README** にチェック
2. `gfo-test-branch` ブランチを上記 Step 2 の手順で作成

#### API トークン取得

1. GitLab.com > User Settings > Access Tokens
2. **Add new token** をクリック
3. Token name: `gfo-test`
4. Expiration date: 任意（テスト後は削除推奨）
5. Scopes:
   - `api`（全 API 操作）
6. Create personal access token してコピー

#### 環境変数

```bash
GFO_TEST_GITLAB_TOKEN=glpat-xxxxxxxxxxxx
GFO_TEST_GITLAB_OWNER=your-gitlab-username
GFO_TEST_GITLAB_REPO=gfo-integration-test
```

> **注意**: `GFO_TEST_GITLAB_OWNER` には GitLab のユーザー名またはグループ名を設定する。

---

### Bitbucket Cloud

Bitbucket は **release / label / milestone** を API でサポートしていないため、これらのテストはスキップされる。

#### リポジトリ作成

1. https://bitbucket.org/repo/create でリポジトリ作成
   - Repository name: `gfo-integration-test`
   - **Include a README?** → Yes
2. `gfo-test-branch` ブランチを上記 Step 2 の手順で作成

> **Issue トラッカーの有効化**: リポジトリ設定 > Features > Issue tracker を有効にする（Issue テストに必要）。

#### スコープ付き API Token 取得

Bitbucket Cloud は **スコープ付き API Token** を使用する（App Password は 2026 年 6 月に完全廃止）。

1. https://id.atlassian.com/manage-profile/security/api-tokens を開く
2. **Create API token** をクリック
3. Label: `gfo-test`
4. **Scopes** で以下を選択:
   | スコープ | 理由 |
   |---------|------|
   | `read:repository:bitbucket` | リポジトリ情報の読み取り・一覧 |
   | `write:repository:bitbucket` | テスト間でブランチに差分コミットを追加するため（※） |
   | `create:repository:bitbucket` | `repo create` に必要 |
   | `delete:repository:bitbucket` | `repo delete` に必要 |
   | `read:pullrequest:bitbucket` | PR 一覧・取得 |
   | `write:pullrequest:bitbucket` | PR 作成・マージ・クローズ |
   | `read:issue:bitbucket` | Issue 一覧・取得 |
   | `write:issue:bitbucket` | Issue 作成・状態変更 |

   > **※** `write:repository:bitbucket` は gfo 本体の機能には不要。前回テストでの PR マージ後に `gfo-test-branch` と `main` の差分がなくなるため、テスト実行前にマーカーファイルをコミットして差分を作る処理（Bitbucket Src API 経由）に必要。
5. Create してトークンをコピー

#### 環境変数

トークンは **`email:api-token`** 形式で設定する（Basic Auth）。メールアドレスは Atlassian アカウントのログインメールアドレスを使用する。

```bash
GFO_TEST_BITBUCKET_TOKEN=your-email@example.com:ATATT-xxxxxxxxxxxx
GFO_TEST_BITBUCKET_OWNER=your-workspace-slug
GFO_TEST_BITBUCKET_REPO=gfo-integration-test
```

> **注意**: `GFO_TEST_BITBUCKET_OWNER` には Bitbucket のワークスペーススラグを設定する（個人アカウントの場合はユーザー名と同じ）。

---

### Azure DevOps

Azure DevOps は **release / label / milestone** を API でサポートしていないため、これらのテストはスキップされる。Issue は Work Items として扱われる。

#### 組織とプロジェクトの作成

1. https://dev.azure.com で組織を作成（または既存を使用）
2. New project で `gfo-integration-test` プロジェクトを作成
   - Version control: **Git**
   - Work item process: **Agile**（任意）
3. Repos > Initialize（README で初期化）
4. `gfo-test-branch` ブランチを上記 Step 2 の手順で作成

#### API トークン（Personal Access Token）取得

1. Azure DevOps 右上のユーザーアイコン > **Personal access tokens**
2. **New Token** をクリック
3. Name: `gfo-test`
4. Organization: テスト対象の組織を選択
5. Scopes: **Custom defined** を選択
   - Code: **Read, write & manage** （`repo create/delete` に必要; **Read & write** では不可）
   - Work Items: **Read, write & manage** （`issue delete` に必要; **Read & write** では削除不可）
6. Create してトークンをコピー

#### 環境変数

```bash
GFO_TEST_AZURE_DEVOPS_PAT=xxxxxxxxxxxx
GFO_TEST_AZURE_DEVOPS_ORG=your-organization-name
GFO_TEST_AZURE_DEVOPS_PROJECT=gfo-integration-test
GFO_TEST_AZURE_DEVOPS_REPO=gfo-integration-test
```

> **注意**:
> - `GFO_TEST_AZURE_DEVOPS_ORG`: `dev.azure.com/{ORG}` の組織名部分
> - `GFO_TEST_AZURE_DEVOPS_PROJECT`: Azure DevOps プロジェクト名
> - `GFO_TEST_AZURE_DEVOPS_REPO`: リポジトリ名（プロジェクト名と同じことが多い）

---

### Backlog（有料サービス）

Backlog は **有料プランのみ**のため、デフォルトではテストをスキップする。アカウントを持つ場合のみ設定する。

非対応操作: pr merge / release / label / milestone

#### リポジトリ作成

1. Backlog スペースでプロジェクトを作成
2. プロジェクト設定 > Git > リポジトリを追加 > `gfo-integration-test`
3. `gfo-test-branch` ブランチを上記 Step 2 の手順で作成

#### API キー取得

1. 個人設定 > API > **新しいAPIキーを発行**
2. メモ: `gfo-test`
3. 発行してコピー

#### 環境変数

```bash
GFO_TEST_BACKLOG_API_KEY=xxxxxxxxxxxx
GFO_TEST_BACKLOG_HOST=your-space.backlog.com
GFO_TEST_BACKLOG_OWNER=your-project-key
GFO_TEST_BACKLOG_REPO=gfo-integration-test
GFO_TEST_BACKLOG_PROJECT_KEY=YOUR-PROJECT-KEY
```

> **注意**: `GFO_TEST_BACKLOG_OWNER` には Backlog のプロジェクトキー（大文字英字）を設定する。

---

## 環境変数まとめ

`.env.example` を参照。`.env` にコピーして値を設定する。

```bash
cp tests/integration/.env.example tests/integration/.env
```

`.env` は `.gitignore` に含まれるためリポジトリにはコミットされない。

---

## テスト対応マトリクス

| 操作 | GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|---|---|---|---|---|---|---|---|---|---|
| repo view/list | o | o | o | o | o | o | o | o | o |
| label | o | o | skip | skip | o | o | skip | o | skip |
| milestone | o | o | skip | skip | o | o | skip | o | skip |
| issue | o | o | o | o | o | o | o | o | o |
| pr create/list/view | o | o | o | o | o | o | skip | o | o |
| pr merge | o | o | o | o | o | o | skip | o | skip |
| release | o | o | skip | skip | o | o | o | o | skip |

---

## トラブルシューティング

### Docker サービスが起動しない

```bash
# ログ確認
docker compose -f tests/integration/docker-compose.yml logs gitea

# 個別サービスの再起動
docker compose -f tests/integration/docker-compose.yml restart gitea
```

### ポートが既に使用されている

`docker-compose.yml` のポートマッピングを変更し、`setup_services.py` 内のベース URL も合わせて更新する。

### テストがタイムアウトする

`setup_services.py` の `wait_for_health` 関数の `timeout` 引数を増やす（デフォルト 120 秒）。

### SaaS テストで 401 エラー

- トークンのスコープ・権限を再確認する
- Bitbucket は `email:api-token` 形式になっているか確認する
- Azure DevOps のトークンが正しい組織に紐付いているか確認する

### Azure DevOps で PR テストが失敗する

`gfo-test-branch` が `gfo-integration-test` **リポジトリ**（プロジェクトではなく）に存在するか確認する。
Azure DevOps のプロジェクトとリポジトリは別概念のため注意。

### テスト後のリソースが残る

各テスト実行では Issue・PR・Release 等がサービス上に残る。
再実行時に「既に存在する」エラーが出る場合は、サービスの Web UI から手動で削除するか、
テストリポジトリごと削除して再作成する。
