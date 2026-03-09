# gfo Review Report — Round 7: コード品質・設計パターン・保守性（統合版）

## 概要
- レビュー日: 2026-03-09
- レビュー回数: 3回（重複排除済み）
- 対象ファイル:
  - `src/gfo/__init__.py`, `src/gfo/cli.py`, `src/gfo/__main__.py`
  - `src/gfo/auth.py`, `src/gfo/config.py`, `src/gfo/detect.py`
  - `src/gfo/exceptions.py`, `src/gfo/git_util.py`, `src/gfo/http.py`, `src/gfo/output.py`
  - `src/gfo/adapter/base.py`, `src/gfo/adapter/registry.py`
  - `src/gfo/adapter/github.py`, `src/gfo/adapter/gitlab.py`, `src/gfo/adapter/gitea.py`
  - `src/gfo/adapter/gogs.py`, `src/gfo/adapter/forgejo.py`, `src/gfo/adapter/gitbucket.py`
  - `src/gfo/adapter/bitbucket.py`, `src/gfo/adapter/azure_devops.py`, `src/gfo/adapter/backlog.py`
  - `src/gfo/commands/pr.py`, `src/gfo/commands/issue.py`, `src/gfo/commands/release.py`
  - `src/gfo/commands/repo.py`, `src/gfo/commands/label.py`, `src/gfo/commands/milestone.py`
  - `src/gfo/commands/auth_cmd.py`, `src/gfo/commands/init.py`
- 発見事項: 重大 5 / 中 13 / 軽微 6

---

## 発見事項

---

### [R7-01] 🔴 `paginate_link_header` が次ページURLを `next_url` に代入せず2ページ目以降を取得しない

- **ファイル**: `src/gfo/http.py` L181-185
- **説明**: `paginate_link_header` のループ末尾でLinkヘッダーから次ページURLを取得しているが、変数名が `url` になっており `next_url` に代入されていない。そのため次のループ反復では常に `next_url is None` が真になり、常に1ページ目を再取得し続ける無限ループが発生するか（`limit` が `per_page` より大きい場合）、または `limit <= per_page` の場合は1ページ目だけを返して終了する。
  ```python
  match = re.search(r'<([^>]+)>;\s*rel="next"', link)
  if not match:
      break
  url = match.group(1)   # ← next_url = match.group(1) であるべき
  ```
  `next_url` は L158 で初期化されているが、ループ内で一度も再代入されない。
- **影響**: GitHub/Gitea/Forgejo/GitBucket アダプターで `limit > per_page` の場合にページネーションが機能しない。`limit` をデフォルト（30）より大きく設定した場合、常に最初の1ページのみ返される。無限ループの可能性もある（1ページが30件ちょうどで `limit > 30` の場合）。
- **推奨修正**: `url = match.group(1)` を `next_url = match.group(1)` に変更する（1行修正）。
- **テスト**: `limit=60` かつ1ページあたり30件のレスポンスを2回返すモックで、60件すべてが返されることを確認するテスト。また `limit=100`, `per_page=30` の複数ページシナリオの統合テスト。
- **検出回数**: 3/3

---

### [R7-02] 🔴 `paginate_link_header` / `paginate_response_body` 内でプライベートAPIを直接参照

- **ファイル**: `src/gfo/http.py` L165, L170, L243, L248
- **説明**: ページネーション関数内でページネーションの2ページ目以降を取得する際、`HttpClient` の内部セッション `client._session` を直接参照している（`client._session.get(next_url, timeout=30)`）。これは `HttpClient` のパブリック API を迂回してセッションオブジェクトを直接操作しており、`_handle_response` の呼び出しも個別に追加する必要が生じている。`paginate_link_header` と `paginate_response_body` の両方に同パターンが存在する（L165, L170 および L243, L248）。
- **影響**: `HttpClient` の内部実装（`_session`、リトライロジック等）を変更するとページネーション関数が静かに壊れる。認証付きリダイレクトURLへの対応が困難になる。テスト時にモックが複雑になる。
- **推奨修正**: `HttpClient` に `get_absolute(url: str, ...)` のようなパブリックメソッドを追加し、絶対URLへのGETリクエストをカプセル化する。ページネーション関数はそのメソッドを呼び出す。
- **テスト**: `HttpClient._session` を差し替えても `paginate_link_header` が正常動作することを確認するテスト。`get_absolute` 追加後のリグレッションテスト。
- **検出回数**: 3/3

---

### [R7-03] 🔴 `GitHubAdapter` と `GiteaAdapter` の変換メソッドが完全重複

- **ファイル**: `src/gfo/adapter/github.py` L27-103、`src/gfo/adapter/gitea.py` L27-103
- **説明**: `_to_pull_request`、`_to_issue`、`_to_repository`、`_to_release`、`_to_label`、`_to_milestone` の6メソッドがほぼ完全に同一（APIレスポンスのフィールド名が両サービスで一致しているためコードが文字列レベルで一致している）。`merged_at` を確認して `state` を決定し、`user.login`、`head.ref`、`base.ref` を参照する構造が一致。`GitBucketAdapter` は `GitHubAdapter` を継承しており、`ForgejoAdapter` は `GiteaAdapter` を継承しているため、この重複は間接的にさらに広がっている。
- **影響**: バグ修正やフィールド変更を両ファイルに同時適用しなければならず、片方への修正漏れがサービス間の動作差異を生む。GitHub API / Gitea API の仕様が変わった場合、同一のバグ修正を2箇所に行う必要がある。
- **推奨修正**: `GiteaAdapter` が `GitHubAdapter` を継承するよう変更し差分のある部分のみオーバーライドするか、`GitHubLikeAdapter` などの中間基底クラスを作成し共通変換ヘルパー群をそこに集約する（`GitHubAdapter`、`GiteaAdapter`、`GitBucketAdapter` がそれを継承）。
- **テスト**: 同一入力 dict で両アダプターの変換メソッドが同一出力を返すことを確認する回帰テスト。変換ロジックの単体テストを基底クラスに対して書き、両アダプターでのパラメトライズドテストで確認する。
- **検出回数**: 3/3

