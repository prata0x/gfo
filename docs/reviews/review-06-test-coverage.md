# gfo Review Report — Round 5: テストカバレッジの穴・テストケース不足（統合版）

## 概要
- レビュー日: 2026-03-09
- レビュー回数: 3回（重複排除済み）
- 対象ファイル:
  - `src/gfo/__main__.py`
  - `src/gfo/http.py`
  - `src/gfo/output.py`
  - `src/gfo/config.py`
  - `src/gfo/cli.py`
  - `src/gfo/commands/init.py`, `pr.py`, `repo.py`, `issue.py`, `label.py`, `milestone.py`, `release.py`, `auth_cmd.py`
  - `src/gfo/adapter/github.py`, `gitlab.py`, `gitea.py`, `forgejo.py`, `gogs.py`, `gitbucket.py`, `bitbucket.py`, `azure_devops.py`, `backlog.py`
  - 対応テストファイル全て (`tests/` 以下)
- 発見事項: 重大 5 / 中 12 / 軽微 5

---

## 発見事項

### [R5-01] 🔴 重大 `__main__.py` のテストが存在しない

- **ファイル**: `src/gfo/__main__.py` L1-6（対応テストなし）
- **説明**: `__main__.py` は `python -m gfo` エントリポイントとして機能し、`sys.exit(main())` を呼び出す。`tests/` ディレクトリ内に `__main__` という語句を含むファイルが一切存在せず、このファイルをカバーするテストが皆無である。`python -m gfo` 形式での起動が正常動作するか、終了コードが意図通り伝搬するかが検証されていない。
- **影響**: `python -m gfo` エントリポイントが壊れても CI で検知できない。pip インストール後の動作確認も自動化されない。
- **推奨テストケース**:
  ```python
  # tests/test_main.py
  import subprocess, sys

  def test_python_m_gfo_no_args():
      """python -m gfo は引数なしで exit code 1 を返す。"""
      result = subprocess.run(
          [sys.executable, "-m", "gfo"],
          capture_output=True, text=True,
      )
      assert result.returncode == 1
      assert "gfo" in result.stdout  # help テキスト

  def test_python_m_gfo_version():
      result = subprocess.run(
          [sys.executable, "-m", "gfo", "--version"],
          capture_output=True, text=True,
      )
      assert result.returncode == 0
      assert "gfo" in result.stdout
  ```
- **検出回数**: 3/3

---

### [R5-02] 🔴 重大 `http.py` の 429 リトライ後のネットワーク障害シナリオが未テスト

- **ファイル**: `src/gfo/http.py` L82-96（リトライ後の `ConnectionError` / `Timeout` ハンドリング）
- **説明**: 既存の `test_429_retry_also_429_raises` はリトライ後に再度 429 が返る場合をカバーしているが、以下のシナリオが未テストである:
  1. リトライ時に `ConnectionError` が発生するケース（L92-94 のパス）
  2. リトライ時に `Timeout` が発生するケース（L94-95 のパス）
  これらのコードパスは `_session.request()` の except 節として存在しているが、テストで一度も実行されない。リトライ中のネットワーク切断が `NetworkError` ではなく未処理の `requests.ConnectionError` として漏れる可能性がある。
- **影響**: ネットワーク障害がリトライ後に発生した場合の例外伝播が保証されない。
- **推奨テストケース**:
  ```python
  @responses.activate
  def test_429_retry_then_connection_error(self, monkeypatch):
      import requests as req
      monkeypatch.setattr("gfo.http.time.sleep", lambda _: None)
      responses.add(responses.GET, f"{BASE}/x", status=429,
                    headers={"Retry-After": "1"})
      responses.add(responses.GET, f"{BASE}/x",
                    body=req.ConnectionError("disconnected"))
      c = HttpClient(BASE)
      with pytest.raises(NetworkError):
          c.get("/x")

  @responses.activate
  def test_429_retry_then_timeout(self, monkeypatch):
      from requests.exceptions import ReadTimeout
      monkeypatch.setattr("gfo.http.time.sleep", lambda _: None)
      responses.add(responses.GET, f"{BASE}/x", status=429,
                    headers={"Retry-After": "1"})
      responses.add(responses.GET, f"{BASE}/x", body=ReadTimeout("timeout"))
      c = HttpClient(BASE)
      with pytest.raises(NetworkError):
          c.get("/x")
  ```
- **検出回数**: 2/3

---

### [R5-03] 🔴 重大 `config.py` の `resolve_project_config()` における設定解決優先度テストが不足

- **ファイル**: `src/gfo/config.py` L108-158 / `tests/test_config.py` L242-349
- **説明**: `resolve_project_config()` には以下の未テストシナリオが存在する:
  1. git config に `stype` のみある（`shost` がない）場合や `shost` のみある（`stype` がない）場合のパス（L113 の `if stype and shost:` 分岐）
  2. git config に `stype` と `shost` が両方ある場合に `detect_service()` が呼ばれないことの明示的検証
  3. `gfo.organization` / `gfo.project-key` の git config 上書きパス（L135-140）の上書き検証
  4. `gfo.api-url` が git config に設定されている場合に host_config より優先されるか
  既存テストは「両方ある」か「両方ない」の2ケースしかカバーしていない。
