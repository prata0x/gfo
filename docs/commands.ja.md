# コマンドリファレンス

## グローバルオプション

すべてのコマンドで使用できます。

| オプション | 説明 | デフォルト |
|---|---|---|
| `--format {table,json,plain}` | 出力形式 | `table` |
| `--jq EXPRESSION` | JSON 出力に jq フィルタを適用（`--format json` を暗黙有効化） | — |
| `--remote REMOTE` | origin 以外の git remote を使用（未指定時は `origin`、`origin` が存在しない場合は最初に見つかったリモートにフォールバック） | — |
| `--repo REPO` | 対象リポジトリを直接指定（URL または `HOST/OWNER/REPO` 形式）。`--remote` と排他 | — |
| `--account ACCOUNT` | マルチアカウントのトークン解決に使用するアカウント名（`gfo auth login --account` 参照） | — |
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
gfo auth login [--host HOST] [--token TOKEN] [--account ACCOUNT]
```

| オプション | 説明 |
|---|---|
| `--host HOST` | ホスト名（省略時は `gfo init` の設定から自動解決） |
| `--token TOKEN` | トークンを直接指定（省略時は対話入力） |
| `--account ACCOUNT` | アカウント名（デフォルト: `default`）。ホストごとに複数トークンを管理する場合に使用。 |

**例:**

```bash
gfo auth login
gfo auth login --host github.com
gfo auth login --host gitea.example.com --token mytoken123
gfo auth login --host github.com --account work --token ghp_work_token
```

### gfo auth status

設定済みのトークン一覧を表示します（トークン値は非表示）。各ホストのアクティブアカウントは `*` で表示されます。

```
gfo auth status
```

### gfo auth switch

ホストのアクティブアカウントを切り替えます。

```
gfo auth switch ACCOUNT [--host HOST]
```

| オプション | 説明 |
|---|---|
| `ACCOUNT` | 切り替え先のアカウント名 |
| `--host HOST` | ホスト名（省略時は自動解決） |

**例:**

```bash
gfo auth switch work
gfo auth switch work --host github.com
```

### gfo auth logout

保存済みトークンを削除します。

```
gfo auth logout [--host HOST] [--account ACCOUNT]
```

| オプション | 説明 |
|---|---|
| `--host HOST` | ログアウト対象のホスト（省略時は自動解決） |
| `--account ACCOUNT` | 削除するアカウント名（省略時はホストの全アカウントを削除） |

**例:**

```bash
gfo auth logout
gfo auth logout --host github.com
gfo auth logout --host github.com --account work
```

### gfo auth token

現在のホストまたは指定ホストの認証トークンを出力します。

```
gfo auth token [--host HOST]
```

| オプション | 説明 |
|---|---|
| `--host HOST` | ホスト名（省略時は `gfo init` の設定から自動解決） |

```bash
gfo auth token
gfo auth token --host github.com
```

---

## gfo completion

シェル補完スクリプトを生成します。

```
gfo completion {bash,zsh,fish}
```

| オプション | 説明 |
|---|---|
| `bash` | bash 補完を生成 |
| `zsh` | zsh 補完を生成 |
| `fish` | fish 補完を生成 |

**例:**

```bash
# bash
eval "$(gfo completion bash)"

# zsh
gfo completion zsh > "${fpath[1]}/_gfo"

