# 04 Organization 管理 — 所属組織の一覧・詳細・メンバー・リポジトリ

## 1. 概要

認証ユーザーが所属する組織（Organization）の一覧取得、組織詳細表示、メンバー一覧、組織リポジトリ一覧を提供するコマンド。

`gh org list` / `glab group list` に相当する機能。
gfo では統一コマンド `gfo org` として提供し、サービスごとの命名差異（Organization / Group / Team）を吸収する。

---

## 2. コマンド設計

```
gfo org {list,view,members,repos}
```

### `gfo org list`

```
gfo org list [--limit N]
```

認証ユーザーが所属する組織の一覧を表示する。

### `gfo org view`

```
gfo org view <name>
```

| 引数 | 説明 |
|---|---|
| `name` | 組織名（または GitLab の場合はグループの full_path） |

### `gfo org members`

```
gfo org members <name> [--limit N]
```

指定した組織のメンバー一覧を表示する。

### `gfo org repos`

```
gfo org repos <name> [--limit N]
```

指定した組織のリポジトリ一覧を表示する。

---

## 3. 対応サービス

| サービス | 対応 | エンドポイント（list） | 備考 |
|---|---|---|---|
| GitHub | ✅ | `GET /user/orgs` | `GET /orgs/{org}`, `/orgs/{org}/members`, `/orgs/{org}/repos` |
| GitLab | ✅ | `GET /groups` | グループとして扱う。`GET /groups/{id}`, `/groups/{id}/members`, `/groups/{id}/projects` |
| Gitea | ✅ | `GET /user/orgs` | `GET /orgs/{org}`, `/orgs/{org}/members`, `/orgs/{org}/repos` |
| Forgejo | ✅ | `GET /user/orgs` | Gitea 互換 |
| Gogs | ✅ | `GET /user/orgs` | Gitea 互換（一部 API が異なる可能性あり） |
| Bitbucket | ✅ | `GET /2.0/user/permissions/workspaces` | ワークスペースとして扱う |
| Azure DevOps | ✅ | `GET /accounts` | プロジェクトは org 相当。Organization は Azure アカウント |
| GitBucket | ❌ | API 未対応 | `NotSupportedError` を送出 |
| Backlog | ❌ | チームは別概念（プロジェクト） | `NotSupportedError` を送出 |

---

## 4. データモデル

`src/gfo/adapter/base.py` に追加:

```python
@dataclass(frozen=True, slots=True)
class Organization:
    name: str           # ログイン名 / グループパス / ワークスペーススラッグ
    display_name: str   # 表示名（フルネーム）
    description: str | None
    url: str            # Web URL
```

> - GitHub: `login` → `name`, `name` → `display_name`
> - GitLab: `path` → `name`, `full_name` → `display_name`
> - Bitbucket: `slug` → `name`, `name` → `display_name`
> - Azure DevOps: `accountName` → `name`

---

## 5. アダプター抽象メソッド

`base.py` の `GitServiceAdapter` に以下を追加:

```python
# --- Organization ---
def list_organizations(self, *, limit: int = 30) -> list[Organization]:
    raise NotSupportedError(self.service_name, "org list")

def get_organization(self, name: str) -> Organization:
    raise NotSupportedError(self.service_name, "org view")

def list_org_members(self, name: str, *, limit: int = 30) -> list[str]:
    """メンバーのユーザー名一覧を返す。"""
    raise NotSupportedError(self.service_name, "org members")

def list_org_repos(self, name: str, *, limit: int = 30) -> list[Repository]:
    raise NotSupportedError(self.service_name, "org repos")
```

`list_org_members` は `list[str]`（ユーザー名のみ）とする。
詳細が必要な場合は `--format json` を使用する方針。

---

## 6. 既存コードへの変更

### 新規ファイル

#### `src/gfo/commands/org.py`

