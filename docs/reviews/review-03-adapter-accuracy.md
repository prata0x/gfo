# gfo Review Report — Round 2: アダプター層の正確性・API変換整合性（統合版）

> **✅ 修正完了**: 2026-03-09 に対象 16 件の修正をすべてコミット済み。

## 概要
- レビュー日: 2026-03-09
- レビュー回数: 3回（重複排除済み）
- 対象ファイル:
  - `src/gfo/adapter/base.py`
  - `src/gfo/adapter/github.py`
  - `src/gfo/adapter/gitbucket.py`
  - `src/gfo/adapter/gitea.py`
  - `src/gfo/adapter/forgejo.py`
  - `src/gfo/adapter/gitlab.py`
  - `src/gfo/adapter/bitbucket.py`
  - `src/gfo/adapter/azure_devops.py`
  - `src/gfo/adapter/backlog.py`
  - `src/gfo/adapter/gogs.py`
  - `src/gfo/adapter/registry.py`
  - `src/gfo/http.py`
- 発見事項: 重大 7 / 中 11 / 軽微 8 / 問題なし 2

---

## 発見事項

### [R2-01] 🔴 backlog.py: `issueKey.split("-")[-1]` が `str` を返すが `Issue.number` は `int` 型

- **ファイル**: `src/gfo/adapter/backlog.py` L89
- **説明**: `_to_issue` メソッド内で `data["issueKey"].split("-")[-1]` の結果（文字列）を `Issue.number` に代入している。`Issue` dataclass の `number` フィールドは `int` 型で宣言されているため、型不一致が発生する。`Issue` は `frozen=True, slots=True` の dataclass であり、`__post_init__` による型強制もないため、`str` のまま格納される。呼び出し側が `Issue.number` を整数として扱った場合（例: ソート、比較、フォーマット文字列での `%d` 使用）に `TypeError` が発生する可能性がある。`issueKey` が存在しない場合は `data["id"]` を使うパスに切り替わるため挙動が非一貫になる。
- **影響**: Issue 一覧表示やフィルタリングで予期しない動作または `TypeError` が発生する。CI/CD パイプラインで Backlog の issue 番号を整数として利用しているコードが壊れる。また型アノテーションに基づく静的解析ツールがエラーを報告する。
- **推奨修正**: `int(data["issueKey"].split("-")[-1])` と明示的にキャストする。ただし `issueKey` が数値部分を含まない場合の `ValueError` 対処も必要。`issueKey` が存在しない場合のフォールバック (`data["id"]`) は整数のため問題なし。
- **テスト**: `issueKey="PROJ-123"` を含む dict を渡したとき `issue.number == 123`（int）になることを確認するユニットテスト。`issueKey` が存在しない場合は `issue.number == data["id"]` で `int` であることを確認。
- **検出回数**: 3/3

---

### [R2-02] 🔴 bitbucket.py: `close_issue` で無効な state 値 `"closed"` を送信

- **ファイル**: `src/gfo/adapter/bitbucket.py` L164–L168
- **説明**: `close_issue` は `{"state": "closed"}` を PATCH ボディに送信するが、Bitbucket Cloud API v2 が Issues で受け付ける有効な state 値は `"new"`, `"open"`, `"resolved"`, `"on hold"`, `"invalid"`, `"duplicate"`, `"wontfix"` であり、`"closed"` は存在しない。API は 400 Bad Request を返す。
- **影響**: `gfo issue close` コマンドが Bitbucket Cloud 環境で常に失敗する。
- **推奨修正**: `{"state": "resolved"}` に変更する。要件によっては `"wontfix"` や `"invalid"` を選択肢として引数化することも検討できる。
- **テスト**: モック HTTP クライアントで `close_issue(1)` を呼び出し、送信ボディが `{"state": "resolved"}` であることをアサート。
- **検出回数**: 2/3

---

### [R2-03] 🔴 azure_devops.py: `_PR_STATE_FROM_API` / `_PR_STATE_TO_API` に存在しないキーで `KeyError`

- **ファイル**: `src/gfo/adapter/azure_devops.py` L62, L112
- **説明**: `_to_pull_request` 内で `_PR_STATE_FROM_API[data["status"]]` を辞書直接参照している。`_PR_STATE_FROM_API` は `"active"`, `"abandoned"`, `"completed"` の 3 キーのみ定義されている。Azure DevOps API はほかに `"notSet"` や `"all"` を返す可能性があり、その場合 `KeyError` が発生しクラッシュする。同様に `list_pull_requests` での `_PR_STATE_TO_API[state]` も、`"all"` 以外の未定義 state（例: `"unknown"`）が渡された場合に `KeyError` が発生する。コードは `if state != "all":` でガードしているが、その他の予期せぬ値のエラーハンドリングがない。
- **影響**: 呼び出し元に予期しない `KeyError` が伝播し、ユーザーには意味不明なトレースバックが表示される。`"notSet"` 状態の PR（下書き作成直後など）を取得した場合にアプリケーションが例外で落ちる。
- **推奨修正**: `_PR_STATE_FROM_API.get(data["status"], "open")` のように `.get()` でデフォルト値を返すか、`KeyError` を明示的にハンドルして意味のある値にマッピングする。`_PR_STATE_TO_API` は `.get(state, "active")` を使用するか、不正値の場合に `ValueError` を明示的に raise する。
- **テスト**: `status="notSet"` を持つ dict を渡したとき `KeyError` が発生しないことを確認するテスト。`list_pull_requests(state="invalid")` が `KeyError` でなく適切な例外を送出することを確認。
- **検出回数**: 3/3

