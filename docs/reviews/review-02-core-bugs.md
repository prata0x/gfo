# gfo Review Report — Round 1: コアモジュールのバグ・ロジックエラー（統合版）

## 概要

- レビュー日: 2026-03-09
- レビュー回数: 3回（重複排除済み）
- 対象ファイル:
  - `src/gfo/http.py`
  - `src/gfo/config.py`
  - `src/gfo/detect.py`
  - `src/gfo/cli.py`
  - `src/gfo/commands/init.py`
  - `src/gfo/commands/issue.py`
  - `src/gfo/adapter/backlog.py`
  - `src/gfo/adapter/azure_devops.py`（参照確認）
  - `src/gfo/adapter/registry.py`（参照確認）
  - `src/gfo/adapter/base.py`（参照確認）
- 発見事項: 重大 3 / 中 7 / 軽微 4

---

## 発見事項

---

### [R1-01] 🔴 重大 — `paginate_link_header`: `next_url` が更新されず無限ループ／1ページ目のみ取得

- **ファイル**: `src/gfo/http.py` L185
- **説明**:
  Link ヘッダーから次ページ URL を抽出した結果を `url` というローカル変数に代入しているが、ループ条件で参照される変数は `next_url` である。
  `next_url` は初期値 `None` のまま更新されないため、次ループでは常に `if next_url is None` が真となり、
  初回と同じ `path`（1ページ目）に再リクエストが送られ続ける。
  Link ヘッダーが存在するレスポンスが継続する限り、同一ページを無限にフェッチする無限ループとなる。

  ```python
  # 現在の誤ったコード（L185）
  url = match.group(1)          # next_url に代入すべき

  # 正しいコード
  next_url = match.group(1)
  ```

- **影響**: GitHub / Gitea / GitBucket 等を対象とするすべての `list_*` 操作で、2ページ目以降のデータが取得不能。
  かつサーバーがページ末尾で Link ヘッダーを返さなくなるまで、または `limit` に達するまで
  1ページ目と同一データを繰り返し取得するため、メモリ膨張と余分な API リクエストが発生する。
  実務上は GitHub の rate limit に先に到達してエラー終了するが、正しいデータは返らない。
  `limit` 上限によりループを脱出できる場合でも、常に1ページ目だけを `limit` 件数分取得してしまう。
- **推奨修正**: L185 の `url = match.group(1)` を `next_url = match.group(1)` に変更する。
- **テスト**:
  - 2ページ以上のモックレスポンスを用意し、2ページ目のデータが結果に含まれることを確認するテスト
  - 2ページ目の URL が1ページ目と異なることを `mock.call_args_list` で確認するテスト
  - `limit=0`（無制限）で呼んだときに全ページを回収するテスト
  - `Link` ヘッダーがない最終ページで正常終了するテスト
  - `limit` を超えた際に途中でループが打ち切られることを確認するテスト
- **検出回数**: 3/3

---

### [R1-02] 🔴 重大 — `commands/issue.py`: サービス名文字列がアンダースコア表記でハイフン表記と不一致

- **ファイル**: `src/gfo/commands/issue.py` L31, L35
- **説明**:
  `handle_create` 内で `config.service_type` を文字列比較しているが、プロジェクト全体で使用している正規の識別子は `"azure-devops"`（ハイフン）である。
  コード上の比較値は `"azure_devops"`（アンダースコア）となっており、常に不一致となる。
  `registry.py`・`config.py`・`detect.py` はすべて `"azure-devops"` を使用している。

  ```python
  # 現状（誤り）— L31
  if config.service_type == "azure_devops":
      kwargs["work_item_type"] = args.type

  # 正しいコード
  if config.service_type == "azure-devops":
      kwargs["work_item_type"] = args.type
  ```

  `"azure_devops"` の比較が失敗するため、Azure DevOps ユーザーが `--type` を指定しても
  `work_item_type` が `kwargs` に追加されず、`AzureDevOpsAdapter.create_issue` のデフォルト値 `"Task"` が常に使用される。
  `"backlog"` の比較（L35）は文字列が正しい（ハイフンなし）ため問題ない。

