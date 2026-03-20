# コードレビュー: ae32e09..b17aec5 (todo.md 実装)

**対象**: 12 コミット / 55 ファイル / +5,566 -146 行
**レビュー日**: 2026-03-20
**テスト結果**: 3154 tests passed, 0 failures, coverage 89%

---

## 総合評価

todo.md の 13 セクション（TODO 1〜13）がすべて実装されている。API 設計の一貫性、既存パターンへの準拠、テストカバレッジはいずれも良好。以下に指摘事項をまとめる。

---

## Critical

### C1: GitLab `_to_webhook` / `update_webhook` で `active` が `enable_ssl_verification` に誤マッピング

**ファイル**: `src/gfo/adapter/gitlab.py:903`, `src/gfo/adapter/gitlab.py:1493-1494`

```python
# _to_webhook（読み取り時）
active=data.get("enable_ssl_verification", True),  # BUG

# update_webhook（書き込み時）
if active is not None:
    payload["enable_ssl_verification"] = active  # BUG
```

`active` フィールドが Webhook の有効/無効ではなく、SSL 検証の有効化フラグ (`enable_ssl_verification`) にマッピングされている。これにより:
- `gfo webhook list` で表示される `active` 状態が SSL 検証の状態を反映してしまう
- `gfo webhook edit --inactive` を実行すると Webhook が無効化されるのではなく SSL 検証が無効化される

**推奨**: GitLab Webhook API は直接的な `active` トグルを持たないため、`_warn_unsupported_params("webhook edit", active=active)` で未対応として扱うのが安全。`_to_webhook` では `active=True` を固定値で返すか、GitLab 15.7+ の `alert_status` / `disabled_until` フィールドで判定する。

---

## High

### H1: `pr status` の `review-requested` 検索が全サービスで機能しない

**ファイル**: `src/gfo/commands/pr.py:221-223`

```python
review_requested = adapter.list_pull_requests(
    state="open", search=f"review-requested:{username}"
)
```

`search` パラメータに `review-requested:` という GitHub Search API 固有の構文を渡しているが、GitHub アダプターの `list_pull_requests` は Search API ではなくクライアント側の title/body テキストマッチで `search` を処理している。そのため GitHub でも正しく動作しない（PR の title/body に `review-requested:xxx` という文字列を含むものを検索してしまう）。GitLab/Gitea 等でも同様に意味のないフィルタになる。

**推奨**: 各サービスの review-requested フィルタリングをアダプター層で個別に実装するか、`handle_status` で `review_requested` セクションの取得方式を再設計する。

### H2: `ci watch` にタイムアウト機構がない

**ファイル**: `src/gfo/commands/ci.py:73-80`

```python
while True:
    pipeline = adapter.get_pipeline(args.id)
    ...
    if pipeline.status in terminal_statuses:
        break
    time.sleep(args.interval)
```

パイプラインが `terminal_statuses` に含まれないステータスのまま停滞した場合、無限ループになる。

**推奨**: `--timeout` オプション（デフォルト 30 分程度）を追加し、経過時間を超えたら警告メッセージとともに終了する。

### H4: GitHub `sync_fork` で `branch` が必須パラメータ

**ファイル**: `src/gfo/adapter/github.py` (`sync_fork` メソッド)

```python
def sync_fork(self, *, branch: str | None = None) -> None:
    payload: dict = {}
    if branch is not None:
        payload["branch"] = branch
    self._client.post(f"{self._repos_path()}/merge-upstream", json=payload)
```

GitHub の `POST /repos/{owner}/{repo}/merge-upstream` は `branch` が**必須パラメータ**。`branch` を省略するとリクエストが 422 エラーになる。

**推奨**: `branch` が `None` の場合、リポジトリのデフォルトブランチを取得して設定する。

```python
if branch is None:
    repo = self.get_repository()
    branch = repo.default_branch
payload["branch"] = branch
```

### H5: `pr status` の `user["login"]` キーが全サービスで保証されていない

**ファイル**: `src/gfo/commands/pr.py:218`

```python
username = user["login"]
```

`get_current_user()` は `dict` を返すが、サービスによってキー名が異なる（Bitbucket: `username`、Backlog: `userId` 等）。`login` キーが存在しない場合 `KeyError` で落ちる。

**推奨**: 各アダプターの `get_current_user()` が必ず `login` キーを返すよう統一するか、コマンド側でフォールバックする。

---

## Medium

### M1: GitHub `list_pull_requests` のクライアント側フィルタによるパフォーマンス問題

**ファイル**: `src/gfo/adapter/github.py` (`list_pull_requests`)

`author`, `label`, `assignee`, `draft`, `search` のフィルタがすべてクライアント側で処理されている。`limit=30` 指定時、API から取得した全データ（最大30件）に対してフィルタリングするため、フィルタ後の結果が期待数より少なくなる可能性がある。

