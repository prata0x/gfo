# コマンドリファレンス

## グローバルオプション

すべてのコマンドで使用できます。

| オプション | 説明 | デフォルト |
|---|---|---|
| `--format {table,json,plain}` | 出力形式 | `table` |
| `--jq EXPRESSION` | JSON 出力に jq フィルタを適用（`--format json` を暗黙有効化） | — |
| `--version` | バージョンを表示して終了 | — |

---

## gfo init

リポジトリの gfo 設定を初期化します。remote URL からサービスを自動検出し、`git config --local` に保存します。

> **対応サービス**: 全サービス

```
gfo init [--non-interactive] [--type TYPE] [--host HOST] [--api-url URL] [--project-key KEY]
```

| オプション | 必須 | 説明 |
|---|---|---|
| `--non-interactive` | — | 対話プロンプトをスキップ（CI 向け） |
| `--type TYPE` | `--non-interactive` 時必須 | サービス識別子（`github`, `gitlab`, `bitbucket`, `azure-devops`, `gitea`, `forgejo`, `gogs`, `gitbucket`, `backlog`） |
| `--host HOST` | `--non-interactive` 時必須 | ホスト名（例: `github.com`, `gitea.example.com`） |
| `--api-url URL` | — | API ベース URL（省略時は自動構築） |
| `--project-key KEY` | — | プロジェクトキー（Azure DevOps / Backlog） |

**例:**

```bash
# 対話モード（remote URL から自動検出）
gfo init

# 非対話モード（CI 向け）
gfo init --non-interactive --type github --host github.com

# セルフホスト GitLab
gfo init --non-interactive --type gitlab --host gitlab.example.com

# Azure DevOps（organization と project が必要）
gfo init --non-interactive --type azure-devops --host dev.azure.com --project-key MyProject

# Backlog
gfo init --non-interactive --type backlog --host myspace.backlog.com --project-key MYPROJECT
```

---

## gfo auth

認証トークンを管理します。

> **対応サービス**: 全サービス

### gfo auth login

トークンをインタラクティブに入力し `credentials.toml` に保存します。

```
gfo auth login [--host HOST] [--token TOKEN]
```

| オプション | 説明 |
|---|---|
| `--host HOST` | ホスト名（省略時は `gfo init` の設定から自動解決） |
| `--token TOKEN` | トークンを直接指定（省略時は対話入力） |

**例:**

```bash
gfo auth login
gfo auth login --host github.com
gfo auth login --host gitea.example.com --token mytoken123
```

### gfo auth status

設定済みのトークン一覧を表示します（トークン値は非表示）。

```
gfo auth status
```

---

## gfo pr

プルリクエスト（Merge Request）を操作します。

> **対応サービス**: GitHub, GitLab, Bitbucket, Azure DevOps, Backlog, Gitea, Forgejo, GitBucket（Gogs は非対応）

### gfo pr list

```
gfo pr list [--state {open,closed,merged,all}] [--limit N]
```

| オプション | デフォルト | 説明 |
|---|---|---|
| `--state` | `open` | 表示する PR の状態 |
| `--limit` | `30` | 取得件数の上限 |

```bash
gfo pr list
gfo pr list --state all --limit 50
```

### gfo pr create

```
gfo pr create [--title TITLE] [--body BODY] [--base BRANCH] [--head BRANCH] [--draft]
```

| オプション | 説明 |
|---|---|
| `--title` | PR のタイトル（省略時は対話入力） |
| `--body` | PR の本文 |
| `--base` | マージ先ブランチ（省略時はデフォルトブランチ） |
| `--head` | マージ元ブランチ（省略時は現在のブランチ） |
| `--draft` | ドラフト PR として作成 |

```bash
gfo pr create --title "Fix login bug" --base main --head feature/fix-login
gfo pr create --title "WIP: new feature" --draft
```

### gfo pr view

```
gfo pr view NUMBER
```

```bash
gfo pr view 42
```

### gfo pr merge

> Backlog は PR マージ非対応

```
gfo pr merge NUMBER [--method {merge,squash,rebase}]
```

| オプション | デフォルト | 説明 |
|---|---|---|
| `--method` | `merge` | マージ方法 |

```bash
gfo pr merge 42
gfo pr merge 42 --method squash
```

### gfo pr close

```
gfo pr close NUMBER
```

```bash
gfo pr close 42
```

### gfo pr checkout