---

### [R2-04] 🔴 backlog.py: `create_issue` で `priorities` が空リストのとき `IndexError` リスクと `None` ペイロード

- **ファイル**: `src/gfo/adapter/backlog.py` L195–L198
- **説明**: `priorities` が空リストの場合、`next(...)` のデフォルト値 `priorities[0]["id"]` が `IndexError` を送出する。`priorities[0]` は `next()` のデフォルト引数として評価されるため、`priorities` が空であっても即座に例外が発生する（遅延評価されない）。実際には `if priorities else None` で `None` が返るため IndexError は回避されているように見えるが、空リスト時のフォールバックが `None` になることで後続の `payload["priorityId"] = None` がAPIエラーを引き起こす可能性がある。同様に `issue_type` が `None` のままペイロードに `"issueTypeId": None` が含まれる場合、Backlog API では `issueTypeId` と `priorityId` は必須フィールドであり `None` を渡すと 400 エラーが発生する。
- **影響**: Backlog 環境によっては優先度設定なしの issue 作成が API エラーになる。イシュータイプまたは優先度が未設定のプロジェクトで `gfo issue create` が失敗する。エラーメッセージは HTTP 400 として伝播するが、原因が分かりにくい。
- **推奨修正**: `issue_type` または `priority` が `None` のまま続行しようとする場合は事前に `ConfigError` または `GfoError` を raise し、明確なエラーメッセージを提供する。`None` の場合はペイロードに `priorityId` を含めないようにする条件分岐も検討する。
- **テスト**: `/priorities` が空リストを返すモックで `create_issue` を呼んだとき IndexError が発生しないことを確認するテスト。issueTypes API が空リストを返す場合に `create_issue` が適切な例外を送出することを確認。
- **検出回数**: 3/3

---

### [R2-05] 🔴 gitlab.py: `_to_pull_request` で state `"locked"` のマッピング漏れ

- **ファイル**: `src/gfo/adapter/gitlab.py` L31–L46
- **説明**: GitLab の MR state は `"opened"`, `"closed"`, `"merged"`, `"locked"` の 4 種類がある。現在の変換ロジックは `"opened"` → `"open"` のみ変換し、それ以外はそのまま渡している。`"merged"` は `base.py` の仕様（`"open" | "closed" | "merged"`）と一致するため問題ないが、`"locked"` が返された場合は仕様外の値が `PullRequest.state` に入る。
- **影響**: `locked` 状態の MR が存在する環境では `PullRequest.state` に `"locked"` が入り、state によるフィルタリングや表示が壊れる。
- **推奨修正**: `_to_pull_request` 内で `state_map = {"opened": "open", "closed": "closed", "merged": "merged", "locked": "closed"}` のようなマッピングを用いる。
- **テスト**: `state="locked"` を持つデータを `_to_pull_request` に渡したとき、返り値の `state` が `"closed"` になることを確認するテスト。
- **検出回数**: 3/3

---

### [R2-06] ✅ gitbucket.py: `list_issues` のPRフィルタリングは問題なし（GitBucket API確認済み）

- **ファイル**: `src/gfo/adapter/github.py` L161（GitBucketAdapter が継承）
- **説明**: `list_issues` では `"pull_request" not in r` でPRを除外するフィルタが存在する。GitBucket の公式ソースコード（`ApiIssue.scala`）を確認したところ、GitBucket は GitHub API 互換で `pull_request` フィールドを実装しており、PRの場合は `Some(Map(...))` として、Issueの場合は `None` として返す。これにより `"pull_request" not in r`（Python では `None` が JSON の `null` に対応し、`None is not None` が `False` になるが、GitBucket のレスポンスでは PR の場合はオブジェクト、Issue の場合はフィールド自体が省略される）フィルタが正しく機能する。実際には GitBucket が `pull_request` フィールドを省略しないケースも考慮する必要があるが、仕様上は GitHub 互換として動作することが確認された。
- **影響**: なし（GitBucket API仕様確認により問題なしと判定）。
- **推奨修正**: 対応不要。現行の `"pull_request" not in r` フィルタはGitBucket APIの仕様に基づき正しく機能する。
- **テスト**: 対応不要。
- **検出回数**: 1/3（誤検知）

---

### [R2-07] 🔴 gitea.py: `list_issues` に `type=issues` パラメータ未指定でPR混入の可能性

- **ファイル**: `src/gfo/adapter/gitea.py` L148–L161
- **説明**: `"pull_request" not in r` によるクライアント側フィルタは存在するが、`type=issues` パラメータが未指定である。Gitea v1 API では `/repos/{owner}/{repo}/issues?type=issues` とすることで API レベルで PR を除外できる。`type` パラメータを渡さないと、デフォルトで issues と PRs 両方が返される可能性がある（Gitea のデフォルトは `type=issues` だが、バージョンによって異なる）。古い Gitea バージョンでは PR に対して `pull_request` フィールドを返さない場合があり、その場合クライアント側フィルタが機能せず PR が issue 一覧に混入する。つまり `type=issues`パラメータが未指定で、古いGiteaバージョンではPRが混入する可能性があり、クライアント側の `pull_request` フィールドフィルタで部分的に対処済みだが不完全な実装となっている。
- **影響**: 古い Gitea バージョンや `pull_request` フィールドを返さないバージョンでは、state="closed" の際に closed PR が issue 一覧に混入する可能性がある。
- **推奨修正**: `params["type"] = "issues"` を追加することで、APIレベルでPRを除外する。
- **テスト**: `type=issues` パラメータが送信されることを確認するテスト、Gitea APIレスポンスに `pull_request` フィールドがないPRオブジェクトが含まれる場合のテスト。
- **検出回数**: 1/3

