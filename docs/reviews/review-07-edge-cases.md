# gfo Review Report — Round 6: エッジケース・境界値・堅牢性（統合版）

## 概要
- レビュー日: 2026-03-09
- レビュー回数: 3回（重複排除済み）
- 対象ファイル:
  - `src/gfo/http.py`
  - `src/gfo/output.py`
  - `src/gfo/config.py`
  - `src/gfo/detect.py`
  - `src/gfo/git_util.py`
  - `src/gfo/auth.py`
  - `src/gfo/cli.py`
  - `src/gfo/exceptions.py`
  - `src/gfo/commands/issue.py`
  - `src/gfo/adapter/` 以下の全ファイル（github, gitlab, bitbucket, azure_devops, gitea, forgejo, gogs, gitbucket, backlog, registry を含む11ファイル）
  - `src/gfo/commands/` 以下の全ファイル（pr, issue, init, auth_cmd, release, label, milestone, repo の9ファイル）
- 発見事項: 重大 4 / 中 13 / 軽微 10

---

## 発見事項

### [R6-01] 🔴 `limit=0` のとき全ページネーション関数が無限ループになる

- **ファイル**: `src/gfo/http.py` L177, L211, L256, L290, L323
- **説明**: すべてのページネーション関数は `if limit > 0 and len(results) >= limit:` という条件でループを打ち切る。`limit=0` を渡すと条件が恒偽となり、API が返すデータをページが尽きるまで際限なく取得し続ける。意図的な「無制限取得」の設計かもしれないが、呼び出し側（`base.py` の抽象インタフェースやコマンドハンドラ）にその契約が明示されていない。CLI ユーザーが `--limit 0` を渡した場合にも同様の事態が起きる。APIが大量データを返す場合（例：1000件以上のissueを持つリポジトリ）、プロセスがメモリを使い果たすか、タイムアウトまで停止しない。
- **影響**: 数千・数万件のデータを持つリポジトリでコマンドを実行すると、大量のAPIリクエストが発行され、メモリ枯渇・レート制限超過・長時間ハングが発生しうる。
- **推奨修正**: `limit <= 0` を「無制限」と明確に文書化するか、あるいは `limit < 1` の場合は `ValueError` を送出して呼び出し元で弾く。CLI 側では `--limit` の最小値バリデーション（`type=int` のカスタムタイプや `argparse` の `choices` 等）を追加する。「無制限取得」として意図的に設計するなら適切な安全上限（例: 10,000件）を設ける。
- **テスト**: `paginate_link_header(client, path, limit=0)` に対して無限ループしないことを確認するテスト。モックで2ページ分のデータを返すよう設定し、呼び出し回数が有界であることを検証するテスト。
- **検出回数**: 3/3

---

### [R6-02] 🔴 `format_table` / `format_plain` でタブ・改行を含む値が出力を破壊する

- **ファイル**: `src/gfo/output.py` L38, L51, L64–70
- **説明**: `format_table` は各フィールド値を `str(d.get(f, ""))` で変換してそのまま使う。Issue タイトルや PR タイトルに `\n`（改行）が含まれる場合（GitLabでは可能）、テーブル行が途中で改行されてヘッダーとのカラム位置がずれ、視覚的に完全に崩壊する。`\t`（タブ）が含まれる場合は幅計算が不正確になる。`format_plain` はタブ区切りのため、タイトル中にタブが含まれるとパース側が列を誤認する。ユーザーが `fields=["number", "body"]` のように指定した場合にも発生しうる。
- **影響**: ユーザーがパイプで出力を処理するスクリプトを書いた場合、タブを含むタイトルで意図せずフィールド分割される。テーブルフォーマット出力が視覚的に崩れ、パイプ処理でCSV/TSVとして利用する場合に誤パースが生じる。
- **推奨修正**: `format_table` 用のサニタイズ関数を追加し、`\n` を `↵` または空白に、`\t` を空白に変換する（例: `val.replace("\n", "\\n").replace("\r", "\\r").replace("\t", " ")`）。`format_plain` では値中のタブを `\\t` にエスケープするか、区切り文字を変更する。
- **テスト**: タイトルに `"line1\nline2"` や `"col1\tcol2"` を含む Issue データで `format_table` / `format_plain` を呼び出し、出力が1行に収まることを確認するテスト。`title="日本語タイトル🎉\n改行あり"` のケースも含める。
- **検出回数**: 3/3

---

### [R6-03] 🔴 `paginate_link_header` / `paginate_response_body` の次ページ取得で `_auth_params` が消える

- **ファイル**: `src/gfo/http.py` L164–171, L243
- **説明**: 2ページ目以降は `next_url` を使って `client._session.get(next_url, timeout=30)` を直接呼び出している。この呼び出しには `merged_params`（`auth_params` を含む）が付与されない。Backlog のように `apiKey` クエリパラメータで認証するサービスでは、次ページ以降のリクエストに認証情報が含まれなくなり、2ページ目以降で 401 エラーが発生する。GitHub / GitLab など `Session.headers` に認証情報を設定するサービスでは問題ないが、`_auth_params` を使用するサービスは影響を受ける。また `next_url` が別ドメインを指す場合、`requests.Session` は認証ヘッダーを送信しない（セキュリティ仕様）。`paginate_response_body` にも同パターン（L243）が存在する。
- **影響**: Backlog で 20 件超のイシュー・PR をリストアップした際に認証エラーが発生する。`_auth_params` を使用する将来の新アダプターでも同様の問題が再現する構造的バグ。
- **推奨修正**: `client._session.get(next_url, ...)` の代わりに `client.request("GET", ...)` を使うか、`client._auth_params` を `params` として明示的に渡す（`client._session.get(next_url, params=client._auth_params, timeout=30)`）。あるいは `HttpClient` に `get_raw(url)` のようなメソッドを追加して `_auth_params` を自動付与するようにする。
- **テスト**: Backlog アダプターで 2 ページ分のモックレスポンスを用意し、2 ページ目のリクエストに `apiKey` パラメータが含まれることを確認するテスト。`auth_params` ありの `HttpClient` で `paginate_link_header()` を呼び出し、2ページ目のリクエストに auth_params が含まれることをモックで検証するテスト。
- **検出回数**: 3/3