# fish
gfo completion fish > ~/.config/fish/completions/gfo.fish
```

---

## gfo pr

プルリクエスト（Merge Request）を操作します。

> **対応サービス**: GitHub, GitLab, Bitbucket, Azure DevOps, Backlog, Gitea, Forgejo, GitBucket（Gogs は非対応）

### gfo pr list

```
gfo pr list [--state {open,closed,merged,all}] [--limit N] [--author USER] [--label LABEL] [--assignee USER] [--search QUERY] [--base BRANCH] [--head BRANCH] [--draft | --no-draft]
```

| オプション | デフォルト | 説明 |
|---|---|---|
| `--state` / `-s` | `open` | 表示する PR の状態 |
| `--limit` / `-L` | `30` | 取得件数の上限 |
| `--author` / `-A` | — | 作成者でフィルタ |
| `--label` / `-l` | — | ラベルでフィルタ |
| `--assignee` / `-a` | — | 担当者でフィルタ |
| `--search` / `-S` | — | タイトル/説明でフィルタ |
| `--base` / `-B` | — | ベースブランチでフィルタ |
| `--head` / `-H` | — | ヘッドブランチでフィルタ |
| `--draft` / `-d` / `--no-draft` | — | ドラフト状態でフィルタ |
| `--milestone` / `-m` | — | マイルストーンでフィルタ |

```bash
gfo pr list
gfo pr list --state all --limit 50
gfo pr list --author alice --label bug
gfo pr list --base main --draft
```

### gfo pr create

```
gfo pr create [--title TITLE] [--body BODY] [--body-file FILE] [--base BRANCH] [--head BRANCH] [--draft] [--reviewer USER] [--assignee USER] [--label NAME] [--milestone NAME] [--fill]
```

| オプション | 説明 |
|---|---|
| `--title` / `-t` | PR のタイトル（省略時は対話入力） |
| `--body` / `-b` | PR の本文 |
| `--body-file` / `-F` | ファイルから本文を読み込む |
| `--base` / `-B` | マージ先ブランチ（省略時はデフォルトブランチ） |
| `--head` / `-H` | マージ元ブランチ（省略時は現在のブランチ） |
| `--draft` / `-d` | ドラフト PR として作成 |
| `--reviewer` / `-r` | レビュアーのユーザー名（繰り返し可） |
| `--assignee` / `-a` | 担当者のユーザー名（繰り返し可） |
| `--label` / `-l` | ラベル名（繰り返し可） |
| `--milestone` / `-m` | マイルストーン名 |
| `--fill` / `-f` | コミット情報をタイトルとボディに使用 |
| `--web` / `-w` | ブラウザで作成した PR を開く |
| `--dry-run` | 実際に作成せず、作成される内容を表示 |

```bash
gfo pr create --title "Fix login bug" --base main --head feature/fix-login
gfo pr create --title "WIP: new feature" --draft
gfo pr create --fill --reviewer alice --label bug --milestone v1.0
gfo pr create --title "Release" --body-file CHANGELOG.md
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
gfo pr merge NUMBER [--merge | --squash | --rebase] [--delete-branch] [--subject TITLE] [--body BODY] [--auto] [--disable-auto]
```

| オプション | 説明 |
|---|---|
| `--merge` / `-m` | マージコミットを作成（デフォルト） |
| `--squash` / `-s` | スカッシュしてマージ |
| `--rebase` / `-r` | リベースしてマージ |
| `--delete-branch` / `-d` | マージ後にブランチを削除 |
| `--subject` / `-t` | マージコミットのタイトル |
| `--body` / `-b` | マージコミットの本文 |
| `--auto` | 自動マージを有効化（条件を満たしたら自動でマージ） |
| `--disable-auto` | 自動マージを無効化 |

> `--auto` 対応サービス: GitLab, Azure DevOps, Gitea, Forgejo
>
> `--disable-auto` 対応サービス: GitLab, Azure DevOps, Gitea, Forgejo

```bash
gfo pr merge 42
gfo pr merge 42 --squash --delete-branch
gfo pr merge 42 --subject "feat: merge feature X" --body "Detailed description"
gfo pr merge 42 --rebase --auto
gfo pr merge 42 --disable-auto
```

### gfo pr close

```
gfo pr close NUMBER
```

```bash
gfo pr close 42
```

### gfo pr reopen

> Azure DevOps, Backlog, Bitbucket は非対応

```
gfo pr reopen NUMBER
```

```bash
gfo pr reopen 42
```

### gfo pr checkout

```
gfo pr checkout NUMBER
```

PR のブランチをローカルにチェックアウトします。

```bash
gfo pr checkout 42
```

### gfo pr status

自分に関連する PR（作成済み、レビュー依頼、担当）のステータスを表示します。

```
gfo pr status
```

```bash
gfo pr status
```

### gfo pr lock

PR の会話をロックします。

> **対応サービス**: GitHub, GitLab, Gitea

```
gfo pr lock NUMBER [--reason REASON]
```

| オプション | 説明 |
|---|---|
| `--reason` | ロック理由 |

```bash
gfo pr lock 42
gfo pr lock 42 --reason "resolved"
```

### gfo pr unlock

PR の会話ロックを解除します。

> **対応サービス**: GitHub, GitLab, Gitea

```
gfo pr unlock NUMBER
```

```bash
gfo pr unlock 42
```

### gfo pr edit

```
gfo pr edit NUMBER [--title TITLE] [--body BODY] [--base BRANCH] [--add-label LABEL] [--remove-label LABEL] [--add-assignee USER] [--remove-assignee USER] [--milestone NAME]
```

| オプション | 説明 |
|---|---|
| `--title` / `-t` | タイトル |
| `--body` / `-b` | 本文 |
| `--base` / `-B` | ベースブランチ |
| `--add-label` | ラベルを追加（繰り返し可） |
| `--remove-label` | ラベルを削除（繰り返し可） |
| `--add-assignee` | 担当者を追加（繰り返し可） |
| `--remove-assignee` | 担当者を削除（繰り返し可） |
| `--milestone` / `-m` | マイルストーン名 |
| `--draft` / `-d` / `--ready` | ドラフトと公開状態を切り替え |

```bash
gfo pr edit 42 --title "Updated title"
gfo pr edit 42 --base develop
gfo pr edit 42 --add-label bug --add-label urgent --remove-label wip
gfo pr edit 42 --add-assignee alice --milestone v1.0
```

### gfo pr diff

PR の差分を表示します。

> **対応サービス**: GitHub, GitLab, Bitbucket, Gitea, Forgejo

```
gfo pr diff NUMBER
```

```bash
gfo pr diff 42
```

### gfo pr checks

PR に関連する CI チェック・ステータスを表示します。

> **対応サービス**: GitHub, GitLab, Bitbucket, Azure DevOps, Gitea, Forgejo

```
gfo pr checks NUMBER
```

```bash
gfo pr checks 42
```

### gfo pr files

PR で変更されたファイル一覧を表示します。

> **対応サービス**: GitHub, GitLab, Bitbucket, Azure DevOps, Gitea, Forgejo

```
gfo pr files NUMBER
```

```bash
gfo pr files 42
```

### gfo pr commits

PR に含まれるコミット一覧を表示します。

> **対応サービス**: GitHub, GitLab, Bitbucket, Azure DevOps, Gitea, Forgejo

```
gfo pr commits NUMBER
```

```bash
gfo pr commits 42
```

### gfo pr reviewers

PR のレビュアーを管理します。

> **対応サービス**: GitHub, GitLab, Bitbucket（list のみ）, Azure DevOps, Gitea, Forgejo

```
gfo pr reviewers list NUMBER
gfo pr reviewers add NUMBER USERNAME [USERNAME ...]
gfo pr reviewers remove NUMBER USERNAME [USERNAME ...]
```

```bash
gfo pr reviewers list 42
gfo pr reviewers add 42 alice bob
gfo pr reviewers remove 42 alice
```

### gfo pr update-branch

PR のブランチをベースブランチの最新に更新します。

> **対応サービス**: GitHub, GitLab, Gitea, Forgejo

```
gfo pr update-branch NUMBER
```

```bash
gfo pr update-branch 42
```

### gfo pr ready

ドラフト PR を「レビュー準備完了」に変更します。

> **対応サービス**: GitLab, Azure DevOps, Gitea, Forgejo

```
gfo pr ready NUMBER
```

```bash
gfo pr ready 42
```

### gfo pr review

PR のレビューを操作します。

> **対応サービス**: GitHub, GitLab, Bitbucket, Azure DevOps, Gitea, Forgejo

```
gfo pr review list NUMBER
gfo pr review create NUMBER {--approve | --request-changes | --comment} [--body BODY]
gfo pr review dismiss NUMBER REVIEW_ID [--message MESSAGE]
```

`--approve`, `--request-changes`, `--comment` のいずれか 1 つが必須です。

```bash
gfo pr review list 42
gfo pr review create 42 --approve
gfo pr review create 42 --request-changes --body "Please fix the tests"
gfo pr review create 42 --comment --body "Looks interesting, will review more later"
gfo pr review dismiss 42 12345
gfo pr review dismiss 42 12345 --message "Outdated review"
```

### gfo pr subscribe

プルリクエストの通知を購読します。

> **対応サービス**: GitHub, GitLab, Gitea, Forgejo

```
gfo pr subscribe NUMBER
```

```bash
gfo pr subscribe 42
```

### gfo pr unsubscribe

プルリクエストの通知購読を解除します。

> **対応サービス**: GitHub, GitLab, Gitea, Forgejo

```
gfo pr unsubscribe NUMBER
```

```bash
gfo pr unsubscribe 42
```

### gfo pr comment

PR のコメントを管理します。

> **対応サービス**: 全サービス（edit / delete は GitHub, Backlog, Gitea, Forgejo, GitBucket のみ）

```
gfo pr comment list NUMBER [--limit N]
gfo pr comment create NUMBER --body BODY
gfo pr comment edit COMMENT_ID --body BODY
gfo pr comment delete COMMENT_ID
```

```bash
gfo pr comment list 42
gfo pr comment create 42 --body "LGTM!"
gfo pr comment edit 12345 --body "Updated comment"
gfo pr comment delete 12345
```

---

## gfo issue

Issue を操作します。

> **対応サービス**: 全サービス

### gfo issue list

```
gfo issue list [--state {open,closed,all}] [--assignee USER] [--label LABEL] [--author USER] [--milestone NAME] [--search QUERY] [--limit N]
```

| オプション | デフォルト | 説明 |
|---|---|---|
| `--state` / `-s` | `open` | 表示する Issue の状態 |
| `--assignee` / `-a` | — | 担当者でフィルタ |
| `--label` / `-l` | — | ラベルでフィルタ |
| `--author` / `-A` | — | 作成者でフィルタ |
| `--milestone` / `-m` | — | マイルストーンでフィルタ |
| `--search` / `-S` | — | タイトル/説明でフィルタ |
| `--limit` / `-L` | `30` | 取得件数の上限 |

```bash
gfo issue list
gfo issue list --state all --assignee alice --limit 100
gfo issue list --author bob --milestone v1.0
gfo issue list --search "login bug"
```

### gfo issue create

```
gfo issue create --title TITLE [--body BODY] [--body-file FILE] [--assignee USER] [--label LABEL] [--milestone NAME] [--type TYPE] [--priority N]
```

| オプション | 必須 | 説明 |
|---|---|---|
| `--title` / `-t` | **必須** | Issue のタイトル |
| `--body` / `-b` | — | Issue の本文 |
| `--body-file` / `-F` | — | ファイルから本文を読み込む |
| `--assignee` / `-a` | — | 担当者 |
| `--label` / `-l` | — | ラベル |
| `--milestone` / `-m` | — | マイルストーン名 |
| `--type` | — | Issue タイプ（Azure DevOps: `Task`, `Bug` など） |
| `--priority` | — | 優先度（Backlog など数値で指定するサービス向け） |
| `--due-date` | — | 期限（YYYY-MM-DD 形式、対応サービスのみ） |
| `--template` | — | Issue テンプレート名 |
| `--web` / `-w` | — | ブラウザで作成した Issue を開く |

```bash
gfo issue create --title "Bug: login fails"
gfo issue create --title "Feature request" --body "Details..." --label enhancement --milestone v1.0
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

