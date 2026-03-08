# 振り返り (Retrospective)

タスクごとの振り返りを蓄積するファイル。

---

## T-01: パッケージ構造・プロジェクト設定

### 発生した問題

1. **hatchling の build-backend パス誤り**
   - `build-backend = "hatchling.backends"` と書いたが正しくは `"hatchling.build"`
   - `pip install -e ".[dev]"` が `BackendUnavailable: Cannot import 'hatchling.backends'` で失敗
   - 教訓: hatchling の正しいエントリポイントは `hatchling.build`

2. **`__pycache__` をコミットに含めてしまった**
   - `.gitignore` を作成せずにコミットしたため `src/gfo/__pycache__/*.pyc` がトラッキング対象に
   - 追加コミットで `.gitignore` 作成 + `git rm -r --cached` で除外
   - 教訓: プロジェクト初期セットアップでは `.gitignore` をファイル作成と同時に用意する

### うまくいった点

- `src/` レイアウト + hatchling の組み合わせは問題なく動作
- `__main__.py` に暫定バージョン表示を入れる方針で `python -m gfo --version` 検証をクリア

---

## T-02: exceptions.py — 全エラー型の定義

### 発生した問題

- 特になし

### うまくいった点

- design.md に完全なコードが記載されていたため、そのまま移植するだけで実装が完了した
- テスト 28 件が全パスし、スムーズに完了

---

## T-03: git_util.py — git コマンドラッパー関数

### 発生した問題

- 特になし

### うまくいった点

- プランが明確で実装・テスト共にスムーズに完了（18テスト全パス）

---

## T-04: http.py — HttpClient + ページネーション関数

### 発生した問題

1. **`paginate_link_header` の重複リクエストバグ**
   - 初回実装時に分岐ロジックが重複し、同じリクエストが2回発行されるコードになっていた
   - 変数名を `next_url` に統一し、分岐を整理して解消

2. **`responses` ライブラリの URL マッチング**
   - `responses.add()` でクエリパラメータ付きURLを登録しても、ベースURLの部分一致で先に登録したモックがマッチし続ける問題
   - `query_param_matcher` でも解決せず、最終的にコールバックベース (`add_callback`) でリクエスト回数に基づく分岐に変更して解決
   - 教訓: `responses` ライブラリでページネーションのマルチページテストを書く際は `add_callback` が確実

### うまくいった点

- design.md の仕様が詳細で、HttpClient の構造・ページネーション関数のシグネチャをそのまま実装できた
- 43テスト全パス、既存テスト (89件) にも影響なし

---

## T-05: detect.py — サービス自動検出

### 発生した問題

1. **`import gfo.config` による `gfo` 名前空間の衝突**
   - `detect_service()` 内で `import gfo.config` を関数内 import したところ、モジュールレベルの `import gfo.git_util` と衝突し `UnboundLocalError` が発生
   - Python は関数内に `import gfo.config` があると `gfo` をローカル変数と見なし、それ以前の `gfo.git_util` 参照が失敗する
   - 解決: `import gfo.git_util` → `from gfo.git_util import get_remote_url, git_config_get` に変更
   - 教訓: 関数内 import でパッケージ名を使う場合、同じパッケージ名のモジュールレベル import との衝突に注意

2. **`_AZURE_PATH_RE` のオプショナルグループによる誤マッチ**
   - design.md の正規表現 `(?:_git/)?` がオプショナルだったため、`project/_git/repo` が `org=project, project=_git, repo=repo` と誤パースされた
   - 解決: `_AZURE_GIT_PATH_RE` (`_git/` 必須) と `_AZURE_V3_PATH_RE` (`v3/` プレフィックス) の2つに分離
   - さらに `*.visualstudio.com` では path に org がないため `(?:(?P<org>[^/]+)/)?` でオプショナル化
   - 教訓: design.md の正規表現をそのまま使う前に、各パターンの実際の URL でマッチ結果を検証すべき

### うまくいった点

