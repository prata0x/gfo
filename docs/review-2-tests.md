# テストコードレビュー: 76b4712..c4fbefd

**対象コミット範囲**: 76b4712 → c4fbefd（10 コミット）
**レビュー日**: 2026-03-19
**対象**: tests/ ディレクトリ（23 ファイル、+1928/-119 行）

## 対象コミット一覧

| コミット | 内容 |
|---|---|
| 83669f8 | `update` → `edit` リネーム |
| b0ce8f4 | `comment` を pr/issue サブコマンドに移動 |
| 2b28bc4 | `review` を pr サブコマンドに移動 |
| 90d12b3 | `pr merge --method` → `--merge/--squash/--rebase` 個別フラグ |
| e897578 | `view/list` に `--web/-w` オプション追加 |
| 15a4255 | `pr create` に `--reviewer/--assignee/--label/--milestone/--fill` 追加 |
| b974ec1 | `release create` に `--target` 追加 |
| 2a740c5 | docs のみ（テスト変更なし） |
| 2638849 | credentials.toml マルチアカウント新形式 |
| c4fbefd | `auth logout` サブコマンド追加 |

---

## 総合評価

**良好**。テストは全体的に高品質で、各機能追加に対して十分なカバレッジが確保されている。テスト規約（`.claude/rules/10-testing.md`）にも概ね準拠している。以下に詳細な指摘事項をまとめる。

---

## 良い点

### 1. 網羅的なマルチアカウントテスト（test_auth.py）

- `resolve_token` のアカウント解決を **ContextVar > git config > config.toml > _default** の全4層で個別テスト
- 優先度の検証テスト (`test_resolve_token_priority_contextvar_over_git_config`) も含む
- `remove_token` のエッジケース（最後のアカウント削除、_default シフト）もカバー
- ヘルパー `_new_format_toml()` / `_multi_host_toml()` でテストデータ生成を DRY に保持

### 2. 破壊的変更に伴うテスト移行が確実

- `update` → `edit` リネーム: 全 8 コマンド（pr/issue/repo/release/label/milestone/wiki/comment）のテストクラス名・メソッド呼び出しを漏れなく更新
- `comment` のサブコマンド化: `TestHandleList/Create/Update/Delete` → `TestHandlePrComment/TestHandleIssueComment` に再構成し、PR/Issue 両方のパスをテスト
- `review` のサブコマンド化: `TestHandleReview` ディスパッチャテストを新規追加
- `pr merge --method` → 個別フラグ: `test_squash_method` / `test_rebase_method` を更新

### 3. --web オプションのテストパターンが統一

- `TestHandleListWeb` / `TestHandleViewWeb` を pr/issue/release/milestone/repo の 5 コマンドに追加
- 各クラスで「ブラウザが開く」「API が呼ばれない」の 2 観点を統一的にテスト
- `test_browse.py` に全 9 アダプターの URL 生成テスト（list/detail 両方）を網羅

### 4. pr create の新オプションテスト

- `--reviewer/--assignee/--label/--milestone` を各アダプター (GitHub/GitLab/Bitbucket/Gitea/Azure DevOps/Backlog/GitBucket) で個別テスト
- 非対応オプションが無視されることの検証 (`test_create_ignores_unsupported_options`) も全サービスで実施
- `--fill` の body 自動設定・既存 body の非上書きの両ケースをテスト

---

## 指摘事項

### [重要度: 中] テスト関数名とコメントの不一致

**ファイル**: `tests/test_cli.py:514`

```python
def test_dispatch_table_has_68_entries():
    assert len(_DISPATCH) == 145  # auth logout 追加
```

関数名が `68_entries` のままだが、実際のアサート値は `145`。このコミット範囲で 147 → 145 に変更されているが（comment/review コマンドの統合により減少）、**関数名が元々のエントリ数から更新されていない**。テスト自体は通るが、可読性の問題がある。

**推奨**: `test_dispatch_table_entry_count()` のような汎用名にリネームする。

---

### [重要度: 中] ContextVar テストのクリーンアップが try/finally 依存

**ファイル**: `tests/test_auth.py:117-131`, `tests/test_auth.py:156-175`

```python
token = cli_account.set("work")
try:
    assert resolve_token("github.com", "github") == "tok-work"
finally:
    cli_account.reset(token)
```

正しく動作するが、pytest の `monkeypatch` でラップするか、共通フィクスチャ化すれば安全かつ簡潔になる。

**推奨**: `test_cli.py:test_main_sets_context_var_account` では `main()` 内部でリセットされることを検証しているので問題ないが、`test_auth.py` 側は pytest フィクスチャ化を検討。

---

### [重要度: 中] test_commands/test_comment.py の `test_no_action_raises` の検証対象