---

### [R7-04] 🔴 `DetectResult` が `dataclass` だが `frozen=True` でなく mutable

- **ファイル**: `src/gfo/detect.py` L15-27, L238
- **説明**: `DetectResult` は `@dataclass` で定義されているが `frozen=True` も `slots=True` も指定されていない。一方、`base.py` の `PullRequest`/`Issue`/`Repository`/`Release`/`Label`/`Milestone` はすべて `@dataclass(frozen=True, slots=True)` を使用している。この設計の不一致により、`DetectResult` のフィールドが外部から書き換え可能な状態になっている。実際に `detect_service()` 内（L238）で `result.service_type = stype` と直接フィールドへの代入が行われており、これは意図的な設計だが、`frozen=True` の他データクラスとの一貫性が欠如している。コメントによる意図の明示もない。
- **影響**: `DetectResult` インスタンスを複数箇所で参照している場合、一箇所での書き換えが意図せず他箇所に影響するリスクがある。ハッシュ化・辞書キーとして使えない。コードの読者が「なぜここだけ mutable なのか」を理解する追加コストが生じる。
- **推奨修正**: `frozen=True` にして `detect_service()` 内では `dataclasses.replace(result, service_type=stype)` を使用する。または mutable である設計理由をクラスのドキュメントに明記する。`detect_service()` 内の直接代入も同時に `dataclasses.replace()` に統一する。
- **テスト**: `detect_service()` が `DetectResult.service_type` を正しく設定するシナリオのテスト。`detect_service()` の戻り値を書き換えても元の `result` が変化しないことを検証するテスト。
- **検出回数**: 3/3

---

### [R7-05] 🔴 `GogsAdapter` の全メソッドに型ヒントがない

- **ファイル**: `src/gfo/adapter/gogs.py` L26-60
- **説明**: `GogsAdapter` の全オーバーライドメソッド（`list_pull_requests`、`create_pull_request`、`get_pull_request`、`merge_pull_request`、`close_pull_request`、`list_labels`、`create_label`、`list_milestones`、`create_milestone`）がすべて型ヒントなしで定義されている。親クラス `GiteaAdapter` および `GitServiceAdapter` では全メソッドに型ヒントが付与されている。例: `def list_pull_requests(self, *, state="open", limit=30):` — 戻り値型も引数型も省略されている。
- **影響**: mypy / pyright などの静的型チェッカーが `GogsAdapter` に対して機能しない。基底クラスの抽象メソッドと異なるシグネチャが存在してもエラーにならない。IDEの補完・ドキュメント生成が機能しない。コードの一貫性が損なわれる。
- **推奨修正**: 親クラスのシグネチャをコピーして型ヒントを付与する。例: `def list_pull_requests(self, *, state: str = "open", limit: int = 30) -> list[PullRequest]:`
- **テスト**: mypy を CI に組み込み `gogs.py` のエラーが検出・解消されることを確認するテスト。`mypy --strict` によるゼロエラーを CI で確認。
- **検出回数**: 3/3

---

### [R7-06] 🟡 `issue.py` の Azure DevOps サービス種別文字列バグ（タイポ）

- **ファイル**: `src/gfo/commands/issue.py` L31
- **説明**: `config.service_type == "azure_devops"` と比較しているが、実際のサービス種別文字列は `"azure-devops"`（ハイフン区切り）である。`_REGISTRY`（registry.py L39）、`_SERVICE_ENV_MAP`（auth.py L23）、`_KNOWN_HOSTS`（detect.py L73）すべてが `"azure-devops"` を使用しており、アンダースコア版は存在しない。この条件は常に `False` になるため、Azure DevOps でも `work_item_type` が `kwargs` に渡されない。
- **影響**: Azure DevOps で `gfo issue create --type Epic` 等のオプションが無視される機能バグ。`work_item_type` が渡されないため `AzureDevOpsAdapter.create_issue` のデフォルト値 `"Task"` が常に使用される。ユーザーが指定した `--type` 引数が無視される。
- **推奨修正**: `"azure_devops"` を `"azure-devops"` に修正する（1文字の変更）。
- **テスト**: `service_type="azure-devops"` の場合に `work_item_type` が `kwargs` に含まれることを確認するテスト。`--type Bug` を指定した際に `create_issue(work_item_type="Bug")` が呼ばれることを確認するテスト。
- **検出回数**: 2/3

---

### [R7-07] 🟡 ページネーション関数間の共通ロジック重複

- **ファイル**: `src/gfo/http.py` L145-330
- **説明**: `paginate_link_header`、`paginate_page_param`、`paginate_response_body`、`paginate_offset`、`paginate_top_skip` の5関数はすべて「レスポンスを取得→データ抽出→リストへの追加→上限チェック→次ページ判定→ループ」という同一の骨格を持つ。絶対URLへの直接GETと `_handle_response` 呼び出しのパターン（`paginate_link_header` L164-171、`paginate_response_body` L243-249）が完全に同一コードで重複している。また、リスト切り詰め処理（`results = results[:limit]` + `break`）も5箇所に重複している。
- **影響**: 上限チェックや絶対URL直接GET処理を変更する場合（タイムアウト値変更、ヘッダー追加など）、複数箇所を同時に修正する必要があり、片方の変更漏れによる動作差異が生じやすい。
- **推奨修正**: 絶対URLへの直接GETロジックを `_fetch_absolute_url(client, url)` のような内部ヘルパーに切り出す。`_collect_pages(fetcher: Callable, limit: int) -> list[dict]` などの共通スケルトンを導入し、各ページネーション関数はフェッチロジックのみを実装する戦略パターンに統一することも検討する。
- **テスト**: `paginate_link_header` と `paginate_response_body` で次ページ取得時の HTTP エラーが同様に処理されることを確認するテスト。`limit=0`（無制限）、`limit=1`（最小）でのページネーション動作テスト。
- **検出回数**: 3/3