- URL パース 18件 + API プローブ 8件 + 統合フロー 5件 = 31テスト全パス、既存テスト (89件) にも影響なし
- Backlog SSH 特殊処理 (ホスト名正規化 + path lstrip) がプラン通りに動作

---

## T-06: config.py — 3層設定解決 + TOML読み込み

### 発生した問題

1. **Windows で環境変数全クリア時に `Path.home()` が失敗するテスト問題**
   - テストで `monkeypatch.delenv()` を使い環境変数を全クリアすると、Windows 環境では `Path.home()` が `USERPROFILE` / `HOMEDRIVE`+`HOMEPATH` を参照できず `RuntimeError` になる
   - テスト側で必要な環境変数を保持するよう調整して解決

### うまくいった点

- design.md の仕様が明確で、3層設定解決 (デフォルト → TOML → 環境変数) の実装がスムーズに進んだ
- 32テスト全パス、既存テスト (120件) にも影響なし

---

## T-07: auth.py — トークン解決 + credentials.toml 管理

### 発生した問題

1. **`get_auth_status()` の型アノテーションバグ**
   - `result: list[dict[str, str]] = {}` と dict リテラルで初期化してしまった
   - 正しくは `= []`。実装直後に気づいて即修正

2. **Windows での `os.chmod` テスト失敗**
   - `sys.platform` を `"linux"` に mock して POSIX パーミッションテストを書いたが、Windows では `os.chmod(path, 0o600)` が実際には POSIX パーミッションを設定しない
   - 解決: `os.chmod` 自体を mock し、引数 `0o600` で呼ばれたことを検証する方式に変更

### うまくいった点

- design.md の仕様が明確で、4段フォールバック (`credentials.toml` → サービス別環境変数 → `GFO_TOKEN` → `AuthError`) の実装がスムーズ
- T-06 の retro で学んだ「Windows 環境変数全クリアで `Path.home()` が失敗する」問題を回避できた（`monkeypatch.delenv` で必要変数のみ操作）
- 16テスト全パス、既存152テストにも影響なし（計168テスト）

---

## T-08: adapter/base.py — データクラス

### 発生した問題

- 特になし

### うまくいった点

- design.md に完全なコード定義があり、6つの frozen dataclass をそのまま実装するだけで完了
- 15テスト全パス、既存テストにも影響なし

---

## T-09: adapter/base.py — ABC 定義

### 発生した問題

- 特になし

### うまくいった点

- design.md L1043-1170 に ABC の完全な定義があり、そのまま移植するだけで完了
- 抽象メソッド18個 + 具象メソッド `get_pr_checkout_refspec` のデフォルト実装を追加
- 4テスト全パス、既存テストにも影響なし

---

## T-10: adapter/registry.py + output.py

### 発生した問題

- 特になし

### うまくいった点

- design.md の擬似コードがほぼそのまま実装に使えた
- output.py: table/json/plain の3フォーマッタ + output 関数を実装。dataclasses.asdict/fields を活用しシンプルに
- registry.py: register デコレータ + get_adapter_class + create_adapter ファクトリを実装。9サービスの認証方式を網羅
- 29テスト全パス、既存テストにも影響なし

---

## T-11: adapter/github.py — GitHubAdapter

### 発生した問題

- 特になし

### うまくいった点

- design.md の PR 関連実装例 (L1282-1334) をベースに、残り15メソッド + 5変換ヘルパーを GitHub REST API パターンに沿ってスムーズに実装
- list_issues で PR 除外フィルタ (`"pull_request" not in data`)、list_pull_requests の merged フィルタなど GitHub 固有の注意点を計画通り処理
- conftest.py に共通フィクスチャ (mock_responses, github_client, github_adapter) を用意し、後続アダプターテストでも再利用可能な構造に
- 38テスト全パス (変換8 + PR11 + Issue6 + Repo5 + Release2 + Label3 + Milestone3 + Registry1)、全254テストにも影響なし

---

## T-12: adapter/gitlab.py — GitLabAdapter

### 発生した問題

- 特になし

### うまくいった点