### gfo issue reopen

> Bitbucket, GitBucket, Backlog は非対応

```
gfo issue reopen NUMBER
```

```bash
gfo issue reopen 10
```

### gfo issue delete

> GitHub / Gogs は非対応

```
gfo issue delete NUMBER
```

```bash
gfo issue delete 10
```

### gfo issue lock

Issue の会話をロックします。

> **対応サービス**: GitHub, GitLab, Gitea

```
gfo issue lock NUMBER [--reason REASON]
```

| オプション | 説明 |
|---|---|
| `--reason` | ロック理由 |

```bash
gfo issue lock 10
gfo issue lock 10 --reason "resolved"
```

### gfo issue unlock

Issue の会話ロックを解除します。

> **対応サービス**: GitHub, GitLab, Gitea

```
gfo issue unlock NUMBER
```

```bash
gfo issue unlock 10
```

### gfo issue subscribe

Issue の通知を購読します。

> **対応サービス**: GitHub, GitLab, Gitea, Forgejo

```
gfo issue subscribe NUMBER
```

```bash
gfo issue subscribe 10
```

### gfo issue unsubscribe

Issue の通知購読を解除します。

> **対応サービス**: GitHub, GitLab, Gitea, Forgejo

```
gfo issue unsubscribe NUMBER
```

```bash
gfo issue unsubscribe 10
```

### gfo issue status

現在のユーザーに関連する Issue のサマリーを表示します（作成した Issue・アサインされた Issue）。

```
gfo issue status
```

```bash
gfo issue status
```

### gfo issue develop

Issue の開発用ブランチを作成します。

```
gfo issue develop NUMBER [--name BRANCH] [--base BRANCH]
```

| オプション | 説明 |
|---|---|
| `--name` / `-n` | ブランチ名（デフォルト: `issue-{number}-{slug}`） |
| `--base` / `-B` | ベースブランチ（デフォルト: デフォルトブランチ） |

```bash
gfo issue develop 10
gfo issue develop 10 --name feature/fix-login --base develop
```

### gfo issue edit

> GitBucket は非対応

```
gfo issue edit NUMBER [--title TITLE] [--body BODY] [--assignee USER] [--label LABEL] [--add-label LABEL] [--remove-label LABEL] [--add-assignee USER] [--remove-assignee USER] [--milestone NAME]
```

| オプション | 説明 |
|---|---|
| `--title` / `-t` | タイトル |
| `--body` / `-b` | 本文 |
| `--assignee` / `-a` | 担当者（置換） |
| `--label` / `-l` | ラベル（置換） |
| `--add-label` | ラベルを追加（繰り返し可） |
| `--remove-label` | ラベルを削除（繰り返し可） |
| `--add-assignee` | 担当者を追加（繰り返し可） |
| `--remove-assignee` | 担当者を削除（繰り返し可） |
| `--milestone` / `-m` | マイルストーン名 |
| `--due-date` | 期限（YYYY-MM-DD 形式、空文字で解除） |

```bash
gfo issue edit 10 --title "New title" --assignee bob
gfo issue edit 10 --add-label bug --remove-label wontfix --milestone v2.0
```

### gfo issue comment

Issue のコメントを管理します。

> **対応サービス**: 全サービス（edit / delete は GitHub, Backlog, Gitea, Forgejo, GitBucket のみ）

```
gfo issue comment list NUMBER [--limit N]
gfo issue comment create NUMBER --body BODY
gfo issue comment edit COMMENT_ID --body BODY
gfo issue comment delete COMMENT_ID
```

```bash
gfo issue comment list 10
gfo issue comment create 10 --body "v1.2.3 で再現しました"
gfo issue comment edit 12345 --body "Updated comment"
gfo issue comment delete 12345
```

### gfo issue reaction

Issue のリアクション（絵文字）を管理します。

> **対応サービス**: GitHub, GitLab, Gitea, Forgejo

```
gfo issue reaction list NUMBER
gfo issue reaction add NUMBER REACTION
gfo issue reaction remove NUMBER REACTION
```

| 引数 | 説明 |
|---|---|
| `NUMBER` | Issue 番号 |
| `REACTION` | リアクション名（例: `+1`, `-1`, `laugh`, `hooray`, `confused`, `heart`, `rocket`, `eyes`） |

```bash
gfo issue reaction list 10
gfo issue reaction add 10 +1
gfo issue reaction remove 10 heart
```

### gfo issue depends

Issue の依存関係を管理します。

> **対応サービス**: GitLab, Azure DevOps, Gitea, Forgejo

```
gfo issue depends list NUMBER
gfo issue depends add NUMBER DEPENDENCY
gfo issue depends remove NUMBER DEPENDENCY
```