---

### [R7-08] 🟡 コマンドハンドラの定型パターン重複

- **ファイル**: `src/gfo/commands/` 以下の全ハンドラファイル（各 L13-25 付近）
- **説明**: すべてのコマンドハンドラ関数が「`resolve_project_config()` → `create_adapter(config)` → APIメソッド呼び出し → `output()`」という同一パターンを繰り返している。`pr.py`、`issue.py`、`label.py`、`milestone.py`、`release.py`、`repo.py` の合計15個以上のハンドラ関数で、最初の2行（`config = resolve_project_config()` / `adapter = create_adapter(config)`）が完全に重複している。
- **影響**: `create_adapter` のシグネチャ変更や設定解決ロジックの変更時に全ハンドラを修正する必要がある。テストでのモックも各ファイルで個別に設定する必要がある。
- **推奨修正**: `def _get_adapter() -> GitServiceAdapter` のような共通ヘルパーを `commands` 共通モジュールに定義するか、デコレータパターンを使って設定解決をラップする。
- **テスト**: アダプター取得ロジックを一元的にモックできるかを確認するテスト。リファクタリング後に全コマンドハンドラが正しくアダプターを取得できることの回帰テスト。
- **検出回数**: 2/3

---

### [R7-09] 🟡 `handle_clone` での URL 構築ロジックの分散（DRY 違反）

- **ファイル**: `src/gfo/commands/repo.py` L104-121
- **説明**: `handle_clone` 内でクローンURLを if/elif チェーン（8分岐）で組み立てている。一方、`config.py` の `_build_default_api_url` にも同様のサービス別分岐が存在する。同じ「サービス種別→URL」マッピングが2箇所に分散しており、DRY 原則に違反している。また `azure-devops` のコメント「`project は owner と同じと仮定`」（L111）は実際の運用で問題が生じる可能性がある不正確な仮定を示している。
- **影響**: 新しいサービスを追加する際に `_build_default_api_url` と `handle_clone` の両方を更新する必要があり、片方への追加漏れが発生しやすい。Azure DevOps のURL構築が不正確な仮定に基づいており、実際のリポジトリURLと一致しない場合がある。
- **推奨修正**: `GitServiceAdapter` に `clone_url_for(owner, name) -> str` などの抽象メソッドを追加するか、`build_clone_url(service_type, host, owner, name) -> str` ヘルパーを `config.py` または `registry.py` に集約し、`handle_clone` はその関数を呼び出すのみとする。
- **テスト**: 各サービス種別でのクローン URL 生成テスト。Azure DevOps の org/project 混同ケースのテスト。
- **検出回数**: 3/3

---

### [R7-10] 🟡 `_KNOWN_HOSTS` プライベートシンボルを外部モジュールから直接参照

- **ファイル**: `src/gfo/commands/repo.py` L62-63
- **説明**: `_resolve_host_without_repo()` 内で `from gfo.detect import _KNOWN_HOSTS` と `_KNOWN_HOSTS.get(host)` によって、`detect.py` のプライベート変数を直接参照している。`_KNOWN_HOSTS` は先頭アンダースコアによりモジュールの内部実装として定義されている。この参照は `probe_unknown_host` が `None` を返した場合のフォールバックとして使われており、`detect.py` の公開APIを経由せずに内部テーブルへ直接アクセスしている。
- **影響**: `_KNOWN_HOSTS` の名前・構造が変更された場合に `repo.py` が無通知で壊れる。モジュールの境界が崩れており、`detect.py` の内部実装を安心してリファクタリングできない。意図しない依存関係がパブリックAPIと区別できなくなる。
- **推奨修正**: `detect.py` に `get_known_service_type(host: str) -> str | None` のようなパブリック関数を追加し、`repo.py` はその関数を呼び出す形にする。または `probe_unknown_host` が `_KNOWN_HOSTS` も参照するように拡張する。
- **テスト**: `_KNOWN_HOSTS` に登録されたホストに対して `_resolve_host_without_repo` が正しいサービス種別を返すテスト。`detect.py` の公開 API を通じてホスト解決ができることを確認するテスト。
- **検出回数**: 3/3

---

### [R7-11] 🟡 `backlog.py` のマジックナンバー（ステータスID）が複数箇所に散在

- **ファイル**: `src/gfo/adapter/backlog.py` L57-61, L82, L121, L123, L151, L168, L170, L219
- **説明**: `_to_pull_request` で Backlog の PR ステータス ID を直接数値で判定している（`status_id == 4` が "closed"、`status_id == 5` が "merged"）。同様のマジックナンバーが以下の全9箇所に散在している: `_to_pull_request`（L57: `status_id == 4`、L59: `status_id == 5`）、`_to_issue`（L82: `status_id == 4`）、`list_pull_requests`（L121: `statusId[] = [1, 2, 3]`、L123: `statusId[] = [4]`）、`close_pull_request`（L151: `statusId: 4`）、`list_issues`（L168: `statusId[] = [1, 2, 3]`、L170: `statusId[] = [4]`）、`close_issue`（L219: `statusId: 4`）。`close_pull_request`（L151）と `close_issue`（L219）の両方に `statusId: 4` が重複存在している。
- **影響**: Backlog の statusId の意味が暗号的で、コードを読んだだけでは意味が分からない。ステータスID体系が変わった場合（またはカスタムステータスが導入された場合）、全箇所を修正する必要がある。
- **推奨修正**: `_BACKLOG_PR_STATUS_OPEN = [1, 2, 3]`、`_BACKLOG_STATUS_CLOSED = 4`、`_BACKLOG_PR_STATUS_MERGED = 5` などのクラス定数またはモジュールレベル定数を定義し、すべての数値リテラルを置換する。
- **テスト**: 各 status_id に対する PR/Issue 状態マッピングの単体テスト。
- **検出回数**: 3/3

