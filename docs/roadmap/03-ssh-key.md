# 03 SSH Key 管理 — ユーザー SSH 公開鍵の list / create / delete

## 1. 概要

ユーザーアカウントに登録された SSH 公開鍵を CLI から管理する機能。
`deploy-key`（リポジトリレベル）との違いは**ユーザーレベル**である点。

`gh ssh-key` / `glab ssh-key` に相当する機能。

---

## 2. コマンド設計

```
gfo ssh-key {list,create,delete}
```

### `gfo ssh-key list`

```
gfo ssh-key list [--limit N]
```

| オプション | デフォルト | 説明 |
|---|---|---|
| `--limit N` | 30 | 取得件数の上限 |

### `gfo ssh-key create`

```
gfo ssh-key create --title TITLE --key PUBLIC_KEY
```

| オプション | 説明 |
|---|---|
| `--title TITLE` | 鍵の名前（必須） |
| `--key PUBLIC_KEY` | 公開鍵の内容（必須、`ssh-rsa ...` 形式） |

### `gfo ssh-key delete`

```
gfo ssh-key delete <id>
```

| 引数 | 説明 |
|---|---|
| `id` | 削除する鍵の ID（`list` で確認） |

---

## 3. 対応サービス

| サービス | 対応 | エンドポイント |
|---|---|---|
| GitHub | ✅ | `GET/POST /user/keys`, `DELETE /user/keys/{key_id}` |
| GitLab | ✅ | `GET/POST /user/keys`, `DELETE /user/keys/{key_id}` |
| Gitea | ✅ | `GET/POST /user/keys`, `DELETE /user/keys/{id}` |
| Forgejo | ✅ | `GET/POST /user/keys`, `DELETE /user/keys/{id}` |
| Gogs | ✅ | `GET/POST /user/keys`, `DELETE /user/keys/{id}` |
| Bitbucket | ✅ | `GET/POST /2.0/users/{username}/ssh-keys`, `DELETE /2.0/users/{username}/ssh-keys/{key_id}` |
| Azure DevOps | ❌ | SSH 鍵管理 API なし（Web UI のみ） |
| GitBucket | ❌ | API 未対応 |
| Backlog | ❌ | SSH 鍵管理 API なし |

> Azure DevOps・GitBucket・Backlog は `NotSupportedError` を送出する。

---

## 4. データモデル

`src/gfo/adapter/base.py` に追加:

```python
@dataclass(frozen=True, slots=True)
class SshKey:
    id: int | str   # GitHub/GitLab/Gitea 系は int、Bitbucket は UUID 文字列
    title: str
    key: str        # 公開鍵の全文（`ssh-rsa AAAA...` 形式）
    created_at: str
```

> **フィールド設計の注意**:
> - GitHub / Gitea / Forgejo / Gogs は `id` が int、`key` フィールドに公開鍵の全文を返す
> - GitLab は `id` が int、`key` フィールドに全文を返す
> - Bitbucket は `id` が UUID 文字列（`uuid` フィールド）のため `int | str` に統一する
> - `created_at` が返されないサービスでは空文字列を設定する

---

## 5. アダプター抽象メソッド

`base.py` の `GitServiceAdapter` に以下を追加:

```python
# --- SSH Key ---
def list_ssh_keys(self, *, limit: int = 30) -> list[SshKey]:
    raise NotSupportedError(self.service_name, "ssh-key list")

def create_ssh_key(self, *, title: str, key: str) -> SshKey:
    raise NotSupportedError(self.service_name, "ssh-key create")

def delete_ssh_key(self, *, key_id: int | str) -> None:
    raise NotSupportedError(self.service_name, "ssh-key delete")
```

`deploy-key` と異なり、SSH 鍵は**ユーザーレベル**のため `self._owner` / `self._repo` を使用しない。
Bitbucket のみ `self._owner`（ユーザー名）を使用する必要があるため、アダプター側で保持する。

---

## 6. 既存コードへの変更

### 新規ファイル

#### `src/gfo/commands/ssh_key.py`

```python
"""gfo ssh-key サブコマンドのハンドラ。"""

from gfo.commands import get_adapter
from gfo.output import output


def handle_list(args, *, fmt: str) -> None:
    adapter = get_adapter()
    keys = adapter.list_ssh_keys(limit=args.limit)
    output(keys, fmt=fmt, fields=["id", "title", "created_at"])


def handle_create(args, *, fmt: str) -> None:
    adapter = get_adapter()
    key = adapter.create_ssh_key(title=args.title, key=args.key)
    output(key, fmt=fmt)


def handle_delete(args, *, fmt: str) -> None:
    adapter = get_adapter()
    adapter.delete_ssh_key(key_id=args.id)
```