| 引数 | 説明 |
|---|---|
| `NUMBER` | Issue 番号 |
| `DEPENDENCY` | 依存先の Issue 番号 |

```bash
gfo issue depends list 10
gfo issue depends add 10 5
gfo issue depends remove 10 5
```

### gfo issue timeline

Issue のタイムライン（イベント履歴）を表示します。

> **対応サービス**: GitHub, GitLab, Azure DevOps, Gitea, Forgejo

```
gfo issue timeline NUMBER [--limit N]
```

```bash
gfo issue timeline 10
gfo issue timeline 10 --limit 50
```

### gfo issue pin / unpin

Issue をピン留め / ピン留め解除します。

> **対応サービス**: GitHub, Gitea, Forgejo

```
gfo issue pin NUMBER
gfo issue unpin NUMBER
```

```bash
gfo issue pin 10
gfo issue unpin 10
```

### gfo issue time

Issue のタイムトラッキング（作業時間記録）を管理します。

> **対応サービス**: GitLab, Azure DevOps, Backlog, Gitea, Forgejo

```
gfo issue time list NUMBER
gfo issue time add NUMBER DURATION
gfo issue time delete NUMBER ENTRY_ID
```

| 引数 | 説明 |
|---|---|
| `NUMBER` | Issue 番号 |
| `DURATION` | 作業時間（例: `1h30m`, `2h`, `45m`） |
| `ENTRY_ID` | 削除するタイムエントリの ID |

```bash
gfo issue time list 10
gfo issue time add 10 1h30m
gfo issue time delete 10 42
```

### gfo issue migrate

異なるサービス間で Issue を移行します。ラベルの自動同期、コメントの移行にも対応。gfo のキラー機能。

> **対応サービス**: GitHub, GitLab, Bitbucket（部分）, Azure DevOps（部分）, Backlog（部分）, Gitea, Forgejo

```
gfo issue migrate --from SERVICE_SPEC --to SERVICE_SPEC {--number N | --numbers N,N,... | --all}
```

| オプション | 説明 |
|---|---|
| `--from` | 移行元リポジトリ（`service:owner/repo` 形式） |
| `--to` | 移行先リポジトリ（`service:host:owner/repo` 形式） |
| `--number N` | 移行する Issue 番号（単一） |
| `--numbers N,N,...` | 移行する Issue 番号（カンマ区切り） |
| `--all` | 全 Issue を移行 |

#### サービス指定文字列（SERVICE_SPEC）

`service:owner/repo` または `service:host:owner/repo` 形式でリポジトリを指定。

| 形式 | 例 |
|---|---|
| SaaS（デフォルトホスト） | `github:owner/repo`, `gitlab:owner/repo` |
| セルフホスト（host 必須） | `gitea:gitea.example.com:owner/repo` |
| SaaS カスタムホスト | `github:gh.example.com:owner/repo` |
| Azure DevOps | `azure-devops:org/project/repo` |
| Backlog | `backlog:team.backlog.com:PROJECT/repo` |

```bash
# GitHub → Gitea に Issue #42 を移行
gfo issue migrate --from github:owner/repo --to gitea:gitea.example.com:owner/repo --number 42

# 複数 Issue を移行
gfo issue migrate --from github:owner/repo --to gitlab:owner/repo --numbers 1,2,3

# 全 Issue を移行
gfo issue migrate --from github:owner/repo --to gitea:gitea.example.com:owner/repo --all
```

---

## gfo repo

リポジトリを操作します。

> **対応サービス**: 全サービス

### gfo repo list

```
gfo repo list [--owner OWNER] [--archived] [--visibility public|private|internal] [--limit N]
```

| オプション | 説明 |
|---|---|
| `--owner OWNER` | リポジトリオーナーでフィルタ |
| `--archived` | アーカイブ済みリポジトリのみ表示 |
| `--visibility` / `-V` | 可視性でフィルタ（`public`, `private`, `internal`） |
| `--limit N` | 最大取得件数（デフォルト: 30） |

```bash
gfo repo list
gfo repo list --owner myorg --limit 50
gfo repo list --visibility private
```

### gfo repo create

```
gfo repo create NAME (--private | --public) [--description DESC] [--host HOST]
```