- **影響**: Azure DevOps で `gfo issue create --type Bug` 等を実行しても WorkItemType が反映されず、
  常に `Task` タイプのワークアイテムが作成される。ユーザーにはエラーが表示されず、無言でデフォルト値が使われる。
  実質的に Azure DevOps の作業項目タイプ指定機能が無効化されている。
- **推奨修正**: L31 を `config.service_type == "azure-devops"` に変更する。
- **テスト**:
  - `config.service_type = "azure-devops"` かつ `args.type = "Bug"` でハンドラを呼んだ際、`adapter.create_issue` に `work_item_type="Bug"` が渡されることをモックで検証するユニットテスト
  - `config.service_type = "azure_devops"`（アンダースコア）では渡されないことを回帰テストとして残す
- **検出回数**: 3/3

---

### [R1-03] 🔴 重大 — `adapter/backlog.py`: `Issue.number` に `str` が代入される型不一致

- **ファイル**: `src/gfo/adapter/backlog.py` L89
- **説明**:
  `_to_issue` メソッド内で `Issue.number` を以下のように構築している。

  ```python
  # 現状（誤り）
  number=data["issueKey"].split("-")[-1] if isinstance(data.get("issueKey"), str) else data["id"],

  # 正しいコード
  number=int(data["issueKey"].split("-")[-1]) if isinstance(data.get("issueKey"), str) else data["id"],
  ```

  `issueKey` は `"PROJECT-123"` 形式の文字列であり、`.split("-")[-1]` の結果は文字列 `"123"` となる。
  一方 `Issue` データクラス（`base.py`）は `number: int` と宣言されており、`@dataclass(frozen=True, slots=True)` で
  型強制は行われないため実行時エラーにはならないが、`str` 型の値が `int` フィールドに格納される。
  下流で `adapter.get_issue(args.number)` のように `int` が期待される箇所（`cli.py` の argparse は `type=int` で変換）、
  あるいは数値比較・フォーマット出力で型エラーが発生する可能性がある。

- **影響**: Backlog 使用時に `issue view`・`issue close` で数値比較が失敗する。
  `handle_view(args.number)` の int と `Issue.number`（str）の型不一致でルックアップが失敗し NotFoundError が
  発生する恐れがある。表示上の問題として `gfo issue list` のテーブル表示で文字列ソートになる等の不整合が生じる。
- **推奨修正**: `split("-")[-1]` の結果を `int()` でキャストする。
- **テスト**:
  - `issueKey = "PROJ-42"` を持つダミーデータを `_to_issue` に渡し、`result.number` が `int` 型の `42` であることを検証する
  - `isinstance(issue.number, int)` をアサートするユニットテストを追加する
- **検出回数**: 3/3

---

### [R1-04] 🟡 中 — `config.py` L113: `resolve_project_config` の条件分岐がリモートなし環境で失敗する

- **ファイル**: `src/gfo/config.py` L113
- **説明**:
  `resolve_project_config` の中核ロジックは以下のとおり:

  ```python
  if stype and shost:
      # git config に両方設定されているブロック
      remote_url = gfo.git_util.get_remote_url(cwd=cwd)
      detect_result = gfo.detect.detect_from_url(remote_url)
      ...
  else:
      # 少なくとも一方が未設定 → 自動検出
      detect_result = gfo.detect.detect_service(cwd=cwd)
      ...
  ```

  コメントには「いずれも未設定なら `detect_service()` で自動検出」と書かれており、設定済みの場合に URL パース（`detect_from_url`）が実行される構造自体は正しい。
  しかし設定済みの場合でも `detect_from_url` を呼んでいるため、git remote が存在しない環境
  （例: git config で手動設定したが remote がない場合）で `get_remote_url` が失敗してエラーになる。
  また `detect_from_url` は `service_type` を URL から再判定するが、その結果は使われず
  `stype`（git config の値）が優先されるため、実質 `owner`/`repo` の取得のみが目的であるにもかかわらず、
  不必要な URL パースのサイドエフェクト（失敗リスク）を含んでいる。
  さらに `stype` のみ設定・`shost` 未設定の場合、`else` ブランチで `detect_service()` が呼ばれ `stype` が上書きされる可能性がある。