**ファイル**: `tests/test_commands/test_comment.py:46-49`, `93-96`

```python
def test_no_action_raises(self):
    with patch_adapter("gfo.commands.comment"):
        args = make_args(comment_action=None)
        with pytest.raises(SystemExit):
            comment_cmd.handle_pr_comment(args, fmt="table")
```

`SystemExit` を期待しているが、これは `argparse` のエラーハンドリングに依存している可能性がある。`GfoError` や `ConfigError` などのアプリケーション例外のほうが意図が明確。実装側が `sys.exit()` を直接呼んでいるなら問題ないが、例外型を確認すべき。

---

### [重要度: 低] auth テストの `_multi_host_toml` 使用箇所が少ない

**ファイル**: `tests/test_auth.py:19-23`

`_multi_host_toml()` ヘルパーが定義されているが、使用箇所は `test_load_tokens_success` の 1 箇所のみ。他のマルチホストテストケースが不足しているというわけではないが、`_new_format_toml` で十分カバーできるケースが多い。ヘルパーの存在自体は将来のテスト追加に有用。

---

### [重要度: 低] release view の --web テストで --latest パスの API 呼び出し確認

**ファイル**: `tests/test_commands/test_release.py:442-450`

```python
def test_opens_browser_with_latest(self, sample_config):
    args = make_args(tag=None, latest=True, web=True)
    ...
    self.adapter.get_latest_release.assert_called_once()
    self.adapter.get_web_url.assert_called_once_with("release", "v1.0.0")
```

`--latest --web` の場合、最新リリースの tag を取得するために `get_latest_release` が呼ばれることを検証している。これは正しい動作だが、`--web` 時に `get_release` が呼ばれないことは `test_does_not_call_get_release` で検証済み。整合性が取れている。

---

### [重要度: 低] Backlog の create_pull_request テストで statuses モック追加

**ファイル**: `tests/test_adapters/test_backlog.py:352-356`

```python
mock_responses.add(
    responses.GET,
    f"{BASE}/projects/TEST/statuses",
    json=[{"id": 5, "name": "Merged"}],
    status=200,
)
```

`test_create_ignores_extra_options` で statuses エンドポイントのモックが追加されている。Backlog アダプターの `create_pull_request` 実装が内部で statuses を取得する必要があるため正しいが、他の Backlog PR 作成テストにはこのモックがない場合、`assert_all_requests_are_fired=True` に注意が必要。テスト自体は通っているので問題なし。

---

### [重要度: 低] test_cli.py のディスパッチテーブルキー一覧の可読性

**ファイル**: `tests/test_cli.py:518-622`

`test_dispatch_table_all_keys` のキー一覧は手動管理されている。コマンド追加・削除時に更新を忘れやすい。ただし、これは既存のテスト設計上の問題で、今回の変更範囲では正しく更新されている（`auth switch/logout` 追加、`comment/review` の移動反映）。

---

## テストカバレッジ分析

### 十分にカバーされている領域

| 領域 | テスト数（追加） | 評価 |
|---|---|---|
| マルチアカウント (auth) | +28 テスト | 優秀 |
| --web オプション (browse) | +14 テスト (browse) + 各コマンド | 優秀 |
| pr create オプション | +10 テスト (コマンド) + 各アダプター | 優秀 |
| release --target | +各アダプター2テスト | 十分 |
| edit リネーム | 既存テストの修正 | 十分 |
| comment/review 移動 | +ディスパッチャテスト | 十分 |
| pr merge フラグ変更 | 既存テストの修正 + rebase 追加 | 十分 |

### テスト不足の可能性がある領域

| 領域 | 現状 | 推奨 |
|---|---|---|
| `auth logout` の JSON 出力 | テストなし | `fmt="json"` テストを追加（テスト規約の必須パターン） |
| `auth switch` の JSON 出力 | テストなし | 同上 |
| `auth status` の JSON 出力（マルチアカウント）| テストなし | 複数アカウント時の JSON 出力を検証 |
| `pr merge` の複数フラグ同時指定 | テストなし | `--squash --rebase` 同時指定時のバリデーションテスト |
| `--web` + `--format json` の組み合わせ | テストなし | JSON モードで --web 指定時の動作を検証 |
| `resolve_token` の git config fallback 失敗パス | テストなし | `git_config_get` が例外を投げた場合 |

---

## まとめ

- テスト品質は高く、破壊的変更に伴うテスト更新も漏れなく実施されている
- マルチアカウント機能は特に入念にテストされており、優先度チェーンの各層を個別に検証
- `--web` オプションは全サービス × 全リソースタイプの URL 生成を網羅
- 主な改善点は `fmt="json"` テストの追加（テスト規約の必須パターン）と、関数名の整合性修正