- T-11 (GitHub) のコード構造をベースに、GitLab API v4 の差異を計画通りに反映できた
- 主な差異対応: プロジェクトパスの URL エンコード (`urllib.parse.quote`)、state マッピング (`open` ↔ `opened`)、MR 用語 (`/merge_requests`)、`paginate_page_param` (`X-Next-Page` ヘッダー方式)、close/merge の PUT + `state_event`、author (`data["author"]["username"]`)、Label color の `#` プレフィックス除去
- conftest.py の `mock_responses` フィクスチャを GitHub テストと共有し、`gitlab_client` / `gitlab_adapter` を追加するだけで済んだ
- 38テスト全パス (変換8 + MR11 + Issue6 + Repo5 + Release2 + Label3 + Milestone3 + Registry1)、全292テストにも影響なし

---

## T-13: adapter/bitbucket.py — BitbucketAdapter

### 発生した問題

- 特になし

### うまくいった点

- T-11/T-12 で確立したアダプター実装パターンに沿い、スムーズに実装完了
- Bitbucket 固有の差異を計画通りに反映: state 大文字→小文字変換 (`OPEN`→`open`, `DECLINED`/`SUPERSEDED`→`closed`, `MERGED`→`merged`)、ネストされた branch 名 (`source.branch.name`)、`paginate_response_body` (`values`/`next` キーによるレスポンスボディベースページネーション)、Issue の `content.raw` → `body`、assignee 単一値→リスト化、`links.clone` から https の href 抽出
- Release/Label/Milestone の 6 メソッドを `NotSupportedError` で実装し、テストでも全て検証
- 36テスト全パス (変換10 + PR9 + Issue6 + Repo5 + NotSupported6 + Registry1)、全116アダプターテスト・既存テストにも影響なし

---

## T-14: adapter/azure_devops.py — AzureDevOpsAdapter

### 発生した問題

- 特になし

### うまくいった点

- T-11〜T-13 で確立したアダプター実装パターンに沿い、スムーズに実装完了
- Azure DevOps 固有の複雑な仕組みを計画通りに反映: `refs/heads/` の自動付与/除去ヘルパー (`_add_refs_prefix`/`_strip_refs_prefix`)、PR state マッピング (`active`↔`open`, `abandoned`↔`closed`, `completed`↔`merged`)、merge strategy マッピング (`merge`→`noFastForward`, `squash`→`squash`, `rebase`→`rebase`)、WIQL 2段階クエリ (POST wiql → バッチ GET workitems)、JSON Patch 形式 (`application/json-patch+json`) での Work Item 作成/更新、`$top/$skip` ページネーション (`paginate_top_skip`)
- Work Item の state 変換で `frozenset` を使い、Closed/Done/Removed → "closed"、それ以外 → "open" を簡潔に実装
- `_to_repository` はインスタンスメソッド (`self._project` を `full_name` に使用) とし、他の変換ヘルパーは `@staticmethod` で統一
- 49テスト全パス (変換12 + PR11 + Issue8 + Repo4 + NotSupported6 + RefsPrefix5 + Registry1 + Refspec1 + Checkout1)

---

## T-15: adapter/gitea.py — GiteaAdapter

### 発生した問題

- 特になし

### うまくいった点

- GitHub API とほぼ互換のため、`github.py` をベースに `per_page_key="limit"` の差分のみ反映するだけで実装完了
- T-11〜T-14 で確立したアダプター実装・テストパターンに沿い、非常にスムーズに進んだ
- Gitea 固有の検証として、ページネーション4箇所 (`list_pull_requests`, `list_issues`, `list_repositories`, `list_releases`) で `limit` パラメータが使われ `per_page` が使われないことを明示的にテスト
- 後続の T-16 (Forgejo) と T-17 (Gogs) が継承する基底クラスとして安定した実装を提供
- 41テスト全パス (変換8 + PR7 + Issue7 + Repo5 + Release3 + Label3 + Milestone3 + Registry1 + Checkout1 + limit検証4)、全418テストにも影響なし

---

## T-16: adapter/forgejo.py — ForgejoAdapter

### 発生した問題

- 特になし

### うまくいった点

