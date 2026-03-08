# gfo 詳細設計書

## 1. モジュール間依存関係図

```
                        ┌──────────┐
                        │ cli.py   │
                        └────┬─────┘
                             │ argparse → dispatch
              ┌──────────────┼──────────────────────┐
              ▼              ▼                       ▼
        ┌──────────┐  ┌──────────┐          ┌──────────────┐
        │commands/ │  │commands/ │   ...    │commands/     │
        │  pr.py   │  │ issue.py │          │  auth_cmd.py │
        └────┬─────┘  └────┬─────┘          └──────┬───────┘
             │              │                       │
             ▼              ▼                       ▼
      ┌─────────────┐  ┌─────────┐          ┌──────────┐
      │adapter/     │  │output.py│          │ auth.py  │
      │ registry.py │  └─────────┘          └────┬─────┘
      └──────┬──────┘                            │
             │ resolve                           │
             ▼                                   ▼
      ┌─────────────┐                    ┌──────────────┐
      │adapter/     │                    │ config.py    │
      │ base.py     │                    └──────┬───────┘
      │ (ABC+DC)    │                           │
      └──────┬──────┘                           ▼
             │ 継承                      ┌──────────────┐
    ┌────────┼────────────┐              │ detect.py    │
    ▼        ▼            ▼              └──────┬───────┘
 github.py  gitlab.py  ...                      │
    │                                           ▼
    │                                    ┌──────────────┐
    └───────────────────────────────────▶│ http.py      │
                                         └──────┬───────┘
                                                │
                                                ▼
                                         ┌──────────────┐
                                         │ git_util.py  │
                                         └──────────────┘
                                                │
                                                ▼
                                          subprocess(git)
```

**依存関係サマリー**:

| モジュール | 依存先 |
|-----------|--------|
| `cli.py` | `commands/*`, `config.py`, `output.py` |
| `commands/*.py` | `adapter/registry.py`, `config.py`, `auth.py`, `output.py`, `git_util.py` |
| `adapter/*.py`（各実装） | `adapter/base.py`, `http.py` |
| `adapter/registry.py` | `adapter/*.py`（各実装クラス） |
| `config.py` | `detect.py`, `git_util.py` |
| `detect.py` | `git_util.py`, `http.py`（API プローブ時） |
| `auth.py` | `config.py` |
| `http.py` | `auth.py` |
| `output.py` | `adapter/base.py`（データクラス参照） |
| `git_util.py` | （外部依存なし、subprocess のみ） |

---

## 2. 各モジュール詳細設計

### 2.1 git_util.py

#### 責務
`git` コマンドの subprocess 呼び出しをラップし、他モジュールが直接 subprocess を扱わなくて済むようにする。

#### 公開関数

```python
def run_git(*args: str, cwd: str | None = None) -> str:
    """git コマンドを実行し、stdout を stripped で返す。
    
    失敗時は GitCommandError を送出。
    内部実装: subprocess.run(
        ["git", *args],
        capture_output=True, text=True, check=False, cwd=cwd
    )
    returncode != 0 の場合 GitCommandError(stderr)。
    """

def get_remote_url(remote: str = "origin", cwd: str | None = None) -> str:
    """git remote get-url {remote} の結果を返す。
    
    remote が存在しない場合は GitCommandError。
    """

def get_current_branch(cwd: str | None = None) -> str:
    """git symbolic-ref --short HEAD の結果を返す。
    
    detached HEAD の場合は GitCommandError。
    """

def get_last_commit_subject(cwd: str | None = None) -> str:
    """git log -1 --format=%s の結果を返す。"""

def get_default_branch(remote: str = "origin", cwd: str | None = None) -> str:
    """git symbolic-ref refs/remotes/{remote}/HEAD の結果から
    refs/remotes/{remote}/ を除去して返す。
    
    取得できない場合は "main" をフォールバックとして返す。
    """

def git_config_get(key: str, cwd: str | None = None) -> str | None:
    """git config --local {key} の結果を返す。未設定なら None。
    
    内部: returncode != 0 は None 扱い（エラーではない）。
    """

def git_config_set(key: str, value: str, cwd: str | None = None) -> None:
    """git config --local {key} {value} を実行。"""

def git_fetch(remote: str, refspec: str, cwd: str | None = None) -> None:
    """git fetch {remote} {refspec} を実行。"""

def git_checkout_new_branch(branch: str, start: str = "FETCH_HEAD",
                            cwd: str | None = None) -> None:
    """git checkout -b {branch} {start} を実行。"""

def git_clone(url: str, dest: str | None = None, cwd: str | None = None) -> None:
    """git clone {url} [{dest}] を実行。"""
```

#### subprocess 呼び出し方針
- 全呼び出しで `capture_output=True, text=True, check=False` を使用
- `encoding` は指定しない（`text=True` のデフォルトに任せる）
- `shell=False`（リスト形式呼び出し）を厳守
- タイムアウトは `timeout=30` を設定（フリーズ防止）

#### エラー処理
- `run_git` 内で `returncode != 0` を検知した場合 `GitCommandError(stderr.strip())` を送出
- `git_config_get` のみ例外的に `returncode != 0` を `None` 返却とする（未設定は正常系）

---

### 2.2 detect.py

#### 責務
git remote URL からサービス種別・ホスト名・owner/repo 情報を検出する。

#### 公開関数

```python
@dataclass
class DetectResult:
    """検出結果。"""
    service_type: str       # "github", "gitlab", "bitbucket", "azure-devops",
                            # "gitea", "forgejo", "gogs", "gitbucket", "backlog"
    host: str               # "github.com", "gitlab.example.com" 等
    owner: str              # owner / workspace / org
    repo: str               # リポジトリ名
    api_url: str | None     # 自動構築した API Base URL（プローブ経由は確定値）
    organization: str | None  # Azure DevOps 用
    project: str | None       # Azure DevOps / Backlog 用（project-key）


def detect_from_url(remote_url: str) -> DetectResult:
    """remote URL をパースし、ホスト・owner・repo を抽出する。
    
    サービス種別は既知ホストテーブルおよび特殊パターンで判定。
    未知ホストの場合は service_type を None としたまま返す（後段でプローブ）。
    """

def probe_unknown_host(host: str, scheme: str = "https") -> str | None:
    """未知ホストに対して API プローブを実行し、サービス種別を返す。
    
    試行順序:
    1. GET {scheme}://{host}/api/v1/version → Gitea/Forgejo/Gogs
       - レスポンス JSON に "forgejo" キーがあれば "forgejo"
       - "go-version" または "go_version" キーがあれば "gitea"（Gogs にはこのフィールドがない）
       - "version" のみで Gitea 固有フィールドがなければ "gogs" と判定
    2. GET {scheme}://{host}/api/v4/version → "gitlab"
    3. GET {scheme}://{host}/api/v3/ → "gitbucket"
    
    全プローブ失敗: None を返す。
    各リクエストは timeout=5 で実行（通常の 30 より短い）。
    """

def detect_service(cwd: str | None = None) -> DetectResult:
    """完全な検出フローを実行する。
    
    1. git_config_get("gfo.type") → 設定済みならそれを使用
    2. config.toml の hosts セクションを参照
    3. remote URL パース → 既知ホスト/特殊パターン判定
    4. 未知ホストなら probe_unknown_host()
    5. すべて失敗なら DetectionError
    """
```

#### URL パース正規表現

```python
# HTTPS パターン
_HTTPS_RE = re.compile(
    r"^https?://(?P<host>[^/:]+)(?::(?P<port>\d+))?/(?P<path>.+?)(?:\.git)?/?$"
)

# SSH パターン: git@host:path 形式
_SSH_SCP_RE = re.compile(
    r"^(?:\w+@)?(?P<host>[^:]+):(?P<path>.+?)(?:\.git)?/?$"
)

# SSH パターン: ssh://git@host[:port]/path 形式
_SSH_URL_RE = re.compile(
    r"^ssh://(?:\w+@)?(?P<host>[^/:]+)(?::(?P<port>\d+))?/(?P<path>.+?)(?:\.git)?/?$"
)
```

#### パスパーサー（host 確定後のパス部分を解析）

