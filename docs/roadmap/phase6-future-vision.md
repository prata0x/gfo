# 第6弾: 将来構想 — マルチサービス CLI ならではの機能

複合コマンド（複数アダプタの組み合わせや git 操作を伴う）のため、単機能の実装が一通り完了した後に取り組む。

## TODO

1. [ ] **Issue のサービス間移行** (#49) — gfo のキラー機能候補。既存アダプタの組み合わせで実装可能
2. [ ] **Multi-repo batch PR creation** (#52) — 複数リポジトリへの一括 PR 作成。組織全体の変更適用に有用

---

## Issue のサービス間移行 (#49)

異なる Git ホスティングサービス間で Issue とコメントを移行する。マルチサービス CLI である gfo ならではのキラー機能。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | △ | △ | ○ | ○ | × | × | △ |

### 実装方針

専用 API はないが、gfo の **既存アダプタの get + create を組み合わせ**てコマンド層で実装可能。

- ソース側: `get_issue()` / `list_comments()` で取得
- ターゲット側: `create_issue()` / `create_comment()` で再作成
- メタデータ（ラベル、マイルストーン、担当者）も可能な範囲で移行

> **注**: PR の移行は base/head ブランチの移送や git 操作が必要であり、API の組み合わせだけでは完結しないためスコープ外とする。

### 実装詳細

- **adapter層**: 新しいアダプタメソッドは不要。既存の `get_issue()`, `list_comments()`, `create_issue()`, `create_comment()` を組み合わせ
- **command層**: `commands/issue.py` に `migrate` サブコマンドを追加
  - `gfo issue migrate --from github:owner/repo --to gitea:owner/repo --number 42` の形式
  - 複数 Issue の一括移行: `--all` または `--numbers 1,2,3`
  - マッピング戦略:
    - ラベル: ターゲット側に同名ラベルが存在すれば紐付け、なければ作成
    - マイルストーン: 同名マイルストーンがあれば紐付け
    - 担当者: ユーザー名が一致する場合のみ紐付け
    - コメント: 元のコメント投稿者・日時をコメント本文に埋め込み（API では投稿者を偽装できないため）

---

## Multi-repo batch PR creation (#52)

複数リポジトリに対して一括で PR を作成する。組織全体のセキュリティパッチ適用やツール更新に有用。

### API対応表

| GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|:------:|:------:|:---------:|:------------:|:-----:|:-------:|:----:|:---------:|:-------:|
| ○ | ○ | ○ | ○ | ○ | ○ | × | ○ | △ |

### 実装方針

gfo の既存 `pr create` を複数リポジトリに対してループ実行する形で実装可能。`gfo pr create --repos owner/repo1,owner/repo2,...` または設定ファイルでリポジトリグループを定義。

multi-gitter が 12K+ スター。gfo のアダプタ抽象化と相性が良く、サービスをまたいだバッチ操作（GitHub の一部リポ + Gitea の一部リポ）も可能。

### 実装詳細

- **adapter層**: 新しいアダプタメソッドは不要。既存の `create_pull_request()` を複数リポジトリに対して呼び出し
- **command層**: `commands/pr.py` の `create` に `--repos` オプションを追加、または `commands/batch.py` を新規作成
  - `gfo batch pr create --repos owner/repo1,owner/repo2 --title "Update deps" --body "..." --head feature-branch`
  - 設定ファイル方式: `gfo batch pr create --repo-group security-repos --title "..."`
  - 結果のサマリー表示（成功/失敗/スキップのリポジトリ一覧）
  - `--dry-run` オプションで事前確認
  - サービスをまたいだバッチ操作も可能（例: GitHub 3リポ + Gitea 2リポ）
