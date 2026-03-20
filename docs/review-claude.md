# コードレビュー: ae32e09..b17aec5 (docs/todo.md 実装)

**レビュー日**: 2026-03-20
**対象**: 12 コミット、55 ファイル、+5,566 / -146 行
**テスト**: 2,552 → 3,154（+602 テスト追加、全パス）

---

## 総合評価

| カテゴリ | 評価 |
|---|---|
| CLI 一貫性 | ✅ 良好 — 既存パターンに完全準拠 |
| コード品質 | ✅ 良好 — base.py / adapter / commands 一貫したパターン |
| テスト品質 | ✅ 良好 — 602 テスト追加。主要パスは網羅 |
| ドキュメント | ⚠️ 要改善 — docs/commands.md が 12 コミット分未更新 |
| ルール準拠 | ✅ 良好 — .claude/rules/ にほぼ完全準拠 |

---

## Major

### M1. GitLab `update_webhook` で `active` が `enable_ssl_verification` にマッピングされている

- **ファイル**: `src/gfo/adapter/gitlab.py` (`update_webhook`)
- **内容**: `active` パラメータが `enable_ssl_verification` に変換されている。SSL 検証のオン/オフと webhook 有効/無効は別概念。ユーザーが `gfo webhook edit --inactive` を実行すると、webhook は無効にならず SSL 検証だけオフになる。
- **対象コミット**: `048c2f7`

### M2. `pr status` の `review-requested:` 検索クエリが GitHub 固有

- **ファイル**: `src/gfo/commands/pr.py` (`handle_status`)
- **内容**: `search=f"review-requested:{username}"` は GitHub Search API の構文。GitLab/Bitbucket/Gitea では解釈が異なり、「レビューリクエストされた PR」が正しく取得できない。
- **対象コミット**: `e9bd2fd`

### M3. `pr status` の `user["login"]` キーがサービスごとに異なる

- **ファイル**: `src/gfo/commands/pr.py` (`handle_status`)
- **内容**: `get_current_user()` の戻り値は `dict` で、キー名はサービス依存（GitHub: `login`、GitLab: `username`、Bitbucket: `nickname`）。GitHub 以外で KeyError になる。
- **対象コミット**: `e9bd2fd`

### M4. GitHub PR list のクライアント側フィルタと limit の相互作用

- **ファイル**: `src/gfo/adapter/github.py` (`list_pull_requests`)
- **内容**: `author`/`label`/`assignee`/`search` がクライアント側フィルタ。API から `limit` 件取得後にフィルタするため、マッチする PR が limit 以降にある場合、結果が 0 件になりうる。`02-adapter-common.md` の「フィルタ後に limit を適用」規約と不整合。
- **対象コミット**: `11a7f93`

### M5. update 系パラメータの silent ignore（警告なし）

- **ファイル**: 各アダプターの `update_pull_request` / `update_issue` / `merge_pull_request`
- **内容**: Azure DevOps・Backlog・Bitbucket で `add_labels`/`remove_labels`/`add_assignees`/`remove_assignees`/`milestone` が指定されても警告なしで無視される。list 系では `_warn_unsupported_params` が丁寧に実装されているのと対照的。
- **対象コミット**: `b040561`, `43ab22f`

### M6. GitHub `update_pull_request` の返却値が古い

- **ファイル**: `src/gfo/adapter/github.py` (`update_pull_request`)
- **内容**: `/pulls/{number}` を PATCH → `pr` 取得後、labels/assignees/milestone を `/issues/{number}` で別途更新。返却される `pr` はラベル更新前の状態。
- **対象コミット**: `b040561`

### M7. Gogs の `sync_fork` オーバーライド漏れ

- **ファイル**: `src/gfo/adapter/gogs.py`
- **内容**: Gogs は GiteaAdapter を継承するため、`sync_fork` が Gitea 実装をそのまま呼ぶ。しかし Gogs には `merge-upstream` API は存在せず、実行時に不明瞭な HTTP エラーになる。CI 系メソッドは全て `NotSupportedError` でオーバーライド済みなのに `sync_fork` のみ漏れ。
- **対象コミット**: `b17aec5`

