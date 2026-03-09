# gfo Review Report — Round 16: http.py / config.py / auth / commands 品質

## 概要
- レビュー日: 2026-03-09
- 対象: `http.py`, `config.py`, `auth.py`, `auth_cmd.py`, `adapter/base.py`, `commands/issue.py`, `commands/__init__.py`, `backlog.py`, `test_http.py`, `test_config.py`
- 発見事項: 新規 7 件（高 2 / 中 3 / 軽微 2）、既知課題 5 件の現状確認

---

## 既知課題の現状確認

| ID | 現在の実装 | 状態 |
|----|-----------|------|
| R11-02 | `http.py` `request()` / `get_absolute()` のリトライループが同一コード重複 | **未修正** |
| R11-05 | `config.py` L14 `@dataclass` のみ（`frozen=True` なし） | **未修正** |
| R12-06 | `backlog.py` L254-258 `items[:limit]` のみ（ページネーション不使用） | **未修正** |
| R15-01 | `commands/issue.py` `handle_create` が `resolve_project_config()` + `create_adapter()` を直接呼び出し | **未修正** |
| R15-03 | `http.py` `_parse_retry_after()` が RFC 7231 日時形式で `default=60` を返す | **未修正** |

---

## 新規発見事項

---

### [R16-01] 🔴 `config.py` L14 — `ProjectConfig` が `frozen=True` でない（R11-05 詳細確認）

- **ファイル**: `src/gfo/config.py` L14
- **説明**: `ProjectConfig` は設定解決の成果物であり不変であるべきだが、`@dataclass` のみで `frozen=True` がない。`adapter/base.py` の全データクラス（`PullRequest`, `Issue`, `Repository` 等）は `@dataclass(frozen=True, slots=True)` で統一されており、`ProjectConfig` のみが例外。
  ```python
  @dataclass          # ← frozen=True, slots=True がない
  class ProjectConfig:
      service_type: str
      host: str
      api_url: str
      ...
  ```
- **影響**: 設定オブジェクトが意図せず変更される可能性。コードベース内でのデータクラス設計が不統一。
- **推奨修正**: `@dataclass(frozen=True)` に変更。`slots=True` は Python 3.10+ 対応なら追加可能。
  ```python
  @dataclass(frozen=True)
  class ProjectConfig:
  ```

---

### [R16-02] 🟡 `auth.py` L117-146 — `get_auth_status()` の host 形式が credentials.toml と環境変数で混在

- **ファイル**: `src/gfo/auth.py` L117-146
- **説明**: `gfo auth status` の出力で、credentials.toml 由来のエントリは `host: "github.com"` 形式、環境変数由来は `host: "env:github"` 形式となり、列挙型が混在する。
  ```
  HOST              STATUS       SOURCE
  github.com        configured   credentials.toml
  env:gitlab        configured   env:GITLAB_TOKEN   ← 形式が異なる
  ```
- **影響**: スクリプトで `gfo auth status --format json` を解析する場合、host フィールドの形式が一定でなく処理が複雑になる。
- **推奨修正**: 環境変数エントリも `host` に実ホスト名または `(all {service} hosts)` を設定し、`source` フィールドで区別する。

---

### [R16-03] 🟡 `commands/issue.py` L26-47 — `handle_create` のみ `get_adapter()` を使わず直接解決（R15-01 詳細）

- **ファイル**: `src/gfo/commands/issue.py` L26-47
- **現在のコード**:
  ```python
  def handle_create(args, *, fmt):
      config = resolve_project_config()  # ← 直接呼び出し
      adapter = create_adapter(config)   # ← 直接呼び出し
      if config.service_type == "azure-devops":
          kwargs["work_item_type"] = args.type
  ```
- **他のハンドラ**: `handle_list`, `handle_view`, `handle_close` はすべて `get_adapter()` を使用。
- **理由**: `handle_create` は `config.service_type` を直接参照するため `get_adapter()` では `config` にアクセスできない。
- **推奨修正**: `get_adapter_with_config()` ヘルパーを `commands/__init__.py` に追加するか、`config.service_type` の参照を別の方法で取得する。
  ```python
  # commands/__init__.py に追加
  def get_adapter_with_config() -> tuple[GitServiceAdapter, ProjectConfig]:
      config = resolve_project_config()
      return create_adapter(config), config
  ```

---

### [R16-04] 🟡 `http.py` L169-182 — Retry-After RFC 7231 日時形式を無視（R15-03 詳細）

- **ファイル**: `src/gfo/http.py` L169-182
- **現在のコード**:
  ```python
  try:
      result = int(value)
  except ValueError:
      return default  # ← 日時形式は常に 60 秒で処理
  ```
