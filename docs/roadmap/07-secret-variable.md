# 07 Secret / Variable 管理 — CI/CD シークレット・変数の管理

## 1. 概要

CI/CD パイプラインで使用するシークレット（暗号化済み値）と変数（平文値）を CLI から管理する機能。

| 種別 | コマンド | 説明 |
|---|---|---|
| Secret | `gfo secret` | 暗号化して保存される機密情報（値の読み取り不可） |
| Variable | `gfo variable` | 平文で保存される環境変数（値の読み取り可） |

`gh secret` / `glab variable` に相当する機能。

---

## 2. コマンド設計

### Secret

```
gfo secret {list,set,delete}
```

#### `gfo secret list`

```
gfo secret list [--limit N]
```

シークレット名と更新日時の一覧（値は表示不可）。

#### `gfo secret set`

```
gfo secret set <name> [--value VALUE | --env-var ENV_VAR | --file FILE]
```

| 引数/オプション | 説明 |
|---|---|
| `name` | シークレット名（必須） |
| `--value VALUE` | シークレット値（平文で渡す） |
| `--env-var ENV_VAR` | 環境変数から値を取得する |
| `--file FILE` | ファイルから値を取得する |

`--value` / `--env-var` / `--file` のいずれか 1 つが必須（相互排他）。

#### `gfo secret delete`

```
gfo secret delete <name>
```

### Variable

```
gfo variable {list,set,get,delete}
```

#### `gfo variable list`

```
gfo variable list [--limit N]
```

#### `gfo variable set`

```
gfo variable set <name> --value VALUE [--masked]
```

| オプション | 説明 |
|---|---|
| `--masked` | GitLab の masked 変数として設定する（GitLab のみ有効） |

#### `gfo variable get`

```
gfo variable get <name>
```

変数の値を表示する（Secret では使用不可）。

#### `gfo variable delete`

```
gfo variable delete <name>
```

---

## 3. 対応サービス

### Secret

| サービス | 対応 | エンドポイント | 備考 |
|---|---|---|---|
| GitHub | ✅ | `GET/PUT /repos/{owner}/{repo}/actions/secrets/{name}` | 値は libsodium で暗号化が必要 |
| GitLab | ✅ | `GET/PUT /projects/{id}/variables/{key}` | GitLab では Secret と Variable の区別なし（`masked` フラグで制御） |
| Gitea | ✅ | `GET/PUT /repos/{owner}/{repo}/actions/secrets/{secretname}` | Gitea 1.19+ |
| Forgejo | ✅ | `GET/PUT /repos/{owner}/{repo}/actions/secrets/{secretname}` | Gitea 互換 |
| Bitbucket | ✅ | `GET /2.0/repositories/{workspace}/{repo_slug}/pipelines_config/variables/` | Bitbucket Pipelines 変数 |
| Azure DevOps | ❌ | Library API が複雑 | 将来対応 |
| Gogs | ❌ | Actions API なし | `NotSupportedError` を送出 |
| GitBucket | ❌ | Actions API なし | `NotSupportedError` を送出 |
| Backlog | ❌ | CI/CD 機能なし | `NotSupportedError` を送出 |

### Variable

| サービス | 対応 | エンドポイント | 備考 |
|---|---|---|---|
| GitHub | ✅ | `GET/POST/PATCH/DELETE /repos/{owner}/{repo}/actions/variables/{name}` | |
| GitLab | ✅ | `GET/POST/PUT/DELETE /projects/{id}/variables/{key}` | `masked=false` で変数 |
| Gitea | ✅ | `GET/POST/PUT/DELETE /repos/{owner}/{repo}/actions/variables/{variablename}` | |
| Forgejo | ✅ | Gitea 互換 | |
| Bitbucket | ✅ | Pipelines 変数（Secret と同一エンドポイント、`secured` フラグで区別） | |
| Azure DevOps | ❌ | 将来対応 | |
| Gogs / GitBucket / Backlog | ❌ | `NotSupportedError` | |