- **影響**: 設定の片側だけが git config に書かれているケースで `detect_service()` を呼ばずに誤った設定が使われるバグを検出できない。git config の上書きが機能しない場合も検知できない。
- **推奨テストケース**:
  ```python
  def test_resolve_git_config_does_not_call_detect_service():
      """git config に type/host があれば detect_service は呼ばれない。"""
      git_cfg = {"gfo.type": "github", "gfo.host": "github.com",
                 "gfo.api-url": None, "gfo.organization": None, "gfo.project-key": None}
      with (
          patch("gfo.git_util.git_config_get", side_effect=_mock_git_config(git_cfg)),
          patch("gfo.git_util.get_remote_url",
                return_value="https://github.com/owner/repo.git"),
          patch("gfo.detect.detect_service") as mock_detect,
      ):
          resolve_project_config()
      mock_detect.assert_not_called()

  def test_resolve_only_stype_in_git_config():
      """git config に type のみある場合 → detect_service() が呼ばれる。"""
      from gfo.detect import DetectResult
      detect_result = DetectResult(service_type="github", host="github.com",
                                   owner="user", repo="repo")
      git_cfg = {"gfo.type": "github", "gfo.host": None, "gfo.api-url": None,
                 "gfo.organization": None, "gfo.project-key": None}
      with patch("gfo.git_util.git_config_get", side_effect=_mock_git_config(git_cfg)), \
           patch("gfo.detect.detect_service", return_value=detect_result) as mock_detect:
          cfg = resolve_project_config()
      mock_detect.assert_called_once()
      assert cfg.service_type == "github"

  def test_resolve_git_config_org_override():
      """git config の gfo.organization が detect 結果を上書きする。"""
      from gfo.detect import DetectResult
      detect_result = DetectResult(
          service_type="azure-devops", host="dev.azure.com",
          owner="org", repo="repo", organization="original-org", project="proj",
      )
      git_cfg = {"gfo.type": None, "gfo.host": None, "gfo.api-url": None,
                 "gfo.organization": "override-org", "gfo.project-key": None}
      with (
          patch("gfo.git_util.git_config_get", side_effect=_mock_git_config(git_cfg)),
          patch("gfo.detect.detect_service", return_value=detect_result),
      ):
          cfg = resolve_project_config()
      assert cfg.organization == "override-org"
  ```
- **検出回数**: 3/3

---

### [R5-04] 🔴 重大 コマンドレイヤーで `--format plain` のテストが全コマンドにわたって欠如

- **ファイル**: `tests/test_commands/test_pr.py`, `test_issue.py`, `test_repo.py`, `test_release.py`, `test_label.py`, `test_milestone.py`
- **説明**: 全コマンドテストにおいて `fmt="plain"` を指定したテストケースが存在しない。`test_output.py` では `format_plain` の単体テストがあるが、コマンド層から `output(..., fmt="plain")` を経由した際の実際の出力検証が行われていない。`fmt="table"` と `fmt="json"` は各コマンドでテストされているが、`fmt="plain"` は完全に抜けている。
- **影響**: `--format plain` でスクリプト連携した場合の出力崩れを検知できない。タブ区切りかつヘッダーなしの出力が保証されない。
- **推奨テストケース**:
  ```python
  # test_pr.py に追加
  def test_plain_format(self, sample_config, mock_adapter, capsys):
      args = make_args(state="open", limit=30)
      with _patch_all(sample_config, mock_adapter):
          pr_cmd.handle_list(args, fmt="plain")

      out = capsys.readouterr().out
      assert "\t" in out  # タブ区切り
      assert "NUMBER" not in out  # ヘッダーなし
      assert "1" in out
  ```
- **検出回数**: 3/3

---

### [R5-05] 🔴 重大 `issue.py` の `"azure_devops"` アンダースコア表記によるサービスタイプ不一致（潜在的バグ）

- **ファイル**: `src/gfo/commands/issue.py` L31
- **説明**: `issue.py` の L31 で `config.service_type == "azure_devops"` と比較しているが、プロジェクト全体での正しい値は `"azure-devops"`（ハイフン）である。`test_issue.py` の `test_azure_devops_work_item_type` は `_make_config("azure_devops")` を使用して偽のサービスタイプで呼んでいるため、実際の `"azure-devops"` を使ったテストがなく、この潜在的なバグを隠蔽している。他の箇所はすべてハイフン区切りを使用しており、この不一致がバグである可能性が高い。
- **影響**: 実運用で Azure DevOps を使った際に `work_item_type` が渡されず、デフォルトの `title`/`body` のみで issue 作成されてしまう可能性がある。
- **推奨テストケース**:
  ```python
  def test_azure_devops_work_item_type_with_correct_service_type(self):
      """service_type は "azure-devops" (ハイフン) で work_item_type が渡されるべき。"""
      config = _make_config("azure-devops")  # ハイフンが正しい
      adapter = _make_adapter(self.issue)
      args = make_args(title="My Task", body="", assignee=None, label=None,
                       type="Bug", priority=None)
      with _patch_all(config, adapter):
          issue_cmd.handle_create(args, fmt="table")
      call_kwargs = adapter.create_issue.call_args.kwargs
      assert call_kwargs.get("work_item_type") == "Bug"
  ```
- **検出回数**: 1/3

---

### [R5-06] 🟡 中 `output.py` の `format_table()` におけるエッジケースが不足

