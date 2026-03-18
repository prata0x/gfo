# コードレビュー: `0e2d591..HEAD`（Phase 1〜6）

**対象**: 76ファイル、+13,239行
**レビュー日**: 2026-03-18
**レビュー方法**: 4つのサブエージェントで並行レビュー（単体テスト・統合テスト・実装・ドキュメント）

---

## 総合サマリー

| カテゴリ | Critical | Warning | Info |
|---|---|---|---|
| 実装コード | 2 | 7 | 7 |
| 単体テスト | 1 | 11 | 7 |
| 統合テスト | 2 | 3 | 4 |
| ドキュメント | 3 | 6 | 9 |
| **合計** | **8** | **27** | **27** |

### Critical 一覧（対応必須）

| ID | カテゴリ | 内容 |
|---|---|---|
| impl-C1 | 実装 | `http.py` upload_file/upload_multipart のリトライ時にファイルが再読できない |
| impl-C2 | 実装 | GitHub Release Asset Upload が `api.github.com` に誤送信（`uploads.github.com` が正しい） |
| impl-C3 | 実装 | GitLab `migrate_repository` で認証トークンが clone_url に埋め込まれている |
| ut-C1 | 単体テスト | Forgejo テストの `list_issue_templates` が `TestDeleteInheritance` クラス内にネスト |
| it-C1 | 統合テスト | Phase 1〜6 の新機能 64 メソッドに統合テストが一切追加されていない |
| it-C2 | 統合テスト | ドキュメントのカバレッジ表が実態と乖離（「o」記載だが実テストなし） |
| doc-C1 | ドキュメント | `gfo package view` の引数がドキュメントと実装で異なる |
| doc-C2 | ドキュメント | `gfo package delete` の引数がドキュメントと実装で異なる |
| doc-C3 | ドキュメント | `gfo label clone` の引数がドキュメントと実装で異なる |

---

# 1. 実装コード レビュー

## 対象: `src/gfo/` の変更

## 1.1 アーキテクチャ・設計

### [Info] 全体設計は既存パターンと良好に整合

base.py の抽象メソッド定義 -> 各 adapter での具象実装 -> commands/ のハンドラーという三層構造が一貫して守られています。新規データクラスも全て `frozen=True, slots=True` で統一されています。新モジュール（api.py, batch.py, ci.py, gpg_key.py, issue_template.py, org.py, search.py, tag_protect.py, wiki.py, package.py）も commands/ 配下の既存パターンに沿っています。

### [Info] commands/__init__.py の ServiceSpec / parse_service_spec の追加は適切

Issue migrate と batch PR create に必要なマルチサービス指定パーサーが `commands/__init__.py` に追加されています。`create_adapter_from_spec` も既存の `create_adapter` と整合した実装です。

---

## 1.2 コード品質

### [Warning] 型ヒントの欠落 -- 複数の adapter メソッドで戻り値型が省略されている

**ファイル**: `src/gfo/adapter/github.py`, `gitlab.py`, `bitbucket.py`, `azure_devops.py`, `gitea.py`

`update_repository`, `archive_repository`, `get_languages`, `list_topics`, `set_topics`, `add_topic`, `remove_topic`, `compare`, `get_latest_release`, `list_release_assets`, `upload_release_asset`, `download_release_asset`, `delete_release_asset` 等、多くの新規メソッドで戻り値型アノテーションが省略されています。

base.py では明示的に定義されています:
```python
def update_repository(self, *, description: str | None = None, ...) -> Repository:
```

しかし各 adapter 側の実装は:
```python
def update_repository(self, *, description=None, private=None, default_branch=None):  # 戻り値型なし
```

**影響**: mypy でエラーが出ないとしても、読み手にとっての可読性が下がり、IDE の補完が利かなくなります。既存コード（Phase 1-4 で追加されたメソッド）は全て型ヒント付きなので、統一性を保つべきです。

**改善案**: base.py と同じシグネチャを各 adapter にコピーする。

---

### [Warning] GitLab upload_release_asset が HttpClient の内部 API に直接アクセスしている

**ファイル**: `src/gfo/adapter/gitlab.py` 行 537-543

```python
upload_resp = self._client._retry_loop(
    lambda: self._client._session.post(
        self._client.base_url + url,
        files=files,
        timeout=300,
    )
)
self._client._handle_response(upload_resp)
```

`_retry_loop`, `_session`, `_handle_response` はいずれも `HttpClient` のプライベートメンバーです。Gitea 用には `upload_multipart` というパブリックメソッドが `http.py` に追加されているのに、GitLab ではそれを使わずプライベート API に直接アクセスしています。

**影響**: `HttpClient` の内部構造が変更されると GitLab adapter が壊れます。また認証ヘッダーが `_session.headers` に含まれているため動作はしますが、`_auth_params`（Backlog の apiKey パラメータ）が適用されず、将来の認証方式変更時に問題が起きる可能性があります。

**改善案**: `http.py` に GitLab uploads 用のパブリックメソッドを追加するか、既存の `upload_multipart` を利用するように修正する。

---

### [Info] DRY -- Reaction の _to 変換が adapter ごとにインライン展開されている

GitHub, GitLab, Gitea の `list_issue_reactions` / `add_issue_reaction` で `Reaction(id=..., content=..., user=..., created_at=...)` の構築が各所でインライン展開されています。`_to_reaction` のような共通変換メソッドを `GitHubLikeAdapter` に追加すると良いですが、各サービスのフィールド名が微妙に異なるため（GitLab は Award Emoji API で `user.username`、Gitea は `user.login`）、現状のままでも大きな問題ではありません。

---

## 1.3 セキュリティ

### [Critical] GitLab migrate_repository で認証トークンが clone_url に埋め込まれている

**ファイル**: `src/gfo/adapter/gitlab.py` 行 408 付近

```python
if auth_token:
    payload["import_url"] = clone_url.replace("://", f"://oauth2:{auth_token}@")
```

