# gfo Review Report — Round 3: 入力バリデーション・エラーハンドリング（統合版）

## 概要
- レビュー日: 2026-03-09
- レビュー回数: 3回（重複排除済み）
- 対象ファイル:
  - `src/gfo/commands/issue.py`
  - `src/gfo/commands/pr.py`
  - `src/gfo/commands/repo.py`
  - `src/gfo/commands/label.py`
  - `src/gfo/commands/milestone.py`
  - `src/gfo/commands/release.py`
  - `src/gfo/commands/init.py`
  - `src/gfo/auth.py`
  - `src/gfo/config.py`
  - `src/gfo/http.py`
  - `src/gfo/exceptions.py`
  - `src/gfo/cli.py`（補助調査）
  - `src/gfo/adapter/github.py`（補助調査）
  - `src/gfo/adapter/registry.py`（補助調査）
  - `src/gfo/detect.py`（補助調査）
  - `src/gfo/git_util.py`（補助調査）
- 発見事項: 重大 6 / 中 11 / 軽微 8

---

## 発見事項

---

### [R3-01] 🔴 重大 `--limit` に負数・ゼロを指定しても無制限ページネーションが発生する

- **ファイル**: `src/gfo/cli.py` L52, L76, L94, L110 / `src/gfo/http.py` L177
- **説明**: `issue list`、`pr list`、`repo list`、`release list` の `--limit` 引数は `type=int` のみ指定されており、負数（例: `-1`、`-100`）やゼロを渡してもエラーにならない。`paginate_link_header` 等のページネーション関数では `if limit > 0 and len(results) >= limit:` という条件のみで上限チェックを行うため、`limit=0` は上限なし（全件取得）として動作し、`limit=-1` のような負数の場合も `limit > 0` が False になるため全件ループが走る。大規模リポジトリで無限に近いリクエストが発生しうる。
- **影響**: ユーザーが誤って `gfo issue list --limit 0` や `gfo issue list --limit -100` を入力した場合、意図せず全件取得リクエストが大量に発行され、レート制限超過・メモリ枯渇・長時間フリーズを引き起こす。
- **推奨修正**: argparse の `type` に `lambda x: int(x) if int(x) > 0 else parser.error(...)` を使う独自バリデーション関数（例: `positive_int`）を設定する。全 `list` サブコマンドで共通化が望ましい。`paginate_*` 関数のドキュメントに `limit <= 0` が「無制限」であることを明記し、防衛的処理も追加する。
- **テスト**: `--limit 0`、`--limit -1`、`--limit -999` でエラーメッセージとともに非0終了になることを確認するテスト。`paginate_link_header(client, path, limit=0)` が全件取得にならないことの単体テスト。
- **検出回数**: 3/3

---

### [R3-02] 🔴 重大 `issue create --title ""` で空文字列タイトルが API に送信される

- **ファイル**: `src/gfo/cli.py` L78 / `src/gfo/commands/issue.py` L37-43
- **説明**: `issue_create.add_argument("--title", required=True)` は `--title` の指定自体を必須とするが、空文字列 `""` や空白のみの `"   "` は argparse にとって合法な引数として通過する。`handle_create` は `args.title` を直接 `adapter.create_issue(title=args.title, ...)` に渡す。空文字列タイトルのイシューはほとんどの Git サービスで API エラーになるが、そのエラーは `HttpError` として下位レイヤーで処理されるため、ユーザーへのメッセージが「HTTP 422: ...」という内部的なものになる。
- **影響**: ユーザーは「なぜ失敗したのか」を理解できない。またサービスによっては空タイトルのイシューが実際に作成されてしまう。
- **推奨修正**: `handle_create` 内で `if not args.title or not args.title.strip(): raise ConfigError("--title must not be empty.")` を追加する。
- **テスト**: `gfo issue create --title ""` および `gfo issue create --title "   "` でユーザーフレンドリーなエラーメッセージが表示されることを確認するテスト。
- **検出回数**: 2/3

---

### [R3-03] 🔴 重大 `milestone create` で空文字列タイトルが API に送信される

- **ファイル**: `src/gfo/cli.py` L132 / `src/gfo/commands/milestone.py` L24-28
- **説明**: `milestone create` のタイトルは位置引数（必須）だが、空文字列 `""` は argparse に受け入れられる。`gfo milestone create ""` を実行すると API に空タイトルが送信される。`issue create` と同様の問題で、ハンドラ層での検証が欠如している。
- **影響**: 空タイトルのマイルストーンが API を通じて作成される可能性がある、またはサービス側の不明瞭な API エラーがユーザーに表示される。
- **推奨修正**: `handle_create` 内で `if not args.title.strip(): raise ConfigError("title must not be empty.")` を追加する。
- **テスト**: `gfo milestone create ""` でエラーが返ることを確認するテスト。
- **検出回数**: 1/3

---

### [R3-04] 🔴 重大 `repo clone` / `repo view` の `owner/repo` 形式バリデーションが不統一