- **ファイル**: `src/gfo/output.py` L40-53 / `tests/test_output.py` L52-60
- **説明**: `test_column_width_adjustment` はカラム幅の調整を確認しているが、以下のエッジケースが未テストである:
  1. ヘッダー名がデータより長い場合（ヘッダー幅が基準になるパス）— セパレーターの幅がヘッダー幅と一致することの明示的な検証がない
  2. データ値が空文字列の場合
  3. 複数カラムで一部だけ長い値を持つ場合の末尾 rstrip 動作
- **影響**: カラム幅計算の回帰バグを見落とす可能性がある。
- **推奨テストケース**:
  ```python
  def test_header_width_dominates_when_value_shorter(self):
      """ヘッダー名が値より長い場合、セパレーターはヘッダー幅に合わせる。"""
      result = format_table(
          [SampleItem(1, "X", "Y", "Z")],
          ["number", "title", "state", "author"],
      )
      lines = result.split("\n")
      # "NUMBER" は 6文字、値 "1" は 1文字 → セパレーターは "------"
      assert "------" in lines[1]

  def test_empty_field_value_pads_to_header_width():
      result = format_table([SampleItem(1, "", "open", "alice")], ["number", "title"])
      lines = result.split("\n")
      # ヘッダー "TITLE" (5文字) 以上の幅でパディングされる
      assert "NUMBER" in result

  def test_table_trailing_whitespace_stripped(self):
      """末尾に余分な空白が付かないことを確認する。"""
      result = format_table(
          [SampleItem(1, "Short", "x", "y")],
          ["number", "title"],
      )
      for line in result.split("\n"):
          assert line == line.rstrip()
  ```
- **検出回数**: 3/3

---

### [R5-07] 🟡 中 `config.py` の `_build_default_api_url()` で Azure DevOps に project のみ欠ける場合が未テスト

- **ファイル**: `src/gfo/config.py` L193-198 / `tests/test_config.py` L187-189
- **説明**: `test_build_azure_devops_missing_org` は organization がない場合をテストしているが、organization はあって project だけない場合のパスが未テスト（L194 の条件は `not organization or not project`）。
- **影響**: Azure DevOps で project_key だけ設定漏れした場合のエラー処理が検証されない。
- **推奨テストケース**:
  ```python
  def test_build_azure_devops_missing_project():
      with pytest.raises(ConfigError, match="organization"):
          _build_default_api_url("azure-devops", "dev.azure.com", organization="myorg")
  ```
- **検出回数**: 1/3

---

### [R5-08] 🟡 中 `GogsAdapter` の Issue 操作（write 系）テストが存在しない

- **ファイル**: `src/gfo/adapter/gogs.py` / `tests/test_adapters/test_gogs.py`
- **説明**: `GogsAdapter` は `GiteaAdapter` を継承しており、Issue 系（`create_issue`, `close_issue`, `get_issue`）は GiteaAdapter から継承されている。しかし `test_gogs.py` の `TestInheritedOperations` には `list_issues` と `list_issues_pagination` しか存在せず、Issue の write 系操作テストが一切ない。加えて `list_repositories`、`create_repository`、`get_repository`、`list_releases`、`create_release` 等のリポジトリ・リリース操作も未テスト。
- **影響**: GogsAdapter が Issue の write 系操作やリポジトリ操作で予期しない挙動を示しても検知できない。継承チェーンが正しく機能しているかの保証がない。
- **推奨テストケース**:
  ```python
  class TestInheritedIssueOperations:
      def test_create_issue(self, mock_responses, gogs_adapter):
          mock_responses.add(responses.POST, f"{REPOS}/issues",
                             json=_issue_data(), status=201)
          issue = gogs_adapter.create_issue(title="Test", body="body")
          assert issue.number == 1

      def test_close_issue(self, mock_responses, gogs_adapter):
          mock_responses.add(responses.PATCH, f"{REPOS}/issues/1",
                             json=_issue_data(state="closed"), status=200)
          gogs_adapter.close_issue(1)

      def test_get_issue(self, mock_responses, gogs_adapter):
          mock_responses.add(responses.GET, f"{REPOS}/issues/1",
                             json=_issue_data(), status=200)
          issue = gogs_adapter.get_issue(1)
          assert issue.number == 1
  ```
- **検出回数**: 3/3

---

### [R5-09] 🟡 中 複数のアダプターで HTTP エラーレスポンス（404, 401, 422 等）のテストが欠如

- **ファイル**: `tests/test_adapters/test_github.py`, `test_gitlab.py`, `test_gitea.py`, `test_bitbucket.py`, `test_backlog.py`, `test_azure_devops.py`
- **説明**: `test_forgejo.py` と `test_gitbucket.py` には `TestErrorHandling` クラスで 404/401/500 のエラーテストが存在し、HTTP エラーが `NotFoundError`/`AuthenticationError`/`ServerError` に変換されることを検証している。しかし GitHub・GitLab・Gitea・Bitbucket・Backlog・AzureDevOps の各アダプターには対応するクラスが存在しない。特に 422 Unprocessable Entity（重複ラベル名など）を返す write 系操作のエラーテストが全アダプターで欠如している。
- **影響**: HTTP エラーが正しい例外に変換されることが一部アダプターでのみ保証されている。将来アダプターごとに特殊な `_handle_response` オーバーライドを追加した際のバグを見落とすリスク。
- **推奨テストケース**:
  ```python
  # test_github.py に追加
  class TestErrorHandling:
      def test_get_issue_not_found(self, mock_responses, github_adapter):
          mock_responses.add(responses.GET, f"{REPOS}/issues/999", status=404)
          with pytest.raises(NotFoundError):
              github_adapter.get_issue(999)

      def test_401_raises_auth_error(self, mock_responses, github_adapter):
          mock_responses.add(responses.GET, f"{REPOS}/pulls", status=401)
          with pytest.raises(AuthenticationError):
              github_adapter.list_pull_requests()

      def test_422_raises_http_error_on_create_label(self, mock_responses, github_adapter):
          mock_responses.add(responses.POST, f"{REPOS}/labels", status=422,
                             json={"message": "Validation Failed"})
          with pytest.raises(HttpError) as exc_info:
              github_adapter.create_label(name="duplicate-label")
          assert exc_info.value.status_code == 422
  ```
