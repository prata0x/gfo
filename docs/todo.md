# issues.md 対応作業 TODO

**ソース**: `docs/issues.md`（対応必要 23件）

---

## Batch 1: auth.py 一括修正

**対象**: #1, #2, #3, #5, #6, #13
**ファイル**: `src/gfo/auth.py`

- [ ] #1 `_write_credentials_toml()` でアカウントキーをダブルクォートして書き出す
- [ ] #2 `save_token`・`switch_account`・`remove_token` で `_default` アカウント名を拒否
- [ ] #3 `_resolve_account_name` の `except Exception` を具体的な例外に限定
- [ ] #5 `load_tokens()` で旧形式エントリ検出時に `warnings.warn()` で通知
- [ ] #6 `_write_credentials_toml()` を `tempfile` + `os.replace()` でアトミック化
- [ ] #13 `_write_credentials_toml()` の書き込みを `try/except OSError` → `ConfigError` でラップ

---

## Batch 2: コマンドハンドラ小修正

**対象**: #7, #9, #10, #11, #12, #21, #26
**ファイル**: `comment.py`, `review.py`, `repo.py`, `gitea.py`, `milestone.py`, `auth.py`（微修正）

- [ ] #9 `comment.py:28` と `review.py:56` の `SystemExit` → `ConfigError`
- [ ] #10 `comment.py` の delete 後に成功メッセージを追加
- [ ] #11 `comment.py` `_dispatch()` で action=None チェックを `get_adapter()` の前に移動
- [ ] #7 `repo.py` `handle_view` の `--web` パスで `args.repo` を解釈
- [ ] #12 `gitea.py:1362` の `/milestone/` → `/milestones/`（Forgejo/Gogs も確認）
- [ ] #21 `auth.py` `resolve_token` で未登録アカウント名を含むエラーメッセージに改善
- [ ] #26 `milestone.py` `handle_close`/`handle_reopen` に成功メッセージを追加

---

## Batch 3: create_pull_request 改善

**対象**: #4, #8
**ファイル**: `base.py`, `bitbucket.py`, `azure_devops.py`, `backlog.py`, `gitbucket.py`, `github.py`

- [ ] #4 `base.py` に `_warn_unsupported_params()` ヘルパーを追加し、未対応アダプターで呼び出す
- [ ] #8 GitHub `create_pull_request` で PATCH/POST 後に `get_pull_request(pr.number)` で再取得

---

## Batch 4: テスト改善

**対象**: #16, #17, #37
**ファイル**: `test_cli.py`, `test_auth_cmd.py` 他

- [ ] #16 `test_dispatch_table_has_68_entries` → `test_dispatch_table_entry_count` にリネーム
- [ ] #17 auth logout/switch/status の `fmt="json"` テストを追加
- [ ] #37 `--web + --format json` と `resolve_token` fallback 失敗パスのテストを追加

---

## Batch 5: ドキュメント更新

**対象**: #14, #15, #33, #34, #35
**ファイル**: `spec.md`, `cli-comparison.md`, `cli-alignment.md`, `roadmap/` 2ファイル

- [ ] #14+#34 `spec.md` を実装に合わせて一括更新（6箇所 + 「edit 将来対応」注記削除）
- [ ] #15 `cli-comparison.md:386` の記述を修正
- [ ] #33 `cli-alignment.md` のサマリーテーブル・セクション見出し・「現状」テキストを更新
- [ ] #35 `roadmap/8-auth-multi-account.md` と `9-auth-logout.md` の先頭にステータスを追加