トークンが URL 文字列に直接埋め込まれています。この URL はそのまま GitLab API に JSON ペイロードとして送信されますが:

1. GitLab サーバー側のログにトークン付き URL が記録される可能性がある
2. API エラー時に `HttpError` の例外メッセージにトークン付き URL が含まれ、標準エラーに出力される可能性がある
3. `clone_url` に既にクエリパラメータが含まれている場合、URL が壊れる

**改善案**: GitLab の Project Import API はヘッダーベースの認証にも対応しているか確認する。対応していない場合でも、エラーメッセージのマスキングを確保すべき。

---

### [Warning] api.py がアダプター層をバイパスして任意 API リクエストを送信する

**ファイル**: `src/gfo/commands/api.py` 行 32-47

これは設計意図通りですが、`--data` パラメータで任意の JSON を送信できるため、ユーザーが意図せず破壊的操作（DELETE, リポジトリ変更等）を実行するリスクがあります。

**改善案**: 必須ではないが、`--data` が指定された場合にワンライナーのワーニングを stderr に出力することを検討。

---

### [Info] URL 構築は quote() で適切にサニタイジングされている

ほぼ全ての URL パス構築で `quote(value, safe='')` が使用されており、パスインジェクションリスクは低い。

---

## 1.4 バグ・論理エラー

### [Critical] http.py upload_file でリトライ時にファイルが再読できない

**ファイル**: `src/gfo/http.py` 行 171-180

```python
with open(file_path, "rb") as f:
    return self._retry_loop(
        lambda: self._session.post(
            url,
            params=merged_params,
            data=f.read(),
            ...
        )
    )
```

`_retry_loop` は 429 (RateLimitError) 時にラムダを再実行しますが、`f.read()` は最初の呼び出しで全バイトを読み切るため、2回目以降は空のデータが送信されます。

**改善案**:
```python
with open(file_path, "rb") as f:
    data = f.read()
return self._retry_loop(
    lambda: self._session.post(url, params=merged_params, data=data, ...)
)
```

同様の問題は `upload_multipart` (行 190-198) にもあります。`files` 辞書内のファイルオブジェクトが2回目の `_retry_loop` 実行時には EOF になっています。

---

### [Critical] GitHub Release Asset Upload が api.github.com に誤送信

**ファイル**: `src/gfo/adapter/github.py` 行 409

```python
upload_path = f"/repos/{...}/releases/{release_id}/assets"
resp = self._client.upload_file(upload_path, file_path, name=name)
```

GitHub の公式ドキュメントでは、アセットアップロード先は `https://uploads.github.com/repos/{owner}/{repo}/releases/{release_id}/assets` であり、`api.github.com` ではありません。このコードは `api.github.com` にポストするため、GitHub.com 環境では 404 もしくは不正なレスポンスになる可能性が高いです。

**改善案**: Release 取得レスポンスの `upload_url` フィールドを使用する。

---

### [Warning] GitHub search_pull_requests で "merged" ステートの PR が正しく判定されない可能性

**ファイル**: `src/gfo/adapter/github.py` 行 1608-1611

```python
state="merged" if pr_data.get("merged_at") else r["state"],
```

Search API のレスポンスで `pull_request` オブジェクトの中に `merged_at` が含まれるかどうかは API バージョンに依存します。含まれない場合、マージ済み PR でも `state="closed"` になります。

---

### [Warning] Bitbucket compare で ahead_by / behind_by が常に 0

**ファイル**: `src/gfo/adapter/bitbucket.py` 行 310-317

```python
return CompareResult(
    total_commits=0,
    ahead_by=0,
    behind_by=0,
    files=files,
)
```

Bitbucket の diffstat API からは commit 数を取得できないという制約は理解できますが、CompareResult のドキュメントには「コミット数」「ahead/behind」が主要フィールドとして定義されているため、全て 0 を返すのは利用者にとって誤解を招きます。

**改善案**: 別途 commits API を呼んで `total_commits` を埋めるか、少なくともドキュメントコメントで制約を明記する。

---

### [Warning] Gitea compare で behind_by が常に 0、ahead_by が total_commits と同じ

**ファイル**: `src/gfo/adapter/gitea.py` 行 268-271

```python
return CompareResult(
    total_commits=data.get("total_commits", 0),
    ahead_by=data.get("total_commits", 0),
    behind_by=0,
    ...
)
```

Gitea の compare API レスポンスに `behind_by` 相当のフィールドがない場合は仕方ないですが、`ahead_by = total_commits` は必ずしも正しくありません（total_commits は両方向の合計の場合がある）。

---

### [Warning] GitLab delete_time_entry がリセット操作になっている

**ファイル**: `src/gfo/adapter/gitlab.py` 行 1856-1860

```python
def delete_time_entry(self, issue_number: int, entry_id: int | str) -> None:
    self._client.post(
        f"{self._project_path()}/issues/{issue_number}/reset_spent_time",
        json={},
    )
```

`entry_id` が無視され、指定した1エントリではなく全ての記録時間がリセットされます。GitLab API の制約（個別エントリ削除 API がない）によるものと推測されますが、利用者にとって予期しない動作です。

**改善案**: 最低限、この動作をドキュメントコメントで明記するか、`entry_id` が渡されたときに警告を出す。

---

### [Info] Azure DevOps add_time_entry が累積ではなく上書き

**ファイル**: `src/gfo/adapter/azure_devops.py` 行 1537

```python
{"op": "add", "path": "/fields/Microsoft.VSTS.Scheduling.CompletedWork", "value": hours}
```

これは Work Item の CompletedWork フィールドを設定するため、呼ぶたびに前の値が上書きされます。累積にするには現在値を取得して加算する必要があります。

---

### [Info] Gitea get_latest_release は "最新" ではなく "最初のリリース" を返す可能性

**ファイル**: `src/gfo/adapter/gitea.py` 行 360-370

