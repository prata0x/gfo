# gfo Review Report — Round 24: auth / commands / detect / http 精査

## 概要

- **レビュー日**: 2026-03-09
- **対象**:
  - `src/gfo/auth.py` — 認証モジュール
  - `src/gfo/adapter/gogs.py` — Gogs アダプター
  - `src/gfo/adapter/registry.py` — アダプターレジストリ
  - `src/gfo/detect.py` — サービス検出
  - `src/gfo/commands/` 配下全コマンド
  - `src/gfo/config.py` — 設定モジュール
  - `src/gfo/http.py` — HTTP クライアント

- **発見事項**: 新規 10 件（重大 0 / 中 7 / 軽微 3）、既知課題 2 件の現状確認

---

## 既知残課題の現状確認

| ID | 状態 |
|----|------|
| R16-02 / R23-02 | `auth.py` `get_auth_status()` の env var エントリ host 形式が `"env:github"` と `"github.com"` で不統一 — **継続中** |
| R13-03 | `gitea.py` `list_issues` フィルタ後 limit 未満 — **継続中（設計決定待ち）** |

---

## 新規発見事項

---

### [R24-01] 🟡 `commands/repo.py` — リポジトリパース処理の重複

- **ファイル**: `src/gfo/commands/repo.py`
- **説明**: `handle_clone` と `handle_view` で同一の `repo_arg.split("/", 1)` パース処理が重複している。
- **影響**: コードの保守性低下。将来の変更時に一方の修正を忘れる可能性。
- **推奨修正**: `_parse_repo_arg(repo_str)` ヘルパーに抽出する。

---

### [R24-02] 🟡 `commands/pr.py` — git_util 関数のエラーハンドリング不備

- **ファイル**: `src/gfo/commands/pr.py` L23-25
- **現在のコード**:
  ```python
  head = args.head or gfo.git_util.get_current_branch()
  base = args.base or gfo.git_util.get_default_branch()
  title = args.title or gfo.git_util.get_last_commit_subject()
  ```
- **説明**: 各 git_util 関数が例外を送出した場合、ハンドラレベルでキャッチされていない。`GitCommandError` が伝播し、CLI の GfoError ハンドラでキャッチされるため実用上は問題ないが、エラーメッセージが git コマンド失敗の文脈で表示される。
- **影響**: ユーザーへのエラーメッセージが不明瞭な場合がある（軽微）。
- **推奨修正**: `GitCommandError` を明示的にキャッチして `ConfigError` に変換する、またはそのままにする（`GitCommandError` は `GfoError` のサブクラスであれば CLI ハンドラで処理される）。

---

### [R24-03] 🟡 `commands/init.py` — 2 回目の API URL 構築失敗時の例外処理なし

- **ファイル**: `src/gfo/commands/init.py`
- **説明**: `_handle_interactive` 内で `build_default_api_url` が最初に失敗した後、organization / project_key をユーザー入力で補完して再試行する。しかし 2 回目の呼び出しが失敗した場合、例外が伝播して対話が中断される。
- **影響**: Azure DevOps での `gfo init` が 2 回失敗した場合、スタックトレースが表示される可能性。
- **推奨修正**: 2 回目の失敗もキャッチして分かりやすいエラーメッセージを出す。

---

### [R24-04] 🟡 `config.py` — `get_hosts_config` の型チェック不完全

- **ファイル**: `src/gfo/config.py` L87-98
- **現在のコード**:
  ```python
  result[host_name] = host_cfg["type"]
  ```
- **説明**: `host_cfg["type"]` の値が `str` であることを確認していない。`type: null` や `type: 123` のような無効な TOML が与えられた場合、非文字列が辞書に入る。
- **影響**: 軽微。通常の TOML では発生しにくいが、設定ファイルが手動編集された場合のリスク。
- **推奨修正**: `if isinstance(host_cfg["type"], str)` チェックを追加する。

---

### [R24-05] 🟡 `detect.py` — API プローブの JSON パース例外処理なし

- **ファイル**: `src/gfo/detect.py` `probe_unknown_host()`
- **現在のコード**:
  ```python
  resp = requests.get(f"{base}/api/v1/version", timeout=5, verify=_VERIFY_SSL)
  if resp.status_code == 200:
      data = resp.json()
      if "forgejo" in data:
          return "forgejo"
  ```
- **説明**: `resp.json()` が `ValueError`（無効な JSON）を送出した場合、`requests.RequestException` ハンドラではキャッチされない（`ValueError` は `RequestException` のサブクラスではない）。
- **影響**: API が 200 で非 JSON レスポンスを返す場合、例外が伝播する。
- **推奨修正**: `except (requests.RequestException, ValueError)` に拡張する。

---

### [R24-06] 🟡 `http.py` — `paginate_link_header` の JSON 型チェック不備

- **ファイル**: `src/gfo/http.py` `paginate_link_header()`
- **現在のコード**:
  ```python
  page_data = resp.json()
  if not isinstance(page_data, list) or not page_data:
      break
  ```
- **説明**: `resp.json()` が例外（`JSONDecodeError`）を送出した場合のキャッチがない。
- **影響**: API が不正な JSON を返した場合、`JSONDecodeError` が伝播する。`HttpClient.get()` 内で処理されるが明示的でない。
- **推奨修正**: `resp.json()` を try-except で囲む、または `HttpClient` が JSON バリデーションを保証するよう明確化する。