- **ファイル**: `src/gfo/commands/repo.py` L95-101, L130-138
- **説明**: `handle_clone` では `repo_arg.split("/", 1)` で分割し、スラッシュがない場合は `ConfigError` を送出する正しいバリデーションを行う（L100-102）。一方 `handle_view` では同じ分割処理を行うが、スラッシュがない場合に `owner=None, name=repo_arg` としてサイレントに処理が継続される（L136）。また `"owner/"` や `"/name"` のような入力では `owner=""` または `name=""` となり、形式チェックは通過してしまう。この `None` / 空文字列の `owner` がアダプターに渡ると、`/repos//name` のような不正パスが生成される場合がある。
- **影響**: `gfo repo view invalidformat` でリクエストパス不正または意図しないリポジトリが参照される。ユーザーへのエラーメッセージが不明瞭。
- **推奨修正**: `handle_view` でも `split("/", 1)` の後に `if not owner or not name: raise ConfigError(...)` を追加し、`handle_clone` と同等のバリデーションを適用する。`"/"` のみの入力でも同様のチェックを行う。
- **テスト**: `""`, `"/"`, `"owner/"`, `"/name"`, `"owner/name/extra"` を引数として渡した場合の挙動テスト。`gfo repo view invalidformat`（スラッシュなし）でエラーが返ることを確認するテスト。
- **検出回数**: 3/3

---

### [R3-05] 🔴 重大 アダプター変換ヘルパーが必須フィールド欠如時に `KeyError` を送出する

- **ファイル**: `src/gfo/adapter/github.py` L30, L36-47 他
- **説明**: `_to_pull_request` では `data["state"]`、`data["number"]`、`data["title"]`、`data["user"]["login"]`、`data["head"]["ref"]`、`data["base"]["ref"]`、`data["html_url"]`、`data["created_at"]` に直接インデックスアクセスする。API が予期しないフィールドを省略した場合（サービスのバージョン差異、サービス障害時の部分レスポンス等）に `KeyError` が発生し、`GfoError` ではないため `cli.py` の `except GfoError` をバイパスしてスタックトレースがユーザーに表示される。`_to_issue`、`_to_repository`、`_to_release`、`_to_milestone` も同様のパターン。なお `paginate_link_header` で非リスト型レスポンス（例: `{"message": "..."}` のようなエラーオブジェクト）が返ってきた場合は `isinstance(page_data, list)` が `False` でブレークするが、ラッパー付き JSON（`{"items": [...]}` 等）の場合は空リストとして扱われる問題もある。
- **影響**: API の軽微な変更や非標準レスポンスに対して脆弱。ユーザーに生の Python スタックトレースが露出する。
- **推奨修正**: 変換ヘルパー全体を `try/except KeyError as e: raise GfoError(f"Unexpected API response: missing field {e}") from e` でラップするか、フィールド取得に `data.get(key)` を使い `None` のケースを明示的にハンドルする。
- **テスト**: `_to_pull_request({})` や `_to_issue({"number": 1})`（必須フィールド欠如）で `GfoError` サブクラスが送出されることを確認する単体テスト。
- **検出回数**: 3/3

---

### [R3-06] 🔴 重大 `load_tokens()` / `load_user_config()` で壊れた TOML ファイルの `TOMLDecodeError` が未キャッチ

- **ファイル**: `src/gfo/auth.py` L88-95 / `src/gfo/config.py` L53-59
- **説明**: `load_tokens()` は `tomllib.load(f)` を `try/except` なしで呼び出す。`credentials.toml` が手動編集ミスや文字化け等で破損していた場合、`tomllib.TOMLDecodeError` が `GfoError` でないため `cli.py` の `except GfoError` をすり抜け、ファイルパスを含む完全なスタックトレースが標準エラー出力に表示される。`config.py` の `load_user_config()` L53-59 でも同一問題がある（別ファイルで検出された問題だが実質同一）。
- **影響**: 設定ファイル破損時に全 `gfo` コマンドが実行不能になり、かつユーザーフレンドリーなエラーメッセージが表示されない。`credentials.toml` が絡む場合はファイルパス等の機密情報に近い情報も露出する。
- **推奨修正**: `load_tokens()` と `load_user_config()` の両方で `tomllib.TOMLDecodeError` を `try/except` でラップし、`ConfigError(f"Failed to parse {path}: {e}")` または `AuthError(f"credentials.toml is malformed: {e}")` として再送出する。
- **テスト**: 不正 TOML 内容（例: `[tokens\n broken`）の `credentials.toml` および `config.toml` が存在する状態で任意のコマンドを実行した際に `ConfigError` / `AuthError` が送出されることを確認するテスト。
- **検出回数**: 3/3

---

### [R3-07] 🟡 中 `paginate_page_param` の `X-Next-Page` ヘッダーが非整数値の場合に `ValueError` で未処理クラッシュ

