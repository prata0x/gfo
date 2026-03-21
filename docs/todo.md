# 実装計画

`docs/issues.md` の 7 項目に対する詳細実装計画。

---

## S-1: `release edit --notes-file` 追加

### 概要

`release create` には `--notes-file` / `-F` があるが `release edit` にない不整合を解消する。
クライアント側でファイル読み込みして `--notes` に渡すだけで、アダプター変更不要。

### 実装手順

1. **CLI 引数追加** (`src/gfo/cli.py`)
   - `release edit` サブパーサーに `--notes-file` / `-F` を追加
   - `type=argparse.FileType("r")` （`release create` と同じパターン）

2. **コマンドハンドラ修正** (`src/gfo/commands/release.py` `handle_edit`)
   - `args.notes_file` が指定されていれば `read()` → `close()` で内容を取得
   - `--notes` と `--notes-file` が同時指定された場合のエラー処理（`--notes` 優先 or 排他）
   - `release create` の既存処理（行 34-37）と同じパターンで実装

3. **単体テスト** (`tests/test_commands/test_release.py`)
   - `--notes-file` 指定時にファイル内容が notes として渡されることを検証
   - `--notes` と `--notes-file` 同時指定時の挙動テスト
   - ファイルが空の場合のエッジケース

4. **ドキュメント更新**
   - `docs/cli-comparison.md` セクション 4.4「release edit」のオプション比較表を更新
   - `docs/commands.ja.md` / `docs/commands.md` の release edit セクションを更新

---

## S-2: `release list` に `--draft` / `--prerelease` フィルタ追加

### 概要

全サービスのレスポンスに `draft` / `prerelease` フィールドがあるため、クライアント側フィルタで対応。
Gitea / Forgejo は API パラメータでもフィルタ可能だが、統一的にクライアント側で処理する。

### 実装手順

1. **CLI 引数追加** (`src/gfo/cli.py`)
   - `release list` サブパーサーに以下を追加:
     - `--draft` / `--no-draft`（ドラフトのみ / ドラフト除外）
     - `--prerelease` / `--no-prerelease`（プレリリースのみ / プレリリース除外）
   - `store_true` / `store_false` で `default=None`（フィルタなし）

2. **コマンドハンドラ修正** (`src/gfo/commands/release.py` `handle_list`)
   - `adapter.list_releases()` の結果をクライアント側でフィルタ
   - `args.draft is not None` の場合、`release.draft == args.draft` で絞り込み
   - `args.prerelease is not None` の場合、同様に絞り込み
   - フィルタ後に `limit` を適用（フィルタ → limit の順序）

3. **単体テスト** (`tests/test_commands/test_release.py`)
   - `--draft` でドラフトのみ表示されることを検証
   - `--no-draft` でドラフトが除外されることを検証
   - `--prerelease` / `--no-prerelease` の同様のテスト
   - `--draft` と `--prerelease` の組み合わせテスト
   - 全リリースがフィルタされた場合（結果 0 件）のエッジケース
   - `--limit` との組み合わせ（フィルタ後に limit 適用）

4. **ドキュメント更新**
   - `docs/cli-comparison.md` セクション 4.4「release list」のオプション比較表を更新
   - `docs/commands.ja.md` / `docs/commands.md` の release list セクションを更新

---

## A-1: `repo list --visibility` 追加

### 概要

7+/9 サービスで API 対応。`public` / `private` / `internal` でリポジトリ一覧をフィルタする。

### サービス別 API パラメータ

| サービス | パラメータ |
|---|---|
| GitHub | GET `/user/repos?visibility=public\|private\|all` |
| GitLab | GET `/projects?visibility=public\|private\|internal` |
| Bitbucket | GET `/repositories/{workspace}?q=is_private=false` |
| Azure DevOps | プロジェクトスコープで制御 |
| Gitea | GET `/repos/search?private=true\|false` |
| Forgejo | Gitea 互換 |
| Gogs | GET `/repos/search?private=true\|false`（部分対応） |
| GitBucket | 部分対応 |
| Backlog | 非対応 |

### 実装手順

1. **CLI 引数追加** (`src/gfo/cli.py`)
   - `repo list` サブパーサーに `--visibility` / `-V` を追加
   - `choices=["public", "private", "internal"]`

2. **アダプター基底クラス修正** (`src/gfo/adapter/base.py`)
   - `list_repositories()` に `visibility: str | None = None` パラメータを追加