### M8. `update_release_asset` の型アノテーション欠落

- **ファイル**: `src/gfo/adapter/github.py`, `gitea.py`, `gitlab.py`
- **内容**: `def update_release_asset(self, *, tag, asset_id, name=None):` と型注釈なし。base.py では `-> ReleaseAsset` と定義済み。`02-adapter-common.md` 違反。
- **対象コミット**: `048c2f7`

### M9. Gogs アダプター全般の型注釈省略

- **ファイル**: `src/gfo/adapter/gogs.py`
- **内容**: CI 系（`list_workflows`, `enable_workflow`, `download_run_logs` 等）やその他の新規オーバーライドで戻り値型・引数型が省略。mypy がオーバーライドの整合性を検出できない。
- **対象コミット**: `4fa6d3b`, `293a433`

---

## Minor

### m1. Bitbucket PR search のエスケープ不足

- **ファイル**: `src/gfo/adapter/bitbucket.py` (`list_pull_requests`)
- **内容**: `q_parts.append(f'title~"{search}"')` でダブルクォートのエスケープなし。issue list 側（`eb44644`）では `search.replace('"', '\\"')` でエスケープ済みなので不整合。
- **対象コミット**: `11a7f93`

### m2. Bitbucket issue list の `author` パラメータが silent ignore

- **ファイル**: `src/gfo/adapter/bitbucket.py` (`list_issues`)
- **内容**: `author` が指定されても `_warn_unsupported_params` に含まれず静かに無視。`milestone` のみ警告対象。
- **対象コミット**: `eb44644`

### m3. Backlog の `search` と `label` が排他的

- **ファイル**: `src/gfo/adapter/backlog.py` (`list_issues`)
- **内容**: `search` → `params["keyword"]`、`elif label:` → 同じキーに設定。同時指定時に `label` が無視されるが警告なし。
- **対象コミット**: `eb44644`

### m4. `label` と `add_labels` の潜在的競合

- **ファイル**: `src/gfo/adapter/github.py` (`update_issue`)
- **内容**: 既存の `label`（単一ラベルを上書き）と新規の `add_labels`/`remove_labels`（差分操作）が共存。同時指定時の優先順位が不明確。
- **対象コミット**: `b040561`

### m5. `ci workflow enable/disable` 成功メッセージ欠落

- **ファイル**: `src/gfo/commands/ci.py` (`_handle_workflow_enable`, `_handle_workflow_disable`)
- **内容**: 成功時に何も出力しない。規約「削除/書き込みハンドラは成功メッセージを `print()` すること」に違反。
- **対象コミット**: `4fa6d3b`

### m7. Azure DevOps `get_branch`/`get_tag` のプレフィックスマッチ曖昧性

- **ファイル**: `src/gfo/adapter/azure_devops.py`
- **内容**: refs API の `filter` は前方一致。`get_branch("main")` が `heads/main-v2` も返す可能性があり、`items[0]` を無条件に返す。
- **対象コミット**: `137de1c`

### m8. Forgejo の `sync_fork` API が TODO の計画と異なる

- **ファイル**: `src/gfo/adapter/gitea.py`（Forgejo は継承）
- **内容**: todo.md では Forgejo に `sync_fork/{branch}` エンドポイントを記載しているが、実装は Gitea と同じ `merge-upstream` を使用。Forgejo が実際にこのエンドポイントをサポートしているか要確認。
- **対象コミット**: `b17aec5`

### m9. `variable get` に `scope` パラメータ未追加

- **ファイル**: `src/gfo/cli.py`, `src/gfo/adapter/base.py`
- **内容**: `secret get` / `variable list` / `variable set` / `variable delete` には `--org` が追加されたが、`variable get` のみ未対応。
- **対象コミット**: `8928969`