- **ファイル**: `src/gfo/http.py` L218
- **説明**: `params["page"] = int(next_page)` において、`X-Next-Page` ヘッダーが空文字列以外の非数値文字列（例: `"last"`、`"next"`、壊れた値）を持つ場合 `ValueError` が発生する。この `ValueError` は `GfoError` サブクラスではないため `cli.py` の `except GfoError` でキャッチされず、スタックトレースがユーザーに表示される。
- **影響**: GitLab 互換サービス等で非標準の `X-Next-Page` ヘッダーを返す場合に、Python スタックトレースがユーザーに表示される。
- **推奨修正**: `try: params["page"] = int(next_page)` とし、`except ValueError` で `HttpError` または `NetworkError` に変換して再送出するか、`break` でループを安全に終了させる。
- **テスト**: `X-Next-Page: next` や `X-Next-Page: invalid` のような非整数ヘッダーを返すモックで `paginate_page_param` が `ValueError` をユーザーに露出しないことを確認するテスト。
- **検出回数**: 3/3

---

### [R3-08] 🟡 中 `Retry-After` ヘッダーの値処理に複数の問題がある

- **ファイル**: `src/gfo/exceptions.py` L66-68 / `src/gfo/http.py` L80, L132-134
- **説明**: 2つの関連する問題が存在する。(1) `http.py` L132 で `int(retry_after) if retry_after else None` とあるが、`retry_after` が `"0"` の場合 falsy であるため `None` になり、リトライ待機時間が 60 秒になる（L80）。`Retry-After: 0` は「即座にリトライ可能」を意味するが 60 秒待機が発生する。`RateLimitError.__init__` も `if retry_after:` で `retry_after=0` の "Retry after 0s." メッセージが表示されない。(2) RFC 7231 では `Retry-After` に HTTP 日時形式（例: `Wed, 09 Mar 2026 10:00:00 GMT`）も許容されているが、この場合 `int()` 変換が失敗して `ValueError` が未捕捉のまま伝播する。
- **影響**: `Retry-After: 0` が正しく処理されず 60 秒待機が発生する。特定のサーバーからレート制限を受けた際に `ValueError` が露出する可能性がある。
- **推奨修正**: (1) `retry_after` の判定を `if retry_after is not None:` に変更する。(2) `int(retry_after)` を `try/except ValueError` でラップし、変換失敗時はデフォルト値（60 秒等）にフォールバックする。
- **テスト**: `Retry-After: 0` ヘッダーで待機時間が 0 秒になることを確認するテスト。`Retry-After: Wed, 09 Mar 2026 10:00:00 GMT` を含むモックレスポンスで `_handle_response` がクラッシュしないことを確認するテスト。
- **検出回数**: 3/3

---

### [R3-09] 🟡 中 `GitHubAdapter.list_labels` / `list_milestones` がページネーションを使わず全件取得できない

- **ファイル**: `src/gfo/adapter/github.py` L232-233, L248-249
- **説明**: `list_labels` と `list_milestones` は `resp = self._client.get(...)` で単一リクエストのみ行い、`paginate_link_header` を使用していない。GitHub API のデフォルト `per_page` は 30 件であり、それを超えるラベル・マイルストーンがあるリポジトリでは一部しか取得されない。また `resp.json()` が非リスト（エラーオブジェクト等）の場合も `KeyError` / `TypeError` で未処理例外となる可能性がある。
- **影響**: 大規模リポジトリで一覧が不完全になるが、ユーザーへの告知がない。
- **推奨修正**: `paginate_link_header` を使用してページネーション対応とする。
- **テスト**: 30 件超のラベルが存在するリポジトリでの取得件数検証テスト（ページネーションモックテスト）。
- **検出回数**: 1/3

---

### [R3-10] 🟡 中 `auth login` でホスト自動検出失敗時のエラーメッセージが不適切

- **ファイル**: `src/gfo/commands/auth_cmd.py` L14-21
- **説明**: `handle_login` で `args.host` が指定されていない場合、`gfo.detect.detect_service()` を呼ぶが、`try/except` がない。`detect_service()` が `DetectionError` を送出した場合、`cli.py` の `except GfoError` でキャッチはされるものの、エラーメッセージが「Could not detect git forge service. Run 'gfo init' to configure manually.」となり、`gfo auth login` のコンテキストで「`--host` を使え」という具体的な誘導がない。git リポジトリ外からの実行や `origin` リモートが未設定の場合も同様。
- **影響**: ユーザーが `--host` 引数の存在に気づかず、`gfo init` を実行しても解決しない状況に陥る可能性がある。
- **推奨修正**: `handle_login` 内で `DetectionError` / `GitCommandError` をキャッチし、`ConfigError("Could not detect host. Use --host option: gfo auth login --host <host>")` として再送出する。
- **テスト**: git リポジトリ外で `gfo auth login`（`--host` なし）を実行した場合のエラーメッセージが `--host` の使い方を案内することを確認するテスト。
- **検出回数**: 3/3

---

### [R3-11] 🟡 中 空トークンが `credentials.toml` に保存・使用される