---

### [R6-04] 🔴 GitHub / Gitea アダプターの `list_labels()` / `list_milestones()` がページネーション未対応

- **ファイル**: `src/gfo/adapter/github.py` L231–233, L247–249, `src/gfo/adapter/gitea.py` L232–234, L248–250
- **説明**: `list_labels()` と `list_milestones()` は `self._client.get(...)` で単一レスポンスを取得し、`resp.json()` をそのまま使用する。GitHub / Gitea API はラベル・マイルストーンも最大 per_page=100 でページネーションを返す。ラベルが100件を超えるリポジトリでは2ページ目以降が取得されない。
- **影響**: ラベル数が多いリポジトリで全件が表示されず、ユーザーが存在するはずのラベルを発見できない。
- **推奨修正**: `paginate_link_header()` を使用してページネーションに対応する。
- **テスト**: モックで101件のラベルを返すAPIに対して `list_labels()` が全101件を返すこと。
- **検出回数**: 1/3

---

### [R6-05] 🟡 空リスト返却時に `output()` が何も出力しない（静寂な失敗）

- **ファイル**: `src/gfo/output.py` L17–18
- **説明**: `if not items: return` により、空リストの場合は何も出力せずに関数が戻る。ユーザーが `gfo issue list` を実行してイシューが 0 件の場合、プロンプトが返るだけで「0 件です」という通知が一切表示されない。エラーなのか正常（0 件）なのかが区別できない。
- **影響**: ユーザーが空結果をコマンド失敗と誤解する。スクリプトが出力の有無を正常判定の条件にしていた場合に誤動作する。
- **推奨修正**: `fmt == "json"` のときは `[]` を出力し、`table`/`plain` のときは `"No results found."` 等のメッセージを `stderr` に出力する。
- **テスト**: `output([], fmt="table")` で `stdout` が空であること、および `fmt="json"` で `[]` が出力されることを確認するテスト。
- **検出回数**: 1/3

---

### [R6-06] 🟡 `format_table` で多バイト文字・絵文字を含む値のテーブル幅計算が不正

- **ファイル**: `src/gfo/output.py` L40–43
- **説明**: `widths[i] = max(widths[i], len(val))` は多バイト文字（日本語・絵文字）の表示幅を考慮しない。`len("日本語")` は `3` を返すが、ターミナルの表示幅は `6` である。絵文字（例: `"🐛 Fix bug"` ）も `len()` の値とターミナル表示幅が一致しない。絵文字は GitHub/Gitea のイシュータイトルに頻繁に使われるため実用上の影響が特に大きい。また 1000 文字を超えるタイトルが格納されている場合、テーブル幅が極端に広がり可読性が著しく損なわれる。
- **影響**: 日本語タイトルを持つイシューのテーブル出力でカラムアライメントがずれる。絵文字を含むタイトルのある行でテーブルのカラムアライメントがずれる。長いタイトルのあるリストで横スクロールが必要な幅になる。
- **推奨修正**: `wcwidth` ライブラリを使って表示幅を計算する（`wcswidth` 関数）。テーブル列の最大幅に上限（例: 80文字）を設け、超過分は `...` で省略する。
- **テスト**: 日本語タイトル・絵文字タイトル・1000文字タイトルを含む Issue データで `format_table` を呼び出し、各行の区切り文字位置が一致することを確認するテスト。
- **検出回数**: 3/3

---

### [R6-07] 🟡 `paginate_page_param` で `X-Next-Page` ヘッダーが変換不能値のとき `ValueError`

- **ファイル**: `src/gfo/http.py` L218
- **説明**: `params["page"] = int(next_page)` において、`next_page` がスペース等の変換不能文字列である場合 `ValueError` が発生する。ヘッダー値のバリデーションが不十分である。通常の GitLab 運用では問題ないが、カスタム GitLab インスタンスやプロキシが異常なヘッダーを返した場合に未処理例外として上位に伝播する。`ValueError` が `GfoError` を継承していないため `cli.py` の例外ハンドラで捕捉されず、スタックトレースがユーザーに表示される。また `X-Next-Page: 0` を返した場合（GitLab 仕様では起きないが）、`int("0")` = `0` が `params["page"]` に設定されてループが継続する可能性もある。
- **影響**: `ValueError` が `GfoError` を継承していないため `cli.py` の例外ハンドラで捕捉されず、スタックトレースがユーザーに表示される。
- **推奨修正**: `int(next_page)` を `try/except ValueError` で囲み、失敗時はページネーションを終了する。`if not next_page or next_page == "0": break` と明示的に `"0"` も終了条件に含めることも検討する。
- **テスト**: `X-Next-Page` ヘッダーに `"invalid"` や `"0"` を含むモックレスポンスで `paginate_page_param` がエラーなく終了することを確認するテスト。
- **検出回数**: 2/3

---

### [R6-08] 🟡 GitLab サブグループ 3 階層以上での動作が不確実

