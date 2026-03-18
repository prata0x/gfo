# コードレビュー統合結果: Phase 1〜6 (0e2d591..HEAD)

**レビュー日**: 2026-03-18
**対象**: 76ファイル、+13,239行（Phase 1〜6 全機能追加）
**ソース**: 7つの独立AIレビュー（review-1〜review-7）を統合・コード検証済み

---

## サマリー

| 重要度 | 件数 | 概要 |
|--------|------|------|
| **Critical** | **10** | セキュリティ脆弱性、バグ、ドキュメント不一致 |
| **Warning** | **14** | 動作上の問題、コード品質、ドキュメント不備 |
| **Info** | **6** | 改善提案、統一性の向上 |
| **合計** | **30** | |

### 除外した指摘（INVALID）

| 指摘 | 除外理由 |
|------|----------|
| GitHub `pin_issue`/`unpin_issue` REST API が存在しない (review-4) | REST エンドポイント `PUT/DELETE /repos/{owner}/{repo}/issues/{number}/pin` は存在する |
| GitHub `mark_pull_request_ready` 未実装 (review-5) | GitHub REST API にエンドポイントがなく（GraphQL のみ）、`NotSupportedError` は正しい動作 |
| review-6 の指摘 | 具体的なコード指摘なし（概要レベルの評価のみ） |

---

## Critical（10件）

### C-01: `download_release_asset` にパストラバーサル脆弱性

**ファイル**: `src/gfo/adapter/github.py`, `gitea.py`, `gitlab.py` の各 `download_release_asset`
**参照**: review-4 SEC-01, review-7 #1

API レスポンスの `name` フィールドをサニタイズせず `os.path.join(output_dir, asset_name)` に使用。
悪意あるアセット名（例: `../../.bashrc`）で `output_dir` 外に書き込み可能。

```python
# 現在のコード（github.py）
asset_name = meta_resp.json().get("name", f"asset-{asset_id}")
output_path = os.path.join(output_dir, asset_name)
```

**修正案**: `os.path.basename(asset_name)` でサニタイズし、解決後パスが `output_dir` 配下であることを検証する。

---

### C-02: `upload_file` / `upload_multipart` のリトライ時にファイル内容が消失

**ファイル**: `src/gfo/http.py:168-199`
**参照**: review-1 impl-C1, review-4 SEC-03, review-5 #2.1, review-7 #2

`_retry_loop` に渡すラムダ内で `f.read()` を呼び出すため、429 リトライ時にファイルポインタが末尾のまま空データが送信される。`upload_multipart` も同様の問題あり。

```python
# 現在のコード
with open(file_path, "rb") as f:
    return self._retry_loop(
        lambda: self._session.post(url, data=f.read(), ...)  # 2回目以降は b"" を送信
    )
```

**修正案**: ラムダの外で `data = f.read()` してから参照する。

---

### C-03: GitLab `migrate_repository` で認証トークンが clone URL に埋め込まれる

**ファイル**: `src/gfo/adapter/gitlab.py` `migrate_repository`
**参照**: review-1 impl-C3, review-4 SEC-02

```python
payload["import_url"] = clone_url.replace("://", f"://oauth2:{auth_token}@")
```

トークンが URL に直接埋め込まれ、GitLab サーバーログや API エラーの例外メッセージで漏洩するリスクがある。

**修正案**: エラー時のマスク処理を追加する。

---

### C-04: GitHub Release Asset Upload が `api.github.com` に誤送信

**ファイル**: `src/gfo/adapter/github.py` `upload_release_asset`
**参照**: review-1 impl-C2

GitHub のアセットアップロード先は `https://uploads.github.com` であるが、`api.github.com` に送信している。GitHub.com 環境では 404 または不正レスポンスになる。

**修正案**: Release 取得レスポンスの `upload_url` フィールドを使用する。

---

### C-05: GitLab `upload_release_asset` が HttpClient の内部 API に直接依存

