# add-web-option

## 概要

`--web` / `-w` オプションを追加し、対象リソースをブラウザで開けるようにする。
gh / glab はいずれもサブコマンドに `--web` オプションを提供しており、gfo もこれに合わせる。

- **種別**: 機能追加
- **優先度**: Phase 2（独立して実施可能）

## 変更後

```
gfo pr view 42 --web       # PR #42 をブラウザで開く
gfo issue view 10 --web    # Issue #10 をブラウザで開く
gfo pr list --web          # PR 一覧をブラウザで開く
gfo repo view --web        # リポジトリページをブラウザで開く
```

## 対象サブコマンド

- `pr view`, `pr list`
- `issue view`, `issue list`
- `repo view`
- `release view`
- `milestone view`

## 実装手順

### 1. CLI パーサー定義 (`src/gfo/cli.py`)

対象の各サブコマンドパーサーに `--web` / `-w` を追加:

```python
pr_view.add_argument("--web", "-w", action="store_true", help=_("Open in browser"))
pr_list.add_argument("--web", "-w", action="store_true", help=_("Open in browser"))
issue_view.add_argument("--web", "-w", action="store_true", help=_("Open in browser"))
issue_list.add_argument("--web", "-w", action="store_true", help=_("Open in browser"))
repo_view.add_argument("--web", "-w", action="store_true", help=_("Open in browser"))
release_view.add_argument("--web", "-w", action="store_true", help=_("Open in browser"))
milestone_view.add_argument("--web", "-w", action="store_true", help=_("Open in browser"))
```

### 2. アダプター基底クラス (`src/gfo/adapter/base.py`)

既存の `get_web_url` メソッドを確認（`browse` コマンドで使用済み）。
リソース種別ごとの Web URL 生成が必要な場合は拡張:

```python
def get_web_url(self, resource: str = "", number: int | str | None = None) -> str:
    """リソースの Web URL を返す。"""
    ...
```

### 3. コマンドハンドラー修正

各 `handle_view` / `handle_list` の先頭で `--web` チェックを追加:

```python
import webbrowser

def handle_view(args, *, fmt, jq=None):
    if getattr(args, "web", False):
        adapter = get_adapter()
        url = adapter.get_web_url("pr", args.number)
        webbrowser.open(url)
        return
    # 既存の処理
    ...
```

### 4. テスト

- 各コマンドの view テストに `--web` フラグのテストを追加
- `webbrowser.open` をモックして URL 確認
- `get_web_url` のリソース種別ごとの URL 生成をテスト

### 5. ドキュメント更新

- `docs/commands.md` / `.ja.md`: 各対象コマンドに `--web` オプションを追記
- `docs/cli-comparison.md`: セクション 2 グローバルオプション比較表の gfo 列を更新
- `docs/cli-alignment.md`: 完了後にステータス更新