- **ファイル**: `src/gfo/adapter/gitlab.py` L25
- **説明**: `_project_path()` は `quote(self._owner + '/' + self._repo, safe='')` でスラッシュを `%2F` にエンコードしている。`detect_from_url` の `_GENERIC_PATH_RE` は最後のスラッシュより前をすべて `owner` として取得するため、3階層以上のサブグループ（`group/sub1/sub2/repo`）では `self._owner` が `group/sub1/sub2` となり `%2F` にエンコードされる。spec.md ではこの多段エンコードを仕様として記載しているが、GitLab のバージョンや設定によって `group%2Fsub1%2Fsub2%2Frepo` を正しく解釈しないケースがあり、3階層以上のサブグループでの動作が不確実。また `get_repository()` の別呼び出しパスにおいて `owner` がすでにスラッシュを含む場合に二重エンコードの危険もある。
- **影響**: サブグループ 3 階層以上の GitLab リポジトリで `repo.py` の `handle_view` からのリポジトリ取得が 404 になる可能性がある。
- **推奨修正**: GitLab の namespace を `urllib.parse.quote(namespace, safe='')` で統一的に扱うドキュメントを追加し、3階層以上のサブグループの動作をテストで確認する。`owner` を `ProjectConfig` レベルで保存するときに `namespace.full_path` から正規化する方針を検討する。
- **テスト**: `owner="group/sub1/sub2"`, `repo="myrepo"` で `_project_path()` が `/projects/group%2Fsub1%2Fsub2%2Fmyrepo` を返すことを確認するテスト。
- **検出回数**: 3/3

---

### [R6-09] 🟡 `_SSH_SCP_RE` がハイフン入りユーザー名・非ASCII ホスト名に対応しない

- **ファイル**: `src/gfo/detect.py` L39–41
- **説明**: `_SSH_SCP_RE = re.compile(r"^(?:\w+@)?(?P<host>[^:]+):(?P<path>.+?)(?:\.git)?/?$")` のユーザー部分 `\w+` は ASCII 英数字とアンダースコアのみにマッチする。`git@gitlab.com:my-org/my-repo.git` のようにハイフン入りのユーザー名部分が `_SSH_SCP_RE` にマッチしない（`_HTTPS_RE` でフォールバックされるため、SSH URL の場合に検出が失敗する可能性がある）。また国際化ドメイン名（IDN）をACE形式ではなくUnicode文字列で指定した場合、`_KNOWN_HOSTS` テーブルに存在しないため `probe_unknown_host` でHTTPリクエストが発生し、`probe_unknown_host()` の `requests.get()` で IDN が Punycode に変換されないまま使用される可能性もある。
- **影響**: ハイフンを含む SSH ユーザー名を使う GitLab 等で SSH URL の検出が失敗する可能性がある。国際化ドメインを使用する社内 Git サーバーでの自動検出が失敗する可能性がある。
- **推奨修正**: `_SSH_SCP_RE` の `\w+@` を `[^\s@]+@` に変更してハイフン等を許容する。`probe_unknown_host` に渡す前に `host.encode('idna').decode('ascii')` で punycode 変換する処理を追加する。
- **テスト**: `detect_from_url("git@gitlab.com:my-org/repo.git")` が正しく `owner="my-org"` を返すこと。`detect_from_url("https://git.例え.jp/owner/repo")` が正しく host を抽出することを確認するテスト。
- **検出回数**: 3/3

---

### [R6-10] 🟡 Azure DevOps WIQL クエリへの特殊文字インジェクション

- **ファイル**: `src/gfo/adapter/azure_devops.py` L174, L176
- **説明**: `list_issues()` の `assignee` および `label` パラメータが WIQL クエリ文字列に直接埋め込まれる。例: `conditions.append(f"[System.AssignedTo] = '{assignee}'")`。`assignee` や `label` にシングルクォートが含まれる場合（例: `"O'Brien"` や `"bug's label"`）、WIQL クエリ文字列が不正になる。Azure DevOps の WIQL は DDL 操作はできないが、論理条件を任意に変更されて意図しないデータが返される可能性がある。これは SQL インジェクションに類似した構造的問題。
- **影響**: 特殊文字を含むラベル名・担当者名で `gfo issue list` を実行すると、API が構文エラーを返すか、意図しないワークアイテムが返される。
- **推奨修正**: `label` および `assignee` の値を WIQL エスケープする（シングルクォートを `''` に置換する）。
- **テスト**: `label="bug's issue"` または `assignee="O'Brien"` で `list_issues` を呼び出した場合の WIQL クエリ文字列にシングルクォートが適切にエスケープされていることを確認するテスト。
- **検出回数**: 3/3

---

### [R6-11] 🟡 GitLab アダプターの `list_repositories()` でクエリパラメータをパスにハードコード

- **ファイル**: `src/gfo/adapter/gitlab.py` L207
- **説明**: `path = "/projects?owned=true&membership=true"` のように、パスにクエリパラメータをハードコードしている。`paginate_page_param()` は `params` 引数を使ってクエリパラメータを構築するが、`path` 自体にパラメータを埋め込んでいる。`paginate_page_param()` 内部で `client.get(path, params=params)` を呼ぶと、`path` のクエリストリングと `params` が混在したURLが生成される可能性があり、`per_page` や `page` と `owned`/`membership` が正しく結合されない可能性がある。
- **影響**: ページネーションが正しく機能しない可能性がある。特に2ページ目以降のリクエストで `owned=true&membership=true` が消える可能性がある。
- **推奨修正**: クエリパラメータを `params` 辞書に移動する: `params = {"owned": "true", "membership": "true"}`、`path = "/projects"` とする。
- **テスト**: `list_repositories()` の2ページ目リクエストに `owned=true` が含まれること。
- **検出回数**: 1/3

---

### [R6-12] 🟡 git リポジトリ外での実行時に不明瞭なエラーメッセージ