- **検出回数**: 3/3

---

### [R5-10] 🟡 中 コマンドレイヤーで `resolve_project_config` 失敗時のエラーハンドリングが未テスト

- **ファイル**: `tests/test_commands/test_pr.py`, `test_issue.py`, `test_repo.py`, `test_label.py`, `test_milestone.py`, `test_release.py`
- **説明**: 全コマンドテストでは `resolve_project_config` と `create_adapter` をモックしており、実際のエラーシナリオ（サービス未設定時の `ConfigError`、認証失敗時の `AuthenticationError`）が `main()` まで正しく伝播するかをテストしていない。`cli.py` の `main()` が `GfoError` を捕捉することは `test_cli.py` でテスト済みだが、コマンド → cli の統合シナリオがない。
- **影響**: ユーザーが gfo 未設定のディレクトリでコマンドを実行した場合の動作保証がない。コマンドの前提条件エラーのユーザー体験が品質保証されていない。
- **推奨テストケース**:
  ```python
  def test_pr_list_config_error(capsys):
      with patch("gfo.commands.pr.resolve_project_config",
                 side_effect=ConfigError("not configured")):
          from gfo.cli import main
          result = main(["pr", "list"])
      assert result == 1
      assert "not configured" in capsys.readouterr().err
  ```
- **検出回数**: 2/3

---

### [R5-11] 🟡 中 `init.py` の対話モードで `get_remote_url()` 取得失敗時のフォールバックが未テスト

- **ファイル**: `src/gfo/commands/init.py` L95-105 / `tests/test_commands/test_init.py`
- **説明**: `_handle_interactive()` の手動入力パスでは `get_remote_url()` が例外を投げた場合に `owner = ""`, `repo = ""`, `organization = None` にフォールバックするコード（L102-105）がある。このパスは既存テストでカバーされていない。すべての既存テストは `get_remote_url` が成功する前提でモックしている（または `detect_service` が成功して `get_remote_url` を呼ばないパス）。
- **影響**: git リポジトリ外での `gfo init` 実行時に owner/repo が空のまま保存されるバグを見逃す可能性がある。
- **推奨テストケース**:
  ```python
  def test_detect_failure_manual_no_remote_url():
      """手動入力時に get_remote_url が失敗 → owner/repo は空文字。"""
      args = make_args(non_interactive=False)
      inputs = iter(["github", "github.com", "https://api.github.com", ""])
      with patch("gfo.commands.init.detect_service", side_effect=DetectionError()), \
           patch("gfo.commands.init.get_remote_url",
                 side_effect=Exception("not a git repo")), \
           patch("gfo.commands.init.save_project_config") as mock_save, \
           patch("builtins.input", side_effect=inputs):
          init_cmd.handle(args, fmt="table")
      saved = mock_save.call_args[0][0]
      assert saved.owner == ""
      assert saved.repo == ""
  ```
- **検出回数**: 3/3

---

### [R5-12] 🟡 中 `repo.py` の `handle_clone()` で Azure DevOps / Forgejo / Gogs の URL 構築が未テスト

- **ファイル**: `src/gfo/commands/repo.py` L104-120 / `tests/test_commands/test_repo.py`
- **説明**: `handle_clone` のテストは github / gitlab / bitbucket / gitbucket / backlog / gitea をカバーしているが、`azure-devops`（L110-112）、`forgejo`/`gogs`（L113）、`else` ブランチ（L119-120）の URL 構築パスが未テスト。Azure DevOps の clone URL は他のサービスとは異なる `dev.azure.com/{owner}/{owner}/_git/{name}` 形式（owner をプロジェクトとして二重使用する特殊な構造）を使用している。
- **影響**: Azure DevOps / Forgejo / Gogs のクローン URL が誤っていてもテストで検知されない。
- **推奨テストケース**:
  ```python
  def test_azure_devops_url(self):
      args = make_args(host="dev.azure.com", repo="myorg/myrepo")
      with patch("gfo.commands.repo._resolve_host_without_repo",
                 return_value=("dev.azure.com", "azure-devops")), \
           patch("gfo.commands.repo.git_clone") as mock_clone:
          repo_cmd.handle_clone(args, fmt="table")
      mock_clone.assert_called_once_with(
          "https://dev.azure.com/myorg/myorg/_git/myrepo"
      )

  def test_forgejo_url(self):
      args = make_args(host="codeberg.org", repo="owner/myrepo")
      with patch("gfo.commands.repo._resolve_host_without_repo",
                 return_value=("codeberg.org", "forgejo")), \
           patch("gfo.commands.repo.git_clone") as mock_clone:
          repo_cmd.handle_clone(args, fmt="table")
      mock_clone.assert_called_once_with("https://codeberg.org/owner/myrepo.git")
  ```