---

## 4. データモデル

`src/gfo/adapter/base.py` に追加:

```python
@dataclass(frozen=True, slots=True)
class Secret:
    name: str
    created_at: str
    updated_at: str

@dataclass(frozen=True, slots=True)
class Variable:
    name: str
    value: str          # Secret とは異なり値を保持する
    created_at: str
    updated_at: str
```

> **フィールド設計の注意**:
> - GitHub Secret は `created_at` / `updated_at` を返すが、値は返さない
> - GitLab の Variable は値を返す（Secret 相当の `masked=true` 変数も値を返さない場合あり）
> - Bitbucket の `secured=true` 変数は値を返さない
> - `created_at` / `updated_at` が取得できないサービスでは空文字列を設定する

---

## 5. アダプター抽象メソッド

`base.py` の `GitServiceAdapter` に以下を追加:

```python
# --- Secret ---
def list_secrets(self, *, limit: int = 30) -> list[Secret]:
    raise NotSupportedError(self.service_name, "secret list")

def set_secret(self, name: str, value: str) -> Secret:
    raise NotSupportedError(self.service_name, "secret set")

def delete_secret(self, name: str) -> None:
    raise NotSupportedError(self.service_name, "secret delete")

# --- Variable ---
def list_variables(self, *, limit: int = 30) -> list[Variable]:
    raise NotSupportedError(self.service_name, "variable list")

def set_variable(self, name: str, value: str, *, masked: bool = False) -> Variable:
    raise NotSupportedError(self.service_name, "variable set")

def get_variable(self, name: str) -> Variable:
    raise NotSupportedError(self.service_name, "variable get")

def delete_variable(self, name: str) -> None:
    raise NotSupportedError(self.service_name, "variable delete")
```

---

## 6. 既存コードへの変更

### 新規ファイル

#### `src/gfo/commands/secret.py`

```python
"""gfo secret サブコマンドのハンドラ。"""

import argparse
import os
from gfo.commands import get_adapter
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str) -> None:
    adapter = get_adapter()
    secrets = adapter.list_secrets(limit=args.limit)
    output(secrets, fmt=fmt, fields=["name", "updated_at"])


def handle_set(args: argparse.Namespace, *, fmt: str) -> None:
    adapter = get_adapter()
    if args.value is not None:
        value = args.value
    elif args.env_var is not None:
        value = os.environ[args.env_var]
    else:
        with open(args.file) as f:
            value = f.read().strip()
    secret = adapter.set_secret(args.name, value)
    output(secret, fmt=fmt)


def handle_delete(args: argparse.Namespace, *, fmt: str) -> None:
    adapter = get_adapter()
    adapter.delete_secret(args.name)
```

#### `src/gfo/commands/variable.py`

```python
"""gfo variable サブコマンドのハンドラ。"""

import argparse
from gfo.commands import get_adapter
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str) -> None:
    adapter = get_adapter()
    variables = adapter.list_variables(limit=args.limit)
    output(variables, fmt=fmt, fields=["name", "value", "updated_at"])


def handle_set(args: argparse.Namespace, *, fmt: str) -> None:
    adapter = get_adapter()
    variable = adapter.set_variable(args.name, args.value, masked=args.masked)
    output(variable, fmt=fmt)


def handle_get(args: argparse.Namespace, *, fmt: str) -> None:
    adapter = get_adapter()
    variable = adapter.get_variable(args.name)
    print(variable.value)


def handle_delete(args: argparse.Namespace, *, fmt: str) -> None:
    adapter = get_adapter()
    adapter.delete_variable(args.name)
```

### 変更ファイル

#### `src/gfo/cli.py`