- T-15 (Gitea) の継承設計通り、`GiteaAdapter` を継承し `service_name = "Forgejo"` のみオーバーライドする最小実装で完了
- `forgejo.py` 本体は9行 (docstring・import・クラス定義含む) と非常にシンプル
- テストは Registry・継承確認・service_name・PR list の4件で継承の意図を明確に検証
- 4テスト全パス、全既存テストにも影響なし

---

## T-17: adapter/gogs.py — GogsAdapter

### 発生した問題

- 特になし

### うまくいった点

- T-15/T-16 の継承パターンに沿い、`GiteaAdapter` を継承する最小実装でスムーズに完了
- `_web_url()` で `urllib.parse.urlparse` を使い、`scheme://hostname[:port]` を抽出する設計が明快で再利用しやすい
- PR 5メソッドは `web_url` 付き、Label/Milestone 4メソッドは `web_url=None` という使い分けを `NotSupportedError` の `web_url` 属性で表現でき、テストで全9パターンを網羅
- ポート番号付き URL (`http://gogs.local:3000/api/v1` → `http://gogs.local:3000`) の検証も `TestWebUrl` で明示的にカバー
- 15テスト全パス、全既存テストにも影響なし

---

## T-18: adapter/gitbucket.py — GitBucketAdapter

### 発生した問題

- 特になし

### うまくいった点

- T-16 (Forgejo) と同じ最小継承パターンで、`GitHubAdapter` を継承し `service_name = "GitBucket"` のみオーバーライドする実装が11行で完了
- GitHub v3 互換 API のため追加オーバーライドは不要で、レジストリの `"gitbucket"` エントリが既に存在していたため登録もスムーズ
- テストは Registry・継承確認・service_name・PR list の4件で意図を明確に検証
- 4テスト全パス、全既存テストにも影響なし

---

## T-19: adapter/backlog.py — BacklogAdapter

### 発生した問題

- 特になし

### うまくいった点

- `paginate_offset` が既に `http.py` に用意されていたため、Backlog のオフセットページネーションをそのまま利用できた
- `_ensure_project_id()` と `_resolve_merged_status_id()` の遅延取得キャッシュにより、API 呼び出しを必要最小限に抑えられた
- `_to_issue()` で `issueKey`（例: `"TEST-42"`）から末尾の数字部分を取り出す設計がシンプルかつ実用的
- `create_issue()` で `issue_type`/`priority` 未指定時に API から自動取得しつつ、指定済みの場合は API 呼び出しをスキップする最適化も実装
- `merge_pull_request()` の `NotSupportedError` に `web_url` を付与し、ユーザーがブラウザで直接マージできるよう誘導
- 42テスト全パス、全271既存テストにも影響なし

---

## T-20: adapter/__init__.py — 全アダプター登録

### 発生した問題

- 特になし

### うまくいった点

- 全9アダプター (github, gitlab, bitbucket, azure-devops, gitea, forgejo, gogs, gitbucket, backlog) を `import` するだけでレジストリへの自動登録が完了する設計が機能した
- T-10 (registry.py) の `@register` デコレータパターンにより、`__init__.py` は9行のシンプルな実装で済んだ
- 3テスト全パス (全サービス登録確認・クラス取得・未対応サービスエラー)、全既存テストにも影響なし

---

## T-21: commands/pr.py — PR コマンドハンドラ

### 発生した問題

1. **`format_json` の1件リスト出力がオブジェクトになるテスト失敗**
   - `output.py` の `format_json` は1件のリストを単一オブジェクトとして出力する仕様だった
   - テストで `isinstance(data, list)` を assert したため失敗
   - 解決: `list` と `dict` 両方に対応するアサーションに修正
   - 教訓: `output.py` の仕様 (1件→オブジェクト、複数→配列) をテスト設計時に確認すること

### うまくいった点

