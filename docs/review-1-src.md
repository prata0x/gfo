# コードレビュー: src/ (76b4712..c4fbefd)

**対象コミット**: 76b4712 → c4fbefd（10 コミット）
**レビュー日**: 2026-03-19
**対象**: `src/gfo/` 配下 25 ファイル（+806 / -281 行）

## 対象コミット一覧

| コミット | 概要 |
|---|---|
| `83669f8` | feat!: update サブコマンドを edit にリネーム（全 8 コマンド） |
| `b0ce8f4` | feat!: comment コマンドを pr/issue サブコマンドに移動 |
| `2b28bc4` | feat!: review コマンドを pr サブコマンドに移動 |
| `90d12b3` | feat!: pr merge の --method を --merge/--squash/--rebase 個別フラグに変更 |
| `e897578` | feat: view/list サブコマンドに --web/-w オプションを追加 |
| `15a4255` | feat: pr create に --reviewer/--assignee/--label/--milestone/--fill オプションを追加 |
| `b974ec1` | feat: release create に --target オプションを追加 |
| `2a740c5` | docs: auth-multi-account ロードマップ追加 & auth-logout をリナンバー |
| `2638849` | feat!: credentials.toml をマルチアカウント対応の新形式に変更 |
| `c4fbefd` | feat: auth logout サブコマンドを追加 |

---

## Critical (2件)

### C-1. `_write_credentials_toml` がアトミック書き込みではない

**ファイル**: `src/gfo/auth.py:295`

```python
path.write_text("\n".join(lines) + "\n", encoding="utf-8")
```

書き込み途中でプロセスが中断（クラッシュ、SIGKILL、電源断）すると `credentials.toml` が不完全な状態になり、すべてのトークンが失われる可能性がある。マルチアカウント対応でファイルに保存されるトークン数が増えたため影響が大きい。

**改善案**: 一時ファイルに書き込み後 `os.replace()` でアトミックにリネームする。

```python
import tempfile
with tempfile.NamedTemporaryFile(
    mode="w", dir=path.parent, suffix=".tmp",
    delete=False, encoding="utf-8"
) as tmp:
    tmp.write("\n".join(lines) + "\n")
    tmp_path = Path(tmp.name)
os.replace(tmp_path, path)
```

---

### C-2. `create_pull_request` 新パラメータのサイレント無視

**ファイル**: 複数アダプター

`--reviewer`/`--assignee`/`--label`/`--milestone` を指定しても、一部アダプターでは何も起きず、エラーも警告も出ない。

| アダプター | reviewers | assignees | labels | milestone |
|---|---|---|---|---|
| GitHub | OK | OK | OK | OK |
| GitLab | OK | OK | OK | OK |
| Gitea/Forgejo | OK | OK | OK | OK |
| Bitbucket | OK | **無視** | **無視** | **無視** |
| Azure DevOps | OK | **無視** | **無視** | **無視** |
| Backlog | **無視** | **無視** | **無視** | **無視** |
| GitBucket | **無視** | **無視** | **無視** | **無視** |
| Gogs | NotSupported | N/A | N/A | N/A |

**改善案**: サポートしていないパラメータが渡された場合 `warnings.warn()` で警告する共通パターンを導入する。

```python
if labels:
    warnings.warn(f"{self.service_name} does not support labels on pull requests")
```

---

## Warning (8件)

### W-1. 旧形式 credentials.toml の自動マイグレーションが存在しない

**ファイル**: `src/gfo/auth.py` (`load_tokens` 164-168行)

`load_tokens()` は `isinstance(v, dict)` でフィルタしており、旧形式のフラット値（`"github.com" = "ghp_xxx"`）は黙って無視される。コミットメッセージに `feat!:` と書かれているので意図的な breaking change だが、旧ユーザーのトークンがサイレントに読み込まれなくなる。

**改善案**: 旧形式を検出したら自動マイグレーション、または warning を出してユーザーに通知する。

---

### W-2. `_default` 予約語のバリデーション欠如

**ファイル**: `src/gfo/auth.py:74,95,120`

`save_token()`, `switch_account()`, `remove_token()` で `account="_default"` のバリデーションがない。`save_token("github.com", "tok", account="_default")` を呼ぶと、メタデータキーと実データキーが衝突しデータ破損を引き起こす。

