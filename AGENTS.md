# gfo – Git Forge Operator

複数の Git ホスティングサービスを**統一コマンド**で操作する Python CLI ツール。

## プロジェクト概要

| 項目 | 内容 |
|---|---|
| パッケージ名 | `gfo` |
| エントリポイント | `gfo.cli:main` |
| 対象 Python | 3.11 以上 |
| ライセンス | MIT |

### 対応サービス

| サービス | 識別子 | 認証環境変数 |
|---|---|---|
| GitHub | `github` | `GITHUB_TOKEN` |
| GitLab | `gitlab` | `GITLAB_TOKEN` |
| Bitbucket Cloud | `bitbucket` | `BITBUCKET_APP_PASSWORD`（`user:app-password` 形式） |
| Azure DevOps | `azure-devops` | `AZURE_DEVOPS_PAT` |
| Gitea | `gitea` | `GITEA_TOKEN` |
| Forgejo | `forgejo` | `GITEA_TOKEN` |
| Gogs | `gogs` | `GITEA_TOKEN` |
| GitBucket | `gitbucket` | `GITBUCKET_TOKEN` |
| Backlog | `backlog` | `BACKLOG_API_KEY`（クエリパラメータ `apiKey` で送信） |

---

## 技術スタック

- **ランタイム依存**: `requests` のみ
- **開発依存**: `pytest`, `responses`（HTTP モック）, `pytest-cov`
- **ビルド**: `hatchling`
- **テスト**: `pytest --cov=gfo --cov-report=term-missing`（設定済み）

---

## ディレクトリ構成

```
src/gfo/
├── __init__.py
├── __main__.py          # python -m gfo エントリポイント
├── cli.py               # argparse ルートパーサー
├── auth.py              # トークン保存・解決
├── config.py            # ProjectConfig, save/load, 設定解決
├── detect.py            # remote URL からサービス自動検出
├── exceptions.py        # カスタム例外体系
├── git_util.py          # git コマンドラッパー
├── http.py              # HttpClient, ページネーション
├── output.py            # table/json/plain 出力フォーマッター
├── adapter/
│   ├── base.py          # 抽象基底クラス + データクラス定義
│   ├── registry.py      # レジストリ, create_adapter()
│   ├── github.py
│   ├── gitlab.py
│   ├── bitbucket.py
│   ├── azure_devops.py
│   ├── backlog.py
│   ├── gitea.py
│   ├── forgejo.py       # GiteaAdapter のサブクラス
│   ├── gogs.py          # GiteaAdapter のサブクラス
│   └── gitbucket.py     # GiteaAdapter のサブクラス
└── commands/
    ├── init.py          # gfo init
    ├── auth_cmd.py      # gfo auth login/status
    ├── pr.py            # gfo pr list/create/view/merge/close/checkout
    ├── issue.py         # gfo issue list/create/view/close
    ├── repo.py          # gfo repo list/create/clone/view
    ├── release.py       # gfo release list/create
    ├── label.py         # gfo label list/create
    └── milestone.py     # gfo milestone list/create

tests/
├── conftest.py
├── test_adapter_base.py
├── test_auth.py
├── test_cli.py
├── test_config.py
├── test_adapters/       # アダプターごとのテスト
│   ├── conftest.py
│   ├── test_github.py
│   └── ...（各サービス）
└── test_commands/       # コマンドごとのテスト
    ├── conftest.py      # make_args() ヘルパー
    └── ...（各コマンド）
```

---

## アーキテクチャ

### アダプターパターン

`GitServiceAdapter`（`adapter/base.py`）が抽象基底クラス。全サービス共通の操作を `@abstractmethod` で定義する。

```
GitServiceAdapter (ABC)
├── GitHubAdapter
├── GitLabAdapter
├── BitbucketAdapter
├── BacklogAdapter
├── AzureDevOpsAdapter
├── GiteaAdapter
│   ├── ForgejoAdapter
│   ├── GogsAdapter
│   └── GitBucketAdapter
└── ...
```

`GitHubLikeAdapter`（`adapter/base.py`）は GitHub/Gitea 系の共通 `_to_*` 変換ヘルパーを提供するミックスインクラス。

### レジストリ

