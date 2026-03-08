# gfo 実装タスクリスト

design.md に基づく実装タスク。1タスク = 1コミット単位。
依存関係図 (design.md L3-61) に従い、下位モジュールから順に実装する。

---

## Phase 0: プロジェクトセットアップ

### T-01: パッケージ構造・プロジェクト設定 ✅
- **参照**: design.md L2199-2228 (付録 A-D), L2186-2195 (5.5 開発依存)
- **成果物**:
  - `pyproject.toml` — メタデータ, scripts エントリ (`gfo = "gfo.cli:main"`), dev 依存
  - `src/gfo/__init__.py` — `__version__ = "0.1.0"`
  - `src/gfo/__main__.py` — `python -m gfo` エントリポイント
  - `src/gfo/commands/__init__.py`
  - `src/gfo/adapter/__init__.py`
  - `tests/__init__.py`, `tests/test_commands/__init__.py`, `tests/test_adapters/__init__.py`
  - コーディング規約: `import gfo.xxx` 形式、完全修飾呼び出し (design.md L68-74)
- **検証**: `pip install -e ".[dev]"` が成功し、`python -m gfo --version` で `0.1.0` が表示される

---

## Phase 1: 基盤モジュール

### T-02: exceptions.py ✅
- **参照**: design.md L1887-2005 (セクション 4), L2217-2219 (付録 C)
- **成果物**:
  - `src/gfo/exceptions.py` — 全エラー型 (GfoError, GitCommandError, DetectionError, ConfigError, AuthError, HttpError, AuthenticationError, NotFoundError, RateLimitError, ServerError, NetworkError, NotSupportedError, UnsupportedServiceError)
  - `tests/test_exceptions.py` — メッセージフォーマット検証
- **検証**: `pytest tests/test_exceptions.py`

### T-03: git_util.py ✅
- **参照**: design.md L76-151 (セクション 2.1)
- **成果物**:
  - `src/gfo/git_util.py` — run_git, get_remote_url, get_current_branch, get_default_branch, get_last_commit_subject, git_config_get, git_config_set, git_fetch, git_checkout_new_branch, git_clone
  - `tests/test_git_util.py` — subprocess モックによるテスト
- **依存**: T-02 (exceptions)
- **検証**: `pytest tests/test_git_util.py`

### T-04: http.py ✅
- **参照**: design.md L489-690 (セクション 2.5)
- **成果物**:
  - `src/gfo/http.py` — HttpClient クラス (get, post, put, patch, delete (※ design.md 未定義だが PR close / issue close 等に必要), get_paginated), ページネーション (Link header, page_param, response_body, offset, $top+$skip), エラーハンドリング
  - `tests/test_http.py` — responses ライブラリによるHTTPモックテスト (ページネーション含む)
- **依存**: T-02 (exceptions)
- **検証**: `pytest tests/test_http.py`

---

## Phase 2: 設定・検出・認証

### T-05: detect.py ✅
- **参照**: design.md L153-291 (セクション 2.2)
- **成果物**:
  - `src/gfo/detect.py` — detect_service, URL パース正規表現, パスパーサー, API プローブ, Backlog SSH 特殊処理
  - `tests/test_detect.py` — 全9サービスの URL パターン、API プローブ、エッジケース
- **依存**: T-03 (git_util), T-04 (http)
- **注記**: detect.py は config.py の hosts セクションを実行時に参照する (design.md L56, L62)。循環回避のため関数内 import。T-06 との相互依存に注意
- **検証**: `pytest tests/test_detect.py`

### T-06: config.py ✅
- **参照**: design.md L292-423 (セクション 2.3)
- **成果物**:
  - `src/gfo/config.py` — ProjectConfig, get_config_dir, resolve_project_config, save_project_config, get_default_host, get_default_output_format, TOML 読み書き
  - `tests/test_config.py` — tmp_path + git config モックによるテスト (Windows パス含む)
- **依存**: T-03 (git_util), T-05 (detect — 実行時依存)
- **検証**: `pytest tests/test_config.py`