**改善案**: 各関数の入口で `if account == "_default": raise ConfigError(...)` を追加。

---

### W-3. GitHub `create_pull_request` の返却値が PATCH 前の状態

**ファイル**: `src/gfo/adapter/github.py:91-103`

PR 作成後に labels/assignees/milestone を PATCH しているが、返却する `pr` オブジェクトは PATCH 前の状態のまま。呼び出し元 (`pr.py:39-49`) が `output(pr, ...)` でそのまま出力するため、ラベルやマイルストーンが表示に反映されない。

**改善案**: PATCH 後に `get_pull_request(pr.number)` で再取得するか、PATCH レスポンスから再構築する。

---

### W-4. `comment.py` / `review.py` で `SystemExit` を使用

**ファイル**: `src/gfo/commands/comment.py:28`, `src/gfo/commands/review.py:56`

サブコマンド未指定時のエラーで `SystemExit` を使用。他のサブサブコマンドディスパッチ（issue reaction, release asset 等）はすべて `ConfigError` を使用。`SystemExit` だと `cli.py` の `main()` でキャッチされず、`--format json` 時に構造化エラー出力がバイパスされる。

**改善案**: `SystemExit` を `ConfigError` に変更する。

---

### W-5. `comment.py` の delete 成功メッセージ欠落

**ファイル**: `src/gfo/commands/comment.py:25-26`

`action == "delete"` のとき成功メッセージが表示されない。他の全 delete コマンド（label, milestone, wiki, release asset 等）は成功メッセージを表示しており不統一。

**改善案**: `print(_("Deleted comment '{comment_id}'.").format(comment_id=args.comment_id))` を追加。

---

### W-6. `comment.py` のアダプター初期化タイミング

**ファイル**: `src/gfo/commands/comment.py:14`

`_dispatch()` の最初で `get_adapter()` を呼んでおり、`action` が `None`（サブコマンド未指定）の場合でもアダプター初期化（ネットワーク検出等を含みうる）が走る。`review.py` では action 判定後に各ハンドラ内で初期化する設計で不統一。

**改善案**: action が `None` の場合は先にエラーを返す。

---

### W-7. Gitea の `milestone` Web URL が単数形で誤り

**ファイル**: `src/gfo/adapter/gitea.py:1362`

`f"{base}/milestone/{number}"` となっているが、Gitea の Web UI は `/milestones/{number}`（複数形）を使用する。

**改善案**: `f"{base}/milestones/{number}"` に修正。

---

### W-8. `_write_credentials_toml` の write 失敗時のエラーハンドリング不統一

**ファイル**: `src/gfo/auth.py:295`

`load_tokens` では `OSError` を `ConfigError` でラップしているが、write 側は生の `OSError` が漏れる。

**改善案**: 一貫性のため `try/except OSError` で `ConfigError` にラップ。

---

## Info (14件)

### I-1. `_default` 自動切り替えの順序が dict の挿入順に依存

**ファイル**: `src/gfo/auth.py:136-138`

`remove_token` でアカウント削除後に `remaining[0]` で次のデフォルトを選ぶが、dict 挿入順に依存するため予測しにくい。

**改善案**: `sorted(remaining)[0]` にしてアルファベット順にする等の決定論的な挙動にするか、ドキュメントで明記。

---

### I-2. アカウントキー名がベアキーで書き出される

**ファイル**: `src/gfo/auth.py:292`

TOML のベアキーは `[A-Za-z0-9_-]` のみ許可。アカウント名にスペースやドット等が含まれると不正な TOML が生成される。

**改善案**: アカウントキーもクォートするか、`save_token()` でアカウント名のバリデーションを行う。

---

### I-3. `_resolve_account_name` の遅延 import

**ファイル**: `src/gfo/auth.py:315,325`

`gfo.config` はモジュール冒頭で既にインポート済みだが、`get_host_config` は冒頭に含まれていない。

**改善案**: `gfo.config` の冒頭 import に `get_host_config` を追加。`gfo.git_util` の遅延 import は循環依存回避のため妥当。

---

