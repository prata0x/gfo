# 非対応機能の記録

gfo が設計上の理由で意図的に提供しない機能を記録する。

---

## 非対応コマンド

CRUD 一貫性の観点で不足に見えるが、API 仕様上対応不可または不要なもの。

| コマンド | 理由 |
|---|---|
| `secret view` | シークレットは暗号化済みで読み取り不可（全サービス共通仕様） |
| `status edit` | コミットステータスは追記モデル（GitHub/GitLab 共通） |
| `pr review edit` | 投稿済みレビュー本文の編集 API が全サービスで未提供 |
| `issue time edit` | 時間エントリの修正 API が未提供。delete → re-add で代替 |
| `notification delete` | 通知の削除 API が未提供。mark-read のみ（全サービス共通） |
| `collaborator edit` | `collaborator add` の再実行で権限変更可能。専用 edit は不要 |

---

## 非対応サブコマンド

API 対応サービス数が 1〜2、またはデータモデルの統一が困難なもの。

| 機能 | 対応数 | 理由 |
|---|---|---|
| `pr rebase` | 1 (GitLab) | GitLab のみ専用 API を持つ。他はマージ時の strategy 指定のみ |
| `pr revert` | 1 (Azure DevOps) | GitHub は GraphQL のみ。REST API 対応は 1 サービス |
| `pr delete` | 1 (GitLab) | GitLab のみ。他は close のみ対応 |
| `pr todo` | 1 (GitLab) | GitLab 固有の TODO リスト概念。他サービスに該当機能なし |
| `pr issues` (関連 Issue) | 2+ | サービス間でデータモデルが根本的に異なる（後述） |
| `issue transfer` | 2 (GitLab + Azure DevOps) | GitHub は GraphQL のみ |
| `repo autolink` | 1 (GitHub) | GitHub 固有機能 |
| `ci lint` | 2 (GitLab + Azure DevOps) | CI 設定形式がサービスごとに異なる |
| `cache` (CI キャッシュ) | 2 (GitHub + Bitbucket) | 対応が限定的 |
| `schedule` (CI スケジュール) | 2 (GitLab + Bitbucket) | 他は YAML 定義で API 管理不可 |
| `runner` (CI Runner 管理) | 5 | サービス固有度が高い。階層構造・スコープ・権限モデルがサービスごとに大きく異なる（後述） |
| `issue board` | 5 | ボードの定義がサービスごとに全く異なる（後述）。gfo のスコープ外 |
| `gist` / `snippet` | 3 (GitHub + GitLab + Bitbucket) | リポジトリ操作と独立した機能。Git Forge 操作の範囲外 |

---

## 非対応オプション

API 対応サービス数が 1 のもの。

| 機能 | 対応サービス | 理由 |
|---|---|---|
| `pr edit --add-reviewer` / `--remove-reviewer` | - | `pr reviewers add/remove` で既にカバー |
| `pr list --reviewer` | 2 (GitLab + Azure DevOps) | 直接フィルタは 2 サービスのみ。GitHub は Search API 経由で間接的に可能だが方式が異なる |
| `pr merge --admin` | Azure DevOps | 明示パラメータは Azure DevOps のみ |
| `issue list --mention` | GitHub | GitHub のみ |
| `issue create/edit --confidential` | GitLab | GitLab のみ |
| `repo list --language` | GitHub | GitHub の検索 API のみ |
| `release create/edit --latest` | GitHub | GitHub のみ |
| `release create --discussion-category` | GitHub | GitHub のみ |
| `alias` | - | ローカル機能で API 不要だが、`schema` コマンドによる AI 連携を推進しており需要が不明確 |

---

## 個別の設計判断

### `pr issues` のデータモデル問題

「PR に関連する Issue」の定義がサービスごとに根本的に異なるため、統一インターフェースの提供が困難。

| サービス | 関連の定義 | 取得方法 | 返るエンティティ |
|---|---|---|---|
| GitLab | マージ時にクローズされる Issue | `GET /merge_requests/:iid/closes_issues` | Issue |
| Azure DevOps | 明示的にリンクされた Work Item | `GET /pullRequests/:id/workitems` | Work Item（Bug/Task/Epic 等） |
| GitHub | クロスリファレンス | Issue 側の Timeline Events から逆引き | Issue |
| Backlog | PR 作成時の紐付け | PR の `issueId` フィールド（1 対 1） | Issue |

### `issue board` のデータモデル問題

「ボード」の定義・カラムの概念がサービスごとに全く異なる。

| サービス | ボードの定義 | カラムの意味 | Issue の移動 = |
|---|---|---|---|
| GitLab | ラベルベースのカラム | ラベル | ラベル付け替え |
| Azure DevOps | Work Item の状態遷移 | 状態 | 状態変更 |
| GitHub | Projects v2 | カスタムフィールド | フィールド値変更 |
| Gitea / Forgejo | Projects（カラムベース） | 任意カラム | カラム間移動 |

### `runner` のデータモデル問題

Runner のスコープ階層・権限モデルがサービスごとに根本的に異なり、`list` 操作すら統一できない。
また Bitbucket は REST API が存在しない（UI のみ）ため、実質 5 サービス。

| サービス | スコープ階層 | API パス | 備考 |
|---|---|---|---|
| GitHub | リポジトリ or 組織（排他） | `/repos/{owner}/{repo}/actions/runners` or `/orgs/{org}/actions/runners` | 管理者権限が必要 |
| GitLab | インスタンス / グループ / プロジェクトの 3 階層 | `/admin/runners`, `/groups/{id}/runners`, `/projects/{id}/runners` | `shared` フラグで全体公開可能 |
| Azure DevOps | 組織レベルの pool のみ | `/_apis/distributedtask/pools` | プロジェクトは pool を参照するだけ |
| Gitea / Forgejo | インスタンス / オーナー / リポジトリの 3 階層 | `/admin/actions/runners`, `/{owner}/runners`, `/repos/{owner}/{repo}/runners` | GitLab に類似 |
| Bitbucket | - | **REST API なし** | UI のみで管理。API 実装不可 |