```python
results = paginate_link_header(
    self._client,
    f"{self._repos_path()}/releases",
    limit=1,
    per_page_key="limit",
)
```

Gitea の releases API がデフォルトで作成日降順にソートされていれば問題ありませんが、ソート順が保証されていない場合は最新リリースを返すとは限りません。GitBucket にも同様の実装があります。

---

## 1.5 サービス間の一貫性

### [Warning] Forgejo adapter (forgejo.py) に新機能が追加されていない

変更ファイル一覧に `forgejo.py` が含まれていません。Forgejo は `GiteaAdapter` のサブクラスなので、Gitea の新機能は全て継承されますが、差分が0行ということは Forgejo 固有のオーバーライドが不要だったことを意味します。これ自体は問題ありませんが、念のため確認。

**確認済み**: `src/gfo/adapter/forgejo.py` は変更ファイルリストに含まれていない -- Gitea の全メソッドをそのまま継承するため OK。

---

### [Info] NotSupportedError の網羅性は良好

Gogs は Gitea の全新機能に対して NotSupportedError をオーバーライドしています。GitBucket も同様。Bitbucket は `request_reviewers` / `remove_reviewers` / `mark_pull_request_ready` に NotSupportedError を定義済み。Azure DevOps の `get_pull_request_diff` も NotSupportedError を raise しています。

---

### [Warning] Bitbucket search_pull_requests の query フィルタが不正確な可能性

**ファイル**: `src/gfo/adapter/bitbucket.py` 行 1329-1330

```python
if query:
    params["q"] = f'title ~ "{query}"'
```

Bitbucket の `q` パラメータは BBQL 構文です。ユーザー入力の `query` にダブルクォートが含まれている場合、BBQL が壊れます。

**改善案**: query 文字列のエスケープ処理を追加するか、最低限ダブルクォートを除去する。

---

### [Info] update_repository の各 adapter 実装の差異は適切

- GitHub: `private` フィールド直接
- GitLab: `visibility: "private"/"public"` に変換
- Bitbucket: `is_private` フィールド、default_branch 変更不可
- Azure DevOps: description/private 変更不可（defaultBranch のみ）

各サービスの API 差異が適切に吸収されています。

---

## 1.6 その他

### [Info] from __future__ import annotations は全 commands/ に適用済み

確認の結果、全ての新規 commands/ ファイルに `from __future__ import annotations` が含まれています。規約準拠。

---

### [Info] 新規データクラスは全て frozen=True, slots=True で定義済み

`CheckRun`, `PullRequestFile`, `PullRequestCommit`, `CompareFile`, `CompareResult`, `ReleaseAsset`, `Reaction`, `TimelineEvent`, `Commit`, `Package`, `TimeEntry`, `PushMirror`, `WikiRevision`, `IssueTemplate`, `GpgKey`, `TagProtection` -- 全て規約通り。

---

## 実装コード サマリー

| 深刻度 | 件数 | 主な内容 |
|---|---|---|
| Critical | 2 | http.py upload_file/upload_multipart のリトライ時ファイル再読不能; GitHub Asset Upload が api.github.com に誤送信 |
| Warning | 7 | 型ヒント欠落; GitLab adapter がプライベート API 使用; GitLab delete_time_entry がリセット動作; Bitbucket compare 値 0; Gitea compare behind_by 不正確; Bitbucket search_prs の BBQL インジェクション; GitLab migrate_repository のトークン埋め込み |
| Info | 7 | 設計パターン整合性良好; DRY の改善余地; NotSupportedError 網羅性良好; update_repository のサービス差異は適切; コーディング規約準拠 |

**全体的な評価**: 約50機能の大規模追加にもかかわらず、既存のアーキテクチャパターンに沿った一貫性のある実装です。Critical な2件（http.py のリトライ時ファイル再読問題、GitHub Asset Upload のドメイン問題）は実運用で確実に問題になるため、優先的に修正すべきです。Warning レベルの型ヒント欠落は、一括で対応可能な機械的修正です。

---

# 2. 単体テスト コードレビュー

## 対象: 29ファイル（tests/integration/ 除外）

## 2.1 テスト品質

### Critical

**(C-1) `tests/test_adapters/test_forgejo.py` 454-492行目: `list_issue_templates` テストが `TestDeleteInheritance` クラス内にネストされている**

Forgejo の `test_list_issue_templates`, `test_list_issue_templates_empty`, `test_list_issue_templates_not_found` の3テストメソッドが `TestDeleteInheritance` クラスの中に追加されています。機能的にはテスト自体は動作しますが、`list_issue_templates` は delete 継承動作とは無関係であり、テストのグルーピングとして不適切です。

**改善案**: 独立した `TestListIssueTemplatesForgejo` クラスを作成し、`TestDeleteInheritance` クラスの外に配置する。Gitea の `TestListIssueTemplatesGitea` テストクラス（`test_gitea.py`）と同じ構造にする。

---

### Warning

**(W-1) `tests/test_commands/test_package.py`: テストケースが最小限すぎる**

`handle_list`, `handle_view`, `handle_delete` の各テストが各1ケースのみで、以下が不足しています:
- `fmt="json"` テスト（テスト規約 `10-testing.md` で必須とされている）
- エラー伝搬テスト（`HttpError` / `NotSupportedError`）
- `handle_delete` の確認プロンプトテスト（`yes=False` で `input` をパッチしたテスト）
- 空リスト `[]` テスト

**(W-2) `tests/test_commands/test_wiki.py` `TestHandleRevisions`: テストが1ケースのみ**

`handle_revisions` の正常系 table 出力のみ。以下が不足:
- `fmt="json"` テスト
- エラー伝搬テスト
- 空リスト `[]` テスト

**(W-3) `tests/test_commands/test_search.py` `TestHandlePrs` / `TestHandleCommits`: テストが各1ケースのみ**

正常系の adapter 呼び出し確認のみ。以下が不足:
- `fmt="json"` テスト
- エラー伝搬テスト