- **ファイル**: `src/gfo/git_util.py` L23–25, `src/gfo/config.py` L109–110, `src/gfo/exceptions.py` L9–12
- **説明**: git リポジトリ外で `gfo issue list` 等を実行すると、`run_git("config", "--local", ...)` または `get_remote_url()` が git コマンドの stderr（`fatal: not a git repository` または `fatal: --local can only be used inside a git repository`）をそのまま `GitCommandError` に包んで投げる。この例外は `detect_service()` で `DetectionError` に変換されないため、ユーザーには低レベルの git エラーメッセージが直接表示される。「git リポジトリ外では gfo は動作しない（ただし `gfo auth` 等は除く）」という文脈が伝わらない。
- **影響**: 新規ユーザーが git リポジトリ外でコマンドを実行した際に原因を理解しにくく、`gfo init` を実行すべきかどうか判断しにくい。
- **推奨修正**: `get_remote_url()` または `detect_service()` 内で `GitCommandError` を捕捉し、「not a git repository」を含む場合は適切な `DetectionError` または `ConfigError` に変換する。例: `"gfo must be run inside a git repository. Run 'git init' or clone a repository first."` または `"gfo init を実行してください"` 等のメッセージを付与する。
- **テスト**: 一時ディレクトリ（git 管理外）で `resolve_project_config()` や `detect_service()` を呼び出したとき、ユーザーフレンドリーなメッセージを持つ `DetectionError` または `ConfigError` が発生することを確認するテスト。
- **検出回数**: 3/3

---

### [R6-13] 🟡 `resolve_project_config` の `stype`/`shost` 分岐ロジックのバグ

- **ファイル**: `src/gfo/config.py` L113–127
- **説明**: `if stype and shost:` が `True` の場合（git config に両方が設定されている場合）のブロックで `detect_from_url(remote_url)` を呼び出して `owner/repo` を取得している。しかし `else` ブロック（git config が未設定の場合）では `detect_service()` が呼ばれ、git config の値を再度呼び出す二重呼び出しが発生する。より深刻なのは条件が `stype and shost`（両方必要）なのに対して、`stype` のみ設定・`shost` のみ設定のケースが `else` に落ちる点。片方だけ git config に設定されている場合、`detect_service()` で `DetectionError` が発生して手動設定が無視される可能性がある。
- **影響**: git config に `gfo.type` のみ設定され `gfo.host` が未設定の場合、`detect_service()` で `DetectionError` が発生し、手動設定が無視される。
- **推奨修正**: 条件を `if stype and shost` / `elif stype or shost` / `else` の 3 分岐に整理する。
- **テスト**: `gfo.type` のみ設定し `gfo.host` が未設定の場合に、`resolve_project_config()` が `detect_service()` の結果と git config の `stype` を正しく統合することを確認するテスト。
- **検出回数**: 2/3

---

### [R6-14] 🟡 非ASCII文字を含む owner/repo が URL エンコードされずHTTPパスに埋め込まれる

- **ファイル**: `src/gfo/adapter/github.py` L22–23, `src/gfo/adapter/gitea.py` L22–23, `src/gfo/adapter/backlog.py` L31
- **説明**: `_repos_path()` は `f"/repos/{self._owner}/{self._repo}"` のように文字列フォーマットで直接パスを構築する。`self._owner` や `self._repo` に日本語文字などの非ASCII文字が含まれる場合、URLエンコードが行われない。`requests` ライブラリは `path` 部分のエンコードを一部自動処理するが、保証される動作ではない。Gitea/GitHub では実際に日本語リポジトリ名（例: `プロジェクト`）が使える場合がある。
- **影響**: 非ASCII文字を含む owner/repo で API 404 または URL解析エラーが発生する可能性がある。
- **推奨修正**: `urllib.parse.quote(self._owner, safe='')` および `urllib.parse.quote(self._repo, safe='')` を適用する（GitLabアダプターの実装を参考にする）。
- **テスト**: `owner="日本語ユーザー"`, `repo="リポジトリ"` で `_repos_path()` が正しくエンコードされたパスを返すことを確認するテスト。
- **検出回数**: 1/3

---

### [R6-15] 🟡 `commands/issue.py` の Azure DevOps サービス種別文字列にタイポ

- **ファイル**: `src/gfo/commands/issue.py` L31
- **説明**: `if config.service_type == "azure_devops":` とアンダースコアを使用しているが、実際のサービス種別文字列は `"azure-devops"` （ハイフン）である。この条件は常に偽となり、Azure DevOps の `work_item_type` が `create_issue()` に渡されない。`Task` 以外の型（例: `Bug`, `User Story`）を指定した場合に無視される。
- **影響**: Azure DevOps で `gfo issue create --type Bug` 等を指定しても `work_item_type` が無視され、デフォルト値 (`"Task"`) が使われる。
- **推奨修正**: `"azure_devops"` を `"azure-devops"` に修正する。
- **テスト**: `service_type="azure-devops"` かつ `--type Bug` で `create_issue()` が `work_item_type="Bug"` を受け取ること。
- **検出回数**: 1/3

---

### [R6-16] 🟡 `git_util.py` で `git` コマンド不在時に `FileNotFoundError` が未処理

- **ファイル**: `src/gfo/git_util.py` L12–25
- **説明**: `run_git` は `subprocess.run` を使って git コマンドを実行するが、`FileNotFoundError`（`git` コマンドが PATH に存在しない場合）が `except` 節に含まれていない。`git` コマンドがインストールされていない環境（一部のCI/コンテナ環境）では `FileNotFoundError: [Errno 2] No such file or directory: 'git'` がそのままユーザーに表示される。
- **影響**: `git` コマンドがインストールされていない環境での実行時に不明確なエラーが表示される。
- **推奨修正**: `subprocess.run` の呼び出しを `try/except (FileNotFoundError, PermissionError)` でラップし、「git コマンドが見つかりません。Git をインストールしてください。」のようなメッセージを `GitCommandError` として送出する。
- **テスト**: `git` コマンドが存在しない環境（`PATH=''` 等）で `run_git()` を呼び出した際に `GitCommandError` が発生することを確認するテスト。
- **検出回数**: 1/3

