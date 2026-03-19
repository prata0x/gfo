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
| リポジトリ指定 | `--repo` (`URL` or `HOST/OWNER/REPO`) | `--repo` / `-R` (`OWNER/REPO`) | `--repo` / `-R` (`OWNER/REPO`) | `--repo` / `-r` | `---` |
| リモート指定 | `--remote` | `---` | `---` | `--remote` | `--remote` |
| 出力形式 | `--format` (`table`/`json`/`plain`) | `--json` (フィールド指定) | `--output` (`json`/`text`) | `--output` (`simple`/`table`/`csv`/`tsv`/`yaml`/`json`) | `--json` |
| フィルタ式 | `--jq` (JSON 出力に適用) | `--jq` (JSON 出力に適用) | `---` | `---` | `---` |
| ページネーション | `--limit` (サブコマンドごと) | `--limit` / `-L` | `--per-page` / `-P`, `--page` / `-p` | `--limit` / `-l`, `--page` / `-p` | `--count` |
| ブラウザで開く | `browse` (別コマンド) + `--web` | `--web` / `-w` | `--web` / `-w` | `--browse` / `-b` | `---` |
| バージョン表示 | `--version` | `--version` | `--version` | `--version` | `--version` |
| ヘルプ | `--help` / `-h` | `--help` | `--help` | `--help` / `-h` | `--help` / `-h` |
| ホスト指定 | `--repo` にホストを含める | `--hostname` (auth 時) | `---` | `--login` / `-l` | `--host` |

---

## 3. メインコマンド一覧

gfo の 33 トップレベルコマンドを基準に、各ツールの対応コマンド名を一覧する。

**コア操作**

| カテゴリ | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| PR / MR | `pr` | `pr` | `mr` | `pr` | `pr` |
| Issue | `issue` | `issue` | `issue` | `issue` | `issue` |
| リポジトリ | `repo` | `repo` | `repo` | `repo` | `repo` |
| リリース | `release` | `release` | `release` | `release` | `release` |

**ラベル・マイルストーン**

| カテゴリ | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| ラベル | `label` | `label` | `label` | `label` | `label` |
| マイルストーン | `milestone` | `---` | `milestone` | `milestone` | `---` |

**Git リソース**

| カテゴリ | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| ブランチ | `branch` | `---` | `---` | `---` | `---` |
| タグ | `tag` | `---` | `---` | `---` | `---` |
| コミットステータス | `status` | `---` | `---` | `---` | `---` |

**CI/CD**

| カテゴリ | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| CI | `ci` | `run` / `workflow` | `ci` / `pipeline` | `---` | `---` |
| シークレット | `secret` | `secret` | `variable` | `---` | `---` |
| 変数 | `variable` | `variable` | `variable` | `---` | `---` |

**検索・通知**

| カテゴリ | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| 検索 | `search` | `search` | `---` | `---` | `---` |
| 通知 | `notification` | `status` | `---` | `notification` | `notification` |

**リポジトリ管理**

| カテゴリ | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| ファイル | `file` | `---` | `---` | `---` | `---` |
| Webhook | `webhook` | `---` | `---` | `---` | `---` |
| デプロイキー | `deploy-key` | `---` | `---` | `---` | `---` |
| コラボレーター | `collaborator` | `---` | `---` | `---` | `---` |
| ブランチ保護 | `branch-protect` | `---` | `---` | `---` | `---` |
| タグ保護 | `tag-protect` | `---` | `---` | `---` | `---` |
| Wiki | `wiki` | `---` | `---` | `---` | `wiki` |
| パッケージ | `package` | `---` | `---` | `---` | `---` |

**ユーザー・組織**

| カテゴリ | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| ユーザー | `user` | `---` | `---` | `---` | `user` |
| 組織 | `org` | `org` | `---` | `---` | `---` |
| SSH キー | `ssh-key` | `ssh-key` | `ssh-key` | `---` | `ssh-key` |
| GPG キー | `gpg-key` | `gpg-key` | `---` | `---` | `---` |

**ユーティリティ**

| カテゴリ | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| 初期化 | `init` | `---` | `---` | `---` | `---` |
| 認証 | `auth` | `auth` | `auth` | `login` | `auth` |
| ブラウザ | `browse` | `browse` | `---` | `open` | `---` |
| API | `api` | `api` | `api` | `---` | `api` |
| 一括操作 | `batch` | `---` | `---` | `---` | `---` |
| スキーマ | `schema` | `---` | `---` | `---` | `---` |
| Issue テンプレート | `issue-template` | `---` | `---` | `---` | `---` |

