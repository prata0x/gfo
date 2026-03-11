# 05 通知管理 — インボックス通知の一覧・既読化

## 1. 概要

認証ユーザーのインボックス通知を一覧表示し、既読化する機能。
`gh notification list` / `glab todo list` に相当する機能。

gfo では統一コマンド `gfo notification` として提供する。
サービスごとに「通知」「TODO」「アクティビティ」等の名称が異なるが、gfo では一律 `notification` に統一する。

---

## 2. コマンド設計

```
gfo notification {list,read}
```

### `gfo notification list`

```
gfo notification list [--unread-only] [--limit N]
```

| オプション | デフォルト | 説明 |
|---|---|---|
| `--unread-only` | false | 未読のみ表示 |
| `--limit N` | 30 | 取得件数の上限 |

### `gfo notification read`

```
gfo notification read [<id>] [--all]
```

| 引数/オプション | 説明 |
|---|---|
| `<id>` | 既読にする通知 ID |
| `--all` | すべての通知を既読にする |

`<id>` と `--all` は相互排他。

---

## 3. 対応サービス

| サービス | 対応 | エンドポイント（list） | 備考 |
|---|---|---|---|
| GitHub | ✅ | `GET /notifications` | `PATCH /notifications/threads/{id}`, `PUT /notifications` |
| GitLab | ✅ | `GET /todos` | `POST /todos/{id}/mark_as_done`, `POST /todos/mark_as_done` |
| Gitea | ✅ | `GET /notifications` | `PATCH /notifications/threads/{id}`, `PUT /notifications` |
| Forgejo | ✅ | `GET /notifications` | Gitea 互換 |
| Backlog | ✅ | `GET /api/v2/notifications` | `POST /api/v2/notifications/{id}/markAsRead`, `POST /api/v2/notifications/markAsRead` |
| Azure DevOps | ❌ | 通知 API は管理者向けのみ | `NotSupportedError` を送出 |
| Bitbucket | ❌ | 通知 API なし | `NotSupportedError` を送出 |
| Gogs | ❌ | 通知 API なし | `NotSupportedError` を送出 |
| GitBucket | ❌ | 通知 API なし | `NotSupportedError` を送出 |

---

## 4. データモデル

`src/gfo/adapter/base.py` に追加:

```python
@dataclass(frozen=True, slots=True)
class Notification:
    id: str             # すべてのサービスで str に統一（GitHub・Gitea は数値を文字列化、Backlog も str 化）
    title: str          # 通知のタイトル
    reason: str         # 通知理由（"mention" / "review_requested" / "todo" / "assigned" 等）
    unread: bool
    repository: str     # リポジトリの full_name（例: "owner/repo"）
    url: str            # 対象リソースの Web URL
    updated_at: str     # ISO 8601
```

> **フィールド設計の注意**:
> - GitHub: `subject.title` → `title`, `reason` → `reason`, `repository.full_name` → `repository`
> - GitLab: `body` → `title`, `target_type` → `reason`, `project.path_with_namespace` → `repository`
> - Backlog: `comment.content` または `issue.summary` → `title`, `reason` は `"notification"` 固定
> - `id` は `str` に統一して型の不一致を吸収する

---

## 5. アダプター抽象メソッド

`base.py` の `GitServiceAdapter` に以下を追加:

```python
# --- Notification ---
def list_notifications(
    self, *, unread_only: bool = False, limit: int = 30
) -> list[Notification]:
    raise NotSupportedError(self.service_name, "notification list")

def mark_notification_read(self, notification_id: str) -> None:
    raise NotSupportedError(self.service_name, "notification read")

def mark_all_notifications_read(self) -> None:
    raise NotSupportedError(self.service_name, "notification read --all")
```

---

## 6. 既存コードへの変更

### 新規ファイル

#### `src/gfo/commands/notification.py`

```python
"""gfo notification サブコマンドのハンドラ。"""

import argparse
from gfo.commands import get_adapter
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str) -> None:
    adapter = get_adapter()
    notifications = adapter.list_notifications(
        unread_only=args.unread_only,
        limit=args.limit,
    )
    output(notifications, fmt=fmt, fields=["id", "title", "reason", "unread", "repository", "updated_at"])


def handle_read(args: argparse.Namespace, *, fmt: str) -> None:
    adapter = get_adapter()
    if args.all and args.id:
        raise SystemExit("ID と --all は同時に指定できません")
    if not args.all and args.id is None:
        raise SystemExit("通知 ID または --all を指定してください")
    if args.all:
        adapter.mark_all_notifications_read()
    else:
        adapter.mark_notification_read(args.id)
```

### 変更ファイル

#### `src/gfo/cli.py`

