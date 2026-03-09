# gfo Review Report — Round 11: フォローアップ3（R9/R10 再確認 + 新規発見）

## 概要
- レビュー日: 2026-03-09
- 対象: R9/R10 未修正の継続確認 + 新規領域の精査
- コミット差分なし（R9/R10 の修正は未実施）
- 発見事項: 新規 5 件（中 3 件 / 軽微 2 件）

---

## R9/R10 未修正問題の継続確認

git log より前回レビュー以降のコミットがないため、R9/R10 の全問題は **引き続き未修正**。

| ID | ファイル | 問題概要 | 重大度 |
|----|---------|---------|--------|
| R9-01 | `bitbucket.py` | `GfoError` 未インポート | 🔴 |
| R9-02 | `commands/repo.py` L65 | f-string プレフィックス欠落 | 🟡 |
| R9-03 | `backlog.py` L100 | `ValueError` 未捕捉 | 🟡 |
| R9-04 | `http.py` L47 | SSL 証明書検証ハードコード | 🟡 |
| R9-05 | `config.py` L128 | `except Exception` 広範捕捉 | 🟡 |
| R9-06 | `output.py` L91 | 単一要素でオブジェクト返却 | 🟡 |
| R9-07 | `detect.py` L15 | `_mask_credentials` 正規表現不完全 | 🟡 |
| R10-01 | `detect.py` L16 | import が関数定義の後（PEP 8 違反） | 🔴 |
| R10-02 | `commands/init.py` L138 | `except Exception` 広範捕捉 | 🟡 |
| R10-03 | `http.py` L103, L149 | 到達不可能な `return resp` | 🟢 |

---

## 新規発見事項

---

### [R11-01] 🟡 `_mask_credentials` が `git_util.py` と `detect.py` の 2 箇所に重複定義