- **影響**: git config で `gfo.type`/`gfo.host` を明示設定したリポジトリで、かつ remote URL が存在しないまたは不正な場合に `resolve_project_config` が失敗する。
  `detect_from_url` の結果が `owner`/`repo` を上書きするため、git config での `owner`/`repo` 固定手段がない。
- **推奨修正**: git config 設定済みブロック内で `owner`/`repo` が取得できない場合のフォールバックを追加するか、
  `owner`/`repo` を個別に git config で保存する（`gfo.owner`, `gfo.repo`）設計に変更する。
  または `stype and shost` の場合は remote URL 解析を任意（try/except）にする。
- **テスト**:
  - `gfo.type` と `gfo.host` が設定済みで、`get_remote_url` が例外を投げる状況での `resolve_project_config` の挙動を検証するテスト
  - 両方設定済みで `detect_from_url()` だけが呼ばれることを確認するモックテスト
- **検出回数**: 3/3

---

### [R1-05] 🟡 中 — `commands/init.py` L44: `_build_default_api_url` に `organization` が渡されない（Azure DevOps 非対話初期化失敗）

- **ファイル**: `src/gfo/commands/init.py` L44
- **説明**:
  `_handle_non_interactive` 内での API URL 構築:

  ```python
  # 現状（誤り）
  api_url = _build_default_api_url(service_type, host, project=project_key)
  # ↑ organization 引数が抜けている

  # 正しいコード
  api_url = _build_default_api_url(service_type, host, organization=detect_result.organization, project=project_key)
  ```

  `_build_default_api_url` のシグネチャは `(service_type, host, organization=None, project=None)` であるが、
  `organization` 引数が渡されていない。そのため `organization=None`（デフォルト値）で呼ばれる。
  Azure DevOps の場合 `_build_default_api_url` は `organization` が `None` であると
  `ConfigError: Azure DevOps requires organization and project_key.` を送出する。
  なお、L44 時点では `detect_result` がまだ取得されていない（`detect_from_url` の呼び出しは L47-48）ため、
  `_build_default_api_url` の呼び出し順序も見直しが必要である（修正後は `detect_result.organization` を渡せるよう順序を入れ替える）。

- **影響**: `gfo init --non-interactive --type azure-devops` を実行すると、
  `organization` が渡されないため `organization=None` のまま `_build_default_api_url` が呼ばれ、
  必ず `ConfigError: Azure DevOps requires organization and project_key.` で失敗する。
  Azure DevOps での `gfo init --non-interactive` が `--api-url` を省略すると常にエラー。
- **推奨修正**: `detect_from_url()` の呼び出し（L47-48）を `_build_default_api_url` の前に移動し、
  `detect_result.organization` を `organization` として渡す。
- **テスト**:
  - Azure DevOps リポジトリを想定した `_handle_non_interactive` の結合テスト
  - Azure DevOps で `--non-interactive --type azure-devops` を使用した初期化フローのエンドツーエンドテスト
- **検出回数**: 3/3

---

### [R1-06] 🟡 中 — `cli.py` L181: `_subparsers` は argparse の内部 API であり将来の互換性がない