---

### [R7-12] 🟡 `GitLabAdapter._to_issue` のデッドコード（冗長な state 変換）

- **ファイル**: `src/gfo/adapter/gitlab.py` L54-55
- **説明**: `_to_issue` 内で以下のコードが存在する:
  ```python
  if state == "opened":
      state = "open"
  if state == "closed":
      state = "closed"  # ← 何もしていない
  ```
  2つ目の `if` 文は `state` に `"closed"` を代入しているが、すでに `state` は `"closed"` であるため何の効果もない。意図的な `pass` であれば `elif` にするべきだが、実際には不要なコードが残存している。
- **影響**: コードの読者が「`state == "closed"` の場合に何か特別な処理が必要なのか」と誤解する可能性がある。将来的に "closed" → "resolved" などのマッピングが必要になったとき、このブロックが存在することで誤解が生じる可能性がある。
- **推奨修正**: `if state == "closed": state = "closed"` ブロックを削除する。`state = "open" if state == "opened" else state` の1行に整理できる。
- **テスト**: GitLab の `_to_issue` で `state="closed"` の変換が正しく動作することを確認するテスト（既存テストで十分）。
- **検出回数**: 3/3

---

### [R7-13] 🟡 `GitLabAdapter._to_release` で `draft` と `prerelease` に同一フィールドを使用

- **ファイル**: `src/gfo/adapter/gitlab.py` L87-88
- **説明**: GitLab の Release には GitHub の `draft`/`prerelease` に相当する直接対応フィールドがない。現在の実装では `upcoming_release` を `draft` と `prerelease` の両方にマッピングしている:
  ```python
  draft=data.get("upcoming_release", False),
  prerelease=data.get("upcoming_release", False),
  ```
  `Release` データクラスは `draft` と `prerelease` を独立したフィールドとして定義しているが、常に同値になる。GitLab の `upcoming_release` は「将来リリース予定」を意味し、GitHub の `draft`（未公開）とも `prerelease`（プレリリース）とも意味が異なる。
- **影響**: `Release.draft` と `Release.prerelease` のセマンティクスが GitLab では区別できず、ユーザーが混乱する。フィルタリング等の用途で誤った結果を返す可能性がある。`is_draft` と `is_prerelease` を区別するロジックが `draft=True` かつ `prerelease=True` という矛盾した状態を返す。
- **推奨修正**: GitLab の `upcoming_release` は `prerelease=True` のみにマッピングし、`draft=False` に固定する。または GitLab 独自の別フィールドを参照するよう修正する。設計上の決定をコメントで明示する。
- **テスト**: `upcoming_release=True` の GitLab Release データを変換した場合の `draft` と `prerelease` フィールド値確認テスト。
- **検出回数**: 2/3

---

### [R7-14] 🟡 `AzureDevOpsAdapter._to_repository` が `@staticmethod` でなくインスタンスメソッド

- **ファイル**: `src/gfo/adapter/azure_devops.py` L96-105
- **説明**: 他の全アダプターの `_to_repository` は `@staticmethod` で定義されているが、`AzureDevOpsAdapter._to_repository` のみ `self` を参照するためインスタンスメソッドになっている（`self._project` を参照）。設計の一貫性が欠如しており、クラスの外から静的にデータ変換できない。
- **影響**: テストで `_to_repository` を単独でテストする際にインスタンスが必要になる。シグネチャの不一致がコードの読者に余分な注意を要求する。一貫したパターンを期待するコードが誤動作するリスクがある。
- **推奨修正**: `_to_repository(self, data, project=None)` のようにプロジェクト名を引数として受け取るか、呼び出し元で `full_name` を組み立てる `@staticmethod` に変更する。
- **テスト**: `AzureDevOpsAdapter._to_repository` を `project` パラメータで呼び出せることを確認するユニットテスト。
- **検出回数**: 2/3

---

### [R7-15] 🟡 `http.py` の再試行コードの重複（DRY 違反）

- **ファイル**: `src/gfo/http.py` L63-96
- **説明**: `HttpClient.request` メソッド内で、通常リクエストと 429 再試行後のリクエストが全く同じパラメータ（`method, url, params, json, data, headers, timeout`）でほぼ同一の try/except ブロックを使って2回実行されている（L63-75 と L83-95）。例外処理コードが重複している。
- **影響**: タイムアウト秒数の変更や新しい例外への対応を片方だけに行うバグが起こりやすい。コード行数が不必要に増加する。
- **推奨修正**: リクエスト実行と例外ハンドリングを `_do_request(...)` という内部メソッドに抽出し、`request()` から2回呼び出す。
- **テスト**: 429 受信後のリトライフローをテスト。2回目もタイムアウト設定が適用されることを確認。
- **検出回数**: 1/3

---

### [R7-16] 🟡 `list_labels`/`list_milestones` でページネーション未使用

- **ファイル**: `src/gfo/adapter/github.py` L231-249、`src/gfo/adapter/gitea.py` L232-250
- **説明**: `list_labels()` と `list_milestones()` では `resp.json()` でレスポンス全件を取得しており、`paginate_link_header` を使っていない。一方で `list_pull_requests`、`list_issues` などでは同ページネーション関数を使用している。GitLab では `paginate_page_param` を使用しており正しく実装されている。
- **影響**: ラベルやマイルストーンが30件超のリポジトリでデータの欠落が発生する。GitHub/Gitea アダプターのみに影響し、GitLab 等との動作差異が生じる。
- **推奨修正**: `list_labels()` と `list_milestones()` でも `paginate_link_header` を使用するよう統一する。
- **テスト**: 31件以上のラベルが存在する場合の取得件数を検証するテスト。
- **検出回数**: 1/3