```
gfo pr checkout NUMBER
```

PR のブランチをローカルにチェックアウトします。

```bash
gfo pr checkout 42
```

### gfo pr update

```
gfo pr update NUMBER [--title TITLE] [--body BODY] [--base BRANCH]
```

```bash
gfo pr update 42 --title "Updated title"
gfo pr update 42 --base develop
```

---

## gfo issue

Issue を操作します。

> **対応サービス**: 全サービス

### gfo issue list

```
gfo issue list [--state {open,closed,all}] [--assignee USER] [--label LABEL] [--limit N]
```

| オプション | デフォルト | 説明 |
|---|---|---|
| `--state` | `open` | 表示する Issue の状態 |
| `--assignee` | — | 担当者でフィルタ |
| `--label` | — | ラベルでフィルタ |
| `--limit` | `30` | 取得件数の上限 |

```bash
gfo issue list
gfo issue list --state all --assignee alice --limit 100
```

### gfo issue create

```
gfo issue create --title TITLE [--body BODY] [--assignee USER] [--label LABEL] [--type TYPE] [--priority N]
```

| オプション | 必須 | 説明 |
|---|---|---|
| `--title` | **必須** | Issue のタイトル |
| `--body` | — | Issue の本文 |
| `--assignee` | — | 担当者 |
| `--label` | — | ラベル |
| `--type` | — | Issue タイプ（Azure DevOps: `Task`, `Bug` など） |
| `--priority` | — | 優先度（Backlog など数値で指定するサービス向け） |

```bash
gfo issue create --title "Bug: login fails"
gfo issue create --title "Feature request" --body "Details..." --label enhancement
```

### gfo issue view

```
gfo issue view NUMBER
```

```bash
gfo issue view 10
```

### gfo issue close

> GitBucket は非対応

```
gfo issue close NUMBER
```

```bash
gfo issue close 10
```

### gfo issue delete

> GitHub / Gogs は非対応

```
gfo issue delete NUMBER
```

```bash
gfo issue delete 10
```

### gfo issue update

> GitBucket は非対応

```
gfo issue update NUMBER [--title TITLE] [--body BODY] [--assignee USER] [--label LABEL]
```

```bash
gfo issue update 10 --title "New title" --assignee bob
```

---

## gfo repo

リポジトリを操作します。

> **対応サービス**: 全サービス

### gfo repo list

```
gfo repo list [--owner OWNER] [--limit N]
```

```bash
gfo repo list
gfo repo list --owner myorg --limit 50
```

### gfo repo create

```
gfo repo create NAME [--private] [--description DESC] [--host HOST]
```

```bash
gfo repo create my-new-repo --private --description "My project"
gfo repo create my-new-repo --host gitea.example.com
```

> **注意**: Azure DevOps と Backlog は事前に `gfo init` で設定が必要です。
> - Azure DevOps: `organization` と `project` を設定してください
> - Backlog: `project_key` を設定してください

### gfo repo clone

```
gfo repo clone REPO [--host HOST] [--project PROJECT]
```

`REPO` は `owner/name` 形式で指定します。

`--project` は Azure DevOps でプロジェクト名を指定する場合に使用します。`gfo init` で設定済みの場合は省略できます。

```bash
gfo repo clone alice/my-project
gfo repo clone alice/my-project --host gitea.example.com
gfo repo clone my-repo --host dev.azure.com --project MyProject
```

### gfo repo view

```
gfo repo view [REPO]
```

`REPO` を省略すると現在のリポジトリを表示します。

```bash
gfo repo view
gfo repo view alice/my-project
```

### gfo repo delete

```
gfo repo delete [--yes]
```

現在のリポジトリを削除します。`--yes` を指定しない場合は確認プロンプトが表示されます。

```bash
gfo repo delete --yes
```

### gfo repo fork

```
gfo repo fork [--org ORG]
```

```bash
gfo repo fork
gfo repo fork --org myorg
```

---

## gfo release

リリースを管理します。

> **対応サービス**: GitHub, GitLab, Gitea, Forgejo, GitBucket

### gfo release list

```
gfo release list [--limit N]
```

```bash
gfo release list
```

### gfo release create

```
gfo release create TAG [--title TITLE] [--notes NOTES] [--draft] [--prerelease]
```

```bash
gfo release create v1.0.0 --title "Version 1.0.0" --notes "Release notes here"
gfo release create v1.1.0-rc1 --prerelease
gfo release create v2.0.0 --draft
```