```python
# Azure DevOps: {org}/{project}/_git/{repo}
_AZURE_PATH_RE = re.compile(
    r"^(?:v3/)?(?P<org>[^/]+)/(?P<project>[^/]+)/(?:_git/)?(?P<repo>[^/]+)$"
)

# Backlog: git/{PROJECT}/{repo}
_BACKLOG_PATH_RE = re.compile(
    r"^git/(?P<project>[^/]+)/(?P<repo>[^/]+)$"
)

# GitBucket: git/{owner}/{repo}
_GITBUCKET_PATH_RE = re.compile(
    r"^git/(?P<owner>[^/]+)/(?P<repo>[^/]+)$"
)

# 汎用: {owner}/{repo} または {group}/{sub1}/{sub2}/.../project（GitLab サブグループ対応）
_GENERIC_PATH_RE = re.compile(
    r"^(?P<owner>.+)/(?P<repo>[^/]+)$"
)
```

#### 検出フロー詳細

```
remote URL
  │
  ├─ _HTTPS_RE でパース → host, path 取得
  ├─ _SSH_SCP_RE でパース → host, path 取得
  └─ _SSH_URL_RE でパース → host, path 取得
  │
  ▼
host を既知ホストテーブルで検索
  ├─ "github.com"     → service_type="github",    path を _GENERIC_PATH_RE でパース
  ├─ "gitlab.com"     → service_type="gitlab",    path を _GENERIC_PATH_RE でパース
  ├─ "bitbucket.org"  → service_type="bitbucket",  path を _GENERIC_PATH_RE でパース
  ├─ "dev.azure.com"  → service_type="azure-devops", path を _AZURE_PATH_RE でパース
  ├─ "codeberg.org"   → service_type="forgejo",   path を _GENERIC_PATH_RE でパース
  │
  ├─ *.backlog.com / *.backlog.jp     → service_type="backlog",  path.lstrip("/") を _BACKLOG_PATH_RE でパース
  ├─ *.visualstudio.com               → service_type="azure-devops"
  ├─ SSH: ssh.dev.azure.com           → service_type="azure-devops", path を _AZURE_PATH_RE でパース
  │
  └─ 未知ホスト → probe_unknown_host(host) でサービス種別を判定
       ├─ path が "git/..." で始まる → _GITBUCKET_PATH_RE を優先的に試行
       └─ その他 → _GENERIC_PATH_RE でパース
```

#### Backlog SSH の特殊処理

Backlog SSH URL は `{space}@{space}.git.backlog.com:/{PROJECT}/{repo}.git` 形式。
- ユーザー名部分（`{space}`）がホストのスペース ID になる
- host は `{space}.git.backlog.com` → `{space}.backlog.com` に正規化して使用
- `_SSH_SCP_RE` でマッチ後、path が `/{PROJECT}/{repo}` と先頭 `/` 付きになるため、
  `detect_from_url` 内で `path = path.lstrip("/")` を実行してから `_BACKLOG_PATH_RE` に渡す

---

### 2.3 config.py

#### 責務
3 層設定の解決ロジック。git config、TOML ユーザー設定、detect.py を統合する。

#### 公開関数・クラス

```python
@dataclass
class ProjectConfig:
    """解決済みプロジェクト設定。"""
    service_type: str
    host: str
    api_url: str
    owner: str
    repo: str
    organization: str | None = None  # Azure DevOps
    project_key: str | None = None   # Backlog / Azure DevOps


def get_config_dir() -> Path:
    """プラットフォーム別の設定ディレクトリパスを返す。
    
    Windows: Path(os.environ["APPDATA"]) / "gfo"
    Other:   Path.home() / ".config" / "gfo"
    
    ディレクトリが存在しない場合は作成しない（呼び出し元で必要時に作成）。
    """

def get_config_path() -> Path:
    """config.toml のフルパスを返す。"""
    return get_config_dir() / "config.toml"

def get_credentials_path() -> Path:
    """credentials.toml のフルパスを返す。"""
    return get_config_dir() / "credentials.toml"

def load_user_config() -> dict:
    """config.toml を読み込み dict で返す。
    
    ファイルが存在しない場合は空 dict を返す。
    内部: tomllib.load() を使用。
    """

def get_default_output_format() -> str:
    """config.toml の defaults.output を返す。未設定なら "table"。"""

def get_default_host() -> str | None:
    """config.toml の defaults.host を返す。未設定なら None。"""

def get_host_config(host: str) -> dict | None:
    """config.toml の hosts.{host} セクションを返す。未設定なら None。"""

def resolve_project_config(cwd: str | None = None) -> ProjectConfig:
    """3 層の設定解決を実行し、ProjectConfig を返す。

    解決フロー:
    1. git_config_get("gfo.type") で service_type を取得
    2. git_config_get("gfo.host") で host を取得
    3. いずれも未設定なら detect_service() で自動検出
    4. api_url の解決:
       a. git_config_get("gfo.api-url")
       b. config.toml の hosts.{host}.api_url
       c. サービス種別のデフォルト URL を構築（_build_default_api_url）
    5. owner/repo は detect_from_url() の結果を使用
    6. organization / project_key は git config から取得

    いずれかの必須フィールドが解決できない場合は ConfigError。
    """

def save_project_config(config: ProjectConfig, cwd: str | None = None) -> None:
    """ProjectConfig を git config --local に保存する。
    
    git_config_set("gfo.type", ...)
    git_config_set("gfo.host", ...)
    git_config_set("gfo.api-url", ...)
    organization があれば git_config_set("gfo.organization", ...)
    project_key があれば git_config_set("gfo.project-key", ...)
    """

def _build_default_api_url(service_type: str, host: str,
                           organization: str | None = None,
                           project: str | None = None) -> str:
    """サービス種別とホスト名からデフォルト API Base URL を構築する。

    "github"       → "https://api.github.com"（github.com の場合）
                   → "https://{host}/api/v3"（GHE の場合）
    "gitlab"       → "https://{host}/api/v4"
    "bitbucket"    → "https://api.bitbucket.org/2.0"
    "azure-devops" → "https://dev.azure.com/{org}/{project}/_apis"
    "gitea"        → "https://{host}/api/v1"
    "forgejo"      → "https://{host}/api/v1"
    "gogs"         → "https://{host}/api/v1"
    "gitbucket"    → "https://{host}/api/v3"
    "backlog"      → "https://{host}/api/v2"
    """
```

#### TOML 読み書き方針

- **読み込み**: 標準ライブラリ `tomllib.load()` を使用（Python 3.11+ 保証）
- **書き込み**: `tomllib` は読み取り専用のため、シンプルな文字列フォーマットで書き込む

```python
def _write_toml_tokens(path: Path, tokens: dict[str, str]) -> None:
    """credentials.toml を書き込む。
    
    フォーマット:
    [tokens]
    "github.com" = "ghp_xxxx"
    "gitlab.example.com" = "glpat-xxxx"
    
    値に含まれる特殊文字はダブルクォートでエスケープ。
    既存ファイルは全体を上書きする（部分更新ではない）。
    """
```

- 書き込み時は全件読み込み → dict 更新 → 全件書き出し の流れ
- config.toml の書き込みは v1 スコープでは不要（手動編集を想定）

---

### 2.4 auth.py

#### 責務
トークンの解決（credentials.toml + 環境変数フォールバック）と credentials.toml の読み書き。

#### 公開関数

```python
# サービス種別 → 環境変数名のマッピング
_SERVICE_ENV_MAP: dict[str, str] = {
    "github":      "GITHUB_TOKEN",
    "gitlab":      "GITLAB_TOKEN",
    "gitea":       "GITEA_TOKEN",
    "forgejo":     "GITEA_TOKEN",
    "gogs":        "GITEA_TOKEN",
    "gitbucket":   "GITBUCKET_TOKEN",
    "bitbucket":   "BITBUCKET_APP_PASSWORD",
    "backlog":     "BACKLOG_API_KEY",
    "azure-devops": "AZURE_DEVOPS_PAT",
}


def resolve_token(host: str, service_type: str) -> str:
    """トークンを解決する。

    解決順序:
    1. credentials.toml の tokens.{host}
    2. _SERVICE_ENV_MAP[service_type] 環境変数
    3. GFO_TOKEN 環境変数
    4. すべて未設定なら AuthError

    返り値: トークン文字列（Bitbucket の場合は "user:password" 形式）
    """

def save_token(host: str, token: str) -> None:
    """credentials.toml にトークンを保存する。

    1. 設定ディレクトリが存在しなければ作成（mkdir -p 相当）
    2. 既存の credentials.toml を読み込み（なければ空 dict）
    3. tokens[host] = token で更新
    4. 全件書き出し
    5. パーミッション設定:
       - POSIX: os.chmod(path, 0o600)
       - Windows: subprocess.run(["icacls", str(path), "/inheritance:r",
                   "/grant:r", f"{os.getlogin()}:R"], ...)
         ※ ベストエフォート（失敗しても続行）
    """

def load_tokens() -> dict[str, str]:
    """credentials.toml の [tokens] セクションを dict で返す。
    
    ファイルが存在しない場合は空 dict。
    """

def get_auth_status() -> list[dict[str, str]]:
    """全ホストのトークン状態を返す。
    
    返り値: [{"host": "github.com", "status": "configured", "source": "credentials.toml"}, ...]
    credentials.toml のトークンと、環境変数で設定されているトークンの両方を列挙。
    トークンの値自体は含めない（セキュリティ考慮）。
    """
```