- **ファイル**: `src/gfo/cli.py` L181
- **説明**:
  サブコマンド未指定時のヘルプ表示に argparse の内部属性を直接参照している:

  ```python
  parser._subparsers._group_actions[0].choices[args.command].print_help()
  ```

  `_subparsers` および `_group_actions` はアンダースコアで始まる内部属性であり、
  Python の標準ライブラリである argparse の公開 API ではない。
  Python のマイナーバージョンアップで変更・削除される可能性があり、
  将来のバージョンで `AttributeError` または `IndexError` が発生するリスクがある。
  また、`_group_actions[0]` が必ず存在するという前提が崩れると `IndexError` が発生する。

- **影響**: Python バージョンアップ時に CLI が破損する。
  特にサブコマンドを未指定で呼んだ際（`gfo pr` のみ等）にエラーが発生しユーザー体験が悪化する。
- **推奨修正**: サブパーサーへの参照を `create_parser()` の戻り値と共に管理するか、
  `subparsers.choices` を直接保持する辞書を `_DISPATCH` と同様にモジュール変数として持つ。
  または `set_defaults(func=...)` パターンでサブパーサーごとにデフォルトハンドラを設定する。

  ```python
  # 例: create_parser でサブパーサー辞書を返す設計
  def create_parser() -> tuple[argparse.ArgumentParser, dict]:
      ...
      return parser, subparser_map
  ```

- **テスト**:
  - サブコマンド未指定（`gfo issue` のみ）の場合に exit code 1 でヘルプが出力されるテスト
  - `gfo pr`（サブコマンドなし）実行で `AttributeError` が発生しないことを検証するテスト
- **検出回数**: 3/3

---

### [R1-07] 🟡 中 — `detect.py` L198-203: Gitea/Forgejo/Gogs の判定順序と精度に問題がある

- **ファイル**: `src/gfo/detect.py` L198-203
- **説明**:
  `probe_unknown_host` 内の Gitea/Forgejo/Gogs 判定ロジック:

  ```python
  if "forgejo" in data:
      return "forgejo"
  if "go-version" in data or "go_version" in data:
      return "gitea"
  if "version" in data:
      return "gogs"
  ```

  Gogs の判定が `"version" in data` のみに依存しており、
  他サービスが同エンドポイントに `version` キーを含むレスポンスを返した場合に誤判定が発生しうる。
  また Forgejo は Gitea フォークであり、一部バージョンの Forgejo は `/api/v1/version` に `"forgejo"` キーを持たない。
  その場合 `"go_version"` や `"version"` キーから `"gitea"` や `"gogs"` と誤判定される。
  さらに `"go_version"` または `"go-version"` が存在しない旧バージョンの Gitea を Gogs と誤判定する可能性がある。

- **影響**: 未知ホストの自動検出で Gogs ホストが誤って Gitea または別サービスと判定される可能性がある。
  一部 Forgejo インスタンスで `"gitea"` と誤検出される。将来 Forgejo 固有の機能を実装した際に問題が顕在化する。
  影響範囲は `probe_unknown_host` が呼ばれる場合（既知ホスト・git config・hosts.toml 未設定時）に限定される。
- **推奨修正**: Gogs 判定を `"version" in data and "go-version" not in data and "forgejo" not in data` のように
  除外条件を追加する。また `/api/v1/version` の `"source_url"` や `"app_name"` フィールドで Forgejo を識別するロジックを追加する。
  判定ロジックにコメントを追加し、Gitea/Gogs/Forgejo の `/api/v1/version` レスポンス仕様を明記しておく。
- **テスト**:
  - `{"version": "0.13.0"}` を返すモックで `"gogs"` が返ることを確認するテスト
  - `{"version": "1.21.0", "go_version": "go1.21"}` で `"gitea"` が返ることを確認するテスト
  - Forgejo の旧バージョン形式のモックレスポンスで正しく `"forgejo"` が返ることのテスト
  - Gitea/Forgejo/Gogs それぞれのダミーレスポンスで正しいサービス種別が返ることを確認するテスト
- **検出回数**: 3/3

---

