# gfo – Git Forge Operator

複数の Git ホスティングサービスを**統一コマンド**で操作する Python CLI ツール。

## プロジェクト概要

| 項目 | 内容 |
|---|---|
| パッケージ名 | `gfo` |
| エントリポイント | `gfo.cli:main` |
| 対象 Python | 3.11 以上 |
| ライセンス | 0BSD |

### 対応サービス

| サービス | 識別子 | 認証環境変数 |
|---|---|---|
| GitHub | `github` | `GITHUB_TOKEN` |
| GitLab | `gitlab` | `GITLAB_TOKEN` |
| Bitbucket Cloud | `bitbucket` | `BITBUCKET_TOKEN`（`email:api-token` 形式） |
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
├── cli.py / auth.py / config.py / detect.py / exceptions.py
├── git_util.py / http.py / output.py
├── adapter/
│   ├── base.py          # 抽象基底クラス + データクラス定義
│   ├── registry.py      # @register デコレータ, create_adapter()
│   ├── github.py / gitlab.py / bitbucket.py / azure_devops.py
│   ├── backlog.py / gitea.py / forgejo.py / gogs.py / gitbucket.py
└── commands/
    ├── init.py / auth_cmd.py / pr.py / issue.py
    ├── repo.py / release.py / label.py / milestone.py
    ├── package.py
    └── schema.py

tests/
├── conftest.py / test_adapter_base.py / test_auth.py / test_cli.py / test_config.py
├── test_adapters/       # アダプターごとのテスト
└── test_commands/       # コマンドごとのテスト（make_args() ヘルパー）
```

詳細なルール・規約は `.claude/rules/` を参照:
- `01-exceptions.md` — 例外体系と使い分け
- `02-adapter-common.md` — アダプター共通規約
- `03-github.md` 〜 `08-gitea-family.md` — サービス別固有ルール
- `09-config-auth.md` — 設定・認証
- `10-testing.md` — テスト規約

---

## 開発コマンド

```bash
# インストール（開発モード）
pip install -e ".[dev]"

# テスト実行（カバレッジ付き）
pytest

# 特定テストの実行
pytest tests/test_commands/test_pr.py -v
```

カバレッジ: 2552 テスト、88%