---

### 2.5 http.py

#### 責務
`requests` ライブラリのラッパー。認証ヘッダー付与、エラーハンドリング、ページネーション。

#### 公開クラス・関数

```python
class HttpClient:
    """認証付き HTTP クライアント。

    アダプターごとに 1 インスタンス生成する。
    """

    def __init__(self, base_url: str, auth_header: dict[str, str] | None = None,
                 auth_params: dict[str, str] | None = None,
                 basic_auth: tuple[str, str] | None = None,
                 extra_headers: dict[str, str] | None = None,
                 default_params: dict[str, str] | None = None):
        """
        Args:
            base_url:       API ベース URL（末尾スラッシュなし）
            auth_header:    認証ヘッダー dict（例: {"Authorization": "Bearer xxx"}）
            auth_params:    認証クエリパラメータ dict（例: {"apiKey": "xxx"}）Backlog 用
            basic_auth:     (username, password) タプル。Bitbucket / Azure DevOps 用
            extra_headers:  追加ヘッダー（例: Content-Type 等）
            default_params: 全リクエストに付与するデフォルトクエリパラメータ
                            （例: Azure DevOps の {"api-version": "7.1"}）

        auth_header, auth_params, basic_auth は排他的に使用する。
        複数指定された場合は ValueError を送出する。
        """
        # 排他的認証の検証
        auth_count = sum(x is not None for x in (auth_header, auth_params, basic_auth))
        if auth_count > 1:
            raise ValueError("auth_header, auth_params, basic_auth are mutually exclusive.")
        self._session = requests.Session()
        self._default_params = default_params or {}
        # Session に認証情報を設定
        # extra_headers を Session.headers に追加

    def request(self, method: str, path: str, *,
                params: dict | None = None,
                json: Any = None,
                data: str | None = None,
                headers: dict[str, str] | None = None,
                timeout: int = 30) -> requests.Response:
        """HTTP リクエストを実行する。

        1. URL 構築: base_url + path
        2. default_params → auth_params → params の順でクエリパラメータをマージ
        3. requests.Session.request() を呼び出し
        4. _handle_response() でステータスコードを検査
        5. Response を返す
        """

    def get(self, path: str, **kwargs) -> requests.Response:
        """GET リクエスト。"""

    def post(self, path: str, **kwargs) -> requests.Response:
        """POST リクエスト。"""

    def put(self, path: str, **kwargs) -> requests.Response:
        """PUT リクエスト。"""

    def patch(self, path: str, **kwargs) -> requests.Response:
        """PATCH リクエスト。"""

    def _handle_response(self, response: requests.Response) -> None:
        """ステータスコードを検査し、適切なエラーを送出する。
        
        200-299: 正常（何もしない）
        401/403: AuthenticationError（トークン再設定を案内するメッセージ付き）
        404:     NotFoundError（リソースが見つからない旨のメッセージ）
        429:     Retry-After ヘッダーを読み取り time.sleep() 後に 1 回リトライ
                 リトライも 429 なら RateLimitError を送出
        5xx:     ServerError
        その他:  HttpError(status_code, response.text)
        """

    @staticmethod
    def _mask_api_key(url: str) -> str:
        """URL 内の apiKey=xxx を apiKey=*** に置換する。

        正規表現: re.sub(r'apiKey=[^&]+', 'apiKey=***', url)

        使用箇所:
        - _handle_response() 内のエラーメッセージ構築時: HttpError の url 引数に渡す前に適用
        - HttpError.__init__ に渡す url を常にマスク済みにすることで、
          エラーメッセージから API キーが漏れることを防止する
        """


def paginate_link_header(client: HttpClient, path: str, *,
                         params: dict | None = None,
                         per_page: int = 30,
                         per_page_key: str = "per_page",
                         limit: int = 30) -> list[dict]:
    """Link header ベースのページネーション（GitHub / Gitea / GitBucket 用）。

    1. params に {per_page_key}={per_page} パラメータを追加
       - GitHub / GitBucket: per_page_key="per_page"
       - Gitea / Forgejo / Gogs: per_page_key="limit"
    2. GET リクエスト実行
    3. レスポンスの Link ヘッダーから rel="next" URL を抽出
    4. limit に達するか、next URL がなくなるまで繰り返す
    5. limit=0 の場合は全件取得

    返り値: JSON レスポンス（list[dict]）の結合リスト

    Link ヘッダーパース:
    re.search(r'<([^>]+)>;\s*rel="next"', link_header)
    """

def paginate_offset(client: HttpClient, path: str, *,
                    params: dict | None = None,
                    count: int = 20,
                    limit: int = 30,
                    count_key: str = "count",
                    offset_key: str = "offset") -> list[dict]:
    """オフセットベースのページネーション（Backlog 用）。

    1. params に count={count}, offset=0 を追加
    2. GET リクエスト実行
    3. レスポンスの件数が count 未満 → 終了
    4. offset を count 分増加して次ページ取得
    5. limit に達するまで繰り返す
    6. limit=0 の場合は全件取得
    """

def paginate_top_skip(client: HttpClient, path: str, *,
                      params: dict | None = None,
                      top: int = 30,
                      limit: int = 30,
                      result_key: str = "value") -> list[dict]:
    """$top+$skip ベースのページネーション（Azure DevOps 用）。

    1. params に $top={top}, $skip=0 を追加
    2. GET リクエスト実行
    3. レスポンス JSON の {result_key} 配列を結果に追加
    4. 件数が $top 未満 → 終了
    5. $skip を $top 分増加して次ページ取得
    6. limit に達するまで繰り返す
    """

def paginate_page_param(client: HttpClient, path: str, *,
                        params: dict | None = None,
                        per_page: int = 20,
                        limit: int = 30,
                        next_page_header: str = "X-Next-Page") -> list[dict]:
    """ページパラメータ + レスポンスヘッダーベースのページネーション（GitLab 用）。

    1. params に page=1, per_page={per_page} を追加
    2. GET リクエスト実行
    3. レスポンスの {next_page_header} ヘッダーが空でなければ page を更新して次ページ取得
    4. limit に達するか、次ページがなくなるまで繰り返す
    5. limit=0 の場合は全件取得
    """

def paginate_response_body(client: HttpClient, path: str, *,
                           params: dict | None = None,
                           limit: int = 30,
                           values_key: str = "values",
                           next_key: str = "next") -> list[dict]:
    """レスポンスボディベースのページネーション（Bitbucket Cloud 用）。

    1. GET リクエスト実行
    2. レスポンス JSON の {values_key} 配列がデータ
    3. {next_key} フィールドがあれば次ページ URL として使用
    4. limit に達するか、next URL がなくなるまで繰り返す
    5. limit=0 の場合は全件取得
    """
```

#### 認証ヘッダー構築（adapter 側で HttpClient に渡す）

| サービス | HttpClient 初期化 |
|---------|-------------------|
| GitHub | `auth_header={"Authorization": f"Bearer {token}"}` |
| GitLab | `auth_header={"Private-Token": token}` |
| Bitbucket | `basic_auth=(username, password)` ※ token を `:` で分割 |
| Azure DevOps | `basic_auth=("", pat)`, `default_params={"api-version": "7.1"}` |
| Gitea/Forgejo/Gogs | `auth_header={"Authorization": f"token {token}"}` |
| GitBucket | `auth_header={"Authorization": f"token {token}"}` |
| Backlog | `auth_params={"apiKey": token}` |

---

### 2.6 output.py

#### 責務
データクラスのリストを table / json / plain 形式に変換して stdout に出力する。