- **影響**: `Retry-After: Mon, 09 Mar 2026 15:30:00 GMT` 形式のレスポンスに対して 60 秒固定待機。実際の残り時間が 5 秒なら 55 秒余分に待つ。
- **推奨修正**:
  ```python
  import email.utils
  from datetime import datetime, timezone

  @staticmethod
  def _parse_retry_after(value: str | None, default: int = 60) -> int:
      if value is None:
          return default
      try:
          return max(1, min(int(value), _MAX_RETRY_AFTER))
      except ValueError:
          pass
      try:
          dt = email.utils.parsedate_to_datetime(value)
          diff = int((dt - datetime.now(timezone.utc)).total_seconds())
          return max(1, min(diff, _MAX_RETRY_AFTER))
      except Exception:
          return default
  ```

---

### [R16-05] 🟡 `http.py` — `request()` と `get_absolute()` のリトライループ重複（R11-02 詳細）

- **ファイル**: `src/gfo/http.py` L80-101, L132-147
- **説明**: 両メソッドのリトライロジックは `resp_fn` の呼び方のみが異なり、残りのコードは完全に同一。
- **推奨修正**:
  ```python
  def _retry_loop(self, resp_fn: Callable[[], requests.Response]) -> requests.Response:
      for attempt in range(self._max_retries + 1):
          try:
              resp = resp_fn()
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
      raise AssertionError("unreachable")

  def request(self, method, path, *, params=None, json=None, data=None,
               headers=None, timeout=30):
      url = self._base_url + path
      merged_params = {**self._default_params, **self._auth_params, **(params or {})}
      return self._retry_loop(lambda: self._session.request(
          method, url, params=merged_params, json=json, data=data,
          headers=headers, timeout=timeout,
      ))
  ```

---

### [R16-06] 🟢 `test_http.py` — `_parse_retry_after()` の RFC 日時形式テストが欠落

- **ファイル**: `tests/test_http.py`
- **説明**: Retry-After の秒数形式テストはあるが、RFC 7231 日時形式（`Mon, 09 Mar 2026 15:30:00 GMT`）のテストがない。R16-04 の修正後に追加すべき。

---

### [R16-07] 🟢 `http.py` `paginate_*` 関数 — `limit=0` が「無制限」を意味するが不明瞭

- **ファイル**: `src/gfo/http.py` 各 `paginate_*` 関数のシグネチャ
- **説明**: `limit=0` が無制限を意味するが、デフォルト値が `limit=30` のため意図が混乱しやすい。テストには `test_limit_zero_unlimited` がある。
- **影響**: 軽微。ドキュメントに明記されており実害なし。

---

## 全問題サマリーテーブル（R16 現在の未修正・新規）

| ID | 重大度 | ファイル | 概要 |
|----|--------|---------|------|
| **R16-01/R11-05** | 🔴 高 | `config.py` L14 | `ProjectConfig` が `frozen=True` でない |
| **R16-02** | 🟡 中 | `auth.py` L117 | `get_auth_status()` の host 形式が混在 |
| **R16-03/R15-01** | 🟡 中 | `commands/issue.py` L26 | `handle_create` のみ `get_adapter()` 未使用 |
| **R16-04/R15-03** | 🟡 中 | `http.py` L169 | Retry-After RFC 日時形式を 60 秒固定で処理 |
| **R16-05/R11-02** | 🟡 中 | `http.py` L80, L132 | リトライループ重複 |
| R12-06 | 🟢 軽微 | `backlog.py` L254 | `list_repositories` ページネーション不使用 |
| **R16-06** | 🟢 軽微 | `test_http.py` | RFC 日時形式テスト欠落 |
| **R16-07** | 🟢 軽微 | `http.py` paginate_* | `limit=0` の意味が不明瞭 |

---

## 推奨アクション（優先度順）

### 即時対応（1〜3行で修正可能）

1. **[R16-01/R11-05]** `config.py` L14 — `@dataclass` → `@dataclass(frozen=True)` に変更

### 設計変更が必要なもの

2. **[R16-03/R15-01]** `commands/__init__.py` に `get_adapter_with_config()` を追加し、`issue.py` の `handle_create` を統一
3. **[R16-05/R11-02]** `http.py` — `_retry_loop()` プライベートメソッドに共通化
4. **[R16-04/R15-03]** `http.py` — `_parse_retry_after()` に RFC 7231 日時形式パースを追加

---

## 次ラウンドへの申し送り

- R16-01 は 1 行修正で対応可能。config.py の `ProjectConfig` を使用している箇所（`save_project_config`, `commands/*`）が `config.service_type = "xxx"` のような再代入を行っていないか確認してから適用する。
- R16-05 のリトライループ統合は `Callable` の型注釈に注意（`from collections.abc import Callable` or `typing.Callable`）。