3. **各アダプター修正**（9 ファイル）
   - `github.py`: `visibility` パラメータを API クエリに追加
   - `gitlab.py`: `visibility` パラメータを API クエリに追加
   - `bitbucket.py`: `q` パラメータで `is_private` フィルタ
   - `azure_devops.py`: 可能な範囲で対応、非対応ならクライアント側フィルタ
   - `gitea.py`: `private` パラメータに変換
   - `forgejo.py`: Gitea 互換
   - `gogs.py`: `private` パラメータに変換（部分対応）
   - `gitbucket.py`: クライアント側フィルタ
   - `backlog.py`: クライアント側フィルタまたは `NotSupportedError`

4. **コマンドハンドラ修正** (`src/gfo/commands/repo.py` `handle_list`)
   - `args.visibility` を `adapter.list_repositories()` に渡す

5. **単体テスト** (`tests/test_commands/test_repo.py`)
   - `--visibility public` で adapter に正しいパラメータが渡されることを検証
   - `--visibility private` / `--visibility internal` の同様のテスト
   - 未指定時にフィルタなしであることを検証

6. **アダプターテスト** (`tests/test_adapters/`)
   - 各アダプターで `visibility` パラメータが正しい API リクエストに変換されることを検証
   - `internal` が非対応のサービスでの挙動テスト

7. **統合テスト** (`tests/integration/`)
   - セルフホストサービス（Gitea/Forgejo/Gogs/GitBucket）で `--visibility` フィルタの動作確認
   - public リポジトリと private リポジトリを作成し、フィルタ結果を検証

8. **ドキュメント更新**
   - `docs/cli-comparison.md` セクション 4.3「repo list」のオプション比較表を更新
   - `docs/commands.ja.md` / `docs/commands.md` の repo list セクションを更新

---

## A-2: `pr merge --disable-auto` 追加

### 概要

`--auto` の逆操作。5/9 サービスで API 対応。

### サービス別 API

| サービス | エンドポイント |
|---|---|
| GitHub | GraphQL `disablePullRequestAutoMerge` |
| GitLab | `POST /merge_requests/:iid/cancel_merge_when_pipeline_succeeds` |
| Azure DevOps | PATCH で `autoCompleteSetBy` を null に設定 |
| Gitea | `DELETE /pulls/{index}/merge` |
| Forgejo | Gitea 互換 |

### 実装手順

1. **CLI 引数追加** (`src/gfo/cli.py`)
   - `pr merge` サブパーサーに `--disable-auto` を追加
   - `--auto` と `--disable-auto` を相互排他グループに

2. **アダプター基底クラス修正** (`src/gfo/adapter/base.py`)
   - `disable_auto_merge(self, number: int) -> None` メソッドを追加
   - デフォルト実装で `NotSupportedError` を送出

3. **各アダプター修正**（5 ファイル）
   - `github.py`: GraphQL mutation `disablePullRequestAutoMerge` を実装
     - node_id の取得が必要（REST で PR 情報取得 → `node_id` フィールド）
   - `gitlab.py`: `POST /merge_requests/:iid/cancel_merge_when_pipeline_succeeds`
   - `azure_devops.py`: PATCH で `autoCompleteSetBy` を `None` に設定
   - `gitea.py`: `DELETE /repos/{owner}/{repo}/pulls/{index}/merge`
   - `forgejo.py`: Gitea 互換（`gitea.py` を継承していれば変更不要）

4. **コマンドハンドラ修正** (`src/gfo/commands/pr.py` `handle_merge`)
   - `args.disable_auto` が True の場合、`adapter.disable_auto_merge(args.number)` を呼び出して return
   - 他のマージオプション（`--squash` 等）との組み合わせを排除

5. **単体テスト** (`tests/test_commands/test_pr.py`)
   - `--disable-auto` で `disable_auto_merge` が呼ばれることを検証
   - `--auto` と `--disable-auto` 同時指定時のエラーテスト
   - `--disable-auto` と `--squash` 等の同時指定時の挙動テスト

6. **アダプターテスト** (`tests/test_adapters/`)
   - GitHub: GraphQL mutation の正しいペイロード検証
   - GitLab: 正しいエンドポイント呼び出し検証
   - Gitea: DELETE メソッドの検証
   - 非対応サービス: `NotSupportedError` の送出確認

7. **統合テスト** (`tests/integration/`)
   - Gitea / Forgejo で auto-merge 設定 → `--disable-auto` で解除の E2E テスト
   - ※ auto-merge にはリポジトリ設定の有効化が前提条件

8. **ドキュメント更新**
   - `docs/cli-comparison.md` セクション 4.1「pr merge」のオプション比較表を更新
   - `docs/commands.ja.md` / `docs/commands.md` の pr merge セクションを更新

---

## A-3: `release edit --tag` / `--target` 追加

### 概要

`release create` には `--target` があるが `release edit` にない不整合を解消。
リリース対応サービス中 3+ で API 対応。

### サービス別 API