### I-4. `_resolve_account_name` の広い `except Exception`

**ファイル**: `src/gfo/auth.py:320,330`

`# nosec B110` で意図的だが、デバッグ時に問題を見逃す可能性がある。

**改善案**: `except (GitCommandError, ConfigError, OSError, ImportError)` のように具体的な例外に限定。

---

### I-5. アカウント未登録時のエラーメッセージが不明確

**ファイル**: `src/gfo/auth.py:52-56`

`--account work` を指定したが `work` が未登録の場合、「トークン未設定」としか見えず原因が分かりにくい。

**改善案**: 明示指定されたアカウントが見つからない場合は `AuthError(f"Account '{account_name}' not found for host: {host}")` を raise する。

---

### I-6. `_escape_toml_value` が DEL 文字 (`\x7f`) をエスケープしない

**ファイル**: `src/gfo/auth.py:247-251`

TOML 仕様上 DEL は制御文字だが、トークン値に含まれることはほぼなく実害は極めて低い。

---

### I-7. Gitea `_resolve_label_ids` の `limit=0` の互換性リスク

**ファイル**: `src/gfo/adapter/gitea.py:106-117`

`params={"limit": 0}` で全件取得しているが、`limit=0` の挙動は Gitea API のバージョンで異なる可能性がある。

**改善案**: 十分大きい値（50 や 100）を明示するか、ページネーションを使用。

---

### I-8. GitLab `create_release` で `ref` が常に設定される

**ファイル**: `src/gfo/adapter/gitlab.py:490`

既存タグに対してリリースを作成する場合 `ref` は不要だが、常に設定される。GitLab はこれをエラーにしないため実害は低く、変更前からの挙動。

---

### I-9. `pr merge` で `--merge` フラグの True/False が参照されない

**ファイル**: `src/gfo/commands/pr.py:66-80`

`--squash` でも `--rebase` でもなければ `"merge"` がデフォルトになる設計。`--merge` を明示指定しても `args.merge` は参照されない。相互排他グループで排他性は担保されており、動作上は問題なし。

---

### I-10. milestone close/reopen に成功メッセージがない

**ファイル**: `src/gfo/commands/milestone.py:73-82`

`adapter.update_milestone(args.number, state="closed")` を呼ぶだけで何も出力しない。`pr close` や `issue close` は成功メッセージを出力しており不統一。

---

### I-11. `_OUTPUT_MAP` に `("schema", None)` がない

**ファイル**: `src/gfo/commands/schema.py`

schema コマンドは自前で出力するため実害なし。

---

### I-12. GitHub `_resolve_milestone_number` の全件取得

**ファイル**: `src/gfo/adapter/github.py:105-110`

全マイルストーンを取得して線形探索。マイルストーンが多い場合にパフォーマンスが懸念されるが、通常の利用では問題にならない。

---

### I-13. `update` → `edit` リネームの完全性

CLI 層（パーサー定義・ハンドラ関数名・`_DISPATCH` キー・`_OUTPUT_MAP` キー）で完全に行われている。adapter 層の `update_*` メソッド名は API 操作を表す名前として適切であり変更不要。取りこぼしなし。

---

### I-14. `--web` オプションの適用範囲

pr list/view, issue list/view, repo view, release view, milestone list/view に付与済み。release list / repo list にはないが、リスト系で Web を開く意味が薄いリソースのため意図的と推測。

---

## 総合評価

| 重大度 | 件数 |
|---|---|
| Critical | 2 |
| Warning | 8 |
| Info | 14 |

全体として **設計・実装の品質は高い**。各アダプターの基底クラス追従、CLI パーサー定義、コマンドハンドラのロジックはほぼ正確。

**優先的に対処すべき項目**:
1. **W-2**: `_default` 予約語バリデーション — ユーザー入力で容易にデータ破損を引き起こせる
2. **W-4**: `SystemExit` → `ConfigError` — `--format json` でのエラー出力整合性
3. **C-2**: パラメータのサイレント無視 — ユーザー体験上の問題
4. **W-1**: 旧形式マイグレーション — breaking change の影響緩和
5. **C-1**: アトミック書き込み — 発生確率は低いが影響大。中期的改善でも可