#### 公開関数

```python
def output(data: Any, *, format: str = "table", fields: list[str] | None = None) -> None:
    """データを指定フォーマットで stdout に出力する。
    
    data がリスト → 一覧表示
    data が単一オブジェクト → 詳細表示
    """

def format_table(items: list, fields: list[str]) -> str:
    """テーブル形式にフォーマットする。
    
    ヘッダー行 + 区切り行 + データ行。
    各カラム幅はデータに合わせて自動調整。
    
    例:
    #    TITLE              STATE   AUTHOR
    ---  -----------------  ------  ------
    1    Fix typo           open    alice
    42   Add feature        merged  bob
    """

def format_json(items: list) -> str:
    """JSON 形式にフォーマットする。
    
    dataclass を dict に変換し、json.dumps(indent=2, ensure_ascii=False)。
    単一オブジェクトの場合はオブジェクト、リストの場合は配列。
    """

def format_plain(items: list, fields: list[str]) -> str:
    """プレーン形式にフォーマットする。
    
    タブ区切り。ヘッダーなし。パイプ処理向け。
    例:
    1\tFix typo\topen\talice
    42\tAdd feature\tmerged\tbob
    """
```

#### 各リソースの表示フィールド

| リソース | list 表示フィールド | view 表示フィールド |
|---------|-------------------|-------------------|
| PullRequest | number, title, state, author | 全フィールド |
| Issue | number, title, state, author | 全フィールド |
| Repository | full_name, description, private | 全フィールド |
| Release | tag, title, draft, prerelease | 全フィールド |
| Label | name, color, description | — |
| Milestone | number, title, state, due_date | — |

#### dataclass → dict 変換

```python
from dataclasses import asdict

def _to_dict(obj) -> dict:
    """dataclass を dict に変換。None フィールドは view 時に "—" として表示。"""
    return asdict(obj)
```

---

### 2.7 cli.py

#### 責務
argparse による全サブコマンド定義とディスパッチ。

#### 構造設計

```python
def create_parser() -> argparse.ArgumentParser:
    """メインパーサーと全サブコマンドパーサーを構築して返す。"""
    
    parser = argparse.ArgumentParser(prog="gfo", description="統合 Git Forge CLI")
    parser.add_argument("--format", choices=["table", "json", "plain"], default=None)
    parser.add_argument("--version", action="version", version=f"gfo {__version__}")
    
    subparsers = parser.add_subparsers(dest="command")
    
    # gfo init
    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--non-interactive", action="store_true")
    init_parser.add_argument("--type")
    init_parser.add_argument("--host")
    init_parser.add_argument("--api-url")
    init_parser.add_argument("--project-key")
    
    # gfo auth → サブサブコマンド
    auth_parser = subparsers.add_parser("auth")
    auth_sub = auth_parser.add_subparsers(dest="subcommand")
    # auth login
    login_parser = auth_sub.add_parser("login")
    login_parser.add_argument("--host")
    login_parser.add_argument("--token")
    # auth status
    auth_sub.add_parser("status")
    
    # gfo pr → サブサブコマンド
    pr_parser = subparsers.add_parser("pr")
    pr_sub = pr_parser.add_subparsers(dest="subcommand")
    # pr list
    pr_list = pr_sub.add_parser("list")
    pr_list.add_argument("--state", choices=["open","closed","merged","all"], default="open")
    pr_list.add_argument("--limit", type=int, default=30)
    # pr create, view, merge, close, checkout ...（同様のパターン）
    
    # gfo issue → サブサブコマンド
    issue_parser = subparsers.add_parser("issue")
    issue_sub = issue_parser.add_subparsers(dest="subcommand")
    # issue list
    issue_list = issue_sub.add_parser("list")
    issue_list.add_argument("--state", choices=["open","closed","all"], default="open")
    issue_list.add_argument("--assignee")
    issue_list.add_argument("--label")
    issue_list.add_argument("--limit", type=int, default=30)
    # issue create
    issue_create = issue_sub.add_parser("create")
    issue_create.add_argument("--title", required=True)  # 省略時はエラー: "Error: --title is required"
    issue_create.add_argument("--body", default="")
    issue_create.add_argument("--assignee")
    issue_create.add_argument("--label")
    issue_create.add_argument("--type")
    issue_create.add_argument("--priority")
    # issue view, close ...

    # gfo repo, release, label, milestone も同様
    
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI エントリポイント。

    1. create_parser() でパーサー構築
    2. args = parser.parse_args(argv)
    3. resolved_format = args.format or get_default_output_format()
    4. command + subcommand でディスパッチテーブルを参照
    5. handler(args, format=resolved_format) でコマンドハンドラを呼び出し
    6. GfoError をキャッチして stderr 出力 + exit(1)
       - NotSupportedError の場合:
         a. stderr に str(err) を出力
         b. err.web_url が存在すれば stdout に出力（パイプ利用可能にするため）
         c. exit(1)
    7. 正常終了は exit(0)
    """
```

#### ディスパッチテーブル

```python
_DISPATCH: dict[tuple[str, str | None], Callable] = {
    ("init", None):          commands.init.handle,
    ("auth", "login"):       commands.auth_cmd.handle_login,
    ("auth", "status"):      commands.auth_cmd.handle_status,
    ("pr", "list"):          commands.pr.handle_list,
    ("pr", "create"):        commands.pr.handle_create,
    ("pr", "view"):          commands.pr.handle_view,
    ("pr", "merge"):         commands.pr.handle_merge,
    ("pr", "close"):         commands.pr.handle_close,
    ("pr", "checkout"):      commands.pr.handle_checkout,
    ("issue", "list"):       commands.issue.handle_list,
    ("issue", "create"):     commands.issue.handle_create,
    ("issue", "view"):       commands.issue.handle_view,
    ("issue", "close"):      commands.issue.handle_close,
    ("repo", "list"):        commands.repo.handle_list,
    ("repo", "create"):      commands.repo.handle_create,
    ("repo", "clone"):       commands.repo.handle_clone,
    ("repo", "view"):        commands.repo.handle_view,
    ("release", "list"):     commands.release.handle_list,
    ("release", "create"):   commands.release.handle_create,
    ("label", "list"):       commands.label.handle_list,
    ("label", "create"):     commands.label.handle_create,
    ("milestone", "list"):   commands.milestone.handle_list,
    ("milestone", "create"): commands.milestone.handle_create,
}
```

---

### 2.8 adapter/base.py

#### データクラス実装方針

`@dataclass(frozen=True, slots=True)` を使用する。

- **frozen=True**: データクラスは API レスポンスから生成した後に変更しない。不変性を保証する
- **slots=True**: メモリ効率向上。Python 3.10+ で利用可能
- **NamedTuple ではなく dataclass を採用する理由**: `Optional` フィールドのデフォルト値指定が自然に書ける。将来的なメソッド追加にも対応しやすい

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PullRequest:
    number: int
    title: str
    body: str | None
    state: str          # "open" | "closed" | "merged"
    author: str
    source_branch: str
    target_branch: str
    draft: bool
    url: str
    created_at: str     # ISO 8601
    updated_at: str | None


@dataclass(frozen=True, slots=True)
class Issue:
    number: int
    title: str
    body: str | None
    state: str          # "open" | "closed"
    author: str
    assignees: list[str]
    labels: list[str]
    url: str
    created_at: str


@dataclass(frozen=True, slots=True)
class Repository:
    name: str
    full_name: str      # "owner/repo"
    description: str | None
    private: bool
    default_branch: str | None
    clone_url: str
    url: str


@dataclass(frozen=True, slots=True)
class Release:
    tag: str
    title: str
    body: str | None
    draft: bool
    prerelease: bool
    url: str
    created_at: str


@dataclass(frozen=True, slots=True)
class Label:
    name: str
    color: str | None
    description: str | None


@dataclass(frozen=True, slots=True)
class Milestone:
    number: int
    title: str
    description: str | None
    state: str          # "open" | "closed"
    due_date: str | None