- **検出回数**: 3/3

---

### [R5-13] 🟡 中 `pr.py` の `handle_checkout()` でエラーケース（PR 非存在・fetch 失敗）が未テスト

- **ファイル**: `src/gfo/commands/pr.py` L60-67 / `tests/test_commands/test_pr.py`
- **説明**: `TestHandleCheckout` には正常系（fetch + checkout が成功する）のみを確認する `test_fetches_and_checks_out` が存在する。PR番号が存在しない場合の `NotFoundError` 伝搬、`git_fetch` が失敗した場合（`subprocess.CalledProcessError` 等）の動作テストが欠如している。
- **影響**: git 操作失敗時に適切なエラーメッセージが表示されるかが保証されない。checkout 操作のエラーパスが未検証。
- **推奨テストケース**:
  ```python
  def test_checkout_pr_not_found_raises(self, sample_config, mock_adapter):
      mock_adapter.get_pull_request.side_effect = NotFoundError("/pulls/999")
      args = make_args(number=999)
      with _patch_all(sample_config, mock_adapter):
          with pytest.raises(NotFoundError):
              pr_cmd.handle_checkout(args, fmt="table")
  ```
- **検出回数**: 2/3

---

### [R5-14] 🟡 中 `paginate_link_header` の 2 ページ目での NetworkError テストが欠如

- **ファイル**: `src/gfo/http.py` L163-171（2ページ目フェッチ時の例外処理）
- **説明**: `paginate_link_header` は2ページ目以降を `client._session.get(next_url, ...)` で直接フェッチするが、このコードパスの `ConnectionError` と `Timeout` 例外処理（L166-171）はテストされていない。`TestPaginateLinkHeader` には正常系の multi_page テストはあるが、2ページ目でネットワーク障害が起きた場合のテストがない。同様に `paginate_response_body` の L244-248 も同様に未テスト。
- **影響**: ページネーション中の障害が `NetworkError` として正しく変換されることが保証されず、未処理例外が発生する可能性がある。
- **推奨テストケース**:
  ```python
  @responses.activate
  def test_paginate_link_header_second_page_connection_error(monkeypatch):
      import json as json_mod, requests as req_lib
      next_url = f"{BASE}/items?page=2"

      def callback(request):
          headers = {"Link": f'<{next_url}>; rel="next"'}
          return (200, headers, json_mod.dumps([{"id": 1}]))

      responses.add_callback(responses.GET, f"{BASE}/items", callback=callback)
      responses.add(responses.GET, next_url, body=req_lib.ConnectionError("refused"))
      c = HttpClient(BASE)
      with pytest.raises(NetworkError):
          paginate_link_header(c, "/items", limit=10)
  ```
- **検出回数**: 2/3

---

### [R5-15] 🟡 中 `paginate_link_header` の `per_page_key` カスタムパラメータが未テスト

- **ファイル**: `src/gfo/http.py` L151（`per_page_key` パラメータ）
- **説明**: `paginate_link_header` の `per_page_key` 引数はデフォルト `"per_page"` だが、Gitea/Forgejo 系アダプターは `per_page_key="limit"` を使う。テストではデフォルト値のみ検証されており、カスタム値を渡した場合（例: `per_page_key="limit"`）に正しくパラメータが設定されるかのテストがない。
- **影響**: Gitea/Forgejo 系アダプターの実際のページネーション動作がアダプターレベルでは検証されているが、`paginate_link_header` 単体での `per_page_key` の動作保証がない。
- **推奨テストケース**:
  ```python
  @responses.activate
  def test_paginate_link_header_custom_per_page_key():
      responses.add(responses.GET, f"{BASE}/items", json=[{"id": 1}])
      c = HttpClient(BASE)
      paginate_link_header(c, "/items", per_page_key="limit", per_page=20, limit=10)
      assert "limit=20" in responses.calls[0].request.url
      assert "per_page=" not in responses.calls[0].request.url
  ```
- **検出回数**: 1/3

---

### [R5-16] 🟡 中 `output.py` で未知の `fmt` 値のときのテーブルフォールバック動作が未テスト

- **ファイル**: `src/gfo/output.py` L23-28（`fmt` の分岐）
- **説明**: `fmt` が `"json"` でも `"plain"` でもない場合（例: `"csv"` や空文字列）は `format_table` にフォールバックする（L27 `else`）。この動作の明示的なテストがない。
- **影響**: 将来 `fmt` バリデーションを追加した際の変更で暗黙のフォールバックが破壊されても検知できない。
- **推奨テストケース**:
  ```python
  def test_unknown_fmt_falls_back_to_table(self, capsys):
      output(SampleItem(1, "Fix typo", "open", "alice"), fmt="csv")
      captured = capsys.readouterr()
      assert "NUMBER" in captured.out  # テーブルフォーマットにフォールバック
  ```
- **検出回数**: 1/3

---

### [R5-17] 🟡 中 `resolve_project_config()` の `ConfigError` 発生パス（解決不能時）が未テスト