```bash
gfo repo create my-new-repo --private --description "My project"
gfo repo create my-new-repo --public --host gitea.example.com
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

現在のリポジトリを削除します。`--yes` / `-y` を指定しない場合は確認プロンプトが表示されます。

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

### gfo repo edit

リポジトリの設定を編集します。

> **対応サービス**: GitHub, GitLab, Bitbucket, Azure DevOps, Gitea, Forgejo

```
gfo repo edit [--name NAME] [--description TEXT] [--private | --public] [--default-branch BRANCH] [--allow-merge-commit | --no-allow-merge-commit] [--allow-squash-merge | --no-allow-squash-merge] [--allow-rebase-merge | --no-allow-rebase-merge] [--delete-branch-on-merge | --no-delete-branch-on-merge]
```

| オプション | 説明 |
|---|---|
| `--name NAME` | リポジトリをリネーム |
| `--description TEXT` | リポジトリの説明 |
| `--private` | リポジトリを非公開に設定 |
| `--public` | リポジトリを公開に設定 |
| `--default-branch BRANCH` | デフォルトブランチを変更 |
| `--allow-merge-commit` / `--no-allow-merge-commit` | マージコミットの許可/禁止 |
| `--allow-squash-merge` / `--no-allow-squash-merge` | スカッシュマージの許可/禁止 |
| `--allow-rebase-merge` / `--no-allow-rebase-merge` | リベースマージの許可/禁止 |
| `--delete-branch-on-merge` / `--no-delete-branch-on-merge` | マージ後のブランチ自動削除の有効/無効 |

```bash
gfo repo edit --name new-repo-name
gfo repo edit --description "Updated description" --private
gfo repo edit --allow-squash-merge --no-allow-merge-commit --delete-branch-on-merge
```

### gfo repo contributors

リポジトリの貢献者一覧を表示します。

> **対応サービス**: GitHub, GitLab, Gitea, Forgejo

```
gfo repo contributors [--limit N]
```

```bash
gfo repo contributors
gfo repo contributors --limit 10
```

### gfo repo archive

リポジトリをアーカイブします。

> **対応サービス**: GitHub, GitLab, Azure DevOps, Gitea, Forgejo

```
gfo repo archive [--yes]
```

| オプション | 説明 |
|---|---|
| `--yes` / `-y` | 確認プロンプトをスキップ |

### gfo repo unarchive

リポジトリのアーカイブを解除します。

> **対応サービス**: GitHub, GitLab, Azure DevOps, Gitea, Forgejo

```
gfo repo unarchive
```

```bash
gfo repo unarchive
```

### gfo repo languages

リポジトリの言語統計を表示します。

> **対応サービス**: GitHub, GitLab, Gitea, Forgejo

```
gfo repo languages
```

### gfo repo topics

リポジトリのトピックを管理します。

> **対応サービス**: GitHub, GitLab, Gitea, Forgejo

```
gfo repo topics list
gfo repo topics add <topic>
gfo repo topics remove <topic>
gfo repo topics set <topic> [<topic> ...]
```

### gfo repo compare

2 つのブランチまたはコミットを比較します。

> **対応サービス**: GitHub, GitLab, Bitbucket, Azure DevOps, Gitea, Forgejo

```
gfo repo compare <base>...<head>
gfo repo compare <base>..<head>
```

### gfo repo migrate

外部リポジトリをインポート（移行）します。

> **対応サービス**: GitHub, GitLab, Azure DevOps, Gitea, Forgejo

```
gfo repo migrate CLONE_URL --name NAME [--private] [--description DESC] [--mirror] [--auth-token TOKEN]
```

| オプション | 必須 | 説明 |
|---|---|---|
| `CLONE_URL` | **必須** | インポート元リポジトリの clone URL |
| `--name` / `-n` | **必須** | 作成するリポジトリ名 |
| `--private` | — | 非公開リポジトリとして作成 |
| `--description` / `-d` | — | リポジトリの説明 |
| `--mirror` | — | ミラーリポジトリとして作成 |
| `--auth-token` | — | プライベートリポジトリの認証トークン |

```bash
gfo repo migrate https://github.com/other/repo.git --name my-repo
gfo repo migrate https://github.com/other/private-repo.git --name imported --private --auth-token ghp_xxxx
```

### gfo repo mirror

プッシュミラーを管理します。

> **対応サービス**: GitLab, Gitea, Forgejo

```
gfo repo mirror list
gfo repo mirror add URL [--interval INTERVAL]
gfo repo mirror remove MIRROR_ID
gfo repo mirror sync
```

| オプション | 説明 |
|---|---|
| `URL` | ミラー先リポジトリの URL |
| `--interval` / `-i` | 同期間隔（例: `8h0m0s`） |
| `MIRROR_ID` | ミラーの ID |

```bash
gfo repo mirror list
gfo repo mirror add https://github.com/user/mirror.git
gfo repo mirror remove 1
gfo repo mirror sync        # 全ミラーを同期
```

### gfo repo transfer

リポジトリを別のオーナー（ユーザーまたは組織）に移譲します。

> **対応サービス**: GitHub, GitLab, Gitea, Forgejo

```
gfo repo transfer NEW_OWNER [--yes]
```

| オプション | 説明 |
|---|---|
| `NEW_OWNER` | 移譲先のユーザー名または組織名 |
| `--yes` / `-y` | 確認プロンプトをスキップ |

```bash
gfo repo transfer new-owner
gfo repo transfer my-org --yes
```

### gfo repo sync

フォークを上流リポジトリと同期します。

> **対応サービス**: GitHub, Gitea, Forgejo

```
gfo repo sync [--branch BRANCH]
```

| オプション | 説明 |
|---|---|
| `--branch` / `-b` | 同期するブランチ（省略時はデフォルトブランチ） |

```bash
gfo repo sync
gfo repo sync --branch develop
```

### gfo repo star / unstar

リポジトリにスターを付ける / スターを外します。

> **対応サービス**: GitHub, GitLab, Gitea, Forgejo, Gogs

```
gfo repo star
gfo repo unstar
```

```bash
gfo repo star
gfo repo unstar
```

---

## gfo release

リリースを管理します。

> **対応サービス**: GitHub, GitLab, Gitea, Forgejo, GitBucket

### gfo release list

```
gfo release list [--limit N] [--draft | --no-draft] [--prerelease | --no-prerelease]
```

| オプション | 説明 |
|---|---|
| `--limit N` | 最大取得件数（デフォルト: 30） |
| `--draft` / `-d` / `--no-draft` | ドラフトのみ / ドラフト除外 |
| `--prerelease` / `-p` / `--no-prerelease` | プレリリースのみ / プレリリース除外 |

```bash
gfo release list
gfo release list --draft
gfo release list --no-prerelease
```

### gfo release create

```
gfo release create TAG [--title TITLE] [--notes NOTES] [--notes-file FILE] [--draft] [--prerelease] [--target TARGET] [--generate-notes]
```

| オプション | 説明 |
|---|---|
| `--title` / `-t` | リリースタイトル |
| `--notes` / `-n` | リリースノート |
| `--notes-file` / `-F` | ファイルからリリースノートを読み込み |
| `--draft` / `-d` | ドラフトとして作成 |
| `--prerelease` / `-p` | プレリリースとしてマーク |
| `--target` | ターゲットブランチまたはコミット SHA |
| `--generate-notes` | リリースノートを自動生成（GitHub/GitLab） |

```bash
gfo release create v1.0.0 --title "Version 1.0.0" --notes "Release notes here"
gfo release create v1.0.0 --notes-file CHANGELOG.md
gfo release create v1.1.0-rc1 --prerelease
gfo release create v2.0.0 --draft
gfo release create v1.0.0 --generate-notes
```

### gfo release delete

```
gfo release delete TAG
```

```bash
gfo release delete v0.9.0
```

### gfo release view

> GitBucket は非対応

```
gfo release view TAG [--latest]
```

| オプション | 説明 |
|---|---|
| `TAG` | 表示するリリースのタグ |
| `--latest` | 最新リリースを表示（TAG を省略可能） |

```bash
gfo release view v1.0.0
gfo release view --latest
```

### gfo release edit

> GitBucket は非対応

```
gfo release edit TAG [--title TITLE] [--notes NOTES] [--notes-file FILE] [--draft | --no-draft] [--prerelease | --no-prerelease] [--tag NEW_TAG] [--target TARGET]
```

| オプション | 説明 |
|---|---|
| `--title` / `-t` | リリースタイトル |
| `--notes` / `-n` | リリースノート |
| `--notes-file` / `-F` | ファイルからリリースノートを読み込み |
| `--draft` / `-d` / `--no-draft` | ドラフト状態の切り替え |
| `--prerelease` / `-p` / `--no-prerelease` | プレリリース状態の切り替え |
| `--tag` | 新しいタグ名（GitHub, Gitea, Forgejo） |
| `--target` | ターゲットブランチまたはコミット SHA（GitHub, Gitea, Forgejo） |

```bash
gfo release edit v1.0.0 --title "Version 1.0.0 GA"
gfo release edit v1.0.0 --notes "Updated release notes"
gfo release edit v1.0.0 --no-draft --no-prerelease
gfo release edit v1.0.0 --notes-file CHANGELOG.md
gfo release edit v1.0.0 --tag v1.0.1 --target main
```

### gfo release asset

リリースアセットを管理します。

> **対応サービス**: GitHub, GitLab, Gitea, Forgejo

```
gfo release asset list --tag TAG
gfo release asset upload --tag TAG <file> [--name NAME]
gfo release asset download --tag TAG [--asset-id ID | --pattern GLOB] [--dir DIR]
gfo release asset edit --tag TAG <asset_id> [--name NAME]
gfo release asset delete --tag TAG <asset_id>
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