---

### [R7-17] 🟡 `stype`/`shost` 省略変数名の可読性問題

- **ファイル**: `src/gfo/detect.py` L232-233、`src/gfo/config.py` L109-110、`src/gfo/adapter/registry.py` L64
- **説明**: `stype = git_config_get("gfo.type", ...)` / `shost = git_config_get("gfo.host", ...)` という省略変数名が `detect.py`、`config.py`、`registry.py` に散在している。`s` プレフィックスが「saved」「service」「string」のいずれを意図しているか不明瞭でコメントもない。他のコードでは `service_type`/`host` という完全な名前が使われており、局所的に省略名が現れる。`config.py` の `resolve_project_config()` では `stype`/`shost` を複数回使用し、後半で `config.service_type` などの完全名と混在するため混乱しやすい。
- **影響**: コードの可読性が低下する。新規貢献者が変数名の意味を理解するために文脈を追う必要がある。
- **推奨修正**: `service_type_override`、`host_override` など意味が明確な名前に変更するか、少なくとも関数の先頭でコメントを添える。
- **テスト**: 変数名変更は動作に影響しないため新規テスト不要。
- **検出回数**: 3/3

---

### [R7-18] 🟡 `_build_default_api_url` プライベート関数を外部モジュールから直接参照

- **ファイル**: `src/gfo/commands/repo.py` L10、`src/gfo/commands/init.py` L9
- **説明**: `config.py` の `_build_default_api_url`（アンダースコアプレフィックスによりモジュール内部APIを示す）が、`commands/repo.py` および `commands/init.py` で直接インポート・使用されている。`_` プレフィックスは「このモジュール外からは使わない」ことを示す慣例だが、その慣例が守られていない。
- **影響**: `_build_default_api_url` のシグネチャや戻り値の変更が、テストなしで外部コードを壊す可能性がある。モジュールの境界が崩れており、`config.py` の内部実装を安心してリファクタリングできない。
- **推奨修正**: `_build_default_api_url` を `build_default_api_url`（パブリック）に名前変更するか、あるいは `resolve_project_config` と同様のファクトリ関数を通じて外部公開する。
- **テスト**: `config.py` の公開 API のみを使用しているかを確認するリント/テスト。
- **検出回数**: 1/3

---

### [R7-19] 🟢 `cli.py` の `argparse` 内部プライベート属性参照

- **ファイル**: `src/gfo/cli.py` L181
- **説明**: サブコマンド未指定時のヘルプ表示に以下のコードを使用している:
  ```python
  parser._subparsers._group_actions[0].choices[args.command].print_help()
  ```
  `_subparsers`、`_group_actions` はいずれも `argparse` の内部プライベート属性（`_` プレフィックス）で、Python のバージョン間で互換性が保証されていない。
- **影響**: Python の argparse 実装が変更されると、このコードが `AttributeError` で突然クラッシュする可能性がある。特に Python のマイナーバージョンアップでも内部実装は変更されうる。
- **推奨修正**: `subparsers` オブジェクトを変数に保持しておき `subparsers.choices` を直接参照する方法か、サブパーサーの辞書を `create_parser()` で `dict` として保持し `cli.py` から参照できるようにする。
- **テスト**: `gfo pr`（サブコマンドなし）実行時にヘルプが表示されることの確認テスト。サブコマンド未指定時に正常にヘルプが表示されることを確認するテスト。
- **検出回数**: 2/3

---

### [R7-20] 🟢 `auth.py` の `get_auth_status` で `host` フィールドに異なる意味の値が混在

- **ファイル**: `src/gfo/auth.py` L111-122
- **説明**: `get_auth_status()` では credentials.toml のトークンに対して `"host"` キーにホスト名（例: `github.com`）を設定するが、環境変数のエントリでは `"host"` キーにサービス種別（例: `"github"`）を設定している:
  ```python
  result.append({
      "host": service_type,  # ← "github" などサービス種別が入る
      "source": f"env:{env_var}",
  })
  ```
  同じキー `"host"` に異なる意味の値（ホスト名 vs サービス種別）が入る設計の不一致がある。さらに、環境変数ループでは `seen_hosts` セットへの追加が行われないため、同一のサービスに複数の環境変数が割り当てられている場合（例: forgejo, gogs, gitea がすべて `GITEA_TOKEN` を参照）、複数のエントリが出力される可能性がある。
- **影響**: `gfo auth status` の出力で環境変数設定時の `HOST` 列に `github.com` ではなく `github` が表示され、ユーザーが混乱する可能性がある。将来的に `HOST` 列でフィルタリングや照合を行う処理を追加した場合にバグになる。同一トークンを参照する重複エントリが表示される可能性がある。
- **推奨修正**: 環境変数の場合も実際のホスト名を `HOST` 列に表示するか、キー名を `"identifier"` などに変更して意味の曖昧さを排除する。環境変数ループでも `seen_hosts` にエントリを追加する。
- **テスト**: `get_auth_status` の返却値で `host` フィールドの内容が credentials.toml と環境変数で一貫しているかの確認テスト。複数サービスが同じ環境変数を共有するケースでの出力テスト。
- **検出回数**: 2/3

---

### [R7-21] 🟢 `create_adapter` / `create_http_client` の対称性欠如

