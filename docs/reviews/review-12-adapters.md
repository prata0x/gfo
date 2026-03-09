# gfo Review Report — Round 12: アダプター精査（Backlog/Azure/GitLab/CLI）

## 概要
- レビュー日: 2026-03-09
- 対象: `backlog.py`, `azure_devops.py`, `gitlab.py`, `cli.py`, `auth_cmd.py`, `label.py` の精読
- コミット差分なし（R9〜R11 の修正は引き続き未実施）
- 発見事項: 重大 1 / 中 4 / 軽微 2

---

## R9〜R11 未修正問題（全件継続）

git log に新コミットなし。R9-01〜R11-05 の 15 件は引き続き未修正。

---

## 新規発見事項

---

### [R12-01] 🔴 `BacklogAdapter.close_issue` が issueKey でなく数値のみで PATCH → 誤った Issue をクローズする

- **ファイル**: `src/gfo/adapter/backlog.py` L249-250 vs L245-247
- **説明**: `get_issue` と `close_issue` で参照する API パスが不一致。
  ```python
  # get_issue: プロジェクトキー付き（例: /issues/PROJECT-42）
  def get_issue(self, number: int) -> Issue:
      resp = self._client.get(f"/issues/{self._project_key}-{number}")

  # close_issue: 数値のみ（例: /issues/42）← バグ
  def close_issue(self, number: int) -> None:
      self._client.patch(f"/issues/{number}", json={"statusId": _STATUS_CLOSED_ID})
  ```
  `_to_issue` が返す `number` は issueKey の末尾整数（`PROJECT-42` → `42`）であり、Backlog の内部 issueId とは異なる。Backlog API の `PATCH /api/v2/issues/{issueIdOrKey}` は issueKey 形式（`PROJECT-42`）または内部 issueId（全プロジェクト横断の連番）を受け付けるが、`42` という単独数値は別のプロジェクトの別の Issue の内部 ID に一致する可能性がある。
- **影響**: `gfo issue close 42` を実行した際、`PROJECT-42` ではなく内部 ID=42 の Issue（別プロジェクトのものである可能性）がクローズされる。または `PROJECT-42` が内部 ID=42 に一致しない場合は 404 エラーになる。Backlog を使用するすべてのユーザーの `issue close` コマンドに影響する。
- **推奨修正**: `close_issue` を `get_issue` と同じ issueKey 形式に統一する。
  ```python
  def close_issue(self, number: int) -> None:
      self._client.patch(
          f"/issues/{self._project_key}-{number}",
          json={"statusId": _STATUS_CLOSED_ID},
      )
  ```
- **テスト**: `close_issue(42)` が `/issues/PROJECT-42` に PATCH することを確認するテスト。プロジェクトキーが含まれることを検証する。

---

### [R12-02] 🟡 `GitLabAdapter.create_release` が `prerelease` パラメータを API に渡さない

- **ファイル**: `src/gfo/adapter/gitlab.py` L255-264
- **説明**: `create_release` は `prerelease: bool` パラメータを受け取るが、payload に含めていない。GitLab の Release API では `upcoming_release: true` で「リリース予定」（prerelease 相当）として作成できる。
  ```python
  def create_release(self, *, tag: str, title: str = "",
                     notes: str = "", draft: bool = False,
                     prerelease: bool = False) -> Release:
      payload = {
          "tag_name": tag,
          "name": title,
          "description": notes,
          # draft, prerelease が含まれていない ← バグ
      }
  ```
  `_to_release` で `prerelease=data.get("upcoming_release", False)` として読み取っているのに、作成時は `upcoming_release` を設定していない。
- **影響**: `gfo release create v1.0 --prerelease` を実行しても、GitLab 上でリリースが「upcoming release」にならない。`prerelease=True` が無視される。
- **推奨修正**: payload に `upcoming_release` を追加する。
  ```python
  payload = {
      "tag_name": tag,
      "name": title,
      "description": notes,
  }
  if prerelease:
      payload["upcoming_release"] = True
  ```