`--color` / `-c` は `RRGGBB` 形式の 16 進数（`#` なし）で指定します。

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

### gfo label edit

```
gfo label edit NAME [--name NEW_NAME] [--color COLOR] [--description DESC]
```

| オプション | 説明 |
|---|---|
| `--name` / `-n` | 新しいラベル名 |
| `--color` / `-c` | 色（`RRGGBB` 形式、`#` なし） |
| `--description` / `-d` | 説明 |

```bash
gfo label edit bug --color 00ff00
gfo label edit old-name --name new-name
gfo label edit bug --description "Updated description"
```

### gfo label clone

別のリポジトリからラベルをコピーします。

> **対応サービス**: GitHub, GitLab, Gitea, Forgejo, GitBucket（Azure DevOps は部分対応）

```
gfo label clone --from SOURCE [--overwrite]
```

| オプション | 説明 |
|---|---|
| `--from SOURCE` | コピー元リポジトリ（`owner/name` 形式） |
| `--overwrite` | 既存のラベルを上書き |

```bash
gfo label clone --from alice/my-project
gfo label clone --from alice/my-project --overwrite
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

### gfo milestone view

> Backlog は非対応

```
gfo milestone view NUMBER
```

```bash
gfo milestone view 1
```

### gfo milestone edit

```
gfo milestone edit NUMBER [--title TITLE] [--description DESC] [--due DATE] [--state STATE]
```

| オプション | 説明 |
|---|---|
| `--title` / `-t` | タイトル |
| `--description` / `-d` | 説明 |
| `--due` | 期日（`YYYY-MM-DD` 形式） |
| `--state` / `-s` | 状態（`open` / `closed`） |

```bash
gfo milestone edit 1 --title "v2.0 Release"
gfo milestone edit 1 --due 2025-06-30 --state open
```

### gfo milestone close

```
gfo milestone close NUMBER
```

```bash
gfo milestone close 1
```

### gfo milestone reopen

```
gfo milestone reopen NUMBER
```

```bash
gfo milestone reopen 1
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

### gfo branch view

ブランチの詳細を表示します。

```
gfo branch view NAME
```

```bash
gfo branch view main
gfo branch view feature/new-ui
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

### gfo tag view

タグの詳細を表示します。

> **対応サービス**: GitHub, GitLab, Gitea, Forgejo

```
gfo tag view NAME
```

```bash
gfo tag view v1.0.0
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

### gfo webhook edit

Webhook の設定を編集します。

```
gfo webhook edit ID [--url URL] [--event EVENT ...] [--secret SECRET] [--active | --inactive]
```

| オプション | 説明 |
|---|---|
| `--url` | Webhook URL |
| `--event` | イベントタイプ（繰り返し可） |
| `--secret` | Webhook シークレット |
| `--active` | Webhook を有効化 |
| `--inactive` | Webhook を無効化 |

```bash
gfo webhook edit 5 --url https://example.com/new-hook
gfo webhook edit 5 --event push --event pull_request
gfo webhook edit 5 --inactive
```

### gfo webhook test

> **対応サービス**: GitHub, GitLab, Gitea, Forgejo, GitBucket

```
gfo webhook test ID
```

```bash
gfo webhook test 5
```

---

## gfo deploy-key

デプロイキーを管理します。

> **対応サービス**: GitHub, GitLab, Bitbucket, Gitea, Forgejo, Gogs（Azure DevOps / Backlog / GitBucket は非対応）

### gfo deploy-key list

```
gfo deploy-key list [--limit N]
```

### gfo deploy-key view

デプロイキーの詳細を表示します。

```
gfo deploy-key view ID
```

```bash
gfo deploy-key view 3
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

### gfo ci delete

パイプライン実行を削除します。

```
gfo ci delete ID
```

```bash
gfo ci delete 12345678
```

### gfo ci watch

パイプラインのステータスをリアルタイムで監視します。

```
gfo ci watch ID [--interval N] [--timeout N]
```

| オプション | デフォルト | 説明 |
|---|---|---|
| `--interval` / `-i` | `5` | ポーリング間隔（秒） |
| `--timeout` / `-t` | `1800` | タイムアウト秒数（0 で無制限） |

```bash
gfo ci watch 12345678
gfo ci watch 12345678 --interval 10
gfo ci watch 12345678 --timeout 0  # 無制限
```

### gfo ci download

パイプラインのログをファイルにダウンロードします。

```
gfo ci download ID [--job JOB] [--dir DIR]
```

| オプション | デフォルト | 説明 |
|---|---|---|
| `--job` / `-j` | — | ジョブ名または ID |
| `--dir` | `.` | 出力ディレクトリ |

```bash
gfo ci download 12345678
gfo ci download 12345678 --job build --dir ./logs
```

### gfo ci workflow

CI ワークフローを管理します。

> **対応サービス**: GitHub, Gitea

```
gfo ci workflow list [--limit N]
gfo ci workflow enable ID
gfo ci workflow disable ID
```

```bash
gfo ci workflow list
gfo ci workflow enable ci.yml
gfo ci workflow disable ci.yml
```

### gfo ci artifact

CI アーティファクトを管理します。

> **対応サービス**: GitHub, GitLab, Gitea

```
gfo ci artifact list RUN_ID [--limit N]
gfo ci artifact download RUN_ID ARTIFACT_ID [--dir DIR]
```

| オプション | デフォルト | 説明 |
|---|---|---|
| `--limit` / `-L` | `30` | 取得件数の上限 |
| `--dir` | `.` | 出力ディレクトリ |

```bash
gfo ci artifact list 12345678
gfo ci artifact download 12345678 1 --dir ./artifacts
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

リポジトリ、Issue、PR、コミットを検索します。

> **対応サービス**: GitHub, GitLab, Bitbucket（部分対応）, Azure DevOps（部分対応）, Gitea, Forgejo

### gfo search repos

> **対応サービス**: GitHub, GitLab

```
gfo search repos QUERY [--limit N]
```

```bash
gfo search repos "cli tool" --limit 20
```

### gfo search issues

> **対応サービス**: GitHub, GitLab

```
gfo search issues QUERY [--limit N]
```

```bash
gfo search issues "login bug" --limit 10
```

### gfo search prs

PR を検索します。

> **対応サービス**: GitHub, GitLab, Bitbucket（部分対応）, Azure DevOps, Gitea, Forgejo

```
gfo search prs QUERY [--limit N]
```

