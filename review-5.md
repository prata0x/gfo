# コードレビュー: Phase 1〜6 機能追加（0e2d591..HEAD）

## 1. 変更概要

### コミット一覧

| コミット | Phase | 概要 |
|---------|-------|------|
| `db45378` | docs | Phase 1 実装（9機能）をドキュメントに反映 |
| `ef37835` | 2 | PR操作の拡充（9機能追加） |
| `8f62ef0` | docs | Phase 2 ドキュメント反映 |
| `156f37c` | 3 | Release/Repo管理の拡充（10機能追加） |
| `7273777` | docs | Phase 3 ドキュメント反映 |
| `4d1471e` | docs | Phase 3 ドキュメント反映 |
| `b774f15` | 4 | CI/セキュリティ/組織の拡充（8機能追加） |
| `7b60464` | docs | Phase 4 ドキュメント反映 |
| `b34572d` | 5 | Issue拡張/検索/ニッチ機能（14機能追加） |
| `df85182` | docs | Phase 5 ドキュメント反映 |
| `80cb44a` | docs | Phase 5 ドキュメント反映 |
| `9b317ec` | 6 | マルチサービス連携（issue migrate, batch pr create） |
| `7fa7879` | docs | Phase 6 ドキュメント反映 |

### ファイル統計

- **76 ファイル変更**: +13,239 行 / -175 行
- **テスト**: 2,552 → 2,612（+60テスト）
- **cli.py**: 719 → 1,053行（+334行、146コマンドのディスパッチ）

### Phase 別機能マトリクス

| Phase | 新規サブコマンド | 新規コマンドモジュール | アダプター拡張 |
|-------|----------------|---------------------|-------------|
| 1 | 9 | — (既存拡張) | base.py + 8サービス |
| 2 | 9 | review.py | 同上 |
| 3 | 10 | wiki.py | 同上 |
| 4 | 8 | ci.py, org.py, gpg_key.py, tag_protect.py | 同上 |
| 5 | 14 | search.py, issue_template.py, schema.py | 同上 |
| 6 | 2 | batch.py, api.py | 同上 |
| **合計** | **52+** | **10 新規** | **9 アダプター** |

---

## 2. アダプター層レビュー

### 2.1 `upload_file` の lambda 内 `f.read()` — リトライ時に空データ送信

**重大度: Critical**

`http.py:171-180`

```python
with open(file_path, "rb") as f:
    return self._retry_loop(
        lambda: self._session.post(
            url,
            params=merged_params,
            data=f.read(),
            headers=upload_headers,
            timeout=timeout,
        )
    )
```

`_retry_loop`（http.py:63-78）は 429 レートリミット時にリトライする。初回の `f.read()` でファイルポインタが末尾に移動するため、2回目以降のリトライでは `data=b""` が送信される。

**推奨修正**: lambda の先頭で `f.seek(0)` を呼ぶか、先に `data = f.read()` してから lambda で参照する。

```python
with open(file_path, "rb") as f:
    data = f.read()
return self._retry_loop(
    lambda: self._session.post(
        url, params=merged_params, data=data, ...
    )
)
```

---

### 2.2 GitHub `mark_pull_request_ready` 未実装

**重大度: Warning**

`base.py:691-692` で定義:
```python
def mark_pull_request_ready(self, number: int) -> None:
    raise NotSupportedError(self.service_name, "pr ready")
```

全 7 アダプター中、**GitHub だけ** がオーバーライドしていない:
- Azure DevOps: `azure_devops.py:345` — 実装あり
- Bitbucket: `bitbucket.py:677` — 実装あり
- Gitea: `gitea.py:631` — 実装あり
- GitBucket: `gitbucket.py:107` — 実装あり（NotSupportedError）
- GitLab: `gitlab.py:1032` — 実装あり
- Gogs: `gogs.py:131` — 実装あり（NotSupportedError）