**(W-4) `tests/test_commands/test_review.py` `TestHandleDismiss`: `fmt="json"` テストが不足**

正常系2ケース（メッセージあり/なし）はあるが、JSON 出力テストとエラー伝搬テストがない。

**(W-5) 複数のアダプターテストファイルで `import json as _json` / `import json as json_mod` がメソッド内ローカルインポートされている**

該当箇所:
- `tests/test_adapters/test_azure_devops.py` `TestMarkPullRequestReadyAzure.test_mark_ready` 内の `import json as _json`
- `tests/test_adapters/test_azure_devops.py` `TestMigrateRepository.test_migrate_with_auth_token` 内の `import json as json_mod`
- `tests/test_adapters/test_github.py` `TestMigrateRepository.test_migrate_with_auth_token` 内の `import json as json_mod`
- `tests/test_adapters/test_gitlab.py` `TestMigrateRepository` の複数テスト内の `import json as json_mod`
- `tests/test_adapters/test_gitea.py` `TestMigrateRepository.test_migrate_with_options` 内の `import json as json_mod`

これらのファイルはすべてファイル先頭で `import json` 済みです。メソッド内でのリネームインポートは不要であり、コード上の一貫性を損なっています。

**改善案**: メソッド内の `import json as _json` / `import json as json_mod` を削除し、ファイル先頭の `json` をそのまま使う。

**(W-6) `tests/test_commands/test_label.py` `TestHandleClone`: パッチ対象が多く脆弱**

`test_clone_labels` が6つの `patch()` を使っており、内部実装に強く依存しています。`patch_adapter` パターンと比べてメンテナンスコストが高い。

**改善案**: `handle_clone` の内部で使うヘルパー関数レベルでのパッチに整理するか、少なくともテスト内コメントで各パッチの意図を説明する。

**(W-7) `tests/test_commands/test_batch.py`: `parse_service_spec` の戻り値が MagicMock**

`_make_spec()` が MagicMock を返しているが、`parse_service_spec` は本来 `ServiceSpec` データクラスを返す。MagicMock だと属性アクセスが何でも通るため、テストが本来なら失敗すべきケースを見逃す可能性がある。

**改善案**: `_make_spec()` で実際の `ServiceSpec` を生成する。`test_service_spec.py` では正しく `ServiceSpec` を使っているので、同じパターンに揃える。

---

### Info

**(I-1) `tests/test_commands/test_api.py`: `_patch_all` ヘルパーが `patch_adapter` パターンと異なる**

テスト規約（`10-testing.md`）では `patch_adapter` 共通ヘルパーを使うことが推奨されていますが、`test_api.py` は独自の `_patch_all` コンテキストマネージャを定義しています。`handle_api` は `get_adapter` を使わず `create_http_client` を直接使う構造のため、`patch_adapter` が適用しづらい事情は理解できますが、ファイル上部にその旨のコメントがあると理解しやすい。

**(I-2) Gitea 系の Pipeline テスト: `get_pipeline_logs` テストが Gitea にのみ欠落**

GitHub / GitLab / Bitbucket / Azure DevOps には `TestGetPipelineLogs` クラスがありますが、Gitea にはありません。Gitea adapter が `get_pipeline_logs` をサポートしない場合は `NotSupportedError` テストが望ましく、サポートする場合はテストが必要です。

**(I-3) `tests/test_commands/test_issue_migrate.py` `_make_comment`: デフォルト引数名 `id=1` が Python ビルトイン `id()` を隠蔽**

`_make_comment(id=1, ...)` のパラメータ名が Python ビルトイン `id` と衝突しています。テスト内での使用なので実害はほぼありませんが、`comment_id=1` の方が明確です。同様に `_make_issue` も `number=1` で統一されているので問題ないが、`_make_comment` だけ `id` になっている不整合がある。

**(I-4) `tests/test_commands/test_pr.py` `TestHandleChecks` / `TestHandleFiles` / `TestHandleCommits`: JSON テスト内で `import json` がメソッドローカル**

ファイル先頭で `json` をインポートしていないため、各テストメソッド内で `import json` しています。一貫性のためファイル先頭でインポートするのが望ましい。

**(I-5) `tests/test_cli.py`: `_DISPATCH` のエントリ数がマジックナンバー**

`test_dispatch_table_has_68_entries` という関数名が元々 68 を示していたが、実際のアサーションは `len(_DISPATCH) == 147` になっています。関数名を `test_dispatch_table_entry_count` などに変更するか、コメントの `# 145 + phase6` を正確にする（147 != 145 + 2 であるなら）。

---

## 2.2 テストコードの一貫性

### Warning

**(W-8) モックパターンの混在: `@responses.activate` デコレータ vs `mock_responses` フィクスチャ**

同一ファイル内で2つのパターンが混在しています:
- `TestTriggerPipeline`（Gitea）: `mock_responses` フィクスチャ使用
- `TestUpdateRepositoryGitea`: `@responses.activate` デコレータ使用

既存コードでは `mock_responses` フィクスチャが主流ですが、新規追加の Phase 3 以降のテスト（repo 操作、リリースアセット等）では `@responses.activate` が多用されています。

該当ファイル: `test_gitea.py`, `test_github.py`, `test_gitlab.py` で Phase 2 は `mock_responses`、Phase 3 以降は `@responses.activate` が使われています。

**改善案**: Phase 3 以降のテストも `mock_responses` フィクスチャに統一する。少なくとも同一ファイル内では一方に統一する。

**(W-9) コマンドテストのパッチパターン不統一**

- `test_pr.py`, `test_ci.py`, `test_org.py` 等: `patch_adapter` ヘルパーを使用
- `test_repo.py`, `test_release.py`: `_patch_all` 独自ヘルパー + `patch("gfo.commands.repo.get_adapter", ...)` を直接使用