---

### [R6-17] 🟡 `credentials.toml` の `\r` エスケープ漏れ

- **ファイル**: `src/gfo/auth.py` L129–140
- **説明**: `_write_credentials_toml` は `lines.append(f'"{key}" = "{escaped}"')` の形式でキーを常にダブルクォートで囲んで credentials.toml を書き出すため、ホスト名キーのクォート問題は存在しない。ただし `escaped` のエスケープ処理に `\r`（CR）のエスケープが欠けており、Windows環境でトークン末尾にCRが混入した場合（例: PowerShellでコピーペーストされたトークン）に値が壊れる可能性がある。
- **影響**: CRLFを含むトークンが保存された場合、次回読み込み時に不正なトークン文字列になる。
- **推奨修正**: `escaped` に `"\r"` のエスケープ（`"\r" → "\\r"`）を追加する。
- **テスト**: `\r` を含むトークンを `save_token()` → `load_tokens()` でラウンドトリップしたとき、元のトークン値と一致することを確認するテスト。
- **検出回数**: 2/3

---

### [R6-18] 🟢 Windows での `os.getlogin()` 失敗リスク

- **ファイル**: `src/gfo/auth.py` L79
- **説明**: `os.getlogin()` は Windows 環境でサービスアカウントやコンテナ環境（Docker・CI）では `OSError: [Errno 6] No such device or address` を発生させることがある。外側に `except OSError: pass` で握りつぶしているため動作は継続するが、`icacls` コマンド自体が呼び出されない（＝ファイルのアクセス権設定が行われない）という問題が残る。また MSYS2/Git Bash 環境では `str(path)` を `icacls` に渡す際に `/c/Users/...` のようなパスが `icacls` で認識されない場合がある。
- **影響**: Windows CI/Docker コンテナ内でトークンが保存されるが、適切なパーミッションが設定されないリスク。MSYS2 環境で `icacls` が失敗し、ファイル権限が設定されない。ただし `except OSError: pass` により処理は継続する。
- **推奨修正**: `os.getlogin()` の代わりに `os.environ.get("USERNAME", "")` や `os.environ.get("USERDOMAIN", "") + "\\" + os.environ.get("USERNAME", "")` を使うか、`icacls` に渡すパスを `os.path.abspath(str(path))` で正規化する。エラー時に警告メッセージを出力することも検討する。
- **テスト**: `os.getlogin()` が `OSError` を発生させるモック環境で `save_token` が例外なく完了することを確認するテスト。
- **検出回数**: 3/3

---

### [R6-19] 🟢 設定ファイルへのシンボリックリンクでの書き込み・権限問題

- **ファイル**: `src/gfo/auth.py` L66–85, `src/gfo/config.py` L55–59
- **説明**: `save_token()` は `_write_credentials_toml(path, tokens)` でファイルを上書き後に `os.chmod(path, 0o600)` を実行する。シンボリックリンクが読み取り専用ファイルや別ユーザーが所有するファイルへのリンクだった場合に `PermissionError` が未捕捉で発生する。また `config_dir.mkdir(parents=True, exist_ok=True)` が `config_dir` がシンボリックリンクの場合でも成功し、リンク先ディレクトリへの意図しない書き込みが発生する可能性がある。`load_user_config()` でも同様に `PermissionError` が未処理。
- **影響**: セキュリティ設定ファイルの配置先がシンボリックリンクでリダイレクトされている場合、意図しない場所にトークンが保存される。credentials.toml がシンボリックリンクで書き込み不可の場合、トークン保存時に `PermissionError` がそのまま伝播する。
- **推奨修正**: `get_credentials_path().resolve()` を使って実体パスを確認するか、シンボリックリンクを警告する処理を追加する。`save_token` 内でファイル書き込み時の `PermissionError` を捕捉し、適切なエラーメッセージを表示する。
- **テスト**: `credentials_path` がシンボリックリンクの場合に `save_token` の動作を確認するテスト。`config.toml` が `chmod 000` の状態で `load_user_config()` を呼んだ場合に `ConfigError` が発生することを確認するテスト。
- **検出回数**: 2/3

---

### [R6-20] 🟢 不正な `config.toml` で `TOMLDecodeError` が露出する

- **ファイル**: `src/gfo/config.py` L53–59
- **説明**: `load_user_config()` は `tomllib.load(f)` を呼び出すが、`config.toml` が不正な TOML 形式（例: 手動編集で壊れた場合）だと `tomllib.TOMLDecodeError` が発生し、`GfoError` を継承していないため `cli.py` のハンドラで捕捉されずスタックトレースが表示される。同様に `auth.py` の `load_tokens()` も `PermissionError` が未処理。
- **影響**: 設定ファイルが破損した場合にユーザーが `TOMLDecodeError: ...` という低レベルエラーを受け取る。
- **推奨修正**: `tomllib.TOMLDecodeError` を捕捉して `ConfigError(f"Invalid config file: {path}")` に変換する。`open()` を `try/except PermissionError` でラップし、`ConfigError` を送出する。
- **テスト**: 不正な TOML 内容を持つ `config.toml` で `load_user_config()` が `ConfigError` を送出することを確認するテスト。
- **検出回数**: 2/3

---

### [R6-21] 🟢 `subprocess.TimeoutExpired` が未処理

