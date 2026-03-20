# テストコードレビュー: ae32e09..b17aec5

## レビュー対象

| コミット | 内容 |
|---|---|
| `11a7f93` | B5-1〜B5-7 pr list フィルタ拡張 |
| `eb44644` | B3-1〜B3-4 issue list フィルタ拡張 + issue create --milestone |
| `b040561` | B2-1〜B2-7 pr/issue edit メタデータ拡張 |
| `43ab22f` | B1-2 pr merge --subject/--body |
| `137de1c` | F1-1〜F1-5 branch/tag/deploy-key/ssh-key/gpg-key view |
| `048c2f7` | F2-1〜F2-4 webhook/org/release-asset/tag-protect edit |
| `e9bd2fd` | E1-1 pr status |
| `a75ca77` | E1-5/E1-6 pr/issue lock/unlock |
| `4fa6d3b` | E1-3/E1-4/E1-7/E1-8 CI 拡張 |
| `8928969` | E1-9/E1-10 issue subscribe/unsubscribe + org scope secret/variable |
| `293a433` | E1-2 repo edit --name |
| `b17aec5` | E2-1 repo sync (fork 同期) |

変更規模: 29 ファイル、+3520 行

---

## 総合評価

テスト全体の品質は **良好**。コマンドレイヤー（モック）とアダプターレイヤー（HTTP モック）の 2 層テストが一貫しており、`patch_adapter` / `make_args` / `_patch_all` ヘルパーの活用で DRY 原則も守られている。全コマンドハンドラにエラー伝搬テストがあり、新パラメータ追加時の既存テスト更新も漏れなく行われている。

ただし、**アダプターレイヤーでのテスト不足** がいくつかの機能で見られる。特に issue list フィルタのアダプターテスト欠如、lock/unlock の NotSupportedError テスト欠如が目立つ。

---

## TODO 別レビュー

### TODO 2: pr list フィルタ (B5-1〜B5-7) — 評価: A

**コマンドテスト** (`test_commands/test_pr.py`):
- `test_passes_filter_params` — 全フィルタパラメータの受け渡し検証 ✓
- `test_default_filter_params_are_none` — デフォルト値 None の検証 ✓
- `TestPrListArgParsing` — CLI 引数パースのテスト ✓

**アダプターテスト**: 全サービスで充実。
- GitHub: base/head/author/label/assignee/draft/search の 7 テスト
- GitLab: 同等の 7 テスト
- Bitbucket: author/search の 2 テスト
- Azure DevOps: base/head/author/search + unsupported 警告テスト
- Gitea: 7 テスト
- Forgejo: 最小限だが Gitea 継承のため妥当
- GitBucket/Backlog: unsupported 警告テスト

#### 指摘事項

| # | 重要度 | 内容 |
|---|---|---|
| 1 | 軽微 | GitHub `test_search_client_filter` — title マッチのみテスト。実装は body マッチもサポートしているが、そのテストケースがない |

---

### TODO 3: issue list フィルタ (B3-1〜B3-4) — 評価: B-

**コマンドテスト** (`test_commands/test_issue.py`):
- `test_list_all_params` / `test_list_filters` に author/milestone/search 追加 ✓
- `test_list_with_new_filters` — 新フィルタ指定時のテスト ✓
- `test_create_with_milestone` — milestone 付き issue create ✓

#### 指摘事項

| # | 重要度 | 内容 |
|---|---|---|
| 2 | **重要** | issue list の author/milestone/search フィルタの **アダプターレベルテストが全サービスで完全に欠落**。pr list フィルタは全アダプターで詳細にテストされているのに対し不均衡。GitHub の `list_issues(author=...)` で `creator=` パラメータが送信されるか等、パラメータ名の誤りがあっても検出できない |

---

### TODO 4: pr/issue edit メタデータ (B2-1〜B2-7) — 評価: B+

**コマンドテスト** (`test_commands/test_pr_update.py`, `test_issue_update.py`):
- 全パラメータ (add_labels, remove_labels, add_assignees, remove_assignees, milestone) のテスト ✓
- CLI 引数パーステスト ✓

**アダプターテスト**:
- GitHub: add/remove labels, add/remove assignees, milestone — 非常に充実 ✓
- GitLab: add/remove labels ✓

#### 指摘事項

| # | 重要度 | 内容 |
|---|---|---|
| 3 | 中 | GitLab の `TestUpdatePullRequest` / `TestUpdateIssue` に add/remove assignees テストがない。GitLab は `assignee_ids` 形式のため検証が必要 |
| 4 | 中 | Gitea の remove_labels, add/remove_assignees, milestone テストがない |
| 5 | 中 | Bitbucket/Azure DevOps/Backlog/GitBucket の metadata update テスト（サポート有無の検証含む）が欠如 |

---

### TODO 5: pr merge commit message (B1-2) — 評価: A

**コマンドテスト** (`test_commands/test_pr.py`):
- デフォルト (`title=None, message=None`) / 両方指定 / subject のみの 3 ケース ✓

