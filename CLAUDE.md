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

## 言語方針

- 応答・コミットメッセージ・docs・issue/PR 本文は**日本語**。
- コード識別子・shell・YAML キー・型・コメント中の技術語は英語。

---

## 技術スタック

- **ランタイム依存**: `requests` のみ
- **開発依存**（`[dependency-groups]` で管理）: `pytest`, `responses`（HTTP モック）, `pytest-cov`, `ruff`, `bandit`, `mypy`, `types-requests`, `pre-commit`
- **ビルド**: `hatchling`（バージョンは `src/gfo/__init__.py`）
- **toolchain**: `mise`（python / uv を pin）+ `uv`（依存解決・`uv.lock` で frozen install）

---

## 開発環境（WSL / Linux）

開発は WSL(Ubuntu) で行う。**`python` コマンドは存在せず `python3` のみ**のため、`mise` の auto-venv で `.venv` を有効化して `python` を成立させる。

```bash
# 初回セットアップ（mise が python + uv を供給し、.venv を自動作成）
mise install
uv sync            # dependency-groups の dev も既定でインストールされる

# 以降は uv run 経由でツールを実行する（`python -m ...` は使わない）
uv run pytest                       # 単体テスト（カバレッジ付き・統合テストは自動除外）
uv run pytest tests/test_commands/test_pr.py -v   # 特定テスト
uv run ruff check .                 # lint
uv run ruff format .                # format
uv run mypy src/gfo                 # 型チェック
uv run bandit -r src/gfo -c pyproject.toml   # セキュリティ

# pre-commit（フックは uv run 経由で動く）
uv run pre-commit install
```

- `uv.lock` は hash 付きで commit する。依存を変えたら `uv lock` で更新し lock も同じ PR に含める。
- CI は `uv sync --locked` で lock 整合を強制する（lock が古いと fail）。

---

## CI / サプライチェーン

- **CI**: `.github/workflows/ci.yml`。gfo は **public リポジトリで GitHub Actions が無料のため、全ジョブを GitHub-hosted `ubuntu-latest` で実行**（self-hosted は使わない）。
  - 内容: ruff（lint）+ ruff format --check + mypy + bandit + pytest。
  - **統合テストは CI で実行しない**（実サービスへアクセスするため）。pytest 設定（`pyproject.toml` の `addopts` に `--ignore=tests/integration`）で除外済み。
  - ハードニング: `permissions: contents: read` / `persist-credentials: false` / 各 action は 40桁 commit SHA で pin + 「SHA pin されているか」自己検証 step。
- **Dependabot**: `.github/dependabot.yml`。`uv` + `github-actions` を週次（月曜 06:00 JST）。`cooldown: 7日` でリリース直後の新版を隔離（供給網対策）。CI が通った PR だけマージする。
- public リポジトリのため**秘密情報・トークン・内部 URL 等は一切コミット/issue/PR に出さない**。

---

## ワークフロー（規律）

GitHub Rules（`main` ブランチ保護・リリースタグ保護）は free プランでは実効しないが、**規律として遵守する**。

- **`main` へ直接 commit / push・force-push しない。** 必ず feature branch を切る（`git switch -c <kebab>`）→ commit → push → `gh pr create --base main` → **CI green を確認して self-merge**（squash）。
- **赤い CI はマージしない。**
- 問題を見つけたら **issue を起票** してから着手する。
- リリースタグ（保護対象）を勝手に作成・移動・削除しない。
- branch への commit / push・PR 作成・**CI green 後の self-merge** は通常運用＝確認不要。

---

## Do / Don't

- **Do**: feature branch → PR → CI green → self-merge。依存変更は `uv lock` を同 PR に含める。action は SHA pin。秘密は出さない。
- **Don't**: `main` へ直接 push / force-push。赤い CI のマージ。秘密情報のコミット。lock を伴わない依存変更。SHA pin されていない action の追加。

---

## 確認が必要な操作

新規依存の追加、認証方式の変更、破壊的な操作（リモートのリリース/タグ削除等）、外部サービス連携。**`main` への直接 push / force-push は禁止**（feature branch + PR で代替）。

---

## コミット規約

Conventional Commits（日本語 subject、header ≤72 目安）。scope 例: `cli, adapter, github, gitlab, pr, issue, release, http, config, auth, ci, deps, docs`。

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
└── commands/             # 30+ サブコマンドモジュール
    ├── init.py / auth_cmd.py / config_cmd.py / completion.py
    ├── pr.py / issue.py / issue_template.py / comment.py / review.py
    ├── repo.py / release.py / label.py / milestone.py / wiki.py
    ├── branch.py / branch_protect.py / tag.py / tag_protect.py / file.py
    ├── webhook.py / deploy_key.py / ssh_key.py / gpg_key.py / collaborator.py
    ├── ci.py / status.py / search.py / org.py / user.py / notification.py
    ├── secret.py / variable.py / package.py / browse.py
    ├── api.py / batch.py / schema.py

tests/
├── conftest.py / test_adapter_base.py / test_auth.py / test_cli.py / test_config.py
├── test_adapters/       # アダプターごとのテスト
├── test_commands/       # コマンドごとのテスト（make_args() ヘルパー）
└── integration/         # 実サービスへアクセスする統合テスト（CI 非対象）
```

詳細なルール・規約は `.claude/rules/` を参照:
- `01-exceptions.md` — 例外体系と使い分け
- `02-adapter-common.md` — アダプター共通規約
- `03-github.md` 〜 `08-gitea-family.md` — サービス別固有ルール
- `09-config-auth.md` — 設定・認証
- `10-testing.md` — テスト規約