`test_repo.py` は既存の `_patch_all` パターンが残っている（`sample_config` フィクスチャ経由）ため、新規テストでも2パターンが混在しています。例えば `TestHandleUpdate` は `patch("gfo.commands.repo.get_adapter", ...)` を直接使い、`TestHandleStar` は `_patch_all` を使い、両方とも `patch_adapter` は使っていません。

---

## 2.3 テストの信頼性

### Info

**(I-6) テスト間の依存はなく、順序依存のリスクは低い**

全テストが独立しており、共有状態を持っていません。フィクスチャも適切にスコープされています。

**(I-7) `test_issue_migrate.py` の `_migrate_one_issue` 直接呼び出し: プライベート関数のテスト**

`_migrate_one_issue` と `_sync_labels` はプライベート関数ですが、直接テストされています。これ自体は問題ありませんが、関数シグネチャが変わるとテストが壊れます。現時点では十分な粒度でテストされており、妥当なトレードオフです。

---

## 2.4 バグやミス

### Warning

**(W-10) `tests/test_commands/test_batch.py` `TestHandleBatchPr.test_no_batch_pr_action_raises_config_error`: `batch_pr_action` 属性がない `Namespace` の挙動に依存**

```python
args = make_args(
    repos="github:owner/repo",
    title="Test PR",
    body="",
    head="feature",
    base="main",
)
# batch_pr_action 属性なし → getattr で None
```

コメントで `getattr で None` と説明しているが、`make_args` は `argparse.Namespace(**kwargs)` なので `batch_pr_action` 属性自体が存在しません。`getattr(args, 'batch_pr_action', None)` であれば問題ないが、実装が `args.batch_pr_action` なら `AttributeError` になる可能性がある。テストが通っているなら実装側が `getattr` を使っているということですが、テスト側で明示的に `batch_pr_action=None` を渡す方が意図が明確です。

**(W-11) `tests/test_commands/test_pr.py` `TestHandleMergeAuto`: `auto` フラグの既存テストとの関係が不明**

`test_auto_merge_calls_enable_auto_merge` が `auto=True` を渡していますが、既存の `TestHandleMerge` クラスでは `auto` フラグが引数に含まれていません。既存テストで `auto=False` のデフォルトが正しく動作することを確認するテストが不足しています。

---

## 単体テスト サマリー

| 深刻度 | 件数 | 主な内容 |
|--------|------|----------|
| Critical | 1 | Forgejo テストのクラスネスト問題 |
| Warning | 11 | テストケース不足（package, wiki, search, review）、インポートの不統一、モックパターン混在、パッチパターン不統一 |
| Info | 7 | 命名、マジックナンバー、ビルトイン隠蔽等の軽微な問題 |

**全体的な評価**: 追加されたテストコードは概ね良質で、特に以下の点が優れています。

- Phase 2 以降の PR 操作テスト（checks, files, commits, reviewers 等）は全サービスに対して一貫したパターンで書かれている
- `test_service_spec.py` は非常に網羅的で、SaaS/セルフホスト/Azure DevOps/Backlog の全パターンとエラーケースを丁寧にカバーしている
- `test_issue_migrate.py` は複雑な機能（クロスサービス移行）に対して、メタデータ埋め込み・部分失敗・ラベル同期などの重要なエッジケースをテストしている
- `test_tag_protect.py` と `test_gpg_key.py` は横断テストとして全サービスの NotSupported テストを網羅している

主な改善ポイントは、**テスト規約で必須とされている `fmt="json"` テストとエラー伝搬テストの追加**（特に `test_package.py`, `test_wiki.py`, `test_search.py`）と、**モックパターンの統一**（`mock_responses` vs `@responses.activate`、`patch_adapter` vs 独自 `_patch_all`）です。

---

# 3. 統合テスト コードレビュー

## 3.1 カバレッジ

### Critical: Phase 1〜6 の新機能に対する統合テストが一切追加されていない

`git diff 0e2d591..HEAD -- tests/integration/` の出力が空です。つまり、`0e2d591`（Phase 1）以降に追加された **64 個の新しいアダプターメソッド** に対して、統合テストが **1 件も追加されていません**。

以下が統合テストにカバーされていない全メソッド一覧です（Phase 別に分類）。

#### Phase 2: PR 操作の拡充（9機能）-- 統合テスト 0/9

| メソッド | ドキュメント上のカバレッジ記載 | 実テスト |
|---|---|---|
| `get_pull_request_diff` | o (6サービス) | **なし** |
| `list_pull_request_checks` | o (6サービス) | **なし** |
| `list_pull_request_files` | o (6サービス) | **なし** |
| `list_pull_request_commits` | o (6サービス) | **なし** |
| `list_requested_reviewers` / `request_reviewers` / `remove_reviewers` | o (6サービス) | **なし** |
| `update_pull_request_branch` | o (4サービス) | **なし** |
| `mark_pull_request_ready` | o (4サービス) | **なし** |
| `enable_auto_merge` | o (4サービス) | **なし** |
| `dismiss_review` | o (4サービス) | **なし** |

#### Phase 3: Release/Repo 管理の拡充（10機能）-- 統合テスト 0/10

| メソッド | ドキュメント上のカバレッジ記載 | 実テスト |
|---|---|---|
| `update_repository` | o (6サービス) | **なし** |
| `archive_repository` | o (5サービス) | **なし** |
| `get_languages` | o (4サービス) | **なし** |
| `list_topics` / `set_topics` / `add_topic` / `remove_topic` | o (4サービス) | **なし** |
| `compare` | o (6サービス) | **なし** |
| `get_latest_release` | o (5サービス) | **なし** |
| `list_release_assets` / `upload_release_asset` / `download_release_asset` / `delete_release_asset` | o (4サービス) | **なし** |
| `trigger_pipeline` / `retry_pipeline` / `get_pipeline_logs` | -- | **なし** |
| raw api (`api_request`) | o (全サービス) | **なし** |

#### Phase 4: CI/セキュリティ/組織の拡充（8機能）-- 統合テスト 0/8

