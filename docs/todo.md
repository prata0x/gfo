# テスト拡充 実装計画

`docs/issues.md` の T-1〜T-3 に対する詳細実装計画。

---

## T-1: アダプターレベルのテスト追加

既存テストファイルに追記する。ペイロード検証は `json.loads(calls[N].request.body)` パターンで行う。
モック方式はクラスごとに異なる（`mock_responses` フィクスチャ or `@responses.activate` デコレータ）ため、追記先の既存テストに合わせる。

### 1. GitHub (`tests/test_adapters/test_github.py`)

既存の `TestUpdateRelease`（L1111）と `TestUpdateRepository`（L2890）に追記。

#### update_release: new_tag / target

既存 `TestUpdateRelease` に 2 テスト追加:

- `test_update_new_tag`: `new_tag="v1.0.1"` → ペイロードに `tag_name` が含まれることを検証
- `test_update_target`: `target="main"` → ペイロードに `target_commitish` が含まれることを検証

GET（リリース ID 取得）+ PATCH の 2 リクエストパターン。`mock_responses.calls[1].request.body` で検証。

#### update_repository: マージ戦略

既存 `TestUpdateRepository` に 2 テスト追加:

- `test_update_merge_strategy`: `allow_merge_commit=True, allow_squash_merge=False, allow_rebase_merge=True` → ペイロード検証
- `test_update_delete_branch_on_merge`: `delete_branch_on_merge=True` → ペイロード検証

#### list_contributors

新規 `TestListContributors` クラス:

- `test_basic`: `[{"login": "alice", "contributions": 100}]` → `Contributor(username="alice", commits=100)` マッピング検証
- `test_empty`: `[]` → 空リスト

---

### 2. GitLab (`tests/test_adapters/test_gitlab.py`)

#### update_release: NotSupportedError

既存 `TestUpdateRelease`（L1150）に 2 テスト追加:

- `test_new_tag_raises_not_supported`: `new_tag="v2.0.0"` → `NotSupportedError` 検証
- `test_target_raises_not_supported`: `target="main"` → `NotSupportedError` 検証

#### update_repository: merge_method 変換

既存 `TestUpdateRepositoryGitLab`（L3228）に 5 テスト追加:

- `test_allow_merge_commit`: `allow_merge_commit=True` → `merge_method: "merge"` 検証
- `test_allow_squash_merge`: `allow_squash_merge=True` → `merge_method: "merge"` 検証（`allow_merge_commit` と同じ値になることを明示的に確認）
- `test_allow_rebase_merge`: `allow_rebase_merge=True` → `merge_method: "rebase_merge"` 検証
- `test_delete_branch_on_merge`: `delete_branch_on_merge=True` → `remove_source_branch_after_merge: true` 検証
- `test_merge_strategy_none`: 全 None → ペイロードに `merge_method` キーなし検証

#### disable_auto_merge

新規 `TestDisableAutoMerge` クラス:

- `test_calls_cancel_endpoint`: `POST /merge_requests/1/cancel_merge_when_pipeline_succeeds` 呼び出し検証

#### list_contributors

新規 `TestListContributors` クラス:

- `test_basic`: `[{"name": "Alice", "email": "a@ex.com", "commits": 50}]` → `Contributor(username=None, name="Alice", ...)` マッピング検証
- `test_empty`: `[]` → 空リスト

---

### 3. Gitea (`tests/test_adapters/test_gitea.py`)

#### update_repository: default_merge_style 変換

既存の `TestUpdateRepositoryGitea` に 3 テスト追加:

- `test_allow_squash_merge`: `allow_squash_merge=True` → `default_merge_style: "squash"` 検証
- `test_allow_rebase_merge`: `allow_rebase_merge=True` → `default_merge_style: "rebase"` 検証
- `test_delete_branch_on_merge`: `delete_branch_on_merge=True` → `default_delete_branch_after_merge: true` 検証

#### disable_auto_merge

新規 `TestDisableAutoMerge` クラス:

- `test_calls_delete`: `DELETE /repos/test-owner/test-repo/pulls/1/merge` 呼び出し検証（ステータス 204）

#### list_contributors

新規 `TestListContributors` クラス:

- `test_basic`: `[{"login": "alice", "contributions": 100}]` → マッピング検証
- `test_api_not_found_raises`: 404 → `NotSupportedError` 検証（Gitea 1.22 未満対応）

---

### 4. Azure DevOps (`tests/test_adapters/test_azure_devops.py`)

#### disable_auto_merge

新規 `TestDisableAutoMerge` クラス:

- `test_calls_patch_with_empty_autocomplete`: PATCH ペイロードに `{"autoCompleteSetBy": {"id": ""}}` 検証

---

### 5. Bitbucket (`tests/test_adapters/test_bitbucket.py`)

#### list_repositories: visibility パラメータ変換

既存の `TestListRepositories` に 1 テスト追加:

- `test_visibility_private`: `visibility="private"` → URL に `q=is_private%3Dtrue` が含まれることを検証

---

### 6. 非対応サービス NotSupportedError テスト

各テストファイルの既存 NotSupported テストクラスに追記。

| サービス | テストファイル | クラス名 | 追加メソッド |
|---|---|---|---|
| Bitbucket | `test_bitbucket.py` | `TestNotSupported` | `test_disable_auto_merge`, `test_list_contributors` |
| Gogs | `test_gogs.py` | `TestNotSupportedOperations` | `test_disable_auto_merge`, `test_list_contributors` |
| GitBucket | `test_gitbucket.py` | `TestNotSupported` | `test_disable_auto_merge`, `test_list_contributors` |
| Backlog | `test_backlog.py` | `TestNotSupported` | `test_disable_auto_merge`, `test_list_contributors` |

---

## T-2: コマンドレベルのエッジケーステスト

### `tests/test_commands/test_release.py`

`TestHandleListFilter` クラスに 2 テスト追加:

- `test_filter_then_limit`: リリース 4 件（1 件 draft, 1 件 prerelease, 2 件 通常）→ `draft=False, prerelease=False, limit=4` → アダプターから 4 件返却後、コマンド側フィルタで 2 件に減ることを検証
  - ハンドラで `adapter.list_releases(limit=args.limit)` を呼ぶため、limit はアダプター側で適用済み。コマンド側 draft/prerelease フィルタで件数が減る可能性の確認
- `test_prerelease_and_limit`: リリース 3 件（2 件 prerelease, 1 件 通常）→ `prerelease=True, limit=3` → フィルタ後 2 件を検証

### `tests/test_commands/test_pr.py`

`TestHandleMergeDisableAuto` に 2 テスト追加:

- `test_disable_auto_ignores_merge_method`: `disable_auto=True, squash=True` → `disable_auto_merge` のみ呼ばれ `merge_pull_request` は呼ばれないことを検証
- `test_disable_auto_wins_over_auto`: `disable_auto=True, auto=True` → `disable_auto_merge` のみ呼ばれ `enable_auto_merge` は呼ばれないことを検証（`--auto` と `--disable-auto` は排他グループではなく、ハンドラの `elif` で `disable_auto` が優先される）

### `tests/test_commands/test_repo.py`

`TestHandleContributors` に 1 テスト追加:

- `test_empty_contributors_list`: `adapter.list_contributors.return_value = []` → JSON 出力が `[]`

`TestHandleEditMergeStrategy` に 1 テスト追加:

- `test_all_merge_options_none`: 全 `allow_*` と `delete_branch_on_merge` が None → adapter に None が渡されることを検証

### `tests/test_cli.py`

CLI パースレベルのテスト 1 件追加:

- `test_disable_auto_parsed`: `["pr", "merge", "1", "--disable-auto"]` → `ns.disable_auto is True` 検証

---

## T-3: 統合テスト追加

`tests/integration/base_gitea_family.py` に追記。

テスト番号は既存の隙間に挿入（`test_02a_*`, `test_16a_*` の命名規則）。