- **ファイル**: `src/gfo/git_util.py` L14-16、`src/gfo/detect.py` L13-15
- **説明**: 認証情報をマスクする `_mask_credentials` 関数が 2 モジュールに独立して定義されており、どちらも全く同一の（不完全な）正規表現を使用している。
  ```python
  # git_util.py L14-16
  def _mask_credentials(text: str) -> str:
      """URL 内の認証情報（`://user:pass@` 形式）をマスクする。"""
      return re.sub(r"://[^@\s]+@", "://***@", text)

  # detect.py L13-15（完全に同一）
  def _mask_credentials(text: str) -> str:
      """URL 内の認証情報（`://user:pass@` 形式）をマスクする。"""
      return re.sub(r"://[^@\s]+@", "://***@", text)
  ```
  これは R9-07 で指摘した正規表現の不完全さ（`@` を含むパスワードで不完全マスク）が **2 箇所に同時に存在する** ことを意味する。一方を修正しても他方が残る。
- **影響**: DRY 違反。正規表現の改善（R9-07 対応）を片方だけに適用しても、もう一方のモジュールを使うコードパスでは旧来の不完全なマスクが続く。`git_util.py` は `git clone` エラー時に使用され、`detect.py` は URL 検出エラー時に使用されるため、両方のパスで同じ問題が再現する。
- **推奨修正**: どちらか一方（`git_util.py` が依存関係として適切）にまとめるか、`gfo.exceptions` や新たな `gfo.util` モジュールに移動して両者からインポートする。
  ```python
  # gfo/util.py (新規)
  def mask_credentials(text: str) -> str:
      return re.sub(r"://[^\s:/]*(?::[^\s/@]+)?@", "://***@", text)
  ```
- **テスト**: `mask_credentials` の単体テストを作成し、`@` を含むパスワード、トークン形式 URL、通常の `user:pass@` 形式をすべてカバーする。

---

### [R11-02] 🟡 `http.py` の `get_absolute` がリトライループを `request()` と重複実装

- **ファイル**: `src/gfo/http.py` L125-149 vs L60-103
- **説明**: `get_absolute()` メソッドはページネーション用の絶対 URL GET として R7-02 対応時に追加されたが、`request()` と全く同一のリトライループ構造を持つ。
  ```python
  # request() L78-103 と get_absolute() L132-149 の骨格が同一
  for attempt in range(self._max_retries + 1):
      try:
          resp = self._session.request(...)  # or self._session.get(...)
      except requests.ConnectionError as e:
          raise gfo.exceptions.NetworkError(self._mask_api_key(str(e))) from e
      except requests.Timeout as e:
          raise gfo.exceptions.NetworkError(self._mask_api_key(str(e))) from e

      try:
          self._handle_response(resp)
          return resp
      except gfo.exceptions.RateLimitError:
          if attempt >= self._max_retries:
              raise
          wait = self._parse_retry_after(resp.headers.get("Retry-After"))
          time.sleep(wait)

  return resp  # unreachable
  ```
  `request()` と `get_absolute()` の差分は `self._session.request(method, url, ...)` か `self._session.get(url, ...)` かだけで、エラーハンドリング・リトライ・マスク処理が完全に重複している。
- **影響**: リトライ動作（最大待機時間の変更、新しい例外ハンドリング、ログ追加など）を変更する場合に 2 箇所を同時に修正する必要がある。R10-03 の「到達不可能な `return resp`」も両方に存在する。
- **推奨修正**: リトライループを内部ヘルパー `_execute_with_retry(callable, *, mask_url)` に抽出し、`request()` と `get_absolute()` の両方から呼び出す。
  ```python
  def _execute_with_retry(self, send_fn, *, label: str = "") -> requests.Response:
      for attempt in range(self._max_retries + 1):
          try:
              resp = send_fn()
          except requests.ConnectionError as e:
              raise gfo.exceptions.NetworkError(self._mask_api_key(str(e))) from e
          except requests.Timeout as e:
              raise gfo.exceptions.NetworkError(self._mask_api_key(str(e))) from e
          try:
              self._handle_response(resp)
              return resp
          except gfo.exceptions.RateLimitError:
              if attempt >= self._max_retries:
                  raise
              time.sleep(self._parse_retry_after(resp.headers.get("Retry-After")))
      raise AssertionError("unreachable")
  ```
- **テスト**: `get_absolute()` のリトライ動作テスト（現在欠如している可能性）。`request()` と同様のリトライシナリオをカバーする。

---

### [R11-03] 🟡 `commands/pr.py` の `handle_checkout` でローカルブランチ既存時のエラー未処理

- **ファイル**: `src/gfo/commands/pr.py` L57-63
- **説明**: `handle_checkout` は以下の流れで動作する。
  1. `adapter.get_pull_request(args.number)` で PR 情報取得
  2. `gfo.git_util.git_fetch("origin", refspec)` でフェッチ
  3. `gfo.git_util.git_checkout_new_branch(pr.source_branch)` でブランチ作成・チェックアウト

  `git_checkout_new_branch` は内部で `git checkout -b <branch> FETCH_HEAD` を実行するが、`<branch>` がローカルに既存の場合は `fatal: A branch named '<branch>' already exists.` というエラーで `GitCommandError` が発生する。`handle_checkout` にこのケースの処理はなく、エラーメッセージがそのままユーザーに表示される。
  ```python
  def handle_checkout(args: argparse.Namespace, *, fmt: str) -> None:
      adapter = get_adapter()
      pr = adapter.get_pull_request(args.number)
      refspec = adapter.get_pr_checkout_refspec(args.number, pr=pr)
      gfo.git_util.git_fetch("origin", refspec)
      gfo.git_util.git_checkout_new_branch(pr.source_branch)  # ← 既存ブランチで失敗
  ```
  同一 PR を 2 回 checkout しようとしたり、同名のローカルブランチを持つ場合に再現する。
- **影響**: 「ブランチが既に存在します」という git の生のエラーメッセージがユーザーに表示され、次に何をすればよいかのガイダンスがない。`gh pr checkout` など競合ツールはブランチが存在する場合に `git checkout <branch>` に切り替える動作をする。
- **推奨修正**: `git checkout -b` が失敗した場合に `git checkout <branch>` を試みるフォールバックを追加する。または `git_util.git_checkout_new_branch` のドキュメントで「ブランチが既に存在する場合は呼び出し元でハンドリングすること」と明記する。
  ```python
  try:
      gfo.git_util.git_checkout_new_branch(pr.source_branch)
  except GitCommandError as e:
      if "already exists" in str(e):
          gfo.git_util.run_git("checkout", pr.source_branch)
      else:
          raise
  ```
- **テスト**: ブランチ既存時の `handle_checkout` が graceful に動作することを確認するテスト。

---

### [R11-04] 🟢 `commands/issue.py` の `handle_create` が `get_adapter()` ヘルパーの設計上の限界を露呈

- **ファイル**: `src/gfo/commands/issue.py` L7-9, L26-31
- **説明**: `handle_create` は `config.service_type` の値に基づいてサービス固有の `kwargs` を組み立てるため、`config` オブジェクトへの参照が必要。しかし `get_adapter()` ヘルパーは adapter インスタンスのみを返し、`config` を捨てている。そのため `handle_create` だけは `get_adapter()` を使えず、`resolve_project_config()` + `create_adapter(config)` の 2 ステップを直接呼んでいる。
  ```python
  # handle_list / handle_view / handle_close → get_adapter() を使用
  def handle_list(args, *, fmt):
      adapter = get_adapter()       # ← ヘルパー使用
      ...

  # handle_create だけ直接呼び出し
  def handle_create(args, *, fmt):
      config = resolve_project_config()   # ← 直接呼び出し
      adapter = create_adapter(config)    # ← 直接呼び出し
      ...
  ```
  また `from gfo.adapter.registry import create_adapter` と `from gfo.config import resolve_project_config` が同ファイルに import されているが、これらは `handle_create` にしか使われていない。
- **影響**: 将来的に他のコマンドでも `config.service_type` を参照する必要が出た場合、同様のパターンが増殖する。`get_adapter()` が `(adapter, config)` のタプルを返すか、`get_adapter_with_config()` のような派生ヘルパーを提供するかの設計を検討するきっかけになる。
- **推奨修正**: `commands/__init__.py` に `get_adapter_and_config()` を追加し、adapter と config の両方を返す。
  ```python
  def get_adapter_and_config() -> tuple[GitServiceAdapter, ProjectConfig]:
      config = resolve_project_config()
      return create_adapter(config), config
  ```
  `handle_create` はこれを使用することで import の削減とパターンの統一が可能。

---

### [R11-05] 🟢 `config.py` の `ProjectConfig` が `frozen=True` でない（他のデータクラスと設計不一致）

- **ファイル**: `src/gfo/config.py` L14-24
- **説明**: `ProjectConfig` は `@dataclass` で定義されているが、`base.py` のすべてのデータクラス（`PullRequest`, `Issue`, `Repository`, `Release`, `Label`, `Milestone`）が `@dataclass(frozen=True, slots=True)` を使用しているのに対して、`ProjectConfig` は `frozen=True` も `slots=True` も指定されていない。
  ```python
  # config.py
  @dataclass                        # ← frozen=True なし
  class ProjectConfig:
      service_type: str
      host: str
      ...

  # base.py（他のデータクラス）
  @dataclass(frozen=True, slots=True)
  class PullRequest:
      ...
  ```
  `ProjectConfig` は生成後に変更される想定はなく、`save_project_config()` も引数として受け取るだけで内部フィールドを変更しない。
- **影響**: `ProjectConfig` が意図せず変更されてもエラーにならない（デバッグが困難）。ハッシュ化・辞書キーとして使えない。コードの読者が「なぜここだけ mutable なのか」を理解するコストが生じる。
- **推奨修正**: `@dataclass(frozen=True)` に変更する（`slots=True` はフィールドに `| None = None` があるため Python 3.10 以前では問題が生じる可能性があるため慎重に検討）。または `frozen=True` にできない設計上の理由をコメントで明記する。

---

## 全問題サマリーテーブル（R9〜R11 未修正 + 新規）

| ID | 重大度 | ファイル | 概要 |
|----|--------|---------|------|
| R9-01 | 🔴 重大 | `bitbucket.py` | `GfoError` 未インポート |
| R10-01 | 🔴 重大 | `detect.py` L16 | import が関数定義の後 |
| R9-02 | 🟡 中 | `commands/repo.py` L65 | f-string 欠落 |
| R9-03 | 🟡 中 | `backlog.py` L100 | `ValueError` 未捕捉 |
| R9-04 | 🟡 中 | `http.py` L47 | SSL 証明書検証ハードコード |
| R9-05 | 🟡 中 | `config.py` L128 | `except Exception` 広範捕捉 |
| R9-06 | 🟡 中 | `output.py` L91 | 単一要素でオブジェクト返却 |
| R9-07 | 🟡 中 | `detect.py` L15 | `_mask_credentials` 正規表現不完全 |
| R10-02 | 🟡 中 | `commands/init.py` L138 | `except Exception` 広範捕捉 |
| **R11-01** | 🟡 中 | `git_util.py` L14, `detect.py` L13 | `_mask_credentials` 重複定義（不完全な同一正規表現） |
| **R11-02** | 🟡 中 | `http.py` L60-103, L125-149 | `get_absolute` と `request` でリトライループ重複 |
| **R11-03** | 🟡 中 | `commands/pr.py` L63 | `handle_checkout` でブランチ既存時のエラー未処理 |
| R10-03 | 🟢 軽微 | `http.py` L103, L149 | 到達不可能な `return resp` が 2 箇所 |
| **R11-04** | 🟢 軽微 | `commands/issue.py` L26-31 | `handle_create` だけ `get_adapter()` を使えない設計の限界 |
| **R11-05** | 🟢 軽微 | `config.py` L14 | `ProjectConfig` が `frozen=True` でない（他との設計不一致） |

---

## 推奨アクション（優先度順）

1. **[R9-01] `bitbucket.py`**: `from gfo.exceptions import GfoError, NotSupportedError` — 1 行追加。最優先。

2. **[R10-01] `detect.py` import 順序修正** — `from gfo.git_util import ...` を L10 付近の import ブロックに移動。isort で自動修正可能。

3. **[R9-07][R11-01] `_mask_credentials` の統合と正規表現改善** — `git_util.py` と `detect.py` の重複を解消し、改善した正規表現（`r"://[^\s:/]*(?::[^\s/@]+)?@"`）を 1 か所に集約。2 件を同時対応。

4. **[R9-02] `repo.py` L65** — f-string プレフィックス追加。1 文字の修正。

5. **[R9-03] `backlog.py` L110** — `except (KeyError, TypeError, ValueError)` に変更。

6. **[R9-05][R10-02] `config.py` L128 + `init.py` L138** — `except Exception` を限定例外に統一。1 PR でまとめて対応。

7. **[R11-02] `http.py` リトライループ共通化** — `_execute_with_retry` ヘルパーを追加し、`request` と `get_absolute` の重複を解消。R10-03 の `return resp  # unreachable` も同時に削除。