```python
# secret（create_parser() 内に追加）
secret_parser = subparser_map["secret"] = subparsers.add_parser("secret", help="シークレットを管理する")
secret_sub = secret_parser.add_subparsers(dest="subcommand")

p_secret_list = secret_sub.add_parser("list")
p_secret_list.add_argument("--limit", type=_positive_int, default=30)

p_secret_set = secret_sub.add_parser("set")
p_secret_set.add_argument("name")
_secret_value_group = p_secret_set.add_mutually_exclusive_group(required=True)
_secret_value_group.add_argument("--value")
_secret_value_group.add_argument("--env-var", dest="env_var")
_secret_value_group.add_argument("--file")

p_secret_delete = secret_sub.add_parser("delete")
p_secret_delete.add_argument("name")

# variable（aliases は _DISPATCH と非互換のため使用しない）
variable_parser = subparser_map["variable"] = subparsers.add_parser("variable", help="変数を管理する")
variable_sub = variable_parser.add_subparsers(dest="subcommand")

p_variable_list = variable_sub.add_parser("list")
p_variable_list.add_argument("--limit", type=_positive_int, default=30)

p_variable_set = variable_sub.add_parser("set")
p_variable_set.add_argument("name")
p_variable_set.add_argument("--value", required=True)
p_variable_set.add_argument("--masked", action="store_true")

p_variable_get = variable_sub.add_parser("get")
p_variable_get.add_argument("name")

p_variable_delete = variable_sub.add_parser("delete")
p_variable_delete.add_argument("name")
```

`_DISPATCH` に以下を追加:

```python
("secret", "list"):   gfo.commands.secret.handle_list,
("secret", "set"):    gfo.commands.secret.handle_set,
("secret", "delete"): gfo.commands.secret.handle_delete,
("variable", "list"):   gfo.commands.variable.handle_list,
("variable", "set"):    gfo.commands.variable.handle_set,
("variable", "get"):    gfo.commands.variable.handle_get,
("variable", "delete"): gfo.commands.variable.handle_delete,
```

> **注意**: `aliases=["var"]` は使用しない（`_DISPATCH` との非互換）。`dest="subcommand"` は既存 cli.py の dispatch 規約。`set_defaults(func=...)` は使用しない。

#### `src/gfo/adapter/gitlab.py` — GitLab Secret の実装

GitLab は Secret と Variable を同一エンドポイント（`/projects/{id}/variables`）で管理し、`masked` フラグで区別する。

```python
def list_secrets(self, *, limit: int = 30) -> list[Secret]:
    # GitLab は masked=true の変数を Secret として扱う
    data = self._client.get(f"/projects/{self._project_id}/variables")
    secrets = [d for d in data if d.get("masked")]
    return [
        Secret(name=d["key"], created_at=d.get("created_at", ""), updated_at=d.get("updated_at", ""))
        for d in secrets[:limit]
    ]

def set_secret(self, name: str, value: str) -> Secret:
    # masked=True で set_variable を呼び、Secret に変換して返す
    var = self.set_variable(name, value, masked=True)
    return Secret(name=var.name, created_at=var.created_at, updated_at=var.updated_at)
```

`list_variables` では逆に `masked=false` の変数のみを返す（または全変数を返して `Variable` として扱う）。

#### `src/gfo/adapter/github.py` — GitHub Actions Secret の暗号化

GitHub の `set_secret` は libsodium の公開鍵暗号化が必要:

```python
def set_secret(self, name: str, value: str) -> Secret:
    # リポジトリの公開鍵を取得
    pub_key_data = self._client.get(
        f"/repos/{self._owner}/{self._repo}/actions/secrets/public-key"
    )
    encrypted = self._encrypt_secret(pub_key_data["key"], value)
    self._client.put(
        f"/repos/{self._owner}/{self._repo}/actions/secrets/{name}",
        json={"encrypted_value": encrypted, "key_id": pub_key_data["key_id"]},
    )
    # PUT は 201/204 を返し、作成後のデータを含まないため GET で再取得する
    data = self._client.get(
        f"/repos/{self._owner}/{self._repo}/actions/secrets/{name}"
    )
    return Secret(name=data["name"], created_at=data.get("created_at", ""), updated_at=data.get("updated_at", ""))

@staticmethod
def _encrypt_secret(public_key: str, secret_value: str) -> str:
    """PyNaCl を使って libsodium sealed box で暗号化する。"""
    try:
        from nacl import encoding, public
    except ImportError:
        raise GfoError(
            "GitHub Secret の暗号化には PyNaCl が必要です: pip install PyNaCl"
        )
    key = public.PublicKey(public_key.encode(), encoding.Base64Encoder())
    sealed_box = public.SealedBox(key)
    encrypted = sealed_box.encrypt(secret_value.encode())
    return encoding.Base64Encoder().encode(encrypted).decode()
```

