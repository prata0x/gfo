# 実装予定・検討項目

---

## テスト拡充

### T-1: アダプターレベルのテスト追加（最優先）

v0.6.0 で追加した 7 機能のアダプターテストが不足している。

#### GitLab

- `update_release`: `new_tag`/`target` 指定時の `NotSupportedError` テスト
- `update_repository`: `merge_method` 変換ロジック（`allow_merge_commit` → `"merge"`, `allow_rebase_merge` → `"rebase_merge"` 等）の全パターンテスト
- `update_repository`: `delete_branch_on_merge` → `remove_source_branch_after_merge` 変換テスト
- `disable_auto_merge`: `POST /cancel_merge_when_pipeline_succeeds` 呼び出しテスト
- `list_contributors`: マッピングテスト（`name`/`email`/`commits`）

#### GitHub

- `update_release`: `tag_name`/`target_commitish` PATCH ペイロードテスト
- `update_repository`: `allow_merge_commit`/`allow_squash_merge`/`allow_rebase_merge`/`delete_branch_on_merge` ペイロードテスト
- `list_contributors`: `login`/`contributions` マッピングテスト

#### Gitea

- `update_repository`: `default_merge_style` 変換テスト、`default_delete_branch_after_merge` テスト
- `disable_auto_merge`: `DELETE /pulls/{index}/merge` テスト
- `list_contributors`: マッピングテスト

#### Azure DevOps

- `disable_auto_merge`: `autoCompleteSetBy` を空にする PATCH テスト

#### Bitbucket

- `list_repositories`: `q=is_private` パラメータ変換テスト

#### 非対応サービス

- Bitbucket/Gogs/GitBucket/Backlog で `disable_auto_merge`, `list_contributors` が `NotSupportedError` を返すことのテスト

### T-2: コマンドレベルのエッジケーステスト

- S-2: `--draft` + `--prerelease` + `--limit` の組み合わせ（フィルタ→limit 適用順序）
- A-2: `--auto` と `--disable-auto` の同時指定時の CLI パースエラーテスト
- B-1: 空コントリビューターリスト（`[]`）のテスト
- B-2: 全 `allow_*` が None の場合のテスト

### T-3: 統合テスト追加

`tests/integration/base_gitea_family.py` に以下を追加:

- `release edit`（title, notes, draft, prerelease の変更）
- `release list` のフィルタ確認（draft/prerelease リリース作成 → フィルタ）
- `repo contributors` 一覧取得
- `repo edit` マージ戦略変更（Gitea/Forgejo）
- `repo list --visibility` フィルタ