```python
# limit=30 で取得 → author フィルタで 5 件に → ユーザーは 30 件期待
results = paginate_link_header(..., limit=limit)
if author:
    results = [r for r in results if ...]
```

**推奨**: クライアント側フィルタ使用時は `limit=0`（全件取得）してからフィルタリングし、その後 `limit` で切り詰める方式を検討。または GitHub Search API の利用を検討。

### M2: `webhook edit --active` / `--inactive` の排他チェック不足

**ファイル**: `src/gfo/cli.py`（`webhook_edit` 定義）

```python
webhook_edit.add_argument("--active", action="store_true", default=None, ...)
webhook_edit.add_argument("--inactive", action="store_true", ...)
```

`--active` と `--inactive` が同時指定可能。コマンド側（`commands/webhook.py`）では `--inactive` が優先される実装だが、ユーザーの意図と異なる動作になりうる。

**推奨**: `mutually_exclusive_group` で排他制約を追加（`pr list --draft/--no-draft` で既に同パターンを使用済み）。

### M4: Gitea `lock_issue` で `reason` パラメータが無視される

**ファイル**: `src/gfo/adapter/gitea.py` (`lock_issue`)

```python
def lock_issue(self, number: int, *, reason: str | None = None) -> None:
    self._client.put(
        f"{self._repos_path()}/issues/{number}/lock",
        json={},  # reason が渡されていない
    )
```

Gitea API は `lock_reason` フィールドをサポートしている（v1.17+）。

**推奨**: `json={"lock_reason": reason} if reason else {}` に変更。

### M5: 複数アダプターで `add_labels`/`remove_labels` 等が受け取るだけで無視される

**ファイル**: Backlog/Azure DevOps/Bitbucket/Gogs/GitBucket の `update_pull_request` / `update_issue`

新しいパラメータをシグネチャに追加しているが、実際には使用せずにサイレントに無視している。一部のメソッド（Backlog の `issue create` 等）では `_warn_unsupported_params` を呼んでいるが、`update_issue` / `update_pull_request` では呼んでいない。

**推奨**: サポートしないパラメータが指定された場合は `_warn_unsupported_params` で警告を出す。一貫性のため、`list_issues` での `author`/`milestone` 等と同じパターンを適用。

### M6: `pr merge --delete-branch` でマージ後に `get_pull_request` を再呼び出し

**ファイル**: `src/gfo/commands/pr.py:89-92`

```python
if getattr(args, "delete_branch", False):
    pr = adapter.get_pull_request(args.number)
    adapter.delete_branch(name=pr.head)
```

マージ後に PR 情報を再取得して head ブランチ名を得ている。一部サービスではマージ後に PR 状態が変わるまでにラグがある場合がある。マージ前に取得しておく方が確実。

**推奨**: マージ前に `pr = adapter.get_pull_request(args.number)` を呼び、`pr.head` を保持してからマージ→ブランチ削除の順序で実行。

### M7: `variable get` に `--org` オプションがない

**ファイル**: `src/gfo/cli.py:1127-1128`

`variable list`, `variable set`, `variable delete` には `--org` が追加されたが、`variable get` には `--org` が追加されていない。org スコープの variable を取得する手段がない。

**推奨**: `variable_get.add_argument("--org", help=_("Organization scope"))` を追加し、`handle_get` でも `scope` を渡す。

### M8: `update_release_asset` と Gogs CI メソッドで型アノテーションが欠落

**ファイル**: `src/gfo/adapter/github.py`, `src/gfo/adapter/gitlab.py`, `src/gfo/adapter/gitea.py`, `src/gfo/adapter/gogs.py`

`update_release_asset` の実装が3アダプターで型なし定義:
```python
# 現在
def update_release_asset(self, *, tag, asset_id, name=None):
# あるべき形
def update_release_asset(self, *, tag: str, asset_id: int | str, name: str | None = None) -> ReleaseAsset:
```

Gogs の CI 関連メソッド (`list_workflows`, `enable_workflow` 等) も同様に型アノテーション欠落。

---

## Low

### L1: `ci workflow enable/disable` のハンドラに成功メッセージがない

**ファイル**: `src/gfo/commands/ci.py:113-120`

```python
def _handle_workflow_enable(args: argparse.Namespace) -> None:
    adapter = get_adapter()
    adapter.enable_workflow(args.id)
    # 成功メッセージなし
```

他のコマンド（`lock`, `unlock`, `delete` 等）では `print(_("..."))` で成功メッセージを表示している。

**推奨**: `print(_("Enabled workflow '{id}'.").format(id=args.id))` 等を追加。

### L2: `get_tag` の GitHub / Backlog 実装が全件スキャン

**ファイル**: `src/gfo/adapter/github.py`, `src/gfo/adapter/backlog.py`