---

### [R2-08] 🔴 http.py: `paginate_link_header` で `next_url` 未代入により 2 ページ目以降が無限ループの危険

- **ファイル**: `src/gfo/http.py` L181–L186
- **説明**: `paginate_link_header` 内でループ末尾の `url = match.group(1)` で `next_url` が設定されないまま（変数名が `url` であり `next_url` ではない）次ループで `if next_url is None` が `True` のままになる。`next_url` 変数への代入が行われていないことで、2 ページ目以降は常に `next_url is None` が `True` のまま最初のページの URL に再リクエストし、無限ループになる危険性がある。これにより全 GitHub 系・Gitea 系アダプターに影響する根本バグである。
- **影響**: GitHub / Gitea / Forgejo / GitBucket で 2 ページ以上のデータが存在する場合、無限ループに陥る可能性がある。ただし `limit` チェックで抜けるケースは多い。全ページネーション依存機能が正常動作しない。
- **推奨修正**: `url = match.group(1)` を `next_url = match.group(1)` に変更する。
- **テスト**: 2 ページ以上のモックレスポンスで `paginate_link_header` を呼び出し、全件取得できることを確認。
- **検出回数**: 1/3

---

### [R2-09] 🟡 gitlab.py: `_to_release` で `draft` と `prerelease` が同一フィールドにマッピング

- **ファイル**: `src/gfo/adapter/gitlab.py` L82–L91
- **説明**: `_to_release` において `draft` と `prerelease` の両方が `data.get("upcoming_release", False)` に設定されている。GitLab の `upcoming_release` は「まだリリースされていない将来のリリース」を示すフラグであり、GitHub の `draft`（未公開）や `prerelease`（プレリリース）とは概念が異なる。この実装では `draft=True` かつ `prerelease=True` が常に同じ値になってしまう。GitLab には draft release の概念が直接存在しないため、`draft=False` と固定するか、明示的に定義すべきである。加えて `create_release` で `draft`/`prerelease` パラメータを受け取るが、GitLab API のリリース作成エンドポイントには `upcoming_release` パラメータがなく（`released_at` で将来日付を指定）、これらのフラグはサイレントに無視される。
- **影響**: `release.draft` や `release.prerelease` を参照するコードが誤った値を得る。「draft ではないが prerelease のリリース」や「draft だが prerelease ではないリリース」を区別できない。`create_release(draft=True)` がドラフト状態を再現できない。
- **推奨修正**: `prerelease=False` を固定値にし、`draft=data.get("upcoming_release", False)` のみ維持する。`create_release` で `draft`/`prerelease` を渡せない旨をドキュメント化するか、`NotSupportedError` を検討する。
- **テスト**: `upcoming_release=True` の場合に `release.draft == True` かつ `release.prerelease == False` であることを確認するテスト。
- **検出回数**: 3/3

---

### [R2-10] 🟡 bitbucket.py: `_to_issue` で `assignee` が deleted user の場合 `KeyError`

- **ファイル**: `src/gfo/adapter/bitbucket.py` L59
- **説明**: `assignee["nickname"]` でキーアクセスしているが、Bitbucket では削除済みユーザーが assignee になっている場合 API レスポンスの `assignee` オブジェクトに `nickname` キーが含まれない可能性がある（`account_status: "closed"` のユーザーは一部フィールドが省略される）。
- **影響**: 削除済みユーザーが担当者になっている issue を取得するとクラッシュする。
- **推奨修正**: `assignee.get("nickname", "")` または `assignee.get("nickname") or assignee.get("display_name", "")` でフォールバックを設ける。
- **テスト**: `"assignee": {"account_status": "closed"}` （`nickname` キーなし）のデータで `_to_issue` を呼んだとき `KeyError` が発生しないことを確認するテスト。
- **検出回数**: 1/3

---

### [R2-11] 🟡 gitlab.py: `list_pull_requests` で state マッピングが部分的で暗黙依存

- **ファイル**: `src/gfo/adapter/gitlab.py` L116–L123
- **説明**: `list_pull_requests` では `api_state = "opened" if state == "open" else state` としている。`state="merged"` が渡された場合、GitLab API に `state=merged` が送信される。GitLab の Merge Requests API における有効な state は `opened`, `closed`, `locked`, `merged` であるため、`"merged"` は実際に正しく機能する。しかし `state="closed"` の場合、GitLab は `"closed"` と `"merged"` の両方を返す可能性がある。state マッピングを辞書として明示的に定義しないことで可読性と保守性が低下する。
- **影響**: 軽微だが仕様の暗黙的依存によりメンテナンス性が低下する。GitLab でマージ済みPRが `state="closed"` でリクエストした際に意図しない結果が生じる可能性がある。
- **推奨修正**: state マッピングを辞書として明示的に定義する（例: `_ISSUE_STATE_TO_API = {"open": "opened", "closed": "closed"}`）。GitLab MR の `state` フィールドの仕様を確認し、`"closed"` と `"merged"` の区別が正しく行われているか検証する。
- **テスト**: `state="merged"` と `state="closed"` でそれぞれ正しい MR だけが返ることを確認するテスト。
- **検出回数**: 3/3

---

### [R2-12] 🟡 azure_devops.py: `list_issues` の WIQL に SQLインジェクション相当のリスク