| メソッド | ドキュメント上のカバレッジ記載 | 実テスト |
|---|---|---|
| `list_tag_protections` / `create_tag_protection` / `delete_tag_protection` | -- | **なし** |
| `list_gpg_keys` / `create_gpg_key` / `delete_gpg_key` | -- | **なし** |
| `create_organization` / `delete_organization` | -- | **なし** |
| `list_issue_templates` | -- | **なし** |
| webhook test | o (5サービス) | **なし** |

#### Phase 5: Issue 拡張/検索/ニッチ機能（14機能）-- 統合テスト 0/14

| メソッド | ドキュメント上のカバレッジ記載 | 実テスト |
|---|---|---|
| `list_issue_reactions` / `add_issue_reaction` / `remove_issue_reaction` | o (4サービス) | **なし** |
| `list_issue_dependencies` / `add_issue_dependency` / `remove_issue_dependency` | o (4サービス) | **なし** |
| `get_issue_timeline` | o (5サービス) | **なし** |
| `pin_issue` / `unpin_issue` | o (3サービス) | **なし** |
| `search_pull_requests` | o (6サービス) | **なし** |
| `search_commits` | o (3サービス, 一部partial) | **なし** |
| `list_packages` / `get_package` / `delete_package` | o (4サービス) | **なし** |
| `list_time_entries` / `add_time_entry` / `delete_time_entry` | o (4サービス) | **なし** |
| `list_push_mirrors` / `create_push_mirror` / `delete_push_mirror` / `sync_mirror` | o (3サービス) | **なし** |
| `transfer_repository` | o (4サービス) | **なし** |
| `star_repository` / `unstar_repository` | o (5サービス) | **なし** |
| `list_wiki_revisions` | o (2サービス) | **なし** |
| label clone | o (4サービス) | **なし** |

#### Phase 6: マルチサービス連携機能（2機能）-- 統合テスト 0/2

| メソッド | ドキュメント上のカバレッジ記載 | 実テスト |
|---|---|---|
| issue migrate | o (Gitea/Forgejo) | **なし** |
| batch pr create | o (Gitea/Forgejo) | **なし** |

---

## 3.2 統合テストの品質（既存テストに対する評価）

### Info: 既存テストの設計は良好

- `tests/integration/conftest.py` -- `.env` ファイルからの環境変数読み込み、`ServiceTestConfig`、`safe_temporary_directory()` による Windows 互換の一時ディレクトリなど、基盤は堅実
- `tests/integration/base_gitea_family.py` -- Gitea/Forgejo 共通テストの基底クラスパターンで DRY を実現
- `tests/integration/setup_services.py` -- Docker サービスの自動セットアップ（ユーザー作成、トークン生成、リポジトリ作成）が完備

### Warning: teardown_class のリソースクリーンアップが Phase 1〜6 のリソースに対応していない

**ファイル**: `tests/integration/base_gitea_family.py` 行 49-104

既存の `teardown_class` は初期の Phase（label, milestone, webhook, deploy_key, wiki, issue, PR）のクリーンアップのみで、新しく追加される可能性のあるリソース（tag protection, GPG key, organization, push mirror, release asset, time entry 等）のクリーンアップが含まれていません。統合テストを追加する際にはこの teardown を拡張する必要があります。

### Info: time.sleep() の使用は適切

`test_github.py` 行 165-172、784、802-803 等で `time.sleep(2)` / `time.sleep(3)` を使用しており、`.claude/rules/10-testing.md` のルール（API 反映ラグ対策で `time.sleep(3)` を入れる）に準拠しています。

### Info: プライベートメンバーへの依存は TODO で管理されている

複数の統合テストファイルで `_client`, `_repos_path()`, `_project_path()`, `_git_path()` などのプライベートメンバーに依存していますが、全て `# TODO: _client はプライベートメンバーへの依存。公開 API への移行を検討。` とコメントされており、技術的負債として認識されています。

---

## 3.3 ドキュメントとの整合

### Critical: ドキュメントのカバレッジ表が実際のテスト実装と大幅に乖離している

**ファイル**: `docs/integration-testing.ja.md` 行 330-365, `docs/integration-testing.md` 行 330-365

ドキュメントのカバレッジ表には Phase 1〜6 の全新機能が「o」（完全カバー）として記載されていますが、`tests/integration/` ディレクトリには該当するテストコードが存在しません。これは**ドキュメントが将来の計画（あるべき状態）を記載しているか、あるいは実装とドキュメントの更新が同期されていない**ことを意味します。

具体例:
- `pr diff: o (GitHub, GitLab, Bitbucket, Gitea, Forgejo)` -- 実テストなし
- `repo update: o (GitHub, GitLab, Bitbucket, Azure DevOps, Gitea, Forgejo)` -- 実テストなし
- `issue reaction: o (GitHub, GitLab, Gitea, Forgejo)` -- 実テストなし
- 他 30 項目以上が同様

### Info: 統合テストスキルの追加は適切

**ファイル**: `.claude/skills/integration-test/SKILL.md`

新しく追加された統合テストスキルの内容は、実際のテスト実行手順と一致しています。`selfhosted` / `saas` のカテゴリ分け、`--no-cov` オプション、pytest マーカーの使い方が正確です。

---

## 3.4 潜在的問題

### Warning: テスト順序への依存（既存の問題、新機能追加で悪化の可能性）

**ファイル**: 全統合テストファイル

テストは `test_01_*` 〜 `test_52_*` の番号順で実行され、後続テストが前のテストで作成したリソース（`_issue_number`, `_pr_number` 等）に依存しています。これは意図的な設計（テスト間でリソースを共有してAPI呼び出し回数を最小化）ですが、1つのテストが失敗すると後続テストが連鎖的に失敗するリスクがあります。

Phase 1〜6 の新機能テストを追加する際に番号が 52 番以降まで伸びると、この問題がさらに顕在化します。

**改善案**: 独立して実行可能なテストグループに分割するか、pytest の `--last-failed` オプションとの併用を推奨する文書を追加する。

