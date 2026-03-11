# 06 ブランチ保護 — ブランチ保護ルールの確認・設定

## 1. 概要

リポジトリのブランチ保護ルールを CLI から確認・設定する機能。
`gh api repos/.../branches/.../protection` / `glab protected-branches list` に相当する機能。

ブランチ保護の API はサービスごとに大きく異なる（特に GitHub と GitLab）ため、
gfo では最大公約数的なフィールドセットに正規化して提供する。

---

## 2. コマンド設計

```
gfo branch-protect {list,view,set,remove}
```

`deploy-key` / `label` と同形式のトップレベルコマンド。

### `gfo branch-protect list`

```
gfo branch-protect list [--limit N]
```

リポジトリのすべてのブランチ保護ルールを一覧表示する。

### `gfo branch-protect view`

```
gfo branch-protect view <branch>
```

| 引数 | 説明 |
|---|---|
| `branch` | 保護ルールを確認するブランチ名 |

### `gfo branch-protect set`

```
gfo branch-protect set <branch> [オプション]
```

| オプション | 説明 |
|---|---|
| `--require-reviews N` | 必要なレビュー承認数（0 で無効） |
| `--require-status-checks CHECK...` | 必須ステータスチェックのコンテキスト名（複数指定可） |
| `--enforce-admins` / `--no-enforce-admins` | 管理者にも保護を適用するか |
| `--allow-force-push` / `--no-allow-force-push` | 強制プッシュを許可するか |
| `--allow-deletions` / `--no-allow-deletions` | ブランチ削除を許可するか |

### `gfo branch-protect remove`

```
gfo branch-protect remove <branch>
```

指定ブランチの保護ルールを削除する。

---

## 3. 対応サービス

| サービス | 対応 | エンドポイント（list/view） | 備考 |
|---|---|---|---|
| GitHub | ✅ | `GET /repos/{owner}/{repo}/branches/{branch}/protection` | `PUT` で設定、`DELETE` で削除。一覧は `GET /repos/{owner}/{repo}/branches` の `protected` フラグで判断 |
| GitLab | ✅ | `GET /projects/{id}/protected_branches` | `POST` で追加、`DELETE /protected_branches/{name}` で削除。一覧 API が存在する |
| Gitea | ✅ | `GET /repos/{owner}/{repo}/branch_protections` | `POST` で追加、`DELETE` で削除 |
| Forgejo | ✅ | `GET /repos/{owner}/{repo}/branch_protections` | Gitea 互換 |
| Bitbucket | ✅ | `GET /2.0/repositories/{workspace}/{repo_slug}/branch-restrictions` | ルールタイプが異なる（`push`, `delete`, `force` 等） |
| Azure DevOps | ✅ | `GET /{org}/{project}/_apis/policy/configurations` | ポリシーとして管理。変換ロジックが複雑 |
| Gogs | ❌ | API 未対応 | `NotSupportedError` を送出 |
| GitBucket | ❌ | API 未対応 | `NotSupportedError` を送出 |
| Backlog | ❌ | ブランチ保護 API なし | `NotSupportedError` を送出 |

---

## 4. データモデル

`src/gfo/adapter/base.py` に追加:

```python
@dataclass(frozen=True, slots=True)
class BranchProtection:
    branch: str                         # ブランチ名またはパターン（例: "main", "release/*"）
    require_reviews: int                # 必要なレビュー承認数（0 = 無効）
    require_status_checks: tuple[str, ...]  # 必須ステータスチェック名のリスト
    enforce_admins: bool                # 管理者にも保護を適用するか
    allow_force_push: bool              # 強制プッシュを許可するか
    allow_deletions: bool               # ブランチ削除を許可するか
```

> **フィールド設計の注意**:
> - GitHub: `required_pull_request_reviews.required_approving_review_count` → `require_reviews`
> - GitLab: `required_approvals` → `require_reviews`（GitLab EE のみ）
> - Bitbucket: ルールタイプを `allow_force_push` / `allow_deletions` フラグに変換
> - Azure DevOps: ポリシー設定を各フィールドにマッピング（変換ロジックが複雑）
> - 各サービスで対応していないフィールドはデフォルト値（`0`, `False`）を設定

---

## 5. アダプター抽象メソッド

`base.py` の `GitServiceAdapter` に以下を追加:

```python
# --- BranchProtection ---
def list_branch_protections(self, *, limit: int = 30) -> list[BranchProtection]:
    raise NotSupportedError(self.service_name, "branch-protect list")

def get_branch_protection(self, branch: str) -> BranchProtection:
    raise NotSupportedError(self.service_name, "branch-protect view")

def set_branch_protection(
    self,
    branch: str,
    *,
    require_reviews: int | None = None,
    require_status_checks: list[str] | None = None,
    # 注意: 引数は list[str] だが、BranchProtection.require_status_checks は tuple[str, ...]。
    # アダプター実装側で tuple(require_status_checks) に変換して格納する。
    enforce_admins: bool | None = None,
    allow_force_push: bool | None = None,
    allow_deletions: bool | None = None,
) -> BranchProtection:
    raise NotSupportedError(self.service_name, "branch-protect set")

def remove_branch_protection(self, branch: str) -> None:
    raise NotSupportedError(self.service_name, "branch-protect remove")
```

`set_branch_protection` の引数はすべて `None` デフォルトとし、
指定されなかったフィールドは現在の設定を維持する（部分更新）。