**ファイル**: `src/gfo/adapter/gitlab.py` `upload_release_asset`
**参照**: review-1 impl-W2, review-4 ADAPTER-01

`self._client._retry_loop`, `self._client._session.post`, `self._client._handle_response` のプライベートメンバーに直接アクセス。Gitea 用の `upload_multipart` パブリックメソッドが存在するにもかかわらず使われていない。

**修正案**: `http.py` に GitLab uploads 用のパブリックメソッドを追加するか、既存の `upload_multipart` を利用する。

---

### C-06: `gfo package view` の引数がドキュメントと実装で不一致

**ファイル**: `docs/commands.md`, `docs/commands.ja.md`
**参照**: review-1 doc-C1, review-4 DOC-01

- ドキュメント: `gfo package view NAME [--type TYPE] [--version VERSION]`
- 実装: `gfo package view PACKAGE_TYPE NAME [--version VERSION]`（`package_type` が必須位置引数）

---

### C-07: `gfo package delete` の引数がドキュメントと実装で不一致

**ファイル**: `docs/commands.md`, `docs/commands.ja.md`
**参照**: review-1 doc-C2, review-4 DOC-01

- ドキュメント: `gfo package delete NAME [--type TYPE] [--version VERSION] [--yes]`
- 実装: `gfo package delete PACKAGE_TYPE NAME VERSION [--yes]`（3つ全て必須位置引数）

---

### C-08: `gfo label clone` の引数がドキュメントと実装で不一致

**ファイル**: `docs/commands.md`, `docs/commands.ja.md`
**参照**: review-1 doc-C3, review-4 DOC-02

- ドキュメント: `gfo label clone SOURCE_REPO [--host HOST] [--overwrite]`
- 実装: `gfo label clone --from SOURCE [--overwrite]`（`--host` は存在しない）

---

### C-09: `gfo issue migrate` が closed issue を open 状態で再作成する

**ファイル**: `src/gfo/commands/issue.py:257-274`
**参照**: review-3 #1, review-7 #10

`_migrate_one_issue()` は `dst.create_issue()` を呼ぶだけで、ソースの `issue.state` を反映しない。`--all` で closed issue も対象になるが、移行先では常に open 状態で作成される。

**修正案**: `create_issue()` 後に `issue.state == "closed"` であれば `dst.close_issue()` を呼ぶ。

---

### C-10: `ServiceSpec` に `slots=True` がない

**ファイル**: `src/gfo/commands/__init__.py:25`
**参照**: review-7 #3

プロジェクト規約では全データクラスに `frozen=True, slots=True` が必須だが、`ServiceSpec` は `@dataclass(frozen=True)` のみ。同ファイルの `BatchPrResult` と `MigrateResult` は正しく付与されている。

---

## Warning（14件）

### W-01: GitLab `delete_time_entry` が個別削除ではなく全リセット

**ファイル**: `src/gfo/adapter/gitlab.py` `delete_time_entry`
**参照**: review-1 impl-W6, review-5 nit

`entry_id` が無視され、`reset_spent_time` API が呼ばれて全ての記録時間がリセットされる。GitLab API に個別エントリ削除がないための制約だが、ユーザーにとって予期しない動作。

**修正案**: ドキュメントコメントで動作を明記するか、`entry_id` 指定時に警告を出す。

---

### W-02: Bitbucket `compare` で `ahead_by` / `behind_by` が常に 0

**ファイル**: `src/gfo/adapter/bitbucket.py` `compare`
**参照**: review-1 impl-W4

`CompareResult` の `total_commits`, `ahead_by`, `behind_by` が全て 0 で返される。API 制約によるものだが、利用者にとって誤解を招く。

**修正案**: 別途 commits API でカウントするか、制約をドキュメントに明記する。

---

### W-03: Gitea `compare` で `behind_by` が常に 0、`ahead_by` が `total_commits` と同値

**ファイル**: `src/gfo/adapter/gitea.py` `compare`
**参照**: review-1 impl-W5, review-2 minor