### [R1-08] 🟡 中 — `detect.py` L237: `detect_service` で `service_type` を無条件上書きすることで `host` との不整合が発生しうる

- **ファイル**: `src/gfo/detect.py` L237
- **説明**:
  `detect_service()` の git config ショートカット分岐（L234-238）で、
  `detect_from_url()` の結果に `result.service_type = stype` を直接代入している。
  URL パースで得られた `service_type` を git config の値で**無条件上書き**するため、
  `detect_from_url` が `None` 以外の値を返した場合でも検証なしに置き換わる。

  また、`result.host` は `detect_from_url()` で得られた値であり、
  git config の `gfo.host` とは異なる可能性があるが、`result.host` は上書きされない。
  この場合、`detect_service()` が返す `DetectResult` の `service_type` と `host` が
  互いに矛盾した組み合わせになりうる。

- **影響**: `gfo.type` に誤った値を設定したユーザーがエラーメッセージを受け取れず、
  誤ったアダプターが選択される。
- **推奨修正**: git config ショートカット分岐でも `stype` と URL パース結果の `service_type` が
  一致しない場合に警告を出すか、`result.host` を `shost` で上書きする一貫性を持たせる。
- **テスト**:
  - `gfo.type=github` を設定しつつ GitLab の URL を remote に持つ場合の `detect_service()` テスト
- **検出回数**: 1/3

---

### [R1-09] 🟡 中 — `http.py` L79-96: リトライが1回固定でハードコードされており仕様がドキュメントにない

- **ファイル**: `src/gfo/http.py` L79–L96
- **説明**:
  429 を受けたとき `Retry-After` 秒待機して1回だけ再送するが、再送後も同一エラーが返った場合、
  `RateLimitError` がキャッチされずそのまま呼び出し元に伝播する。
  これ自体は意図的（1回のみリトライ）である可能性があるが、リトライが1回固定でハードコードされており、
  再送でも同一エラーが返った場合に呼び出し元が `RateLimitError` を受け取るという仕様がドキュメントにない。

- **影響**: 継続的なレート制限（例: CI/CD 環境）では1回のリトライで不十分。
  呼び出し元が `RateLimitError` のハンドリングを実装していない場合、エラーメッセージなしで失敗する。
- **推奨修正**: リトライ回数を設定可能にするか、少なくともリトライ失敗時の `RateLimitError` について docstring に明記する。
- **テスト**:
  - 429 → 429 の2連続レスポンスで `RateLimitError` が呼び出し元に伝播するテスト
  - 429 → 200 のリトライ成功テスト
- **検出回数**: 1/3

---

### [R1-10] 🟡 中 — `commands/issue.py` L35: `args.priority` の falsy 評価で `0` が無視される

- **ファイル**: `src/gfo/commands/issue.py` L35
- **説明**:
  ```python
  if args.priority and config.service_type == "backlog":
      kwargs["priority"] = args.priority
  ```
  `args.priority` が CLI から文字列として受け取られる場合、空文字列 `""` は falsy となり正しく動作しない。
  argparse の定義では `--priority` は `type` 未指定の文字列引数であるため、
  ユーザーが `--priority 0` を渡した場合に `"0"` は truthy だが、将来的に `type=int` に変更された場合は
  `0` が falsy となり条件が成立しなくなる。
  現状は Backlog の priority が正の整数 ID のため実害は小さいが、設計上の脆弱性がある。

- **影響**: `--priority 0` や空値が falsy 評価されると、ユーザーの意図した priority が無視される。
- **推奨修正**: `if args.priority is not None and config.service_type == "backlog":` と明示的な `None` チェックに変更する。
- **テスト**:
  - `args.priority = "0"` および `args.priority = 0` のいずれの場合でも `kwargs["priority"]` が設定されることを検証するテスト
- **検出回数**: 1/3

---

### [R1-11] 🟢 軽微 — `http.py` L165, L243: `paginate_link_header` / `paginate_response_body` が `_session` を直接アクセスし認証パラメータをバイパス

