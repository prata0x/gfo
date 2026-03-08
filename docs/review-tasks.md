# レビュー修正タスクリスト

レビューで検出された問題の修正タスク。docs/tasks.md (T-01〜T-31) とは別管理。
タスク番号は R-01〜 (Review) とする。

---

## Phase R-A: バグ修正

### R-01: detect.py — scheme 判定デッドコード修正 ✅

- **問題**: `detect_service()` 内の scheme 条件分岐が両方 `"https"` を返すバグ
- **参照**: @docs/design.md L197-210 (detect_service フロー), L182-195 (probe_unknown_host の scheme パラメータ)
- **修正箇所**:
  - `src/gfo/detect.py:257` — `else "https"` → `else "http"`
- **テスト**:
  - `tests/test_detect.py` — HTTP remote URL でプローブ時に `scheme="http"` が渡されることを検証するテスト追加
- **検証**: `pytest tests/test_detect.py -v`

---

## Phase R-B: コード品質改善

### R-02: HttpClient 生成ロジックの共通化 ✅

- **問題**: `commands/repo.py:74-104` と `adapter/registry.py:29-77` に HttpClient 生成の service_type 分岐が重複。更新漏れリスクあり
- **参照**: @docs/design.md L1208-1248 (create_adapter), L1789-1798 (handle_create)
- **修正箇所**:
  - `src/gfo/adapter/registry.py` — `create_http_client(service_type: str, api_url: str, token: str) -> HttpClient` ファクトリ関数を追加。`create_adapter()` 内の HttpClient 生成を新関数に委譲
  - `src/gfo/commands/repo.py:74-104` — `handle_create()` 内の HttpClient 生成を `create_http_client()` 呼び出しに置換
- **テスト**:
  - `tests/test_registry.py` — `create_http_client()` の各 service_type に対するテスト追加
  - 既存テストが引き続きパスすることを確認
- **検証**: `pytest tests/test_registry.py tests/test_commands/test_repo.py -v`

### R-03: config.py ⇔ detect.py 相互遅延インポートの整理 ✅

- **問題**: `config.py` が `detect.py` を、`detect.py` が `config.py` を関数内 import で相互参照。循環依存の兆候
- **参照**: @docs/design.md L62 (循環回避の設計方針), L292-295 (config.py の責務), L345-360 (resolve_project_config)
- **修正箇所**:
  - `src/gfo/detect.py:247` — `import gfo.config` の遅延インポートを確認。detect.py が必要とする config 情報（hosts テーブル）を引数として受け取る設計に変更可能か検討
  - 現状動作しているため、遅延インポート箇所にコメントで循環依存の理由を明記する最小修正とする
- **テスト**: 既存テストのパスを確認
- **検証**: `pytest tests/test_detect.py tests/test_config.py -v`

---

## Phase R-C: テストカバレッジ強化

### R-04: adapter/forgejo.py のテスト強化

- **問題**: 7テストのみ。GiteaAdapter 継承だが差分メソッドのテストが不足の可能性
- **参照**: @docs/design.md L1480-1487 (Forgejo アダプター設計), L1866 (継承関係), L1882 (継承共有ロジック), L2156-2164 (adapter テスト方針)
- **修正箇所**:
  - `tests/test_adapters/test_forgejo.py` — service_name 確認、Gitea API との互換性テスト、エラーケース追加
- **検証**: `pytest tests/test_adapters/test_forgejo.py -v`

### R-05: adapter/gitbucket.py のテスト強化

- **問題**: 7テストのみ。GitHubAdapter 継承だが差分メソッドのテストが不足の可能性
- **参照**: @docs/design.md L1536-1548 (GitBucket アダプター設計), L1861 (継承関係), L1881 (継承共有ロジック), L2156-2164 (adapter テスト方針)
- **修正箇所**:
  - `tests/test_adapters/test_gitbucket.py` — base_url 差異の検証、GitHub API 互換パス構造テスト、エラーケース追加
- **検証**: `pytest tests/test_adapters/test_gitbucket.py -v`

### R-06: commands/auth_cmd.py のテスト強化

- **問題**: 6テストのみ。エラーケースのテストが不足
- **参照**: @docs/design.md L1833-1851 (auth_cmd ハンドラ設計)
- **修正箇所**:
  - `tests/test_commands/test_auth_cmd.py` — トークン未設定時のエラー、無効ホストのエラー、`--token` オプション警告、status コマンドの各状態テスト追加
- **検証**: `pytest tests/test_commands/test_auth_cmd.py -v`

### R-07: commands/label.py のテスト強化

- **問題**: 5テストのみ。他コマンド (pr:14, issue:14) と比較して少ない
- **参照**: @docs/design.md L885-894 (label CLI パーサー), L950-951 (ディスパッチ), L1648-1664 (コマンド共通パターン)
- **修正箇所**:
  - `tests/test_commands/test_label.py` — list のフォーマット出力テスト、create のエラーケース、引数バリデーション追加
- **検証**: `pytest tests/test_commands/test_label.py -v`

### R-08: commands/milestone.py のテスト強化

- **問題**: 6テストのみ。label と同様に少ない
- **参照**: @docs/design.md L896-905 (milestone CLI パーサー), L952-953 (ディスパッチ), L1648-1664 (コマンド共通パターン)
- **修正箇所**:
  - `tests/test_commands/test_milestone.py` — list のフォーマット出力テスト、create のエラーケース、引数バリデーション追加
- **検証**: `pytest tests/test_commands/test_milestone.py -v`

---

## Phase R-D: インフラ整備

### R-09: pytest-cov 導入・カバレッジ計測設定

- **問題**: カバレッジ計測が未設定で実際のカバレッジ率が不明
- **参照**: @docs/design.md L2186-2195 (開発依存)
- **修正箇所**:
  - `pyproject.toml` — `[project.optional-dependencies]` の `dev` に `pytest-cov` を追加
  - `pyproject.toml` — `[tool.pytest.ini_options]` に `addopts = "--cov=gfo --cov-report=term-missing"` を追加
- **検証**: `pytest` 実行時にカバレッジレポートが出力されることを確認

### R-10: GitHub Actions CI ワークフロー追加

- **問題**: CI/CD 設定がなく、テストの自動実行環境が未構築
- **参照**: @docs/design.md にCI/CDセクションは未記載（新規追加）
- **修正箇所**:
  - `.github/workflows/ci.yml` — Python 3.11+ での pytest 実行、push/PR トリガー
- **検証**: `act` またはローカルでワークフロー YAML の構文確認

---

## 実行順序

依存関係を考慮した推奨順序:

1. **R-01** (バグ修正 — 最優先)
2. **R-02** (HttpClient 共通化 — R-03 の前提整理)
3. **R-03** (循環インポート整理)
4. **R-04〜R-08** (テスト強化 — 並行可能)
5. **R-09** (pytest-cov — テスト強化後に導入)
6. **R-10** (CI — 最後に追加)

## 全体検証

全タスク完了後: `pytest --tb=short -q` で全テストパス + カバレッジレポート確認