---

## 4. サブコマンド・オプション詳細比較

### 4.1 PR / MR

#### サブコマンド対応表

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| list | `pr list` | `pr list` | `mr list` | `pr list` | `pr list` |
| create | `pr create` | `pr create` | `mr create` | `pr create` | `pr create` |
| view | `pr view` | `pr view` | `mr view` | `pr view` | `pr view` |
| edit | `pr edit` | `pr edit` | `mr update` | `pr edit` | `pr edit` |
| close | `pr close` | `pr close` | `mr close` | `pr close` | `pr close` |
| reopen | `pr reopen` | `pr reopen` | `mr reopen` | `pr reopen` | `pr reopen` |
| merge | `pr merge` | `pr merge` | `mr merge` | `pr merge` | `pr merge` |
| checkout | `pr checkout` | `pr checkout` | `mr checkout` | `pr checkout` | `pr checkout` |
| diff | `pr diff` | `pr diff` | `mr diff` | `---` | `pr diff` |
| checks | `pr checks` | `pr checks` | `mr checks` | `---` | `---` |
| files | `pr files` | `---` | `---` | `---` | `---` |
| commits | `pr commits` | `---` | `---` | `---` | `---` |
| ready | `pr ready` | `pr ready` | `---` | `---` | `---` |
| update-branch | `pr update-branch` | `---` | `---` | `---` | `---` |
| review | `pr review` (list/create/dismiss) | `pr review` | `mr approve` | `pr approve`/`reject` | `---` |
| comment | `pr comment` (list/create/edit/delete) | `pr comment` | `mr note` | `---` | `---` |
| reviewers | `pr reviewers` (list/add/remove) | `---` | `mr reviewers` / `revoke` | `---` | `---` |

#### オプション比較: pr create

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| タイトル | `--title` | `--title` | `--title` | `--title` | `--title` |
| 本文 | `--body` | `--body` | `--body` | `--description` | `--body` |
| ベースブランチ | `--base` | `--base` | `--base` | `--base` | `--base` |
| ヘッドブランチ | `--head` | `--head` | `--head` | `--head` | `--head` |
| ドラフト | `--draft` | `--draft` | `--draft` | `---` | `---` |
| レビュアー | `--reviewer` | `--reviewer` | `--reviewer` | `---` | `---` |
| 担当者 | `--assignee` | `--assignee` | `--assignee` | `---` | `---` |
| ラベル | `--label` | `--label` | `--label` | `--label` | `--label` |
| マイルストーン | `--milestone` | `--milestone` | `--milestone` | `--milestone` | `---` |
| 自動入力 | `--fill` | `--fill` | `--fill` | `---` | `---` |

#### オプション比較: pr merge

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| マージコミット | `--merge` | `--merge` | `---` (デフォルト) | `--style merge` | `--merge` |
| スカッシュ | `--squash` | `--squash` | `--squash` | `--style squash` | `--squash` |
| リベース | `--rebase` | `--rebase` | `--rebase` | `--style rebase` | `--rebase` |
| 自動マージ | `--auto` | `--auto` | `--when-pipeline-succeeds` | `---` | `---` |
| ブランチ削除 | `---` | `--delete-branch` | `--delete-branch` | `--delete-branch` | `---` |

#### オプション比較: pr edit

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| タイトル | `--title` | `--title` | `--title` | `--title` | `--title` |
| 本文 | `--body` | `--body` | `--body` | `---` | `--body` |
| ベースブランチ | `--base` | `--base` | `--target-branch` | `---` | `---` |

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
| list | `issue list` | `issue list` | `issue list` | `issue list` | `issue list` |
| create | `issue create` | `issue create` | `issue create` | `issue create` | `issue create` |
| view | `issue view` | `issue view` | `issue view` | `issue view` | `issue view` |
| edit | `issue edit` | `issue edit` | `issue update` | `issue edit` | `issue edit` |
| close | `issue close` | `issue close` | `issue close` | `issue close` | `issue close` |
| reopen | `issue reopen` | `issue reopen` | `issue reopen` | `issue reopen` | `issue reopen` |
| delete | `issue delete` | `issue delete` | `issue delete` | `---` | `---` |
| comment | `issue comment` (list/create/edit/delete) | `issue comment` | `issue note` | `---` | `---` |
| pin / unpin | `issue pin` / `issue unpin` | `issue pin` / `unpin` | `---` | `---` | `---` |
| reaction | `issue reaction` (list/add/remove) | `---` | `---` | `---` | `---` |
| depends | `issue depends` (list/add/remove) | `---` | `---` | `---` | `---` |
| timeline | `issue timeline` | `---` | `---` | `---` | `---` |
| time | `issue time` (list/add/delete) | `---` | `issue time-tracking` | `---` | `---` |
| migrate | `issue migrate` | `---` | `---` | `---` | `---` |