- **ファイル**: `src/gfo/auth.py` L27-54, L57-85
- **説明**: `resolve_token` は `load_tokens()` で取得したトークンが空文字列 `""` の場合も有効なトークンとして返す（`if host in tokens: return tokens[host]` の空文字チェックなし）。環境変数 `GFO_TOKEN=""` や `GITHUB_TOKEN=""` の場合は `if val:` / `if gfo_token:` の判定で空文字列はスキップされるが、`credentials.toml` 経由では同等のチェックがなく一貫性がない。また `save_token(host, token)` は `token` の内容チェックをしないため、`getpass.getpass("Token: ")` でユーザーが Enter のみを押した場合、空文字列 `""` が `credentials.toml` に永続化される。
- **影響**: 空トークンで API リクエストが実行され、401 エラーが返る。デバッグ時に「なぜトークンがあるのに認証失敗するのか」が不明確。以降の全コマンドで無効な認証リクエストが送信され続ける。
- **推奨修正**: `save_token` の先頭で `if not token or not token.strip(): raise AuthError(host, "Token must not be empty.")` を追加する。`resolve_token` でも `credentials.toml` から取得した値が空文字列なら次の解決手順に進む（`if tokens.get(host): return tokens[host]`）。
- **テスト**: `save_token("github.com", "")` が `AuthError` を送出することを確認するテスト。空トークンが `credentials.toml` に保存されている場合に `resolve_token` が `AuthError` を送出することを確認するテスト。空トークンで `gfo auth login` を実行したときにエラーが返ることを確認するテスト。
- **検出回数**: 3/3

---

### [R3-12] 🟡 中 `paginate_top_skip` で `resp.json()` が dict 以外の場合に `AttributeError` が発生する

- **ファイル**: `src/gfo/http.py` L318-319
- **説明**: `body = resp.json()` で取得した値が dict でない場合（API がリストや null を返した場合）、`body.get(result_key, [])` で `AttributeError` が発生する。Azure DevOps 固有の関数だが、サーバーエラー時にプレーンテキストや配列が返ると問題となる。`paginate_response_body` でも `body.get(values_key, [])` を使うが、`resp.json()` が dict でない場合に `AttributeError` が発生する点は同様。
- **影響**: Azure DevOps の API が予期しないレスポンスを返した場合にクラッシュし、Python スタックトレースが露出する。
- **推奨修正**: `body.get()` の前に `if not isinstance(body, dict): break` を追加する。
- **テスト**: `paginate_top_skip` で `resp.json()` がリスト型の場合に安全に終了することを確認するテスト。
- **検出回数**: 1/3

---

### [R3-13] 🟡 中 `pr create` でタイトルが空コミットサブジェクトから導出される場合がある

- **ファイル**: `src/gfo/commands/pr.py` L27
- **説明**: `title = args.title or gfo.git_util.get_last_commit_subject()` の実装では、直近コミットのサブジェクトが空文字列の場合（`--allow-empty-message` で作成されたコミット等）、空タイトルの PR が API に送信される。`get_last_commit_subject()` の戻り値の空チェックがない。これは `issue create` の空タイトル問題（`R3-02`）と同根。
- **影響**: 空タイトルの PR が作成されるか、API エラーが不明瞭なメッセージで返る。
- **推奨修正**: `if not title or not title.strip(): raise ConfigError("Could not determine PR title. Use --title option.")` を追加する。
- **テスト**: 直近コミットのメッセージが空の状態で `gfo pr create`（`--title` なし）を実行するとエラーが返ることを確認するテスト。
- **検出回数**: 1/3

---

### [R3-14] 🟡 中 `paginate_link_header` で `rel="Next"`（大文字）の Link ヘッダーをサイレント無視する

- **ファイル**: `src/gfo/http.py` L181-184
- **説明**: `re.search(r'<([^>]+)>;\s*rel="next"', link)` でマッチしなければ次ページなしとしてループを終了する。正規表現が `rel="next"` を小文字固定でマッチするため、`rel="Next"` を返す一部のサーバーでは次ページが無視されてサイレントに途中で打ち切られた結果が返る。
- **影響**: 一部の非標準サーバーで全件取得が行われず、ユーザーへの通知もない。
- **推奨修正**: 正規表現に `re.IGNORECASE` フラグを追加するか、`rel` の値を小文字に正規化してから比較する。
- **テスト**: `Link: <url>; rel="Next"` を返すモックで全ページが取得されることを確認するテスト。
- **検出回数**: 1/3

---

### [R3-15] 🟢 軽微 `init` 対話モードで空文字列 `service_type` / `host` が `ProjectConfig` に保存される

- **ファイル**: `src/gfo/commands/init.py` L90-92, L112-122
- **説明**: 対話モードの手動入力パスで `service_type = input(...).strip()` および `host = input(...).strip()` を実行するが、ユーザーが Enter のみを押した場合に空文字列が取得される。その空文字列のまま `ProjectConfig` が生成される。`_build_default_api_url("")` は `ConfigError: Unknown service type:` を発火するが、`api_url_input` が指定されると `_build_default_api_url` は呼ばれず実際に空の設定が書き込まれる。非対話モードの `_handle_non_interactive` では同様のチェックが実装済みであり（L31-34）、対話モードにも同等のガードが必要。
- **影響**: 不完全な設定が git config に書き込まれ、以降のコマンドで `ConfigError` や API 呼び出し失敗が不明瞭なエラーで発生する可能性がある。
- **推奨修正**: 入力受付後に `if not service_type: raise ConfigError("service_type cannot be empty.")` および `if not host: raise ConfigError("host cannot be empty.")` のバリデーションを追加する。
- **テスト**: 対話モードで `service_type` または `host` を空 Enter した場合に再入力プロンプトまたはエラーが表示され、設定が保存されないことを確認するテスト。
- **検出回数**: 3/3