- **ファイル**: `src/gfo/git_util.py` L12–25, L80–95
- **説明**: `run_git()` は `timeout=_DEFAULT_TIMEOUT` (30 秒) を指定しているが、`subprocess.TimeoutExpired` 例外の処理が存在しない。この例外は `GfoError` を継承していないため `cli.py` のハンドラで捕捉されず、スタックトレースが表示される。また `git_clone()` (L80–95) では `timeout=None` が設定されており、大容量リポジトリのクローンが永久にハングする可能性がある。
- **影響**: git コマンドが 30 秒以上かかる（例: 非常に遅いネットワーク）場合に、スタックトレースがユーザーに表示される。`git_clone` では無制限待機になる。
- **推奨修正**: `subprocess.TimeoutExpired` を捕捉して `GitCommandError` または `NetworkError` に変換する。`git_clone` には現実的な上限タイムアウトを設定するか、`--progress` フラグと組み合わせて進捗表示を行う。
- **テスト**: `subprocess.run` が `TimeoutExpired` を送出するモックで `run_git` が `GitCommandError` を送出することを確認するテスト。
- **検出回数**: 1/3

---

### [R6-22] 🟢 `limit=1` でも `per_page=30` 件取得する非効率

- **ファイル**: `src/gfo/http.py` L155–156
- **説明**: `paginate_link_header` では `params[per_page_key] = per_page` で固定の `per_page=30` を API に渡しており、`limit` に応じて調整する仕組みがない。`limit=1` でも30件分のAPIレスポンスが発生する（帯域・レート制限の無駄）。
- **影響**: 不必要なAPI呼び出しコストが発生する。GitHub/GitLab等のレート制限消費が増える。
- **推奨修正**: `per_page = min(per_page, limit)` として不要なデータ取得を削減する（ただし `limit=0` の無限取得ケースと矛盾しないよう注意）。
- **テスト**: `limit=1` で `paginate_link_header` を呼び出した際に APIリクエストの `per_page` パラメータが `1` に調整されることを確認するテスト。
- **検出回数**: 1/3

---

### [R6-23] 🟢 `probe_unknown_host` が HTTPS 失敗時に HTTP にフォールバックしない

- **ファイル**: `src/gfo/detect.py` L187–223
- **説明**: `probe_unknown_host` はデフォルトで `scheme="https"` を使用してプローブを実行する。HTTPS でのプローブが失敗（SSL証明書エラー等）した場合に HTTP にフォールバックする仕組みがなく、`except Exception: pass` で全例外を無視する。自己署名証明書を使う社内 Gitea サーバーでは HTTPS プローブが常に失敗し、サービス種別の自動検出ができない。
- **影響**: 自己署名証明書を使う社内サーバーで自動検出が失敗し、`gfo init` が必要になる（ユーザー体験が悪い）。
- **推奨修正**: SSL検証失敗の場合に `verify=False` で再試行するか、検出失敗をより明確なメッセージでユーザーに伝える（`gfo init --type gitea --host internal.example.com` の案内など）。
- **テスト**: SSL証明書エラーをモックした状態で `probe_unknown_host` を呼び出し、例外が伝播せずに `None` を返すことを確認するテスト。
- **検出回数**: 1/3

---

### [R6-24] 🟢 Windows・Git Bash 環境での設定ディレクトリパス問題

- **ファイル**: `src/gfo/config.py` L30–37
- **説明**: `get_config_dir()` は Windows で `APPDATA` 環境変数を使い、未設定の場合 `Path.home() / "AppData" / "Roaming" / "gfo"` にフォールバックする。企業環境でリダイレクトフォルダポリシーが適用されている場合、`APPDATA` が `%USERPROFILE%` と異なるドライブにあることがあり、フォールバックが正しくない可能性がある。また MINGW64（Git Bash on Windows）環境では `sys.platform` が `"win32"` を返す場合と返さない場合があり、Linux 用のパス（`~/.config/gfo`）が使われる可能性がある。ユーザーホームディレクトリが UNC パス（`\\server\share\users\user`）の場合にも問題が生じる可能性がある。
- **影響**: 特定のWindows環境（UNCパス、Git Bash、企業リダイレクト）で設定ファイルが期待しない場所に作成される可能性がある。
- **推奨修正**: `sys.platform` チェックに加えて環境変数 `MSYSTEM`（MINGW環境を示す）を確認するか、`platformdirs` ライブラリの採用を検討する。フォールバックを使用する場合は警告ログを出力する。
- **テスト**: `APPDATA` が未設定の Windows 環境をシミュレートして `get_config_dir()` が正しいパスを返すことを確認するテスト。
- **検出回数**: 2/3

---

### [R6-25] 🟢 `output()` に非データクラスオブジェクトを渡した場合に内部エラーが露出

- **ファイル**: `src/gfo/output.py` L20–21
- **説明**: `output()` は `fields` が `None` の場合 L20–21 で `dataclasses.fields(items[0])` を呼び出すが、`items[0]` がデータクラスでない場合（例: `dict` を誤って渡した場合）に `TypeError` が発生し、適切なエラーメッセージが表示されない。なお L17–18 は空リストの早期リターン箇所であり、問題の本質はその後の `dataclasses.fields` 呼び出し箇所である。
- **影響**: 非データクラスオブジェクトを `output()` に渡した場合に内部エラーが露出する。
- **推奨修正**: `output()` の先頭で `dataclasses.is_dataclass(items[0])` を確認するか、`TypeError` を捕捉してユーザーフレンドリーなエラーを表示する。
- **テスト**: `output([{"key": "value"}], fmt="table")` が適切なエラーを発生させることを確認するテスト。
- **検出回数**: 1/3

---

### [R6-26] 🟢 URLフィルターのラベル名に特殊文字が含まれる場合の誤動作