GitHub REST API / Backlog API にタグ単体取得エンドポイントがないため `limit=0`（全件取得）してリニアサーチしている。タグ数が多いリポジトリではパフォーマンスに影響しうるが、頻繁に呼ばれるコマンドではないため許容範囲。

### L3: Forgejo の `sync_fork` エンドポイント

**ファイル**: `src/gfo/adapter/forgejo.py`（変更なし）

todo.md では Forgejo は `POST /repos/{owner}/{repo}/sync_fork` を使うと記載されているが、Forgejo アダプターは Gitea を継承しており `merge-upstream` エンドポイントを使用。Forgejo の新しいバージョンでは `sync_fork` エンドポイントが導入されている可能性がある。

**推奨**: Forgejo の対応バージョンを確認し、必要なら `sync_fork` をオーバーライド。

### L4: `pr merge --subject`/`--body` が `--auto` と併用時に無視される

**ファイル**: `src/gfo/commands/pr.py:86-95`

`--auto` を指定した場合、`--subject` と `--body` は黙って無視される。ユーザーに警告するか、`enable_auto_merge` にも渡すべき。

### L5: `_to_workflow` の `state` マッピングが二値的

**ファイル**: `src/gfo/adapter/github.py`, `src/gfo/adapter/gitea.py`

```python
state = "active" if data.get("state") == "active" else "disabled"
```

GitHub の workflow state には `disabled_fork`, `disabled_inactivity`, `disabled_manually` 等のバリエーションがある。すべて `disabled` に丸めるとユーザーが原因を区別できない。

---

## Info

### I1: todo.md との差異まとめ

| TODO | 項目 | 状況 |
|------|------|------|
| 1 (A1) | `label edit --new-name` → `--name` | **対象範囲外**（ae32e09 以前に実装済み） |
| 1 (B4-1) | `release create --notes-file` | 実装済み |
| 1 (B1-1) | `pr merge --delete-branch` | 実装済み |
| 2 | `pr list` フィルタ拡張 | 実装済み |
| 3 | `issue list` / `issue create` フィルタ拡張 | 実装済み |
| 4 | `pr edit` / `issue edit` メタデータ拡張 | 実装済み |
| 5 | `pr merge` コミットメッセージ | 実装済み |
| 6 | CRUD view 追加 | 実装済み |
| 7 | CRUD edit 追加 | 実装済み |
| 8 | `pr status` | 実装済み（H1/H5 の問題あり） |
| 9 | PR/Issue lock/unlock | 実装済み |
| 10 | CI 拡張 | 実装済み（H2/H3 の問題あり） |
| 11 | Issue subscribe + Org secrets | 実装済み |
| 12 | `repo edit --name` | 実装済み（警告メッセージも対応） |
| 13 | `repo sync` (fork 同期) | 実装済み（H4 の問題あり） |

### I2: コード品質の良い点

- **パターンの一貫性**: 新しいコマンドハンドラはすべて既存パターン（`get_adapter()` → API 呼び出し → `output()` / `print()`）に従っている
- **`getattr` の活用**: CLI 引数が存在しない場合の安全なアクセスに `getattr(args, "xxx", None)` を一貫して使用
- **`_warn_unsupported_params` の活用**: Backlog/Azure DevOps/Bitbucket でサポートしないパラメータに対して警告を出す既存パターンを踏襲（ただし M5 の漏れあり）
- **schema.py の同期**: 新しいコマンドがすべて `COMMAND_SCHEMAS` に登録されている
- **`mutually_exclusive_group` の使用**: `pr list --draft/--no-draft` で正しく排他制約を実装
- **repo rename の警告**: `repo edit --name` 使用時に stderr で remote URL 変更の警告を表示
- **milestone 名前解決**: GitHub の `_resolve_milestone_number()` ヘルパーで名前→番号変換を適切に実装
- **ci watch の stdout/stderr 分離**: ステータス表示を stderr、最終結果を stdout に出力する設計が良い
- **Org scope の設計**: Secret/Variable で `_secrets_base_path(scope)` ヘルパーが GitHub/GitLab/Gitea で統一されている

### I3: テストカバレッジ

- テスト総数 3154 (89% coverage)
- 全アダプターの新メソッドに対応するテストが追加されている
- `make_args()` ヘルパーが新パラメータに対応済み

---

## 指摘の優先順位サマリー

| 優先度 | 件数 | 即時対応推奨 |
|--------|------|-------------|
| Critical | 1 | C1（GitLab webhook の active 誤マッピング） |
| High | 3 | H1（pr status 動作不具合）、H4（sync_fork 422 エラー）、H5（user["login"] キー不統一） |
| Medium | 6 | M5（サイレント無視）、M7（variable get --org 欠落） |
| Low | 5 | 必要に応じて対応 |