```python
"""gfo org サブコマンドのハンドラ。"""

from gfo.commands import get_adapter
from gfo.output import output


def handle_list(args, *, fmt: str) -> None:
    adapter = get_adapter()
    orgs = adapter.list_organizations(limit=args.limit)
    output(orgs, fmt=fmt, fields=["name", "display_name", "url"])


def handle_view(args, *, fmt: str) -> None:
    adapter = get_adapter()
    org = adapter.get_organization(args.name)
    output(org, fmt=fmt)


def handle_members(args, *, fmt: str) -> None:
    adapter = get_adapter()
    members = adapter.list_org_members(args.name, limit=args.limit)
    # list[str] は output() が非対応のため簡易出力。--format json 時は JSON 配列として出力する
    if fmt == "json":
        import json
        print(json.dumps(members, ensure_ascii=False))
        return
    for member in members:
        print(member)


def handle_repos(args, *, fmt: str) -> None:
    adapter = get_adapter()
    repos = adapter.list_org_repos(args.name, limit=args.limit)
    output(repos, fmt=fmt, fields=["name", "full_name", "private", "url"])
```

### 変更ファイル

#### `src/gfo/cli.py`

```python
# org（create_parser() 内に追加。dest="subcommand" は cli.py の dispatch 規約に従う）
org_parser = subparser_map["org"] = subparsers.add_parser("org", help="所属組織を管理する")
org_sub = org_parser.add_subparsers(dest="subcommand")

p_org_list = org_sub.add_parser("list", help="所属組織の一覧")
p_org_list.add_argument("--limit", type=_positive_int, default=30)

p_org_view = org_sub.add_parser("view", help="組織の詳細")
p_org_view.add_argument("name", help="組織名")

p_org_members = org_sub.add_parser("members", help="メンバー一覧")
p_org_members.add_argument("name", help="組織名")
p_org_members.add_argument("--limit", type=_positive_int, default=30)

p_org_repos = org_sub.add_parser("repos", help="リポジトリ一覧")
p_org_repos.add_argument("name", help="組織名")
p_org_repos.add_argument("--limit", type=_positive_int, default=30)
```

`_DISPATCH` に以下を追加:

```python
("org", "list"):    gfo.commands.org.handle_list,
("org", "view"):    gfo.commands.org.handle_view,
("org", "members"): gfo.commands.org.handle_members,
("org", "repos"):   gfo.commands.org.handle_repos,
```

> **注意**: 既存 cli.py は `dest="subcommand"` / `_DISPATCH` パターンを採用する。
> `set_defaults(func=...)` は使用しない。`--limit` は `_positive_int` 型を使用する。

#### 各アダプター

GitHub / Gitea 系は API 形式が近いため、`GitHubLikeAdapter` に共通の `_to_organization` ヘルパーを追加することを検討する。

GitLab はグループ API を使用するため、グループ → `Organization` への変換ロジックを個別実装。

---

## 7. テスト方針

`collaborator` テストと同パターン。

### `tests/test_adapters/test_github_org.py`（新規）

```python
@responses.activate
def test_list_organizations(github_adapter):
    responses.add(GET, ".../user/orgs", json=[
        {"login": "my-org", "name": "My Organization", "description": "...", "html_url": "https://github.com/my-org"}
    ])
    orgs = github_adapter.list_organizations()
    assert orgs[0].name == "my-org"
    assert orgs[0].display_name == "My Organization"

@responses.activate
def test_get_organization(github_adapter):
    responses.add(GET, ".../orgs/my-org", json={
        "login": "my-org", "name": "My Organization", "description": "desc", "html_url": "https://github.com/my-org"
    })
    org = github_adapter.get_organization("my-org")
    assert org.name == "my-org"

@responses.activate
def test_list_org_members(github_adapter):
    responses.add(GET, ".../orgs/my-org/members", json=[
        {"login": "alice"}, {"login": "bob"}
    ])
    members = github_adapter.list_org_members("my-org")
    assert members == ["alice", "bob"]

@responses.activate
def test_list_org_repos(github_adapter):
    responses.add(GET, ".../orgs/my-org/repos", json=[...])
    repos = github_adapter.list_org_repos("my-org")
    assert len(repos) > 0
```

### `tests/test_commands/test_org.py`（新規）

各ハンドラ関数の単体テスト。`mock_adapter` フィクスチャを使用。

### 未対応サービスのテスト

GitBucket / Backlog で `NotSupportedError` が送出されることを確認。
