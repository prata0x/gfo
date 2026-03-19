# レビュー指摘事項 Issue 一覧

**ソース**: `docs/review-1-src.md` 〜 `docs/review-5.md`（76b4712..c4fbefd）
**作成日**: 2026-03-19

---

## 高優先度（7件）

### #1 アカウント名のベアキー書き出しで credentials.toml が壊れる

**ファイル**: `src/gfo/auth.py` (`save_token`, `_write_credentials_toml`)
**出典**: review-1 I-2, review-5 #1

`_write_credentials_toml()` でアカウント名をクォートせずベアキーとして書き出している。TOML のベアキーは `[A-Za-z0-9_-]` のみ許可のため、`me@example.com` や `work.prod` のような自然なアカウント名で保存すると、次回の `load_tokens()` で parse エラーが発生しトークンが全滅する。

**再現確認済み**: `save_token("github.com", "token", account="me@example.com")` → `Expected '=' after a key` で読み込み不能。

**改善案**: アカウントキーを常にクォートするか、`save_token()` でアカウント名のバリデーションを行う。

> `_write_credentials_toml()` でアカウントキーを常にダブルクォートして書き出す（`f'"{key}" = ...'`）。バリデーションで制約するよりユーザーが使えるアカウント名の自由度を保てる。

---

### #2 予約キー `_default` をアカウント名として受け入れてしまう

**ファイル**: `src/gfo/auth.py` (`save_token`, `switch_account`, `remove_token`)
**出典**: review-1 W-2, review-4, review-5 #2

`save_token(host, token, account="_default")` を呼ぶと、内部メタデータキー `_default` と実データキーが衝突し、`list_accounts()` や `get_auth_status()` から見えない壊れた状態になる。`switch_account(host, "_default")` でも `_default = "_default"` という不正状態が発生する。

**再現確認済み**。

**改善案**: 各関数の入口で `if account == "_default": raise ConfigError(...)` を追加。

> `save_token`・`switch_account`・`remove_token` の先頭に `if account == "_default": raise ConfigError("'_default' is a reserved key and cannot be used as an account name.")` を追加。

---

### #3 アカウント解決で設定エラーを握りつぶし、意図しないアカウントへフォールバック

**ファイル**: `src/gfo/auth.py` (`_resolve_account_name`)
**出典**: review-1 I-4, review-5 #3

`_resolve_account_name()` が `git_config_get()` と `get_host_config()` の両方を `except Exception` で握りつぶしている。`config.toml` の parse 失敗や設定不整合が起きても `_default` へサイレントにフォールバックし、意図しないアカウントのトークンで API を叩く危険がある。

**改善案**: `except (GitCommandError, ConfigError, OSError, ImportError)` のように具体的な例外に限定する。

> git config 側を `except (GitCommandError, OSError)`、config.toml 側を `except (ConfigError, OSError)` に変更。`# nosec B110` コメントも削除。

---

### #4 `create_pull_request` 未対応パラメータのサイレント無視

**ファイル**: 複数アダプター（Bitbucket, Azure DevOps, Backlog, GitBucket, Gogs）
**出典**: review-1 C-2, review-4

`--reviewer`/`--assignee`/`--label`/`--milestone` を指定しても、未対応アダプターでは何も起きずエラーも警告も出ない。ユーザーが指定したオプションが反映されたか確認する手段がない。

| アダプター | reviewers | assignees | labels | milestone |
|---|---|---|---|---|
| Bitbucket | OK | 無視 | 無視 | 無視 |
| Azure DevOps | OK | 無視 | 無視 | 無視 |
| Backlog | 無視 | 無視 | 無視 | 無視 |
| GitBucket | 無視 | 無視 | 無視 | 無視 |
| Gogs | NotSupported | N/A | N/A | N/A |

**改善案**: 未対応パラメータが渡された場合 `warnings.warn()` で警告する共通パターンを導入する。

> 基底クラス `base.py` に `_warn_unsupported_params(**kwargs)` ヘルパーを追加し、未対応アダプターの `create_pull_request` 内で呼び出す。`warnings.warn(f"{self.service_name} does not support {param} on pull requests")` の形式。

---

### #5 旧形式 credentials.toml がサイレントに無視される

**ファイル**: `src/gfo/auth.py` (`load_tokens`)
**出典**: review-1 W-1, review-4

`load_tokens()` は `isinstance(v, dict)` でフィルタしており、旧形式のフラット値（`"github.com" = "ghp_xxx"`）は黙って無視される。既存ユーザーがアップデートすると設定済みトークンが「消える」ように見える。`feat!:` の breaking change だが、マイグレーション手段がない。

