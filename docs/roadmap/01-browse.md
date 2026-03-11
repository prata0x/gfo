# 01 browse — リポジトリ・PR・Issue をブラウザで開く

## 1. 概要

`gfo browse` は、現在のリポジトリ・PR・Issue の URL をデフォルトブラウザで開くコマンド。
`webbrowser.open()` を使用するため **API 呼び出し不要**。URL 構築ロジックのみ実装する。

`gh browse` / `glab browse` に相当するが、gfo は全 9 サービスに対応する点が差別化要因。

---

## 2. コマンド設計

```
gfo browse [--pr N | --issue N | --settings] [--print]
```

| オプション | 説明 |
|---|---|
| （なし） | リポジトリトップページを開く |
| `--pr N` | PR #N のページを開く |
| `--issue N` | Issue #N のページを開く |
| `--settings` | リポジトリ設定ページを開く |
| `--print` | ブラウザを開かず URL を標準出力に表示する（スクリプト向け） |

### 使用例

```bash
gfo browse                     # リポジトリトップを開く
gfo browse --pr 42             # PR #42 を開く
gfo browse --issue 7           # Issue #7 を開く
gfo browse --settings          # 設定ページを開く
gfo browse --pr 42 --print     # URL を表示するだけ（ブラウザは開かない）
```

---

## 3. 対応サービス

全 9 サービス対応。URL パターンのみ異なる。

| サービス | リポジトリ URL パターン | PR | Issue | Settings |
|---|---|---|---|---|
| GitHub | `https://github.com/{owner}/{repo}` | `/pull/{n}` | `/issues/{n}` | `/settings` |
| GitLab | `https://gitlab.com/{owner}/{repo}` | `/-/merge_requests/{n}` | `/-/issues/{n}` | `/-/settings/general` |
| Bitbucket | `https://bitbucket.org/{owner}/{repo}` | `/pull-requests/{n}` | `/issues/{n}` | `/admin` |
| Azure DevOps | `https://dev.azure.com/{org}/{project}/_git/{repo}` | `/pullrequest/{n}` | `/workitems?id={n}` | `/_settings/repositories` |
| Gitea | `{base_url}/{owner}/{repo}` | `/pulls/{n}` | `/issues/{n}` | `/settings` |
| Forgejo | `{base_url}/{owner}/{repo}` | `/pulls/{n}` | `/issues/{n}` | `/settings` |
| Gogs | `{base_url}/{owner}/{repo}` | `/pulls/{n}` | `/issues/{n}` | `/settings` |
| GitBucket | `{base_url}/{owner}/{repo}` | `/pulls/{n}` | `/issues/{n}` | `/settings` |
| Backlog | `https://{space}.backlog.jp/git/{projectKey}/{repo}` | `/pullRequests/{n}` | — | — |

> **注意**: Backlog の Issue キーは `PROJ-123` のような文字列形式であり、`--issue N`（整数）では表現できない。
> Backlog アダプターの `get_web_url` では `resource="issue"` に対して `NotSupportedError` を送出する。

---

## 4. データモデル

新規データクラスは不要。URL は `str` として直接返す。

---

## 5. アダプター抽象メソッド

`base.py` の `GitServiceAdapter` に以下を追加する:

```python
def get_web_url(self, resource: str = "repo", number: int | None = None) -> str:
    """Web ブラウザで開くための URL を返す。

    Args:
        resource: "repo" | "pr" | "issue" | "settings"
        number: PR / Issue 番号（resource が "pr" / "issue" の場合に必須）

    Returns:
        完全な URL 文字列
    """
    raise NotSupportedError(self.service_name, "browse")
```

各アダプターがサービス固有の URL 構築ロジックを実装する。
API 呼び出しは発生しないため、HTTP クライアントは使用しない。

---

## 6. 既存コードへの変更

### 新規ファイル

#### `src/gfo/commands/browse.py`

```python
"""gfo browse サブコマンドのハンドラ。"""

import webbrowser
from gfo.commands import get_adapter


def handle_browse(args, *, fmt: str) -> None:
    adapter = get_adapter()
    resource = "repo"
    number = None
    if args.pr is not None:
        resource, number = "pr", args.pr
    elif args.issue is not None:
        resource, number = "issue", args.issue
    elif args.settings:
        resource = "settings"

    url = adapter.get_web_url(resource, number)

    if args.print:
        print(url)
    else:
        webbrowser.open(url)
```

### 変更ファイル

#### `src/gfo/cli.py`

`deploy-key` と同様のパターンで `browse` サブパーサーを追加:

```python
# browse（サブコマンドなし。create_parser() 内の subparsers.add_parser で追加）
browse_parser = subparser_map["browse"] = subparsers.add_parser("browse", help="リポジトリをブラウザで開く")
_browse_group = browse_parser.add_mutually_exclusive_group()
_browse_group.add_argument("--pr", type=int, metavar="N", help="PR 番号")
_browse_group.add_argument("--issue", type=int, metavar="N", help="Issue 番号")
_browse_group.add_argument("--settings", action="store_true", help="設定ページを開く")
browse_parser.add_argument("--print", action="store_true", help="URL を表示するだけ")
```

`_DISPATCH` に以下を追加（`browse` はサブコマンドなしのため `None` キー）:

```python
("browse", None): gfo.commands.browse.handle_browse,
```

> **注意**: 既存 cli.py は `set_defaults(func=...)` パターンではなく `_DISPATCH` 辞書でディスパッチする。
> `browse` のように単一ハンドラのコマンドはキー `(command, None)` で登録する。

#### `src/gfo/adapter/*.py`

各アダプターに `get_web_url` メソッドを実装する。
`base.py` のデフォルト実装は `NotSupportedError` を送出するため、対応しないサービスは実装不要。

---

## 7. テスト方針

### アダプター単体テスト（HTTP モック不要）

`get_web_url` は API 呼び出しを行わないため、`tests/test_adapters/` にサービスごとのテストを作成する:

- `tests/test_adapters/test_github_browse.py` 等、各アダプターに対応するファイル
- `resource="repo"` / `resource="pr"` / `resource="issue"` / `resource="settings"` のケースを網羅
- Azure DevOps・Backlog 固有の URL 形式を個別検証（Azure DevOps の `_git` パス、Backlog の `--issue` → `NotSupportedError`）

### コマンドハンドラのテスト

`tests/test_commands/test_browse.py` に `webbrowser.open` モックを使ったテストを配置:

### `webbrowser.open` のモック

```python
from unittest.mock import patch

def test_browse_opens_browser(mock_adapter):
    with patch("webbrowser.open") as mock_open:
        handle_browse(args, fmt="table")
        mock_open.assert_called_once_with("https://github.com/owner/repo")
```

### `--print` フラグのテスト

```python
def test_browse_print(capsys, mock_adapter):
    handle_browse(args_with_print, fmt="table")
    assert capsys.readouterr().out.strip() == "https://github.com/owner/repo"
```

### 統合テスト

Docker Compose 環境では `--print` フラグのみ使用し、実際のブラウザ起動は行わない。