- **ファイル**: `src/gfo/adapter/azure_devops.py` L174–L176
- **説明**: `assignee` と `label` パラメータが WIQL クエリに直接文字列補間されている。
  ```python
  conditions.append(f"[System.AssignedTo] = '{assignee}'")
  conditions.append(f"[System.Tags] CONTAINS '{label}'")
  ```
  悪意のある値（例: `assignee = "x' OR 1=1 --"`）を渡された場合、WIQL クエリが意図しない結果を返す可能性がある。gfo はローカルツールのため外部入力を直接受け付けるリスクは低いが、設計上の欠陥として記録する。
- **影響**: 悪意のある入力による情報漏洩または予期しないクエリ結果。CLI ツールとして内部利用が前提であれば実被害は限定的。
- **推奨修正**: WIQL のパラメータバインディング機構（Azure DevOps API の `parameters` フィールド）を使用するか、シングルクォートをエスケープする。
- **テスト**: シングルクォートを含む `assignee` 文字列を渡したとき WIQL が壊れないことを確認するテスト。
- **検出回数**: 1/3

---

### [R2-13] 🟡 azure_devops.py: `_to_pull_request` の `updated_at` に `closedDate` を使用

- **ファイル**: `src/gfo/adapter/azure_devops.py` L69
- **説明**: `updated_at=data.get("closedDate")` としているが、`base.py` の `PullRequest.updated_at` の意味は「最後に更新された日時」である。Azure DevOps API では `closedDate` はPRがクローズされた日時であり、オープン中のPRでは `None` になる。更新日時を取得するには `lastMergeCommit` の日時や `completionQueueTime` など代替手段が必要。
- **影響**: オープン中のPRで `updated_at=None` が返される。PRが更新されても `updated_at` が変わらない。更新日時でのソートや表示が機能しない。
- **推奨修正**: `updated_at` を `data.get("completionQueueTime") or data.get("closedDate")` に変更するか、`None` 許容として現状維持の上でドキュメント化する（`base.py` では `updated_at: str | None` なので `None` 自体は許容）。
- **テスト**: `closedDate=None` のオープン PR データで `_to_pull_request` を呼び出し、`pr.updated_at is None` であることを確認し、これが意図通りかを文書化。
- **検出回数**: 2/3

---

### [R2-14] 🟡 github.py: `state="all"` の未サポート（暗黙の動作）

- **ファイル**: `src/gfo/adapter/github.py` L148–L161
- **説明**: `base.py` の `list_issues` シグネチャでは `state: str = "open"` と定義されており、有効値として `"open"` / `"closed"` が想定される。しかし GitHub API は `state=all` もサポートしており、`list_issues` で `state="all"` を渡した場合、`{"state": "all"}` としてAPIに送信されるため、実際には動作するが base クラスのコントラクトに記載がないため、挙動が曖昧。
- **影響**: コードの明確性と保守性の低下。呼び出し元が `state="all"` を期待する場合の動作が未保証。
- **推奨修正**: `base.py` の `list_issues` と `list_pull_requests` のシグネチャに `state` の有効値ドキュメントを追加するか、バリデーションを実装する。
- **テスト**: `state="all"` での動作確認テスト。
- **検出回数**: 1/3

---

### [R2-15] 🟡 backlog.py: `get_issue` が issueKey ではなく数値IDで取得（整合性の不一致）

- **ファイル**: `src/gfo/adapter/backlog.py` L214–L216
- **説明**: `get_issue(number: int)` は `GET /issues/{number}` を呼び出すが、`_to_issue` で `issue.number` には issueKey の末尾番号（例: `42`）が格納される。それは Backlog 内部の数値 ID とは異なる場合があり（issueKey は連番でも内部 ID とは別物）、そのため `get_issue(42)` が `PROJ-42` ではなく内部 ID=42 のイシューを返す不整合が生じる。
- **影響**: `gfo issue view 42` が期待と異なるイシューを返すか、404 になる可能性がある。`list_issues` → `get_issue` のフローで誤ったissueを取得する可能性がある。
- **推奨修正**: `get_issue` で issueKey 形式 `f"/issues/{self._project_key}-{number}"` を使用するか、`number` の意味を内部 ID に統一し `_to_issue` では `data["id"]` を常に使うよう変更する。
- **テスト**: `list_issues` で取得した `issue.number` を `get_issue` に渡した際に同一issueが返ることを確認するテスト。
- **検出回数**: 2/3

---

### [R2-16] 🟡 backlog.py: `_to_pull_request` の merged 判定が `status_id==5` 固定でプロジェクト設定と乖離

- **ファイル**: `src/gfo/adapter/backlog.py` L56–L62
- **説明**: `_to_pull_request` でマージ済みを `status_id == 5` にハードコードしているが、実際の Backlog のステータスは動的に設定可能である。一方 `list_pull_requests` では `_resolve_merged_status_id()` を呼び出して動的にマージ済みステータスを解決するが、`_to_pull_request` はその結果を参照せず `id == 5` を固定値として使っている。これにより、Backlog プロジェクトのマージ済みステータス ID が 5 以外の場合、正しく `"merged"` と判定されない。
- **影響**: マージ済み PR が `"open"` または `"closed"` として表示される可能性がある。
- **推奨修正**: `_to_pull_request` を静的メソッドから通常メソッドに変更し、`self._merged_status_id` を参照するか、`_to_pull_request` に `merged_status_id` 引数を追加する。
- **テスト**: `merged_status_id=3` の Backlog プロジェクトで `status_id=3` の PR が `state="merged"` になることを確認。`status_id=5` の固定値前提のテストも現状の挙動を記録しておく。
- **検出回数**: 1/3