GitHub は GraphQL の `markPullRequestReadyForReview` mutation で draft→ready 変更が可能。REST API では直接的なエンドポイントがないため、意図的な省略と推測されるが、`gfo pr ready` コマンドが GitHub で `NotSupportedError` になるのはユーザー体験として問題がある。

---

### 2.3 広い例外捕捉 `except Exception`

**重大度: Warning**

以下の箇所で `except Exception` による広い例外捕捉が使用されている:

| ファイル | 行 | コンテキスト |
|---------|-----|------------|
| `github.py:165` | `list_issue_templates` | テンプレートディレクトリ取得失敗時 |
| `github.py:185` | `list_issue_templates` | 個別テンプレートファイル取得失敗時（`nosec` コメント付き） |
| `github.py:1020` | `get_pipeline_logs` | ジョブログ取得失敗時 |
| `gitlab.py:296` | `list_issue_templates` | テンプレート取得失敗時 |
| `gitlab.py:1397` | `get_pipeline_logs` | ジョブログ取得失敗時 |
| `azure_devops.py:468` | `list_issue_templates` | ワークアイテムタイプ取得失敗時 |
| `azure_devops.py:1218` | `get_pipeline_logs` | ログ取得失敗時 |
| `bitbucket.py:987` | `get_pipeline_logs` | ステップログ取得失敗時 |
| `gitea.py:173` | `list_issue_templates` | テンプレート取得失敗時 |

**パターン分析**: 2 つのユースケースに集中している:
1. **`list_issue_templates`**: API が当該機能を未サポートの場合に空リストを返す — 意図は理解できるが `requests.RequestException` で十分
2. **`get_pipeline_logs`**: 個別ジョブ/ステップのログ取得失敗をスキップ — 同様に `requests.RequestException` + `KeyError` で限定可能

**推奨**: `except (requests.RequestException, KeyError)` 等に限定し、予期しない例外（メモリ不足、型エラー等）が握りつぶされるのを防ぐ。

---

### 2.4 GitLab `_resolve_user_ids()` サイレントスキップ

**重大度: Info**

`gitlab.py:988-996`

```python
def _resolve_user_ids(self, usernames: list[str]) -> list[int]:
    ids: list[int] = []
    for name in usernames:
        resp = self._client.get("/users", params={"username": name})
        users = resp.json()
        if users:
            ids.append(users[0]["id"])
    return ids
```

`request_reviewers`（gitlab.py:998）で使用されるが、存在しないユーザー名が指定された場合にサイレントにスキップされる。ユーザーが「reviewer を追加した」と思っても実際には追加されないケースが起きうる。

**推奨**: 解決できなかったユーザー名を警告ログに出力するか、オプションで例外を送出する。

---

### 2.5 型注釈の不一致

**重大度: Info**

`base.py` の抽象メソッドには型注釈が明示されているが、一部のアダプター実装では省略されている:

| メソッド | base.py | GitHub/GitLab/Gitea |
|---------|---------|-------------------|
| `update_repository` | `-> Repository` | 戻り型省略 |
| `archive_repository` | `-> None` | 戻り型省略 |
| `add_topic` / `remove_topic` | `-> list[str]` | 戻り型省略 |
| `set_topics` | `-> list[str]` | 戻り型省略 |

例（`github.py:253`）:
```python
def update_repository(self, *, description=None, private=None, default_branch=None):
```

base.py（754-761行）:
```python
def update_repository(
    self,
    *,
    description: str | None = None,
    private: bool | None = None,
    default_branch: str | None = None,
) -> Repository:
```

機能上の問題はないが、mypy strict モードでは警告が出る。Gogs アダプター（`gogs.py:445`）のように型注釈を明示しているものもあり、統一が望ましい。

---

### 2.6 `add_topic` / `remove_topic` の重複ロジック

**重大度: Info**

GitHub（`github.py:279-289`）と GitLab（`gitlab.py:368-378`）で完全に同一のロジック:

```python
def add_topic(self, topic):
    current = self.list_topics()
    if topic not in current:
        current.append(topic)
    return self.set_topics(current)

def remove_topic(self, topic):
    current = self.list_topics()
    if topic in current:
        current.remove(topic)
    return self.set_topics(current)
```

Gitea（`gitea.py:242-248`）は `PUT /topics/{topic}` と `DELETE /topics/{topic}` の専用エンドポイントを使用する別実装。

**推奨**: GitHub/GitLab 共通のロジックは `base.py` のデフォルト実装に移動可能。`list_topics()` と `set_topics()` を実装するだけで自動的に `add_topic`/`remove_topic` が使えるようになる。

---

## 3. コマンド層レビュー

### 3.1 `review.py:handle_dismiss` — 完了メッセージ欠落

**重大度: Warning**

`src/gfo/commands/review.py:35-39`

```python
def handle_dismiss(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    adapter = get_adapter()
    adapter.dismiss_review(args.number, args.review_id, message=args.message or "")
```

プロジェクト全体で delete/dismiss 系操作は完了メッセージを出力するパターンが確立されている（14箇所で確認）:
```python
# 例: commands/label.py:51
print(_("Deleted label '{name}'.").format(name=name))
# 例: commands/release.py:44
print(_("Deleted release '{tag}'.").format(tag=tag))
```

`handle_dismiss` のみメッセージなしで無言終了する。

**推奨修正**:
```python
adapter.dismiss_review(args.number, args.review_id, message=args.message or "")
print(_("Dismissed review '{review_id}'.").format(review_id=args.review_id))
```

---

### 3.2 `wiki.py:handle_delete` — 削除メッセージ欠落

**重大度: Warning**

`src/gfo/commands/wiki.py:39-42`

```python
def handle_delete(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    adapter = get_adapter()
    adapter.delete_wiki_page(args.id)
```

同じ `wiki.py` 内の `handle_create`/`handle_update` は `output()` で結果を出力しているが、`handle_delete` だけ無言。他の delete 系（label, milestone, release, repo 等 14箇所）はすべて `print(_("Deleted ..."))` パターンに従っている。

**推奨修正**:
```python
adapter.delete_wiki_page(args.id)
print(_("Deleted wiki page '{id}'.").format(id=args.id))
```

---

### 3.3 CLI 統合（cli.py）

**重大度: Info（問題なし）**

`src/gfo/cli.py`（1,053行）は 146 コマンドのディスパッチテーブルを含む。Phase 1〜6 で +334 行追加。

確認事項:
- 新規 10 コマンドモジュールのインポートが正しく追加されている
- サブコマンドのパーサー定義とハンドラのマッピングが一貫している
- `--format` / `--jq` オプションが全コマンドに統一的に渡されている

---

## 4. HTTP 層レビュー

### 4.1 新規メソッド

3 つの新規メソッドが `http.py` に追加:

| メソッド | 行 | 用途 |
|---------|-----|------|
| `download_file` | 132-153 | ストリーミングダウンロード（release asset 取得用） |
| `upload_file` | 155-180 | raw binary アップロード（GitHub release asset 用） |
| `upload_multipart` | 182- | multipart/form-data アップロード（Gitea 用） |

**`download_file`**: ストリーミング `resp.iter_content(chunk_size=8192)` で大きなファイルも対処。エラーハンドリングは既存の `_handle_response` + `requests.RequestException` 捕捉で適切。問題なし。

**`upload_file`**: セクション 2.1 で指摘した lambda 内 `f.read()` のリトライ問題あり。

**`upload_multipart`**: `upload_file` と同様に `_retry_loop` を使用。こちらはファイルを `files` パラメータで渡すため、`requests` が内部的にファイルハンドルを管理する点で同様のリトライ問題がありうる。

---

## 5. テスト層レビュー

### 5.1 テスト統計

- **テスト総数**: 2,612（+60）
- **テストファイル変更**: 30 ファイル（新規 15 + 既存拡張 15）
- **注目**: `test_service_spec.py`（380行、39テスト）は新規追加で最もエッジケースが充実