- **ファイル**: `src/gfo/adapter/github.py` L155–160, `src/gfo/adapter/gitlab.py` L172–177
- **説明**: `list_issues` で `label` パラメータをクエリパラメータとして渡す際、GitLab では `labels` パラメータにカンマ区切りで複数ラベルを渡す設計があり、ラベル名にカンマが含まれる場合に誤動作する。また Backlog の `label` フィルターは `keyword` に渡されているため（`params["keyword"] = label`）、ラベル名ではなくキーワード検索になっており意図が異なる可能性がある。
- **影響**: 特殊文字を含むラベル名でフィルターが意図通りに動作しないケースがある。Backlog の `label` フィルターがキーワード検索になっていることはユーザーの期待と異なる。
- **推奨修正**: ラベル名のバリデーションまたはドキュメントによる制約の明示。Backlog の `label` フィルターがキーワード検索であることをドキュメントに明記する。
- **テスト**: スペース・絵文字を含むラベル名（例: `"bug 🐛"`）を `label` フィルターに渡した際の動作確認テスト。
- **検出回数**: 1/3

---

## サマリーテーブル

| ID | 重大度 | ファイル | 行 | 説明 | 検出回数 |
|----|--------|---------|------|------|----------|
| R6-01 | 🔴 重大 | `http.py` | L177, L211, L256, L290, L323 | `limit=0` で全ページネーション関数が無限ループ | 3/3 |
| R6-02 | 🔴 重大 | `output.py` | L38, L51, L64–70 | タブ・改行を含む値がテーブル/プレーン出力を破壊 | 3/3 |
| R6-03 | 🔴 重大 | `http.py` | L164–171, L243 | 次ページ取得で `_auth_params` が欠落（Backlog 等で 401） | 3/3 |
| R6-04 | 🔴 重大 | `adapter/github.py`, `adapter/gitea.py` | L231, L247 | `list_labels()`/`list_milestones()` がページネーション未対応 | 1/3 |
| R6-05 | 🟡 中 | `output.py` | L17–18 | 空リスト時に何も出力しない（静寂な失敗） | 1/3 |
| R6-06 | 🟡 中 | `output.py` | L40–43 | 多バイト文字・絵文字・長文値のテーブル幅計算不正 | 3/3 |
| R6-07 | 🟡 中 | `http.py` | L218 | `X-Next-Page` が変換不能値のとき `ValueError` が未処理 | 2/3 |
| R6-08 | 🟡 中 | `adapter/gitlab.py` | L25 | GitLab サブグループ 3 階層以上で動作が不確実（設計的懸念） | 3/3 |
| R6-09 | 🟡 中 | `detect.py` | L39–41 | `_SSH_SCP_RE` がハイフン入りユーザー名・IDN に対応しない | 3/3 |
| R6-10 | 🟡 中 | `adapter/azure_devops.py` | L174, L176 | WIQL クエリへの特殊文字インジェクション | 3/3 |
| R6-11 | 🟡 中 | `adapter/gitlab.py` | L207 | `list_repositories()` でクエリパラメータをパスにハードコード | 1/3 |
| R6-12 | 🟡 中 | `git_util.py`, `config.py`, `exceptions.py` | L23–25, L109 | git リポジトリ外での不明瞭なエラーメッセージ | 3/3 |
| R6-13 | 🟡 中 | `config.py` | L113–127 | `resolve_project_config` の `stype`/`shost` 分岐ロジックのバグ | 2/3 |
| R6-14 | 🟡 中 | `adapter/github.py`, `adapter/gitea.py`, `adapter/backlog.py` | L22–23, L31 | 非ASCII owner/repo が URL エンコードされない | 1/3 |
| R6-15 | 🟡 中 | `commands/issue.py` | L31 | `azure_devops` → `azure-devops` のタイポ | 1/3 |
| R6-16 | 🟡 中 | `git_util.py` | L12–25 | `git` コマンド不在時に `FileNotFoundError` が未処理 | 1/3 |
| R6-17 | 🟡 中 | `auth.py` | L129–140 | `credentials.toml` の `\r` エスケープ漏れ | 2/3 |
| R6-18 | 🟢 軽微 | `auth.py` | L79 | Windows の `os.getlogin()` 失敗リスクとパス渡し問題 | 3/3 |
| R6-19 | 🟢 軽微 | `auth.py`, `config.py` | L66–85, L55–59 | シンボリックリンクへの書き込み失敗が未処理 | 2/3 |
| R6-20 | 🟢 軽微 | `config.py`, `auth.py` | L53–59, L88–95 | 不正な `config.toml` で `TOMLDecodeError`・`PermissionError` が露出 | 2/3 |
| R6-21 | 🟢 軽微 | `git_util.py` | L12–25, L80–95 | `subprocess.TimeoutExpired` が未処理・`git_clone` の無限待機 | 1/3 |
| R6-22 | 🟢 軽微 | `http.py` | L155–156 | `limit=1` でも `per_page=30` 件取得する非効率 | 1/3 |
| R6-23 | 🟢 軽微 | `detect.py` | L187–223 | `probe_unknown_host` が HTTPS 失敗時に HTTP にフォールバックしない | 1/3 |
| R6-24 | 🟢 軽微 | `config.py` | L30–37 | Windows・Git Bash 環境での設定ディレクトリパス問題 | 2/3 |
| R6-25 | 🟢 軽微 | `output.py` | L20–21 | 非データクラスを渡した場合に内部エラーが露出 | 1/3 |
| R6-26 | 🟢 軽微 | `adapter/github.py`, `adapter/gitlab.py` | L155, L172 | ラベル名の特殊文字でフィルター誤動作の可能性 | 1/3 |

---

## 推奨アクション (優先度順)

