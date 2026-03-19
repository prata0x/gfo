# CLI ツール比較表

gfo と各 Git ホスティングサービス向け公式/主要 CLI ツールのコマンド体系を比較する。

## 1. 比較対象

| ツール | 対象サービス | 言語 | リポジトリ / ドキュメント |
|--------|-------------|------|--------------------------|
| **gfo** | GitHub / GitLab / Bitbucket / Azure DevOps / Gitea / Forgejo / Gogs / GitBucket / Backlog | Python | [gfo](https://github.com/prata0x/gfo) |
| **gh** | GitHub | Go | [cli/cli](https://github.com/cli/cli) |
| **glab** | GitLab | Go | [gitlab-org/cli](https://gitlab.com/gitlab-org/cli) |
| **tea** | Gitea | Go | [gitea/tea](https://gitea.com/gitea/tea) |
| **fj** | Forgejo | Rust | [Cyborus/forgejo-cli](https://codeberg.org/Cyborus/forgejo-cli) |

---

## 2. グローバルオプション比較

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| リポジトリ指定 | `--repo` (`URL` or `HOST/OWNER/REPO`) | `--repo` / `-R` (`OWNER/REPO`) | `--repo` / `-R` (`OWNER/REPO`) | `--repo` / `-r` | `--repo` / `-r` (サブコマンドごと) |
| リモート指定 | `--remote` | `---` | `---` | `--remote` | `--remote` / `-R` |
| 出力形式 | `--format` (`table`/`json`/`plain`) | `--json` (フィールド指定) | `--output` (`json`/`text`) | `--output` (`simple`/`table`/`csv`/`tsv`/`yaml`/`json`) | `--style` (`fancy`/`minimal`) |
| フィルタ式 | `--jq` (JSON 出力に適用) | `--jq` (JSON 出力に適用) | `---` | `---` | `---` |
| ページネーション | `--limit` (サブコマンドごと) | `--limit` / `-L` | `--per-page` / `-P`, `--page` / `-p` | `--limit` / `-l`, `--page` / `-p` | `--page` / `-p` (一部コマンド) |
| ブラウザで開く | `browse` (別コマンド) + `--web` | `--web` / `-w` | `--web` / `-w` | `--browse` / `-b` | `browse` サブコマンド (各リソース) |
| バージョン表示 | `--version` | `--version` | `--version` | `--version` | `--version` |
| ヘルプ | `--help` / `-h` | `--help` | `--help` | `--help` / `-h` | `--help` / `-h` |
| ホスト指定 | `--repo` にホストを含める | `--hostname` (auth 時) | `---` | `--login` / `-l` | `--host` / `-H` |

---

## 3. メインコマンド一覧

gfo の 33 トップレベルコマンドを基準に、各ツールの対応コマンド名を一覧する。

**コア操作**

| カテゴリ | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| PR / MR | `pr` | `pr` | `mr` | `pr` | `pr` |
| Issue | `issue` | `issue` | `issue` | `issue` | `issue` |
| リポジトリ | `repo` | `repo` | `repo` | `repo` | `repo` |
| Gist / スニペット | `---` | `gist` | `snippet` | `---` | `---` |
| プロジェクト | `---` | `project` | `---` | `---` | `---` |
| Codespace | `---` | `codespace` | `---` | `---` | `---` |
| インシデント | `---` | `---` | `incident` | `---` | `---` |
| リリース | `release` | `release` | `release` | `release` | `release` |

**ラベル・マイルストーン**

| カテゴリ | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| ラベル | `label` | `label` | `label` | `label` | `repo labels` / `org label` |
| マイルストーン | `milestone` | `---` | `milestone` | `milestone` | `---` |

**Git リソース**

| カテゴリ | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| ブランチ | `branch` | `---` | `---` | `branches` | `---` |
| タグ | `tag` | `---` | `---` | `---` | `tag` |
| コミットステータス | `status` | `---` | `---` | `---` | `---` |

**CI/CD**

| カテゴリ | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| CI | `ci` | `run` / `workflow` | `ci` / `pipeline` | `actions runs` / `workflows` | `actions` (tasks/dispatch) |
| シークレット | `secret` | `secret` | `variable` | `actions secrets` | `actions secrets` |
| 変数 | `variable` | `variable` | `variable` | `actions variables` | `actions variables` |
| キャッシュ | `---` | `cache` | `---` | `---` | `---` |
| スケジュール | `---` | `---` | `schedule` | `---` | `---` |
| Runner | `---` | `---` | `runner` | `---` | `---` |

**検索・通知**

| カテゴリ | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| 検索 | `search` | `search` | `---` | `---` | `---` |
| 通知 | `notification` | `status` | `---` | `notification` | `---` |

**リポジトリ管理**

| カテゴリ | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| ファイル | `file` | `---` | `---` | `---` | `---` |
| Webhook | `webhook` | `---` | `---` | `webhooks` | `---` |
| デプロイキー | `deploy-key` | `repo deploy-key` | `deploy-key` | `---` | `---` |
| コラボレーター | `collaborator` | `---` | `repo members` | `---` | `---` |
| ブランチ保護 | `branch-protect` | `ruleset` | `---` | `branches protect` | `---` |
| タグ保護 | `tag-protect` | `---` | `---` | `---` | `---` |
| Wiki | `wiki` | `---` | `---` | `---` | `wiki` (contents/view/clone/browse) |
| パッケージ | `package` | `---` | `---` | `---` | `---` |

**ユーザー・組織**

| カテゴリ | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| ユーザー | `user` | `---` | `user` | `whoami` | `user` / `whoami` |
| 組織 | `org` | `org` | `---` | `organizations` | `org` |
| SSH キー | `ssh-key` | `ssh-key` | `ssh-key` | `---` | `user key` |
| GPG キー | `gpg-key` | `gpg-key` | `gpg-key` | `---` | `user gpg` |

**ユーティリティ**

| カテゴリ | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| 初期化 | `init` | `---` | `---` | `---` | `---` |
| 認証 | `auth` | `auth` | `auth` | `login` | `auth` (login/logout/add-key/list) |
| ブラウザ | `browse` | `browse` | `---` | `open` | `browse` (各リソースのサブコマンド) |
| API | `api` | `api` | `api` | `---` | `---` |
| 一括操作 | `batch` | `---` | `---` | `---` | `---` |
| スキーマ | `schema` | `---` | `---` | `---` | `---` |
| Issue テンプレート | `issue-template` | `---` | `---` | `---` | `---` |
| 設定 | `---` | `config` | `config` | `---` | `---` |
| エイリアス | `---` | `alias` | `alias` | `---` | `---` |
| 拡張 | `---` | `extension` | `---` | `---` | `---` |
| 補完 | `---` | `completion` | `completion` | `---` | `completion` |
| トークン管理 | `---` | `---` | `token` | `---` | `---` |
| チェンジログ | `---` | `---` | `changelog` | `---` | `---` |

---

## 4. サブコマンド・オプション詳細比較

### 4.1 PR / MR

#### サブコマンド対応表

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| list | `pr list` | `pr list` | `mr list` | `pr list` | `pr search` |
| create | `pr create` | `pr create` | `mr create` | `pr create` | `pr create` |
| view | `pr view` | `pr view` | `mr view` | `pr view` | `pr view` |
| edit | `pr edit` | `pr edit` | `mr update` | `pr edit` | `pr edit` (title/body/comment/labels) |
| delete | `---` | `---` | `mr delete` | `---` | `---` |
| close | `pr close` | `pr close` | `mr close` | `pr close` | `pr close` (`--with-msg`) |
| reopen | `pr reopen` | `pr reopen` | `mr reopen` | `pr reopen` | `---` |
| merge | `pr merge` | `pr merge` | `mr merge` | `pr merge` | `pr merge` |
| checkout | `pr checkout` | `pr checkout` | `mr checkout` | `pr checkout` | `pr checkout` |
| diff | `pr diff` | `pr diff` | `mr diff` | `---` | `pr view diff` |
| checks | `pr checks` | `pr checks` | `---` | `---` | `pr status` |
| rebase | `---` | `---` | `mr rebase` | `---` | `---` |
| files | `pr files` | `---` | `---` | `---` | `pr view files` |
| commits | `pr commits` | `---` | `---` | `---` | `pr view commits` |
| labels | `---` | `---` | `---` | `---` | `pr view labels` |
| ready | `pr ready` | `pr ready` | `---` | `---` | `---` |
| update-branch | `pr update-branch` | `pr update-branch` | `---` | `---` | `---` |
| review | `pr review` (list/create/dismiss) | `pr review` | `mr approve` / `mr revoke` | `pr approve`/`reject` | `---` |
| comment | `pr comment` (list/create/edit/delete) | `pr comment` | `mr note` | `comment` (独立コマンド) | `pr comment` / `pr edit comment` |
| reviewers | `pr reviewers` (list/add/remove) | `---` | `mr approvers` | `---` | `---` |
| subscribe | `---` | `---` | `mr subscribe` / `unsubscribe` | `---` | `---` |
| todo | `---` | `---` | `mr todo` | `---` | `---` |
| issues | `---` | `---` | `mr issues` | `---` | `---` |
| lock / unlock | `---` | `pr lock` / `pr unlock` | `---` | `---` | `---` |
| revert | `---` | `pr revert` | `---` | `---` | `---` |
| status | `---` | `pr status` | `---` | `---` | `pr status` (`--wait`) |
| browse | `---` | `---` | `---` | `---` | `pr browse` |

#### オプション比較: pr list / search

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| 状態 | `--state` | `--state` | `--closed` / `--merged` / `--all` | `--state` | `--state` / `-s` |
| 件数上限 | `--limit` | `--limit` / `-L` | `--per-page` / `-P`, `--page` / `-p` | `--limit` / `--page` | `---` |
| 作者 | `---` | `--author` / `-A` | `--author` | `---` | `--creator` / `-c` |
| 担当者 | `---` | `--assignee` / `-a` | `--assignee` / `-a` | `---` | `--assignee` / `-a` |
| ラベル | `---` | `--label` / `-l` | `--label` / `-l`, `--not-label` | `---` | `--labels` / `-l` |
| ベースブランチ | `---` | `--base` / `-B` | `--target-branch` / `-t` | `---` | `---` |
| ヘッドブランチ | `---` | `--head` / `-H` | `--source-branch` / `-s` | `---` | `---` |
| マイルストーン | `---` | `---` (`--search` 経由) | `--milestone` / `-m` | `---` | `---` |
| 検索クエリ | `---` | `--search` / `-S` | `--search` | `---` | 位置引数 (query) |
| ドラフト | `---` | `--draft` / `-d` | `--draft` / `--not-draft` | `---` | `---` |
| レビュアー | `---` | `---` (`--search` 経由) | `--reviewer` / `-r` | `---` | `---` |
| Web で開く | `--web` / `-w` | `--web` / `-w` | `---` | `---` | `---` |

#### オプション比較: pr create

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| タイトル | `--title` | `--title` | `--title` | `--title` | 位置引数 (`WIP:` 接頭辞でドラフト) |
| 本文 | `--body` | `--body` / `--body-file` | `--description` | `--description` | `--body` / `--body-file` |
| ベースブランチ | `--base` | `--base` | `--target-branch` | `--base` | `--base` |
| ヘッドブランチ | `--head` | `--head` | `--source-branch` | `--head` | `--head` |
| ドラフト | `--draft` | `--draft` | `--draft` | `---` | `WIP:` 接頭辞 (タイトル) |
| レビュアー | `--reviewer` | `--reviewer` | `--reviewer` | `---` | `---` |
| 担当者 | `--assignee` | `--assignee` | `--assignee` | `--assignees` | `---` |
| ラベル | `--label` | `--label` | `--label` | `--labels` | `---` |
| マイルストーン | `--milestone` | `--milestone` | `--milestone` | `--milestone` | `---` |
| 期限 | `---` | `---` | `---` | `--deadline` | `---` |
| 自動入力 | `--fill` | `--fill` | `--fill` | `---` | `--autofill` / `-A` |
| プロジェクト | `---` | `--project` | `---` | `---` | `---` |
| Web で作成 | `---` | `--web` | `--web` | `---` | `--web` |
| ソースブランチ削除 | `---` | `---` | `--remove-source-branch` | `---` | `---` |
| スカッシュ | `---` | `---` | `--squash-before-merge` | `---` | `---` |
| ドライラン | `---` | `--dry-run` | `---` | `---` | `---` |
| AGit ワークフロー | `---` | `---` | `---` | `---` | `--agit` |

#### オプション比較: pr merge

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| マージコミット | `--merge` | `--merge` | `---` (デフォルト) | `--style merge` | `--method merge` |
| スカッシュ | `--squash` | `--squash` | `--squash` | `--style squash` | `--method squash` |
| リベース | `--rebase` | `--rebase` | `--rebase` | `--style rebase` | `--method rebase` / `rebase-merge` |
| 自動マージ | `--auto` | `--auto` | `--auto-merge` | `---` | `---` |
| ブランチ削除 | `---` | `--delete-branch` | `--remove-source-branch` | `--delete-branch` | `--delete` / `-d` |
| コミットメッセージ | `---` | `--subject` / `--body` | `--message` / `--squash-message` | `---` | `--title` / `--message` |
| 管理者権限 | `---` | `--admin` | `---` | `---` | `---` |
| 自動マージ解除 | `---` | `--disable-auto` | `---` | `---` | `---` |
| 手動マージ | `---` | `---` | `---` | `---` | `--method manual` |

#### オプション比較: pr edit

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| タイトル | `--title` | `--title` | `--title` | `--title` | `pr edit <id> title` |
| 本文 | `--body` | `--body` | `--description` | `--description` | `pr edit <id> body` |
| ベースブランチ | `--base` | `--base` | `--target-branch` | `---` | `---` |
| ラベル追加/削除 | `---` | `--add-label` / `--remove-label` | `--label` / `--unlabel` | `--add-labels` / `--remove-labels` | `pr edit <id> labels --add` / `--rm` |
| 担当者追加/削除 | `---` | `--add-assignee` / `--remove-assignee` | `--assignee` (接頭辞 `+`/`-`) / `--unassign` | `--add-assignees` | `---` |
| レビュアー追加/削除 | `---` | `--add-reviewer` / `--remove-reviewer` | `--reviewer` (接頭辞 `+`/`-`) | `---` | `---` |
| マイルストーン | `---` | `--milestone` / `--remove-milestone` | `--milestone` | `--milestone` | `---` |
| ドラフト切替 | `---` | `---` | `--draft` / `--ready` | `---` | `---` |
| プロジェクト | `---` | `--add-project` / `--remove-project` | `---` | `---` | `---` |
| Discussion ロック | `---` | `---` | `--lock-discussion` / `--unlock-discussion` | `---` | `---` |
| コメント編集 | `---` | `---` | `---` | `---` | `pr edit <id> comment <idx>` |

#### オプション比較: pr review create

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| 承認 | `--approve` | `--approve` | (mr approve) | `pr approve` | `---` |
| 変更要求 | `--request-changes` | `--request-changes` | `---` | `pr reject` | `---` |
| コメント | `--comment` | `--comment` | `---` | `---` | `---` |
| 本文 | `--body` | `--body` | `---` | `---` | `---` |

---

### 4.2 Issue

#### サブコマンド対応表

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| list | `issue list` | `issue list` | `issue list` | `issue list` | `issue search` |
| create | `issue create` | `issue create` | `issue create` | `issue create` | `issue create` |
| view | `issue view` | `issue view` | `issue view` | `issue view` | `issue view` |
| edit | `issue edit` | `issue edit` | `issue update` | `issue edit` | `issue edit` (title/body/comment/labels) |
| board | `---` | `---` | `issue board` | `---` | `---` |
| close | `issue close` | `issue close` | `issue close` | `issue close` | `issue close` (`--with-msg`) |
| reopen | `issue reopen` | `issue reopen` | `issue reopen` | `issue reopen` | `---` |
| delete | `issue delete` | `issue delete` | `issue delete` | `---` | `---` |
| comment | `issue comment` (list/create/edit/delete) | `issue comment` | `issue note` | `comment` (独立コマンド) | `issue comment` / `issue edit comment` |
| subscribe | `---` | `---` | `issue subscribe` / `unsubscribe` | `---` | `---` |
| pin / unpin | `issue pin` / `issue unpin` | `issue pin` / `unpin` | `---` | `---` | `---` |
| reaction | `issue reaction` (list/add/remove) | `---` | `---` | `---` | `---` |
| depends | `issue depends` (list/add/remove) | `---` | `---` | `---` | `---` |
| timeline | `issue timeline` | `---` | `---` | `---` | `---` |
| time | `issue time` (list/add/delete) | `---` | `issue time-tracking` | `times` (独立コマンド) | `---` |
| migrate | `issue migrate` | `---` | `---` | `---` | `---` |
| lock / unlock | `---` | `issue lock` / `issue unlock` | `---` | `---` | `---` |
| develop | `---` | `issue develop` | `---` | `---` | `---` |
| status | `---` | `issue status` | `---` | `---` | `---` |
| transfer | `---` | `issue transfer` | `---` | `---` | `---` |
| browse | `---` | `---` | `---` | `---` | `issue browse` |
| templates | `---` | `---` | `---` | `---` | `issue templates` |

#### オプション比較: issue list / search

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| 状態 | `--state` | `--state` | `--state` | `--state` | `--state` / `-s` |
| 担当者 | `--assignee` | `--assignee` | `--assignee` | `---` | `--assignee` / `-a` |
| ラベル | `--label` | `--label` | `--label` | `--label` | `--labels` / `-l` |
| 作者 | `---` | `--author` | `--author` | `---` | `--creator` / `-c` |
| マイルストーン | `---` | `--milestone` | `--milestone` | `--milestone` | `---` |
| 件数上限 | `--limit` | `--limit` | `--per-page` / `--page` | `--limit` | `---` |
| 検索クエリ | `---` | `--search` | `--search` / `--in` | `--keyword` | 位置引数 (query) |
| 機密 | `---` | `---` | `--confidential` | `---` | `---` |
| Issue タイプ | `---` | `---` | `--issue-type` (issue/incident/test_case) | `---` | `---` |
| Epic | `---` | `---` | `--epic` | `---` | `---` |
| イテレーション | `---` | `---` | `--iteration` | `---` | `---` |
| メンション | `---` | `--mention` | `---` | `---` | `---` |

#### オプション比較: issue create

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| タイトル | `--title` | `--title` | `--title` | `--title` | 位置引数 |
| 本文 | `--body` | `--body` / `--body-file` | `--description` | `--description` | `--body` / `--body-file` |
| 担当者 | `--assignee` | `--assignee` | `--assignee` | `--assignees` | `---` |
| ラベル | `--label` | `--label` | `--label` | `--labels` | `---` |
| マイルストーン | `---` | `--milestone` | `--milestone` | `--milestone` | `---` |
| プロジェクト | `---` | `--project` | `---` | `---` | `---` |
| タイプ | `--type` | `---` | `---` | `---` | `---` |
| 優先度 | `--priority` | `---` | `---` | `---` | `---` |
| 機密 | `---` | `---` | `--confidential` | `---` | `---` |
| 重み | `---` | `---` | `--weight` | `---` | `---` |
| 期限 | `---` | `---` | `--due-date` (YYYY-MM-DD) | `---` | `---` |
| Epic | `---` | `---` | `--epic` | `---` | `---` |
| 関連 Issue | `---` | `---` | `--linked-issues` | `---` | `---` |
| 関連 MR | `---` | `---` | `--linked-mr` | `---` | `---` |
| Web で作成 | `---` | `--web` | `--web` | `---` | `--web` |
| テンプレート | `---` | `--template` | `---` | `---` | `--template` / `--no-template` |

#### オプション比較: issue edit

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| タイトル | `--title` | `--title` | `--title` | `--title` | `issue edit <id> title` |
| 本文 | `--body` | `--body` | `--description` | `--description` | `issue edit <id> body` |
| 担当者 | `--assignee` | `--add-assignee` / `--remove-assignee` | `--assignee` (接頭辞 `+`/`-`) / `--unassign` | `--add-assignees` | `---` |
| ラベル | `--label` | `--add-label` / `--remove-label` | `--label` / `--unlabel` | `--add-labels` / `--remove-labels` | `issue edit <id> labels --add` / `--rm` |
| マイルストーン | `---` | `--milestone` / `--remove-milestone` | `--milestone` | `--milestone` | `---` |
| 機密 | `---` | `---` | `--confidential` / `--public` | `---` | `---` |
| 重み | `---` | `---` | `--weight` | `---` | `---` |
| 期限 | `---` | `---` | `--due-date` | `---` | `---` |
| Discussion ロック | `---` | `---` | `--lock-discussion` / `--unlock-discussion` | `---` | `---` |
| プロジェクト | `---` | `--add-project` / `--remove-project` | `---` | `---` | `---` |
| コメント編集 | `---` | `---` | `---` | `---` | `issue edit <id> comment <idx>` |

#### オプション比較: issue migrate

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| 移行元 | `--from` | `---` | `---` | `---` | `---` |
| 移行先 | `--to` | `---` | `---` | `---` | `---` |
| Issue 番号 (単一) | `--number` | `---` | `---` | `---` | `---` |
| Issue 番号 (複数) | `--numbers` | `---` | `---` | `---` | `---` |
| 全 Issue | `--all` | `---` | `---` | `---` | `---` |

---

### 4.3 Repo

#### サブコマンド対応表

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| list | `repo list` | `repo list` | `repo list` | `repo list` | `---` |
| create | `repo create` | `repo create` | `repo create` | `repo create` | `repo create` |
| view | `repo view` | `repo view` | `repo view` | `---` | `repo view` / `repo readme` |
| edit | `repo edit` | `repo edit` | `repo update` | `---` | `---` (org edit のみ) |
| clone | `repo clone` | `repo clone` | `repo clone` | `repo clone` | `repo clone` |
| fork | `repo fork` | `repo fork` | `repo fork` | `repo fork` | `repo fork` |
| delete | `repo delete` | `repo delete` | `repo delete` | `repo delete` | `repo delete` |
| archive | `repo archive` | `repo archive` | `repo archive` | `---` | `---` |
| languages | `repo languages` | `---` | `---` | `---` | `---` |
| topics | `repo topics` (list/add/remove/set) | `---` | `---` | `---` | `---` |
| compare | `repo compare` | `---` | `---` | `---` | `---` |
| migrate | `repo migrate` | `---` | `---` | `---` | `repo migrate` |
| mirror | `repo mirror` (list/add/remove/sync) | `---` | `repo mirror` | `---` | `---` |
| transfer | `repo transfer` | `---` | `repo transfer` | `---` | `---` |
| search | `---` | `---` | `repo search` | `---` | `---` |
| contributors | `---` | `---` | `repo contributors` | `---` | `---` |
| star / unstar | `repo star` / `repo unstar` | `---` | `---` | `---` | `repo star` / `repo unstar` |
| browse | `---` | `---` | `---` | `---` | `repo browse` |
| rename | `---` | `repo rename` | `---` | `---` | `---` |
| sync | `---` | `repo sync` | `---` | `---` | `---` |
| unarchive | `---` | `repo unarchive` | `---` | `---` | `---` |
| set-default | `---` | `repo set-default` | `---` | `---` | `---` |
| autolink | `---` | `repo autolink` (list/create/delete/view) | `---` | `---` | `---` |

#### オプション比較: repo list

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| 所有者 | `--owner` | `--owner` | `---` | `---` | `---` |
| 件数上限 | `--limit` | `--limit` / `-L` | `--per-page` / `-P`, `--page` / `-p` | `--limit` / `--page` | `---` |
| アーカイブ | `---` | `--archived` | `--archived` | `---` | `---` |
| ソースのみ (フォーク除外) | `---` | `--source` | `---` | `---` | `---` |
| 言語 | `---` | `--language` / `-l` | `---` | `---` | `---` |
| 可視性 | `---` | `--visibility` | `---` | `---` | `---` |

#### オプション比較: repo create

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| 名前 | 位置引数 | 位置引数 | `--name` | 位置引数 | 位置引数 |
| 非公開 | `--private` | `--private` | `--private` | `--private` | `--private` / `-P` |
| 公開 | `---` | `--public` | `--public` | `---` | `---` |
| 内部 | `---` | `---` | `--internal` | `---` | `---` |
| 説明 | `--description` | `--description` | `--description` | `--description` | `--description` / `-d` |
| グループ/所有者 | `--host` | `---` | `--group` | `---` | `---` |
| デフォルトブランチ | `---` | `---` | `--defaultBranch` | `---` | `---` |
| README 初期化 | `---` | `---` | `--readme` | `---` | `---` |
| リモート追加 | `---` | `---` | `---` | `---` | `--remote` |
| プッシュ | `---` | `---` | `---` | `---` | `--push` |
| SSH 使用 | `---` | `---` | `---` | `---` | `--ssh` / `-S` |

#### オプション比較: repo edit

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| 説明 | `--description` | `--description` | `--description` | `---` | `---` |
| 公開/非公開 | `--private` / `--public` | `--visibility` | `---` | `---` | `---` |
| デフォルトブランチ | `--default-branch` | `--default-branch` | `--defaultBranch` | `---` | `---` |
| アーカイブ | `---` | `---` | `--archive` | `---` | `---` |
| ホームページ | `---` | `--homepage` | `---` | `---` | `---` |
| トピック | `---` | `--add-topic` / `--remove-topic` | `---` | `---` | `---` |
| Issues 有効化 | `---` | `--enable-issues` | `---` | `---` | `---` |
| Wiki 有効化 | `---` | `--enable-wiki` | `---` | `---` | `---` |
| Discussions 有効化 | `---` | `--enable-discussions` | `---` | `---` | `---` |
| マージ戦略設定 | `---` | `--enable-merge-commit` / `--enable-squash-merge` / `--enable-rebase-merge` | `---` | `---` | `---` |
| PR マージ後ブランチ削除 | `---` | `--delete-branch-on-merge` | `---` | `---` | `---` |
| テンプレート化 | `---` | `--template` | `---` | `---` | `---` |

#### オプション比較: repo migrate

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| Clone URL | 位置引数 | `---` | `---` | `---` | 位置引数 |
| 名前 | `--name` | `---` | `---` | `---` | 位置引数 |
| 非公開 | `--private` | `---` | `---` | `---` | `--private` / `-P` |
| 説明 | `--description` | `---` | `---` | `---` | `---` |
| ミラー | `--mirror` | `---` | `---` | `---` | `--mirror` / `-m` |
| 認証トークン | `--auth-token` | `---` | `---` | `---` | `--token` (stdin) |
| サービス種別 | `---` | `---` | `---` | `---` | `--service` / `-s` |
| インクルード | `---` | `---` | `---` | `---` | `--include` / `-i` (lfs/wiki/issues/prs/milestones/labels/releases) |
| LFS エンドポイント | `---` | `---` | `---` | `---` | `--lfs-endpoint` / `-L` |

---

### 4.4 Release

#### サブコマンド対応表

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| list | `release list` | `release list` | `release list` | `release list` | `release list` |
| create | `release create` | `release create` | `release create` | `release create` | `release create` |
| view | `release view` | `release view` | `release view` | `---` | `release view` |
| edit | `release edit` | `release edit` | `---` | `release edit` | `release edit` |
| delete | `release delete` | `release delete` | `release delete` | `release delete` | `release delete` |
| asset upload | `release asset upload` | `release upload` | `release upload` | `release attachments create` | `release asset create` |
| asset download | `release asset download` | `release download` | `release download` | `release attachments download` | `release asset download` |
| asset list | `release asset list` | `---` | `---` | `release attachments list` | `---` |
| asset delete | `release asset delete` | `release delete-asset` | `---` | `---` | `release asset delete` |
| browse | `---` | `---` | `---` | `---` | `release browse` |
| verify | `---` | `release verify` / `verify-asset` | `---` | `---` | `---` |

#### オプション比較: release list

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| 件数上限 | `--limit` | `--limit` / `-L` | `---` | `--limit` | `---` |
| プレリリース含む | `---` | `---` | `---` | `---` | `--include-prerelease` / `-p` |
| ドラフト含む | `---` | `---` | `---` | `---` | `--include-draft` / `-d` |

#### オプション比較: release view

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| タグ | 位置引数 | 位置引数 | 位置引数 | `---` | 位置引数 |
| Latest | `--latest` | `---` | `---` | `---` | `---` |
| Web で開く | `--web` / `-w` | `--web` / `-w` | `---` | `---` | `---` |

#### オプション比較: release create

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| タグ | 位置引数 | 位置引数 | `--tag` | `--tag` | `--tag` / `-t` (既存) / `--create-tag` / `-T` (新規作成) |
| タイトル | `--title` | `--title` | `--name` | `--title` | 位置引数 (name) |
| ノート | `--notes` | `--notes` | `--notes` | `--note` | `--body` / `-b` |
| ドラフト | `--draft` | `--draft` | `---` | `--draft` | `--draft` / `-d` |
| プレリリース | `--prerelease` | `--prerelease` | `---` | `--prerelease` | `--prerelease` / `-p` |
| ターゲット ref | `--target` | `--target` | `--ref` | `--target` | `--branch` / `-B` |
| マイルストーン | `---` | `---` | `--milestone` | `---` | `---` |
| ノートファイル | `---` | `--notes-file` | `--notes-file` | `--note-file` | `---` |
| 自動リリースノート | `---` | `--generate-notes` | `---` | `---` | `---` |
| Latest 指定 | `---` | `--latest` | `---` | `---` | `---` |
| Discussion カテゴリ | `---` | `--discussion-category` | `---` | `---` | `---` |
| ファイル添付 | 別途 `asset upload` | 位置引数 | `--assets-links` | `--asset` | `--attach` / `-a` |

#### オプション比較: release edit

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| タイトル | `--title` | `--title` | `---` | `--title` | `--rename` / `-n` |
| ノート | `--notes` | `--notes` | `---` | `--note` | `--body` / `-b` |
| ドラフト切替 | `--draft` / `--no-draft` | `--draft` | `---` | `--draft` | `--draft` / `-d` |
| プレリリース切替 | `--prerelease` / `--no-prerelease` | `--prerelease` | `---` | `--prerelease` | `--prerelease` / `-p` |
| タグ | `---` | `--tag` | `---` | `---` | `--tag` / `-t` |
| Latest 指定 | `---` | `--latest` | `---` | `---` | `---` |
| ターゲット | `---` | `--target` | `---` | `---` | `---` |
| Discussion カテゴリ | `---` | `--discussion-category` | `---` | `---` | `---` |
| ノートファイル | `---` | `--notes-file` | `---` | `---` | `---` |

#### オプション比較: release asset upload

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| タグ | `--tag` | 位置引数 (リリース指定) | 位置引数 | `---` | 位置引数 (release 名) |
| ファイル | 位置引数 | 位置引数 | `--assets-links` | `---` | 位置引数 (path) |
| 名前 | `--name` | `---` | `---` | `---` | 位置引数 (name, 省略可) |

#### オプション比較: release asset download

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| タグ | `--tag` | 位置引数 | 位置引数 | `---` | 位置引数 (release 名) |
| アセット ID | `--asset-id` | `---` | `---` | `---` | `---` |
| アセット名 | `---` | `---` | `---` | `---` | 位置引数 (asset 名) |
| パターン | `--pattern` | `--pattern` | `---` | `---` | `---` |
| 出力先 | `--dir` | `--dir` | `---` | `---` | `--output` / `-o` |

---

### 4.5 Label

#### サブコマンド対応表

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| list | `label list` | `label list` | `label list` | `label list` | `repo labels view` |
| create | `label create` | `label create` | `label create` | `label create` | `repo labels create` |
| edit | `label edit` | `label edit` | `label edit` | `label edit` | `repo labels edit` |
| get | `---` | `---` | `label get` | `---` | `---` |
| delete | `label delete` | `label delete` | `label delete` | `label delete` | `repo labels delete` |
| clone | `label clone` | `label clone` | `---` | `---` | `---` |

> fj はラベルを `repo labels` サブコマンドとして提供。組織ラベルは `org label` で管理。

#### オプション比較: label create

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| 名前 | 位置引数 | 位置引数 | `--name` | 位置引数 | 位置引数 |
| 色 | `--color` (RRGGBB) | `--color` | `--color` | `--color` | 位置引数 (hex) |
| 説明 | `--description` | `--description` | `--description` | `--description` | `--description` / `-d` |
| 優先度 | `---` | `---` | `--priority` / `-p` | `---` | `---` |
| 排他ラベル | `---` | `---` | `---` | `---` | `--exclusive` / `-e` |
| アーカイブ | `---` | `---` | `---` | `---` | `--archived` / `-a` |

#### オプション比較: label edit

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| リネーム | `--new-name` | `--name` | `--new-name` / `-n` | `--name` | `--name` / `-n` |
| 色 | `--color` | `--color` | `--color` / `-c` | `--color` | `--color` / `-c` |
| 説明 | `--description` | `--description` | `--description` / `-d` | `--description` | `--description` / `-d` |
| 優先度 | `---` | `---` | `--priority` / `-p` | `---` | `---` |
| 排他ラベル | `---` | `---` | `---` | `---` | `--exclusive` / `-e` |
| アーカイブ | `---` | `---` | `---` | `---` | `--archived` / `-a` |

#### オプション比較: label clone

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| コピー元 | `--from` | 位置引数 | `---` | `---` | `---` |
| 上書き | `--overwrite` | `--force` | `---` | `---` | `---` |

---

### 4.6 Milestone

#### サブコマンド対応表

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| list | `milestone list` | `---` | `milestone list` | `milestone list` | `---` |
| create | `milestone create` | `---` | `milestone create` | `milestone create` | `---` |
| view | `milestone view` | `---` | `milestone get` | `---` | `---` |
| edit | `milestone edit` | `---` | `milestone edit` | `---` | `---` |
| close | `milestone close` | `---` | `---` | `milestone close` | `---` |
| reopen | `milestone reopen` | `---` | `---` | `milestone reopen` | `---` |
| delete | `milestone delete` | `---` | `milestone delete` | `milestone delete` | `---` |

#### オプション比較: milestone create

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| タイトル | 位置引数 | `---` | `--title` | `--title` | `---` |
| 説明 | `--description` | `---` | `--description` | `--description` | `---` |
| 期限 | `--due` (YYYY-MM-DD) | `---` | `--due-date` | `--deadline` / `-D` | `---` |

#### オプション比較: milestone edit

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| タイトル | `--title` | `---` | `--title` | `---` | `---` |
| 説明 | `--description` | `---` | `--description` | `---` | `---` |
| 期限 | `--due` | `---` | `--due-date` | `---` | `---` |
| 開始日 | `---` | `---` | `--start-date` | `---` | `---` |
| 状態 | `--state` | `---` | `--state` (activate/close) | `---` | `---` |

---

### 4.7 Branch / Tag / Status

#### Branch サブコマンド対応表

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| list | `branch list` | `---` | `---` | `branches list` | `---` |
| create | `branch create` | `---` | `---` | `---` | `---` |
| delete | `branch delete` | `---` | `---` | `---` | `---` |

> gfo の `branch create` は `--ref` でベースを指定。

#### Tag サブコマンド対応表

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| list | `tag list` | `---` | `---` | `---` | `tag list` |
| create | `tag create` | `---` | `---` | `---` | `tag create` |
| view | `---` | `---` | `---` | `---` | `tag view` |
| delete | `tag delete` | `---` | `---` | `---` | `tag delete` |

> gfo の `tag create` は `--ref` でベースを、`--message` でアノテーションを指定。
> fj の `tag create` は `--body` / `-b` でメッセージを、`--branch` / `-B` でターゲットブランチを指定。

#### Status サブコマンド対応表

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| list | `status list` | `---` | `---` | `---` | `---` |
| create | `status create` | `---` | `---` | `---` | `---` |

#### オプション比較: status create

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| リファレンス | 位置引数 | `---` | `---` | `---` | `---` |
| 状態 | `--state` (success/failure/pending/error) | `---` | `---` | `---` | `---` |
| コンテキスト | `--context` | `---` | `---` | `---` | `---` |
| 説明 | `--description` | `---` | `---` | `---` | `---` |
| URL | `--url` | `---` | `---` | `---` | `---` |

---

### 4.8 CI

#### サブコマンド対応表

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| list | `ci list` | `run list` | `ci list` | `---` | `actions tasks` |
| view | `ci view` | `run view` | `ci view` | `---` | `---` |
| trigger | `ci trigger` | `workflow run` | `ci trigger` | `---` | `actions dispatch` |
| retry | `ci retry` | `run rerun` | `ci retry` | `---` | `---` |
| cancel | `ci cancel` | `run cancel` | `ci cancel` | `---` | `---` |
| logs | `ci logs` | `run view --log` | `ci trace` | `---` | `---` |
| download | `---` | `run download` | `---` | `---` | `---` |
| delete | `---` | `run delete` | `---` | `---` | `---` |
| watch | `---` | `run watch` | `---` | `---` | `---` |
| workflow list | `---` | `workflow list` | `---` | `actions workflows` | `---` |
| workflow enable/disable | `---` | `workflow enable` / `disable` | `---` | `---` | `---` |
| run (新規作成) | `---` | `---` | `ci run` | `---` | `---` |
| lint | `---` | `---` | `ci lint` | `---` | `---` |
| status | `---` | `---` | `ci status` | `---` | `---` |
| get | `---` | `---` | `ci get` | `---` | `---` |
| delete | `---` | `run delete` | `ci delete` | `---` | `---` |

#### オプション比較: ci trigger / actions dispatch

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| リファレンス | `--ref` | `--ref` / `-r` | `--ref` | `---` | 位置引数 (ref) |
| ワークフロー | `--workflow` / `-w` | 位置引数 (workflow ID/name) | `---` | `---` | 位置引数 (name) |
| 入力パラメータ | `--input` / `-i` (KEY=VALUE) | `--field` / `-F` / `--raw-field` / `-f` | `--variables` | `---` | `--inputs` / `-I` (KEY=VALUE) |
| JSON 入力 | `---` | `--json` (stdin) | `---` | `---` | `---` |

#### オプション比較: ci logs

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| 実行 ID | 位置引数 | 位置引数 | 位置引数 | `---` | `---` |
| ジョブ指定 | `--job` / `-j` | `--job` | 位置引数 (job ID/name) | `---` | `---` |
| 失敗ステップのみ | `---` | `--log-failed` | `---` | `---` | `---` |

---

### 4.9 Secret / Variable

#### Secret サブコマンド対応表

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| list | `secret list` | `secret list` | `variable list` (type filter) | `actions secrets list` | `actions secrets list` |
| set | `secret set` | `secret set` | `variable set` (masked) | `actions secrets add` | `actions secrets create` |
| delete | `secret delete` | `secret delete` | `variable delete` | `actions secrets delete` | `actions secrets delete` |

#### オプション比較: secret set / create

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| 名前 | 位置引数 | 位置引数 | 位置引数 | `---` | 位置引数 |
| 値 | `--value` | `--body` / stdin | `--value` | `---` | 位置引数 |
| 環境変数から | `--env-var` | `---` | `---` | `---` | `---` |
| ファイルから | `--file` | `--env-file` (dotenv 形式) | `---` | `---` | `---` |
| スコープ | `---` | `--env` (環境) / `--org` (組織) / `--user` (ユーザー) | `---` | `---` | `---` |
| 可視性 | `---` | `--visibility` (組織用: all/private/selected) | `---` | `---` | `---` |
| アプリ指定 | `---` | `--app` (actions/codespaces/dependabot) | `---` | `---` | `---` |

#### Variable サブコマンド対応表

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| list | `variable list` | `variable list` | `variable list` | `actions variables list` | `actions variables list` |
| set | `variable set` | `variable set` | `variable set` | `actions variables add` | `actions variables create` |
| get | `variable get` | `variable get` | `variable get` | `---` | `---` |
| delete | `variable delete` | `variable delete` | `variable delete` | `actions variables delete` | `actions variables delete` |
| update | `---` | `---` | `variable update` | `---` | `---` |
| export | `---` | `---` | `variable export` | `---` | `---` |

---

### 4.10 Search

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| repos | `search repos` | `search repos` | `---` | `---` | `---` |
| issues | `search issues` | `search issues` | `---` | `---` | `---` |
| prs | `search prs` | `search prs` | `---` | `---` | `---` |
| commits | `search commits` | `search commits` | `---` | `---` | `---` |
| code | `---` | `search code` | `---` | `---` | `---` |

---

### 4.11 Wiki

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| list | `wiki list` | `---` | `---` | `---` | `wiki contents` |
| view | `wiki view` | `---` | `---` | `---` | `wiki view` |
| create | `wiki create` | `---` | `---` | `---` | `---` |
| edit | `wiki edit` | `---` | `---` | `---` | `---` |
| delete | `wiki delete` | `---` | `---` | `---` | `---` |
| revisions | `wiki revisions` | `---` | `---` | `---` | `---` |
| clone | `---` | `---` | `---` | `---` | `wiki clone` |
| browse | `---` | `---` | `---` | `---` | `wiki browse` |

---

### 4.12 Notification

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| list | `notification list` | `status` | `---` | `notifications list` | `---` |
| read | `notification read` | `---` | `---` | `notifications read` | `---` |
| mark-unread | `---` | `---` | `---` | `notifications unread` | `---` |
| pin / unpin | `---` | `---` | `---` | `notifications pin` / `unpin` | `---` |

#### オプション比較: notification list

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| 未読のみ | `--unread-only` | `---` | `---` | `---` | `---` |
| 件数上限 | `--limit` | `---` | `---` | `---` | `---` |

#### オプション比較: notification read

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| 全件既読 | `--all` | `---` | `---` | `---` | `---` |

---

### 4.13 Org

#### User サブコマンド対応表

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| whoami | `user whoami` | `---` | `---` | `whoami` (独立コマンド) | `whoami` / `user view` |
| search | `---` | `---` | `---` | `---` | `user search` |
| browse | `---` | `---` | `---` | `---` | `user browse` |
| follow / unfollow | `---` | `---` | `---` | `---` | `user follow` / `user unfollow` |
| block / unblock | `---` | `---` | `---` | `---` | `user block` / `user unblock` |
| followers / following | `---` | `---` | `---` | `---` | `user followers` / `user following` |
| repos | `---` | `---` | `---` | `---` | `user repos` |
| orgs | `---` | `---` | `---` | `---` | `user orgs` |
| activity | `---` | `---` | `---` | `---` | `user activity` |
| edit | `---` | `---` | `---` | `---` | `user edit` (bio/name/pronouns/location/email/website) |
| events | `---` | `---` | `user events` | `---` | `---` |

#### Org サブコマンド対応表

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| list | `org list` | `org list` | `---` | `organizations list` | `org list` |
| view | `org view` | `---` | `---` | `---` | `org view` |
| create | `org create` | `---` | `---` | `organizations create` | `org create` |
| edit | `---` | `---` | `---` | `---` | `org edit` |
| members | `org members` | `org list` (members) | `---` | `---` | `org members` |
| repos | `org repos` | `repo list --owner` | `---` | `---` | `org repo list` / `org repo create` |
| activity | `---` | `---` | `---` | `---` | `org activity` |
| visibility | `---` | `---` | `---` | `---` | `org visibility` |
| teams | `---` | `---` | `---` | `---` | `org team` (list/create/edit/delete/view/member/repo) |
| labels | `---` | `---` | `---` | `---` | `org label` (list/add/edit/rm) |
| delete | `org delete` | `---` | `---` | `organizations delete` | `---` |

---

### 4.14 SSH-Key / GPG-Key

#### SSH-Key サブコマンド対応表

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| list | `ssh-key list` | `ssh-key list` | `ssh-key list` | `---` | `user key list` |
| create | `ssh-key create` | `ssh-key add` | `ssh-key add` | `---` | `user key upload` |
| view | `---` | `---` | `---` | `---` | `user key view` |
| delete | `ssh-key delete` | `ssh-key delete` | `ssh-key delete` | `---` | `user key delete` |

#### GPG-Key サブコマンド対応表

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| list | `gpg-key list` | `gpg-key list` | `gpg-key list` | `---` | `user gpg list` |
| create | `gpg-key create` | `gpg-key add` | `gpg-key add` | `---` | `user gpg upload` |
| view | `---` | `---` | `---` | `---` | `user gpg view` |
| delete | `gpg-key delete` | `gpg-key delete` | `gpg-key delete` | `---` | `user gpg delete` |
| get | `---` | `---` | `gpg-key get` | `---` | `---` |
| verify | `---` | `---` | `---` | `---` | `user gpg verify` |

> fj は SSH キーを `user key`、GPG キーを `user gpg` サブコマンドとして提供。`user key upload` は `--title` / `--force` / `--read-only` オプションをサポート。

---

### 4.15 Auth

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| login | `auth login` | `auth login` | `auth login` | `login` | `auth login` (OAuth) |
| add-key | `---` | `---` | `---` | `---` | `auth add-key` (トークン認証) |
| list | `---` | `---` | `---` | `---` | `auth list` |
| status | `auth status` | `auth status` | `auth status` | `---` | `---` |
| switch | `auth switch` | `auth switch` | `---` | `---` | `---` |
| logout | `auth logout` | `auth logout` | `auth logout` | `logout` (独立コマンド) | `auth logout` |
| use-ssh | `---` | `---` | `---` | `---` | `auth use-ssh` |
| token | `---` | `auth token` | `---` | `---` | `---` |
| refresh | `---` | `auth refresh` | `---` | `---` | `---` |
| setup-git | `---` | `auth setup-git` | `---` | `---` | `---` |
| configure-docker | `---` | `---` | `auth configure-docker` | `---` | `---` |

#### オプション比較: auth login

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| ホスト | `--host` | `--hostname` | `---` | `---` | `--host` / `-H` (グローバル) |
| トークン | `--token` | `--with-token` (stdin) | `--token` / `-t` | `--token` / `-t` | `auth add-key` で設定 |
| アカウント | `--account` | `---` | `---` | `---` | `---` |
| スコープ | `---` | `--scopes` | `---` | `---` | `---` |
| Web 認証 | `---` | `--web` | `---` | `---` | `auth login` (デフォルトで OAuth) |
| Git プロトコル | `---` | `--git-protocol` (ssh/https) | `---` | `---` | `---` |

---

### 4.16 File / Webhook / Deploy-Key / Collaborator

#### File サブコマンド対応表

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| get | `file get` | `---` | `---` | `---` | `---` |
| put | `file put` | `---` | `---` | `---` | `---` |
| delete | `file delete` | `---` | `---` | `---` | `---` |

#### Webhook サブコマンド対応表

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| list | `webhook list` | `---` | `---` | `webhooks list` | `---` |
| create | `webhook create` | `---` | `---` | `webhooks create` | `---` |
| delete | `webhook delete` | `---` | `---` | `webhooks delete` | `---` |
| test | `webhook test` | `---` | `---` | `---` | `---` |

#### オプション比較: webhook create

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| URL | `--url` | `---` | `---` | `---` | `---` |
| イベント | `--event` (複数指定可) | `---` | `---` | `---` | `---` |
| シークレット | `--secret` | `---` | `---` | `---` | `---` |

#### Deploy-Key サブコマンド対応表

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| list | `deploy-key list` | `repo deploy-key list` | `deploy-key list` | `---` | `---` |
| create | `deploy-key create` | `repo deploy-key add` | `deploy-key add` | `---` | `---` |
| delete | `deploy-key delete` | `repo deploy-key delete` | `deploy-key delete` | `---` | `---` |
| get | `---` | `---` | `deploy-key get` | `---` | `---` |

> gh は `repo deploy-key`、glab は `deploy-key`（トップレベル）としてデプロイキーを提供。

#### Collaborator サブコマンド対応表

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| list | `collaborator list` | `---` | `---` | `---` | `---` |
| add | `collaborator add` | `---` | `---` | `---` | `---` |
| remove | `collaborator remove` | `---` | `---` | `---` | `---` |

---

### 4.17 Branch-Protect / Tag-Protect

#### Branch-Protect サブコマンド対応表

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| list | `branch-protect list` | `ruleset list` | `---` | `---` | `---` |
| view | `branch-protect view` | `ruleset view` | `---` | `---` | `---` |
| set | `branch-protect set` | `---` | `---` | `branches protect` | `---` |
| remove | `branch-protect remove` | `---` | `---` | `branches unprotect` | `---` |
| check | `---` | `ruleset check` | `---` | `---` | `---` |

> gh は従来のブランチ保護に代わり `ruleset` コマンドを提供。Ruleset はブランチ・タグ両方のルールを管理する。

#### オプション比較: branch-protect set

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| レビュー必須数 | `--require-reviews N` | `---` | `---` | `---` | `---` |
| ステータスチェック | `--require-status-checks` | `---` | `---` | `---` | `---` |
| 管理者にも適用 | `--enforce-admins` / `--no-enforce-admins` | `---` | `---` | `---` | `---` |
| Force push 許可 | `--allow-force-push` / `--no-allow-force-push` | `---` | `---` | `---` | `---` |
| ブランチ削除許可 | `--allow-deletions` / `--no-allow-deletions` | `---` | `---` | `---` | `---` |

#### Tag-Protect サブコマンド対応表

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| list | `tag-protect list` | `---` | `---` | `---` | `---` |
| create | `tag-protect create` | `---` | `---` | `---` | `---` |
| delete | `tag-protect delete` | `---` | `---` | `---` | `---` |

---

### 4.18 Package

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| list | `package list` | `---` | `---` | `---` | `---` |
| view | `package view` | `---` | `---` | `---` | `---` |
| delete | `package delete` | `---` | `---` | `---` | `---` |

> gfo の `package list` は `--type` (npm/maven/docker/pypi 等) でフィルタ可能。

---

### 4.19 Browse / API / Batch / Schema / Issue-Template

#### Browse

| ツール | コマンド |
|---|---|
| gfo | `browse` (`--pr N` / `--issue N` / `--settings` / `--print`) |
| gh | `browse` (`--settings` / `--wiki` / `--projects` / `--releases` / `--actions`) |
| glab | `---` (`--web` オプションのみ) |
| tea | `open` |
| fj | 各リソースの `browse` サブコマンド (`repo browse` / `pr browse` / `issue browse` / `release browse` / `wiki browse` / `user browse`) |

#### オプション比較: browse

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| PR を開く | `--pr N` | 位置引数 (パス指定) | `---` | `---` | `---` |
| Issue を開く | `--issue N` | 位置引数 (パス指定) | `---` | `---` | `---` |
| 設定を開く | `--settings` | `--settings` | `---` | `---` | `---` |
| URL 表示のみ | `--print` | `--no-browser` | `---` | `---` | `---` |
| ブランチ指定 | `---` | `--branch` | `---` | `---` | `---` |
| Wiki | `---` | `--wiki` | `---` | `---` | `---` |
| Releases | `---` | `--releases` | `---` | `---` | `---` |
| Actions | `---` | `--actions` | `---` | `---` | `---` |
| Projects | `---` | `--projects` | `---` | `---` | `---` |

#### API

| ツール | コマンド | 説明 |
|---|---|---|
| gfo | `api METHOD PATH` | `--data` / `--header` オプション |
| gh | `api PATH` | `--method` / `--field` / `--header` / `--paginate` / `--jq` / `--template` / `--cache` オプション |
| glab | `api METHOD PATH` | `--method` / `--field` / `--header` / `--paginate` / `--input` オプション |
| tea | `---` | `---` |
| fj | `---` | `---` |

#### Batch

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| pr create | `batch pr create` | `---` | `---` | `---` | `---` |

#### オプション比較: batch pr create

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| 対象リポジトリ | `--repos` (カンマ区切り) | `---` | `---` | `---` | `---` |
| タイトル | `--title` | `---` | `---` | `---` | `---` |
| 本文 | `--body` | `---` | `---` | `---` | `---` |
| ヘッドブランチ | `--head` | `---` | `---` | `---` | `---` |
| ベースブランチ | `--base` | `---` | `---` | `---` | `---` |
| ドラフト | `--draft` | `---` | `---` | `---` | `---` |
| ドライラン | `--dry-run` | `---` | `---` | `---` | `---` |

#### Schema

| ツール | コマンド | 説明 |
|---|---|---|
| gfo | `schema [--list] [COMMAND [SUBCOMMAND]]` | コマンドの JSON Schema 出力（AI 連携用） |
| gh | `---` | `---` |
| glab | `---` | `---` |
| tea | `---` | `---` |
| fj | `---` | `---` |

#### Issue-Template

| ツール | コマンド | 説明 |
|---|---|---|
| gfo | `issue-template list` | Issue テンプレート一覧 |
| gh | `---` | `---` |
| glab | `---` | `---` |
| tea | `---` | `---` |
| fj | `---` | `---` |

---

## 5. コマンド数サマリー

| ツール | トップレベルコマンド | サブコマンド合計（概算） |
|---|---|---|
| gfo | 33 | 170+ |
| gh | 32 | 200+ |
| glab | 40+ | 160+ |
| tea | 20 | 80+ |
| fj | 12 | 100+ |

---

## 6. 設計思想の違い

| 観点 | gfo | gh / glab | tea / fj |
|---|---|---|---|
| **対象サービス** | 9 サービス横断 | 単一サービス専用 | 単一サービス専用 |
| **認証** | 環境変数 / `gfo auth login` | OAuth / トークン | トークン (tea) / OAuth + トークン (fj) |
| **リポジトリ検出** | git remote 自動検出 + `--repo` で直接指定 | git remote から自動検出 | git remote / 設定ファイル (tea) / git remote 自動検出 (fj) |
| **出力形式** | `--format` + `--jq` | `--json` + `--jq` (gh) / `--output` (glab) | `--output` (tea) / `--style` fancy/minimal (fj) |
| **拡張性** | アダプターパターン（新サービス追加が容易） | Extensions (Go) | `---` |
| **コメント/レビュー** | pr/issue サブコマンド | PR コマンドに内包 | `---` |
| **一括操作** | `batch` コマンド | `---` | `---` |
| **Schema 出力** | `schema` コマンド（MCP / AI 連携用） | `---` | `---` |

---

## 7. 設計判断の記録

gfo のコマンド名・オプション名を他ツールと比較検討した結果を記録する（旧 `cli-alignment.md` より統合）。

### 採用した変更

| # | 変更内容 | 理由 |
|---|---|---|
| 1 | `update` → `edit` | gh / tea / fj の 3 ツールが `edit` で一致。`update` は glab のみ |
| 2 | `comment` / `review` を pr/issue サブコマンドに移動 | 他ツールは全て pr/issue 内のサブコマンドとして提供 |
| 3 | `merge --method` → `--merge` / `--squash` / `--rebase` | gh / fj が個別フラグ方式で多数派 |
| 4 | `--web` / `-w` オプション追加 | gh / glab が `--web` で一致。既存 `browse` コマンドと併設 |
| 5 | `pr create` に `--reviewer` / `--assignee` / `--label` / `--milestone` / `--fill` 追加 | gh / glab と同等のオプションを提供 |
| 6 | `release create --target` 追加 | gh / tea が `--target`。多数派に合わせて採用 |
| 7 | `auth logout` 追加 | gh / glab が対応。認証管理の基本機能 |
| 8 | `auth` マルチアカウント対応 | `--account` オプションで同一ホスト複数アカウントをサポート |

### 現状維持とした項目

| 項目 | 現状 | 理由 |
|---|---|---|
| `--format` | `--format` (`table`/`json`/`plain`) | 他ツール間でコンセンサスが弱い。`docker`/`kubectl` 等でも一般的 |
| `pr reviewers` | `reviewers list/add/remove` | glab の `revoke` は承認取り消し（単一アクション）で機能が異なる。gfo は CRUD 管理で上位互換 |
| `ci trigger` | `ci trigger` | glab と一致。gh は別体系 (`workflow run`) |
| `ci logs` | `ci logs` | 3 ツールとも全て異なる形式。`logs` が最も明瞭 |
| `notification` | `notification` | tea / fj / gfo で多数派。gh の `status` が例外 |
| `browse` コマンド | `browse` | `--web` オプション追加と併設で維持 |