---

### [R2-17] 🟡 gitlab.py: `list_repositories(owner=None)` でパスにクエリ文字列を埋め込む脆弱な実装

- **ファイル**: `src/gfo/adapter/gitlab.py` L206–L208
- **説明**: `list_repositories` で `owner` が None の場合に `"/projects?owned=true&membership=true"` をパスとして渡しているが、`paginate_page_param` 内でこのパスに追加 params が `&page=1&per_page=20` として結合される際、既に `?` を含むパスに `?` が再度付与される可能性がある。`requests` ライブラリは既存のクエリ文字列を正しくマージするため実害は出ないが、実装として脆弱。
- **影響**: `gfo repo list`（オーナー未指定時）で 404 または不正なリクエストになる可能性。現状は `requests` ライブラリが吸収するが実装の堅牢性が低い。
- **推奨修正**: `list_repositories` で `owner=None` の場合は `params={"owned": "true", "membership": "true"}` を `paginate_page_param` の `params` に渡し、パスは `"/projects"` のみにする。
- **テスト**: `list_repositories(owner=None)` を呼び出し、リクエスト URL が二重クエリ文字列にならないことをモックで確認。
- **検出回数**: 1/3

---

### [R2-18] 🟡 gitlab.py: `merge_pull_request` の squash マッピングが GitLab API と不一致

- **ファイル**: `src/gfo/adapter/gitlab.py` L142–L149
- **説明**: `merge_pull_request` では `method != "merge"` の場合のみ `merge_method` をペイロードに追加している。しかし GitLab の `merge_method` の有効値は `merge`, `rebase_merge`, `ff` であり、他のアダプターが使用する `"squash"` や `"rebase"` とは異なる名前体系になっている。`method="squash"` を渡した場合、`payload["merge_method"] = "squash"` が送信されるが、GitLab API は `"squash"` を `merge_method` パラメータとして受け付けない（GitLab では squash は `squash: true` パラメータで別途指定する）。
- **影響**: `method="squash"` 指定時に GitLab API がエラーを返すか、無視してデフォルトのマージ方式で処理する。
- **推奨修正**: GitLab 向けの merge_method マッピングテーブルを追加する（`"merge" -> "merge"`, `"squash" -> squash フラグ`, `"rebase" -> "rebase_merge"`）。
- **テスト**: `method="squash"` でマージリクエストを送った際に適切なペイロードが送信されることを確認するテスト。
- **検出回数**: 1/3

---

### [R2-19] 🟢 gitlab.py: `_to_issue` の冗長な no-op 代入

- **ファイル**: `src/gfo/adapter/gitlab.py` L54–L55
- **説明**: `_to_issue` 内の `if state == "closed": state = "closed"` は何もしない冗長なコードである。`"opened"` → `"open"` への変換後に `"closed"` を `"closed"` に「再代入」しているが意味がない。意図不明なデッドコードとして保守性を下げ、将来 state 変換を追加する際に見落とされる可能性がある。
- **影響**: 機能的影響はなし。コードの可読性・保守性の低下。
- **推奨修正**: `if state == "closed": state = "closed"` の行を削除する。
- **テスト**: 既存テストで十分。
- **検出回数**: 3/3

---

### [R2-20] 🟢 gitbucket.py / forgejo.py: `get_pr_checkout_refspec` の refspec と `refs/` プレフィックスについての設計的考慮事項

- **ファイル**: `src/gfo/adapter/gitbucket.py`（GitHubAdapter 継承）、`src/gfo/adapter/forgejo.py`（GiteaAdapter 継承）
- **説明**: `get_pr_checkout_refspec` は `pull/{number}/head` を返す。`spec.md` のサービス別 refspec テーブルでは「GitHub / GitBucket: `pull/{number}/head}`」「Gitea / Forgejo: `pull/{index}/head`」と `refs/` プレフィックスなしで定義されており、実装は仕様通りである。Git クライアントは `pull/{number}/head` 形式を `refs/pull/{number}/head` に自動解釈する動作をすることが多いが、これは Git クライアントの振る舞いに依存する設計的考慮事項である。確定的なバグとは言えない。
- **影響**: 一般的な Git クライアントでは `git fetch origin pull/1/head` が正常動作するが、特定の Git バージョンや設定によっては `refs/` プレフィックスが必要な場合がある。
- **推奨修正**: 必要であれば各アダプターで `refs/pull/{number}/head` を返すようオーバーライドするか、呼び出し側で `refs/` プレフィックスを補完する。実際の Git の動作を検証した上で判断する。
- **テスト**: `get_pr_checkout_refspec(1)` の戻り値が Git の refspec として有効であることを確認するテスト。
- **検出回数**: 2/3

---

### [R2-21] 🟢 backlog.py: `_to_repository` で `url` と `clone_url` が同一値

- **ファイル**: `src/gfo/adapter/backlog.py` L108–L109
- **説明**: `Repository.url`（Web UI URL）と `Repository.clone_url`（Git clone 用 URL）の両方に `data.get("httpUrl", "")` が設定されている。Backlog API レスポンスには `httpUrl`（Git clone URL）と別に Web UI への URL が存在する可能性があるが、現状では両フィールドが同値になる。
- **影響**: `Repository.url` をブラウザで開こうとした場合に Git clone URL（`.git` 末尾）が表示される可能性がある。
- **推奨修正**: Backlog API レスポンスに Web UI URL が含まれるか確認し、適切なフィールドをマッピングする。
- **テスト**: `list_repositories` の結果で `url != clone_url` となることを期待するテスト（Backlog API 仕様確認後）。
- **検出回数**: 1/3

