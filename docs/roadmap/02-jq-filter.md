# 02 jq フィルタ — JSON 出力への jq 式適用

## 1. 概要

全コマンドの `--format json` 出力に対して、jq 式でフィルタ・変換をかけるグローバルオプション。
アダプター・コマンド実装には一切手を加えず、`output.py` の出力レイヤーのみで完結する。

`gh --jq` / `glab --output-format json | jq` に相当する機能。

**前提**: `jq` コマンドが実行環境にインストール済みであること。未インストール時はわかりやすいエラーメッセージを表示する。

---

## 2. コマンド設計

```
gfo <command> [--jq EXPRESSION] [--format json]
```

`--jq` はグローバルオプションとして全サブコマンドで使用可能。

| オプション | 説明 |
|---|---|
| `--jq EXPRESSION` | jq 式を指定（`--format json` が暗黙的に有効になる） |

### 使用例

```bash
# PR 一覧からタイトルだけ抽出
gfo pr list --jq '.[].title'

# Issue のうち open のものだけ絞り込み
gfo issue list --format json --jq '[.[] | select(.state == "open")]'

# リポジトリのデフォルトブランチを確認
gfo repo view --jq '.default_branch'

# タイトルと URL を TSV 形式で出力
gfo pr list --jq '.[] | [.number, .title] | @tsv'
```

### `--jq` と `--format` の関係

- `--jq` 指定時は `--format json` を暗黙的に有効にする（`--format` の指定値に関わらず json に上書き）
- `--jq` なしの `--format json` は既存の動作と同一

---

## 3. 対応サービス

アダプター層は変更しないため、全サービス・全コマンドで共通して使用可能。

---

## 4. データモデル

変更なし。

---

## 5. アダプター抽象メソッド

変更なし。

---

## 6. 既存コードへの変更

### `src/gfo/output.py`

`apply_jq_filter` 関数を追加:

```python
import subprocess


def apply_jq_filter(json_str: str, expression: str) -> str:
    """JSON 文字列に jq 式を適用して結果を返す。

    Args:
        json_str: 入力 JSON 文字列
        expression: jq 式（例: '.[].title'）

    Returns:
        jq 適用後の文字列

    Raises:
        GfoError: jq コマンドが見つからない場合、または jq がエラーを返した場合
    """
    try:
        result = subprocess.run(
            ["jq", expression],
            input=json_str,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.rstrip("\n")
    except FileNotFoundError:
        from gfo.exceptions import GfoError
        raise GfoError(
            "jq コマンドが見つかりません。https://stedolan.github.io/jq/ からインストールしてください。"
        )
    except subprocess.CalledProcessError as e:
        from gfo.exceptions import GfoError
        raise GfoError(f"jq フィルタエラー: {e.stderr.strip()}")
```

`output()` 関数のシグネチャを拡張:

```python
def output(
    data: Any,
    *,
    fmt: str = "table",
    fields: list[str] | None = None,
    jq: str | None = None,
) -> None:
    ...
    if fmt == "json":
        json_str = format_json(items)
        if jq:
            print(apply_jq_filter(json_str, jq))
        else:
            print(json_str)
        return
    ...
```

### `src/gfo/cli.py`

グローバルパーサーに `--jq` を追加:

```python
parser.add_argument(
    "--jq",
    metavar="EXPRESSION",
    default=None,
    help="JSON 出力に jq 式でフィルタをかける（--format json を暗黙的に有効化）",
)
```

`main()` 内で `--jq` 指定時に `fmt` を `"json"` に強制:

```python
fmt = args.format
if args.jq:
    fmt = "json"  # --jq 指定時は常に json に変換（--format の指定値を上書き）
```

各コマンドハンドラへ `jq=args.jq` を渡す（`main()` 内の dispatch 呼び出しを変更）:

```python
# 変更前:
handler(args, fmt=resolved_fmt)
# 変更後:
handler(args, fmt=resolved_fmt, jq=args.jq)
```

> **注意**: 既存 cli.py は `_DISPATCH[key]` でハンドラを取得し `handler(args, fmt=resolved_fmt)` と呼ぶ。
> `args.func(...)` は使用しない。`jq` 引数追加に伴い、この 1 行を修正する。

### `src/gfo/commands/*.py`

各コマンドハンドラのシグネチャを拡張:

```python
def handle_list(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    adapter = get_adapter()
    items = adapter.list_pull_requests(...)
    output(items, fmt=fmt, fields=[...], jq=jq)
```

> **注意**: 既存の `handle_*` 関数すべてに `jq: str | None = None` を追加するため、影響範囲が広い。機械的な変更なので diff は大きいが、ロジック変更はない。
> `browse` のように JSON を出力しないコマンドでは `jq` は無効（無視する）。ハンドラのシグネチャには `jq: str | None = None` を追加するが、`output()` 呼び出しを行わないため実質影響なし。

---

## 7. テスト方針

### 単体テスト（`tests/test_output.py` 追記）

#### `apply_jq_filter` のテスト

```python
from unittest.mock import patch
import subprocess

def test_apply_jq_filter_success():
    result = apply_jq_filter('[{"name": "foo"}]', '.[].name')
    assert result == '"foo"'

def test_apply_jq_filter_jq_not_found():
    with patch("subprocess.run", side_effect=FileNotFoundError):
        with pytest.raises(GfoError, match="jq コマンドが見つかりません"):
            apply_jq_filter("[]", ".")

def test_apply_jq_filter_jq_error():
    with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "jq", stderr="parse error")):
        with pytest.raises(GfoError, match="jq フィルタエラー"):
            apply_jq_filter("{}", ".invalid??")
```

#### `output()` 関数との統合テスト

```python
def test_output_with_jq(capsys, monkeypatch):
    monkeypatch.setattr("gfo.output.apply_jq_filter", lambda s, e: '"filtered"')
    prs = [make_pr(title="foo")]
    output(prs, fmt="json", jq=".[].title")
    assert capsys.readouterr().out.strip() == '"filtered"'
```

### CLI レベルのテスト（`tests/test_cli.py` 追記）

- `--jq` 指定時に `fmt` が `"json"` に変換されることを確認（`--format` 指定値に関わらず）
- `--jq` なしでは既存の動作と同一であることを回帰テスト