- **ファイル**: `src/gfo/http.py` L165, L243
- **説明**:
  2ページ目以降のリクエストで `client._session.get(next_url, timeout=30)` とプライベートメンバーに直接アクセスしている。
  これにより `HttpClient.request` が提供する以下の機能がバイパスされる:
  - 429 Rate Limit 時の自動リトライ
  - `_mask_api_key` によるエラーメッセージ内 API キーのマスク
  - `merged_params`（`_auth_params`, `_default_params`）の付与

  `backlog.py` の `auth_params={"apiKey": token}` を使用するアダプターでは、
  2ページ目以降のリクエストに `apiKey` が付与されず 401 エラーが発生する可能性がある。
  同様のパターンが `paginate_response_body`（Bitbucket 用、L243）にも存在する。

- **影響**: `auth_params` を使用するアダプターで2ページ目以降が 401 で失敗する可能性がある。
  Rate limit エラーが自動リトライされずユーザーに即時エラーが返される。
  Backlog は Link-header ベースのページネーションではなくオフセット方式を使うため現状は顕在化しないが、設計上の欠陥。
- **推奨修正**: `HttpClient` に `request_absolute_url(url)` または `get_absolute(url)` のようなメソッドを追加し、
  絶対 URL に対しても認証パラメータを付与できるようにする。
  または `next_url` を相対パスに変換して既存の `client.get` を利用する設計に変更する。
- **テスト**:
  - `auth_params` を持つ `HttpClient` で `paginate_link_header` の2ページ目が正しく認証されることを確認するテスト
- **検出回数**: 3/3

---

### [R1-12] 🟢 軽微 — `commands/init.py` L87: Azure DevOps 対話モードで `organization=None` 時のエラーメッセージが不親切

- **ファイル**: `src/gfo/commands/init.py` L87
- **説明**:
  対話モードで Azure DevOps が自動検出された場合、`_build_default_api_url(service_type, host, organization, project_key)` は正しく呼ばれる。
  しかし `detect_result.organization` が `None` であるケース（URL パースで org が解決できなかった場合）では
  `ConfigError: Azure DevOps requires organization and project_key.` が発生し、対話中に唐突に失敗する。
  ユーザーへのエラーメッセージが不親切。
  また関数の型シグネチャ上 `DetectResult.service_type` は `str | None` であり、
  `None` のまま `_build_default_api_url` に渡ると `ConfigError("Unknown service type: None")` が発生する可能性がある（型チェッカーがエラーを報告する）。

- **影響**: Azure DevOps の特殊な URL 形式（`*.visualstudio.com` 等）で org が解決できなかった場合、対話初期化が中断する。
  型アノテーション上の不整合により mypy がエラーを報告する。
- **推奨修正**: `ConfigError` をキャッチして「organization を手動入力してください」プロンプトにフォールバックする。
  `service_type` が `None` の場合の assert または型ナローイングを追加する。
- **テスト**:
  - `organization=None` で検出された Azure DevOps において対話モードが適切なプロンプトを表示するテスト
  - mypy による静的型チェックの CI 導入
- **検出回数**: 2/3

---

### [R1-13] 🟢 軽微 — `http.py` L80: `Retry-After` ヘッダーが日時形式の場合 `int()` 変換で `ValueError` が発生する

- **ファイル**: `src/gfo/http.py` L80
- **説明**:
  `request` メソッドのリトライ処理で:

  ```python
  wait = int(resp.headers.get("Retry-After", 60))
  ```

  `Retry-After` ヘッダーが HTTP 日時形式（例: `Fri, 09 Mar 2026 12:00:00 GMT`）で提供された場合、
  `int()` 変換が `ValueError` を発生させ、リトライ処理そのものがクラッシュする。
  RFC 7231 では `Retry-After` は秒数整数または HTTP 日時形式の両方を許容している。