```

**注意**: `frozen=True` の場合 `list[str]` フィールド（`Issue.assignees`, `Issue.labels`）のミュータブル性は保証されない。しかし、生成後に変更しない設計方針なので問題ない。

#### ABC 定義

```python
class GitServiceAdapter(ABC):
    """Git サービスアダプターの抽象基底クラス。"""

    def __init__(self, client: HttpClient, owner: str, repo: str, **kwargs):
        """
        Args:
            client: 認証済み HttpClient インスタンス
            owner:  リポジトリオーナー（workspace, org 等含む）
            repo:   リポジトリ名
            **kwargs: サービス固有パラメータ
                      Azure DevOps: organization, project
                      Backlog: project_key
        """
        self._client = client
        self._owner = owner
        self._repo = repo

    # --- PR ---
    @abstractmethod
    def list_pull_requests(self, *, state: str = "open",
                           limit: int = 30) -> list[PullRequest]: ...

    @abstractmethod
    def create_pull_request(self, *, title: str, body: str = "",
                            base: str, head: str,
                            draft: bool = False) -> PullRequest: ...

    @abstractmethod
    def get_pull_request(self, number: int) -> PullRequest: ...

    @abstractmethod
    def merge_pull_request(self, number: int, *,
                           method: str = "merge") -> None: ...

    @abstractmethod
    def close_pull_request(self, number: int) -> None: ...

    def get_pr_checkout_refspec(self, number: int) -> str:
        """PR チェックアウト用の refspec を返す。
        
        サブクラスでオーバーライド可能。デフォルト実装はなし（abstractmethod にはしない）。
        サポートしないサービスは NotSupportedError を送出。
        """
        raise NotSupportedError(self.service_name, "pr checkout")

    # --- Issue ---
    @abstractmethod
    def list_issues(self, *, state: str = "open",
                    assignee: str | None = None,
                    label: str | None = None,
                    limit: int = 30) -> list[Issue]: ...

    @abstractmethod
    def create_issue(self, *, title: str, body: str = "",
                     assignee: str | None = None,
                     label: str | None = None,
                     **kwargs) -> Issue: ...

    @abstractmethod
    def get_issue(self, number: int) -> Issue: ...

    @abstractmethod
    def close_issue(self, number: int) -> None: ...

    # --- Repository ---
    @abstractmethod
    def list_repositories(self, *, owner: str | None = None,
                          limit: int = 30) -> list[Repository]: ...

    @abstractmethod
    def create_repository(self, *, name: str, private: bool = False,
                          description: str = "") -> Repository: ...

    @abstractmethod
    def get_repository(self, owner: str | None = None,
                       name: str | None = None) -> Repository: ...

    # --- Release ---
    @abstractmethod
    def list_releases(self, *, limit: int = 30) -> list[Release]: ...

    @abstractmethod
    def create_release(self, *, tag: str, title: str = "",
                       notes: str = "", draft: bool = False,
                       prerelease: bool = False) -> Release: ...

    # --- Label ---
    @abstractmethod
    def list_labels(self) -> list[Label]: ...

    @abstractmethod
    def create_label(self, *, name: str, color: str | None = None,
                     description: str | None = None) -> Label: ...

    # --- Milestone ---
    @abstractmethod
    def list_milestones(self) -> list[Milestone]: ...

    @abstractmethod
    def create_milestone(self, *, title: str,
                         description: str | None = None,
                         due_date: str | None = None) -> Milestone: ...

    # --- プロパティ ---
    @property
    @abstractmethod
    def service_name(self) -> str:
        """サービス名を返す（エラーメッセージ用）。"""
        ...
```

---

### 2.9 adapter/registry.py

#### 責務
サービス種別文字列からアダプタークラスを解決し、インスタンスを生成する。

```python
from typing import Type

_REGISTRY: dict[str, Type[GitServiceAdapter]] = {}


def register(service_type: str):
    """デコレータとして使用。アダプタークラスをレジストリに登録する。

    Usage:
        @register("github")
        class GitHubAdapter(GitServiceAdapter): ...
    """
    def decorator(cls):
        _REGISTRY[service_type] = cls
        return cls
    return decorator


def get_adapter_class(service_type: str) -> Type[GitServiceAdapter]:
    """サービス種別からアダプタークラスを返す。
    
    未登録の場合は UnsupportedServiceError。
    """
    if service_type not in _REGISTRY:
        raise UnsupportedServiceError(service_type)
    return _REGISTRY[service_type]


def create_adapter(config: ProjectConfig) -> GitServiceAdapter:
    """ProjectConfig からアダプターインスタンスを生成する。

    1. resolve_token(config.host, config.service_type) でトークン取得
    2. サービス種別に応じた HttpClient を構築
    3. get_adapter_class(config.service_type) でクラス取得
    4. クラスをインスタンス化して返す
    """
```

#### 各アダプターファイルでの登録

```python
# adapter/github.py
from .registry import register

@register("github")
class GitHubAdapter(GitServiceAdapter):
    ...
```

#### インポート時登録の仕組み

`adapter/__init__.py` で全アダプターモジュールを import し、デコレータによる登録を実行させる。

```python
# adapter/__init__.py
from . import github, gitlab, gitea, forgejo, gogs, bitbucket, gitbucket, backlog, azure_devops
```

---

### 2.10 各アダプター設計

#### GitHub アダプター (`adapter/github.py`)

```python
@register("github")
class GitHubAdapter(GitServiceAdapter):
    service_name = "GitHub"
    
    def _repos_path(self) -> str:
        return f"/repos/{self._owner}/{self._repo}"
    
    # API レスポンス→データクラス変換例
    @staticmethod
    def _to_pull_request(data: dict) -> PullRequest:
        merged = data.get("merged_at") is not None
        if data["state"] == "closed" and merged:
            state = "merged"
        else:
            state = data["state"]  # "open" or "closed"
        
        return PullRequest(
            number=data["number"],
            title=data["title"],
            body=data.get("body"),
            state=state,
            author=data["user"]["login"],
            source_branch=data["head"]["ref"],
            target_branch=data["base"]["ref"],
            draft=data.get("draft", False),
            url=data["html_url"],
            created_at=data["created_at"],
            updated_at=data.get("updated_at"),
        )
    
    def list_pull_requests(self, *, state="open", limit=30):
        # state="merged" → API には state="closed" で問い合わせ、結果をフィルタ
        api_state = "closed" if state == "merged" else state
        params = {"state": api_state}
        results = paginate_link_header(self._client, f"{self._repos_path()}/pulls",
                                       params=params, limit=limit)
        prs = [self._to_pull_request(r) for r in results]
        if state == "merged":
            prs = [pr for pr in prs if pr.state == "merged"]
        return prs
    
    def get_pr_checkout_refspec(self, number: int) -> str:
        return f"pull/{number}/head"
```

#### GitLab アダプター (`adapter/gitlab.py`)

```python
@register("gitlab")
class GitLabAdapter(GitServiceAdapter):
    service_name = "GitLab"
    
    def _project_path(self) -> str:
        """owner/repo を URL エンコードしたプロジェクト ID パスを返す。"""
        project_id = quote(f"{self._owner}/{self._repo}", safe="")
        return f"/projects/{project_id}"
    
    # ページネーション: http.py の paginate_page_param() を使用
    def list_pull_requests(self, *, state="open", limit=30):
        state_map = {"open": "opened", "closed": "closed", "merged": "merged", "all": "all"}
        params = {"state": state_map.get(state, state)}
        results = paginate_page_param(self._client, f"{self._project_path()}/merge_requests",
                                      params=params, limit=limit)
        return [self._to_pull_request(r) for r in results]
    
    def get_pr_checkout_refspec(self, number: int) -> str:
        return f"merge-requests/{number}/head"
```

#### Bitbucket Cloud アダプター (`adapter/bitbucket.py`)

```python
@register("bitbucket")
class BitbucketAdapter(GitServiceAdapter):
    service_name = "Bitbucket Cloud"
    
    def _repos_path(self) -> str:
        return f"/repositories/{self._owner}/{self._repo}"
    
    # ページネーション: http.py の paginate_response_body() を使用
    # 例: paginate_response_body(self._client, path, params=params, limit=limit)
    
    def get_pr_checkout_refspec(self, number: int) -> str:
        # Bitbucket はソースブランチ名を直接 fetch するため、
        # まず PR 情報を取得してブランチ名を返す
        pr = self.get_pull_request(number)
        return pr.source_branch  # git_util.git_fetch で直接使用
