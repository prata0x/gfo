# gfo ロードマップ — AI エージェント対応

## 背景

AI エージェント（Claude Code, GitHub Copilot, Gemini CLI 等）が CLI ツールの主要な消費者になりつつある。
gfo は `--format json` / `--jq` による構造化出力を既に備えているが、以下の領域が未整備:

- **エラー出力**: 人間向けテキストのみで、エージェントがパース困難
- **終了コード**: 0/1 の二値で、エラー種別を判別できない
- **ツール発見性**: エージェントがコマンドの入出力スキーマを事前に知る手段がない

2026 年 1〜3 月の Web 調査では、MCP サーバーよりも CLI 直接呼び出しのほうがトークン効率が高いケースが多く報告されている。
そのため、まず CLI としての機械可読性を高め、その上で MCP 対応を積み上げる戦略を取る。

## 機能一覧

| 優先度 | 機能 | 規模 | 依存 |
|--------|------|------|------|
| P1 | 構造化エラー出力 | M | なし |
| P2 | 終了コード細分化 | S | なし |
| P3 | TTY 検出による自動 JSON | S | P1 |
| P4 | `gfo schema` コマンド | M | P1 + P2 安定後 |
| P5 | MCP サーバー | L | P4 |

---

## P1: 構造化エラー出力

### 概要

`--format json` 指定時に、エラーも stderr へ JSON で出力する。

```json
{"error": "auth_failed", "message": "Authentication failed for github", "hint": "Run 'gfo auth login github'"}
```

### 設計

- `src/gfo/exceptions.py`: 各例外クラスに `error_code` プロパティを追加

  | 例外クラス | error_code |
  |-----------|------------|
  | GfoError | `general_error` |
  | AuthError / AuthenticationError | `auth_failed` |
  | NotFoundError | `not_found` |
  | RateLimitError | `rate_limited` |
  | ServerError | `server_error` |
  | NetworkError | `network_error` |
  | NotSupportedError | `not_supported` |
  | ConfigError / DetectionError | `config_error` |
  | GitCommandError | `git_error` |
  | UnsupportedServiceError | `unsupported_service` |

- `src/gfo/output.py`: `format_error_json(err)` ヘルパーを追加
  - `GfoError` を受け取り `{"error": ..., "message": ..., "hint": ...}` を返す
  - `hint` は任意フィールド（例外に `hint` 属性がある場合のみ）

- `src/gfo/cli.py`: `main()` の except ブロックで `resolved_fmt == "json"` 時に JSON エラーを stderr へ出力

### 対象ファイル

- `src/gfo/exceptions.py`
- `src/gfo/output.py`
- `src/gfo/cli.py`

### テスト

- 各例外の `error_code` プロパティが正しい値を返す
- `format_error_json()` の出力形式
- `--format json` でエラー発生時に stderr が JSON になる E2E テスト

---

## P2: 終了コード細分化

### 概要

現在の 0/1 二値を `IntEnum` ベースの `ExitCode` で細分化し、エージェントがリトライ判断や分岐に利用できるようにする。

### 設計

- `src/gfo/exceptions.py`: `ExitCode(IntEnum)` を定義

  | 名前 | 値 | 用途 |
  |------|----|------|
  | SUCCESS | 0 | 正常終了 |
  | GENERAL | 1 | 汎用エラー |
  | AUTH | 2 | 認証エラー |
  | NOT_FOUND | 3 | リソース未検出 |
  | RATE_LIMIT | 4 | レート制限 |
  | NOT_SUPPORTED | 5 | 未サポート操作 |
  | CONFIG | 6 | 設定エラー |
  | NETWORK | 7 | ネットワークエラー |

- 各例外クラスに `exit_code` プロパティを追加
- `src/gfo/cli.py`: `return 1` → `return err.exit_code`

### 対象ファイル

- `src/gfo/exceptions.py`
- `src/gfo/cli.py`

### テスト

- 各例外の `exit_code` が正しい `ExitCode` 値を返す
- `main()` が例外種別に応じた終了コードを返す

---

## P3: TTY 検出による自動 JSON

### 概要

stdout が非 TTY（パイプ先がエージェントやスクリプト）の場合、自動的に JSON 出力に切り替える。

フォーマット解決の優先順位:
1. `--format` 明示指定
2. `--jq` 指定（暗黙的に JSON）
3. `config.toml` の `default_format`
4. TTY 検出（非 TTY → JSON）

`GFO_NO_AUTO_JSON=1` 環境変数で無効化可能。

### 設計

- `src/gfo/cli.py`: フォーマット解決ロジックに TTY 判定を追加
  - `sys.stdout.isatty()` で判定
  - 環境変数 `GFO_NO_AUTO_JSON` チェック

### 対象ファイル

- `src/gfo/cli.py`

### テスト

- TTY / 非 TTY 時のフォーマット解決
- `GFO_NO_AUTO_JSON=1` でオプトアウト
- `--format text` 明示指定が TTY 検出より優先される

---

## P4: `gfo schema` コマンド

### 概要

`gfo schema pr list` のように実行すると、そのコマンドの入出力 JSON スキーマを返す。
エージェントが事前にコマンドの引数・出力形式を把握でき、ツール定義の自動生成に利用できる。

### 設計

- `src/gfo/commands/schema.py`: 新規作成
  - argparse イントロスペクションで引数スキーマを生成
  - `dataclasses.fields()` でデータクラス（PullRequest 等）の出力スキーマを生成
  - `gfo schema --list` でコマンド一覧を返す

- `src/gfo/cli.py`: schema サブコマンドのパーサー登録 + ディスパッチ追加

### 対象ファイル

- `src/gfo/commands/schema.py`（新規）
- `src/gfo/cli.py`

### テスト

- `gfo schema pr list` が有効な JSON Schema を返す
- `gfo schema --list` がコマンド一覧を返す
- 存在しないコマンドで適切なエラー

---

## P5: MCP サーバー

### 概要

gfo のアダプター層を MCP（Model Context Protocol）ツールとして公開する。
optional 依存として `pip install gfo[mcp]` でインストール可能にする。

### 設計

- `src/gfo/mcp_server.py`: 新規作成
  - P4 の schema 情報を利用してツール定義を自動生成
  - アダプター層を直接呼び出し（CLI パース不要）
  - stdio トランスポート対応

- `pyproject.toml`: optional-dependencies に `mcp` グループを追加

### 対象ファイル

- `src/gfo/mcp_server.py`（新規）
- `pyproject.toml`

### テスト

- ツール一覧が正しく生成される
- ツール呼び出し → アダプター → レスポンスのフロー
- MCP 未インストール時の graceful なエラー

---

## 実装順序

```
P1（構造化エラー出力）─┐
                       ├→ P3（自動 JSON）→ P4（schema）→ P5（MCP）
P2（終了コード細分化）─┘
```

P1 と P2 は独立して並行実装可能。P3 は P1 に依存（JSON エラー出力が前提）。
P4 は P1 + P2 が安定してから着手。P5 は P4 のスキーマ情報を前提とする。
