# release-create-target

## 概要

`release create` に `--target` オプションを追加し、リリースのターゲットブランチまたはコミット SHA を指定できるようにする。
gh / glab はいずれも `--target` オプションを提供しており、gfo もこれに合わせる。

- **種別**: 機能追加
- **優先度**: Phase 2（独立して実施可能）

## 変更後

```
gfo release create v1.0 --target main
gfo release create v1.0 --target abc1234
gfo release create v1.0                   # target 未指定（デフォルトブランチ）
```

## 実装手順

### 1. アダプター基底クラス (`src/gfo/adapter/base.py`)

`create_release` のシグネチャに `target` パラメータ追加:

```python
def create_release(
    self, *, tag: str, title: str = "", notes: str = "",
    draft: bool = False, prerelease: bool = False,
    target: str | None = None,
) -> Release: ...
```

### 2. 各アダプター実装

| サービス | API フィールド | 備考 |
|---|---|---|
| GitHub | `target_commitish` | POST body に追加 |
| GitLab | `ref` | POST body に追加 |
| Gitea | `target_commitish` | POST body に追加 |
| GitBucket | `target_commitish` | POST body に追加（API サポート確認要） |
| Bitbucket | - | release 未サポート |
| Azure DevOps | - | release 未サポート |
| Backlog | - | release 未サポート |
| Gogs | - | release 未サポート |

### 3. CLI パーサー定義 (`src/gfo/cli.py`)

```python
release_create.add_argument("--target", help=_("Target branch or commit SHA"))
```

### 4. コマンドハンドラー (`src/gfo/commands/release.py`)

`handle_create` で `args.target` を `adapter.create_release(target=target)` に渡す:

```python
def handle_create(args, *, fmt, jq=None):
    tag = (args.tag or "").strip()
    if not tag:
        raise ConfigError(_("tag must not be empty."))
    adapter = get_adapter()
    title = (args.title or "").strip() or tag
    release = adapter.create_release(
        tag=tag,
        title=title,
        notes=args.notes or "",
        draft=args.draft,
        prerelease=args.prerelease,
        target=getattr(args, "target", None),
    )
    output(release, fmt=fmt, jq=jq)
```

### 5. テスト

- `tests/test_commands/test_release.py` に `--target` のテスト追加
- 各アダプターのテストで target パラメータの API マッピングを確認
- target 未指定時のデフォルト動作テスト

### 6. ドキュメント更新

- `docs/commands.md` / `.ja.md`: `release create` のオプション一覧に `--target` を追加
- `docs/cli-comparison.md`: 3.4 の create オプション比較表で gfo 列を更新
- `docs/cli-alignment.md`: 完了後にステータス更新