- **影響**: 一部の API サーバー（RFC 7231 準拠の日時形式 `Retry-After` を使用するサービス）で
  Rate Limit エラー時に `ValueError` が発生しアプリケーションがクラッシュする。
- **推奨修正**: `int()` 変換を try/except で包み、変換失敗時はデフォルト値（例: 60秒）を使用する。
- **テスト**:
  - `Retry-After: Fri, 09 Mar 2026 12:00:00 GMT` ヘッダーを持つ 429 レスポンスで `request` を呼び、
    `ValueError` が発生しないことを確認するテスト
- **検出回数**: 1/3

---

## サマリーテーブル

| ID | 重大度 | ファイル | 行 | 説明 | 検出回数 |
|----|--------|----------|----|------|----------|
| R1-01 | 🔴 重大 | `http.py` | L185 | `next_url` への代入漏れ — 2ページ目以降取得不能・無限ループ | 3/3 |
| R1-02 | 🔴 重大 | `commands/issue.py` | L31 | `"azure_devops"`（アンダースコア）— 正しくは `"azure-devops"` | 3/3 |
| R1-03 | 🔴 重大 | `adapter/backlog.py` | L89 | `issueKey.split("-")[-1]` が `str` — `Issue.number` は `int` | 3/3 |
| R1-04 | 🟡 中 | `config.py` | L113 | `resolve_project_config` 条件分岐 — リモートなし環境で失敗する | 3/3 |
| R1-05 | 🟡 中 | `commands/init.py` | L44 | Azure DevOps 非対話 init で `organization` 未渡し | 3/3 |
| R1-06 | 🟡 中 | `cli.py` | L181 | argparse 内部 API `_subparsers._group_actions` の直接参照 | 3/3 |
| R1-07 | 🟡 中 | `detect.py` | L198-203 | Gogs/Gitea/Forgejo プローブ判別の精度不足 | 3/3 |
| R1-08 | 🟡 中 | `detect.py` | L237 | `service_type` の無条件上書きで `host` との不整合が発生しうる | 1/3 |
| R1-09 | 🟡 中 | `http.py` | L79–L96 | リトライが1回固定でハードコード・仕様がドキュメントなし | 1/3 |
| R1-10 | 🟡 中 | `commands/issue.py` | L35 | `args.priority` の falsy 評価で `0` が無視される | 1/3 |
| R1-11 | 🟢 軽微 | `http.py` | L165, L243 | `_session` 直接アクセスで `auth_params` が付与されない | 3/3 |
| R1-12 | 🟢 軽微 | `commands/init.py` | L87 | Azure DevOps 対話初期化で `organization=None` 時のエラーが不親切 | 2/3 |
| R1-13 | 🟢 軽微 | `http.py` | L80 | `Retry-After` が日時形式の場合 `int()` で `ValueError` | 1/3 |

---

## 推奨アクション (優先度順)

1. **[R1-01] 即時修正**: `http.py` L185 の `url = match.group(1)` を `next_url = match.group(1)` に変更する。
   GitHub/Gitea/GitBucket ユーザー全員に影響する最重要バグ。全件取得機能が壊れており対応必須。

2. **[R1-02] 即時修正**: `commands/issue.py` L31 の `"azure_devops"` を `"azure-devops"` に変更する。
   Azure DevOps ユーザーの作業項目タイプ指定が完全に無効化されており、エラーが出ないため発見困難。

3. **[R1-03] 即時修正**: `adapter/backlog.py` L89 で `int()` キャストを追加する。
   Backlog ユーザーの `issue view` / `issue close` が型不一致で失敗する。

4. **[R1-05] 高優先**: `init.py` の `_handle_non_interactive` で `detect_from_url()` の呼び出し順序を修正し、
   `detect_result.organization` を `_build_default_api_url` に渡す。Azure DevOps での非対話 init が完全に失敗する問題を修正。

