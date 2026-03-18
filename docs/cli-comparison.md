# CLI ツール比較表

gfo と各 Git ホスティングサービス向け公式/主要 CLI ツールのコマンド体系を比較する。

## 1. 比較対象

| ツール | 対象サービス | 言語 | リポジトリ / ドキュメント |
|--------|-------------|------|--------------------------|
| **gh** | GitHub | Go | [cli/cli](https://github.com/cli/cli) |
| **glab** | GitLab | Go | [gitlab-org/cli](https://gitlab.com/gitlab-org/cli) |
| **tea** | Gitea | Go | [gitea/tea](https://gitea.com/gitea/tea) |
| **fj** | Forgejo | Rust | [Cyborus/forgejo-cli](https://codeberg.org/Cyborus/forgejo-cli) |
| **gfo** | GitHub / GitLab / Bitbucket / Azure DevOps / Gitea / Forgejo / Gogs / GitBucket / Backlog | Python | [gfo](https://github.com/prata0x/gfo) |

> **凡例** — 以降の表で使用する記号:
> - **Y** … 対応済み
> - **—** … 未対応 / 該当なし
> - **(P)** … 部分的に対応（注記を参照）

---

## 2. グローバルオプション比較

| オプション | gh | glab | tea | fj | gfo |
|---|---|---|---|---|---|
| リポジトリ指定 | `--repo` / `-R` (`OWNER/REPO`) | `--repo` / `-R` (`OWNER/REPO`) | `--repo` / `-r` | — | `--repo` (`URL` or `HOST/OWNER/REPO`) |
| リモート指定 | — | — | `--remote` | `--remote` | `--remote` |
| 出力形式 | `--json` (フィールド指定) | `--output` (`json`/`text`) | `--output` (`simple`/`table`/`csv`/`tsv`/`yaml`/`json`) | `--json` | `--format` (`table`/`json`/`plain`) |
| フィルタ式 | `--jq` (JSON 出力に適用) | — | — | — | `--jq` (JSON 出力に適用) |
| ページネーション | `--limit` / `-L` | `--per-page` / `-P`, `--page` / `-p` | `--limit` / `-l`, `--page` / `-p` | `--count` | `--limit` (サブコマンドごと) |
| ブラウザで開く | `--web` / `-w` | `--web` / `-w` | `--browse` / `-b` | — | `browse` (別コマンド) |
| バージョン表示 | `--version` | `--version` | `--version` | `--version` | `--version` |
| ヘルプ | `--help` | `--help` | `--help` / `-h` | `--help` / `-h` | `--help` / `-h` |
| ホスト指定 | `--hostname` (auth 時) | — | `--login` / `-l` (ログイン名) | `--host` | `--repo` にホストを含める |

---

## 3. コマンド別比較

### メインコマンド一覧比較表

gfo の 35 トップレベルコマンドを基準に、各ツールの対応状況を一覧する。

**コア操作**

| コマンド | gh | glab | tea | fj | gfo |
|---|---|---|---|---|---|
| pr (mr) | Y | Y | Y | Y | Y |
| issue | Y | Y | Y | Y | Y |
| repo | Y | Y | Y | Y | Y |
| release | Y | Y | Y | Y | Y |

**コードレビュー・コメント**

| コマンド | gh | glab | tea | fj | gfo |
|---|---|---|---|---|---|
| review | — (pr 内) | — (mr 内) | — (pr 内) | — | Y (pr 内) |

**ラベル・マイルストーン**

| コマンド | gh | glab | tea | fj | gfo |
|---|---|---|---|---|---|
| label | Y | Y | Y | Y | Y |
| milestone | — | Y | Y | — | Y |

**Git リソース**

| コマンド | gh | glab | tea | fj | gfo |
|---|---|---|---|---|---|
| branch | — | — | — | — | Y |
| tag | — | — | — | — | Y |
| status | — | — | — | — | Y |

**CI/CD**

| コマンド | gh | glab | tea | fj | gfo |
|---|---|---|---|---|---|
| ci | Y (run/workflow) | Y (ci/pipeline) | — | — | Y |
| secret | Y | Y (variable) | — | — | Y |
| variable | Y | Y (variable) | — | — | Y |

**検索・通知**

| コマンド | gh | glab | tea | fj | gfo |
|---|---|---|---|---|---|
| search | Y | — | — | — | Y |
| notification | Y (status) | — | Y | Y | Y |

**リポジトリ管理**

| コマンド | gh | glab | tea | fj | gfo |
|---|---|---|---|---|---|
| file | — | — | — | — | Y |
| webhook | — | — | — | — | Y |
| deploy-key | — | — | — | — | Y |
| collaborator | — | — | — | — | Y |
| branch-protect | — | — | — | — | Y |
| tag-protect | — | — | — | — | Y |
| wiki | — | — | — | Y | Y |
| package | — | — | — | — | Y |

**ユーザー・組織**

| コマンド | gh | glab | tea | fj | gfo |
|---|---|---|---|---|---|
| user | — | — | — | Y | Y |
| org | Y | — | — | — | Y |
| ssh-key | Y | Y | — | Y | Y |
| gpg-key | Y | — | — | — | Y |

**ユーティリティ**

| コマンド | gh | glab | tea | fj | gfo |
|---|---|---|---|---|---|
| init | — | — | — | — | Y |
| auth | Y | Y | Y (login) | Y | Y |
| browse | Y | — | Y (open) | — | Y |
| api | Y | Y | — | Y | Y |
| batch | — | — | — | — | Y |
| schema | — | — | — | — | Y |
| issue-template | — | — | — | — | Y |

---

### 3.1 PR / Merge Request

#### サブコマンド対応表

| サブコマンド | gh pr | glab mr | tea pr | fj pr | gfo pr |
|---|---|---|---|---|---|
| list | Y | Y | Y | Y | Y |
| create | Y | Y | Y | Y | Y |
| view | Y | Y | Y | Y | Y |
| edit / update | Y (`edit`) | Y (`update`) | Y (`edit`) | Y (`edit`) | Y (`edit`) |
| close | Y | Y | Y | Y | Y |
| reopen | Y | Y | Y | Y | Y |
| merge | Y | Y | Y | Y | Y |
| checkout | Y | Y | Y | Y | Y |
| diff | Y | Y | — | Y | Y |
| checks | Y | Y | — | — | Y |
| review | Y | Y | Y (`approve`/`reject`) | — | Y (list/create/dismiss) |
| comment | Y | Y (`note`) | — | — | Y (list/create/edit/delete) |
| ready | Y | — | — | — | Y |
| files | — | — | — | — | Y |
| commits | — | — | — | — | Y |
| reviewers | — | Y (`revoke`) | — | — | Y (list/add/remove) |
| update-branch | — | — | — | — | Y |

#### 主要オプション比較

**create**

| オプション | gh | glab | tea | fj | gfo |
|---|---|---|---|---|---|
| `--title` | Y | Y | Y | Y | Y |
| `--body` | Y | Y | Y (`--description`) | Y | Y |
| `--base` | Y | Y | Y | Y | Y |
| `--head` | Y | Y | Y | Y | Y |
| `--draft` | Y | Y | — | — | Y |
| `--reviewer` | Y | Y | — | — | Y |
| `--assignee` | Y | Y | — | — | Y |
| `--label` | Y | Y | Y | Y | Y |
| `--milestone` | Y | Y | Y | — | Y |
| `--fill` (自動入力) | Y | Y | — | — | Y |

**merge**

| オプション | gh | glab | tea | fj | gfo |
|---|---|---|---|---|---|
| `--merge` | Y | — | Y (`--style merge`) | Y (`--merge`) | Y |
| `--squash` | Y | Y | Y (`--style squash`) | Y (`--squash`) | Y |
| `--rebase` | Y | Y | Y (`--style rebase`) | Y (`--rebase`) | Y |
| `--auto` | Y | Y (`--when-pipeline-succeeds`) | — | — | Y |
| `--delete-branch` | Y | Y | Y | — | — |

---

### 3.2 Issue

#### サブコマンド対応表

| サブコマンド | gh issue | glab issue | tea issue | fj issue | gfo issue |
|---|---|---|---|---|---|
| list | Y | Y | Y | Y | Y |
| create | Y | Y | Y | Y | Y |
| view | Y | Y | Y | Y | Y |
| edit / update | Y (`edit`) | Y (`update`) | Y (`edit`) | Y (`edit`) | Y (`edit`) |
| close | Y | Y | Y | Y | Y |
| reopen | Y | Y | Y | Y | Y |
| delete | Y | Y | — | — | Y |
| comment | Y | Y (`note`) | — | — | Y (list/create/edit/delete) |
| pin / unpin | Y | — | — | — | Y |
| reaction | — | — | — | — | Y (list/add/remove) |
| depends | — | — | — | — | Y (list/add/remove) |
| timeline | — | — | — | — | Y |
| time | — | Y (`time-tracking`) | — | — | Y (list/add/delete) |
| migrate | — | — | — | — | Y |

#### 主要オプション比較

**list**

| オプション | gh | glab | tea | fj | gfo |
|---|---|---|---|---|---|
| `--state` | Y | Y | Y | Y | Y |
| `--assignee` | Y | Y | — | Y | Y |
| `--label` | Y | Y | Y | Y | Y |
| `--author` | Y | Y | — | Y | — |
| `--milestone` | Y | Y | Y | — | — |
| `--limit` | Y | — | Y | Y | Y |

---

### 3.3 Repo / Repository

#### サブコマンド対応表

| サブコマンド | gh repo | glab repo | tea repo | fj repo | gfo repo |
|---|---|---|---|---|---|
| list | Y | — | Y | Y | Y |
| create | Y | Y | Y | Y | Y |
| view | Y | Y | — | Y | Y |
| edit / update | Y (`edit`) | — | — | — | Y (`edit`) |
| clone | Y | Y | Y | Y | Y |
| fork | Y | Y | Y | Y | Y |
| delete | Y | — | Y | Y | Y |
| archive | Y | Y | — | — | Y |
| languages | — | — | — | — | Y |
| topics | — | — | — | — | Y (list/add/remove/set) |
| compare | — | — | — | — | Y |
| migrate | — | — | — | — | Y |
| transfer | — | — | — | — | Y |
| star / unstar | — | — | — | Y (`star`) | Y |
| mirror | — | — | — | — | Y (list/add/remove/sync) |

---

### 3.4 Release

#### サブコマンド対応表

| サブコマンド | gh release | glab release | tea release | fj release | gfo release |
|---|---|---|---|---|---|
| list | Y | Y | Y | Y | Y |
| create | Y | Y | Y | Y | Y |
| view | Y | — | — | — | Y |
| edit / update | Y (`edit`) | — | Y (`edit`) | — | Y (`edit`) |
| delete | Y | Y | Y | — | Y |
| asset upload | Y (`upload`) | Y (`upload`) | — | — | Y (`asset upload`) |
| asset download | Y (`download`) | Y (`download`) | — | — | Y (`asset download`) |
| asset list | — | — | — | — | Y (`asset list`) |
| asset delete | — | — | — | — | Y (`asset delete`) |

#### 主要オプション比較 (create)

| オプション | gh | glab | tea | fj | gfo |
|---|---|---|---|---|---|
| `--tag` | Y (位置引数) | Y | Y | Y | Y (位置引数) |
| `--title` | Y | Y | Y | Y | Y |
| `--notes` | Y | Y (`--description`) | Y (`--note`) | Y | Y |
| `--draft` | Y | — | Y | — | Y |
| `--prerelease` | Y | — | Y | — | Y |
| `--target` (ref) | Y | Y (`--ref`) | Y | — | — |
| ファイル添付 | Y (位置引数) | Y (`--assets-links`) | Y (`--asset`) | — | — (別途 `asset upload`) |

---

### 3.5 Label

| サブコマンド | gh label | glab label | tea label | fj label | gfo label |
|---|---|---|---|---|---|
| list | Y | Y | Y | Y | Y |
| create | Y | Y | Y | Y | Y |
| edit / update | Y (`edit`) | — | Y (`edit`) | — | Y (`edit`) |
| delete | Y | Y | Y | Y | Y |
| clone | Y (`clone`) | — | — | — | Y (`clone`) |

---

### 3.6 Milestone

| サブコマンド | gh (※) | glab (※) | tea milestone | fj | gfo milestone |
|---|---|---|---|---|---|
| list | — | Y | Y | — | Y |
| create | — | Y | Y | — | Y |
| view | — | — | — | — | Y |
| edit | — | — | — | — | Y |
| close | — | — | Y (`close`) | — | Y |
| reopen | — | — | Y (`reopen`) | — | Y |
| delete | — | Y | Y | — | Y |

> ※ gh には milestone 専用コマンドなし（`--milestone` フィルタのみ）。glab は `glab mr` / `glab issue` 内でマイルストーン操作が部分的に可能。

---

### 3.7 CI / Actions / Pipeline

| サブコマンド | gh run / workflow | glab ci / pipeline | tea | fj | gfo ci |
|---|---|---|---|---|---|
| list | Y (`run list`) | Y (`ci list`) | — | — | Y |
| view | Y (`run view`) | Y (`ci view`) | — | — | Y |
| trigger / run | Y (`workflow run`) | Y (`ci trigger`) | — | — | Y (`trigger`) |
| retry | Y (`run rerun`) | Y (`ci retry`) | — | — | Y |
| cancel | Y (`run cancel`) | Y (`ci cancel`) | — | — | Y |
| logs | Y (`run view --log`) | Y (`ci trace`) | — | — | Y |

---

### 3.8 Search

| サブコマンド | gh search | glab search | tea | fj | gfo search |
|---|---|---|---|---|---|
| repos | Y | — | — | — | Y |
| issues | Y | — | — | — | Y |
| prs | Y | — | — | — | Y |
| commits | Y | — | — | — | Y |
| code | Y | — | — | — | — |

---

### 3.9 認証

| サブコマンド | gh auth | glab auth | tea login | fj auth | gfo auth |
|---|---|---|---|---|---|
| login | Y | Y | Y | Y | Y |
| status | Y | Y | — | — | Y |
| logout | Y | Y | — | — | — |
| token | Y | — | — | — | — |
| refresh | Y | — | — | — | — |

---

## 4. gfo 独自コマンド

以下のコマンドは、比較対象の CLI ツールには存在しない、または大幅に拡張された gfo 独自の機能。

| コマンド | 説明 | サブコマンド |
|---|---|---|
| `branch` | リモートブランチ管理 | `list`, `create`, `delete` |
| `tag` | タグ管理 | `list`, `create`, `delete` |
| `status` | コミットステータス管理 | `list`, `create` |
| `file` | リポジトリファイル API 操作 | `get`, `put`, `delete` |
| `deploy-key` | デプロイキー管理 | `list`, `create`, `delete` |
| `collaborator` | コラボレーター管理 | `list`, `add`, `remove` |
| `branch-protect` | ブランチ保護ルール管理 | `list`, `view`, `set`, `remove` |
| `tag-protect` | タグ保護ルール管理 | `list`, `create`, `delete` |
| `wiki` | Wiki ページ管理 | `list`, `view`, `create`, `edit`, `delete`, `revisions` |
| `package` | パッケージ管理 | `list`, `view`, `delete` |
| `batch` | 複数リポジトリへの一括操作 | `pr create` |
| `schema` | コマンドの JSON Schema 出力 | `--list`, `[target...]` |
| `issue-template` | Issue テンプレート管理 | `list` |
| `variable` | CI/CD 変数管理 | `list`, `set`, `get`, `delete` |
| `gpg-key` | GPG キー管理 | `list`, `create`, `delete` |
| `issue migrate` | Issue のサービス間移行 | `--from`, `--to`, `--number`/`--all` |
| `issue reaction` | Issue リアクション管理 | `list`, `add`, `remove` |
| `issue depends` | Issue 依存関係管理 | `list`, `add`, `remove` |
| `issue timeline` | Issue タイムラインイベント | — |
| `issue pin` / `unpin` | Issue のピン留め | — |
| `issue time` | 時間トラッキング | `list`, `add`, `delete` |

> **注**: gh / glab にも一部類似機能はあるが（例: `gh secret`, `glab variable`）、gfo はこれらを**サービス横断で統一的に**提供している点が最大の差別化ポイント。

---

## 5. コマンド数サマリー

| ツール | トップレベルコマンド | サブコマンド合計（概算） |
|---|---|---|
| gh | 約 20 | 約 100+ |
| glab | 約 15 | 約 60+ |
| tea | 約 10 | 約 40+ |
| fj | 約 10 | 約 30+ |
| gfo | 35 | 約 130+ |

---

## 6. 設計思想の違い

| 観点 | gh / glab | tea / fj | gfo |
|---|---|---|---|
| **対象サービス** | 単一サービス専用 | 単一サービス専用 | 9 サービス横断 |
| **認証** | OAuth / トークン | トークン | 環境変数 / `gfo auth login` |
| **リポジトリ検出** | git remote から自動検出 | git remote / 設定ファイル | git remote 自動検出 + `--repo` で直接指定 |
| **出力形式** | `--json` + `--jq` | `--output` (複数形式) | `--format` + `--jq` |
| **拡張性** | Extensions (Go) | — | アダプターパターン（新サービス追加が容易） |
| **コメント/レビュー** | PR コマンドに内包 | — | コメントは pr/issue サブコマンド、レビューは独立コマンド |
| **一括操作** | — | — | `batch` コマンド |
| **Schema 出力** | — | — | `schema` コマンド（MCP / AI 連携用） |