#### オプション比較: issue list

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| 状態 | `--state` | `--state` | `--state` | `--state` | `--state` |
| 担当者 | `--assignee` | `--assignee` | `--assignee` | `---` | `--assignee` |
| ラベル | `--label` | `--label` | `--label` | `--label` | `--label` |
| 作者 | `---` | `--author` | `--author` | `---` | `--author` |
| マイルストーン | `---` | `--milestone` | `--milestone` | `--milestone` | `---` |
| 件数上限 | `--limit` | `--limit` | `---` | `--limit` | `--limit` |

#### オプション比較: issue create

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| タイトル | `--title` | `--title` | `--title` | `--title` | `--title` |
| 本文 | `--body` | `--body` | `--body` | `--description` | `--body` |
| 担当者 | `--assignee` | `--assignee` | `--assignee` | `---` | `---` |
| ラベル | `--label` | `--label` | `--label` | `--label` | `--label` |
| タイプ | `--type` | `---` | `---` | `---` | `---` |
| 優先度 | `--priority` | `---` | `---` | `---` | `---` |

#### オプション比較: issue edit

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| タイトル | `--title` | `--title` | `--title` | `--title` | `--title` |
| 本文 | `--body` | `--body` | `--body` | `---` | `--body` |
| 担当者 | `--assignee` | `--assignee` | `--assignee` | `---` | `---` |
| ラベル | `--label` | `--label` | `--label` | `---` | `---` |

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
| list | `repo list` | `repo list` | `---` | `repo list` | `repo list` |
| create | `repo create` | `repo create` | `repo create` | `repo create` | `repo create` |
| view | `repo view` | `repo view` | `repo view` | `---` | `repo view` |
| edit | `repo edit` | `repo edit` | `---` | `---` | `---` |
| clone | `repo clone` | `repo clone` | `repo clone` | `repo clone` | `repo clone` |
| fork | `repo fork` | `repo fork` | `repo fork` | `repo fork` | `repo fork` |
| delete | `repo delete` | `repo delete` | `---` | `repo delete` | `repo delete` |
| archive | `repo archive` | `repo archive` | `repo archive` | `---` | `---` |
| languages | `repo languages` | `---` | `---` | `---` | `---` |
| topics | `repo topics` (list/add/remove/set) | `---` | `---` | `---` | `---` |
| compare | `repo compare` | `---` | `---` | `---` | `---` |
| migrate | `repo migrate` | `---` | `---` | `---` | `---` |
| mirror | `repo mirror` (list/add/remove/sync) | `---` | `---` | `---` | `---` |
| transfer | `repo transfer` | `---` | `---` | `---` | `---` |
| star / unstar | `repo star` / `repo unstar` | `---` | `---` | `---` | `repo star` |

#### オプション比較: repo create

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| 名前 | 位置引数 | 位置引数 | `--name` | 位置引数 | 位置引数 |
| 非公開 | `--private` | `--private` | `--private` | `--private` | `--private` |
| 説明 | `--description` | `--description` | `--description` | `--description` | `--description` |
| ホスト | `--host` | `---` | `---` | `---` | `---` |

#### オプション比較: repo edit

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| 説明 | `--description` | `--description` | `---` | `---` | `---` |
| 公開/非公開 | `--private` / `--public` | `--visibility` | `---` | `---` | `---` |
| デフォルトブランチ | `--default-branch` | `--default-branch` | `---` | `---` | `---` |

#### オプション比較: repo migrate

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| Clone URL | 位置引数 | `---` | `---` | `---` | `---` |
| 名前 | `--name` | `---` | `---` | `---` | `---` |
| 非公開 | `--private` | `---` | `---` | `---` | `---` |
| 説明 | `--description` | `---` | `---` | `---` | `---` |
| ミラー | `--mirror` | `---` | `---` | `---` | `---` |
| 認証トークン | `--auth-token` | `---` | `---` | `---` | `---` |