- design.md L1648-1699 に全6ハンドラの擬似コードが揃っており、そのまま実装に移せた
- `git_util.py` に `git_fetch` / `git_checkout_new_branch` が既に実装済みで、`handle_checkout` をシームレスに実装できた
- `unittest.mock.patch` + `MagicMock` を活用し、`resolve_project_config` / `create_adapter` / `gfo.git_util.*` をすべてモック化したユニットテストを構築できた
- `tests/test_commands/conftest.py` に共通フィクスチャ (`make_args`) を用意し、後続コマンドテストで再利用可能な構造にした
- 14テスト全パス、全500テストにも影響なし

---

## T-22: commands/issue.py — issue コマンドハンドラ

### 発生した問題

- 特になし

### うまくいった点

- T-21 (pr.py) で確立したコマンドハンドラ実装・テストパターンをそのまま適用でき、スムーズに完了
- `handle_create` の kwargs 分岐 (`azure_devops` → `work_item_type`、`backlog` → `issue_type`/`priority`) を `config.service_type` で判定する設計がシンプルかつ明快
- `_patch_all` コンテキストマネージャを `contextlib.contextmanager` + `with` で構成し、各テストで簡潔に再利用できる構造にした
- `setup_method` でフィクスチャを初期化することで、クラス内の各テストメソッドが独立した状態で実行されるようにした
- 14テスト全パス（TestHandleList 4件 + TestHandleCreate 6件 + TestHandleView 2件 + TestHandleClose 2件）

---

## T-23: commands/repo.py — repo コマンドハンドラ

### 発生した問題

- 特になし

### うまくいった点

- `_resolve_host_without_repo` の3段フォールバック (args_host → `detect_service()` → `get_default_host()`) を計画通りに実装できた
- service_type 解決で `get_host_config` → `probe_unknown_host` → `_KNOWN_HOSTS` の順にフォールバックする設計がシンプルかつ網羅的
- `handle_create` でサービス別 `HttpClient` 構築ロジックを `registry.py` の `create_adapter` と同じパターンで実装し、一貫性を保てた
- `handle_clone` のサービス別 URL 構築ロジック (github/gitlab/bitbucket/azure-devops/gitea-forgejo-gogs/gitbucket/backlog) をプランの URL テーブル通りに実装
- T-21/T-22 で確立した `_patch_all` コンテキストマネージャパターンをそのまま流用し、ボイラープレートを最小化
- `handle_create` / `handle_clone` のテストでは `_resolve_host_without_repo` 自体をモックすることで、ホスト解決ロジックと切り離した独立テストを構成できた
- 19テスト全パス（TestHandleList 2件 + TestResolveHostWithoutRepo 5件 + TestHandleCreate 2件 + TestHandleClone 7件 + TestHandleView 3件）

---

## T-24: commands/init.py — init コマンドハンドラ

### 発生した問題

- 特になし

### うまくいった点

- 対話モードと `--non-interactive` モードを `getattr(args, "non_interactive", False)` で切り替える設計がシンプルかつテストしやすかった
- 対話モードで `DetectionError` 発生時に手動入力へフォールバックする分岐を `try/except` で自然に表現できた
- `_handle_non_interactive` での api_url 解決順 (`args.api_url` → `get_host_config` → `_build_default_api_url`) が config.py の `resolve_project_config` と一貫したパターンになった
- `builtins.input` を `patch` でモックすることで、対話モードの各入力シナリオを `side_effect=iter([...])` で簡潔にテストできた
- T-21〜T-23 で確立したコマンドテストパターン（`patch` + `make_args`）をそのまま流用し、ボイラープレートを最小化
- 11テスト全パス（TestHandleInteractive 5件 + TestHandleNonInteractive 6件）

---

## T-25: commands/auth_cmd.py — auth コマンドハンドラ

### 発生した問題

- 特になし

### うまくいった点

- `handle_login` の `args.host` / `args.token` 両方オプションのロジックが、`detect_service()` との連携含めシンプルに実装できた
- `gfo.auth.save_token` / `gfo.detect.detect_service` を `patch("gfo.commands.auth_cmd.gfo.auth.save_token")` 形式の完全修飾パスでモックすることで、テストが他モジュールの実装に依存しない独立した構造になった
- `handle_status` のテーブル出力は `output.py` の `output()` 関数が dataclass 専用のため自前で組んだが、列幅を動的に計算するシンプルな実装で対応できた
- T-21〜T-24 で確立したコマンドテストパターン（`patch` + `make_args` + `capsys`）をそのまま流用でき、ボイラープレートを最小化
- 6テスト全パス（TestHandleLogin 4件 + TestHandleStatus 2件）