**改善案**: 旧形式を検出したら自動マイグレーションするか、warning を出して `gfo auth login` での再登録を促す。

> `load_tokens()` 内で `isinstance(v, str)` の旧形式エントリを検出したら `warnings.warn("credentials.toml contains old format entries (...). Run 'gfo auth login' to re-register.")` で通知。自動マイグレーションは行わない（トークンを暗黙に変換するリスクを避ける）。

---

### #6 `_write_credentials_toml` がアトミック書き込みではない

**ファイル**: `src/gfo/auth.py:295`
**出典**: review-1 C-1

書き込み途中でプロセスが中断するとファイルが不完全になり、すべてのトークンが失われる可能性がある。マルチアカウント対応で保存トークン数が増えたため影響が大きい。

**改善案**: 一時ファイルに書き込み後 `os.replace()` でアトミックにリネームする。

> `_write_credentials_toml()` で `tempfile.NamedTemporaryFile(mode="w", dir=path.parent, suffix=".tmp", delete=False)` に書き込み後、`os.replace(tmp_path, path)` でアトミックにリネーム。

---

### #7 `repo view --web OWNER/NAME` が明示したリポジトリを無視する

**ファイル**: `src/gfo/commands/repo.py` (`handle_view`)
**出典**: review-5 #4

`handle_view()` は `--web` が付くと早期 return し、`args.repo` を一切解釈しない。`gfo repo view other-owner/other-repo --web` は常に現在コンテキストのリポジトリ URL を開く。テストも `repo=None` ケースしか検証していない。

**改善案**: `--web` パスでも `args.repo` を解釈し、指定されたリポジトリの URL を開くようにする。

> `--web` パスで `args.repo` がある場合は `get_repository(owner, name)` で取得し `webbrowser.open(repo.url)` で開く。`args.repo` がない場合は現状通り `get_web_url("repo")` を使う。

---

## 中優先度（11件）

### #8 GitHub `create_pull_request` の返却値が PATCH 前の状態

**ファイル**: `src/gfo/adapter/github.py:91-103`
**出典**: review-1 W-3, review-4

PR 作成後に labels/assignees/milestone を PATCH しているが、返却する `pr` オブジェクトは PATCH 前の状態。`output(pr, ...)` でラベルやマイルストーンが表示に反映されない。

**改善案**: PATCH 後に `get_pull_request(pr.number)` で再取得するか、PATCH レスポンスから再構築する。

> PATCH/POST 後に `return self.get_pull_request(pr.number)` で再取得して返す。APIコール1回追加だが確実でシンプル。

---

### #9 `comment.py` / `review.py` で `SystemExit` を使用

**ファイル**: `src/gfo/commands/comment.py:28`, `src/gfo/commands/review.py:56`
**出典**: review-1 W-4

サブコマンド未指定時のエラーで `SystemExit` を使用。他のディスパッチは `ConfigError` を使用しており不統一。`SystemExit` は `cli.py` の `main()` でキャッチされず、`--format json` 時に構造化エラー出力がバイパスされる。

**改善案**: `SystemExit` を `ConfigError` に変更する。

> `comment.py:28` と `review.py:56` の `raise SystemExit(...)` を `raise ConfigError(...)` に変更。`comment.py` は既に `ConfigError` を import していないので import 追加が必要。

---

### #10 `comment.py` の delete 成功メッセージ欠落

**ファイル**: `src/gfo/commands/comment.py:25-26`
**出典**: review-1 W-5

`action == "delete"` 時に成功メッセージが表示されない。他の全 delete コマンド（label, milestone, wiki, release asset 等）は成功メッセージを出力しており不統一。

> delete 後に `print(_("Deleted comment '{comment_id}'.").format(comment_id=args.comment_id))` を追加。

---

### #11 `comment.py` のアダプター初期化タイミング

**ファイル**: `src/gfo/commands/comment.py:14`
**出典**: review-1 W-6

`_dispatch()` の最初で `get_adapter()` を呼んでおり、`action` が `None` の場合でもアダプター初期化が走る。`review.py` では action 判定後に初期化する設計で不統一。

**改善案**: action が `None` の場合は先にエラーを返す。

> `_dispatch()` で `action = getattr(...)` の直後、`get_adapter()` の前に `else: raise ConfigError(...)` ブロックを移動する。

---

### #12 Gitea の `milestone` Web URL が単数形で誤り

**ファイル**: `src/gfo/adapter/gitea.py:1362`
**出典**: review-1 W-7