- **ファイル**: `src/gfo/adapter/registry.py` L29-76
- **説明**: `create_adapter` は `backlog` と `azure-devops` のみ `kwargs` に追加パラメータを設定し、`create_http_client` は `backlog`/`bitbucket`/`azure-devops`/`gitlab`/`github`/`gitea` 系の分岐を持つ。両関数が同じ `service_type` を `if/elif` で個別に扱っており、新サービス追加時に両方の更新が必要で漏れやすい構造になっている。
- **影響**: 新しいサービス追加時に `create_adapter` と `create_http_client` の両方に分岐を追加する必要があり、片方の追加漏れが静的チェックでは検出されない。
- **推奨修正**: アダプタークラスに `@classmethod build_http_client(cls, api_url, token)` と `@classmethod build_kwargs(cls, config)` を持たせ、`create_adapter` がアダプタークラス側にロジックを委譲する設計にする。
- **テスト**: 新サービス追加時の統合テスト。
- **検出回数**: 1/3

---

### [R7-22] 🟢 `detect.py` の `_BACKLOG_PATH_RE` と `_GITBUCKET_PATH_RE` が同一パターン

- **ファイル**: `src/gfo/detect.py` L54-60
- **説明**: `_BACKLOG_PATH_RE = re.compile(r"^git/(?P<project>[^/]+)/(?P<repo>[^/]+)$")` と `_GITBUCKET_PATH_RE = re.compile(r"^git/(?P<owner>[^/]+)/(?P<repo>[^/]+)$")` は同一の正規表現パターン（`git/xxx/yyy`）であり、キャプチャグループ名のみ異なる。コメントがなければ区別が難しく、どちらかが誤って変更された場合に差異が生まれやすい。
- **影響**: 正規表現の変更（例: ポートを含むパスへの対応）を両方に適用する必要がある。コードの重複により保守性が低下する。
- **推奨修正**: 共通の `_GIT_PATH_RE` を定義し、マッチ後にグループ名を解釈するロジックを別に書くか、利用箇所での命名で意図を明確にする。
- **テスト**: Backlog/GitBucket それぞれのパスパースの単体テスト。
- **検出回数**: 1/3

---

### [R7-23] 🟢 `detect.py` の `hosts[result.host]` を `hosts.get(result.host)` に改善

- **ファイル**: `src/gfo/detect.py` L255-256
- **説明**: `detect_service()` の step 3 で `result.service_type = hosts[result.host]`（L256）と直接インデックスアクセスしている。実際には外側に `if result.host in hosts:`（L255）の確認があるため問題ないが、`hosts.get(result.host)` を使う方が安全かつ意図がより明確になる。
- **影響**: 現状は安全に動作しているが、将来のリファクタリングで `in` チェックが外れた場合に `KeyError` が発生するリスクがある。
- **推奨修正**: `result.service_type = hosts[result.host]` を `result.service_type = hosts.get(result.host)` に変更する。
- **テスト**: config.toml の hosts 参照のケースを含む detect_service テスト。
- **検出回数**: 1/3

---

## サマリーテーブル

| ID | 重大度 | ファイル | 行 | 説明 | 検出回数 |
|----|--------|---------|------|------|----------|
| R7-01 | 🔴 重大 | `src/gfo/http.py` | L185 | `paginate_link_header` で `url` を `next_url` に代入せず2ページ目以降が取得されない | 3/3 |
| R7-02 | 🔴 重大 | `src/gfo/http.py` | L165, L170, L243, L248 | ページネーション関数内で `client._session`/`_handle_response` のプライベートAPI直接参照 | 3/3 |
| R7-03 | 🔴 重大 | `src/gfo/adapter/github.py`, `gitea.py` | L27-103 | `_to_*` 変換メソッド6種が完全重複 | 3/3 |
| R7-04 | 🔴 重大 | `src/gfo/detect.py` | L15-27, L238 | `DetectResult` が `frozen=True` でなく mutable、他データクラスと設計不一致 | 3/3 |
| R7-05 | 🔴 重大 | `src/gfo/adapter/gogs.py` | L26-60 | 全オーバーライドメソッドに型ヒント欠如 | 3/3 |
| R7-06 | 🟡 中 | `src/gfo/commands/issue.py` | L31 | `"azure_devops"` vs `"azure-devops"` の文字列不一致バグ | 2/3 |
| R7-07 | 🟡 中 | `src/gfo/http.py` | L145-330 | 5つのページネーション関数の共通骨格・上限チェックが重複 | 3/3 |
| R7-08 | 🟡 中 | `src/gfo/commands/` 全ハンドラ | 各 L13-16 | コマンドハンドラの定型2行が15箇所以上に重複 | 2/3 |
| R7-09 | 🟡 中 | `src/gfo/commands/repo.py` | L104-121 | `handle_clone` の clone URL 構築が `config.py` と二重定義 | 3/3 |
| R7-10 | 🟡 中 | `src/gfo/commands/repo.py` | L62-63 | `_KNOWN_HOSTS` プライベート定数の外部直接参照 | 3/3 |
| R7-11 | 🟡 中 | `src/gfo/adapter/backlog.py` | L57-61, L82, L121, L123, L151, L168, L170, L219 | マジックナンバー（ステータスID 4/5）が9箇所に散在 | 3/3 |
| R7-12 | 🟡 中 | `src/gfo/adapter/gitlab.py` | L54-55 | `_to_issue` の `if state == "closed": state = "closed"` デッドコード | 3/3 |
| R7-13 | 🟡 中 | `src/gfo/adapter/gitlab.py` | L87-88 | `_to_release` で `draft`/`prerelease` に同一フィールドを使用 | 2/3 |
| R7-14 | 🟡 中 | `src/gfo/adapter/azure_devops.py` | L96-105 | `_to_repository` が `@staticmethod` でなくインスタンスメソッド | 2/3 |
| R7-15 | 🟡 中 | `src/gfo/http.py` | L63-96 | 429 リトライの try/except ブロック重複 | 1/3 |
| R7-16 | 🟡 中 | `src/gfo/adapter/github.py`, `gitea.py` | L231-250 | `list_labels`/`list_milestones` でページネーション未使用（30件超で欠落） | 1/3 |
| R7-17 | 🟡 中 | `src/gfo/detect.py`, `config.py`, `registry.py` | 複数 | `stype`/`shost` 省略変数名の可読性問題 | 3/3 |
| R7-18 | 🟡 中 | `src/gfo/commands/repo.py`, `init.py` | L10, L9 | プライベート `_build_default_api_url` の外部参照 | 1/3 |
| R7-19 | 🟢 軽微 | `src/gfo/cli.py` | L181 | `argparse` の内部プライベート属性 `_subparsers._group_actions` 参照 | 2/3 |
| R7-20 | 🟢 軽微 | `src/gfo/auth.py` | L111-122 | `get_auth_status` の `host` フィールドに異なる意味の値が混在・環境変数重複エントリ | 2/3 |
| R7-21 | 🟢 軽微 | `src/gfo/adapter/registry.py` | L29-76 | `create_adapter`/`create_http_client` の対称性欠如 | 1/3 |
| R7-22 | 🟢 軽微 | `src/gfo/detect.py` | L54-60 | `_BACKLOG_PATH_RE` と `_GITBUCKET_PATH_RE` が同一パターン | 1/3 |
| R7-23 | 🟢 軽微 | `src/gfo/detect.py` | L255-256 | `hosts[result.host]` を `hosts.get(result.host)` に改善余地 | 1/3 |