---

## Nitpick

### n1. CLI の `--subject` と内部の `title` の命名不一致

- **ファイル**: `src/gfo/commands/pr.py` (`handle_merge`)
- **内容**: CLI は `--subject`/`--body`（git commit 慣習）、アダプター引数は `title`/`message`。意図的な設計だが対応が直感的でない。
- **対象コミット**: `43ab22f`

### n2. `ssh-key view`/`gpg-key view` の ID 引数が `type=int` 固定

- **ファイル**: `src/gfo/cli.py`
- **内容**: base.py のシグネチャは `key_id: int | str` だが、CLI は `type=int` のみ。Bitbucket 等で UUID 文字列の ID が渡せない。
- **対象コミット**: `137de1c`

### n3. `handle_sync_fork` の `jq` パラメータが未使用

- **ファイル**: `src/gfo/commands/repo.py`
- **内容**: シグネチャに `jq: str | None = None` があるが `output()` を使わず `print()` のみ。`--jq` フィルタが効かない。
- **対象コミット**: `b17aec5`

### n4. GitLab `update_release_asset` の `created_at` が空文字列固定

- **ファイル**: `src/gfo/adapter/gitlab.py`
- **内容**: `created_at=""` で返却。API が値を返さない制約かもしれないが、理由のコメントがない。
- **対象コミット**: `048c2f7`

---

## 肯定的評価

### 設計・アーキテクチャ

- **base.py 中心の規律**: 全コミットで抽象メソッドのシグネチャが先に変更され、9 アダプターが漏れなく追従。`NotSupportedError` デフォルトの一貫した適用。
- **データクラスの規約遵守**: `Workflow`/`Artifact` が `frozen=True, slots=True` パターンに準拠。
- **セキュリティ対策**: `download_artifact` でパストラバーサル防止（`os.path.realpath` チェック）が実装されている。

### コード品質

- **HTTP モックの精度**: `responses` で URL・メソッド・ボディ・クエリパラメータまで検証するテストが多い。
- **GitLab のラベル操作**: `add_labels`/`remove_labels` が API ネイティブのカンマ区切りで効率的（GET 不要）。
- **GitHub の PR/Issue 分離**: PR 更新は `/pulls`、ラベル等メタデータは `/issues` 経由。正しいアーキテクチャ。
- **`--draft`/`--no-draft` の三値設計**: `mutually_exclusive_group` + `default=None` で True/False/None を正しく表現。
- **org scope のヘルパーメソッド**: `_secrets_base_path`/`_variables_base_path` で DRY 原則に従った設計。

### テスト

- 602 テスト追加で全パス。コマンドハンドラとアダプターの両レイヤーにテストあり。
- `ci watch` テストで `time.sleep` を patch して高速実行。
- org scope テストでリクエスト先パスの切り替えを検証。

---

## 推奨アクション（優先度順）

| 優先度 | ID | 内容 |
|---|---|---|
| 🔴 高 | M1 | GitLab `update_webhook` の `active` マッピング修正 |
| 🔴 高 | M2+M3 | `pr status` のサービス間移植性修正（search クエリ + user キー） |
| 🔴 高 | M7 | Gogs に `sync_fork` の `NotSupportedError` オーバーライド追加 |
| 🟡 中 | M4 | GitHub PR list のクライアント側フィルタでページネーション対応 |
| 🟡 中 | M5 | update/merge 系に `_warn_unsupported_params` 追加 |
| 🟡 中 | M6 | GitHub `update_pull_request` でラベル更新後に re-fetch |
| 🟡 中 | M8+M9 | Gogs + `update_release_asset` の型アノテーション追加 |
| 🟡 中 | m5 | `ci workflow enable/disable` に成功メッセージ追加 |
| 🟢 低 | m1-m4,m7-m9 | その他 Minor 項目 |
| 🟢 低 | n1-n4 | Nitpick 項目 |