### 5.2 `test_service_spec.py` — 優良

**重大度: Info（優良事例）**

`tests/test_commands/test_service_spec.py` は以下のケースを網羅:
- SaaS デフォルトホスト解決（GitHub/GitLab/Bitbucket）
- セルフホスト型の明示的ホスト指定
- Azure DevOps の特殊パス構造
- エラーケース（不正なフォーマット、未知のサービス）

テストの品質が高く、他のコマンドテストの模範になる。

### 5.3 コマンドテストのカバレッジ

**重大度: Warning**

新規コマンドテストの多くは `patch_adapter()` によるモック経由で実装されており、アダプター実装コードパスは迂回される。これ自体はコマンド層のテストとして正しいが、アダプター側のテストとの組み合わせで全体カバレッジを確保する必要がある。

**エラーケーステストの不足**:
- `test_batch.py`（200行）: 正常系は充実しているがエラーケース（部分失敗、ネットワークエラー）が少ない
- `test_ci.py`（100行）: `HttpError` 伝搬テストがない
- `test_gpg_key.py`（90行）: 正常系のみ

テスト規約（`.claude/rules/10-testing.md`）では以下が必須とされている:
> - エラー伝搬テスト: adapter が HttpError を投げた場合の伝搬を検証すること

新規コマンドモジュールの一部でこの規約が満たされていない。

---

## 6. ドキュメントレビュー

**重大度: Info（問題なし）**

各 Phase 実装後にドキュメント更新コミットが追加されている:
- `README.md` / `README.ja.md`: +75 行（サポートコマンド一覧更新）
- `docs/commands.md` / `docs/commands.ja.md`: +989 行（新コマンドリファレンス）
- `docs/roadmap/`: Phase 別進捗更新
- `docs/authentication.md` / `docs/authentication.ja.md`: +17 行

日英の双方に一貫して更新されており、Phase-to-docs の追跡が明確。

---

## 7. 総合評価

### スコアカード

| カテゴリ | 評価 |
|---------|------|
| 機能網羅性 | **Excellent** — 52+ サブコマンドを 9 アダプターに一貫実装 |
| コード一貫性 | **Good** — パターンが統一されている（一部例外あり） |
| テスト | **Good** — 2,612 テスト、一部エラーケース不足 |
| ドキュメント | **Excellent** — 日英同時更新、Phase 追跡明確 |
| 安全性 | **Good** — 1件の Critical あり（upload_file リトライ） |

### 推奨修正事項

#### Critical（修正必須）

| # | 問題 | 箇所 | セクション |
|---|------|------|-----------|
| C1 | `upload_file` の lambda 内 `f.read()` がリトライ時に空データ送信 | `http.py:171-180` | 2.1 |

#### Warning（修正推奨）

| # | 問題 | 箇所 | セクション |
|---|------|------|-----------|
| W1 | GitHub `mark_pull_request_ready` 未実装 | `github.py` | 2.2 |
| W2 | 広い例外捕捉 `except Exception`（9箇所） | 複数ファイル | 2.3 |
| W3 | `review.py:handle_dismiss` 完了メッセージ欠落 | `review.py:35-39` | 3.1 |
| W4 | `wiki.py:handle_delete` 削除メッセージ欠落 | `wiki.py:39-42` | 3.2 |
| W5 | 新規コマンドテストのエラーケース不足 | `test_batch.py` 等 | 5.3 |

#### Info（改善提案）

| # | 問題 | 箇所 | セクション |
|---|------|------|-----------|
| I1 | GitLab `_resolve_user_ids` サイレントスキップ | `gitlab.py:988-996` | 2.4 |
| I2 | 型注釈の base.py との不一致 | 複数ファイル | 2.5 |
| I3 | `add_topic`/`remove_topic` 重複ロジック | `github.py`/`gitlab.py` | 2.6 |