- **テスト**: `create_release(tag="v1.0", prerelease=True)` が payload に `"upcoming_release": True` を含めることを確認するテスト。

---

### [R12-03] 🟡 `AzureDevOpsAdapter._to_pull_request` の `url` フィールドが API URL（ブラウザで開けない）

- **ファイル**: `src/gfo/adapter/azure_devops.py` L73
- **説明**: Azure DevOps の PR オブジェクトの `url` フィールドは API エンドポイント URL（例: `https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}/pullRequests/{id}`）であり、ブラウザで開ける URL ではない。他のすべてのアダプターは `html_url`（GitHub）、`web_url`（GitLab）など、ユーザーが直接開ける URL を `PullRequest.url` に設定している。
  ```python
  url=data.get("url", ""),  # ← API URL（ブラウザで開けない）
  ```
  Azure DevOps の PR データには `url`（API URL）が含まれるが、ブラウザ URL は `{repository.remoteUrl}` から派生させて `{org.webUrl}/{project}/_git/{repo}/pullrequest/{id}` のように構成できる。
- **影響**: `gfo pr view --format json` の出力で `url` フィールドをブラウザで開こうとしても 404 になる。`gfo pr list` のテーブル表示の URL 列が API エンドポイント URL になる。
- **推奨修正**: PR データの `repository.webUrl` から web URL を構成する。
  ```python
  repo_web_url = data.get("repository", {}).get("webUrl", "")
  pr_id = data["pullRequestId"]
  web_url = f"{repo_web_url}/pullrequest/{pr_id}" if repo_web_url else data.get("url", "")
  ```
- **テスト**: `_to_pull_request` の返す `url` が API URL でなく web URL であることを確認するテスト。

---

### [R12-04] 🟡 `cli.py` の `--priority` に `type=int` がなく文字列が Backlog API に渡される

- **ファイル**: `src/gfo/cli.py` L96 および `src/gfo/commands/issue.py` L38
- **説明**: `issue create --priority` の argparse 定義で `type=int` が指定されていないため、`args.priority` は文字列として渡される。
  ```python
  # cli.py L96
  issue_create.add_argument("--priority")  # ← type=int がない

  # issue.py L38-39
  if args.priority is not None and config.service_type == "backlog":
      kwargs["priority"] = args.priority  # 文字列 "2" を渡す
  ```
  `BacklogAdapter.create_issue` の型ヒントは `priority: int | None = None` であり、payload には `"priorityId": priority` が設定される。文字列 `"2"` を渡すと、JSON ペイロードが `{"priorityId": "2"}` になり、Backlog API が整数を期待している場合にエラーになる。
- **影響**: `gfo issue create --title "foo" --priority 2` が、実際には `{"priorityId": "2"}` を送信してしまい、Backlog API が 400 Bad Request を返す可能性がある。
- **推奨修正**: `cli.py` に `type=int` を追加する。
  ```python
  issue_create.add_argument("--priority", type=int)
  ```
- **テスト**: `--priority 2` を指定したとき `create_issue(priority=2)` に `int` が渡されることを確認するテスト。

---

### [R12-05] 🟡 `AzureDevOpsAdapter.list_issues` の WIQL 件数が `limit > 200` で無視される

- **ファイル**: `src/gfo/adapter/azure_devops.py` L197
- **説明**: WIQL クエリで Work Item ID を取得する際に `$top: min(limit, 200)` を使用しており、`limit=500` などを指定しても最大 200 件しか ID が返らない。
  ```python
  wiql_resp = self._client.post(
      f"{self._wit_path()}/wiql",
      json={"query": wiql},
      params={"$top": min(limit, 200)},  # ← limit が 200 でキャップされる
  )
  ```
  Azure DevOps の WIQL API は最大 20000 件まで返せるが、ここでは 200 件に上限が固定されている。一方、取得した ID のバッチ処理（L205-213）は `for i in range(0, len(ids), 200)` でバッチ処理されており、200 件超にも対応できる実装になっているが、WIQL 段階で件数が絞られてしまっている。