### gfo release delete

```
gfo release delete TAG
```

```bash
gfo release delete v0.9.0
```

---

## gfo label

ラベルを管理します。

> **対応サービス**: GitHub, GitLab, Gitea, Forgejo, GitBucket

### gfo label list

```
gfo label list
```

### gfo label create

```
gfo label create NAME [--color COLOR] [--description DESC]
```

`--color` は `RRGGBB` 形式の 16 進数（`#` なし）で指定します。

```bash
gfo label create bug --color ff0000 --description "Something is broken"
gfo label create enhancement --color 0075ca
```

### gfo label delete

```
gfo label delete NAME
```

```bash
gfo label delete old-label
```

---

## gfo milestone

マイルストーンを管理します。

> **対応サービス**: GitHub, GitLab, Gitea, Forgejo, GitBucket

### gfo milestone list

```
gfo milestone list
```

### gfo milestone create

```
gfo milestone create TITLE [--description DESC] [--due DATE]
```

`--due` は `YYYY-MM-DD` 形式で指定します。

```bash
gfo milestone create "v1.0 Release" --due 2024-12-31
```

### gfo milestone delete

```
gfo milestone delete NUMBER
```

```bash
gfo milestone delete 3
```

---

## gfo comment

PR または Issue のコメントを操作します。

> **対応サービス**: 全サービス（comment update / delete は GitHub, Backlog, Gitea, Forgejo, GitBucket のみ）

### gfo comment list

```
gfo comment list {pr,issue} NUMBER [--limit N]
```

```bash
gfo comment list pr 42
gfo comment list issue 10 --limit 50
```

### gfo comment create

```
gfo comment create {pr,issue} NUMBER --body BODY
```

```bash
gfo comment create pr 42 --body "LGTM!"
gfo comment create issue 10 --body "I can reproduce this on v1.2.3"
```

### gfo comment update

```
gfo comment update COMMENT_ID --body BODY --on {pr,issue}
```

```bash
gfo comment update 12345 --body "Updated comment" --on pr
```

### gfo comment delete

```
gfo comment delete COMMENT_ID --on {pr,issue}
```

```bash
gfo comment delete 12345 --on issue
```

---

## gfo review

PR のレビューを操作します。

> **対応サービス**: GitHub, GitLab

### gfo review list

```
gfo review list NUMBER
```

```bash
gfo review list 42
```

### gfo review create

```
gfo review create NUMBER {--approve | --request-changes | --comment} [--body BODY]
```

`--approve`, `--request-changes`, `--comment` のいずれか 1 つが必須です。

```bash
gfo review create 42 --approve
gfo review create 42 --request-changes --body "Please fix the tests"
gfo review create 42 --comment --body "Looks interesting, will review more later"
```

---

## gfo branch

ブランチを操作します。

> **対応サービス**: 全サービス（branch create / delete は Gogs 非対応）

### gfo branch list

```
gfo branch list [--limit N]
```

```bash
gfo branch list
```

### gfo branch create

```
gfo branch create NAME --ref REF
```

`--ref` には SHA またはブランチ名を指定します。

```bash
gfo branch create feature/new-ui --ref main
gfo branch create hotfix/v1 --ref abc123def456
```

### gfo branch delete

```
gfo branch delete NAME
```

```bash
gfo branch delete feature/old-ui
```

---

## gfo tag

タグを操作します。

> **対応サービス**: 全サービス（tag create は Gogs / GitBucket 非対応。tag delete は Gogs 非対応）

### gfo tag list

```
gfo tag list [--limit N]
```

### gfo tag create

```
gfo tag create NAME --ref REF [--message MSG]
```

```bash
gfo tag create v1.0.0 --ref main
gfo tag create v1.0.0 --ref main --message "Release v1.0.0"
```

### gfo tag delete

```
gfo tag delete NAME
```

```bash
gfo tag delete v0.9.0-beta
```

---

## gfo status

コミットステータス（CI ステータス）を操作します。

> **対応サービス**: GitHub, GitLab, Gitea, Forgejo

### gfo status list

```
gfo status list REF [--limit N]
```

```bash
gfo status list main
gfo status list abc123def456
```

### gfo status create

```
gfo status create REF --state {success,failure,pending,error} [--context CTX] [--description DESC] [--url URL]
```

