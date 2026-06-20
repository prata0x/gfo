---
name: release
description: PR 経由でリリースを一括実行する。main がクリーンか検証 → release-v<X.Y.Z> ブランチを切る → バージョン bump（__init__.py / test_cli.py / CHANGELOG 2種）→ PR 作成 → CI green 後に --merge → main のマージコミットに注釈タグ → タグ push。タグ push（v*）が release.yml をトリガーし PyPI へ自動公開する。「リリース」「リリースして」「deploy」「PyPI に公開」と言われたときに使う。
allowed-tools: AskUserQuestion, Bash, Read, Edit, Write, Glob, Grep
---

## Context

- 現在のブランチ: !`git branch --show-current`
- 既定ブランチ: !`git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "main"`
- ワーキングツリー状態: !`git status --short`
- リモート追従状態: !`git status -sb | head -1`
- 現在のバージョン (__version__): !`python -c "from gfo import __version__; print(__version__)"`
- 最新タグ (最高 semver): !`git tag --sort=-v:refname | head -1 || echo "(none)"`
- PyPI 公開済み最新版: !`curl -s https://pypi.org/pypi/gfo/json 2>/dev/null | grep -oE '"version":"[^"]*"' | head -1 | sed 's/.*:"//;s/"//' || echo "(取得不可)"`
- 最新タグ以降のコミット (参考): !`git log --oneline $(git tag --sort=-v:refname | head -1)..HEAD 2>/dev/null | head -30 || echo "(タグが履歴外のため算出不可)"`
- 直近のコミットスタイル: !`git log --oneline -10`
- gh 認証状態: !`gh auth status 2>&1 | head -3`
- 今日の日付: !`date +%Y-%m-%d`

## このスキルがやること

ローカルから手動公開するのではなく、**PR フローで bump を main に入れ、main のマージコミットにタグを打ち、その
タグ push が `.github/workflows/release.yml` を起動して PyPI へ自動公開する**、という end-to-end のリリースを行う。

CLAUDE.md の規律（main へ直接 push しない / 赤い CI をマージしない / タグは不変）を厳守する。

## 言語方針

- ユーザー向け出力（AskUserQuestion・進捗・最終報告）は会話の言語（既定は日本語）に合わせる。
- コミット / PR タイトル・本文 / タグメッセージは、リポジトリの規約（Conventional Commits・日本語 subject、
  直近 `git log` と CLAUDE.md から推定）に従う。

## Preflight（前提チェック）

以下を最初に確認する。失敗したら自動修復せず中断してユーザーに相談する。

1. **ワーキングツリーがクリーン**（`git status --short` が空）。未コミット/未追跡があれば commit / stash / 中止を相談する。
2. **既定ブランチ（main）上にいる**。release ブランチは main から切るため main 始点が必須。feature ブランチ上なら拒否し、先に作業を完了させてもらう。
3. **リモートと同期**。`git fetch origin main` 後、乖離が無いこと。behind なら `git pull --ff-only origin main`、diverged ならユーザーに相談する。
4. **`gh` CLI 認証済み**。PR の作成/マージに必須。未認証なら `gh auth login` を依頼する。
5. **衝突するブランチ/タグが無い**。`release-v<new>` ブランチと `v<new>` タグがローカル/リモート双方に存在しないこと。あれば提示して相談する。

## 手順

### 1. バージョン番号の決定

`src/gfo/__init__.py` の `__version__` と**最高 semver タグ**（`git tag --sort=-v:refname | head -1`、先頭 `v` を除去）を比較する。

> 比較に `git describe --tags --abbrev=0` を使ってはならない。describe は「HEAD から到達可能な最も近いタグ」を返すため、
> 過去に履歴を再構築してタグが main の祖先から外れていると古いタグ（実際より小さい版）を返し、判定を誤る。
> 必ず最高 semver タグで比較する。**リリース済み内容の真の基準はタグの祖先関係ではなく CHANGELOG と PyPI 公開版**である
> （タグが履歴外を指す既存リポでは「タグ以降のコミット」は当てにせず、CHANGELOG 未記載＝未リリースとして扱う）。

| 関係 | 意味 | 次の手順 |
|---|---|---|
| `__version__` == 最高タグ | bump 必要（現コードは前リリースとバージョンが同じ） | 手順 2 へ |
| `__version__` > 最高タグ | 既に main 上で bump 済み（かつ未公開）。`v<__version__>` タグが未存在なことを確認 | 手順 6（タグのみ）へスキップ |
| `__version__` < 最高タグ | 異常（作業ツリーが前リリースより古い） | 中断して報告 |
| タグ無し | 初回リリース | 現在の `__version__` をそのまま使い、タグ前に確認 |

bump レベルは **AskUserQuestion** で尋ねる（既定推奨は patch）。

| レベル | 例 | 用途 |
|---|---|---|
| **patch**（推奨） | `0.10.0` → `0.10.1` | bug fix・chore・小さなリファクタ |
| **minor** | `0.10.0` → `0.11.0` | 後方互換の新機能（`feat:` を含む） |
| **major** | `0.10.0` → `1.0.0` | 破壊的変更 |

`$ARGUMENTS` に `patch` / `minor` / `major` または `X.Y.Z` 形式が渡されていればそれを使い、尋ねずに新バージョンを確定する
（ただし確定した番号を一度だけ確認する）。最新タグ以降のコミットに `feat:` があれば minor、`fix:` のみなら patch を既定提案にする。