---

## T-26: commands/release.py — release コマンドハンドラ

### 発生した問題

- 特になし

### うまくいった点

- T-21〜T-25 で確立したコマンドハンドラ実装・テストパターンをそのまま適用でき、スムーズに完了
- `handle_create` の `title = args.title or args.tag` フォールバックがシンプルかつ直感的に表現できた
- `adapter.create_release` のシグネチャ (`tag`, `title`, `notes`, `draft`, `prerelease`) が `base.py` の ABC と完全に一致しており、実装に迷いがなかった
- `_patch_all` コンテキストマネージャ + `setup_method` フィクスチャ初期化パターンにより、8テストが全て独立した状態で実行される構造を維持できた
- 8テスト全パス（TestHandleList 3件 + TestHandleCreate 5件）

---

## T-27: commands/label.py — label コマンドハンドラ

### 発生した問題

- 特になし

### うまくいった点

- T-26 (release.py) のパターンをそのまま踏襲し、`handle_list` / `handle_create` を最小限のコードで実装できた
- `Label` データクラスが `name`, `color`, `description` の3フィールドのみで、release と異なり `limit` 引数が不要なためさらにシンプルな実装になった
- `handle_list` のテストで `list_labels.assert_called_once_with()` (引数なし) を明示的に検証し、limit 引数が渡らないことを確認できた
- `test_create_without_color` で `color=None`, `description=None` のケースを明示的にカバーし、オプション引数の None 伝播を検証した
- 5テスト全パス（TestHandleList 3件 + TestHandleCreate 2件）

---

## T-28: commands/milestone.py — milestone コマンドハンドラ

### 発生した問題

- 特になし

### うまくいった点

- T-27 (label.py) のパターンをそのまま踏襲し、`handle_list` / `handle_create` を最小限のコードで実装できた
- CLI 引数 `--due` → adapter 引数 `due_date` のマッピングを `args.due` → `due_date=args.due` で明示的に行い、テスト `test_due_to_due_date_mapping` で `"due"` キーが渡らないことを確認した
- `Milestone` データクラスが `number`, `title`, `description`, `state`, `due_date` の5フィールドで、`handle_list` の `fields` 指定も計画通り `["number", "title", "state", "due_date"]` で実装できた
- `test_create_without_optional_args` で `description=None`, `due=None` のケースを明示的にカバーし、オプション引数の None 伝播を検証した
- 6テスト全パス（TestHandleList 3件 + TestHandleCreate 3件）

---

## T-29: cli.py — CLI 統合実装

### 発生した問題

1. **argparse 位置引数への `dest` 指定エラー**
   - `repo_clone.add_argument("name", dest="repo")` と書いたところ `ValueError: dest supplied twice for positional argument` で失敗
   - argparse では位置引数の `dest` は第一引数そのものが名前になるため、`dest` を別途指定できない
   - 解決: `add_argument("repo")` と引数名を直接 `repo` にすることで `args.repo` が使えるようになった
   - 教訓: argparse 位置引数の `dest` はオプション引数専用。位置引数を `dest` で別名にしたい場合は引数名自体を変える

### うまくいった点

- T-21〜T-28 で全コマンドハンドラが完成していたため、`create_parser()` + `_DISPATCH` の実装に集中できた
- `main()` のサブコマンド未指定ハンドリングで `parser._subparsers._group_actions[0].choices[args.command].print_help()` を使い、コマンド別 help 表示を実現できた
- `NotSupportedError` の `web_url` を stdout、エラーメッセージを stderr に分けて出力することで、パイプ利用時にURLだけを抽出できる設計を実装できた
- 38テスト全パス（パーサー27件 + ディスパッチ3件 + main8件）、全607テストにも影響なし
