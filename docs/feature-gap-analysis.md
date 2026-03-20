# gfo 機能ギャップ分析

`docs/cli-comparison.md` を元に、gfo に不足している機能を洗い出し、9 サービスの API 対応状況で優先度を評価した結果。

凡例: O=対応, △=部分対応/制限あり, x=非対応

---

## 1. サービス横断 API 対応マトリクス

### 1.1 サブコマンド

| 機能 | GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog | 対応数 |
|---|---|---|---|---|---|---|---|---|---|---|
| `repo unarchive` | O | O | x | O | O | O | x | x | O | **6** |
| `ci delete` (実行の削除) | O | O | x | O | x | x | x | x | x | **3** |
| `auth token` (トークン表示) | ローカル実装 | ローカル実装 | ローカル実装 | ローカル実装 | ローカル実装 | ローカル実装 | ローカル実装 | ローカル実装 | ローカル実装 | **9** |
| `search code` | O | O | O | O | x | x | x | x | x | **4** |
| `issue status` (自分関連 Issue) | O | O | O | O | O | O | △ | △ | O | **7+** |
| `issue develop` (Issue→ブランチ) | △ | △ | △ | △ | △ | △ | x | △ | x | **7** (間接) |
| `pr subscribe` / `unsubscribe` | O | O | x | x | O | O | x | x | x | **4** |

### 1.2 オプション

| 機能 | GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog | 対応数 |
|---|---|---|---|---|---|---|---|---|---|---|
| `pr edit --draft` / `--ready` | △ | O | O | O | O | O | x | x | x | **6** |
| `repo list --archived` | O | O | △ | △ | O | O | x | x | O | **6** |
| `--body-file` (pr/issue create) | ローカル実装 | ローカル実装 | ローカル実装 | ローカル実装 | ローカル実装 | ローカル実装 | ローカル実装 | ローカル実装 | ローカル実装 | **9** |
| `pr create --dry-run` | ローカル実装 | ローカル実装 | ローカル実装 | ローカル実装 | ローカル実装 | ローカル実装 | ローカル実装 | ローカル実装 | ローカル実装 | **9** |
| `repo create --readme` | O | O | x | x | O | O | O | △ | x | **5** |
| `issue create/edit --due-date` | x | O | x | O | O | O | x | x | O | **5** |
| `pr list --milestone` | O | O | x | x | O | O | x | x | x | **4** |
| `issue create --template` | O | x | x | x | O | O | x | x | x | **3** |
| ~~`release create --generate-notes`~~ | ~~O~~ | ~~O~~ | ~~x~~ | ~~x~~ | ~~x~~ | ~~x~~ | ~~x~~ | ~~x~~ | ~~x~~ | ~~**2**~~ |
| `--web` (pr/issue create 等) | ローカル実装 | ローカル実装 | ローカル実装 | ローカル実装 | ローカル実装 | ローカル実装 | ローカル実装 | ローカル実装 | ローカル実装 | **9** |

---

## 2. 優先度評価

API 対応サービス数と実装コストに基づく優先度分類。

### 高優先度（ローカル実装 or 6+ サービス対応）

| 機能 | 対応数 | 実装コスト | 備考 |
|---|---|---|---|
| `--body-file` (pr/issue create) | 9 (ローカル) | 極低 | CLI 側でファイル読込→既存引数に渡すだけ |
| `auth token` | 9 (ローカル) | 極低 | config/auth から取得して表示 |
| `completion` (シェル補完) | 9 (ローカル) | 低 | argparse ベースで自動生成 |
| `--web` (pr/issue create 等) | 9 (ローカル) | 低 | `browse` コマンドの仕組みを流用 |
| `pr create --dry-run` | 9 (ローカル) | 低 | API 呼出をスキップしてプレビュー表示 |
| `issue status` | 7+ | 低 | 既存 `list_issues()` フィルタの組み合わせ |
| `issue develop` (Issue→ブランチ) | 7 (間接) | 低 | 既存 `create_branch()` + 命名規則 |
| `repo unarchive` | 6 | 低 | 既存 `update_repository()` に `archived=false` |
| `pr edit --draft` / `--ready` | 6 | 中 | サービスごとに方式が異なる |
| `repo list --archived` | 6 | 低 | クエリパラメータ追加 |

### 中優先度（3〜5 サービス対応）

| 機能 | 対応数 | 実装コスト | 備考 |
|---|---|---|---|
| `repo create --readme` | 5 | 低 | `auto_init` パラメータ追加 |
| `issue create/edit --due-date` | 5 | 低 | パラメータ追加 |
| `search code` | 4 | 中 | 検索 API のインターフェースがサービスごとに異なる |
| `pr subscribe` / `unsubscribe` | 4 | 中 | GitHub は通知スレッド経由で間接的 |
| `pr list --milestone` | 4 | 低 | クエリパラメータ追加 |
| `ci delete` | 3 | 低 | DELETE エンドポイント呼出 |
| `issue create --template` | 3 | 低 | テンプレート一覧取得→選択 |
| `config` コマンド | - | 中 | ローカル設定管理 |

> 対応サービス数 1〜2 の機能は非対応とした。理由は `docs/unsupported.md` を参照。

---

## 3. 実装計画

変更ファイル単位でグループ化した実装計画は `docs/todo.md` を参照。

> 非対応とした機能の理由は `docs/unsupported.md` を参照。