> **注意**: PyNaCl を必須依存にするのではなく、`set_secret` 実行時に初めてインポートし、
> 未インストールの場合はエラーメッセージを表示する「遅延インポート」方式を採用する。

---

## 7. テスト方針

### `tests/test_adapters/test_github_secret.py`（新規）

#### GitHub Secret 暗号化のモックテスト

```python
@responses.activate
def test_set_secret_encrypts_value(github_adapter):
    # 公開鍵取得をモック
    responses.add(GET, ".../actions/secrets/public-key", json={
        "key_id": "key123",
        "key": base64.b64encode(b"\x00" * 32).decode(),  # ダミー公開鍵
    })
    # PUT をモック
    responses.add(PUT, ".../actions/secrets/MY_SECRET", status=201)
    # GET（作成後の取得）をモック
    responses.add(GET, ".../actions/secrets/MY_SECRET", json={
        "name": "MY_SECRET",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    })

    with patch("gfo.adapter.github.GitHubAdapter._encrypt_secret", return_value="encrypted=="):
        secret = github_adapter.set_secret("MY_SECRET", "supersecret")

    assert secret.name == "MY_SECRET"
    body = json.loads(responses.calls[1].request.body)
    assert body["encrypted_value"] == "encrypted=="
    assert body["key_id"] == "key123"

@responses.activate
def test_list_secrets(github_adapter):
    responses.add(GET, ".../actions/secrets", json={
        "total_count": 1,
        "secrets": [{"name": "MY_SECRET", "created_at": "...", "updated_at": "..."}]
    })
    secrets = github_adapter.list_secrets()
    assert secrets[0].name == "MY_SECRET"
```

### `tests/test_adapters/test_gitlab_variable.py`（新規）

#### GitLab masked フラグの区別テスト

```python
@responses.activate
def test_set_variable_masked(gitlab_adapter):
    responses.add(POST, ".../variables", json={
        "key": "MY_VAR", "value": "secret", "masked": True,
        "created_at": "2024-01-01T00:00:00Z", "updated_at": "2024-01-01T00:00:00Z",
    })
    var = gitlab_adapter.set_variable("MY_VAR", "secret", masked=True)
    body = json.loads(responses.calls[0].request.body)
    assert body["masked"] is True

@responses.activate
def test_set_secret_uses_masked_flag(gitlab_adapter):
    """GitLab の set_secret は masked=True で set_variable を呼ぶことを確認。"""
    responses.add(POST, ".../variables", json={...})
    gitlab_adapter.set_secret("MY_SECRET", "value")
    body = json.loads(responses.calls[0].request.body)
    assert body.get("masked") is True
```

### `tests/test_commands/test_secret.py`（新規）

```python
def test_set_from_env_var(mock_adapter, monkeypatch):
    monkeypatch.setenv("MY_ENV", "secretvalue")
    mock_adapter.set_secret.return_value = Secret(name="X", created_at="", updated_at="")
    handle_set(make_args(name="X", value=None, env_var="MY_ENV", file=None), fmt="table")
    mock_adapter.set_secret.assert_called_once_with("X", "secretvalue")
```

### `tests/test_commands/test_variable.py`（新規）

`variable get` が値を直接 `print()` することを `capsys` で確認。

### 未対応サービスのテスト

Azure DevOps / Gogs / GitBucket / Backlog で `NotSupportedError` が送出されることを確認。