```bash
gfo status create main --state success --context "ci/tests" --description "All tests passed"
gfo status create abc123 --state failure --context "ci/lint" --url https://ci.example.com/build/42
```

---

## gfo file

リポジトリ内のファイルを操作します。

> **対応サービス**: GitHub, GitLab, Bitbucket, Azure DevOps, Gitea, Forgejo, Gogs, GitBucket（Backlog は非対応。Gogs は file get のみ対応）

### gfo file get

ファイルの内容を取得します。

```
gfo file get PATH [--ref REF]
```

```bash
gfo file get README.md
gfo file get src/main.py --ref feature/new-ui
```

### gfo file put

ファイルを作成または更新します。標準入力からファイルの内容を受け取ります。

```
gfo file put PATH --message MSG [--branch BRANCH]
```

```bash
echo "Hello" | gfo file put hello.txt --message "Add hello.txt"
cat myfile.py | gfo file put src/myfile.py --message "Update myfile" --branch feature/update
```

### gfo file delete

```
gfo file delete PATH --message MSG [--branch BRANCH]
```

```bash
gfo file delete old-file.txt --message "Remove old-file.txt"
```

---

## gfo webhook

Webhook を管理します。

> **対応サービス**: GitHub, GitLab, Bitbucket, Backlog, Gitea, Forgejo, Gogs, GitBucket（Azure DevOps は非対応）

### gfo webhook list

```
gfo webhook list [--limit N]
```

### gfo webhook create

```
gfo webhook create --url URL --event EVENT [--event EVENT ...] [--secret SECRET]
```

`--event` は複数指定可能です。

```bash
gfo webhook create --url https://example.com/hook --event push --event pull_request
gfo webhook create --url https://example.com/hook --event push --secret mysecret
```

### gfo webhook delete

```
gfo webhook delete ID
```

```bash
gfo webhook delete 5
```

---

## gfo deploy-key

デプロイキーを管理します。

> **対応サービス**: GitHub, GitLab, Bitbucket, Gitea, Forgejo, Gogs（Azure DevOps / Backlog / GitBucket は非対応）

### gfo deploy-key list

```
gfo deploy-key list [--limit N]
```

### gfo deploy-key create

```
gfo deploy-key create --title TITLE --key KEY [--read-write]
```

```bash
gfo deploy-key create --title "CI Server" --key "ssh-rsa AAAA..."
gfo deploy-key create --title "Deploy Bot" --key "ssh-ed25519 AAAA..." --read-write
```

### gfo deploy-key delete

```
gfo deploy-key delete ID
```

```bash
gfo deploy-key delete 3
```

---

## gfo collaborator

コラボレーター（リポジトリメンバー）を管理します。

> **対応サービス**: GitHub, GitLab, Bitbucket, Gitea, Forgejo, Gogs, GitBucket（Azure DevOps / Backlog は非対応。collaborator add / remove は Bitbucket も非対応）

### gfo collaborator list

```
gfo collaborator list [--limit N]
```

### gfo collaborator add

```
gfo collaborator add USERNAME [--permission {read,write,admin}]
```

| オプション | デフォルト | 説明 |
|---|---|---|
| `--permission` | `write` | 付与する権限 |

```bash
gfo collaborator add alice
gfo collaborator add bob --permission admin
```

### gfo collaborator remove

```
gfo collaborator remove USERNAME
```

```bash
gfo collaborator remove alice
```

---

## gfo ci

CI/CD パイプラインのジョブ・ワークフローを操作します。

> **対応サービス**: GitHub, GitLab, Gitea, Forgejo

### gfo ci list

```
gfo ci list [--ref REF] [--limit N]
```

```bash
gfo ci list
gfo ci list --ref main
```

### gfo ci view

```
gfo ci view ID
```

```bash
gfo ci view 12345678
```

### gfo ci cancel

```
gfo ci cancel ID
```

```bash
gfo ci cancel 12345678
```

---

## gfo user

認証ユーザーの情報を表示します。

> **対応サービス**: GitHub, GitLab, Bitbucket, Azure DevOps, Gitea, Forgejo, Gogs, GitBucket（Backlog は非対応）

### gfo user whoami

認証済みユーザーの情報を表示します。

```bash
gfo user whoami
```

---

## gfo search

リポジトリや Issue を検索します。

> **対応サービス**: GitHub, GitLab

### gfo search repos