### test_02a_repo_list_visibility

`test_02_repo_list` の直後に挿入。

```python
def test_02a_repo_list_visibility(self) -> None:
    repos = self.adapter.list_repositories(visibility="public", limit=10)
    assert isinstance(repos, list)
    # テストリポジトリは private=False で作成されているため public に含まれるはず
    names = [r.name for r in repos]
    assert self.config.repo in names
```

### test_02b_repo_edit_merge_strategy

```python
def test_02b_repo_edit_merge_strategy(self) -> None:
    repo = self.adapter.update_repository(delete_branch_on_merge=True)
    assert isinstance(repo, Repository)
    # 復元
    self.adapter.update_repository(delete_branch_on_merge=False)
```

### test_02c_repo_contributors

```python
def test_02c_repo_contributors(self) -> None:
    contributors = self.adapter.list_contributors(limit=10)
    assert isinstance(contributors, list)
    # セットアップ時にコミット済みなので 1 人以上いるはず
    assert len(contributors) >= 1
    assert contributors[0].commits >= 1
```

### test_16a_release_edit

`test_16_release_list` の直後に挿入。`test_15_release_create` で作成した `v0.0.1-test` を編集。

title, notes に加え draft, prerelease の変更も検証する。

```python
def test_16a_release_edit(self) -> None:
    updated = self.adapter.update_release(
        tag="v0.0.1-test",
        title="Test Release (Updated)",
        notes="Updated notes",
        draft=False,
        prerelease=True,
    )
    assert updated.title == "Test Release (Updated)"
    assert updated.prerelease is True
    # 復元
    self.adapter.update_release(
        tag="v0.0.1-test",
        prerelease=False,
    )
```

### test_16b_release_list_filter

draft と prerelease の両方のフィルタを検証する。

```python
def test_16b_release_list_filter(self) -> None:
    # ドラフトリリースと prerelease を作成
    self.adapter.create_release(
        tag="v0.0.2-draft", title="Draft", notes="", draft=True
    )
    self.adapter.create_release(
        tag="v0.0.3-rc1", title="RC1", notes="", prerelease=True
    )
    time.sleep(2)
    releases = self.adapter.list_releases(limit=50)
    drafts = [r for r in releases if r.draft]
    prereleases = [r for r in releases if r.prerelease]
    non_drafts = [r for r in releases if not r.draft]
    assert any(r.tag == "v0.0.2-draft" for r in drafts)
    assert not any(r.tag == "v0.0.2-draft" for r in non_drafts)
    assert any(r.tag == "v0.0.3-rc1" for r in prereleases)
    # クリーンアップ
    self.adapter.delete_release(tag="v0.0.2-draft")
    self.adapter.delete_release(tag="v0.0.3-rc1")
```

---

## ドキュメント更新

テスト追加後、以下のドキュメント更新が必要:

### AGENTS.md

テスト数とカバレッジの記載を更新:

```
カバレッジ: 2552 テスト、88%
```

→ 実際のテスト数・カバレッジに更新（現在 3641 テスト、91%）

### docs/issues.md

T-1〜T-3 の実装完了後、完了済み項目を削除または完了マークを付与。

---

## 実装順序

```
T-2（コマンドエッジケース）   ← アダプター変更なし、最小実装
 ↓
T-1-6（非対応サービス NSE）   ← NotSupportedError テストのみ、実装変更なし
 ↓
T-1-1（GitHub アダプター）    ← ペイロード検証テスト
 ↓
T-1-2（GitLab アダプター）    ← merge_method 変換が最も複雑
 ↓
T-1-3（Gitea アダプター）     ← default_merge_style 変換
 ↓
T-1-4（Azure DevOps）         ← disable_auto_merge のみ
 ↓
T-1-5（Bitbucket）            ← visibility パラメータのみ
 ↓
T-3（統合テスト）              ← Docker Compose 環境が必要
 ↓
ドキュメント更新               ← テスト数・カバレッジ反映
```
