---
name: integration-test
description: 統合テストを実行するスキル。「統合テスト」「integration test」「セルフホストテスト」「SaaS テスト」と言われたときに使う。引数でサービスやカテゴリを絞り込める。
allowed-tools: Bash, Read, Glob, Grep
---

## Context

- Python パス: !`which python`
- Docker 状態: !`docker compose version 2>&1 | head -1`
- .env 存在確認: !`test -f tests/integration/.env && echo "exists" || echo "not found"`
- Docker Compose 稼働状況: !`docker compose -f tests/integration/docker-compose.yml ps --format "table {{.Name}}\t{{.Status}}" 2>/dev/null || echo "not running"`

## Arguments

- `$ARGUMENTS`: テスト対象の指定（省略可）
  - 省略時: セルフホスト（Docker）テストを実行
  - サービス名: `gitea`, `forgejo`, `gogs`, `gitbucket`, `github`, `gitlab`, `bitbucket`, `azure-devops`, `backlog`
  - カテゴリ: `selfhosted`（Docker 4 サービス）, `saas`（SaaS 5 サービス）
  - ファイルパス: `tests/integration/test_gitea.py`
  - pytest オプション: `-k "test_pr"` 等

## Available services

| カテゴリ | サービス | テストファイル | 備考 |
|---|---|---|---|
| selfhosted | gitea | test_gitea.py | Docker Compose |
| selfhosted | forgejo | test_forgejo.py | Docker Compose |
| selfhosted | gogs | test_gogs.py | Docker Compose |
| selfhosted | gitbucket | test_gitbucket.py | Docker Compose |
| saas | github | test_github.py | トークン必要 |
| saas | gitlab | test_gitlab.py | トークン必要 |
| saas | bitbucket | test_bitbucket.py | トークン必要 |
| saas | azure-devops | test_azure_devops.py | トークン必要 |
| saas | backlog | test_backlog.py | 有料サービス |

## Your task

統合テスト（`tests/integration/` 配下）を実行する。

### 実行手順

1. **引数の解析**: `$ARGUMENTS` を確認する
   - 引数なし → セルフホストテスト（`selfhosted` カテゴリ）を実行
   - `selfhosted` → Docker 4 サービスのテスト
   - `saas` → SaaS 5 サービスのテスト
   - サービス名（例: `gitea`）→ 該当サービスのテストのみ
   - ファイルパスや pytest オプション → そのまま渡す

2. **テスト実行**:
   ```
   python -m pytest {target} -v --no-cov
   ```
   - `selfhosted`: `python -m pytest tests/integration/ -m selfhosted -v --no-cov`
   - `saas`: `python -m pytest tests/integration/ -m saas -v --no-cov`
   - 特定サービス: `python -m pytest tests/integration/test_{service}.py -v --no-cov`
   - `--no-cov` は統合テストではカバレッジ計測が不要なため常に付与する

3. **結果報告**: テスト結果をユーザーに簡潔に報告する
   - 全テスト通過: 通過数を報告
   - 失敗あり: 失敗したテスト名とエラーメッセージの要点を報告
   - スキップされたテスト: スキップ理由があれば併記