---

### [R2-22] 🟢 gogs.py: `get_pr_checkout_refspec` が `NotSupportedError` を送出しない

- **ファイル**: `src/gfo/adapter/gogs.py`
- **説明**: `GogsAdapter` は PR 操作を全て `NotSupportedError` でオーバーライドしているが、`get_pr_checkout_refspec` はオーバーライドされておらず `GiteaAdapter` の実装（`return f"pull/{number}/head"`）が継承される。PR 操作が非サポートなのにチェックアウト refspec のみ返せるのは矛盾している。Gogs で `gfo pr checkout` を実行すると、PR 一覧取得時に `NotSupportedError` が出るが、refspec 取得だけは通過してしまうという非一貫な挙動になる。
- **影響**: `get_pr_checkout_refspec` を直接呼び出した場合に正常な値が返るが、実際に fetch しようとすれば失敗する（PR が存在しないため）。ユーザーが実行時エラーを `git fetch` 時まで気づけない。
- **推奨修正**: `GogsAdapter` でも `get_pr_checkout_refspec` を `NotSupportedError` でオーバーライドする。
- **テスト**: `GogsAdapter.get_pr_checkout_refspec(1)` が `NotSupportedError` を送出することを確認するテスト。
- **検出回数**: 3/3

---

### [R2-23] 🟢 github.py / gitea.py: `list_labels` / `list_milestones` がページネーションを使用していない

- **ファイル**: `src/gfo/adapter/github.py` L231–L233, `src/gfo/adapter/gitea.py` L232–L234
- **説明**: `list_labels` は `resp.json()` を直接返しており、`paginate_link_header` を使用していない。ラベル数が per_page デフォルト値（30）を超えるリポジトリでは、全ラベルを取得できない。`list_milestones` も同様（L247–L249）。
- **影響**: ラベル数が 30 件超のリポジトリで `list_labels` が不完全なリストを返す。マイルストーンも同様に取得漏れが発生する。
- **推奨修正**: `paginate_link_header` を使用するか、ラベル数が多くならない前提であれば `per_page=100` を明示的に指定する。
- **テスト**: 31 件以上のラベルを持つリポジトリで全件取得できることを確認するテスト（ページネーションのモック）。
- **検出回数**: 3/3

---

### [R2-24] 🟢 gitlab.py: `create_label` で `#` プレフィックスを含む color 引数が二重 `##` になる

- **ファイル**: `src/gfo/adapter/gitlab.py` L252–L260
- **説明**: `create_label` は `color` に `f"#{color}"` を付加するが、`_to_label` では `color.startswith("#")` の場合に `color[1:]` で `#` を除去している。つまり `color` 引数に `#` プレフィックスを含む値（例: `"#ff0000"`）を渡すと API には `"##ff0000"` が送信される。
- **影響**: ユーザーが `#ff0000` 形式でカラーを指定すると、GitLab API が 422 または予期しない色コードで処理する可能性がある。
- **推奨修正**: `create_label` で `payload["color"] = f"#{color.lstrip('#')}"` とする。
- **テスト**: `create_label(name="bug", color="#ff0000")` と `create_label(name="bug", color="ff0000")` 両方のリクエストボディで `color` が `"#ff0000"` になることを確認。
- **検出回数**: 1/3

---

### [R2-25] ✅ gitbucket.py / forgejo.py: 認証形式は正しく実装済み

- **ファイル**: `src/gfo/adapter/gitbucket.py` L10–L11、`src/gfo/adapter/forgejo.py` L10–L11
- **説明**: `GitBucketAdapter` は `GitHubAdapter` を、`ForgejoAdapter` は `GiteaAdapter` をそれぞれ `service_name` のみオーバーライドして継承している。認証形式については、`registry.py` の `create_http_client` では `gitbucket` は `gitea`/`forgejo`/`gogs` と同じ分岐（L53-54）で `"Authorization: token {token}"` 形式を使用している。`spec.md` の「サービス別仕様」テーブルでも GitBucket の認証方式は `Authorization: token {token}` と定義されており、実装は仕様通りで問題ない。GitHub（`Bearer` 形式）とは明示的に別の分岐で処理されている。
- **影響**: 現時点では機能影響なし。認証形式は正しく実装されている。将来的に親クラスのコンストラクタや API パスが変更された場合、子クラスが自動的に影響を受けることへの注意は引き続き必要。
- **推奨修正**: 対応不要。コメントとして親クラスとの互換性要件を記載することは保守性向上に寄与する。
- **テスト**: 既存の認証ヘッダーのテストで十分。
- **検出回数**: 1/3

---

## サマリーテーブル