`f"{base}/milestone/{number}"` だが、Gitea の Web UI は `/milestones/{number}`（複数形）。

**改善案**: `f"{base}/milestones/{number}"` に修正。

> `gitea.py:1362` の `/milestone/` を `/milestones/` に修正。Forgejo/Gogs の同箇所も同様の問題がないか確認。

---

### #13 `_write_credentials_toml` の write 失敗時のエラーハンドリング不統一

**ファイル**: `src/gfo/auth.py:295`
**出典**: review-1 W-8

`load_tokens` では `OSError` を `ConfigError` でラップしているが、write 側は生の `OSError` が漏れる。

**改善案**: `try/except OSError` で `ConfigError` にラップして一貫性を保つ。

> `_write_credentials_toml()` の書き込み処理を `try/except OSError as e: raise ConfigError(f"Failed to write credentials file {path}: {e}") from e` でラップ。

---

### #14 spec.md が実装と不整合（6箇所）

**ファイル**: `docs/spec.md`
**出典**: review-3 P1 #1-6

以下が旧仕様のまま残存:
1. `pr merge` が旧 `--method` 形式（実装は `--merge`/`--squash`/`--rebase` 個別フラグ）
2. `pr create` に `--reviewer`/`--assignee`/`--label`/`--milestone`/`--fill` が未記載
3. `auth login` に `--account` が未記載
4. `auth switch` / `auth logout` サブコマンドが未記載
5. credentials.toml が旧フラット形式のまま
6. トークン解決順序にアカウント解決ステップが欠落

> spec.md の該当 6 箇所を `cli.py` の実装と `authentication.md` に合わせて一括更新。#34 の「edit 将来対応」注記の削除もこの issue で対応する。

---

### #15 cli-comparison.md「レビューは独立コマンド」が不正確

**ファイル**: `docs/cli-comparison.md:386`
**出典**: review-3 P1 #7

`gfo review` は廃止され `gfo pr review` に移動済みだが、「レビューは独立コマンド」と記載。同じファイル内の L57 では正しく `Y (pr 内)` と記載されており矛盾。

> L386 の記述を「コメント・レビューとも pr/issue サブコマンド」に修正。

---

### #16 テスト関数名 `test_dispatch_table_has_68_entries` がアサート値 145 と乖離

**ファイル**: `tests/test_cli.py:514`
**出典**: review-2, review-4

関数名が `68_entries` のままだが実際のアサート値は `145`。

**改善案**: `test_dispatch_table_entry_count()` のような汎用名にリネーム。

> `test_dispatch_table_has_68_entries` を `test_dispatch_table_entry_count` にリネーム。コメントの `# auth logout 追加` も削除。

---

### #17 auth コマンドの JSON 出力テスト不足

**ファイル**: `tests/test_commands/test_auth_cmd.py`
**出典**: review-2

以下の `fmt="json"` テストが欠落（テスト規約 `10-testing.md` の必須パターン）:
- `auth logout` の JSON 出力
- `auth switch` の JSON 出力
- `auth status` の複数アカウント時 JSON 出力

> `tests/test_commands/test_auth_cmd.py` に上記 3 件の `fmt="json"` テストを追加。auth logout/switch は print 出力なので capsys で検証、auth status は `output()` の JSON モードを検証。

---

### #18 ContextVar テストのクリーンアップ改善

**ファイル**: `tests/test_auth.py:117-131, 156-175`
**出典**: review-2

ContextVar のリセットが `try/finally` 依存。pytest の `monkeypatch` や共通フィクスチャ化で安全かつ簡潔になる。

> **対応しない** — `try/finally` で正しく動作しており実害なし。リファクタリングの域を超えず、中優先度の対応コストに見合わない。

---

## 低優先度（19件）

### #19 `_default` 自動切り替えの順序が dict 挿入順に依存

**ファイル**: `src/gfo/auth.py:136-138`
**出典**: review-1 I-1

`remove_token` 後の次のデフォルト選択が `remaining[0]` で dict 挿入順依存。`sorted(remaining)[0]` にして決定論的にするか、ドキュメントで明記。

> **対応しない** — Python 3.7+ で dict は挿入順保証。挙動が不安定なのではなく「どのアカウントが選ばれるか予測しにくい」だけで、実害なし。

---

### #20 `_resolve_account_name` の遅延 import

**ファイル**: `src/gfo/auth.py:315,325`
**出典**: review-1 I-3, review-4

