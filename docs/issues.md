# 実装予定項目

cli-comparison.md の調査に基づき、9 サービスの API 対応状況を評価して選定した実装項目。

---

## 優先度 S（クライアント側処理で全サービス対応可能）

### S-1: `release edit --notes-file` 追加

`release create` には `--notes-file` / `-F` があるが `release edit` にない不整合。
ファイルを読み込んで `--notes` に渡すだけのクライアント側処理であり、全サービスで動作する。

- 変更箇所: `cli.py`（argparse）, `commands/release.py`（handle_edit）
- テスト: `tests/test_commands/test_release.py`

### S-2: `release list` に `--draft` / `--prerelease` フィルタ追加

現在 `release list` は `--limit` のみ。ドラフト・プレリリースの絞り込みができない。
全サービスのレスポンスに `draft` / `prerelease` 相当のフィールドがあるため、クライアント側フィルタで対応可能。

- フィルタ方式: API レスポンスのフィールドでクライアント側フィルタ
  - GitHub: `draft`, `prerelease`
  - GitLab: `upcoming_release`（プレリリース相当）
  - Gitea / Forgejo: `draft`, `prerelease`（API パラメータでもフィルタ可能）
  - 他: レスポンスフィールドで判定
- 変更箇所: `cli.py`（argparse）, `commands/release.py`（handle_list）
- テスト: `tests/test_commands/test_release.py`

---

## 優先度 A（5+ サービスで API 対応）

### A-1: `repo list --visibility` 追加

公開/非公開/内部でリポジトリ一覧をフィルタする。
unsupported.md で「GitHub のみ」と誤記されていたが、実際は 7+/9 サービスで対応。

- API 対応: GitHub (`visibility`), GitLab (`visibility`), Bitbucket (`q` パラメータ), Azure DevOps (プロジェクトスコープ), Gitea (`private` パラメータ), Forgejo (同), Gogs (部分対応)
- 変更箇所: `cli.py`, `commands/repo.py`, `adapter/base.py`（`list_repositories` にパラメータ追加）, 各アダプター
- テスト: `tests/test_commands/test_repo.py`, `tests/test_adapters/`

### A-2: `pr merge --disable-auto` 追加

`--auto`（自動マージ有効化）の逆操作。対になるオプションがないのは不自然。
unsupported.md で「GitHub のみ」と誤記されていたが、実際は 5/9 サービスで対応。

- API 対応:
  - GitHub: GraphQL `disablePullRequestAutoMerge`
  - GitLab: `POST /merge_requests/:iid/cancel_merge_when_pipeline_succeeds`
  - Azure DevOps: `autoCompleteSetBy` を null に PATCH
  - Gitea: `DELETE /pulls/{index}/merge`
  - Forgejo: Gitea 互換
- 変更箇所: `cli.py`, `commands/pr.py`, `adapter/base.py`（`disable_auto_merge` メソッド追加）, 対応アダプター
- テスト: `tests/test_commands/test_pr.py`, `tests/test_adapters/`

### A-3: `release edit --tag` / `--target` 追加

`release create` には `--target` があるが `release edit` にない不整合。
リリース対応 7 サービス中、3+ サービスで API 対応。

- API 対応:
  - GitHub: `PATCH /releases/{id}` で `tag_name`, `target_commitish`
  - Gitea: `PATCH /releases/{id}` で `tag_name`, `target_commitish`
  - Forgejo: Gitea 互換
  - GitLab / 他: 非対応（`NotSupportedError`）
- 変更箇所: `cli.py`, `commands/release.py`, `adapter/base.py`（`update_release` にパラメータ追加）, 対応アダプター
- テスト: `tests/test_commands/test_release.py`, `tests/test_adapters/`

---

## 優先度 B（4 サービスで API 対応）

### B-1: `repo contributors` サブコマンド追加

unsupported.md で「2 サービス」と誤記されていたが、実際は 4/9 サービスで対応。
gfo の閾値（3+ サービス）を超えるため実装対象に変更。

- API 対応:
  - GitHub: `GET /repos/{owner}/{repo}/contributors`
  - GitLab: `GET /projects/:id/repository/contributors`
  - Gitea: `GET /repos/{owner}/{repo}/contributors` (GitHub 互換)
  - Forgejo: Gitea 互換
- 出力フィールド: name, email, commits
- 変更箇所: `cli.py`, `commands/repo.py`, `adapter/base.py`（`list_contributors` メソッド追加）, 対応アダプター
- テスト: `tests/test_commands/test_repo.py`, `tests/test_adapters/`

### B-2: `repo edit` マージ戦略オプション追加

リポジトリのマージ方式設定を API 経由で変更する。

- 追加オプション:
  - `--allow-merge-commit` / `--no-allow-merge-commit`
  - `--allow-squash-merge` / `--no-allow-squash-merge`
  - `--allow-rebase-merge` / `--no-allow-rebase-merge`
  - `--delete-branch-on-merge` / `--no-delete-branch-on-merge`
- API 対応:
  - GitHub: `PATCH /repos/{owner}/{repo}` で各フィールド
  - GitLab: `PUT /projects/:id` で `merge_method`, `remove_source_branch_after_merge`
  - Azure DevOps: Policy Configuration API
  - Gitea / Forgejo: `PATCH /repos/{owner}/{repo}` で `default_merge_style` 等（バグ報告あり）
- 変更箇所: `cli.py`, `commands/repo.py`, `adapter/base.py`（`update_repository` にパラメータ追加）, 対応アダプター
- テスト: `tests/test_commands/test_repo.py`, `tests/test_adapters/`