### T-07: auth.py ✅
- **参照**: design.md L424-488 (セクション 2.4)
- **成果物**:
  - `src/gfo/auth.py` — resolve_token, save_token, get_auth_status, credentials.toml 管理, 環境変数フォールバック
  - `tests/test_auth.py` — tmp_path + 環境変数パッチによるテスト
- **依存**: T-06 (config)
- **検証**: `pytest tests/test_auth.py`

---

## Phase 3: アダプター基盤

### T-08: adapter/base.py — データクラス ✅
- **参照**: design.md L959-1042 (セクション 2.8 データクラス実装方針)
- **成果物**:
  - `src/gfo/adapter/base.py` (前半) — frozen dataclass: PullRequest, Issue, Repository, Release, Label, Milestone
- **依存**: なし (データクラスのみ)
- **検証**: import テスト、フィールドの不変性確認

### T-09: adapter/base.py — ABC 定義 ✅
- **参照**: design.md L1043-1173 (セクション 2.8 ABC 定義)
- **成果物**:
  - `src/gfo/adapter/base.py` (後半) — GitServiceAdapter ABC (全抽象メソッド定義)
- **依存**: T-08
- **検証**: ABC の抽象メソッド一覧確認テスト

### T-10: adapter/registry.py + output.py
- **参照**: design.md L1174-1278 (セクション 2.9), L691-757 (セクション 2.6)
- **成果物**:
  - `src/gfo/adapter/registry.py` — register_adapter, create_adapter, インポート時登録の仕組み
  - `src/gfo/output.py` — output 関数, table/json/plain フォーマッタ, dataclass→dict 変換
  - `tests/test_output.py` — 各フォーマットの出力検証
- **依存**: T-08, T-09 (base.py), T-06 (config), T-07 (auth), T-04 (http)
- **検証**: `pytest tests/test_output.py`

---

## Phase 4: アダプター実装

### T-11: GitHub アダプター
- **参照**: design.md L1282-1335 (GitHub アダプター)
- **成果物**:
  - `src/gfo/adapter/github.py` — GitHubAdapter (全メソッド実装)
  - `tests/test_adapters/conftest.py` — mock_responses, github_client 等の共通フィクスチャ
  - `tests/test_adapters/test_github.py`
- **依存**: T-09 (ABC), T-04 (http)
- **検証**: `pytest tests/test_adapters/test_github.py`

### T-12: GitLab アダプター
- **参照**: design.md L1336-1359 (GitLab アダプター)
- **成果物**:
  - `src/gfo/adapter/gitlab.py` — GitLabAdapter
  - `tests/test_adapters/test_gitlab.py`
- **依存**: T-09, T-04
- **検証**: `pytest tests/test_adapters/test_gitlab.py`

### T-13: Bitbucket Cloud アダプター
- **参照**: design.md L1361-1380 (Bitbucket Cloud アダプター)
- **成果物**:
  - `src/gfo/adapter/bitbucket.py` — BitbucketAdapter
  - `tests/test_adapters/test_bitbucket.py`
- **依存**: T-09, T-04
- **検証**: `pytest tests/test_adapters/test_bitbucket.py`

### T-14: Azure DevOps アダプター
- **参照**: design.md L1382-1459 (Azure DevOps アダプター)
- **成果物**:
  - `src/gfo/adapter/azure_devops.py` — AzureDevOpsAdapter (WIQL, JSON Patch, Basic Auth, refs/heads/ 処理)
  - `tests/test_adapters/test_azure_devops.py` — 固有テスト含む (L2166-2172)
- **依存**: T-09, T-04
- **検証**: `pytest tests/test_adapters/test_azure_devops.py`

### T-15: Gitea アダプター
- **参照**: design.md L1461-1478 (Gitea アダプター)
- **成果物**:
  - `src/gfo/adapter/gitea.py` — GiteaAdapter
  - `tests/test_adapters/test_gitea.py`
- **依存**: T-09, T-04
- **検証**: `pytest tests/test_adapters/test_gitea.py`

### T-16: Forgejo アダプター
- **参照**: design.md L1480-1487 (Forgejo アダプター)
- **成果物**:
  - `src/gfo/adapter/forgejo.py` — ForgejoAdapter (Gitea 継承、オーバーライドなし)
  - `tests/test_adapters/test_forgejo.py`