**この時点ではまだファイルを編集しない（先にブランチを切る）。**

### 2. release ブランチを切る

main（preflight で最新化済み）から:

```bash
git switch -c release-v<new>
```

### 3. バージョン bump（4 ファイル）と CHANGELOG 作成

release ブランチ上で以下 4 ファイルを更新する。CHANGELOG の中身は最新タグ以降のコミットを分類して書く
（`feat:`→Added/追加、`fix:`→Fixed/修正、`test:`→Tests/テスト、その他で価値あるもの→Other/その他。
`docs:`/`chore:` 単独は原則含めない）。英語版と日本語版は項目数・順序を一致させる。

- **`src/gfo/__init__.py`**: `__version__` を新バージョンに更新。
- **`tests/test_cli.py`**: `gfo {旧バージョン}` を含むアサーションを `gfo {新バージョン}` に置換。
- **`CHANGELOG.md`（英語）**: `# Changelog` 直後（最初の `## [...]` の前）に新セクションを挿入。

  ```markdown
  ## [X.Y.Z] - YYYY-MM-DD

  ### Added
  - ...

  ### Fixed
  - ...
  ```

- **`CHANGELOG.ja.md`（日本語）**: `# 変更履歴` 直後に対応する新セクションを挿入（`### 追加` / `### 修正`）。

CHANGELOG のエントリは具体的なコマンド名・オプション名を含め、ユーザーが何が変わったか分かるように書く。

> 注: CHANGELOG だけ先に整えたい場合は `bump-version` スキルが同じ編集を単体で行う。release スキルは
> bump からタグ push までを一気通貫で行うため、ここでは編集を内包している。

### 4. bump コミット

```bash
git add src/gfo/__init__.py tests/test_cli.py CHANGELOG.md CHANGELOG.ja.md
git commit -m "chore(release): バージョン <new> リリース準備"
```

実際に変わったファイルだけをステージする（`git add -A` は使わない）。既存 release ブランチで両方とも
編集済みなら本ステップはスキップ。

### 5. release ブランチを push して PR を作成

```bash
git push -u origin release-v<new>
gh pr create \
  --base main \
  --head release-v<new> \
  --title "chore(release): v<new>" \
  --body "$(cat <<'EOF'
## このリリースに含まれる変更

<CHANGELOG の新セクションと同じ箇条書き>

## メモ

- 前タグ: v<previous>
- merge 後、main HEAD に v<new> タグを打つと release.yml が PyPI へ自動公開する
EOF
)"
```

### 6. CI green を待ってマージ

```bash
gh pr checks <pr-number> --watch
```

必須チェック `ci`（Ruleset）が green になるまで待つ。失敗時は **バイパスしない**。原因を release ブランチで
修正（コミット追加）するか、リリースを中止（`gh pr close <pr-number> --delete-branch`）してユーザーに相談する。

green になったら:

```bash
gh pr merge <pr-number> --merge --delete-branch
```

**`--merge` 固定**（このリポは squash / rebase マージを無効化している。`--squash` / `--rebase` は使わない）。

### 7. main を取得してタグを作成・push

マージ後、main HEAD はマージコミットになる。ローカル main を同期し、その HEAD に注釈タグを打つ:

```bash
git switch main
git pull --ff-only origin main
git tag -a v<new> -m "<タグメッセージ>"
git push origin v<new>
```

- タグメッセージは `git log --no-merges --oneline <last-tag>..HEAD` から要約（単一テーマなら命名、
  複数なら `Release v<new>`、いずれもリポ言語）。
- **タグ push がリリースの不可逆点**。release.yml（`push` tags `v*`）が起動し PyPI へ公開される。
  このスキルの起動自体が最終 push の同意とみなすが、途中で想定外（PR コンフリクト・CI flaky・force 要求等）が
  あれば push 前に一旦止めて確認する。
- **main を直接 push しない**（main はマージで更新済み）。push するのはタグのみ。

### 8. 検証と報告

```bash
git log -1 --oneline origin/main
git ls-remote --tags origin "v<new>"
gh run list --workflow=release.yml --limit 3
```

ユーザーへ報告する内容:

- 新バージョン / タグ名
- release.yml（`.github/workflows/release.yml`、trigger: タグ push `v*`）が起動し PyPI 公開が走ること
- 監視先（GitHub Actions の URL は `git remote get-url origin` から導出）と PyPI プロジェクト URL
- マージ済みリリース PR へのリンク

## ガードレール

- **main へ直接 push しない / force-push しない**。bump は必ず PR + `--merge`。
- **タグを書き換えない**。`v*` は不変。リリースが不良なら次バージョンで前進修正する。
- **`--squash` / `--rebase` を使わない**（このリポは無効）。
- **赤い CI をマージしない**。
- **秘密情報を出さない**（public リポ）。PyPI 公開は release.yml の Trusted Publishing（OIDC）で行われ、
  トークンは扱わない。ローカルでの `twine upload` はもう行わない。
- 依存を変えていないリリースでも、CI が `uv.lock` 整合を検証する点に留意する。

## PyPI 側の前提（初回のみ）

release.yml は API トークンを使わず PyPI Trusted Publishing（OIDC）で公開する。事前に PyPI 側で当該リポジトリの
Trusted Publisher を一度登録しておく必要がある（workflow 名 `release.yml`、environment 名 `pypi`）。未登録だと
publish step が認可エラーで落ちる。登録済みなら以降のリリースで追加設定は不要。