---

### [R3-16] 🟢 軽微 `init --non-interactive` で `detect_from_url` 失敗時のエラーが不明瞭

- **ファイル**: `src/gfo/commands/init.py` L47-48
- **説明**: `_handle_non_interactive` 内で `remote_url = get_remote_url()` および `detect_result = detect_from_url(remote_url)` を呼ぶが、`try/except` がない。`get_remote_url()` は git リモートが未設定の場合に `GitCommandError` を送出し、これは `GfoError` のサブクラスなので `cli.py` でキャッチされるが、エラーメッセージが「Git error: fatal: No such remote 'origin'」のみで `init` のコンテキストが分からない。対話モード（L96-105）では `except Exception` で適切にフォールバックしており非対称。
- **影響**: `--non-interactive` モードが git リモートなし環境でわかりにくいエラーで失敗する。`owner=""` / `repo=""` の不完全な設定が保存される可能性がある。
- **推奨修正**: `try/except (GitCommandError, DetectionError)` でラップし「remote 'origin' not found. Please ensure you're in a git repository with an origin remote configured, or use `--owner`/`--repo` options.」といったメッセージに変換する。
- **テスト**: git リモートが未設定のリポジトリで `gfo init --non-interactive --type github --host github.com` を実行した場合のエラーメッセージを確認するテスト。
- **検出回数**: 3/3

---

### [R3-17] 🟢 軽微 `release create` で空文字列タグが API に送信される

- **ファイル**: `src/gfo/cli.py` L112 / `src/gfo/commands/release.py` L23-32
- **説明**: `release create` の `tag` は位置引数（必須）だが、空文字列 `""` や `"v1.0 beta"`（スペース入り）などの git タグとして無効な文字列が検証なしに API に送信される。`title = args.title or args.tag` により `title` も空文字列となり、空タグ・空タイトルの Release が API に送信される。タグ名の基本バリデーション（空文字・スペース含有等）が CLI 層・ハンドラ層のどちらにも存在しない。
- **影響**: 無効なタグ名で API が呼ばれ、サービス側の不明瞭なエラー（例: HTTP 422）がユーザーに表示される。
- **推奨修正**: `handle_create` 冒頭で `if not args.tag or not args.tag.strip(): raise ConfigError("tag must not be empty.")` を追加する。スペース含有や git タグ無効文字の基本チェックも追加することを推奨する。
- **テスト**: `gfo release create ""` および `gfo release create "v1.0 beta"` でエラーメッセージとともに失敗することを確認するテスト。
- **検出回数**: 3/3

---

### [R3-18] 🟢 軽微 `label create` のカラーコードにバリデーションなし

- **ファイル**: `src/gfo/cli.py` L124 / `src/gfo/commands/label.py` L20-29
- **説明**: `--color` は任意引数（`None` 許容）だが、値が指定された場合に GitHub が要求する `#` なしの 6 桁 16 進数（例: `ff0000`）かどうかのチェックがない。`#ff0000`（`#` 付き）、`red`（名前形式）、`ZZZZZZ`（無効文字）等が入力可能。誤ったフォーマットは API エラーになるが、エラーメッセージは汎用的な `HTTP 422` となる。
- **影響**: ユーザーが `#ff0000` と入力した場合に失敗するが理由がわかりにくい。
- **推奨修正**: `handle_create` 内で `re.fullmatch(r"[0-9a-fA-F]{6}", args.color)` によるバリデーションを追加する。`#` プレフィックスを自動除去する選択肢も検討する。エラーメッセージにフォーマット例を含める。
- **テスト**: `--color "#ff0000"`、`--color "red"`、`--color "GGGGGG"` でバリデーションエラーが返ることを確認するテスト。
- **検出回数**: 3/3

---

### [R3-19] 🟢 軽微 `gfo init --type` に利用可能な値の案内がなく誤記を誘発する

- **ファイル**: `src/gfo/config.py` L205 / `src/gfo/cli.py`（`--type` 引数定義箇所）
- **説明**: CLI ヘルプには使用可能な `--type` 値が明示されておらず、ユーザーが `azure_devops`（アンダースコア）と入力した場合に `_build_default_api_url` が `ConfigError: Unknown service type: azure_devops` になる。有効な値は `azure-devops`（ハイフン）だが、このことがヘルプからは判断できない。`--type foobar` のような完全に無効な値でも `_build_default_api_url` が呼ばれるまでエラーが遅延する。
- **影響**: ユーザーが誤ったサービス名（アンダースコアや大文字等）を入力した場合に理解しにくいエラーが出る。エラー発生箇所が深いところになり原因特定が難しい。
- **推奨修正**: `gfo init --type` の引数に `choices` を設定して利用可能なサービス名を明示する。あるいは `_handle_non_interactive` の冒頭で既知サービス一覧との照合バリデーションを行い、わかりやすいエラーメッセージを提供する。
- **テスト**: `--type azure_devops`、`--type unknown_service` を渡したときに明確なエラーが出ることを確認するテスト。
- **検出回数**: 1/3