```
gfo search repos QUERY [--limit N]
```

```bash
gfo search repos "cli tool" --limit 20
```

### gfo search issues

```
gfo search issues QUERY [--limit N]
```

```bash
gfo search issues "login bug" --limit 10
```

---

## gfo wiki

Wiki ページを管理します。

> **対応サービス**: GitLab, Gitea, Forgejo

### gfo wiki list

```
gfo wiki list [--limit N]
```

### gfo wiki view

```
gfo wiki view ID
```

### gfo wiki create

```
gfo wiki create --title TITLE --content CONTENT
```

```bash
gfo wiki create --title "Getting Started" --content "# Getting Started\n\nWelcome!"
```

### gfo wiki update

```
gfo wiki update ID [--title TITLE] [--content CONTENT]
```

```bash
gfo wiki update 1 --title "New Title"
```

### gfo wiki delete

```
gfo wiki delete ID
```

```bash
gfo wiki delete 1
```

---

## gfo browse

リポジトリ・PR・Issue の URL をデフォルトブラウザで開きます。API 呼び出しは発生しません。

> **対応サービス**: 全サービス

```
gfo browse [--pr N | --issue N | --settings] [--print]
```

| オプション | 説明 |
|---|---|
| （なし） | リポジトリトップページを開く |
| `--pr N` | PR #N のページを開く |
| `--issue N` | Issue #N のページを開く |
| `--settings` | リポジトリ設定ページを開く |
| `--print` | ブラウザを開かず URL を標準出力に表示する |

```bash
gfo browse                     # リポジトリトップを開く
gfo browse --pr 42             # PR #42 を開く
gfo browse --issue 7           # Issue #7 を開く
gfo browse --settings          # 設定ページを開く
gfo browse --pr 42 --print     # URL を表示するだけ（ブラウザは開かない）
```

> Backlog は `--issue` / `--settings` 非対応（`NotSupportedError`）

---

## gfo branch-protect

ブランチ保護ルールを管理します。

> **対応サービス**: GitHub, GitLab, Bitbucket, Gitea, Forgejo
>
> **注意**: Bitbucket は強制プッシュと削除の制御のみ対応。レビュー要件（`--require-reviews`）、ステータスチェック（`--require-status-checks`）、管理者への適用（`--enforce-admins`）は非対応。

### gfo branch-protect list

```
gfo branch-protect list [--limit N]
```

### gfo branch-protect view

```
gfo branch-protect view BRANCH
```

### gfo branch-protect set

```
gfo branch-protect set BRANCH [--require-reviews N] [--require-status-checks CHECK...] [--enforce-admins | --no-enforce-admins] [--allow-force-push | --no-allow-force-push] [--allow-deletions | --no-allow-deletions]
```

| オプション | 説明 |
|---|---|
| `--require-reviews N` | 必要なレビュー承認数（0 で無効） |
| `--require-status-checks CHECK...` | 必須ステータスチェック名（複数指定可） |
| `--enforce-admins` / `--no-enforce-admins` | 管理者にも保護を適用するか |
| `--allow-force-push` / `--no-allow-force-push` | 強制プッシュを許可するか |
| `--allow-deletions` / `--no-allow-deletions` | ブランチ削除を許可するか |

```bash
gfo branch-protect set main --require-reviews 2 --no-allow-force-push
```

### gfo branch-protect remove

```
gfo branch-protect remove BRANCH
```

```bash
gfo branch-protect remove main
```

---

## gfo notification

インボックス通知を管理します。

> **対応サービス**: GitHub, GitLab, Gitea, Forgejo, Backlog

### gfo notification list

```
gfo notification list [--unread-only] [--limit N]
```

| オプション | デフォルト | 説明 |
|---|---|---|
| `--unread-only` | false | 未読のみ表示 |
| `--limit N` | 30 | 取得件数の上限 |

```bash
gfo notification list --unread-only
```

### gfo notification read

```
gfo notification read [ID] [--all]
```

| 引数/オプション | 説明 |
|---|---|
| `ID` | 既読にする通知 ID |
| `--all` | すべての通知を既読にする |

```bash
gfo notification read 12345      # 特定の通知を既読にする
gfo notification read --all      # すべて既読にする
```

---

## gfo org

所属する組織（Organization / Group / Workspace）を管理します。

> **対応サービス**: GitHub, GitLab, Bitbucket, Azure DevOps, Gitea, Forgejo, Gogs