**アダプターテスト**: 全サービスで正確。
- GitHub: `commit_title`/`commit_message` + title のみのケース ✓
- GitLab: `merge_commit_message` = "title\n\nbody" ✓
- Bitbucket/Azure DevOps/Gitea/Forgejo/GitBucket: 各サービス固有フィールド ✓

#### 指摘事項

| # | 重要度 | 内容 |
|---|---|---|
| 6 | 軽微 | title のみ指定のアダプターテストが GitHub 以外にない。GitLab 等で title/message を `"\n\n".join` で結合している場合、不要な `\n\n` が入らないか未検証 |

---

### TODO 6: View コマンド (F1-1〜F1-5) — 評価: B+

**コマンドテスト** (`test_commands/test_branch.py`, `test_tag.py`, `test_deploy_key.py`, `test_ssh_key.py`, `test_gpg_key.py`):
- 各 4 テスト（基本/出力/JSON/エラー伝搬）— テスト規約の必須パターンを満たす ✓

**アダプターテスト**:
- GitHub: get_branch/get_tag/get_deploy_key/get_ssh_key/get_gpg_key の基本テスト ✓
- GitHub get_tag: not_found テストも追加 ✓

#### 指摘事項

| # | 重要度 | 内容 |
|---|---|---|
| 7 | 中 | GitHub の `TestGetBranch`, `TestGetDeployKey`, `TestGetSshKey`, `TestGetGpgKey` に 404 エラーテストがない（`TestGetTag` には not_found テストがある） |
| 8 | 中 | GitLab/Gitea アダプターに `get_branch`/`get_tag`/`get_deploy_key`/`get_ssh_key`/`get_gpg_key` のテストが存在しない（GitHub のみ） |

---

### TODO 7: Edit コマンド (F2-1〜F2-4) — 評価: A-

**コマンドテスト** (`test_commands/test_webhook.py`, `test_org.py`, `test_tag_protect.py`, `test_release.py`):
- webhook edit: 7 テスト（URL/events/activate/deactivate/JSON/エラー/inactive フラグ）✓
- org edit: 5 テスト ✓
- tag-protect edit: 6 テスト ✓
- release asset edit: 2 テスト ✓

**アダプターテスト**:
- GitHub/GitLab/Gitea: webhook/org/release-asset/tag-protect edit — 正確 ✓
- tag-protect: 7 サービスの `NotSupportedError` テスト ✓

#### 指摘事項

| # | 重要度 | 内容 |
|---|---|---|
| 9 | 軽微 | GitLab の `TestUpdateWebhook` に active 変更テストがない（GitHub/Gitea にはある） |
| 10 | 軽微 | release-asset edit に 404 テストがない（全サービス） |
| 11 | 軽微 | `test_webhook.py` の行 131, 137 で `json`, `pytest` がローカル import されている（他ファイルはトップレベル import） |

---

### TODO 8: pr status (E1-1) — 評価: A

**コマンドテスト** (`test_commands/test_pr.py` TestHandleStatus):
- API 呼び出し検証（get_current_user + list_pull_requests × 3 回）✓
- テーブル出力セクション/空セクション/JSON 出力/エラー伝搬 ✓
- `list_pull_requests` の 3 呼び出しが正しいパラメータで検証:
  - `author="test-user"` (自分が作成)
  - `search="review-requested:test-user"` (レビュー依頼)
  - `assignee="test-user"` (アサイン)

指摘事項なし。

---

### TODO 9: pr/issue lock/unlock (E1-5/E1-6) — 評価: B+

**コマンドテスト** (`test_commands/test_pr.py`, `test_issue.py`):
- lock/lock with reason/unlock の 3 ケース ✓

**アダプターテスト**:
- GitHub: lock_issue/lock with reason/unlock_issue/lock_pr/unlock_pr の 5 テスト ✓
- GitLab: lock/unlock (PR/Issue 各 2 テスト) ✓
- Gitea: lock/unlock (PR/Issue 各 2 テスト) ✓

#### 指摘事項

| # | 重要度 | 内容 |
|---|---|---|
| 12 | **重要** | lock/unlock の `NotSupportedError` テストが未サポートサービス（Bitbucket, Azure DevOps, Backlog, Gogs, GitBucket）に存在しない。`tag-protect` の `TestTagProtectNotSupported` と同様のパターンが必要 |
| 13 | 低 | Gitea の `lock_issue` が `reason` パラメータを受け取るがペイロードに含めず空 `{}` を送信する実装。意図的かバグか不明 |

---

### TODO 10: CI 拡張 (E1-3/E1-4/E1-7/E1-8) — 評価: A-

**コマンドテスト** (`test_commands/test_ci.py`):
- workflow list/enable/disable/no_action/error 5 テスト ✓
- artifact list/download/no_action/error 4 テスト ✓
- watch 即時成功/ポーリング/失敗/エラー 4 テスト ✓
- download 通常/job_id/エラー 3 テスト ✓