- **依存**: T-15 (Gitea)
- **検証**: `pytest tests/test_adapters/test_forgejo.py`

### T-17: Gogs アダプター
- **参照**: design.md L1489-1534 (Gogs アダプター)
- **成果物**:
  - `src/gfo/adapter/gogs.py` — GogsAdapter (Gitea 継承、PR/Label/Milestone を NotSupportedError)
  - `tests/test_adapters/test_gogs.py` — NotSupportedError テスト含む
- **依存**: T-15 (Gitea)
- **検証**: `pytest tests/test_adapters/test_gogs.py`

### T-18: GitBucket アダプター
- **参照**: design.md L1536-1548 (GitBucket アダプター)
- **成果物**:
  - `src/gfo/adapter/gitbucket.py` — GitBucketAdapter (GitHub 継承、base_url 変更)
  - `tests/test_adapters/test_gitbucket.py`
- **依存**: T-11 (GitHub)
- **検証**: `pytest tests/test_adapters/test_gitbucket.py`

### T-19: Backlog アダプター
- **参照**: design.md L1550-1644 (Backlog アダプター)
- **成果物**:
  - `src/gfo/adapter/backlog.py` — BacklogAdapter (独立実装)
  - `tests/test_adapters/test_backlog.py`
- **依存**: T-09, T-04
- **検証**: `pytest tests/test_adapters/test_backlog.py`

### T-20: adapter/__init__.py — 全アダプター登録
- **参照**: design.md L1251-1278 (各アダプターファイルでの登録, インポート時登録の仕組み)
- **成果物**:
  - `src/gfo/adapter/__init__.py` — 全9アダプターの import による登録
- **依存**: T-10 (registry), T-11〜T-19 (全アダプター)
- **検証**: `python -c "from gfo.adapter.registry import create_adapter"` で全アダプターが登録済み

---

## Phase 5: コマンド実装

### T-21: commands/pr.py
- **参照**: design.md L1648-1699 (commands 共通パターン + PR ハンドラ)
- **成果物**:
  - `src/gfo/commands/pr.py` — handle_list, handle_create, handle_view, handle_merge, handle_close, handle_checkout
  - `tests/test_commands/conftest.py` — コマンドテスト用共通フィクスチャ
  - `tests/test_commands/test_pr.py`
- **依存**: T-10 (registry, output), T-03 (git_util), T-06 (config)
- **検証**: `pytest tests/test_commands/test_pr.py`

### T-22: commands/issue.py
- **参照**: design.md L1701-1737 (issue ハンドラ)
- **成果物**:
  - `src/gfo/commands/issue.py` — handle_list, handle_create, handle_view, handle_close
  - `tests/test_commands/test_issue.py`
- **依存**: T-10, T-06
- **検証**: `pytest tests/test_commands/test_issue.py`

### T-23: commands/repo.py
- **参照**: design.md L1759-1831 (repo ハンドラ)
- **成果物**:
  - `src/gfo/commands/repo.py` — handle_list, handle_create, handle_clone, handle_view, _resolve_host_without_repo
  - `tests/test_commands/test_repo.py` — ホスト解決フローのテスト含む
- **依存**: T-10, T-03, T-05, T-06, T-07
- **検証**: `pytest tests/test_commands/test_repo.py`

### T-24: commands/init.py
- **参照**: design.md L1739-1757 (init ハンドラ)
- **成果物**:
  - `src/gfo/commands/init.py` — handle (対話モード + --non-interactive)
  - `tests/test_commands/test_init.py`
- **依存**: T-05 (detect), T-06 (config)
- **検証**: `pytest tests/test_commands/test_init.py`

### T-25: commands/auth_cmd.py
- **参照**: design.md L1833-1852 (auth_cmd ハンドラ)
- **成果物**:
  - `src/gfo/commands/auth_cmd.py` — handle_login, handle_status
  - `tests/test_commands/test_auth_cmd.py`
- **依存**: T-05 (detect), T-07 (auth)
- **検証**: `pytest tests/test_commands/test_auth_cmd.py`