```python
# notification（create_parser() 内に追加。aliases は _DISPATCH と非互換のため使用しない）
notif_parser = subparser_map["notification"] = subparsers.add_parser(
    "notification", help="通知を管理する"
)
notif_sub = notif_parser.add_subparsers(dest="subcommand")

p_notif_list = notif_sub.add_parser("list", help="通知の一覧")
p_notif_list.add_argument("--unread-only", action="store_true")
p_notif_list.add_argument("--limit", type=_positive_int, default=30)

p_notif_read = notif_sub.add_parser("read", help="通知を既読にする")
p_notif_read.add_argument("id", nargs="?", metavar="ID", help="通知 ID")
p_notif_read.add_argument("--all", action="store_true", help="すべての通知を既読にする")
# 注意: id と --all の相互排他バリデーションはハンドラ内で行う
```

`_DISPATCH` に以下を追加:

```python
("notification", "list"): gfo.commands.notification.handle_list,
("notification", "read"): gfo.commands.notification.handle_read,
```

> **注意**: `aliases=["notif"]` は使用しない。argparse の aliases を使うと `args.command` にエイリアス名が格納され、`_DISPATCH` の単一キーで対応できなくなる。短縮エイリアスが必要なら `_DISPATCH` にも `("notif", ...)` のエントリを追加する。

#### `src/gfo/adapter/github.py`

```python
def list_notifications(self, *, unread_only: bool = False, limit: int = 30) -> list[Notification]:
    params = {"per_page": min(limit, 100)}
    if not unread_only:
        params["all"] = "true"  # GitHub はデフォルトで未読のみ。all=true で既読も含む
    data = self._client.get("/notifications", params=params)
    return [self._to_notification(d) for d in data[:limit]]

def mark_notification_read(self, notification_id: str) -> None:
    self._client.patch(f"/notifications/threads/{notification_id}")

def mark_all_notifications_read(self) -> None:
    self._client.put("/notifications", json={})
```

#### `src/gfo/adapter/gitlab.py`

GitLab の「TODO」を通知として扱う。
`POST /todos/{id}/mark_as_done` / `POST /todos/mark_as_done`。

#### `src/gfo/adapter/gitea.py` / `forgejo.py`

GitHub 互換の通知 API を使用。`/notifications` エンドポイント。

#### `src/gfo/adapter/backlog.py`

`GET /api/v2/notifications` → `Notification` への変換。
`apiKey` クエリパラメータで認証（既存パターンと同一）。

---

## 7. テスト方針

### `tests/test_adapters/test_github_notification.py`（新規）

```python
@responses.activate
def test_list_notifications(github_adapter):
    responses.add(GET, ".../notifications", json=[{
        "id": "1",
        "reason": "mention",
        "unread": True,
        "subject": {"title": "Fix bug", "url": "...", "type": "Issue"},
        "repository": {"full_name": "owner/repo"},
        "updated_at": "2024-01-01T00:00:00Z",
    }])
    notifs = github_adapter.list_notifications()
    assert notifs[0].title == "Fix bug"
    assert notifs[0].unread is True

@responses.activate
def test_mark_notification_read(github_adapter):
    responses.add(PATCH, ".../notifications/threads/1", status=205)
    github_adapter.mark_notification_read("1")

@responses.activate
def test_mark_all_notifications_read(github_adapter):
    responses.add(PUT, ".../notifications", status=205)
    github_adapter.mark_all_notifications_read()

@responses.activate
def test_list_notifications_unread_only(github_adapter):
    """unread_only=True（デフォルト未読のみ）では all パラメータを送らない。"""
    responses.add(GET, ".../notifications", json=[])
    github_adapter.list_notifications(unread_only=True)
    assert "all" not in responses.calls[0].request.params

@responses.activate
def test_list_notifications_all(github_adapter):
    """unread_only=False では all=true を送信して既読も含む全通知を取得する。"""
    responses.add(GET, ".../notifications", json=[])
    github_adapter.list_notifications(unread_only=False)
    assert responses.calls[0].request.params.get("all") == "true"
```

### `tests/test_adapters/test_gitlab_notification.py`（新規）

GitLab TODO API のモックテスト。

### `tests/test_commands/test_notification.py`（新規）

```python
def test_list_command(mock_adapter, capsys):
    mock_adapter.list_notifications.return_value = [
        Notification(id="1", title="Fix", reason="mention", unread=True,
                     repository="owner/repo", url="https://...", updated_at="2024-01-01")
    ]
    handle_list(make_args(unread_only=False, limit=30), fmt="table")
    out = capsys.readouterr().out
    assert "Fix" in out

def test_read_all_command(mock_adapter):
    handle_read(make_args(all=True), fmt="table")
    mock_adapter.mark_all_notifications_read.assert_called_once()
```

### 未対応サービスのテスト

Azure DevOps / Bitbucket / Gogs / GitBucket で `NotSupportedError` が送出されることを確認。