---

### [R24-07] 🟡 `auth.py` — `resolve_token` のトークン空文字チェック不備

- **ファイル**: `src/gfo/auth.py` L41-49
- **現在のコード**:
  ```python
  if tokens.get(host):
      return tokens[host]
  ```
- **説明**: `tokens[host]` が空文字列 `""` の場合、`tokens.get(host)` は truthy でないためスキップされ環境変数にフォールバックする（OK）。しかし `"   "` のような空白のみの文字列はこのチェックをすり抜ける可能性がある。実際には認証フォームで防がれていると思われるが、credentials.toml を手動編集した場合のリスク。
- **影響**: 軽微。空白のみのトークンで API 呼び出しが行われる場合がある。
- **推奨修正**: `tokens.get(host, "").strip()` で確認する。

---

### [R24-08] 🟢 `adapter/gogs.py` — ポート番号の正確性

- **ファイル**: `src/gfo/adapter/gogs.py` L20-23
- **説明**: `_web_url()` は API URL（`https://gogs.example.com/api/v1`）からポートを抽出して Web UI URL を構築する。通常これは正しいが、API と Web UI でポートが異なる環境では正確でない可能性がある。
- **影響**: ごく軽微。標準的な構成では問題なし。
- **推奨修正**: コメントで設計意図を明記する。

---

### [R24-09] 🟢 `commands/label.py` — hex 色コードのエラーメッセージ表示

- **ファイル**: `src/gfo/commands/label.py`
- **説明**: エラーメッセージで `args.color`（`#` 付き元の値）を表示しているが、バリデーションは `lstrip("#")` 後の値に対して行われている。エラーメッセージと処理の対象が若干ずれている（実害なし）。
- **影響**: 軽微。ユーザーへの混乱は最小限。

---

### [R24-10] 🟢 `commands/init.py` / `auth.py` / `detect.py` — サービス種別定数の重複管理

- **ファイル**: 複数箇所
- **説明**: 有効なサービス種別のリスト（`"github"`, `"gitlab"`, `"gitea"` 等）が `commands/init.py`、`auth.py`、`adapter/registry.py`、`detect.py` に散在している。新しいサービス追加時に全箇所の更新が必要。
- **影響**: 保守性の低下。現状は問題が顕在化していないが、将来のリスク。
- **推奨修正**: `gfo/constants.py` 等に集約する（大規模リファクタリングが必要なため保留）。

---

## 全問題サマリー（R24）

| ID | 重大度 | ファイル | 概要 | 状態 |
|----|--------|---------|------|------|
| **R24-01** | 🟡 中 | `commands/repo.py` | リポジトリパース処理の重複 | ✅ 修正済み |
| **R24-02** | 🟡 中 | `commands/pr.py` | git_util 関数のエラーハンドリング | 許容（GitCommandError は GfoError のサブクラス） |
| **R24-03** | 🟡 中 | `commands/init.py` | 2 回目の API URL 構築失敗時の例外処理なし | ✅ 修正済み |
| **R24-04** | 🟡 中 | `config.py` | `get_hosts_config` の型チェック不完全 | ✅ 修正済み |
| **R24-05** | 🟡 中 | `detect.py` | `probe_unknown_host` の JSON パース例外処理なし | ✅ 修正済み |
| **R24-06** | 🟡 中 | `http.py` | `paginate_link_header` の JSON 型チェック不備 | 保留 |
| **R24-07** | 🟡 中 | `auth.py` | `resolve_token` のトークン空文字チェック不備 | ✅ 修正済み |
| **R24-08** | 🟢 軽微 | `adapter/gogs.py` | ポート番号の正確性（コメント不足） | 保留 |
| **R24-09** | 🟢 軽微 | `commands/label.py` | hex 色コードエラーメッセージの表示ずれ | 保留 |
| **R24-10** | 🟢 軽微 | 複数 | サービス種別定数の重複管理 | 保留 |
| R16-02 | 🟡 中 | `auth.py` | host 形式不統一 | ✅ 修正済み |
| R13-03 | 🟡 中 | `gitea.py` | フィルタ後 limit 未満（継続） | 継続中 |

---

## 修正コミット（R24）

| コミット | 修正内容 |
|---------|---------|
| `4b909d3` | R24-01/03/04/05/07 — detect/config/auth/init/repo の堅牢性改善 |
| `b271353` | R16-02/R23-02 — auth.py host 形式統一（_SERVICE_DEFAULT_HOSTS 追加） |

---

## 推奨アクション（優先度順）

1. ~~**[R24-05]**~~ ✅ 修正済み
2. ~~**[R24-04]**~~ ✅ 修正済み
3. ~~**[R24-07]**~~ ✅ 修正済み
4. ~~**[R24-03]**~~ ✅ 修正済み
5. ~~**[R24-01]**~~ ✅ 修正済み
6. ~~**[R16-02]**~~ ✅ 修正済み
7. **[R24-06]** `http.py` — paginate_link_header の JSON 例外処理明確化（保留）
8. **[R24-08/09/10]** 軽微な問題（保留）