`behind_by` は API レスポンスにフィールドがないため常に 0。`ahead_by = total_commits` も必ずしも正しくない。

---

### W-04: Issue migration がコメント30件で暗黙的に切り捨てられる

**ファイル**: `src/gfo/commands/issue.py:265-269`
**参照**: review-3 #2, review-7 #10

`_migrate_one_issue()` が `src.list_comments("issue", number)` を `limit=0` なしで呼び出す。アダプターのデフォルト上限は30件のため、31件以上のコメントは警告なしに失われる。

**修正案**: `limit=0` を渡して全件取得する。

---

### W-05: `parse_service_spec()` が GitLab サブグループに対応していない

**ファイル**: `src/gfo/commands/__init__.py:147-156`
**参照**: review-3 #3, review-7 #10

非 Azure/Backlog サービスで `owner/repo` の2セグメント固定。`GitLabAdapter._project_path()` はサブグループに対応しているのに、`parse_service_spec()` は `group/subgroup/repo` を拒否する。

---

### W-06: `api.py` の `json.loads()` に `JSONDecodeError` ハンドリングがない

**ファイル**: `src/gfo/commands/api.py:39`
**参照**: review-2 major, review-4 W-api, review-7 #11

不正な JSON を `--data` に渡すとスタックトレースが表示される。

**修正案**: `try/except json.JSONDecodeError` で `ConfigError` に変換する。

---

### W-07: 広い例外捕捉 `except Exception` が9箇所で使用

**ファイル**: `github.py`, `gitlab.py`, `gitea.py`, `azure_devops.py`, `bitbucket.py`
**参照**: review-2 minor, review-4 W-横断, review-5 #2.3

`list_issue_templates` と `get_pipeline_logs` で `except Exception` による広い捕捉。認証エラーやメモリ不足も握りつぶされる。

**修正案**: `except (requests.RequestException, KeyError)` 等に限定する。

---

### W-08: `repo.py` がアダプターのプライベート属性 `_owner`, `_repo` に直接アクセス

**ファイル**: `src/gfo/commands/repo.py:179, 214, 330, 357, 366`
**参照**: review-2 major, review-4 W-cmd

複数箇所で `adapter._owner` / `adapter._repo` に直接アクセス。カプセル化違反。

**修正案**: `BaseAdapter` に `owner` / `repo` プロパティを追加する。

---

### W-09: `ci.py` のエラーメッセージが i18n 未対応

**ファイル**: `src/gfo/commands/ci.py:37`
**参照**: review-4 W-cmd, review-7 #8

`ConfigError(f"Invalid input format: ...")` が `_()` で囲まれていない。`from gfo.i18n import _` もインポートされていない。

---

### W-10: `gfo repo mirror sync` のドキュメントに実装にない引数が記載

**ファイル**: `docs/commands.md`, `docs/commands.ja.md`
**参照**: review-1 doc-W1, review-4 W-doc

- ドキュメント: `gfo repo mirror sync [MIRROR_ID]`
- 実装: 引数なし

---

### W-11: Review の対応サービスがドキュメントと実装で不一致

**ファイル**: `docs/commands.md`, `docs/commands.ja.md`
**参照**: review-4 DOC-03

- ドキュメント: GitHub, GitLab のみ
- 実装: Gitea, Forgejo, Azure DevOps, Bitbucket (approve only) も対応済み

---

### W-12: README Feature Support Matrix で Review の Gitea/Forgejo が誤って x

**ファイル**: `README.md`, `README.ja.md`
**参照**: review-4 DOC-04

Gitea/Forgejo は `list_reviews`/`create_review` を完全実装済みだが、Feature Matrix では x（未対応）と記載。

---

### W-13: `handle_dismiss`(review) / `handle_delete`(wiki) に成功メッセージがない

**ファイル**: `src/gfo/commands/review.py:35-39`, `src/gfo/commands/wiki.py:39-42`
**参照**: review-5 #3.1, #3.2