`adapter/registry.py` の `@register("service-id")` デコレータでアダプタークラスを登録。
`create_adapter(config)` が `ProjectConfig` から適切なアダプターインスタンスを生成する。

```python
@register("github")
class GitHubAdapter(GitHubLikeAdapter, GitServiceAdapter):
    ...
```

### 設定解決（3層）

優先度順:
1. `git config --local`（リポジトリ単位）
2. `~/.config/gfo/config.toml`（グローバル）
3. remote URL からの自動検出

認証トークン解決順序:
1. `~/.config/gfo/credentials.toml`
2. サービス別環境変数
3. `GFO_TOKEN`（汎用）

ホスト名はすべて `lower()` で正規化する（`auth.py`, `detect.py`, `config.py`）。

### データクラス（`adapter/base.py`）

すべて `frozen=True, slots=True` の `@dataclass`:

| クラス | 用途 |
|---|---|
| `PullRequest` | PR 情報 |
| `Issue` | Issue 情報 |
| `Repository` | リポジトリ情報 |
| `Release` | リリース情報 |
| `Label` | ラベル情報 |
| `Milestone` | マイルストーン情報 |

### ページネーション（`http.py`）

5種類のページネーション方式に対応:
- GitHub 形式（`Link` ヘッダ）
- GitLab 形式（`X-Next-Page` ヘッダ）
- Backlog 形式（`startPosition` クエリパラメータ）
- Azure DevOps 形式（`continuationToken`）
- オフセット形式（汎用）

---

## 例外階層（`exceptions.py`）

```
Exception
└── GfoError                    # 全カスタム例外の基底
    ├── GitCommandError         # git コマンド実行失敗
    ├── DetectionError          # サービス自動検出失敗
    ├── ConfigError             # 設定解決失敗（バリデーションエラー）
    ├── AuthError               # 認証情報なし
    ├── HttpError               # HTTP エラー基底
    │   ├── AuthenticationError # 401/403
    │   ├── NotFoundError       # 404
    │   ├── RateLimitError      # 429
    │   └── ServerError         # 5xx
    ├── NetworkError            # ConnectionError/Timeout/SSLError
    ├── NotSupportedError       # サービスが非対応の操作
    └── UnsupportedServiceError # 未知のサービス種別
```

---

## コーディング規約

### 例外の使い分け

- バリデーション失敗（設定値不正など） → `ConfigError`
- トークン未設定 → `AuthError`
- API レスポンスの構造が予期しない → `GfoError`（`KeyError`/`TypeError` をラップ）
- HTTP 内部のバリデーション → `ValueError`（そのまま OK）

### API レスポンスの変換

`_to_*` メソッド内で `KeyError`/`TypeError` を `GfoError` でラップする:

```python
try:
    return PullRequest(number=data["number"], ...)
except (KeyError, TypeError) as e:
    raise GfoError(f"Unexpected API response: missing field {e}") from e
```

### テストパターン

- HTTP モックは `@responses.activate` デコレータを使用
- `responses` ライブラリのデフォルトは `assert_all_requests_are_fired=True`。未使用モックを登録するとテスト失敗
- コマンドテストの引数生成は `tests/test_commands/conftest.py` の `make_args()` を使用
- テストファイルは `tests/test_adapters/test_{service}.py` および `tests/test_commands/test_{command}.py` に配置

### Azure DevOps 固有

- コンストラクタに `organization` と `project_key` が必要
- `gfo init` 手動設定パスで `organization` の追加入力がある
- API URL 構築失敗時は `'gfo init' を実行してください` を提案するエラーメッセージを使用

### Bitbucket 固有

- トークンは `username:app-password` 形式（コロン区切り）
- Basic 認証で送信
- Issue の label フィルタは `component.name="{label}"` クエリパラメータ

---

## 開発コマンド

```bash
# インストール（開発モード）
pip install -e ".[dev]"

# テスト実行（カバレッジ付き）
pytest

# 特定テストの実行
pytest tests/test_commands/test_pr.py

# 特定テストファイル + 詳細出力
pytest tests/test_adapters/test_github.py -v
```

カバレッジ: 1016 テスト、99%（`__main__.py` の 4 行のみ未カバー）