```bash
gfo search prs "fix bug" --limit 20
```

### gfo search commits

コミットを検索します。

> **対応サービス**: GitHub, GitLab, Azure DevOps（部分対応）, Gitea（部分対応）, Forgejo（部分対応）

```
gfo search commits QUERY [--limit N]
```

```bash
gfo search commits "refactor auth" --limit 20
```

### gfo search code

リポジトリ内のコードを検索します。

> **対応サービス**: GitHub, GitLab, Azure DevOps

```
gfo search code QUERY [--limit N]
```

```bash
gfo search code "import requests" --limit 20
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

### gfo wiki edit

```
gfo wiki edit ID [--title TITLE] [--content CONTENT]
```

```bash
gfo wiki edit 1 --title "New Title"
```

### gfo wiki delete

```
gfo wiki delete ID
```

```bash
gfo wiki delete 1
```

### gfo wiki revisions

Wiki ページの変更履歴を表示します。

> **対応サービス**: Gitea, Forgejo

```
gfo wiki revisions ID [--limit N]
```

```bash
gfo wiki revisions 1
gfo wiki revisions "Getting-Started" --limit 10
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

### gfo org edit

組織の設定を編集します。

> **対応サービス**: GitHub, GitLab, Gitea, Forgejo, Gogs

```
gfo org edit NAME [--display-name NAME] [--description DESC]
```

| オプション | 説明 |
|---|---|
| `--display-name` | 表示名 |
| `--description` / `-d` | 説明 |

```bash
gfo org edit my-org --display-name "My Organization"
gfo org edit my-org --description "Updated description"
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

### gfo ssh-key view

SSH キーの詳細を表示します。

```
gfo ssh-key view ID
```

```bash
gfo ssh-key view 12345
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
gfo secret list [--limit N] [--org ORG]
```

| オプション | 説明 |
|---|---|
| `--org` | 組織スコープ（組織レベルのシークレットを一覧） |

### gfo secret set

```
gfo secret set NAME {--value VALUE | --env-var ENV_VAR | --file FILE} [--org ORG]
```

| オプション | 説明 |
|---|---|
| `--value VALUE` | シークレット値（平文で渡す） |
| `--env-var ENV_VAR` | 環境変数から値を取得する |
| `--file FILE` | ファイルから値を取得する |
| `--org ORG` | 組織スコープ |

```bash
gfo secret set API_KEY --value "sk-xxxx"
gfo secret set DB_PASSWORD --env-var MY_DB_PASS
gfo secret set CERT --file ./cert.pem
gfo secret set ORG_TOKEN --value "token" --org my-org
```

> GitHub は PyNaCl による暗号化が必要です（`pip install PyNaCl`）。

### gfo secret delete

```
gfo secret delete NAME [--org ORG]
```

| オプション | 説明 |
|---|---|
| `--org` | 組織スコープ |

---

## gfo variable

CI/CD 変数（平文値、読み取り可）を管理します。

> **対応サービス**: GitHub, GitLab, Bitbucket, Gitea, Forgejo

### gfo variable list

```
gfo variable list [--limit N] [--org ORG]
```

| オプション | 説明 |
|---|---|
| `--org` | 組織スコープ（組織レベルの変数を一覧） |

### gfo variable set

```
gfo variable set NAME --value VALUE [--masked] [--org ORG]
```

| オプション | 説明 |
|---|---|
| `--value VALUE` | 変数の値（必須） |
| `--masked` | GitLab の masked 変数として設定する（GitLab のみ有効） |
| `--org ORG` | 組織スコープ |

```bash
gfo variable set NODE_ENV --value "production"
gfo variable set SECRET_KEY --value "abc" --masked   # GitLab のみ
gfo variable set ORG_VAR --value "val" --org my-org
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
gfo variable delete NAME [--org ORG]
```

| オプション | 説明 |
|---|---|
| `--org` | 組織スコープ |

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

---

## gfo api

設定済みサービスに対して直接 API リクエストを送信します。

> **対応サービス**: 全サービス

```
gfo api <METHOD> <PATH> [--data JSON] [--header HEADER]
```

| オプション | 説明 |
|---|---|
| `METHOD` | HTTP メソッド（GET, POST, PUT, PATCH, DELETE） |
| `PATH` | API パス（例: `/repos/owner/repo`） |
| `--data` / `-d` | リクエストボディ（JSON 文字列） |
| `--header` / `-H` | HTTP ヘッダー（複数指定可、形式: `Key: Value`） |

**例:**

```bash
# リポジトリ情報を取得
gfo api GET /repos/owner/repo