```

#### Azure DevOps アダプター (`adapter/azure_devops.py`)

```python
@register("azure-devops")
class AzureDevOpsAdapter(GitServiceAdapter):
    service_name = "Azure DevOps"
    
    def __init__(self, client, owner, repo, *, organization, project, **kwargs):
        super().__init__(client, owner, repo)
        self._org = organization
        self._project = project
        # api-version は HttpClient の default_params={"api-version": "7.1"} で
        # 全リクエストに自動付与される（create_adapter 内で設定）
    
    def _git_path(self) -> str:
        return f"/_apis/git/repositories/{self._repo}"
    
    def _wit_path(self) -> str:
        return "/_apis/wit"
    
    # PR 状態マッピング
    _PR_STATE_TO_API = {"open": "active", "closed": "abandoned", "merged": "completed", "all": "all"}
    _PR_STATE_FROM_API = {"active": "open", "abandoned": "closed", "completed": "merged"}
    
    # Issue → Work Item
    # issue create 時は JSON Patch 形式
    def create_issue(self, *, title, body="", assignee=None, label=None,
                     work_item_type="Task", **kwargs):
        patches = [
            {"op": "add", "path": "/fields/System.Title", "value": title},
        ]
        if body:
            patches.append({"op": "add", "path": "/fields/System.Description", "value": body})
        if assignee:
            patches.append({"op": "add", "path": "/fields/System.AssignedTo", "value": assignee})
        if label:
            patches.append({"op": "add", "path": "/fields/System.Tags", "value": label})
        
        resp = self._client.post(
            f"{self._wit_path()}/workitems/${work_item_type}",
            data=json.dumps(patches),
            headers={"Content-Type": "application/json-patch+json"},
            # api-version は HttpClient の default_params で自動付与
        )
        return self._to_issue(resp.json())
    
    # issue list は WIQL 2段階
    def list_issues(self, *, state="open", assignee=None, label=None, limit=30):
        """
        1. WIQL クエリ構築
        2. POST _apis/wit/wiql で ID リスト取得
        3. GET _apis/wit/workitems?ids=1,2,3 でバッチ取得
        """
        ...
    
    def get_pr_checkout_refspec(self, number: int) -> str:
        return f"pull/{number}/head"
    
    # ブランチ名の refs/heads/ 付与/除去
    @staticmethod
    def _add_refs_prefix(branch: str) -> str:
        if not branch.startswith("refs/heads/"):
            return f"refs/heads/{branch}"
        return branch
    
    @staticmethod
    def _strip_refs_prefix(ref: str) -> str:
        return ref.removeprefix("refs/heads/")
```

#### Gitea アダプター (`adapter/gitea.py`)

```python
@register("gitea")
class GiteaAdapter(GitServiceAdapter):
    service_name = "Gitea"
    
    def _repos_path(self) -> str:
        return f"/repos/{self._owner}/{self._repo}"
    
    # GitHub と同様の Link header ページネーション
    # パラメータ名が page + limit のため per_page_key="limit" を使用
    # 例: paginate_link_header(self._client, path, per_page_key="limit", ...)
    
    def get_pr_checkout_refspec(self, number: int) -> str:
        return f"pull/{number}/head"
```

#### Forgejo アダプター (`adapter/forgejo.py`)

```python
@register("forgejo")
class ForgejoAdapter(GiteaAdapter):
    """Gitea を継承。現時点ではオーバーライドなし。"""
    service_name = "Forgejo"
```

#### Gogs アダプター (`adapter/gogs.py`)

```python
@register("gogs")
class GogsAdapter(GiteaAdapter):
    """Gitea を継承。PR / Label / Milestone 操作を NotSupportedError でオーバーライド。"""
    service_name = "Gogs"
    
    def _web_url(self) -> str:
        """Web UI のベース URL を構築する。"""
        # HttpClient の base_url から /api/v1 を除去
        return self._client._base_url.removesuffix("/api/v1")

    def list_pull_requests(self, **kwargs):
        raise NotSupportedError("Gogs", "pull request operations",
                                web_url=f"{self._web_url()}/{self._owner}/{self._repo}/pulls")

    def create_pull_request(self, **kwargs):
        raise NotSupportedError("Gogs", "pull request operations",
                                web_url=f"{self._web_url()}/{self._owner}/{self._repo}/compare")

    def get_pull_request(self, number):
        raise NotSupportedError("Gogs", "pull request operations",
                                web_url=f"{self._web_url()}/{self._owner}/{self._repo}/pulls/{number}")

    def merge_pull_request(self, number, **kwargs):
        raise NotSupportedError("Gogs", "pull request operations",
                                web_url=f"{self._web_url()}/{self._owner}/{self._repo}/pulls/{number}")

    def close_pull_request(self, number):
        raise NotSupportedError("Gogs", "pull request operations",
                                web_url=f"{self._web_url()}/{self._owner}/{self._repo}/pulls/{number}")
    
    def list_labels(self):
        raise NotSupportedError("Gogs", "label operations")
    
    def create_label(self, **kwargs):
        raise NotSupportedError("Gogs", "label operations")
    
    def list_milestones(self):
        raise NotSupportedError("Gogs", "milestone operations")
    
    def create_milestone(self, **kwargs):
        raise NotSupportedError("Gogs", "milestone operations")
```

#### GitBucket アダプター (`adapter/gitbucket.py`)

```python
@register("gitbucket")
class GitBucketAdapter(GitHubAdapter):
    """GitHub を継承。base_url と認証ヘッダーが異なるのみ。
    
    API パス構造は GitHub v3 互換。
    差異があるエンドポイントのみオーバーライド。
    """
    service_name = "GitBucket"
    
    def get_pr_checkout_refspec(self, number: int) -> str:
        return f"pull/{number}/head"
```

#### Backlog アダプター (`adapter/backlog.py`)

```python
@register("backlog")
class BacklogAdapter(GitServiceAdapter):
    service_name = "Backlog"
    
    def __init__(self, client, owner, repo, *, project_key, **kwargs):
        super().__init__(client, owner, repo)
        self._project_key = project_key
        self._project_id: int | None = None  # 遅延取得
    
    def _pr_path(self) -> str:
        return f"/projects/{self._project_key}/git/repositories/{self._repo}/pullRequests"
    
    def _ensure_project_id(self) -> int:
        """プロジェクト ID を取得してキャッシュする。"""
        if self._project_id is None:
            resp = self._client.get(f"/projects/{self._project_key}")
            self._project_id = resp.json()["id"]
        return self._project_id

    _merged_status_id: int | None = None  # キャッシュ

    def _resolve_merged_status_id(self) -> int | None:
        """PR ステータス一覧から Merged 相当の statusId を動的に判定する。

        GET /projects/{key}/statuses でステータス一覧を取得し、
        name に "merged" を含む（大文字小文字無視）エントリの id を返す。
        見つからない場合は None。結果はインスタンスにキャッシュする。
        """
        if self._merged_status_id is not None:
            return self._merged_status_id
        resp = self._client.get(f"/projects/{self._project_key}/statuses")
        for status in resp.json():
            if "merged" in status["name"].lower():
                self._merged_status_id = status["id"]
                return self._merged_status_id
        return None
    
    def list_pull_requests(self, *, state="open", limit=30):
        params = {}
        if state == "merged":
            merged_id = self._resolve_merged_status_id()
            if merged_id is not None:
                params["statusId[]"] = merged_id
        elif state != "all":
            # open/closed に応じたステータスフィルタを設定
            pass
        results = paginate_offset(self._client, self._pr_path(),
                                  params=params, limit=limit)
        return [self._to_pull_request(r) for r in results]

    def merge_pull_request(self, number, **kwargs):
        raise NotSupportedError("Backlog", "pull request merge",
                                web_url=f"https://{self._client._base_url.split('//')[1].split('/')[0]}"
                                        f"/git/{self._project_key}/{self._repo}/pullRequests/{number}")
    
    def create_issue(self, *, title, body="", assignee=None, label=None,
                     issue_type=None, priority=None, **kwargs):
        """
        1. _ensure_project_id() でプロジェクト ID 取得
        2. issue_type 未指定: GET /projects/{key}/issueTypes で一覧取得 → 先頭を使用
        3. priority 未指定: GET /priorities で一覧取得 → "中"(Normal) を使用
        4. POST /issues でリクエスト
        """
        ...
    
    def get_pr_checkout_refspec(self, number: int) -> str:
        # Backlog はソースブランチ名を直接 fetch
        pr = self.get_pull_request(number)
        return pr.source_branch
```

---

### 2.11 commands/*.py

#### 共通パターン

全コマンドハンドラは以下の共通パターンに従う。

```python
# commands/pr.py の例