### T-26: commands/release.py
- **参照**: design.md L871-883 (CLI パーサー), L948-949 (ディスパッチ), L1648-1665 (共通パターン)
- **成果物**:
  - `src/gfo/commands/release.py` — handle_list, handle_create
  - `tests/test_commands/test_release.py`
- **依存**: T-10, T-06
- **検証**: `pytest tests/test_commands/test_release.py`
- **注記**: design.md 2.11 に個別設計なし。共通パターンに従い、adapter.list_releases / adapter.create_release を呼び出す

### T-27: commands/label.py
- **参照**: design.md L885-894 (CLI パーサー), L950-951 (ディスパッチ), L1648-1665 (共通パターン)
- **成果物**:
  - `src/gfo/commands/label.py` — handle_list, handle_create
  - `tests/test_commands/test_label.py`
- **依存**: T-10, T-06
- **検証**: `pytest tests/test_commands/test_label.py`
- **注記**: design.md 2.11 に個別設計なし。共通パターンに従う

### T-28: commands/milestone.py
- **参照**: design.md L896-905 (CLI パーサー), L952-953 (ディスパッチ), L1648-1665 (共通パターン)
- **成果物**:
  - `src/gfo/commands/milestone.py` — handle_list, handle_create
  - `tests/test_commands/test_milestone.py`
- **依存**: T-10, T-06
- **検証**: `pytest tests/test_commands/test_milestone.py`
- **注記**: design.md 2.11 に個別設計なし。共通パターンに従う

---

## Phase 6: CLI 統合

### T-29: cli.py
- **参照**: design.md L759-957 (セクション 2.7)
- **成果物**:
  - `src/gfo/cli.py` — create_parser, main, _DISPATCH テーブル
  - `tests/test_cli.py` — パーサーテスト、ディスパッチテスト
- **依存**: T-21〜T-28 (全コマンド), T-06 (config — get_default_output_format)
- **検証**: `pytest tests/test_cli.py` + `gfo --help` で全サブコマンドが表示される

---

## Phase 7: テスト整備

### T-30: conftest.py 整理統合
- **参照**: design.md L2059-2141 (セクション 5.3)
- **成果物**:
  - `tests/conftest.py` — 共通フィクスチャ整理 (config_dir, mock_git_config, mock_remote_url)
  - `tests/test_commands/conftest.py` — コマンドテスト用フィクスチャ整理
  - `tests/test_adapters/conftest.py` — アダプターテスト用フィクスチャ整理
- **依存**: T-29 (全モジュール完成後)
- **検証**: `pytest` (全テスト通過)

### T-31: 全テスト実行・カバレッジ確認
- **参照**: design.md L2009-2195 (セクション 5 全体)
- **成果物**:
  - 全テストの通過確認
  - 不足テストケースの追補 (detect.py 全パターン L2145-2154, adapter 共通検証 L2156-2164, ページネーション L2174-2179, Windows 対応 L2181-2184)
- **依存**: T-30
- **検証**: `pytest --tb=short` で全テスト通過

---

## 依存関係サマリー

```
T-01 (setup)
  ├→ T-02 (exceptions)
  │    ├→ T-03 (git_util)
  │    │    └→ T-05 (detect) ←── T-04 も依存
  │    │         ├→ T-06 (config)
  │    │         │    ├→ T-07 (auth)
  │    │         │    │    └→ T-10 (registry + output) ←── T-04, T-08, T-09 も依存
  │    │         │    │         ├→ T-20 (adapter 登録)
  │    │         │    │         │    └→ T-21〜T-28 (commands)
  │    │         │    │         │         └→ T-29 (cli)
  │    │         │    │         │              └→ T-30 (conftest) → T-31 (全テスト)
  │    │         │    │         └→ T-11〜T-19 (adapters) → T-20
  │    │         │    ├→ T-24 (init cmd)
  │    │         │    └→ T-25 (auth cmd)
  │    │         └→ T-23 (repo cmd)
  │    └→ T-04 (http)
  │         └→ T-05, T-10
  └→ T-08 (base dataclass) → T-09 (base ABC)
```

**アダプター間の継承依存**:
- T-11 (GitHub) → T-18 (GitBucket)
- T-15 (Gitea) → T-16 (Forgejo), T-17 (Gogs)
