# gfo 実装 TODO

`docs/feature-gap-analysis.md` の機能ギャップを変更ファイル単位でグループ化した実装計画。

---

## 1. `repo create` 安全性改善

**変更ファイル**: `cli.py`, `commands/repo.py`, テスト

`--private` / `--public` のどちらかを必須にする。未指定時はエラー。

```python
# cli.py: 排他グループを必須に変更
_repo_create_visibility = repo_create.add_mutually_exclusive_group(required=True)
_repo_create_visibility.add_argument("--private", dest="private", action="store_true")
_repo_create_visibility.add_argument("--public", dest="private", action="store_false")
```

**破壊的変更**: 既存の `repo create NAME --description ...` が `--private` または `--public` なしでエラーになる。

---

## 2. `--body-file` 共通対応

**変更ファイル**: `cli.py`, `commands/pr.py`, `commands/issue.py`, テスト

`pr create` と `issue create` に `--body-file` / `-F` オプションを追加。CLI 側でファイル読込→ `args.body` に代入。アダプター変更なし。

```python
# cli.py: pr create / issue create それぞれに追加
pr_create.add_argument("--body-file", "-F", type=argparse.FileType("r"), help=_("Read body from file"))

# commands/pr.py handle_create():
if args.body_file:
    args.body = args.body_file.read()
    args.body_file.close()
```

---

## 3. `repo` コマンド拡張

**変更ファイル**: `cli.py`, `commands/repo.py`, `adapter/base.py`, 各アダプター (9 ファイル), テスト

### 3a. `repo unarchive` (6 サービス対応)

既存の `update_repository()` に `archived=False` を渡す。新規アダプターメソッド不要。

```python
# cli.py
repo_sub.add_parser("unarchive", help=_("Unarchive repository"))

# commands/repo.py handle_unarchive():
adapter.update_repository(archived=False)
```

### 3b. `repo list --archived` (6 サービス対応)

`list_repositories()` に `archived` パラメータを追加。

### 3c. `repo create --readme` (5 サービス対応)

`create_repository()` に `auto_init` パラメータを追加。

---

## 4. `issue` コマンド拡張

**変更ファイル**: `cli.py`, `commands/issue.py`, `adapter/base.py`, 各アダプター (9 ファイル), テスト

### 4a. `issue create/edit --due-date` (5 サービス対応)

`create_issue()` / `update_issue()` に `due_date` パラメータを追加。

### 4b. `issue create --template` (3 サービス対応)

既存の `list_issue_templates()` を使ってテンプレート一覧を取得→選択→本文に反映。

### 4c. `issue status` (7+ サービス対応)

既存の `list_issues()` + `get_current_user()` の組み合わせ。新規アダプターメソッド不要。

```python
# commands/issue.py handle_status():
user = adapter.get_current_user()
created = adapter.list_issues(state="open", author=user.login)
assigned = adapter.list_issues(state="open", assignee=user.login)
```

### 4d. `issue develop` (7 サービス対応、間接)

既存の `create_branch()` を使用。ブランチ名を `issue-{number}-{slug}` 形式で自動生成。

---

## 5. `pr` コマンド拡張

**変更ファイル**: `cli.py`, `commands/pr.py`, `adapter/base.py`, 各アダプター (9 ファイル), テスト

### 5a. `pr edit --draft` / `--ready` (6 サービス対応)

`update_pull_request()` に `draft` パラメータを追加。サービスごとに方式が異なる:
- GitLab: タイトルの `Draft:` プレフィックス付与/除去
- GitHub: REST で draft→ready は不可（GraphQL 必要）。作成時のみ対応
- Azure DevOps / Gitea / Forgejo: `isDraft` / `draft` パラメータ

### 5b. `pr list --milestone` (4 サービス対応)

`list_pull_requests()` に `milestone` パラメータを追加。

### 5c. `pr subscribe` / `unsubscribe` (4 サービス対応)

`subscribe_pull_request()` / `unsubscribe_pull_request()` を `adapter/base.py` に追加。
- GitHub: Notification Thread 経由（間接的）
- GitLab: `POST /merge_requests/:iid/subscribe`
- Gitea / Forgejo: `PUT /issues/:index/subscriptions/:user`

### 5d. `pr create --dry-run`

CLI 側のみ。API 呼出をスキップしてタイトル・本文・ブランチ差分をプレビュー表示。

---

## 6. `ci delete`

**変更ファイル**: `cli.py`, `commands/ci.py`, `adapter/base.py`, 各アダプター (GitHub/GitLab/Azure DevOps), テスト

`delete_pipeline_run()` を `adapter/base.py` に追加。3 サービス対応。

```python
# adapter/base.py
def delete_pipeline_run(self, run_id: int) -> None:
    raise NotSupportedError("ci delete")
```

---

## 7. `search code`

**変更ファイル**: `cli.py`, `commands/search.py`, `adapter/base.py`, 各アダプター (GitHub/GitLab/Bitbucket/Azure DevOps), テスト

`search_code()` を `adapter/base.py` に追加。4 サービス対応。検索 API のインターフェースがサービスごとに異なる。

---

## 8. `release create --generate-notes`

**変更ファイル**: `cli.py`, `commands/release.py`, `adapter/base.py`, 各アダプター (GitHub/GitLab), テスト

`create_release()` に `generate_notes` パラメータを追加。または事前に `generate_release_notes()` でノートを生成して `notes` に渡す。

- GitHub: `generate_release_notes: true` パラメータ
- GitLab: `/repository/changelog` エンドポイントで事前生成

---

## 9. 新コマンド: `auth token` / `completion`

**変更ファイル**: `cli.py`, `commands/auth_cmd.py`, テスト

### 9a. `auth token`

現在の認証情報からトークンを取得して標準出力に出力。パイプ連携用。

```python
# commands/auth_cmd.py handle_token():
token = resolve_token(host)
print(token)
```

### 9b. `completion`

**変更ファイル**: `cli.py` (新サブコマンド登録)

argparse ベースでシェル補完スクリプトを生成。bash / zsh / fish 対応。

---

## 10. `--web` オプション共通追加

**変更ファイル**: `cli.py`, `commands/pr.py`, `commands/issue.py`, `commands/release.py`, `commands/browse.py`, テスト

`pr create`, `pr list`, `issue create`, `release view` 等に `--web` / `-w` オプションを追加。既存の `browse` コマンドの URL 構築ロジックを流用してブラウザで開く。

---

## 11. `config` コマンド

**変更ファイル**: `cli.py`, `commands/` (新規ファイル), `config.py`, テスト

デフォルトのエディタ、出力形式、リポジトリ設定等をローカルに保存・管理。設計要検討。