プロジェクト全体で delete/dismiss 系操作は `print(_("Deleted ..."))` パターンが確立されている（14箇所）が、この2箇所のみ無言で終了する。

---

### W-14: PR/Issue の各種操作に成功メッセージがない

**ファイル**: `src/gfo/commands/pr.py:46-59, 120-126, 129-139`, `src/gfo/commands/issue.py:78-89, 123, 131, 138`
**参照**: review-7 #4, #5, #6, #7

以下のハンドラが操作後にフィードバックを出力しない:
- `pr merge`, `pr close`, `pr reopen`, `pr update-branch`, `pr ready`
- `pr reviewers add/remove`
- `issue close`, `issue reopen`
- `issue reaction remove`, `issue depends add/remove`

---

## Info（6件）

### I-01: 型注釈が `base.py` のシグネチャと不一致

**ファイル**: `github.py`, `gitlab.py`, `gitea.py` 等の各アダプター
**参照**: review-1 W-1, review-4 W-型, review-5 #2.5

`update_repository`, `archive_repository`, `add_topic` 等で base.py には戻り値型があるが、アダプター側で省略されている。

---

### I-02: `add_topic` / `remove_topic` の重複ロジック

**ファイル**: `src/gfo/adapter/github.py`, `gitlab.py`
**参照**: review-5 #2.6

GitHub と GitLab で `list_topics()` → append/remove → `set_topics()` の同一ロジックがインライン展開されている。`base.py` のデフォルト実装に移動可能。

---

### I-03: GitLab `_resolve_user_ids` が存在しないユーザーをサイレントスキップ

**ファイル**: `src/gfo/adapter/gitlab.py:988-996`
**参照**: review-5 #2.4

`request_reviewers` で使用されるが、解決できなかったユーザー名に対する警告がない。

---

### I-04: `ssh_key_delete` / `gpg_key_delete` の CLI 引数に `type=int` がない

**ファイル**: `src/gfo/cli.py:724, 736`
**参照**: review-7 #9

同種の `webhook_delete`, `deploy_key_delete` では `type=int` が指定されているが、この2つでは省略されている。

---

### I-05: テスト規約の `fmt="json"` テスト・エラー伝搬テストが一部不足

**ファイル**: `tests/test_commands/test_package.py`, `test_wiki.py`, `test_search.py`, `test_review.py`
**参照**: review-1 ut-W1〜W4, review-4 W-test, review-5 #5.3

テスト規約（`.claude/rules/10-testing.md`）で必須とされている JSON 出力テストとエラー伝搬テストが不足。

---

### I-06: Forgejo テストの `list_issue_templates` が不適切なクラスにネスト

**ファイル**: `tests/test_adapters/test_forgejo.py:454-492`
**参照**: review-1 ut-C1

`list_issue_templates` の3テストが `TestDeleteInheritance` クラス内に配置されている。独立したテストクラスに移動すべき。

---

## 修正優先度

### P0: セキュリティ・即対応
1. C-01: パストラバーサル脆弱性
2. C-02: upload_file リトライ時空データ送信
3. C-03: GitLab トークン漏洩リスク
4. C-04: GitHub Asset Upload ドメイン誤り

### P1: ドキュメント不整合・ユーザー影響大
5. C-06〜C-08: package/label のドキュメント修正
6. C-09: issue migrate の closed issue 問題
7. W-04: コメント移行の切り捨て
8. W-05: GitLab サブグループ未対応
9. W-11〜W-12: ドキュメントのサービス対応表修正

### P2: コード品質
10. C-05: GitLab upload のカプセル化違反
11. C-10: ServiceSpec の slots=True 追加
12. W-06: api.py JSON エラーハンドリング
13. W-07: except Exception の限定化
14. W-08: プライベート属性アクセスの解消
15. W-13〜W-14: 成功メッセージの追加

### P3: 改善提案
16. W-01〜W-03: compare/time_entry の制約明記
17. W-09〜W-10: i18n/ドキュメント軽微修正
18. I-01〜I-06: 型注釈、DRY、テスト改善
