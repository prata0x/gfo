---
name: bump-version
description: バージョンアップスキル。CHANGELOG 追記・バージョン番号更新・コミットまでを一括で行う。「バージョンアップ」「bump」と言われたときに使う。
allowed-tools: Bash, Read, Edit, Write, Glob, Grep
---

## Context

- 現在のバージョン: !`python -c "from gfo import __version__; print(__version__)"`
- 現在のブランチ: !`git branch --show-current`
- 既存タグ一覧: !`git tag --sort=-v:refname | head -5`
- ワーキングツリー状態: !`git status --short`
- 今日の日付: !`date +%Y-%m-%d`

## Arguments

- `$ARGUMENTS`: バージョンやコミット範囲の指定（省略可）
  - 例: `0.6.0` — バージョンのみ指定
  - 例: `0.6.0 v0.4.0..HEAD` — バージョンとコミット範囲を指定
  - 例: `abc1234..def5678` — コミット範囲のみ指定（バージョンは自動判定）
  - 省略時: 前バージョンタグの次から HEAD まで、バージョンは自動判定

## Your task

バージョンアップに必要なファイル更新とコミットを一括で行う。

### 1. パラメータの決定

#### コミット範囲

`$ARGUMENTS` に `..` を含む文字列があればコミット範囲として使う。
なければ、最新タグから HEAD までを使う:
```bash
git log $(git describe --tags --abbrev=0)..HEAD --oneline
```

#### バージョン番号

`$ARGUMENTS` にセマンティックバージョニング形式（`X.Y.Z`）の文字列があればそれを新バージョンとする。

なければ、コミット範囲の内容から自動判定する:
- **MINOR** (Y+1): `feat:` コミットが含まれる場合
- **PATCH** (Z+1): `fix:` のみの場合
- 判断に迷う場合はユーザーに確認する

### 2. コミット内容の分析

コミットログを取得し、以下のカテゴリに分類する:
- **Added** / **追加**: `feat:` コミット
- **Fixed** / **修正**: `fix:` コミット
- **Tests** / **テスト**: `test:` コミット
- **Other** / **その他**: 上記以外で CHANGELOG に載せる価値があるもの

`docs:` や `chore:` のみのコミットは原則 CHANGELOG に含めないが、ユーザー向けドキュメント更新など重要なものは含める。

### 3. ファイル更新

以下の 4 ファイルを更新する:

#### `src/gfo/__init__.py`
- `__version__` を新バージョンに更新

#### `tests/test_cli.py`
- `gfo {旧バージョン}` を含むアサーションを `gfo {新バージョン}` に置換

#### `CHANGELOG.md`（英語）
- `# Changelog` の直後（最初の `## [...]` の前）に新バージョンのセクションを挿入
- 形式:
  ```markdown
  ## [X.Y.Z] - YYYY-MM-DD

  ### Added
  - ...

  ### Fixed
  - ...
  ```

#### `CHANGELOG.ja.md`（日本語）
- `# 変更履歴` の直後（最初の `## [...]` の前）に新バージョンのセクションを挿入
- 形式:
  ```markdown
  ## [X.Y.Z] - YYYY-MM-DD

  ### 追加
  - ...

  ### 修正
  - ...
  ```

### 4. コミット

更新した 4 ファイルをステージしてコミットする:
```bash
git add src/gfo/__init__.py tests/test_cli.py CHANGELOG.md CHANGELOG.ja.md
git commit -m "chore: バージョン X.Y.Z リリース準備"
```

### 注意事項

- CHANGELOG のエントリは具体的なコマンド名・オプション名を含め、ユーザーが何が変わったか分かるように書く
- 英語版と日本語版の内容は対応させる（項目数・順序を一致させる）
- コミット範囲にコミットがない場合は中断してユーザーに報告する