| ID | 重大度 | ファイル | 行 | 説明 | 検出回数 |
|----|--------|---------|------|------|----------|
| R2-01 | 🔴 重大 | `backlog.py` | L89 | `issueKey.split("-")[-1]` が `str` を返すが `Issue.number` は `int` 型 | 3/3 |
| R2-02 | 🔴 重大 | `bitbucket.py` | L164–L168 | `close_issue` で無効な state 値 `"closed"` を送信（正しくは `"resolved"`） | 2/3 |
| R2-03 | 🔴 重大 | `azure_devops.py` | L62, L112 | `_PR_STATE_FROM_API` / `_PR_STATE_TO_API` に存在しないキーで `KeyError` | 3/3 |
| R2-04 | 🔴 重大 | `backlog.py` | L195–L198 | `create_issue` で `priorities`/`issueType` が空の場合に `IndexError` リスクと `None` ペイロード | 3/3 |
| R2-05 | 🔴 重大 | `gitlab.py` | L31–L46 | `_to_pull_request` で state `"locked"` が変換されず仕様外の値が格納 | 3/3 |
| R2-06 | ✅ 問題なし | `gitbucket.py`（継承: `github.py` L161）| — | GitBucket API仕様確認済み：`pull_request` フィールドはGitHub互換で実装済み。PRフィルタは正常動作 | 1/3（誤検知）|
| R2-07 | 🔴 重大 | `gitea.py` | L148–L161 | `list_issues` に `type=issues` パラメータ未指定でPR混入の可能性 | 1/3 |
| R2-08 | 🔴 重大 | `http.py` | L181–L186 | `paginate_link_header` で `next_url` 未代入により 2 ページ目以降が無限ループの危険 | 1/3 |
| R2-09 | 🟡 中 | `gitlab.py` | L82–L91 | `_to_release` で `draft` と `prerelease` が同一フィールド (`upcoming_release`) に設定 | 3/3 |
| R2-10 | 🟡 中 | `bitbucket.py` | L59 | deleted user の assignee で `KeyError` | 1/3 |
| R2-11 | 🟡 中 | `gitlab.py` | L116–L123 | `list_pull_requests` の state マッピングが部分的で暗黙依存 | 3/3 |
| R2-12 | 🟡 中 | `azure_devops.py` | L174–L176 | WIQL への文字列直接補間（インジェクションリスク） | 1/3 |
| R2-13 | 🟡 中 | `azure_devops.py` | L69 | `updated_at` に `closedDate` を使用し、オープン PR では常に `None` | 2/3 |
| R2-14 | 🟡 中 | `github.py` | L148–L161 | `state="all"` の未サポート（暗黙の動作） | 1/3 |
| R2-15 | 🟡 中 | `backlog.py` | L214–L216 | `get_issue` が issueKey 末尾番号と内部 ID を混在 | 2/3 |
| R2-16 | 🟡 中 | `backlog.py` | L56–L62 | `_to_pull_request` の merged 判定が `status_id==5` 固定 | 1/3 |
| R2-17 | 🟡 中 | `gitlab.py` | L206–L208 | `list_repositories(owner=None)` でパスにクエリ文字列を埋め込む脆弱な実装 | 1/3 |
| R2-18 | 🟡 中 | `gitlab.py` | L142–L149 | `merge_pull_request` の squash マッピングが GitLab API と不一致 | 1/3 |
| R2-19 | 🟢 軽微 | `gitlab.py` | L54–L55 | `_to_issue` 内の冗長な no-op 代入 `if state == "closed": state = "closed"` | 3/3 |
| R2-20 | 🟢 軽微 | `gitbucket.py` / `forgejo.py` | — | `get_pr_checkout_refspec` の refspec と `refs/` プレフィックスについての設計的考慮事項（仕様通りの実装） | 2/3 |
| R2-21 | 🟢 軽微 | `backlog.py` | L108–L109 | `_to_repository` で `url` と `clone_url` が同一値 | 1/3 |
| R2-22 | 🟢 軽微 | `gogs.py` | — | `get_pr_checkout_refspec` が `NotSupportedError` を送出しない | 3/3 |
| R2-23 | 🟢 軽微 | `github.py`, `gitea.py` | L231–L249 | `list_labels` / `list_milestones` がページネーション未使用 | 3/3 |
| R2-24 | 🟢 軽微 | `gitlab.py` | L252–L260 | `create_label` で `#` プレフィックスを含む color 引数が二重 `##` になる | 1/3 |
| R2-25 | ✅ 問題なし | `gitbucket.py` / `forgejo.py` | L10–L11 | 認証形式は `Authorization: token {token}` で仕様通り正しく実装済み | 1/3 |

---

## 推奨アクション (優先度順)