---

## 推奨アクション (優先度順)

1. **[R7-01] `paginate_link_header` のバグ修正（`url` → `next_url`）** — 1行の変更で修正できる重大バグ。GitHub/Gitea/Forgejo/GitBucket の全アダプターで `limit > per_page` 時にページネーションが機能していない。即時修正が必要。修正後は複数ページにわたる統合テストを追加する。

2. **[R7-06] Azure DevOps サービス種別文字列バグの修正** — `"azure_devops"` → `"azure-devops"` への1文字修正。Azure DevOps ユーザーの `--type` 引数が常に無視される実際の動作バグ。修正コストが最小。

3. **[R7-02] ページネーション関数のプライベートAPI直接参照をリファクタリング** — `HttpClient` に `get_absolute(url: str)` パブリックメソッドを追加し、カプセル化を回復する。[R7-07] の重複削減も同時に実施することで効果が大きい。

4. **[R7-03] GitHub/Gitea 変換メソッドの重複解消** — `GiteaAdapter` が `GitHubAdapter` を継承するか `GitHubLikeAdapter` 中間基底クラスを作成し、6メソッドの重複（最大のDRY違反）を解消する。[R7-16] のページネーション対応も同時に行う。

5. **[R7-05] `GogsAdapter` の型ヒント追加** — 親クラスシグネチャをコピーして型ヒントを付与するだけで型安全性が向上。mypy のCI統合と合わせて対応する。

6. **[R7-04] `DetectResult` の設計明確化** — `frozen=True` にして `dataclasses.replace()` に統一するか、mutable である設計理由をドキュメントに明記する。

7. **[R7-10] `_KNOWN_HOSTS` の公開API化** — `detect.py` に `get_known_service_type(host: str) -> str | None` を追加し、内部API参照を解消する。合わせて [R7-18] の `_build_default_api_url` のパブリック化も実施する。

8. **[R7-11] Backlog マジックナンバーの定数化** — クラス定数として `_STATUS_CLOSED = 4` 等を定義し、9箇所の数値リテラルを置換する。

9. **[R7-12] GitLab `_to_issue` のデッドコード削除** — 1行削除するだけで修正完了。[R7-13] の `draft`/`prerelease` マッピング修正と合わせてPRにまとめる。

10. **[R7-09] `handle_clone` の URL 構築ロジックを集約** — 新サービス追加時の変更箇所を1か所にまとめる。アダプターに `clone_url_for` 抽象メソッドを追加する。

11. **[R7-08] コマンドハンドラの定型パターン共通化** — `resolve_project_config()` + `create_adapter()` を共通ヘルパーに集約し全コマンドのボイラープレートを削減する。

12. **[R7-15] `HttpClient.request` の再試行コード重複を内部メソッドに抽出** — `_do_request()` ヘルパーへの抽出で保守性向上。

13. **[R7-19][R7-20][R7-21][R7-22][R7-23] 軽微なクリーンアップ** — `cli.py` の argparse プライベート属性参照の安全化、`auth.py` の `host` フィールド統一・重複エントリ対応、registry.py の対称性改善、detect.py の正規表現重複解消をまとめてPRにする。

---

## 修正記録（2026-03-09）

本ラウンド（review-08-code-quality.md）の推奨アクションに対して以下の修正を実施した。