# Issue を作成
gfo api POST /repos/owner/repo/issues --data '{"title": "Bug report"}'
```

---

## gfo gpg-key

ユーザーアカウントの GPG 公開鍵を管理します。

> **対応サービス**: GitHub, GitLab, Bitbucket, Gitea, Forgejo

### gfo gpg-key list

```
gfo gpg-key list [--limit N]
```

### gfo gpg-key view

GPG キーの詳細を表示します。

```
gfo gpg-key view ID
```

```bash
gfo gpg-key view 12345
```

### gfo gpg-key create

```
gfo gpg-key create --key ARMORED_PUBLIC_KEY
```

```bash
gfo gpg-key create --key "-----BEGIN PGP PUBLIC KEY BLOCK-----..."
```

### gfo gpg-key delete

```
gfo gpg-key delete ID
```

```bash
gfo gpg-key delete 12345
```

---

## gfo ci trigger

パイプライン / ワークフローを手動でトリガーします。

> **対応サービス**: GitHub, GitLab, Bitbucket, Azure DevOps, Gitea, Forgejo
>
> **注意**: GitHub / Gitea は `--workflow` / `-w` が必須です。

```
gfo ci trigger --ref REF [--workflow WORKFLOW] [--input KEY=VALUE ...]
```

| オプション | 必須 | 説明 |
|---|---|---|
| `--ref` | **必須** | 対象ブランチまたはタグ |
| `--workflow` / `-w` | GitHub/Gitea で必須 | ワークフロー名またはファイル名 |
| `--input` / `-i` | — | 入力パラメータ（`KEY=VALUE` 形式、複数指定可） |

```bash
gfo ci trigger --ref main --workflow ci.yml
gfo ci trigger --ref develop --workflow build.yml --input env=staging --input debug=true
gfo ci trigger --ref main  # GitLab / Bitbucket / Azure DevOps
```

## gfo ci retry

失敗したパイプラインを再実行します。

> **対応サービス**: GitHub, GitLab, Bitbucket, Azure DevOps, Gitea, Forgejo

```
gfo ci retry ID
```

```bash
gfo ci retry 12345678
```

## gfo ci logs

パイプラインのログを取得します。

> **対応サービス**: GitHub, GitLab, Bitbucket, Azure DevOps

```
gfo ci logs ID [--job JOB_ID]
```

| オプション | 説明 |
|---|---|
| `--job` / `-j` | 特定のジョブのログのみ取得（省略時は全ジョブのログを結合） |

```bash
gfo ci logs 12345678
gfo ci logs 12345678 --job 42
```

---

## gfo tag-protect

タグ保護ルールを管理します。

> **対応サービス**: GitHub, GitLab, Gitea, Forgejo

### gfo tag-protect list

```
gfo tag-protect list [--limit N]
```

### gfo tag-protect edit

タグ保護ルールを編集します。

> **対応サービス**: GitLab, Gitea, Forgejo

```
gfo tag-protect edit ID [--pattern PATTERN] [--access-level LEVEL]
```

| オプション | 説明 |
|---|---|
| `--pattern` | タグパターン |
| `--access-level` | アクセスレベル |

```bash
gfo tag-protect edit 1 --pattern "v*"
gfo tag-protect edit 1 --access-level maintainer
```

### gfo tag-protect create

```
gfo tag-protect create PATTERN [--access-level LEVEL]
```

| オプション | 説明 |
|---|---|
| `PATTERN` | 保護対象のタグパターン（例: `v*`） |
| `--access-level` | 作成アクセスレベル（GitLab / Gitea 向け） |

```bash
gfo tag-protect create "v*"
gfo tag-protect create "release-*" --access-level maintainer
```

### gfo tag-protect delete

```
gfo tag-protect delete ID
```

```bash
gfo tag-protect delete 1
```

---

## gfo package

パッケージレジストリのパッケージを管理します。

> **対応サービス**: GitHub, GitLab, Gitea, Forgejo

### gfo package list

```
gfo package list [--type TYPE] [--limit N]
```

| オプション | 説明 |
|---|---|
| `--type` | パッケージタイプでフィルタ（例: `npm`, `maven`, `docker`, `pypi`, `nuget`, `rubygems`） |
| `--limit` / `-L` | 取得件数の上限 |

```bash
gfo package list
gfo package list --type npm --limit 10
```

### gfo package view

```
gfo package view PACKAGE_TYPE NAME [--version VERSION]
```

| オプション | 説明 |
|---|---|
| `PACKAGE_TYPE` | パッケージタイプ（例: `npm`, `maven`, `docker`） |
| `NAME` | パッケージ名 |
| `--version` | 特定バージョンの詳細を表示 |

```bash
gfo package view npm my-package
gfo package view npm my-package --version 1.0.0
```

### gfo package delete

```
gfo package delete PACKAGE_TYPE NAME VERSION [--yes]
```

| オプション | 説明 |
|---|---|
| `PACKAGE_TYPE` | パッケージタイプ（例: `npm`, `maven`, `docker`） |
| `NAME` | パッケージ名 |
| `VERSION` | 削除するバージョン |
| `--yes` / `-y` | 確認プロンプトをスキップ |

```bash
gfo package delete npm my-package 1.0.0
gfo package delete npm my-package 1.0.0 --yes
```

---

## gfo org create / delete

組織の作成・削除を行います。

> **対応サービス**: GitHub, GitLab, Gitea, Forgejo, Gogs（Bitbucket / Azure DevOps は API 不可）

### gfo org create

```
gfo org create NAME [--display-name NAME] [--description DESC]
```

| オプション | 説明 |
|---|---|
| `--display-name` | 表示名 |
| `--description` / `-d` | 説明 |

```bash
gfo org create my-new-org
gfo org create my-org --display-name "My Organization" --description "Team org"
```

### gfo org delete

```
gfo org delete NAME [--yes]
```

| オプション | 説明 |
|---|---|
| `--yes` / `-y` | 確認プロンプトをスキップ |

```bash
gfo org delete old-org
gfo org delete old-org --yes
```

---

## gfo issue-template

Issue テンプレートの一覧を取得します。

> **対応サービス**: GitHub, GitLab, Azure DevOps, Gitea, Forgejo

### gfo issue-template list

```
gfo issue-template list
```

```bash
gfo issue-template list
gfo issue-template list --format json
```

---

## gfo batch

複数リポジトリに対して一括操作を実行します。

### gfo batch pr create

複数リポジトリに対して一括で PR を作成します。サービスをまたいだバッチ操作にも対応。

> **対応サービス**: GitHub, GitLab, Bitbucket, Azure DevOps, Backlog（部分）, Gitea, Forgejo, GitBucket

```
gfo batch pr create --repos SPECS --title TITLE --head BRANCH [options]
```

| オプション | 説明 | デフォルト |
|---|---|---|
| `--repos` | 対象リポジトリ（カンマ区切り、`service:owner/repo` 形式） | （必須） |
| `--title` / `-t` | PR タイトル | （必須） |
| `--body` / `-b` | PR 本文 | `""` |
| `--head` / `-H` | ソースブランチ | （必須） |
| `--base` / `-B` | ターゲットブランチ | `main` |
| `--draft` / `-d` | ドラフト PR として作成 | — |
| `--dry-run` | PR を作成せず検証のみ実行 | — |

リポジトリ指定は `gfo issue migrate` の SERVICE_SPEC と同じ形式。

```bash
# GitHub + Gitea の複数リポジトリに PR 作成
gfo batch pr create \
  --repos github:owner/repo1,gitea:gitea.example.com:owner/repo2 \
  --title "Update dependencies" \
  --body "Bumped all deps" \
  --head update-deps

# ドライランで事前確認
gfo batch pr create --repos github:owner/repo1,github:owner/repo2 --title "Fix" --head hotfix --dry-run
```

---

## gfo config

ローカル設定（`config.toml`）を管理します。

### gfo config get

ドット区切りのキーで設定値を取得します。

```
gfo config get KEY
```

| 引数 | 説明 |
|---|---|
| `KEY` | ドット記法の設定キー（例: `defaults.output`） |

**例:**

```bash
gfo config get defaults.output
gfo config get defaults.host
```

### gfo config set

設定値を保存します。

```
gfo config set KEY VALUE
```

| 引数 | 説明 |
|---|---|
| `KEY` | ドット記法の設定キー（例: `defaults.output`） |
| `VALUE` | 設定する値 |

**例:**

```bash
gfo config set defaults.output json
gfo config set defaults.host github.com

# ドットを含むキーは引用符で囲む
gfo config set hosts."gitlab.example.com".type gitlab
gfo config get hosts."gitlab.example.com".type
```

### gfo config list

全設定値を一覧表示します。

```
gfo config list
```

### gfo config unset

設定値を削除します。

```
gfo config unset KEY
```

| 引数 | 説明 |
|---|---|
| `KEY` | 削除する設定キー（例: `defaults.output`） |

**例:**

```bash
gfo config unset defaults.output
```

### gfo config path

設定ファイルのパスを表示します。

```
gfo config path
```