5. **[R1-11] 高優先**: `paginate_link_header` と `paginate_response_body` の2ページ目以降のリクエストを
   `client._session` 直接呼び出しから `HttpClient` の公開 API 経由に変更する。
   R1-01 と合わせて修正すると Backlog の認証も正常化する。

6. **[R1-04] 中優先**: `resolve_project_config` の条件ロジックを整理し、
   remote URL 解析の失敗に対する耐障害性を高める。

7. **[R1-06] 中優先**: argparse 内部 API の使用を排除し、サブパーサー辞書をモジュール変数として管理する。
   Python バージョンアップ時の互換性問題を事前に排除する。

8. **[R1-07] 中優先**: `detect.py` の Gogs 判定に除外条件を追加し、Forgejo の旧バージョンへの対応を強化する。

9. **[R1-08] 低優先**: `detect_service` のショートカット分岐で `host` も `gfo.host` で上書きする
   一貫性を持たせ、設定不整合を警告する仕組みを追加する。

10. **[R1-09] 低優先**: リトライロジックを設定可能にするか、動作仕様を docstring に明記する。

11. **[R1-10] 低優先**: `commands/issue.py` L35 の `if args.priority` を `if args.priority is not None` に変更する。

12. **[R1-12] 低優先**: Azure DevOps 対話初期化のエラーハンドリングを改善し、`organization` 未解決時のユーザー向けプロンプトを追加する。型ナローイングを追加し mypy を CI に導入する。

13. **[R1-13] 低優先**: `http.py` L80 の `int()` 変換を try/except で保護し RFC 準拠サーバーとの互換性を確保する。

---

## 次ラウンドへの申し送り

- **アダプター層の網羅的レビューが未実施**: `adapter/azure_devops.py`・`adapter/github.py`・`adapter/gitlab.py`・`adapter/bitbucket.py` 等の `_to_issue`/`_to_pull_request` 変換メソッドに同様の型不一致・フィールドマッピング誤りがないか確認が必要。

- **`commands/pr.py` 等の他コマンドハンドラ**: `issue.py` と同様に Azure DevOps 固有の kwargs 処理が存在する場合、同じサービス名表記バグ（アンダースコア vs ハイフン）を持つ可能性がある。横断確認を推奨する。

- **`registry.py` の `create_http_client` と `create_adapter` 内での `stype` 文字列整合性**: 各アダプターに `@register("azure-devops")` が付与されているか確認が必要。

- **`auth.py` / `credentials.py` のレビュー未実施**: トークン保存・取得ロジック、credentials.toml の権限設定（ファイルパーミッション）、`resolve_token` のフォールバック順序を確認すること。

- **`output.py` の型安全性**: `Issue.number` が `str` で渡されたときのフォーマット出力の挙動（ソート順、表示等）の確認。テーブル/JSON/plain 各形式の実装を確認する。

- **`git_util.py` のエラーハンドリング**: `git_config_get`、`git_config_set`、`get_remote_url` の実装と、git リポジトリ外で呼ばれた際の挙動を確認すること。

- **R1-11 の根本設計**: `HttpClient` が絶対 URL へのリクエストをサポートしていない設計的制約が複数箇所に影響を与えている。`request_absolute_url` メソッドの追加かアーキテクチャ変更を次ラウンドの設計レビューで議論すること。

- **`paginate_page_param` の `X-Next-Page` 空文字判定**: GitLab では最終ページで `X-Next-Page` ヘッダーが空文字になることが仕様だが、ヘッダーが存在しない場合と空文字の場合を同一視している。現状は `not next_page` で両方捕捉しているため問題ないが、GitLab API 仕様変更時のリスクとして記録しておく。

- **統合テストの欠如**: 現在のテストはユニットテスト中心であり、`resolve_project_config` → `create_adapter` → `list_issues` の全フローを通した統合テストが存在しない。E2E テストのモック設計を検討すること。