| サービス | tag 変更 | target 変更 |
|---|---|---|
| GitHub | PATCH `/releases/{id}` → `tag_name` | `target_commitish` |
| Gitea | PATCH `/releases/{id}` → `tag_name` | `target_commitish` |
| Forgejo | Gitea 互換 | Gitea 互換 |
| GitLab | 非対応（tag_name は URL パスの一部） | 非対応 |

### 実装手順

1. **CLI 引数追加** (`src/gfo/cli.py`)
   - `release edit` サブパーサーに以下を追加:
     - `--tag`: 新しいタグ名
     - `--target`: ターゲット commitish（ブランチ名・コミット SHA）

2. **アダプター基底クラス修正** (`src/gfo/adapter/base.py`)
   - `update_release()` に `new_tag: str | None = None` と `target: str | None = None` パラメータを追加

3. **各アダプター修正**
   - `github.py`: PATCH ペイロードに `tag_name` と `target_commitish` を追加
   - `gitea.py`: 同上
   - `forgejo.py`: Gitea 互換（継承で対応）
   - `gitlab.py`: `new_tag` / `target` が指定された場合は `NotSupportedError`

4. **コマンドハンドラ修正** (`src/gfo/commands/release.py` `handle_edit`)
   - `args.tag` と `args.target` を `adapter.update_release()` に渡す

5. **単体テスト** (`tests/test_commands/test_release.py`)
   - `--tag new-tag` で adapter に正しいパラメータが渡されることを検証
   - `--target main` の同様のテスト
   - `--tag` と `--target` の組み合わせテスト

6. **アダプターテスト** (`tests/test_adapters/`)
   - GitHub / Gitea: PATCH ペイロードに `tag_name` / `target_commitish` が含まれることを検証
   - GitLab: `new_tag` 指定時に `NotSupportedError` が送出されることを検証

7. **統合テスト** (`tests/integration/`)
   - Gitea / Forgejo でリリースのタグ名変更を E2E テスト
   - 存在しないタグへの変更時のエラーハンドリング確認

8. **ドキュメント更新**
   - `docs/cli-comparison.md` セクション 4.4「release edit」のオプション比較表を更新
   - `docs/commands.ja.md` / `docs/commands.md` の release edit セクションを更新

---

## B-1: `repo contributors` サブコマンド追加

### 概要

リポジトリの貢献者一覧を表示する新規サブコマンド。4/9 サービスで API 対応。

### サービス別 API

| サービス | エンドポイント | レスポンスフィールド |
|---|---|---|
| GitHub | `GET /repos/{owner}/{repo}/contributors` | login, contributions |
| GitLab | `GET /projects/:id/repository/contributors` | name, email, commits, additions, deletions |
| Gitea | `GET /repos/{owner}/{repo}/contributors` | login, contributions（GitHub 互換） |
| Forgejo | Gitea 互換 | Gitea 互換 |

### 実装手順

1. **データクラス追加** (`src/gfo/adapter/base.py`)
   - `Contributor` データクラスを定義:
     ```python
     @dataclass(frozen=True, slots=True)
     class Contributor:
         username: str | None
         name: str | None
         email: str | None
         commits: int
     ```

2. **アダプター基底クラス修正** (`src/gfo/adapter/base.py`)
   - `list_contributors(self, *, limit: int = 30) -> list[Contributor]` メソッドを追加
   - デフォルト実装で `NotSupportedError` を送出

3. **各アダプター修正**（4 ファイル）
   - `github.py`: `GET /repos/{owner}/{repo}/contributors` → `Contributor` マッピング
   - `gitlab.py`: `GET /projects/:id/repository/contributors` → `Contributor` マッピング
   - `gitea.py`: `GET /repos/{owner}/{repo}/contributors` → `Contributor` マッピング（GitHub 互換想定だが要確認）
   - `forgejo.py`: Gitea 互換（継承で対応）

4. **CLI サブコマンド追加** (`src/gfo/cli.py`)
   - `repo` サブパーサーに `contributors` を追加
   - オプション: `--limit` / `-L`

5. **コマンドハンドラ追加** (`src/gfo/commands/repo.py`)
   - `handle_contributors(args, adapter, config)` 関数を追加
   - 出力フィールド: `["username", "name", "email", "commits"]`

6. **単体テスト** (`tests/test_commands/test_repo.py`)
   - adapter に正しいパラメータが渡されることを検証
   - 出力フォーマット（table / json / plain）のテスト
   - `--limit` の動作テスト
   - 非対応サービスでの `NotSupportedError` テスト

7. **アダプターテスト** (`tests/test_adapters/`)
   - GitHub / GitLab / Gitea: API レスポンスから `Contributor` への正しいマッピング検証
   - GitLab のレスポンス形式差異（`name`/`email` vs `login`）の変換テスト
   - ページネーション動作テスト
   - 空リポジトリ（コントリビューターなし）のエッジケース