def handle_list(args: argparse.Namespace, *, format: str) -> None:
    """gfo pr list のハンドラ。
    
    1. config = resolve_project_config()
    2. adapter = create_adapter(config)
    3. prs = adapter.list_pull_requests(state=args.state, limit=args.limit)
    4. output(prs, format=format, fields=["number", "title", "state", "author"])
    """

def handle_create(args: argparse.Namespace, *, format: str) -> None:
    """gfo pr create のハンドラ。
    
    1. config = resolve_project_config()
    2. adapter = create_adapter(config)
    3. head = args.head or get_current_branch()
    4. base = args.base or get_default_branch()
    5. title = args.title or get_last_commit_subject()
    6. pr = adapter.create_pull_request(title=title, body=args.body or "",
                                        base=base, head=head, draft=args.draft)
    7. output(pr, format=format)
    """

def handle_view(args: argparse.Namespace, *, format: str) -> None:
    """gfo pr view <number> のハンドラ。"""

def handle_merge(args: argparse.Namespace, *, format: str) -> None:
    """gfo pr merge <number> のハンドラ。"""

def handle_close(args: argparse.Namespace, *, format: str) -> None:
    """gfo pr close <number> のハンドラ。"""

def handle_checkout(args: argparse.Namespace, *, format: str) -> None:
    """gfo pr checkout <number> のハンドラ。
    
    1. config = resolve_project_config()
    2. adapter = create_adapter(config)
    3. pr = adapter.get_pull_request(args.number)
    4. refspec = adapter.get_pr_checkout_refspec(args.number)
    5. git_fetch("origin", refspec)
    6. git_checkout_new_branch(pr.source_branch)
    """
```

#### commands/init.py

```python
def handle(args: argparse.Namespace, *, format: str) -> None:
    """gfo init のハンドラ。

    対話モード:
    1. detect_service() で自動検出
    2. 検出結果を表示: "Detected: {type} at {host}"
    3. "Is this correct? [Y/n]" で確認
    4. 'n' なら手動入力（type, host, api-url, project-key）
    5. save_project_config()

    --non-interactive:
    1. args.type / args.host が必須（未指定ならエラー）
    2. api-url は引数 → config.toml → デフォルト の順で解決
    3. save_project_config()
    """
```

#### commands/repo.py

```python
def handle_list(args: argparse.Namespace, *, format: str) -> None:
    """gfo repo list のハンドラ。

    1. config = resolve_project_config()
    2. adapter = create_adapter(config)
    3. repos = adapter.list_repositories(owner=args.owner, limit=args.limit)
    4. output(repos, format=format, fields=["full_name", "description", "private"])
    """

def handle_create(args: argparse.Namespace, *, format: str) -> None:
    """gfo repo create <name> のハンドラ。

    ホスト解決フロー:
    1. args.host が指定されている → そのホストを使用
    2. 未指定:
       a. git リポジトリ内なら detect_service().host で自動検出
       b. リポジトリ外なら get_default_host()（config.toml の defaults.host）
       c. いずれも未設定なら ConfigError
    3. ホストから service_type を解決（config.toml hosts セクション → probe）
    4. トークンを resolve_token(host, service_type) で取得
    5. HttpClient + adapter を構築
    6. repo = adapter.create_repository(name=args.name, private=args.private,
                                        description=args.description or "")
    7. output(repo, format=format)
    """

def handle_clone(args: argparse.Namespace, *, format: str) -> None:
    """gfo repo clone <owner/name> のハンドラ。

    ホスト解決フロー:
    1. args.host が指定されている → そのホストを使用
    2. 未指定: get_default_host()（config.toml の defaults.host）
    3. 未設定なら ConfigError("No default host configured. Use --host or set defaults.host in config.toml.")

    クローン URL 構築:
    1. ホストの service_type を解決
    2. サービス種別に応じて URL を構築:
       - GitHub:       https://github.com/{owner}/{name}.git
       - GitLab:       https://{host}/{owner}/{name}.git
       - Bitbucket:    https://bitbucket.org/{owner}/{name}.git
       - Azure DevOps: https://dev.azure.com/{org}/{project}/_git/{name}
       - Gitea/Forgejo/Gogs: https://{host}/{owner}/{name}.git
       - GitBucket:    https://{host}/git/{owner}/{name}.git
       - Backlog:      https://{host}/git/{project}/{name}.git
    3. git_clone(url)
    """

def handle_view(args: argparse.Namespace, *, format: str) -> None:
    """gfo repo view [<owner/name>] のハンドラ。

    1. config = resolve_project_config()
    2. adapter = create_adapter(config)
    3. owner, name = args の owner/name をパース（省略時は config から取得）
    4. repo = adapter.get_repository(owner, name)
    5. output(repo, format=format)
    """
```

#### commands/auth_cmd.py

```python
def handle_login(args: argparse.Namespace, *, format: str) -> None:
    """gfo auth login のハンドラ。

    1. host = args.host or detect_service().host（リポジトリ外ならエラー）
    2. token:
       - args.token あり → 使用（警告メッセージ: "Warning: Token may remain in shell history."）
       - args.token なし → getpass.getpass("Token: ") で入力
    3. save_token(host, token)
    4. "Token saved for {host}" を表示
    """

def handle_status(args: argparse.Namespace, *, format: str) -> None:
    """gfo auth status のハンドラ。

    get_auth_status() の結果を table 形式で表示。
    """
```

---

## 3. クラス図・継承関係

```
GitServiceAdapter (ABC)
├── GitHubAdapter
│   └── GitBucketAdapter          ← GitHub を継承、base_url 変更のみ
├── GitLabAdapter                 ← 独立実装
├── BitbucketAdapter              ← 独立実装
├── AzureDevOpsAdapter            ← 独立実装（最も特殊）
├── GiteaAdapter
│   ├── ForgejoAdapter            ← Gitea を継承、オーバーライドなし
│   └── GogsAdapter               ← Gitea を継承、PR/Label/Milestone を NotSupportedError に
└── BacklogAdapter                ← 独立実装

HttpClient
  └─ 各アダプターが内部に保持（コンポジション）

データクラス（frozen dataclass）:
  PullRequest, Issue, Repository, Release, Label, Milestone
```

**継承で共有される主要ロジック**:

| 親クラス | 子クラス | 共有ロジック |
|---------|---------|------------|
| `GitHubAdapter` | `GitBucketAdapter` | 全 API エンドポイントパス、レスポンス→データクラス変換、Link header ページネーション |
| `GiteaAdapter` | `ForgejoAdapter` | 全メソッド（API 完全互換） |
| `GiteaAdapter` | `GogsAdapter` | Issue, Repository, Release の操作。PR / Label / Milestone はオーバーライド |

---

## 4. エラー型の階層設計

```python
class GfoError(Exception):
    """gfo の基底例外。全カスタム例外はこれを継承する。"""
    pass


class GitCommandError(GfoError):
    """git コマンド実行の失敗。"""
    def __init__(self, message: str):
        super().__init__(f"Git error: {message}")


class DetectionError(GfoError):
    """サービス自動検出の失敗。"""
    def __init__(self, message: str = ""):
        msg = "Could not detect git forge service."
        if message:
            msg += f" {message}"
        msg += " Run 'gfo init' to configure manually."
        super().__init__(msg)


class ConfigError(GfoError):
    """設定の解決失敗。"""
    pass


class AuthError(GfoError):
    """認証情報の解決失敗。"""
    def __init__(self, host: str):
        super().__init__(
            f"No token found for {host}. "
            f"Run 'gfo auth login --host {host}' to configure."
        )


class HttpError(GfoError):
    """HTTP リクエストのエラー（基底）。"""
    def __init__(self, status_code: int, message: str, url: str = ""):
        self.status_code = status_code
        self.url = url
        super().__init__(f"HTTP {status_code}: {message}")


class AuthenticationError(HttpError):
    """401/403 認証エラー。"""
    def __init__(self, status_code: int, url: str = ""):
        super().__init__(
            status_code,
            "Authentication failed. Check your token with 'gfo auth status'.",
            url,
        )


class NotFoundError(HttpError):
    """404 リソース未発見。"""
    def __init__(self, url: str = ""):
        super().__init__(404, "Resource not found.", url)


class RateLimitError(HttpError):
    """429 レート制限超過。"""
    def __init__(self, retry_after: int | None = None, url: str = ""):
        msg = "Rate limit exceeded."
        if retry_after:
            msg += f" Retry after {retry_after}s."
        super().__init__(429, msg, url)