1. **[R2-08] `http.py` `paginate_link_header` の `next_url` 未代入を修正** — 全 GitHub 系・Gitea 系アダプターに影響する根本バグ。2 ページ以上のデータで無限ループの可能性があり、最優先で対処すること。`url = match.group(1)` を `next_url = match.group(1)` に変更する。
2. **[R2-02] `bitbucket.py` `close_issue` の state 値を `"resolved"` に修正** — Bitbucket Cloud で `gfo issue close` が常に失敗する致命的な動作不良。`{"state": "resolved"}` に変更する。
3. **[R2-01] `backlog.py` `_to_issue` の `str` → `int` キャストを追加** — 型安全性の根本的破壊。`int(data["issueKey"].split("-")[-1])` に修正する。
4. **[R2-03] `azure_devops.py` `_PR_STATE_FROM_API` / `_PR_STATE_TO_API` の KeyError 対策** — `.get()` メソッドでデフォルト値を設定するか、明示的なバリデーションを追加する。
5. **[R2-05] `gitlab.py` `_to_pull_request` で `"locked"` state のマッピングを追加** — 仕様外の state 値が格納されるのを防ぐ。`state_map` 辞書でマッピングする。
6. **[R2-07] `gitea.py` `list_issues` に `type=issues` パラメータ追加** — `params["type"] = "issues"` を追加してAPIレベルでPRを除外する。
7. **[R2-04] `backlog.py` `create_issue` での None チェックとエラーメッセージ追加** — issueType/priority が未設定のプロジェクトでの失敗を事前検出してユーザーフレンドリーなエラーを提供する。
8. **[R2-16] `backlog.py` `_to_pull_request` の merged 判定を動的 status_id 参照に変更** — プロジェクト設定依存の判定をハードコードで行っており、多くの Backlog 環境で誤った state が返る。
9. **[R2-15] `backlog.py` `get_issue` の issueKey vs 内部 ID の整合性を確立** — API の意味論的な不整合を解消し、`gfo issue view` の信頼性を向上させる。
10. **[R2-10] `bitbucket.py` `_to_issue` の deleted user 対応** — `assignee.get("nickname", "")` でフォールバックを追加する。
11. **[R2-09] `gitlab.py` `_to_release` の `prerelease` マッピングを修正** — `draft=False` に固定し、`prerelease` のみ `upcoming_release` にマッピングする。
12. **[R2-18] `gitlab.py` `merge_pull_request` の squash マッピングを修正** — GitLab API に対応した merge_method マッピングに変更する。
13. **[R2-23] `github.py` / `gitea.py` `list_labels` / `list_milestones` のページネーション対応** — `paginate_link_header` に移行する。
14. **[R2-24] `gitlab.py` `create_label` の二重 `#` プレフィックス防止** — `color.lstrip('#')` で正規化する。
15. **[R2-22] `gogs.py` `get_pr_checkout_refspec` のオーバーライド追加** — PR 非サポートの一貫性のため `NotSupportedError` を送出するよう修正する。
16. **[R2-12] `azure_devops.py` WIQL インジェクション対策** — シングルクォートエスケープまたはパラメータバインディングを実装する。
17. **[R2-17] `gitlab.py` `list_repositories` の URL 構築を params ベースに変更** — 現状は requests ライブラリが吸収するが、実装の堅牢性のために修正する。
18. **[R2-11] `gitlab.py` state マッピング明示化** — state 変換ロジックを辞書で明示的に定義する。
19. **[R2-06] ✅ 対応不要** — GitBucket API（`ApiIssue.scala`）の確認により `pull_request` フィールドはGitHub互換で実装済みと判明。現行フィルタは正常動作する。
20. **[R2-13] `azure_devops.py` `updated_at` の代替フィールド検討** — 機能への実害は限定的だが、ドキュメント化または `completionQueueTime` での改善を行う。
21. **[R2-20] `gitbucket.py` / `forgejo.py` refspec の `refs/` プレフィックス（設計的考慮事項）** — 仕様通りの実装だが、Git クライアントの振る舞いに依存する点を認識しておくこと。実際の `git fetch` 動作を確認し、問題があれば `refs/` プレフィックスを追加する対処を検討する。
22. **[R2-19] `gitlab.py` `_to_issue` の冗長コード削除** — `if state == "closed": state = "closed"` を削除する。
23. **[R2-14] `github.py` `state="all"` の仕様明確化** — `base.py` に有効な state 値のドキュメントを追加するかバリデーションを実装する。
24. **[R2-21] `backlog.py` `url` フィールド確認** — Backlog API 仕様を確認して `Repository.url` に適切な Web UI URL を設定する。
25. **[R2-25] `gitbucket.py` / `forgejo.py` 認証形式は問題なし** — `registry.py` で `gitbucket` は `Authorization: token {token}` 形式を使用しており、`spec.md` の仕様通りに正しく実装されている。対応不要。

---

## 修正記録 (2026-03-09)

review-02 で修正済み: R2-08, R2-01, R2-11 はスキップ。残り 14 件を全て修正・コミット完了。

| ID | 修正内容 | コミット |
|----|---------|---------|
| R2-02 | `bitbucket.py` `close_issue` の state 値を `"resolved"` に修正 | ed68f62 |
| R2-03 | `azure_devops.py` PR state 辞書参照を `.get()` で KeyError 対策 | 2219b4a |
| R2-05 | `gitlab.py` `_to_pull_request` に `"locked"` state マッピングを追加 | 19447d5 |
| R2-07 | `gitea.py` `list_issues` に `type=issues` パラメータを追加 | d7de1b8 |
| R2-04 | `backlog.py` `create_issue` で issue_type/priority が None のとき GfoError を raise | 2408124 |
| R2-16 | `backlog.py` `_to_pull_request` の merged 判定を動的 status_id 参照に変更 | 583904d |
| R2-15 | `backlog.py` `get_issue` を issueKey 形式 (`PROJECT_KEY-N`) で取得 | 9262448 |
| R2-10 | `bitbucket.py` `_to_issue` の deleted user assignee で KeyError を防止 | 0e6a166 |
| R2-09 | `gitlab.py` `_to_release` の `draft` を `False` 固定に修正 | f269d97 |
| R2-18 | `gitlab.py` `merge_pull_request` の squash/rebase マッピングを GitLab API 仕様に修正 | ce01a14 |
| R2-23 | `github.py`/`gitea.py` `list_labels`/`list_milestones` をページネーション対応 | 8f13b56 |
| R2-24 | `gitlab.py` `create_label` の二重 `#` プレフィックス防止 | a0639c7 |
| R2-22 | `gogs.py` `get_pr_checkout_refspec` を `NotSupportedError` でオーバーライド | c53f1d0 |
| R2-12 | `azure_devops.py` WIQL クエリのシングルクォートをエスケープ | ce50256 |
| R2-17 | `gitlab.py` `list_repositories` の URL 構築を params ベースに変更 | 1ed4ace |
| R2-19 | `gitlab.py` `_to_issue` の冗長な no-op 代入を削除 | e380901 |