1. **[R6-15] `commands/issue.py` の `azure_devops` タイポを即修正する** — 単純な文字列1文字の修正で既存テストへの影響も最小限。Azure DevOps ユーザーの `work_item_type` 指定が全件無視されている致命的バグ。

2. **[R6-03] Backlog 次ページ認証消失を修正する** — `paginate_link_header` / `paginate_response_body` の next_url リクエストで `_auth_params` を適切に付与する。本番環境で Backlog ユーザーに直接影響する重大バグ。

3. **[R6-01] `limit=0` の無限ループを対処する** — 全ページネーション関数で `limit <= 0` をガードする。CLIの `--limit` 引数に `min=1` バリデーションを追加する。メモリ枯渇・レート制限超過のリスクがある。

4. **[R6-02] テーブル出力の改行・タブ混入を防ぐ** — `format_table` と `format_plain` の前に値をサニタイズする。CI の gfo 出力をパースするスクリプトを保護する。

5. **[R6-04] GitHub/Gitea の `list_labels()`/`list_milestones()` にページネーションを適用する** — `paginate_link_header()` を使用して100件超のラベル・マイルストーンを正しく取得できるようにする。

6. **[R6-10] Azure DevOps WIQL クエリのインジェクション対策** — ラベル・担当者名のシングルクォートをエスケープする（`'` → `''`）。

7. **[R6-12] git リポジトリ外でのエラーメッセージ改善** — `GitCommandError` を `DetectionError`/`ConfigError` にラップして「gfo init を実行してください」のメッセージを付与する。

8. **[R6-11] GitLab `list_repositories()` のクエリパラメータを `params` 辞書に移動する** — ページネーションの正確性確保。

9. **[R6-13] `resolve_project_config` の分岐バグを修正する** — 条件を3分岐に整理し、片方の git config 設定のみの場合の動作を正しくする。

10. **[R6-06] `wcwidth` を使ったテーブル幅計算に対応する** — 日本語・絵文字タイトルのアライメントを修正する。少なくとも改行・タブの除去は必須。

11. **[R6-05] 空リストの出力を改善する** — `fmt=json` で `[]`、`table`/`plain` で `"No results found."` メッセージを出力する。

12. **[R6-14] 非ASCII owner/repo の URL エンコード対応** — GitHub・Gitea・Backlog アダプターの `_repos_path()` に `urllib.parse.quote` を適用する。

13. **[R6-20] `config.toml` 破損時・権限不足時のエラーハンドリング** — `TOMLDecodeError` を `ConfigError` に、`PermissionError` を `ConfigError` に変換する。

14. **[R6-16] `git` コマンド不在時のエラー処理** — `subprocess.run` を `try/except FileNotFoundError` でラップし、インストール案内を表示する。

15. **[R6-09] `_SSH_SCP_RE` でハイフン入り SSH ユーザー名・IDN に対応する** — `\w+@` を `[^\s@]+@` に変更し、IDN の punycode 変換処理を追加する。

16. **[R6-21] `subprocess.TimeoutExpired` のハンドリング** — `GitCommandError` に変換してユーザーフレンドリーなメッセージを表示する。`git_clone` に現実的な上限タイムアウトを設定する。

17. **[R6-18] Windows での `os.getlogin()` を堅牢な代替に変更する** — `os.environ.get("USERNAME", "")` を使ったフォールバックを実装する。

18. **[R6-17] `credentials.toml` の `\r` エスケープを追加する** — Windows 環境での CRLF 混入トークン対策。

19. **[R6-22] `limit` に応じた `per_page` の最適化** — `per_page = min(per_page, limit)` で不要なデータ取得を削減する。

20. **[R6-08] GitLab サブグループ 3 階層以上の動作をテストで確認する** — `quote(..., safe='')` により `%2F` エンコードは行われているが、3階層以上のサブグループを GitLab API が正しく解釈するか実際の動作を検証し、必要であれば正規化処理を追加する。

---

## 次ラウンドへの申し送り

- **Round 7 候補: セキュリティ観点の深掘り**
  - `credentials.toml` のパーミッション設定が Windows / Linux / macOS でそれぞれ適切かのセキュリティ監査
  - `--token` フラグで渡されたトークンがプロセスリスト（`ps aux`）に表示されるリスク
  - `paginate_link_header` で `next_url` が外部ドメインにリダイレクトされる可能性（SSRF 類似のリスク）
  - 複数の gfo プロセスが同時に `credentials.toml` を書き込んだ場合のレースコンディション

- **Round 7 候補: 並行性・再入可能性**
  - `BacklogAdapter._project_id` キャッシュが並行実行時に競合する可能性
  - 複数ターミナルから同じ `credentials.toml` に同時書き込みした場合のファイルロックの必要性

- **Round 7 候補: テストカバレッジ分析**
  - `adapter/azure_devops.py` の WIQL クエリ生成のユニットテスト追加
  - `config.py` の `resolve_project_config` 分岐網羅テスト
  - `output.py` の `format_table` / `format_plain` / `format_json` に対する境界値テスト

- **未解決の設計課題**
  - `list_issues` は `"pull_request" not in r` でPRを除外しているが、`paginate_link_header` で余分にデータを取得してからフィルターしているため、`limit` との相互作用（フィルター前後でカウントが変わる）に未解決の問題がある可能性がある
  - `auth_cmd.py` の `handle_status` における環境変数ステータスでのホスト名表示が混乱を招く可能性がある（`auth.py` L115）
  - タイムゾーン: ISO 8601 日時文字列のサービスごとの差異（UTC vs ローカルタイムゾーン）の正規化
  - プロキシ環境: NTLM 等の認証が必要な企業環境でのテストが未実施
  - `init.py` 対話モードの EOF（Ctrl+D / パイプ終端）処理が未実装