---

### [R3-20] 🟢 軽微 `init --non-interactive` で未知のサービス種別のエラー発生が遅延する

- **ファイル**: `src/gfo/commands/init.py` L31-34
- **説明**: `--type` が空文字列 `""` の場合は `if not service_type:` でキャッチされるが、未知のサービス種別（例: `--type foobar`）を指定した場合は `_build_default_api_url` が呼ばれるまでエラーが発生しない（`config.py` L205 の `raise ConfigError` が最終的に発火する）。また `--host` の形式チェック（URL として有効かどうか等）が一切ない。`[R3-19]` と関連するが、非対話モード固有の問題として独立して存在する。
- **影響**: 非対話モードで誤った設定が書き込まれる可能性がある。エラー発生箇所が深いところになり原因特定が難しい。
- **推奨修正**: `_handle_non_interactive` の冒頭で `service_type` が有効な値のリストに含まれるか確認し、早期エラーを出す。
- **テスト**: `gfo init --non-interactive --type foobar --host example.com` でわかりやすいエラーが返ることを確認するテスト。
- **検出回数**: 1/3

---

### [R3-21] 🟢 軽微 `config.py` の `get_config_dir` で `APPDATA` 環境変数が空白文字列の場合に意図しないパスが生成される

- **ファイル**: `src/gfo/config.py` L32-33
- **説明**: Windows 環境で `APPDATA=""` のような空文字列の場合は `if appdata:` が `False` になりフォールバックが使われるため問題ない。しかし `APPDATA=" "` のような空白のみの場合は `if appdata:` が `True` となり `Path(" ") / "gfo"` という予期しないパスが生成される可能性がある。
- **影響**: 稀なエッジケースだが、設定ファイルが意図しない場所に作成される可能性がある。
- **推奨修正**: `appdata = os.environ.get("APPDATA", "").strip()` に変更する。
- **テスト**: `APPDATA=" "` 環境で `get_config_dir()` が適切なフォールバックパスを返すことを確認するテスト。
- **検出回数**: 1/3

---

### [R3-22] 🟢 軽微 `save_token` の `os.getlogin()` が CI / Docker 環境でサイレントに失敗する

- **ファイル**: `src/gfo/auth.py`（`save_token` 内の `os.getlogin()` 呼び出し箇所）
- **説明**: `auth.py` の `save_token` 内で `os.getlogin()` が使用されているが、Docker 環境や CI 環境では `OSError` を送出することが知られている。現在 `except OSError` で保護されているものの、`icacls` コマンド全体がスキップされるため、Windows 環境での権限設定が無言で失敗する。
- **影響**: Windows の CI / Docker 環境でトークンファイルのパーミッション設定が無言でスキップされ、セキュリティ上の問題が生じる可能性がある。
- **推奨修正**: スキップされた場合に警告ログを出力する。または `os.getlogin()` の代わりに `os.getenv("USERNAME")` など環境変数ベースの代替手段を使用する。
- **テスト**: `os.getlogin()` が `OSError` を送出する環境で `save_token` を実行した際の挙動確認テスト。
- **検出回数**: 1/3

---

## サマリーテーブル

| ID | 重大度 | ファイル | 行 | 説明 | 検出回数 |
|----|--------|---------|------|------|----------|
| R3-01 | 🔴 重大 | `cli.py` / `http.py` | L52,L76,L94,L110 / L177 | `--limit` 負数・ゼロで無制限ページネーションが発生 | 3/3 |
| R3-02 | 🔴 重大 | `cli.py` / `commands/issue.py` | L78 / L37-43 | 空文字列タイトルが API に送信される | 2/3 |
| R3-03 | 🔴 重大 | `cli.py` / `commands/milestone.py` | L132 / L24-28 | `milestone create ""` で空タイトルが API に送信される | 1/3 |
| R3-04 | 🔴 重大 | `commands/repo.py` | L95-101, L130-138 | `owner/repo` 形式バリデーションが `clone` と `view` で不統一 | 3/3 |
| R3-05 | 🔴 重大 | `adapter/github.py` | L30, L36-47 他 | 変換ヘルパーの必須フィールド欠如時に `KeyError` が未処理で伝播 | 3/3 |
| R3-06 | 🔴 重大 | `auth.py` / `config.py` | L88-95 / L53-59 | 壊れた TOML ファイルで `TOMLDecodeError` が `GfoError` をすり抜ける | 3/3 |
| R3-07 | 🟡 中 | `http.py` | L218 | 不正 `X-Next-Page` ヘッダーで `ValueError` が未処理 | 3/3 |
| R3-08 | 🟡 中 | `exceptions.py` / `http.py` | L66-68 / L80, L132-134 | `Retry-After: 0` の判定誤りと HTTP-date 形式で `ValueError` | 3/3 |
| R3-09 | 🟡 中 | `adapter/github.py` | L232-233, L248-249 | `list_labels` / `list_milestones` がページネーションなし | 1/3 |
| R3-10 | 🟡 中 | `commands/auth_cmd.py` | L14-21 | `auth login` でホスト検出失敗時のエラーメッセージが不適切 | 3/3 |
| R3-11 | 🟡 中 | `auth.py` | L27-54, L57-85 | 空トークンが `credentials.toml` に保存・使用される | 3/3 |
| R3-12 | 🟡 中 | `http.py` | L318-319 | `paginate_top_skip` で非 dict レスポンスに `AttributeError` | 1/3 |
| R3-13 | 🟡 中 | `commands/pr.py` | L27 | 空コミットサブジェクトから空タイトル PR が作成される | 1/3 |
| R3-14 | 🟡 中 | `http.py` | L181-184 | `rel="Next"`（大文字）の Link ヘッダーをサイレント無視 | 1/3 |
| R3-15 | 🟢 軽微 | `commands/init.py` | L90-92, L112-122 | 対話モードで空文字列 `service_type` / `host` が保存される | 3/3 |
| R3-16 | 🟢 軽微 | `commands/init.py` | L47-48 | `--non-interactive` で `detect_from_url` 失敗時のエラーが不明瞭 | 3/3 |
| R3-17 | 🟢 軽微 | `cli.py` / `commands/release.py` | L112 / L23-32 | 空文字列・不正タグが API に送信される | 3/3 |
| R3-18 | 🟢 軽微 | `cli.py` / `commands/label.py` | L124 / L20-29 | カラーコードのフォーマットバリデーションなし | 3/3 |
| R3-19 | 🟢 軽微 | `config.py` / `cli.py` | L205 | `--type` に利用可能な値の案内がなく誤記を誘発 | 1/3 |
| R3-20 | 🟢 軽微 | `commands/init.py` | L31-34 | `--non-interactive` で未知サービス種別のエラー発生が遅延 | 1/3 |
| R3-21 | 🟢 軽微 | `config.py` | L32-33 | `APPDATA` が空白文字列の場合に意図しないパス生成 | 1/3 |
| R3-22 | 🟢 軽微 | `auth.py` | — | `save_token` の `os.getlogin()` が CI/Docker でサイレント失敗 | 1/3 |