- **ファイル**: `src/gfo/config.py` L129-132（`if not stype:` と `if not shost:`）
- **説明**: `test_config.py` の `resolve_project_config` テストには、`detect_service` が `service_type=""` や `host=""` を返した場合に `ConfigError` が投げられることを確認するテストがない。
- **影響**: サービス種別やホストが解決できない場合のエラーメッセージの正確性が未検証。
- **推奨テストケース**:
  ```python
  def test_resolve_raises_when_service_type_unresolvable():
      from gfo.detect import DetectResult
      detect_result = DetectResult(service_type="", host="", owner="u", repo="r")
      git_cfg = {k: None for k in ["gfo.type", "gfo.host", "gfo.api-url",
                                    "gfo.organization", "gfo.project-key"]}
      with (
          patch("gfo.git_util.git_config_get", side_effect=_mock_git_config(git_cfg)),
          patch("gfo.detect.detect_service", return_value=detect_result),
      ):
          with pytest.raises(ConfigError, match="service type"):
              resolve_project_config()
  ```
- **検出回数**: 1/3

---

### [R5-18] 🟢 軽微 `http.py` の `paginate_link_header` で 3 ページ以上の連鎖シナリオが未テスト

- **ファイル**: `src/gfo/http.py` L160-187 / `tests/test_http.py` L276-293
- **説明**: `test_multi_page` は 2 ページ（ページ 1 → ページ 2）のみをテストしている。3 ページ以上の連鎖（ページ 1 → ページ 2 → ページ 3）のシナリオが未テスト。`paginate_page_param`、`paginate_response_body`、`paginate_offset`、`paginate_top_skip` も同様に 2 ページ止まりのテストとなっている。
- **影響**: 3 ページ以上のページネーションで無限ループや誤った中断が起きても検知できない。
- **推奨テストケース**: 3 ページのコールバックチェーンを構築し `len(result) == page1_count + page2_count + page3_count` を確認する。
- **検出回数**: 1/3

---

### [R5-19] 🟢 軽微 `Bitbucket` アダプターの `create_pull_request` で `description` フィールドおよび `draft` フラグが未テスト

- **ファイル**: `src/gfo/adapter/bitbucket.py` / `tests/test_adapters/test_bitbucket.py` L172-184
- **説明**: `TestCreatePullRequest.test_create` はリクエストボディの検証が不十分（`source_branch` と `destination_branch` のみ）。`description` フィールドの検証がない。また GitHub / GitLab / Gitea / Forgejo / GitBucket / Azure DevOps の `create_pull_request` には `draft=True` のテストケースが存在するが、Bitbucket アダプターには draft テストがない。Bitbucket Cloud は draft PR をサポートしていないため `NotSupportedError` になるべきかどうかの確認もない。
- **影響**: PR 作成リクエストボディの正確性が保証されておらず、Bitbucket での draft フラグの扱いが不明確なまま。
- **推奨テストケース**:
  ```python
  def test_create_with_description(self, mock_responses, bitbucket_adapter):
      mock_responses.add(responses.POST, f"{REPOS}/pullrequests",
                         json=_pr_data(), status=201)
      bitbucket_adapter.create_pull_request(
          title="PR", body="Description text", base="main", head="feature",
      )
      req_body = json.loads(mock_responses.calls[0].request.body)
      assert req_body["description"] == "Description text"
  ```
- **検出回数**: 2/3

---

### [R5-20] 🟢 軽微 `config.py` の `get_default_output_format()` で `"plain"` 値が未テスト

- **ファイル**: `src/gfo/config.py` L62-65 / `tests/test_config.py` L92-102
- **説明**: `test_get_default_output_format_configured` は `"json"` のみテストしている。`get_default_output_format()` が `"plain"` を返すケースの動作確認が存在しない。また `cli.py` L175 で `--format` を指定しないときに `get_default_output_format()` が `"plain"` を返す場合の連携テストも欠如している。
- **影響**: `config.toml` に `output = "plain"` を設定した場合の動作が保証されない。
- **推奨テストケース**:
  ```python
  def test_get_default_output_format_plain():
      with patch("gfo.config.load_user_config",
                 return_value={"defaults": {"output": "plain"}}):
          assert get_default_output_format() == "plain"

  def test_main_default_format_from_config_plain():
      mock_handler = MagicMock()
      with patch.dict(_DISPATCH, {("pr", "list"): mock_handler}), \
           patch("gfo.cli.get_default_output_format", return_value="plain"):
          result = main(["pr", "list"])
      assert result == 0
      _, kwargs = mock_handler.call_args
      assert kwargs["fmt"] == "plain"
  ```
- **検出回数**: 2/3

---

### [R5-21] 🟢 軽微 `cli.py` で `--format plain` の CLI レベルテストが欠如

- **ファイル**: `src/gfo/cli.py` L175 / `tests/test_cli.py`
- **説明**: `test_cli.py` の `test_main_format_override` は `--format json` のみテストしている。`--format plain` を明示指定した場合に `fmt` に正しく伝搬することを確認するテストがない。
- **影響**: `--format plain` パスが CLI レベルで実際に機能することの保証がない。
- **推奨テストケース**:
  ```python
  def test_main_format_plain_override():
      mock_handler = MagicMock()
      with patch.dict(_DISPATCH, {("pr", "list"): mock_handler}):
          result = main(["--format", "plain", "pr", "list"])
      assert result == 0
      _, kwargs = mock_handler.call_args
      assert kwargs["fmt"] == "plain"
  ```