### Info: Docker Compose 環境は安定

**ファイル**: `tests/integration/docker-compose.yml`

- Gitea 1.25、Forgejo 14、Gogs 0.14、GitBucket 4.46.0 とバージョンが固定されている
- ヘルスチェックが全サービスに設定されている
- ボリュームが名前付きで管理されている

### Warning: Gogs 0.14 のテストファイルにバージョン不整合の可能性

**ファイル**: `tests/integration/test_gogs.py`, `tests/integration/docker-compose.yml`

docker-compose.yml では `gogs/gogs:0.14` を使用していますが、test_gogs.py のコメントには「Gogs 0.13」への言及が複数あります（行 284, 285, 306）。テスト自体は `NotSupportedError` の try/except でフォールバックしているため実害は小さいですが、コメントの更新が望まれます。

---

## 統合テスト サマリー

| 深刻度 | 件数 | 概要 |
|---|---|---|
| **Critical** | **2** | Phase 1〜6 の新機能 64 メソッドに統合テストなし / ドキュメントのカバレッジ表が実態と乖離 |
| **Warning** | **3** | teardown が新リソースに未対応 / テスト順序依存の悪化リスク / Gogs バージョンコメント不整合 |
| **Info** | **4** | 既存テスト設計は良好 / sleep 使用適切 / プライベートメンバー依存は TODO 管理済み / スキル追加は適切 |

**最も重要な発見**: `0e2d591..HEAD` の変更（Phase 1〜6）で `src/gfo/adapter/base.py` に **64 メソッド** が追加され、対応するアダプター実装（github.py, gitlab.py, gitea.py 等）と単体テスト（tests/test_adapters/, tests/test_commands/）も追加されていますが、`tests/integration/` には **一切変更が入っていません**。ドキュメント（`docs/integration-testing.ja.md`, `docs/integration-testing.md`）のカバレッジ表のみが更新され、新機能が「o」で記載されていますが、対応する実テストコードが存在しない状態です。

統合テストの追加が必要な優先度の高い機能群:
1. PR 操作系（diff, checks, files, commits, reviewers）-- 最も利用頻度が高い
2. Repo 管理系（update, archive, topics, compare）-- 破壊的操作を含む
3. Release アセット系（upload, download, delete）-- ファイル I/O を伴う
4. Issue 拡張系（reaction, dependency, timeline, pin）-- 複数サービスで対応

---

# 4. ドキュメント レビュー

## 4.1 正確性（実装との不一致）

### Critical

**C-1. `gfo package view` の引数がドキュメントと実装で異なる**
- ファイル: `docs/commands.md` (L2137), `docs/commands.ja.md` (L2137)
- ドキュメント: `gfo package view NAME [--type TYPE] [--version VERSION]`
- 実装 (cli.py L633-636): `gfo package view PACKAGE_TYPE NAME [--version VERSION]`
  - 実装では `package_type` が必須の位置引数（1番目）、`name` が2番目の位置引数。`--type` はオプションではなく位置引数。
- 使用例もドキュメントでは `gfo package view my-package --type npm` だが、実際は `gfo package view npm my-package` が正しい。
- 改善案: ドキュメントを実装に合わせて `gfo package view PACKAGE_TYPE NAME [--version VERSION]` に修正。使用例も `gfo package view npm my-package` に修正。

**C-2. `gfo package delete` の引数がドキュメントと実装で異なる**
- ファイル: `docs/commands.md` (L2154), `docs/commands.ja.md` (L2154)
- ドキュメント: `gfo package delete NAME [--type TYPE] [--version VERSION] [--yes]`
- 実装 (cli.py L637-641): `gfo package delete PACKAGE_TYPE NAME VERSION [--yes]`
  - 実装では `package_type`, `name`, `version` の3つがすべて必須の位置引数。`--type` や `--version` オプションは存在しない。
- 改善案: ドキュメントを `gfo package delete PACKAGE_TYPE NAME VERSION [--yes]` に修正。使用例も `gfo package delete npm my-package 1.0.0` に修正。

**C-3. `gfo label clone` の引数がドキュメントと実装で異なる**
- ファイル: `docs/commands.md` (L948), `docs/commands.ja.md` (L948)
- ドキュメント: `gfo label clone SOURCE_REPO [--host HOST] [--overwrite]`
  - `SOURCE_REPO` を位置引数として記載し、`--host` オプションがあるとしている。
- 実装 (cli.py L597-599): `gfo label clone --from SOURCE [--overwrite]`
  - 実装では `--from` が required なオプション引数（dest=source）。`--host` オプションは存在しない。
- 使用例でも `gfo label clone alice/my-project` となっているが、実際は `gfo label clone --from alice/my-project` が正しい。
- 改善案: ドキュメントを `gfo label clone --from SOURCE_REPO [--overwrite]` に修正。使用例も `gfo label clone --from alice/my-project` に修正。`--host` の記載は削除。

### Warning

**W-1. `gfo repo mirror sync` のドキュメントと実装が不一致**
- ファイル: `docs/commands.md` (L741), `docs/commands.ja.md`
- ドキュメント: `gfo repo mirror sync [MIRROR_ID]` と記載し、ID を指定できるとしている。
- 実装 (cli.py L615): `repo_mirror_sub.add_parser("sync")` で引数なし。MIRROR_ID を取る add_argument は無い。
- 改善案: ドキュメントから `[MIRROR_ID]` を削除し、`gfo repo mirror sync` のみに修正。使用例の `gfo repo mirror sync 1` も削除。

**W-2. `gfo repo mirror add` の `--auth-token` オプションがドキュメントに未記載**
- ファイル: `docs/commands.md`, `docs/commands.ja.md`
- 実装 (cli.py L612): `--auth-token` オプションが存在するが、ドキュメントのオプション表に記載なし。
- 改善案: オプション表に `--auth-token` を追加。

