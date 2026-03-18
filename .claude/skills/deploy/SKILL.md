---
name: deploy
description: src/gfo/__init__.py のバージョンでビルド・Git タグ・PyPI 公開を行うデプロイスキル。「デプロイ」「PyPI に公開」「リリース」と言われたときに使う。
disable-model-invocation: true
allowed-tools: Bash, Read
---

## Context

- 現在のバージョン: !`python -c "from gfo import __version__; print(__version__)"`
- 現在のブランチ: !`git branch --show-current`
- 既存タグ一覧: !`git tag --sort=-v:refname | head -5`
- ワーキングツリー状態: !`git status --short`

## Your task

src/gfo/__init__.py に記載されたバージョンを使い、以下の手順でデプロイを実行する。

### 前提チェック

1. ワーキングツリーがクリーンであること（未コミットの変更がないこと）を確認する。クリーンでなければ中断してユーザーに報告する。
2. 該当バージョンのタグ（`v{version}`）がまだ存在しないことを確認する。既に存在する場合は中断してユーザーに報告する。

### デプロイ手順

1. **クリーンビルド**: `rm -rf dist/` で古い成果物を削除してから `python -m build` でパッケージをビルドする
2. **PyPI 公開**: `PYTHONIOENCODING=utf-8 twine upload dist/gfo-{version}*` で PyPI にアップロードする
3. **Git タグ作成**: `git tag v{version}` でタグを打つ
4. **Git プッシュ**: `git push origin {branch} v{version}` でコミットとタグをプッシュする

各ステップの結果をユーザーに簡潔に報告する。エラーが発生した場合はその時点で中断し、状況を報告する。