8. **統合テスト** (`tests/integration/`)
   - Gitea / Forgejo でリポジトリ作成 → コミット → contributors 一覧取得の E2E テスト

9. **ドキュメント更新**
   - `docs/cli-comparison.md` セクション 4.3「Repo」サブコマンド対応表を更新
   - `docs/commands.ja.md` / `docs/commands.md` に repo contributors セクションを追加

---

## B-2: `repo edit` マージ戦略オプション追加

### 概要

リポジトリのマージ方式設定とマージ後ブランチ削除設定を API 経由で変更する。4+/9 サービスで対応。

### サービス別 API

| サービス | マージ戦略 | ブランチ削除 |
|---|---|---|
| GitHub | `allow_merge_commit`, `allow_squash_merge`, `allow_rebase_merge` | `delete_branch_on_merge` |
| GitLab | `merge_method` (merge/rebase_merge/ff) | `remove_source_branch_after_merge` |
| Azure DevOps | Policy Configuration API | 非対応 |
| Gitea | `default_merge_style` | `default_delete_branch_after_merge` |
| Forgejo | Gitea 互換 | Gitea 互換 |

### 実装手順

1. **CLI 引数追加** (`src/gfo/cli.py`)
   - `repo edit` サブパーサーに以下を追加:
     - `--allow-merge-commit` / `--no-allow-merge-commit`
     - `--allow-squash-merge` / `--no-allow-squash-merge`
     - `--allow-rebase-merge` / `--no-allow-rebase-merge`
     - `--delete-branch-on-merge` / `--no-delete-branch-on-merge`
   - 全て `store_true` / `store_false`, `default=None`

2. **アダプター基底クラス修正** (`src/gfo/adapter/base.py`)
   - `update_repository()` に以下パラメータを追加:
     - `allow_merge_commit: bool | None = None`
     - `allow_squash_merge: bool | None = None`
     - `allow_rebase_merge: bool | None = None`
     - `delete_branch_on_merge: bool | None = None`

3. **各アダプター修正**
   - `github.py`: PATCH ペイロードに各フィールドを直接マッピング
   - `gitlab.py`: `merge_method` への変換ロジック
     - 複数の allow フラグから GitLab の `merge_method` 値を決定する必要がある
     - `delete_branch_on_merge` → `remove_source_branch_after_merge`
   - `azure_devops.py`: Policy Configuration API への変換
   - `gitea.py`: `default_merge_style` への変換
     - `delete_branch_on_merge` → `default_delete_branch_after_merge`
   - `forgejo.py`: Gitea 互換

4. **コマンドハンドラ修正** (`src/gfo/commands/repo.py` `handle_edit`)
   - 新しいパラメータを `adapter.update_repository()` に渡す

5. **単体テスト** (`tests/test_commands/test_repo.py`)
   - 各オプションが adapter に正しいパラメータとして渡されることを検証
   - オプション未指定時に None が渡されることを検証
   - 複数オプション同時指定のテスト

6. **アダプターテスト** (`tests/test_adapters/`)
   - GitHub: PATCH ペイロードに各フィールドが正しく含まれることを検証
   - GitLab: `merge_method` への正しい変換を検証
     - `allow_merge_commit=True` のみ → `merge_method: "merge"`
     - `allow_rebase_merge=True` のみ → `merge_method: "rebase_merge"` 等
   - Gitea: `default_merge_style` への変換を検証
   - 非対応サービスでの挙動テスト

7. **統合テスト** (`tests/integration/`)
   - Gitea / Forgejo でマージ戦略変更 → 設定確認の E2E テスト
   - `delete-branch-on-merge` の設定変更テスト

8. **ドキュメント更新**
   - `docs/cli-comparison.md` セクション 4.3「repo edit」のオプション比較表を更新
   - `docs/commands.ja.md` / `docs/commands.md` の repo edit セクションを更新

---

## 実装順序

依存関係と難易度を考慮した推奨実装順序:

```
S-1 (release edit --notes-file)      ← アダプター変更なし、最小実装
 ↓
S-2 (release list フィルタ)           ← アダプター変更なし、クライアント側のみ
 ↓
A-3 (release edit --tag/--target)     ← S-1 と同じファイルを修正、まとめて実施
 ↓
A-1 (repo list --visibility)         ← 全アダプター修正だが単純なパラメータ追加
 ↓
A-2 (pr merge --disable-auto)        ← 新規アダプターメソッド追加、GitHub は GraphQL
 ↓
B-1 (repo contributors)              ← 新規データクラス + サブコマンド + アダプターメソッド
 ↓
B-2 (repo edit マージ戦略)            ← サービス間のデータモデル差異の変換が最も複雑
```