---

### 4.4 Release

#### サブコマンド対応表

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| list | `release list` | `release list` | `release list` | `release list` | `release list` |
| create | `release create` | `release create` | `release create` | `release create` | `release create` |
| view | `release view` | `release view` | `---` | `---` | `---` |
| edit | `release edit` | `release edit` | `---` | `release edit` | `---` |
| delete | `release delete` | `release delete` | `release delete` | `release delete` | `---` |
| asset upload | `release asset upload` | `release upload` | `release upload` | `---` | `---` |
| asset download | `release asset download` | `release download` | `release download` | `---` | `---` |
| asset list | `release asset list` | `---` | `---` | `---` | `---` |
| asset delete | `release asset delete` | `---` | `---` | `---` | `---` |

#### オプション比較: release create

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| タグ | 位置引数 | 位置引数 | `--tag` | `--tag` | `--tag` |
| タイトル | `--title` | `--title` | `--title` | `--title` | `--title` |
| ノート | `--notes` | `--notes` | `--description` | `--note` | `--notes` |
| ドラフト | `--draft` | `--draft` | `---` | `--draft` | `---` |
| プレリリース | `--prerelease` | `--prerelease` | `---` | `--prerelease` | `---` |
| ターゲット ref | `--target` | `--target` | `--ref` | `--target` | `---` |
| ファイル添付 | 別途 `asset upload` | 位置引数 | `--assets-links` | `--asset` | `---` |

#### オプション比較: release edit

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| タイトル | `--title` | `--title` | `---` | `--title` | `---` |
| ノート | `--notes` | `--notes` | `---` | `--note` | `---` |
| ドラフト切替 | `--draft` / `--no-draft` | `--draft` / `--latest` | `---` | `--draft` | `---` |
| プレリリース切替 | `--prerelease` / `--no-prerelease` | `--prerelease` / `--latest` | `---` | `--prerelease` | `---` |

#### オプション比較: release asset upload

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| タグ | `--tag` | 位置引数 (リリース指定) | 位置引数 | `---` | `---` |
| ファイル | 位置引数 | 位置引数 | `--assets-links` | `---` | `---` |
| 名前 | `--name` | `---` | `---` | `---` | `---` |

#### オプション比較: release asset download

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| タグ | `--tag` | 位置引数 | 位置引数 | `---` | `---` |
| アセット ID | `--asset-id` | `---` | `---` | `---` | `---` |
| パターン | `--pattern` | `--pattern` | `---` | `---` | `---` |
| 出力先 | `--dir` | `--dir` | `---` | `---` | `---` |

---

### 4.5 Label

#### サブコマンド対応表

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| list | `label list` | `label list` | `label list` | `label list` | `label list` |
| create | `label create` | `label create` | `label create` | `label create` | `label create` |
| edit | `label edit` | `label edit` | `---` | `label edit` | `---` |
| delete | `label delete` | `label delete` | `label delete` | `label delete` | `label delete` |
| clone | `label clone` | `label clone` | `---` | `---` | `---` |

#### オプション比較: label create

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| 名前 | 位置引数 | 位置引数 | `--name` | 位置引数 | 位置引数 |
| 色 | `--color` (RRGGBB) | `--color` | `--color` | `--color` | `--color` |
| 説明 | `--description` | `--description` | `--description` | `--description` | `--description` |

#### オプション比較: label edit

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| リネーム | `--new-name` | `--name` | `---` | `--name` | `---` |
| 色 | `--color` | `--color` | `---` | `--color` | `---` |
| 説明 | `--description` | `--description` | `---` | `--description` | `---` |

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
| view | `milestone view` | `---` | `---` | `---` | `---` |
| edit | `milestone edit` | `---` | `---` | `---` | `---` |
| close | `milestone close` | `---` | `---` | `milestone close` | `---` |
| reopen | `milestone reopen` | `---` | `---` | `milestone reopen` | `---` |
| delete | `milestone delete` | `---` | `milestone delete` | `milestone delete` | `---` |

#### オプション比較: milestone create

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| タイトル | 位置引数 | `---` | `--title` | `--title` | `---` |
| 説明 | `--description` | `---` | `--description` | `--description` | `---` |
| 期限 | `--due` (YYYY-MM-DD) | `---` | `--due-date` | `--deadline` | `---` |