| ID | 対応状況 | コミット概要 |
|----|----------|-------------|
| R7-01 | ✅ 修正済み（前回） | `paginate_link_header` の `url` → `next_url` 代入バグ修正 |
| R7-02 | ✅ 修正済み（前回） | `HttpClient.get_absolute()` 追加でプライベートAPI参照を解消 |
| R7-03 | ✅ 修正済み | `base.py` に `GitHubLikeAdapter` を追加。GitHub/Gitea の重複 `_to_*` 6メソッドを集約 |
| R7-04 | ✅ 修正済み | `DetectResult` を `frozen=True` に変更。`detect_service()` を `dataclasses.replace()` に更新 |
| R7-05 | ✅ 修正済み | `GogsAdapter` 全メソッドに親クラスと一致する型ヒントを追加 |
| R7-06 | ✅ 修正済み（前回） | `issue.py` の `"azure_devops"` → `"azure-devops"` タイポ修正 |
| R7-07 | ✅ 前回対応 | `get_absolute()` 導入で主な DRY 違反を解消 |
| R7-08 | ✅ 修正済み | `commands/__init__.py` に `get_adapter()` ヘルパーを追加し全ハンドラの定型2行を削減 |
| R7-09 | ✅ 修正済み | `config.py` に `build_clone_url()` を追加し `handle_clone` の 8 分岐を集約 |
| R7-10 | ✅ 修正済み | `detect.py` に `get_known_service_type()` 公開関数を追加。`repo.py` の `_KNOWN_HOSTS` 直接参照を解消 |
| R7-11 | ✅ 修正済み | `backlog.py` に `_STATUS_CLOSED_ID` 等の定数を追加し 9 箇所のマジックナンバーを置換 |
| R7-12 | ✅ 修正済み（前回） | GitLab `_to_issue` のデッドコード `if state == "closed": state = "closed"` を削除 |
| R7-13 | ✅ 修正済み（前回） | GitLab `_to_release` を `draft=False, prerelease=upcoming_release` に修正 |
| R7-14 | ✅ 修正済み | `AzureDevOpsAdapter._to_repository` を `@staticmethod` に変更し `project` を引数化 |
| R7-15 | ✅ 修正済み（前回） | `HttpClient.request` を retry ループ構造に統一し重複 try/except を解消 |
| R7-16 | ✅ 修正済み（前回） | GitHub/Gitea の `list_labels`/`list_milestones` に `paginate_link_header` を適用 |
| R7-17 | ✅ 修正済み | `stype`/`shost` → `saved_type`/`saved_host`（detect.py, config.py, registry.py）に変更 |
| R7-18 | ✅ 修正済み | `_build_default_api_url` → `build_default_api_url` にパブリック化。repo.py/init.py も追従 |
| R7-19 | ✅ 修正済み（前回） | `cli.py` を `subparser_map[args.command].print_help()` に変更し argparse 内部属性参照を解消 |
| R7-20 | ✅ 修正済み | `get_auth_status()` の env var エントリ host を `"env:service_type"` 形式に変更し重複排除 |
| R7-21 | ✅ 対応済み | `registry.py` の `create_adapter` に設計意図コメントを追記 |
| R7-22 | ✅ 修正済み | `_BACKLOG_PATH_RE`/`_GITBUCKET_PATH_RE` を `_GIT_PATH_RE` に統合 |
| R7-23 | ✅ 修正済み | R7-04 対応時に `hosts.get(result.host)` を使用するよう変更済み |

### 主な変更ファイル

- `src/gfo/adapter/base.py` — `GitHubLikeAdapter` 追加
- `src/gfo/adapter/github.py`, `gitea.py` — `GitHubLikeAdapter` を継承、重複 `_to_*` 削除
- `src/gfo/adapter/gogs.py` — 型ヒント追加
- `src/gfo/adapter/backlog.py` — ステータス ID 定数化
- `src/gfo/adapter/azure_devops.py` — `_to_repository` を `@staticmethod` に変更
- `src/gfo/adapter/registry.py` — `stype` → `service_type`、設計コメント追記
- `src/gfo/detect.py` — `DetectResult` frozen 化、`get_known_service_type()` 追加、正規表現統合、`saved_type`/`saved_host` 変数名変更
- `src/gfo/config.py` — `build_default_api_url`（パブリック化）、`build_clone_url()` 追加、`saved_type`/`saved_host` 変数名変更
- `src/gfo/auth.py` — `get_auth_status()` の env var エントリ形式統一・重複排除
- `src/gfo/commands/__init__.py` — `get_adapter()` ヘルパー追加
- `src/gfo/commands/pr.py`, `issue.py`, `label.py`, `milestone.py`, `release.py`, `repo.py`, `init.py` — `get_adapter()` 使用、プライベート関数参照の解消

---

## 次ラウンドへの申し送り

- **[R7-01] 修正後テスト追加**: `paginate_link_header` の修正後、`limit > per_page` のシナリオ（例: `limit=100`, `per_page=30`）で複数ページにわたる応答を正しく集約できることを確認する回帰テストを追加すること。`paginate_response_body` も同様のパターンがないか調査する。

- **[R7-06] テストカバレッジ**: Azure DevOps タイポバグ（R7-06）は既存テストで検出されなかった。`issue create` のサービス別分岐テストが不足している可能性があり、コマンドレイヤーのサービス別パラメータ渡しのテスト網羅率を確認することを推奨する。

- **型チェックの強化**: `GogsAdapter` の型ヒント欠如（R7-05）を契機に、mypy を CI に組み込み全アダプターに対してチェックを実施することを検討する。`detect.py` の `DetectResult.service_type` フィールドへの書き換えパターンは mypy の `--strict` モードで警告になる可能性がある。

- **`handle_clone` のURL構築（R7-09）**: `Repository.clone_url` フィールドは既に設計されているため、`list_repositories` や `get_repository` の結果から直接 `clone_url` を取得するアプローチも検討する（APIを呼び出してURLを取得してからクローンする方式）。ただしリポジトリ外（gitなし）からの操作を想定しているためトレードオフがある。

- **Backlog のカスタムステータス対応（R7-11 関連）**: Backlog のステータスIDはスペースによってカスタマイズ可能なため、`_resolve_merged_status_id()` のような動的解決を close/open にも適用すべきか検討する。

- **`detect.py` の循環依存**: `detect.py` ↔ `config.py` の循環依存を遅延インポートで回避しているが、技術的負債として残存している。将来的にはパッケージ構造の再設計（例: `core` / `infra` 層の分離）を検討することを推奨する。

- **`AzureDevOpsAdapter` の `merge_pull_request`**: PR データを取得してからマージするという2ステップ構成は、並行処理時の TOCTOU（Time of Check / Time of Use）問題を潜在的に含む。本番環境での使用前に検討が必要。

- **`probe_unknown_host` の副作用**: `detect.py` の `probe_unknown_host` は実際のネットワークリクエストを行う。テスト環境でのモック状況が適切かどうかを確認する必要がある。