---

## 推奨アクション (優先度順)

1. **[R3-05] アダプター変換ヘルパーの `KeyError` ラッピング（最優先）**
   全アダプターの `_to_*` メソッドで `KeyError` を `GfoError` にラップする。ユーザーへのスタックトレース露出を防ぐ最も広範な影響を持つ修正。`github.py` だけでなく `gitlab.py`、`bitbucket.py`、`azure_devops.py`、`backlog.py`、`gitea.py`、`forgejo.py`、`gogs.py`、`gitbucket.py` の全アダプターに適用すること。

2. **[R3-06] TOML パースエラーの `ConfigError` / `AuthError` への変換**
   `load_tokens()` と `load_user_config()` の両方で `tomllib.TOMLDecodeError` を捕捉し、ユーザーフレンドリーなエラーに変換する。設定ファイル破損時の全コマンド停止を防ぐ。修正コストが低く影響範囲が広いため早期対応を推奨。

3. **[R3-01] `--limit` の負数・ゼロバリデーション追加**
   `cli.py` の全 `--limit` 引数に `type=positive_int` 相当の検証を追加する。全 list サブコマンドで共通化が望ましい。意図しない全件取得によるレートリミット消費・メモリ枯渇を防ぐ。

4. **[R3-11] 空トークンの保存・使用防止**
   `save_token` および `resolve_token` に空文字列チェックを追加する。認証の信頼性確保に必要。

5. **[R3-02] + [R3-03] + [R3-13] 空タイトルの CLI バリデーション**
   `issue create`、`milestone create`、`pr create` で空文字列タイトルをコマンドハンドラ層で拒否する。`pr create` では `get_last_commit_subject()` の戻り値が空の場合も検証する。

6. **[R3-07] `X-Next-Page` ヘッダーの型変換エラー処理**
   `paginate_page_param` の `int(next_page)` を `try/except ValueError` でラップし `GfoError` に変換するか、安全に `break` する。

7. **[R3-08] `Retry-After` ヘッダーの処理修正**
   `retry_after` の判定を `if retry_after is not None:` に変更し、`int()` 変換を `try/except ValueError` でラップしてフォールバック値を設定する。

8. **[R3-04] `repo view` の引数バリデーション統一**
   `handle_view` に `handle_clone` と同等のバリデーションを適用するか、単一引数時の意味を明確に定義してドキュメント化する。

9. **[R3-10] `auth login` のエラーメッセージ改善**
   `DetectionError` / `GitCommandError` をキャッチし `--host` オプションの使い方を案内するメッセージに変換する。

10. **[R3-15] `init` 対話モードの空入力バリデーション**
    `_handle_interactive` の手動入力パスに `service_type` と `host` の空文字列チェックを追加する（非対話モードに倣う）。

11. **[R3-09] `list_labels` / `list_milestones` のページネーション対応**
    `paginate_link_header` を使用して全件取得を保証する。

12. **[R3-16] `init --non-interactive` のエラーメッセージ改善**
    `get_remote_url()` / `detect_from_url()` を `try/except` でラップし、文脈に沿ったエラーメッセージを提供する。

13. **[R3-12] `paginate_top_skip` の非 dict レスポンス対応**
    `body.get()` の前に `isinstance(body, dict)` チェックを追加する。