- **影響**: `gfo issue list --limit 300` を指定しても最大 200 件しか返らない。ユーザーが指定した `--limit` が無視される。
- **推奨修正**: WIQL の `$top` を `limit` そのまま（または Azure DevOps の実際の上限値）に変更する。
  ```python
  params={"$top": limit},
  ```
- **テスト**: `limit=250` 指定時に WIQL の `$top=250` で呼ばれることを確認するテスト。

---

### [R12-06] 🟢 `BacklogAdapter.list_repositories` でページネーション未使用

- **ファイル**: `src/gfo/adapter/backlog.py` L254-258
- **説明**: `list_repositories` は1回の GET で全件を取得し、Python 側で `[:limit]` でスライスしている。他のリスト系メソッドが `paginate_offset` を使用しているのと対照的。
  ```python
  def list_repositories(self, *, owner: str | None = None, limit: int = 30) -> list[Repository]:
      resp = self._client.get(f"/projects/{self._project_key}/git/repositories")
      items = resp.json()
      return [self._to_repository(r) for r in items[:limit]]
  ```
  Backlog の `/api/v2/projects/{projectKey}/git/repositories` は1リクエストで全件を返す仕様（ページネーションパラメータが存在しない）ため、現状の実装は API 仕様通り。ただし `limit` パラメータをサーバーに渡していないため、リポジトリ数が多い場合に余分なデータを転送する。
- **影響**: リポジトリ数が多い場合に余分なデータを取得・パースする非効率がある。ただし Backlog のプロジェクト内リポジトリ数は通常少ないため実害は限定的。
- **推奨修正**: Backlog API がページネーションをサポートしない場合は現状維持でよいが、コメントでその旨を明記することを推奨。
  ```python
  # Backlog git repositories API はページネーションをサポートしないため全件取得後にスライス
  resp = self._client.get(f"/projects/{self._project_key}/git/repositories")
  ```

---

### [R12-07] 🟢 `auth_cmd.py` の `handle_status` で区切り線の長さが表示幅ベースでない

- **ファイル**: `src/gfo/commands/auth_cmd.py` L60
- **説明**: `print("-" * len(header))` で区切り線を描画しているが、`len(header)` は文字数であり表示幅（バイト幅）ではない。ホスト名に全角文字が含まれる場合（日本語 Backlog スペースのホスト名など）、`len()` は表示幅と一致せず区切り線がずれる。`output.py` の `_display_width` 関数は同様の問題を正しく処理しているが、`auth_cmd.py` ではそれを使用していない。
- **影響**: `gfo auth status` の出力で、全角文字を含むホスト名がある場合に区切り線の長さがずれる。
- **推奨修正**: `output._display_width` を使って区切り線の長さを計算するか、`output.format_table` を利用して表示を統一する。ただし `auth_cmd.py` は `output.py` に対する過度な依存を避けるため、軽微な問題として許容してもよい。

---

## 全問題サマリーテーブル（R9〜R12 未修正・新規）