- **検出回数**: 1/3

---

### [R5-22] 🟢 軽微 `pr.py` の `handle_checkout()` で git 操作失敗時のエラーが未テスト

- **ファイル**: `src/gfo/commands/pr.py` L60-67 / `tests/test_commands/test_pr.py` L167-178
- **説明**: `TestHandleCheckout` は正常系（fetch + checkout が成功する）のみをテストしている。`git_fetch` または `git_checkout_new_branch` が `subprocess.CalledProcessError` 等の例外を投げるエラー系が未テスト。（R5-13 と補完的な関係にある軽微なサブケース）
- **影響**: git 操作失敗時に適切なエラーメッセージが表示されるかが保証されない。
- **推奨テストケース**: `gfo.git_util.git_fetch` を `subprocess.CalledProcessError` を投げるようにモックし、例外が伝播することを確認する。
- **検出回数**: 2/3

---

## サマリーテーブル

| ID | 重大度 | 対象ソース | 欠如テスト | 説明 | 検出回数 |
|----|--------|-----------|-----------|------|----------|
| R5-01 | 🔴 重大 | `__main__.py` | `tests/test_main.py`（なし） | `python -m gfo` エントリポイントのテストが皆無 | 3/3 |
| R5-02 | 🔴 重大 | `http.py` L82-96 | 429 リトライ後の ConnectionError / Timeout | リトライ後の二次的ネットワーク障害パスが未テスト | 2/3 |
| R5-03 | 🔴 重大 | `config.py` L108-158 | `resolve_project_config` 設定解決優先度 | stype/shost 片側のみ・detect_service 非呼び出し確認・git config 上書きテスト不足 | 3/3 |
| R5-04 | 🔴 重大 | 全コマンド | `fmt="plain"` テストケース | コマンドレイヤーで `--format plain` の出力検証が全コマンドで欠如 | 3/3 |
| R5-05 | 🔴 重大 | `commands/issue.py` L31 | `"azure-devops"` ハイフン vs アンダースコア | 実際のサービスタイプ値でのテストが欠如（潜在的バグ） | 1/3 |
| R5-06 | 🟡 中 | `output.py` L40-53 | `format_table` カラム幅エッジケース | ヘッダー幅基準・空値・末尾空白の境界ケース未テスト | 3/3 |
| R5-07 | 🟡 中 | `config.py` L193-198 | Azure DevOps project のみ欠如 | organization あり・project なしの ConfigError 未テスト | 1/3 |
| R5-08 | 🟡 中 | `adapter/gogs.py` | GogsAdapter Issue/リポジトリ継承操作 | `create_issue`, `close_issue`, `get_issue` 等が Gogs コンテキストで未テスト | 3/3 |
| R5-09 | 🟡 中 | 複数アダプター | HTTP エラー（404/401/422）ハンドリング | GitHub/GitLab/Gitea/Bitbucket/Backlog/AzureDevOps でエラーハンドリングテストなし | 3/3 |
| R5-10 | 🟡 中 | 全コマンド | `resolve_project_config` 失敗時エラー伝播 | サービス未設定・認証失敗の ConfigError/AuthenticationError 未テスト | 2/3 |
| R5-11 | 🟡 中 | `commands/init.py` L95-105 | 対話モードの remote URL 取得失敗フォールバック | `get_remote_url` 例外時の owner/repo 空状態保存が未テスト | 3/3 |
| R5-12 | 🟡 中 | `commands/repo.py` L104-120 | Azure DevOps / Forgejo / Gogs clone URL | 3 サービスの URL 構築テストが欠如 | 3/3 |
| R5-13 | 🟡 中 | `commands/pr.py` L60-67 | checkout エラーケース（PR 非存在・fetch 失敗） | PR 非存在・git_fetch 失敗時のエラー伝搬テストなし | 2/3 |
| R5-14 | 🟡 中 | `http.py` L163-171 | ページネーション2ページ目の NetworkError | ページネーション途中のネットワーク断絶が NetworkError に変換されること未テスト | 2/3 |
| R5-15 | 🟡 中 | `http.py` L151 | `paginate_link_header` の `per_page_key` カスタム値 | `per_page_key="limit"` 指定時の動作が未テスト | 1/3 |
| R5-16 | 🟡 中 | `output.py` L27 | 未知 `fmt` のテーブルフォールバック | `else` ブランチの明示的テストなし | 1/3 |
| R5-17 | 🟡 中 | `config.py` L129-132 | `ConfigError` 発生パス（解決不能） | `service_type`/`host` が空の場合の例外テスト不足 | 1/3 |
| R5-18 | 🟢 軽微 | `http.py` L160-187 | ページネーション 3 ページ以上の連鎖 | 全 paginate 関数で 3 ページ以上の連鎖が未テスト | 1/3 |
| R5-19 | 🟢 軽微 | `adapter/bitbucket.py` | Bitbucket PR create の `description`・`draft` フィールド | リクエストボディの完全性検証が不足・draft フラグの挙動が未検証 | 2/3 |
| R5-20 | 🟢 軽微 | `config.py` L62-65 + `cli.py` L175 | `get_default_output_format` の `"plain"` 値と CLI 連携 | "plain" 設定値が動作することと CLI との連携テストなし | 2/3 |
| R5-21 | 🟢 軽微 | `cli.py` L175 | `--format plain` の CLI レベルテスト | `--format plain` が `fmt` に正しく伝搬することの確認不足 | 1/3 |
| R5-22 | 🟢 軽微 | `commands/pr.py` L66-67 | `handle_checkout` での git 操作失敗 | `git_fetch` / `git_checkout_new_branch` の例外伝播が未テスト | 2/3 |