### 変更ファイル

#### `src/gfo/cli.py`

`deploy-key` と同パターンで `ssh-key` サブパーサーを追加（`dest="subcommand"` / `_DISPATCH` パターン）:

```python
# ssh-key（create_parser() 内に追加）
ssh_key_parser = subparser_map["ssh-key"] = subparsers.add_parser("ssh-key", help="SSH 鍵を管理する")
ssh_key_sub = ssh_key_parser.add_subparsers(dest="subcommand")

p_ssh_key_list = ssh_key_sub.add_parser("list")
p_ssh_key_list.add_argument("--limit", type=_positive_int, default=30)

p_ssh_key_create = ssh_key_sub.add_parser("create")
p_ssh_key_create.add_argument("--title", required=True)
p_ssh_key_create.add_argument("--key", required=True)

p_ssh_key_delete = ssh_key_sub.add_parser("delete")
p_ssh_key_delete.add_argument("id")  # int | str（Bitbucket は UUID 文字列）
```

`_DISPATCH` に以下を追加:

```python
("ssh-key", "list"):   gfo.commands.ssh_key.handle_list,
("ssh-key", "create"): gfo.commands.ssh_key.handle_create,
("ssh-key", "delete"): gfo.commands.ssh_key.handle_delete,
```

#### `src/gfo/adapter/github.py`

```python
def list_ssh_keys(self, *, limit: int = 30) -> list[SshKey]:
    data = self._client.get("/user/keys", params={"per_page": min(limit, 100)})
    return [SshKey(id=d["id"], title=d["title"], key=d["key"], created_at=d.get("created_at", "")) for d in data[:limit]]

def create_ssh_key(self, *, title: str, key: str) -> SshKey:
    data = self._client.post("/user/keys", json={"title": title, "key": key})
    return SshKey(id=data["id"], title=data["title"], key=data["key"], created_at=data.get("created_at", ""))

def delete_ssh_key(self, *, key_id: int | str) -> None:
    self._client.delete(f"/user/keys/{key_id}")
```

#### `src/gfo/adapter/gitlab.py`

エンドポイントは GitHub と同一（`/user/keys`）。レスポンス形式も類似。

#### `src/gfo/adapter/gitea.py` / `forgejo.py` / `gogs.py`

`GitHubLikeAdapter` の共通実装として切り出せる可能性あり。
エンドポイントは `/user/keys`、レスポンス形式は GitHub 互換。

#### `src/gfo/adapter/bitbucket.py`

エンドポイントが `/2.0/users/{username}/ssh-keys` と異なる。
Bitbucket の SSH 鍵は `uuid` フィールドを持つ（`"{xxxxxxxx-xxxx-...}"` 形式）。
`SshKey.id` を `int | str` としているため、UUID 文字列をそのまま格納する。
`delete_ssh_key` の引数型も `key_id: int | str` に合わせる。

---

## 7. テスト方針

`deploy-key` テストと同パターンで実装。

### `tests/test_adapters/test_github_ssh_key.py`（新規）

```python
@responses.activate
def test_list_ssh_keys(github_adapter):
    responses.add(GET, ".../user/keys", json=[
        {"id": 1, "title": "my key", "key": "ssh-rsa AAAA...", "created_at": "2024-01-01T00:00:00Z"}
    ])
    keys = github_adapter.list_ssh_keys()
    assert len(keys) == 1
    assert keys[0].title == "my key"

@responses.activate
def test_create_ssh_key(github_adapter):
    responses.add(POST, ".../user/keys", json={
        "id": 2, "title": "new key", "key": "ssh-ed25519 AAAA...", "created_at": "2024-01-02T00:00:00Z"
    })
    key = github_adapter.create_ssh_key(title="new key", key="ssh-ed25519 AAAA...")
    assert key.id == 2

@responses.activate
def test_delete_ssh_key(github_adapter):
    responses.add(DELETE, ".../user/keys/1", status=204)
    github_adapter.delete_ssh_key(key_id=1)  # 例外が発生しなければ OK
```

### `tests/test_commands/test_ssh_key.py`（新規）

```python
def test_list_command(mock_adapter, capsys):
    mock_adapter.list_ssh_keys.return_value = [SshKey(id=1, title="t", key="k", created_at="2024-01-01")]
    handle_list(make_args(limit=30), fmt="table")
    out = capsys.readouterr().out
    assert "t" in out
```

### 未対応サービスのテスト

Azure DevOps / GitBucket / Backlog で `NotSupportedError` が送出されることを確認。