class ServerError(HttpError):
    """5xx サーバーエラー。"""
    def __init__(self, status_code: int, url: str = ""):
        super().__init__(status_code, "Server error. Please try again later.", url)


class NotSupportedError(GfoError):
    """サービスが対応していない操作。"""
    def __init__(self, service: str, operation: str, web_url: str | None = None):
        self.service = service
        self.operation = operation
        self.web_url = web_url
        super().__init__(
            f"{service} does not support {operation}. "
            f"Use the web interface instead."
        )


class UnsupportedServiceError(GfoError):
    """未知のサービス種別。"""
    def __init__(self, service_type: str):
        super().__init__(f"Unsupported service type: {service_type}")
```

**エラー階層図**:

```
GfoError
├── GitCommandError
├── DetectionError
├── ConfigError
├── AuthError
├── HttpError
│   ├── AuthenticationError    (401/403)
│   ├── NotFoundError          (404)
│   ├── RateLimitError         (429)
│   └── ServerError            (5xx)
├── NotSupportedError
└── UnsupportedServiceError
```

**例外の定義場所**: `src/gfo/exceptions.py` に全エラー型を集約する（各モジュールからインポート）。

---

## 5. テスト設計

### 5.1 テストファイル構成

```
tests/
├── conftest.py                    # 共通フィクスチャ
├── test_git_util.py               # git_util.py のテスト
├── test_detect.py                 # detect.py のテスト
├── test_config.py                 # config.py のテスト
├── test_auth.py                   # auth.py のテスト
├── test_http.py                   # http.py のテスト
├── test_output.py                 # output.py のテスト
├── test_cli.py                    # cli.py のパーサーテスト
├── test_exceptions.py             # エラー型のメッセージ検証
├── test_commands/
│   ├── conftest.py                # コマンドテスト用共通フィクスチャ（adapter モック）
│   ├── test_pr.py                 # pr ハンドラのロジック検証
│   ├── test_issue.py              # issue ハンドラのロジック検証
│   ├── test_repo.py               # repo ハンドラのロジック検証（ホスト解決フロー含む）
│   ├── test_release.py
│   ├── test_label.py
│   ├── test_milestone.py
│   ├── test_init.py               # init ハンドラの対話/非対話モード
│   └── test_auth_cmd.py           # auth login/status ハンドラ
└── test_adapters/
    ├── conftest.py                # アダプターテスト用共通フィクスチャ
    ├── test_github.py
    ├── test_gitlab.py
    ├── test_bitbucket.py
    ├── test_azure_devops.py
    ├── test_gitea.py
    ├── test_forgejo.py
    ├── test_gogs.py
    ├── test_gitbucket.py
    └── test_backlog.py
```

### 5.2 モック方針

| テスト対象 | モック手法 | 理由 |
|-----------|----------|------|
| `git_util.py` | `unittest.mock.patch("subprocess.run")` | git コマンドの実行結果を制御 |
| `detect.py` | `unittest.mock.patch("gfo.git_util.run_git")` + `responses` | URL パースは純粋関数。API プローブは HTTP モック |
| `config.py` | `tmp_path` + `unittest.mock.patch("gfo.git_util.git_config_get")` | TOML ファイルは tmpdir に作成、git config はモック |
| `auth.py` | `tmp_path` + `unittest.mock.patch.dict(os.environ)` | credentials.toml は tmpdir、環境変数はパッチ |
| `http.py` | `responses` | HTTP レスポンスを完全にモック |
| `adapter/*.py` | `responses` | API レスポンス→データクラス変換を検証 |
| `commands/*.py` | `unittest.mock.patch` でアダプター ABC をモック | コマンドロジックのみ検証 |

### 5.3 conftest.py 共通フィクスチャ

```python
# tests/conftest.py

import pytest
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """一時的な設定ディレクトリ。config.py の get_config_dir() をパッチする。"""
    d = tmp_path / "gfo_config"
    d.mkdir()
    with patch("gfo.config.get_config_dir", return_value=d):
        yield d


@pytest.fixture
def mock_git_config():
    """git config の読み書きをモックする dict ベースのフィクスチャ。"""
    store = {}
    
    def _get(key, cwd=None):
        return store.get(key)
    
    def _set(key, value, cwd=None):
        store[key] = value
    
    with patch("gfo.git_util.git_config_get", side_effect=_get), \
         patch("gfo.git_util.git_config_set", side_effect=_set):
        yield store


@pytest.fixture
def mock_remote_url():
    """git remote URL をモックするフィクスチャ。"""
    def _factory(url: str):
        return patch("gfo.git_util.get_remote_url", return_value=url)
    return _factory
```

```python
# tests/test_adapters/conftest.py

import pytest
import responses as responses_lib
from gfo.http import HttpClient


@pytest.fixture
def mock_responses():
    """responses ライブラリのアクティベーション。"""
    with responses_lib.RequestsMock() as rsps:
        yield rsps


@pytest.fixture
def github_client() -> HttpClient:
    """GitHub 用テスト HttpClient。"""
    return HttpClient(
        base_url="https://api.github.com",
        auth_header={"Authorization": "Bearer test-token"},
    )


@pytest.fixture
def gitlab_client() -> HttpClient:
    """GitLab 用テスト HttpClient。"""
    return HttpClient(
        base_url="https://gitlab.com/api/v4",
        auth_header={"Private-Token": "test-token"},
    )

# 他サービスも同様のパターン
```

### 5.4 テストケース設計方針

#### detect.py テスト

- 全 9 サービスの HTTPS / SSH URL パターン（計 18+ ケース）
- `.git` サフィックスあり/なし
- `ssh://` 形式 + ポート指定
- GitLab サブグループ（`group/sub1/sub2/project`）
- Azure DevOps 旧 URL（`*.visualstudio.com`）
- Backlog SSH URL（特殊ユーザー名形式）
- 未知ホストの API プローブ（Gitea/Forgejo/Gogs の区別）
- プローブ全失敗時の DetectionError

#### adapter テスト

各アダプターで以下を共通的に検証:

1. **list 系**: API レスポンス JSON → データクラスリスト変換の正確性
2. **create 系**: リクエストボディの構造が正しいか（`responses` で検査）
3. **state 正規化**: 各サービスの state 値が "open"/"closed"/"merged" に正しく変換されるか
4. **ページネーション**: 2 ページ以上、0 件、limit 制御
5. **NotSupportedError**: Gogs の PR / Label / Milestone、Backlog の PR merge

#### Azure DevOps 固有テスト

- WIQL クエリの構築が正しいか
- JSON Patch 形式の Work Item 作成リクエスト
- `refs/heads/` prefix の付与/除去
- `completionOptions.mergeStrategy` のマッピング
- Basic Auth ヘッダーの base64 エンコード

#### ページネーション テスト（http.py）

- 2 ページ以上の取得（Link header / offset / $top+$skip 各方式）
- 空の結果（0 件）
- limit が 1 ページ分より少ない場合
- limit=0（全件取得）

### 5.5 開発依存

```toml
[project.optional-dependencies]
dev = ["pytest", "responses"]
```

- `pytest`: テストランナー
- `responses`: `requests` ライブラリの HTTP モック
- `unittest.mock`: 標準ライブラリ（追加インストール不要）

---

## 付録 A: __main__.py エントリポイント

```python
# src/gfo/__main__.py
"""python -m gfo エントリポイント。"""
import sys
from gfo.cli import main

sys.exit(main())
```

## 付録 B: pyproject.toml スクリプトエントリ

```toml
[project.scripts]
gfo = "gfo.cli:main"
```

## 付録 C: exceptions.py の配置

仕様書のプロジェクト構造には `exceptions.py` が明記されていないが、エラー型を 1 ファイルに集約するため `src/gfo/exceptions.py` を追加する。各モジュールは `from gfo.exceptions import GfoError, ...` でインポートする。これは新規ファイルの追加であり、仕様の変更ではない（仕様書のプロジェクト構造は省略表記であり、ユーティリティファイルの追加は許容範囲）。

## 付録 D: __init__.py バージョン定義

```python
# src/gfo/__init__.py
"""gfo — 統合 Git Forge CLI"""
__version__ = "0.1.0"
```

cli.py では `from gfo import __version__` でインポートし、`--version` オプションで表示する。