---

## 推奨アクション (優先度順)

1. **[最優先] R5-05 `issue.py` の `"azure_devops"` vs `"azure-devops"` バグ調査**: L31 のサービスタイプ比較のアンダースコア表記がハイフン表記の誤りである可能性が高い。まずソースコードのバグの有無を確認し、バグであれば修正後にテストを追加する。

2. **[高] R5-01 `tests/test_main.py` を新規作成**: `python -m gfo` のエントリポイントを subprocess で検証する2〜3テストを追加する。工数が小さく、最も根本的なカバレッジの穴を塞げる。

3. **[高] R5-04 全コマンドテストに `fmt="plain"` テストケースを追加**: `test_pr.py`, `test_issue.py`, `test_repo.py`, `test_release.py`, `test_label.py`, `test_milestone.py` に各1件追加する。タブ区切りかつヘッダーなしの検証を行う。

4. **[高] R5-03 `resolve_project_config` の設定解決優先度テスト補強**: `test_config.py` に `detect_service` の非呼び出し確認、stype/shost 片側設定時のフォールバック、`gfo.organization` 上書きのテストを追加する。

5. **[高] R5-02 429 リトライ時の二次的ネットワーク障害テスト**: `http.py` の既存の `TestRateLimit` クラスに `ConnectionError`/`Timeout` を注入するテストを追加する。実装が比較的シンプルなため工数が低い。

6. **[中] R5-09 全アダプターへの HTTP エラーハンドリングテスト追加**: Forgejo/GitBucket に存在するパターンを GitHub・GitLab・Gitea・Bitbucket・Backlog・AzureDevOps の各アダプターへ横展開する。404/401/422 の例外変換テストを統一的に追加する。

7. **[中] R5-08 Gogs アダプターのテストを拡充**: `test_gogs.py` に `create_issue`, `get_issue`, `close_issue`, `list_repositories` の継承動作テストを追加する。

8. **[中] R5-12 clone コマンドの残 URL テストを追加**: `test_repo.py` の `TestHandleClone` に Azure DevOps / Forgejo / Gogs / else ブランチのテストを追加する。

9. **[中] R5-11 `init.py` の remote URL 取得失敗フォールバックテスト**: コードが存在するのにテストがない状態（デッドコードリスク）。`test_init.py` に `except Exception` ブランチのテストを追加する。

10. **[中] R5-10 コマンドレイヤーでの ConfigError テスト追加**: `test_cli.py` または各コマンドテストに `resolve_project_config` が `ConfigError` を上げた場合の CLI 挙動テストを追加する。

11. **[中] R5-14 `paginate_link_header` の2ページ目 NetworkError テスト**: `responses.add_callback` を使った2ページ目の `ConnectionError`/`Timeout` 注入テストを追加する。

12. **[低] R5-06, R5-07, R5-13, R5-15〜R5-17**: 中程度の優先度の残項目を順次対応する。特に R5-07（Azure DevOps project 欠如）と R5-13（checkout エラーケース）は工数が小さい。

13. **[低] R5-18〜R5-22**: 軽微事項として時間に余裕があれば対応する。R5-19（Bitbucket description フィールド検証）は PR の品質保証として推奨される。

---

## 次ラウンドへの申し送り

- **R5-05 の潜在的バグ優先確認**: `commands/issue.py` L31 の `"azure_devops"` がハイフン表記 `"azure-devops"` の誤りである可能性が高い。プロジェクト内の他すべての箇所がハイフン区切りを使用しているため、次ラウンドで実証・修正することを強く推奨する。

- **`paginate_link_header` の `next_url` 変数参照の確認**: `src/gfo/http.py` の `paginate_link_header` 実装において、`next_url` 変数が更新されずにループが正しく動作するかの確認が必要。2ページ目以降で同じ URL を再リクエストする潜在的バグが存在するように見える（R5-14 と関連）。実際の挙動を確認し、必要であれば修正・テスト追加を検討する。

- **統合テスト（E2E）の検討**: 現在の全テストはユニットテスト（モック多用）であり、実際の HTTP リクエストを発行する統合テストが存在しない。少なくとも `responses` ライブラリを使った「コマンド → アダプター → HTTP」の垂直スライステストを1〜2件追加することを検討する。

- **カバレッジ計測の活用**: `pytest-cov` が導入済み（R-09）なので、`pytest --cov=gfo --cov-report=term-missing` を実行してカバレッジレポートを確認し、本レポートで指摘したコードパスが実際に未カバーであることを数値で確認することを推奨する。

- **`cli.py` の `main()` の catch-all ハンドリング**: `main()` は `GfoError` と `NotSupportedError` を捕捉しているが、それ以外の予期しない例外（例: `ValueError`, `TypeError`）はそのままスタックトレースとして表示される。このユーザー体験についての方針を決め、必要であれば catch-all ハンドリングとテストの追加を検討する。