**W-3. `gfo repo mirror remove` の引数名が不正確**
- ファイル: `docs/commands.md` (L740)
- ドキュメント: `gfo repo mirror remove MIRROR_ID` と記載。
- 実装 (cli.py L614): `mirror_name` という名前で定義されている。
- 軽微だが、ドキュメント上の引数名を `MIRROR_NAME` に合わせるか、実装を MIRROR_ID に合わせるべき。

---

## 4.2 完全性

### Warning

**W-4. AGENTS.md のディレクトリ構成が古い（Phase 2-6 の新規ファイルが反映されていない）**
- ファイル: `AGENTS.md` (L42-54)
- commands/ ディレクトリの記載が以下のファイルのみ:
  ```
  init.py / auth_cmd.py / pr.py / issue.py
  repo.py / release.py / label.py / milestone.py
  package.py
  schema.py
  ```
- 実際には `api.py`, `batch.py`, `ci.py`, `gpg_key.py`, `issue_template.py`, `org.py`, `review.py`, `search.py`, `tag_protect.py`, `wiki.py`, `branch.py`, `branch_protect.py`, `browse.py`, `collaborator.py`, `comment.py`, `deploy_key.py`, `file.py`, `notification.py`, `secret.py`, `ssh_key.py`, `status.py`, `tag.py`, `user.py`, `variable.py`, `webhook.py` が追加されている。
- 改善案: ディレクトリ構成のコマンドファイル一覧を最新化する。

**W-5. AGENTS.md の「カバレッジ: 2552 テスト、88%」が最新でない可能性**
- ファイル: `AGENTS.md` (L84)
- Phase 1-6 で大量のテストが追加されているため、テスト数は増加しているはず。
- 改善案: テストを実行して最新のカバレッジ数値を反映する。

**W-6. `gfo ci trigger` / `gfo ci retry` / `gfo ci logs` が commands.md で別セクションとして重複**
- ファイル: `docs/commands.md` (L1425 と L2013-2068)
- `gfo ci` セクション内に `list`, `view`, `cancel` の記載はあるが、`trigger`, `retry`, `logs` は `gfo ci` セクション内には無く、ファイル末尾に独立した `## gfo ci trigger`, `## gfo ci retry`, `## gfo ci logs` セクションとして追加されている。
- 改善案: `trigger`, `retry`, `logs` を `## gfo ci` セクション配下に統合する（H3 レベルのサブセクションとして）。

### Info

**I-1. `gfo org create / delete` がコマンド表と別セクションに分かれている**
- ファイル: `docs/commands.md` (L1724 と L2171)
- `## gfo org` セクションでは `list`, `view`, `members`, `repos` のみ記載。`create`, `delete` は末尾の `## gfo org create / delete` に独立。
- 改善案: `## gfo org` セクションに統合。

---

## 4.3 一貫性

### Info

**I-2. 日本語版（.ja.md）と英語版（.md）の内容は同期されている**
- README.md / README.ja.md: コマンド一覧表、サービス対応表とも完全に同期。
- docs/commands.md / docs/commands.ja.md: セクション構成、オプション表、使用例がすべて一致。
- docs/authentication.md / docs/authentication.ja.md: クロスサービスコマンドの認証セクションを含めすべて同期。
- docs/integration-testing.md / docs/integration-testing.ja.md: テスト対応マトリクス含め完全同期。
- 問題なし。

**I-3. ロードマップの進捗状況が実装と合っている**
- `docs/roadmap/` 全ファイルで、Phase 1-6 のすべてのアイテムが `[x]` （完了）チェック済み。
- 実装コード（cli.py の _DISPATCH テーブル、adapter 実装）で全機能が実装確認済み。
- 問題なし。

**I-4. README のコマンド一覧表と cli.py の定義が一致**
- 両 README ファイルのコマンド一覧表（34 コマンド）が cli.py の subparser/dispatch 定義と完全に一致。
- サブコマンドの列挙もすべて正確。
- 問題なし。

**I-5. サービス別機能対応表（Feature Support Matrix）が実装と一致**
- README.md / README.ja.md の対応表を adapter 実装と照合。
- 全体的に正確。
- 問題なし。

---

## 4.4 品質

### Info

**I-6. Markdown 構文は良好**
- 表のセパレータ、コードブロック、見出し階層に問題なし。
- リンク（README からの docs 参照、ロードマップのクロスリファレンス）すべて有効。

**I-7. 認証ガイドの新セクションが正確**
- `docs/authentication.md` / `docs/authentication.ja.md` に追加された「Authentication for Cross-Service Commands」(クロスサービスコマンドでの認証) セクションは、`gfo issue migrate` と `gfo batch pr create` の使い方に対応しており正確。

**I-8. 統合テストガイドが充実**
- テスト対応マトリクスに Phase 2-6 の全機能が記載されている。
- 新機能（issue migrate, batch pr create, wiki revisions 等）がすべて含まれている。

**I-9. .claude/skills/ ファイルは問題なし**
- `test/SKILL.md`, `integration-test/SKILL.md`, `deploy/SKILL.md` の内容はすべて適切。
- テストスキルの `tests/integration/` 除外処理が正しく記載されている。

---

## ドキュメント サマリー

| 深刻度 | 件数 | 概要 |
|--------|------|------|
| Critical | 3 | `package view`, `package delete`, `label clone` の引数がドキュメントと実装で不一致 |
| Warning | 6 | `repo mirror sync` 引数不一致、`repo mirror add` の `--auth-token` 未記載、`repo mirror remove` 引数名不一致、AGENTS.md のディレクトリ構成/テスト数が古い、ci trigger/retry/logs の構成上の問題 |
| Info | 9 | 日本語・英語の同期OK、ロードマップ進捗OK、Markdown品質OK 等 |

**最優先の対応**: Critical の3件（`gfo package view`, `gfo package delete`, `gfo label clone`）はドキュメント通りにコマンドを実行するとエラーになるため、早急な修正が必要です。commands.md と commands.ja.md の両方で修正が必要。