### gfo org list

```
gfo org list [--limit N]
```

### gfo org view

```
gfo org view NAME
```

### gfo org members

> Azure DevOps は `org members` 非対応（メンバー管理には Teams を使用）。

```
gfo org members NAME [--limit N]
```

```bash
gfo org members my-org
```

### gfo org repos

```
gfo org repos NAME [--limit N]
```

```bash
gfo org repos my-org --limit 50
```

---

## gfo ssh-key

ユーザーアカウントの SSH 公開鍵を管理します。

> **対応サービス**: GitHub, GitLab, Bitbucket, Gitea, Forgejo, Gogs

### gfo ssh-key list

```
gfo ssh-key list [--limit N]
```

### gfo ssh-key create

```
gfo ssh-key create --title TITLE --key PUBLIC_KEY
```

```bash
gfo ssh-key create --title "My Laptop" --key "ssh-ed25519 AAAA..."
```

### gfo ssh-key delete

```
gfo ssh-key delete ID
```

```bash
gfo ssh-key delete 12345
```

---

## gfo secret

CI/CD シークレット（暗号化済み値、読み取り不可）を管理します。

> **対応サービス**: GitHub, GitLab, Bitbucket, Gitea, Forgejo

### gfo secret list

```
gfo secret list [--limit N]
```

### gfo secret set

```
gfo secret set NAME {--value VALUE | --env-var ENV_VAR | --file FILE}
```

| オプション | 説明 |
|---|---|
| `--value VALUE` | シークレット値（平文で渡す） |
| `--env-var ENV_VAR` | 環境変数から値を取得する |
| `--file FILE` | ファイルから値を取得する |

```bash
gfo secret set API_KEY --value "sk-xxxx"
gfo secret set DB_PASSWORD --env-var MY_DB_PASS
gfo secret set CERT --file ./cert.pem
```

> GitHub は PyNaCl による暗号化が必要です（`pip install PyNaCl`）。

### gfo secret delete

```
gfo secret delete NAME
```

---

## gfo variable

CI/CD 変数（平文値、読み取り可）を管理します。

> **対応サービス**: GitHub, GitLab, Bitbucket, Gitea, Forgejo

### gfo variable list

```
gfo variable list [--limit N]
```

### gfo variable set

```
gfo variable set NAME --value VALUE [--masked]
```

| オプション | 説明 |
|---|---|
| `--value VALUE` | 変数の値（必須） |
| `--masked` | GitLab の masked 変数として設定する（GitLab のみ有効） |

```bash
gfo variable set NODE_ENV --value "production"
gfo variable set SECRET_KEY --value "abc" --masked   # GitLab のみ
```

### gfo variable get

```
gfo variable get NAME
```

```bash
gfo variable get NODE_ENV
```

### gfo variable delete

```
gfo variable delete NAME
```

---

## gfo schema

コマンドの JSON Schema を表示します。AI エージェントがコマンドの入出力をプログラム的に把握するために設計されています。

> **対応サービス**: N/A（メタデータコマンド、API 呼び出しなし）

```
gfo schema [--list] [COMMAND [SUBCOMMAND]]
```

| オプション / 引数 | 説明 |
|---|---|
| `--list` | 全コマンド一覧を説明付きで表示 |
| `COMMAND` | 指定コマンド配下の全サブコマンドのスキーマを表示 |
| `COMMAND SUBCOMMAND` | 特定コマンドの入力・出力スキーマを表示 |
| （なし） | `--list` と同じ |

`--format` の指定に関わらず、出力は常に JSON です。

**例:**

```bash
# 全コマンド一覧
gfo schema --list

# 特定コマンドのスキーマ
gfo schema pr list

# pr 配下の全サブコマンドのスキーマ
gfo schema pr

# jq フィルタを適用
gfo schema pr list --jq '.output'
```

**出力形式（`gfo schema pr list`）:**

```json
{
  "command": "pr list",
  "input": {
    "type": "object",
    "properties": {
      "state": {"type": "string", "enum": ["open","closed","merged","all"], "default": "open"},
      "limit": {"type": "integer", "default": 30}
    }
  },
  "output": {
    "type": "array",
    "items": {
      "type": "object",
      "properties": {
        "number": {"type": "integer"},
        "title": {"type": "string"},
        ...
      },
      "required": ["number", "title", ...]
    }
  }
}
```