`gfo.config` はモジュール冒頭で既にインポート済みだが、`get_host_config` は冒頭に含まれていない。`gfo.git_util` の遅延 import は循環依存回避のため妥当。

> **対応しない** — `gfo.git_util` の遅延 import は循環依存回避で必要。`gfo.config` も同ブロック内で統一されており、Python のモジュールキャッシュにより実行時のパフォーマンス影響はない。

---

### #21 アカウント未登録時のエラーメッセージが不明確

**ファイル**: `src/gfo/auth.py:52-56`
**出典**: review-1 I-5

`--account work` で未登録アカウントを指定した場合「トークン未設定」としか見えない。`AuthError(f"Account '{account_name}' not found for host: {host}")` のような明確なメッセージが望ましい。

> `resolve_token()` 内で `host_accounts` にアカウントが見つからなかった場合、ContextVar 由来のアカウント名を含む `AuthError` を raise する。

---

### #22 `_escape_toml_value` が DEL 文字 (`\x7f`) をエスケープしない

**ファイル**: `src/gfo/auth.py:247-251`
**出典**: review-1 I-6

TOML 仕様上 DEL は制御文字だが、トークン値に含まれることはほぼなく実害は極めて低い。

> **対応しない** — API トークンに DEL 文字 (`\x7f`) が含まれることは事実上ない。仕様上の網羅性の問題であり実害なし。

---

### #23 Gitea `_resolve_label_ids` の `limit=0` の互換性リスク

**ファイル**: `src/gfo/adapter/gitea.py:106-117`
**出典**: review-1 I-7

`params={"limit": 0}` の挙動は Gitea API バージョンで異なる可能性がある。十分大きい値（50 や 100）の明示かページネーションが望ましい。

> **対応しない** — Gitea 公式ドキュメントで `limit=0` は全件取得と定義されており、現状動作に問題なし。将来 API 仕様が変わった場合に対応。

---

### #24 GitLab `create_release` で `ref` が常に設定される

**ファイル**: `src/gfo/adapter/gitlab.py:490`
**出典**: review-1 I-8

既存タグに対してリリースを作成する場合 `ref` は不要だが常に設定される。GitLab はエラーにしないため実害は低く、変更前からの挙動。

> **対応しない** — GitLab API が `ref` の余分な指定をエラーにしない。変更前からの挙動であり実害なし。

---

### #25 `pr merge` で `--merge` フラグの True/False が参照されない

**ファイル**: `src/gfo/commands/pr.py:66-80`
**出典**: review-1 I-9

`--squash` でも `--rebase` でもなければ `"merge"` がデフォルトになる設計。`--merge` を明示指定しても `args.merge` は参照されない。相互排他グループで排他性は担保されており動作上問題なし。

> **対応しない** — `mutually_exclusive_group` で排他性は担保済み。「フラグなし → merge」のデフォルト設計として妥当で、`args.merge` を参照しなくても正しく動作する。

---

### #26 milestone close/reopen に成功メッセージがない

**ファイル**: `src/gfo/commands/milestone.py:73-82`
**出典**: review-1 I-10

`adapter.update_milestone()` を呼ぶだけで何も出力しない。`pr close` や `issue close` は成功メッセージを出力しており不統一。

> `handle_close` に `print(_("Closed milestone '{number}'.").format(number=args.number))`、`handle_reopen` に `print(_("Reopened milestone '{number}'.").format(number=args.number))` を追加。

---

### #27 `_OUTPUT_MAP` に `("schema", None)` がない

**ファイル**: `src/gfo/commands/schema.py`
**出典**: review-1 I-11

schema コマンドは自前で出力するため実害なし。

> **対応しない** — schema コマンドは `_OUTPUT_MAP` を参照せず自前で JSON 出力する。エントリを追加しても動作に影響しない。

---

### #28 GitHub `_resolve_milestone_number` の全件取得

**ファイル**: `src/gfo/adapter/github.py:105-110`
**出典**: review-1 I-12

全マイルストーンを取得して線形探索。マイルストーンが多い場合のパフォーマンス懸念だが、通常利用では問題にならない。

> **対応しない** — マイルストーンが数百を超えるプロジェクトは極めて稀。GitHub API にタイトル検索パラメータもなく、現状の実装が最もシンプル。

---

### #29 schema.py の OUTPUT_MAP 型が実際の戻り値と不一致

**ファイル**: `src/gfo/commands/schema.py`
**出典**: review-4

`("pr", "comment")` と `("issue", "comment")` の型が `list[Comment]` だが、`create`/`edit` 時は単一 `Comment`、`delete` 時は `None`。`("pr", "review")` も同様。schema が動的利用されていなければ実害なし。