**アダプターテスト**:
- GitHub: list_workflows/enable/disable/list_artifacts/download_artifact/download_run_logs — 充実 ✓
- Gitea: 同等のカバレッジ ✓

#### 指摘事項

| # | 重要度 | 内容 |
|---|---|---|
| 14 | 低 | `handle_watch` テストで `time.sleep` の呼び出し回数・引数の assertion がない |
| 15 | 低 | Gitea に download_artifact 404 テスト、download_run_logs job_id テスト、enable/disable 404 テストがない（GitHub 側にはある） |

---

### TODO 11: issue subscribe + org scope secret/variable (E1-9/E1-10) — 評価: B+

**subscribe/unsubscribe アダプターテスト**:
- GitHub: subscribe/unsubscribe ✓ (`subscribed: true/false`)
- GitLab: subscribe/unsubscribe ✓ (POST メソッド)
- Gitea: subscribe/unsubscribe ✓ (GET `/user` + PUT/DELETE 2 段階 API)

**org scope secret/variable**:
- コマンドレイヤー: list/set/delete で `scope="my-org"` 受け渡し ✓
- GitHub/GitLab/Gitea: list/delete の org scope テスト ✓

#### 指摘事項

| # | 重要度 | 内容 |
|---|---|---|
| 16 | 中 | org scope `set_secret` / `set_variable` のアダプターレベルテストが全サービスで欠如。GitHub の `set_secret` は暗号化処理で org scope 用エンドポイントを使うため特に重要 |
| 17 | 低 | subscribe の 404（存在しない issue）テストが全サービスで欠如 |
| 18 | 低 | `test_secret.py` / `test_variable.py` の `make_args` に `org=None` が明示されていない（`getattr` で動くが意図が不明瞭） |

---

### TODO 12: repo edit --name (E1-2) — 評価: A

**コマンドテスト** (`test_commands/test_repo.py`):
- 既存テストに `name=None` 追加 ✓
- `test_rename_shows_warning` — stderr 警告テスト ✓
- `test_no_warning_without_name` — 警告なしテスト ✓

**アダプターテスト**: GitHub/GitLab/Gitea で `test_update_name` ✓

指摘事項なし。

---

### TODO 13: repo sync (E2-1) — 評価: A-

**コマンドテスト** (`test_commands/test_repo.py`):
- sync_fork (branch=None) / sync_fork_with_branch / sync_fork_json の 3 テスト ✓

**アダプターテスト**:
- GitHub: sync_fork / sync_fork_with_branch ✓
- Gitea: 同上 ✓

#### 指摘事項

| # | 重要度 | 内容 |
|---|---|---|
| 19 | 低 | GitLab 等の未サポートサービスに `NotSupportedError` テストがない |
| 20 | 低 | fork でないリポジトリに対する 422/409 エラーテストがない |

---

## 指摘事項サマリー

### 重要 (2 件)

| # | 箇所 | 内容 |
|---|---|---|
| 2 | 全アダプター `TestListIssues` | issue list の author/milestone/search フィルタのアダプターレベルテストが完全に欠落。pr list フィルタは全アダプターで詳細テスト済みなのに対し不均衡 |
| 12 | 全アダプター lock/unlock | lock/unlock の `NotSupportedError` テストが Bitbucket/Azure DevOps/Backlog/Gogs/GitBucket に存在しない |

### 中程度 (6 件)

| # | 箇所 | 内容 |
|---|---|---|
| 3 | `test_gitlab.py` | PR/Issue update の add/remove assignees テストがない |
| 4 | `test_gitea.py` | PR/Issue update の remove_labels, add/remove_assignees, milestone テストがない |
| 5 | `test_bitbucket.py` 他 | metadata update (add/remove labels/assignees/milestone) のテストが欠如 |
| 7 | `test_github.py` | `get_branch`/`get_deploy_key`/`get_ssh_key`/`get_gpg_key` に 404 エラーテストがない |
| 8 | `test_gitlab.py`, `test_gitea.py` | view 系メソッド (`get_branch` 等) のテストが GitHub 以外に存在しない |
| 16 | 全アダプター | org scope `set_secret`/`set_variable` のアダプターレベルテストが欠如 |

### 軽微 (8 件)

| # | 箇所 | 内容 |
|---|---|---|
| 1 | `test_github.py` | search フィルタの body マッチテストがない |
| 6 | 各アダプター merge | title のみ指定時のテストが GitHub 以外にない |
| 9 | `test_gitlab.py` | webhook edit の active 変更テストがない |
| 10 | 各アダプター | release-asset edit に 404 テストがない |
| 11 | `test_webhook.py` | `json`/`pytest` のローカル import（スタイル不統一） |
| 14 | `test_ci.py` | `handle_watch` テストで `time.sleep` 呼び出しの assertion がない |
| 15 | `test_gitea.py` | CI 関連の 404 テスト、job_id テストが GitHub 側と比べて不足 |
| 17-20 | 各所 | subscribe 404、make_args の `org=None` 明示、sync_fork NotSupportedError テスト等 |