> **GitHub 実装上の注意**: GitHub の `PUT /branches/{branch}/protection` は全フィールドを必須で送る仕様（PATCH 不可）。
> 部分更新を実現するには、まず `get_branch_protection()` で現在の設定を取得し、`None` のフィールドは既存値で補完してから PUT する実装になる。
> 他サービス（GitLab・Gitea）は `POST` のため全フィールドが必須ではなく、この問題は発生しない。

---

## 6. 既存コードへの変更

### 新規ファイル

#### `src/gfo/commands/branch_protect.py`

```python
"""gfo branch-protect サブコマンドのハンドラ。"""

import argparse
from gfo.commands import get_adapter
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str) -> None:
    adapter = get_adapter()
    protections = adapter.list_branch_protections(limit=args.limit)
    output(protections, fmt=fmt, fields=["branch", "require_reviews", "enforce_admins", "allow_force_push"])


def handle_view(args: argparse.Namespace, *, fmt: str) -> None:
    adapter = get_adapter()
    protection = adapter.get_branch_protection(args.branch)
    output(protection, fmt=fmt)


def handle_set(args: argparse.Namespace, *, fmt: str) -> None:
    adapter = get_adapter()
    protection = adapter.set_branch_protection(
        args.branch,
        require_reviews=args.require_reviews,
        require_status_checks=args.require_status_checks,
        enforce_admins=args.enforce_admins,
        allow_force_push=args.allow_force_push,
        allow_deletions=args.allow_deletions,
    )
    output(protection, fmt=fmt)


def handle_remove(args: argparse.Namespace, *, fmt: str) -> None:
    adapter = get_adapter()
    adapter.remove_branch_protection(args.branch)
```

### 変更ファイル

#### `src/gfo/cli.py`

```python
# branch-protect（create_parser() 内に追加）
bp_parser = subparser_map["branch-protect"] = subparsers.add_parser(
    "branch-protect", help="ブランチ保護ルールを管理する"
)
bp_sub = bp_parser.add_subparsers(dest="subcommand")

p_bp_list = bp_sub.add_parser("list")
p_bp_list.add_argument("--limit", type=_positive_int, default=30)

p_bp_view = bp_sub.add_parser("view")
p_bp_view.add_argument("branch")

p_bp_set = bp_sub.add_parser("set")
p_bp_set.add_argument("branch")
p_bp_set.add_argument("--require-reviews", type=int, dest="require_reviews")
p_bp_set.add_argument("--require-status-checks", nargs="+", dest="require_status_checks")
p_bp_set.add_argument("--enforce-admins", action="store_true", default=None)
p_bp_set.add_argument("--no-enforce-admins", dest="enforce_admins", action="store_false")
p_bp_set.add_argument("--allow-force-push", action="store_true", default=None)
p_bp_set.add_argument("--no-allow-force-push", dest="allow_force_push", action="store_false")
p_bp_set.add_argument("--allow-deletions", action="store_true", default=None)
p_bp_set.add_argument("--no-allow-deletions", dest="allow_deletions", action="store_false")
# 注意: store_true + default=None の組み合わせにより、
#   未指定 → None（アダプター側で現在設定を維持）
#   --enforce-admins → True
#   --no-enforce-admins → False
# という 3 値で部分更新を実現する

p_bp_remove = bp_sub.add_parser("remove")
p_bp_remove.add_argument("branch")
```

`_DISPATCH` に以下を追加:

```python
("branch-protect", "list"):   gfo.commands.branch_protect.handle_list,
("branch-protect", "view"):   gfo.commands.branch_protect.handle_view,
("branch-protect", "set"):    gfo.commands.branch_protect.handle_set,
("branch-protect", "remove"): gfo.commands.branch_protect.handle_remove,
```

> **注意**: 既存 cli.py は `dest="subcommand"` / `_DISPATCH` パターンを採用する。`set_defaults(func=...)` は使用しない。

---

## 7. テスト方針

サービス間の API 差異が大きいため、**変換ロジックの正確性**を重点的にテストする。

### `tests/test_adapters/test_github_branch_protect.py`（新規）

```python
@responses.activate
def test_get_branch_protection(github_adapter):
    responses.add(GET, ".../branches/main/protection", json={
        "required_pull_request_reviews": {"required_approving_review_count": 2},
        "required_status_checks": {"contexts": ["ci/test"]},
        "enforce_admins": {"enabled": True},
        "restrictions": None,
        "allow_force_pushes": {"enabled": False},
        "allow_deletions": {"enabled": False},
    })
    bp = github_adapter.get_branch_protection("main")
    assert bp.branch == "main"
    assert bp.require_reviews == 2
    assert bp.require_status_checks == ("ci/test",)
    assert bp.enforce_admins is True

@responses.activate
def test_set_branch_protection(github_adapter):
    responses.add(PUT, ".../branches/main/protection", json={...})
    bp = github_adapter.set_branch_protection("main", require_reviews=1)
    assert bp.require_reviews == 1
```

### `tests/test_adapters/test_gitlab_branch_protect.py`（新規）

GitLab のプロテクトブランチ API（`push_access_levels` / `merge_access_levels`）の変換ロジックをテスト。

### `tests/test_adapters/test_azure_devops_branch_protect.py`（新規）

Azure DevOps ポリシー API の変換ロジックをテスト（最も複雑）。

### `tests/test_adapters/test_bitbucket_branch_protect.py`（新規）

Bitbucket branch-restrictions の `kind` フィールドを `allow_force_push` / `allow_deletions` に変換するロジックをテスト。

### `tests/test_commands/test_branch_protect.py`（新規）

各ハンドラ関数の単体テスト。

### 未対応サービスのテスト

Gogs / GitBucket / Backlog で `NotSupportedError` が送出されることを確認。
