---
name: test
description: 単体テストを実行するスキル。「テスト」「テスト実行」「test」と言われたときに使う。引数でテスト対象を絞り込める。
allowed-tools: Bash, Read, Glob, Grep
---

## Context

- Python パス: !`which python`
- pytest バージョン: !`python -m pytest --version 2>&1 | head -1`
- テスト総数: !`python -m pytest --collect-only -q 2>/dev/null | tail -1`
- ワーキングツリー状態: !`git status --short`

## Arguments

- `$ARGUMENTS`: テスト対象の指定（省略可）
  - 省略時: 全単体テストを実行
  - ファイルパス: `tests/test_commands/test_pr.py`
  - テストクラスやテスト関数: `tests/test_commands/test_pr.py::TestPrList`
  - キーワード: `-k "test_create"` 形式

## Your task

単体テスト（`tests/` 配下、`tests/integration/` を除く）を実行する。

### 実行手順

1. **引数の解析**: `$ARGUMENTS` を確認する
   - 引数なし → `python -m pytest --ignore=tests/integration -v`
   - ファイルやキーワード指定あり → そのまま pytest に渡す

2. **テスト実行**: 以下のコマンドで実行する
   ```
   python -m pytest {target} -v
   ```
   - `{target}` は引数から構築する
   - `tests/integration/` は常に除外する（引数で明示的に指定された場合を除く）

3. **結果報告**: テスト結果をユーザーに簡潔に報告する
   - 全テスト通過: 通過数を報告
   - 失敗あり: 失敗したテスト名とエラーメッセージの要点を報告
   - エラーが大量にある場合は、パターンを要約して全件列挙は避ける