#### オプション比較: milestone edit

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| タイトル | `--title` | `---` | `---` | `---` | `---` |
| 説明 | `--description` | `---` | `---` | `---` | `---` |
| 期限 | `--due` | `---` | `---` | `---` | `---` |
| 状態 | `--state` | `---` | `---` | `---` | `---` |

---

### 4.7 Branch / Tag / Status

#### Branch サブコマンド対応表

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| list | `branch list` | `---` | `---` | `---` | `---` |
| create | `branch create` | `---` | `---` | `---` | `---` |
| delete | `branch delete` | `---` | `---` | `---` | `---` |

> gfo の `branch create` は `--ref` でベースを指定。

#### Tag サブコマンド対応表

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| list | `tag list` | `---` | `---` | `---` | `---` |
| create | `tag create` | `---` | `---` | `---` | `---` |
| delete | `tag delete` | `---` | `---` | `---` | `---` |

> gfo の `tag create` は `--ref` でベースを、`--message` でアノテーションを指定。

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
| list | `ci list` | `run list` | `ci list` | `---` | `---` |
| view | `ci view` | `run view` | `ci view` | `---` | `---` |
| trigger | `ci trigger` | `workflow run` | `ci trigger` | `---` | `---` |
| retry | `ci retry` | `run rerun` | `ci retry` | `---` | `---` |
| cancel | `ci cancel` | `run cancel` | `ci cancel` | `---` | `---` |
| logs | `ci logs` | `run view --log` | `ci trace` | `---` | `---` |

#### オプション比較: ci trigger

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| リファレンス | `--ref` | 位置引数 (ref) | `--ref` | `---` | `---` |
| ワークフロー | `--workflow` / `-w` | 位置引数 (workflow) | `---` | `---` | `---` |
| 入力パラメータ | `--input` / `-i` (KEY=VALUE) | `--field` / `-f` | `--variables` | `---` | `---` |

#### オプション比較: ci logs

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| 実行 ID | 位置引数 | 位置引数 | 位置引数 | `---` | `---` |
| ジョブ指定 | `--job` / `-j` | `--job` | `--job` | `---` | `---` |

---

### 4.9 Secret / Variable

#### Secret サブコマンド対応表

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| list | `secret list` | `secret list` | `variable list` (type filter) | `---` | `---` |
| set | `secret set` | `secret set` | `variable set` (masked) | `---` | `---` |
| delete | `secret delete` | `secret delete` | `variable delete` | `---` | `---` |

#### オプション比較: secret set

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| 名前 | 位置引数 | 位置引数 | 位置引数 | `---` | `---` |
| 値 | `--value` | `--body` / stdin | `--value` | `---` | `---` |
| 環境変数から | `--env-var` | `--env-name` | `---` | `---` | `---` |
| ファイルから | `--file` | `---` | `---` | `---` | `---` |

#### Variable サブコマンド対応表

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| list | `variable list` | `variable list` | `variable list` | `---` | `---` |
| set | `variable set` | `variable set` | `variable set` | `---` | `---` |
| get | `variable get` | `variable get` | `variable get` | `---` | `---` |
| delete | `variable delete` | `variable delete` | `variable delete` | `---` | `---` |

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
| list | `wiki list` | `---` | `---` | `---` | `wiki list` |
| view | `wiki view` | `---` | `---` | `---` | `wiki view` |
| create | `wiki create` | `---` | `---` | `---` | `wiki create` |
| edit | `wiki edit` | `---` | `---` | `---` | `wiki edit` |
| delete | `wiki delete` | `---` | `---` | `---` | `wiki delete` |
| revisions | `wiki revisions` | `---` | `---` | `---` | `---` |

---

### 4.12 Notification

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| list | `notification list` | `status` | `---` | `notification list` | `notification list` |
| read | `notification read` | `---` | `---` | `notification read` | `notification read` |

> gfo の `notification list` は `--unread-only` / `--limit` オプション、`notification read` は `--all` オプションをサポート。

---

### 4.13 Org

#### User サブコマンド対応表

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| whoami | `user whoami` | `---` | `---` | `---` | `user` |

#### Org サブコマンド対応表

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| list | `org list` | `org list` | `---` | `---` | `---` |
| view | `org view` | `---` | `---` | `---` | `---` |
| members | `org members` | `org list` (members) | `---` | `---` | `---` |
| repos | `org repos` | `repo list --owner` | `---` | `---` | `---` |
| create | `org create` | `---` | `---` | `---` | `---` |
| delete | `org delete` | `---` | `---` | `---` | `---` |