14. **[R3-14] Link ヘッダーの大文字小文字非感知マッチ**
    `re.IGNORECASE` を追加して非標準サーバーとの互換性を向上させる。

15. **[R3-17] + [R3-18] + [R3-19] + [R3-20] 軽微バリデーション**
    `release tag` 空文字・不正文字チェック、`--color` hex フォーマットチェック、`--type` の `choices` 設定をそれぞれ追加する。

---

## 次ラウンドへの申し送り

- **アダプター全体の変換メソッドレビュー**: 今回は `github.py` を中心に確認した。`gitlab.py`、`bitbucket.py`、`azure_devops.py`、`backlog.py`、`gitea.py`、`forgejo.py`、`gogs.py`、`gitbucket.py` の各実装における `_to_*` メソッドの `KeyError` 耐性、ページネーション実装の正確性、サービス固有の認証エラーハンドリングは Round 4 以降の対象とすることを推奨する。

- **`git_util.py` の未レビュー**: `get_current_branch()`、`get_last_commit_subject()`、`get_remote_url()` 等が空文字列・エラーを返す場合の下流影響が `pr create` / `init` に波及している。`git_util.py` の入出力バリデーションを独立したラウンドでレビューすることを推奨する。

- **`output.py` の未レビュー**: `output()` 関数が受け取るデータ型・フォーマット指定の組み合わせにおける例外処理が未調査。特に `fmt="json"` 時の `dataclass` シリアライズと `fmt="table"` 時の `fields` 不一致ケース、各フィールドが `None` の場合の表示の一貫性を確認する必要がある。

- **`detect.py` のバリデーション**: `detect_service()` および `detect_from_url()` の入力パターン（SSL なし URL、特殊文字を含む URL、ポート番号付き URL、GitLab のサブグループ構造等）に対するバリデーションが未調査。`_GENERIC_PATH_RE` は `owner/repo` を前提としており、ネストされたパス構造に対応していない可能性がある。

- **`repo view` の設計判断**: `[R3-04]` で指摘した `repo view` の非対称バリデーションについて、設計として「owner を省略して現在の設定リポジトリを参照する」という意図がある可能性がある。設計意図を明確にし、ドキュメント化が必要。

- **統合テストの不足**: 現在のテストスイートは各コマンドのモックベース単体テストが中心であり、実際の CLI 引数パース → ハンドラ → アダプター → HTTP の一気通貫テストが不足している。特に今回発見した重大度「重大」の 6 件（R3-01 〜 R3-06）はテスト追加を次スプリントの優先事項とすることを推奨する。

---

## 修正記録 (2026-03-09)

全 20 件（R3-08・R3-09 はスキップ）を修正完了。

| ID | 修正コミット | 変更ファイル |
|----|------------|------------|
| R3-05 | fix: R3-05 全アダプター _to_* メソッドに KeyError/TypeError ラッピングを追加 | adapter/github.py, gitlab.py, bitbucket.py, azure_devops.py, backlog.py, gitea.py, exceptions.py |
| R3-06 | fix: R3-06 TOML パースエラーを ConfigError に変換 | auth.py, config.py |
| R3-01 | fix: R3-01 --limit 引数に正数バリデーションを追加 | cli.py |
| R3-11 | fix: R3-11 空トークンの保存・使用を防止 | auth.py |
| R3-02/03/13 | fix: R3-02/03/13 issue/milestone/pr create で空タイトルを拒否 | commands/issue.py, milestone.py, pr.py |
| R3-07 | fix: R3-07 paginate_page_param の X-Next-Page 非整数値で ValueError 防止 | http.py |
| R3-08 | スキップ（R1-13 で修正済み） | — |
| R3-04 | fix: R3-04 repo view の owner/repo 形式バリデーションを handle_clone と統一 | commands/repo.py |
| R3-10 | fix: R3-10 auth login でホスト検出失敗時に --host オプションを案内 | commands/auth_cmd.py |
| R3-15 | fix: R3-15 init 対話モードで空の service_type/host を拒否 | commands/init.py |
| R3-09 | スキップ（R2-23 で修正済み） | — |
| R3-16 | fix: R3-16 init --non-interactive でリモート URL 検出失敗時のエラーを改善 | commands/init.py |
| R3-12 | fix: R3-12 paginate_top_skip/paginate_response_body の非 dict レスポンス対応 | http.py |
| R3-14 | fix: R3-14 Link ヘッダーの rel="Next" 大文字小文字非感知マッチ | http.py |
| R3-17 | fix: R3-17/18/19/20 (一括) release create で空タグを拒否 | commands/release.py |
| R3-18 | fix: R3-17/18/19/20 (一括) label create で # 自動除去 + hex バリデーション | commands/label.py |
| R3-19/20 | fix: R3-17/18/19/20 (一括) init --non-interactive でサービス種別の早期バリデーション | commands/init.py |
| R3-21 | fix: R3-21/22 (一括) APPDATA に .strip() 追加 | config.py |
| R3-22 | fix: R3-21/22 (一括) os.getlogin() 失敗時の警告追加 | auth.py |