8. **[R11-03] `pr.py` `handle_checkout` のブランチ既存対応** — `GitCommandError` の "already exists" ケースで `git checkout <branch>` にフォールバック。

9. **[R11-04] `commands/__init__.py` に `get_adapter_and_config()` 追加** — `issue.py` の `handle_create` を統一パターンに近づける。

10. **[R9-04] SSL 証明書検証オプション** — `GFO_INSECURE=1` 環境変数対応。企業内環境サポート。

11. **[R9-06] `format_json` を常に配列返却** — スクリプト利用の一貫性確保。

12. **[R11-05] `ProjectConfig` の設計明確化** — `frozen=True` 対応または設計理由のコメント追記。

---

## 次ラウンドへの申し送り

- **修正の集中実施を推奨**: 現時点で R9/R10/R11 を合わせて未修正問題が 15 件蓄積している。コードベースが安定しているため、次のラウンドでは発見より修正に重点を置くことを推奨する。
- **CI 強化**: mypy + isort + flake8 を CI に追加することで、R9-01（import 欠落）・R10-01（import 順序）のようなミスを自動検出できる。これが最もコスパの高い品質向上策。
- **`_mask_credentials` 修正の影響範囲**: R11-01 の統合に合わせて、R9-07 の正規表現改善を同時実施することで、両 module の全コードパスで正しいマスクが適用される。