| ID | 重大度 | ファイル | 概要 |
|----|--------|---------|------|
| R9-01 | 🔴 重大 | `bitbucket.py` | `GfoError` 未インポート → `NameError` |
| R10-01 | 🔴 重大 | `detect.py` L16 | import が関数定義の後（PEP 8 違反） |
| **R12-01** | 🔴 重大 | `backlog.py` L250 | `close_issue` の API パス不一致 → 誤 Issue をクローズ |
| R9-02 | 🟡 中 | `commands/repo.py` L65 | f-string 欠落 |
| R9-03 | 🟡 中 | `backlog.py` L100 | `ValueError` 未捕捉 |
| R9-04 | 🟡 中 | `http.py` L47 | SSL 証明書検証ハードコード |
| R9-05 | 🟡 中 | `config.py` L128 | `except Exception` 広範捕捉 |
| R9-06 | 🟡 中 | `output.py` L91 | 単一要素でオブジェクト返却 |
| R9-07 | 🟡 中 | `detect.py` L15 | `_mask_credentials` 正規表現不完全 |
| R10-02 | 🟡 中 | `commands/init.py` L138 | `except Exception` 広範捕捉 |
| R11-01 | 🟡 中 | `git_util.py` L14, `detect.py` L13 | `_mask_credentials` 重複定義 |
| R11-02 | 🟡 中 | `http.py` L60-149 | リトライループ重複 |
| R11-03 | 🟡 中 | `commands/pr.py` L63 | `handle_checkout` でブランチ既存時エラー未処理 |
| **R12-02** | 🟡 中 | `gitlab.py` L255 | `create_release` で `prerelease` が API に渡らない |
| **R12-03** | 🟡 中 | `azure_devops.py` L73 | PR の `url` フィールドが API URL（ブラウザ不可） |
| **R12-04** | 🟡 中 | `cli.py` L96 | `--priority` に `type=int` がなく文字列が渡る |
| **R12-05** | 🟡 中 | `azure_devops.py` L197 | `list_issues` の WIQL 件数が 200 でキャップ |
| R10-03 | 🟢 軽微 | `http.py` L103, L149 | 到達不可能な `return resp` |
| R11-04 | 🟢 軽微 | `commands/issue.py` | `get_adapter()` が config を返さない設計の限界 |
| R11-05 | 🟢 軽微 | `config.py` L14 | `ProjectConfig` が `frozen=True` でない |
| **R12-06** | 🟢 軽微 | `backlog.py` L256 | `list_repositories` がページネーション未使用 |
| **R12-07** | 🟢 軽微 | `auth_cmd.py` L60 | 区切り線の長さが表示幅ベースでない |

---

## 推奨アクション（優先度順）

1. **[R9-01] `bitbucket.py`** — `from gfo.exceptions import GfoError, NotSupportedError` に変更。1行。
2. **[R12-01] `backlog.py` L250** — `close_issue` を `f"/issues/{self._project_key}-{number}"` に変更。1行。
3. **[R10-01] `detect.py` import 順序** — `from gfo.git_util import ...` を import ブロックへ移動。
4. **[R12-04] `cli.py` L96** — `issue_create.add_argument("--priority", type=int)` に変更。1行。
5. **[R9-02] `repo.py` L65** — f-string プレフィックス追加。1文字。
6. **[R12-02] `gitlab.py` create_release** — `prerelease` が `True` のとき `payload["upcoming_release"] = True` を追加。
7. **[R9-03] `backlog.py` L110** — `except (KeyError, TypeError, ValueError)` に変更。
8. **[R12-03] `azure_devops.py` `_to_pull_request`** — `repository.webUrl` から PR ブラウザ URL を構成。
9. **[R12-05] `azure_devops.py` L197** — `$top: min(limit, 200)` を `$top: limit` に変更。
10. **[R9-05][R10-02] `config.py` + `init.py`** — `except Exception` を限定例外に変更。
11. **[R11-01][R9-07] `_mask_credentials` 統合・改善** — 1か所に集約し正規表現を改善。
12. **[R11-02] リトライループ共通化** — `_execute_with_retry` ヘルパー追加。

---

## 次ラウンドへの申し送り

- **未レビュー領域**: `adapter/gogs.py`、`adapter/forgejo.py`、`adapter/gitbucket.py`、`detect.py` の全体精読、`tests/` 配下のカバレッジ確認がまだ残っている。
- **R12-01 の影響範囲**: `close_issue` と同様に `get_issue`/`list_issues` との間で API パス一貫性を確認すること。`list_issues` は `paginate_offset(self._client, "/issues", params=...)` を使用しているが、返却された Issue の `number` を後続操作で使う際に同様の不一致が発生しないか検証が必要。
- **R12-03 の確認**: Azure DevOps の PR データに `repository.webUrl` が常に含まれるか API ドキュメントで確認が必要。