> **対応しない** — `_OUTPUT_MAP` は `gfo schema` コマンドの参考出力にのみ使用され、実行時バリデーションに使われていない。アクション別に型を分岐させる構造変更は過剰。

---

### #30 webbrowser.open の処理パターンが 6+ 箇所で重複

**ファイル**: `src/gfo/commands/pr.py`, `issue.py`, `milestone.py`, `release.py`, `repo.py`
**出典**: review-4

各コマンドハンドラで `--web` の処理が同じパターンでインライン実装されている。ただし引数の取り方が微妙に異なるため、共通化するとかえって複雑になる可能性もあり現状許容範囲。

> **対応しない** — 各ハンドラで引数の取り方が異なる（`args.number`, `args.tag`, `None`, `--latest` 付きの事前取得等）。共通化は条件分岐の押し込みになり、かえって複雑化する。

---

### #31 `save_token` のホスト名小文字正規化の有無が不明確

**ファイル**: `src/gfo/auth.py`
**出典**: review-4

`resolve_token()` は `host = host.lower()` で正規化しているが、`save_token()` 内に `host.lower()` があるか不明確。テストは通っているが実装の確認が必要。

> **対応しない** — `save_token()` の line 78 に `host = host.lower()` が存在することを確認済み。レビューの見落としであり、問題は存在しない。

---

### #32 `init --account` の用途がドキュメント不足

**ファイル**: `src/gfo/commands/init.py`
**出典**: review-4

ヘルプメッセージが `"Account name to associate"` のみで、マルチアカウント機能との関係が分かりにくい。

> **対応しない** — `authentication.md` / `authentication.ja.md` にマルチアカウントのワークフロー説明があり、`git config gfo.account` の役割も記載済み。ヘルプ改善は nice-to-have。

---

### #33 cli-alignment.md のステータス更新漏れ

**ファイル**: `docs/cli-alignment.md`
**出典**: review-3 P2 #8-10

以下が未反映:
- サマリーテーブルに実装済み項目（#4 merge フラグ, #5 --web, #8 multi-account, #9 auth logout）の完了マーカーなし
- セクション 4（--web）とセクション 6（release create --target）に ✅ マーカーなし
- セクション 1, 2 の「現状」テキストが更新前のまま

> サマリーテーブルの全実装済み項目に `(完了済み)` を追加。セクション 1, 2, 4, 6 の見出しに ✅ を付与し、「現状」テキストに取り消し線を追加。他の完了セクション（3, 5, 7）と同じ形式に揃える。

---

### #34 spec.md「edit を将来バージョンで対応予定」注記が不正確

**ファイル**: `docs/spec.md:315`
**出典**: review-3 P2 #11

`edit`（旧 `update`）は全リソースで実装済みだが「将来バージョンで対応予定」と記載されたまま。

> #14 の spec.md 一括更新で対応。該当注記を削除する。

---

### #35 roadmap のステータスが未更新

**ファイル**: `docs/roadmap/8-auth-multi-account.md`, `docs/roadmap/9-auth-logout.md`
**出典**: review-3 P3 #12-13

両機能とも実装済みだが、ロードマップが「これから実装する」形式のまま。特に `9-auth-logout.md` は関数シグネチャ（`remove_token` の引数）やコマンドオプション（`--account`）が実装と乖離している。

> 両ファイルの先頭に `> **ステータス: 実装済み** (c4fbefd)` を追加。本文の書き換えは行わない（ロードマップとしての履歴価値を維持）。

---

### #36 ディスパッチテーブルキー一覧の手動管理

**ファイル**: `tests/test_cli.py:518-622`
**出典**: review-2

`test_dispatch_table_all_keys` のキー一覧が手動管理されており、コマンド追加・削除時に更新漏れが起きやすい。今回の変更範囲では正しく更新されている。

> **対応しない** — 今回の変更で正しく更新済み。手動管理のテスト設計改善は別タスクの範囲。

---

### #37 テストカバレッジ不足（組み合わせ・エッジケース）

**ファイル**: `tests/`
**出典**: review-2

以下のテストが不足:
- `pr merge` の `--squash --rebase` 同時指定時バリデーション
- `--web` + `--format json` の組み合わせ動作
- `resolve_token` の `git_config_get` が例外を投げた場合のフォールバック

> `--web + --format json` と `resolve_token` fallback 失敗パスのテストを追加。`pr merge` 複数フラグは argparse の `mutually_exclusive_group` が担保するためテスト不要。