---

### 4.14 SSH-Key / GPG-Key

#### SSH-Key サブコマンド対応表

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| list | `ssh-key list` | `ssh-key list` | `ssh-key list` | `---` | `ssh-key list` |
| create | `ssh-key create` | `ssh-key add` | `ssh-key add` | `---` | `ssh-key add` |
| delete | `ssh-key delete` | `ssh-key delete` | `ssh-key delete` | `---` | `ssh-key delete` |

#### GPG-Key サブコマンド対応表

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| list | `gpg-key list` | `gpg-key list` | `---` | `---` | `---` |
| create | `gpg-key create` | `gpg-key add` | `---` | `---` | `---` |
| delete | `gpg-key delete` | `gpg-key delete` | `---` | `---` | `---` |

---

### 4.15 Auth

| サブコマンド | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| login | `auth login` | `auth login` | `auth login` | `login` | `auth login` |
| status | `auth status` | `auth status` | `auth status` | `---` | `---` |
| switch | `auth switch` | `auth switch` | `---` | `---` | `---` |
| logout | `auth logout` | `auth logout` | `auth logout` | `---` | `---` |
| token | `---` | `auth token` | `---` | `---` | `---` |
| refresh | `---` | `auth refresh` | `---` | `---` | `---` |

#### オプション比較: auth login

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| ホスト | `--host` | `--hostname` | `---` | `---` | `--host` |
| トークン | `--token` | `--with-token` (stdin) | `--token` / `-t` | `--token` / `-t` | `--token` |
| アカウント | `--account` | `---` | `---` | `---` | `---` |

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
| list | `webhook list` | `---` | `---` | `---` | `---` |
| create | `webhook create` | `---` | `---` | `---` | `---` |
| delete | `webhook delete` | `---` | `---` | `---` | `---` |
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
| list | `deploy-key list` | `---` | `---` | `---` | `---` |
| create | `deploy-key create` | `---` | `---` | `---` | `---` |
| delete | `deploy-key delete` | `---` | `---` | `---` | `---` |

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
| list | `branch-protect list` | `---` | `---` | `---` | `---` |
| view | `branch-protect view` | `---` | `---` | `---` | `---` |
| set | `branch-protect set` | `---` | `---` | `---` | `---` |
| remove | `branch-protect remove` | `---` | `---` | `---` | `---` |

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
| gh | `browse` (`--projects` / `--settings` / `--wiki`) |
| glab | `---` (`--web` オプションのみ) |
| tea | `open` |
| fj | `---` |

#### オプション比較: browse

| オプション | gfo | gh | glab | tea | fj |
|---|---|---|---|---|---|
| PR を開く | `--pr N` | `--` (URL パス) | `---` | `---` | `---` |
| Issue を開く | `--issue N` | `--` (URL パス) | `---` | `---` | `---` |
| 設定を開く | `--settings` | `--settings` | `---` | `---` | `---` |
| URL 表示のみ | `--print` | `--no-browser` | `---` | `---` | `---` |

#### API

| ツール | コマンド | 説明 |
|---|---|---|
| gfo | `api METHOD PATH` | `--data` / `--header` オプション |
| gh | `api METHOD PATH` | `--field` / `--header` / `--paginate` オプション |
| glab | `api METHOD PATH` | `--field` / `--header` オプション |
| tea | `---` | `---` |
| fj | `api METHOD PATH` | `---` |

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
| gh | 約 20 | 約 100+ |
| glab | 約 15 | 約 60+ |
| tea | 約 10 | 約 40+ |
| fj | 約 10 | 約 30+ |

---

## 6. 設計思想の違い

| 観点 | gfo | gh / glab | tea / fj |
|---|---|---|---|
| **対象サービス** | 9 サービス横断 | 単一サービス専用 | 単一サービス専用 |
| **認証** | 環境変数 / `gfo auth login` | OAuth / トークン | トークン |
| **リポジトリ検出** | git remote 自動検出 + `--repo` で直接指定 | git remote から自動検出 | git remote / 設定ファイル |
| **出力形式** | `--format` + `--jq` | `--json` + `--jq` (gh) / `--output` (glab) | `--output` (tea) / `--json` (fj) |
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
