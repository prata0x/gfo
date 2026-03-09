# gfo Review Report — Round 4: セキュリティ・認証情報管理（統合版）

## 概要
- レビュー日: 2026-03-09
- レビュー回数: 3回（重複排除済み）
- 対象ファイル:
  - `src/gfo/auth.py`
  - `src/gfo/adapter/registry.py`
  - `src/gfo/http.py`
  - `src/gfo/git_util.py`
  - `src/gfo/detect.py`
  - `src/gfo/adapter/azure_devops.py`
  - `src/gfo/config.py`
- 発見事項: 重大 2 / 中 4 / 軽微 8

---

## 発見事項

### [R4-01] 🔴 WIQL へのユーザー入力の非サニタイズ埋め込み（SQLインジェクション類似）

- **ファイル**: `src/gfo/adapter/azure_devops.py` L168–178
- **説明**: `list_issues()` メソッドで `assignee` と `label` パラメータをシングルクォートでエスケープせずに WIQL クエリ文字列に直接埋め込んでいる。
  ```python
  if assignee:
      conditions.append(f"[System.AssignedTo] = '{assignee}'")
  if label:
      conditions.append(f"[System.Tags] CONTAINS '{label}'")
  ```
  シングルクォートを含む入力（例: `O'Brien`）でクエリが破綻し、`assignee="' OR '1'='1"` のような悪意ある値で WIQL の WHERE 句の論理を変更できる。Azure DevOps の WIQL はクライアントサイドで文字列結合されてからサーバーに送信されるため、APIサーバーのパラメータバインドを経由しない。WIQL はサーバーサイドで評価されるクエリ言語であり、不正なクエリが受け入れられると意図しない Work Item 取得につながる。また、構文エラー時に内部クエリ構造がエラーメッセージに露出するリスクもある。
- **影響**: 認証済みユーザーが本来アクセスできない Work Item データを取得できる可能性がある。WIQL は SELECT 文のみ許容されるため書き込み操作は発生しないが、全プロジェクトの Work Item を漏洩させるクエリを注入できる。CLIの引数やスクリプト経由で悪用されうる。
- **推奨修正**:
  1. シングルクォートを `''`（WIQL のエスケープ表記）に置換するサニタイズ関数を実装する。
  2. より安全な対策として、Azure DevOps WIQL の `@parameter` 機構（WIQL Parametrize API）が利用可能か調査する。
  3. `assignee` は Azure DevOps のメールアドレス形式、`label` は英数字・スペース・ハイフンのみ許可するなど、正規表現で入力を制限するホワイトリストバリデーションを追加する。
- **テスト**:
  - `assignee="' OR '1'='1"` を渡したとき、生成された WIQL が想定外の条件を含まないことを検証するユニットテスト
  - `assignee="O'Brien"` 渡し時にクエリが破綻しないことを確認するテスト
  - `label="'; DROP TABLE--"` 相当のケースで適切にエスケープされることを検証するテスト
- **検出回数**: 3/3

---

### [R4-02] 🔴 Retry-After 大値によるDoS（無制限スリープ）

- **ファイル**: `src/gfo/http.py` L80–81
- **説明**: 429 レスポンスの `Retry-After` ヘッダー値を上限なしで `time.sleep()` に渡している。
  ```python
  wait = int(resp.headers.get("Retry-After", 60))
  time.sleep(wait)
  ```
  悪意あるサーバーまたは SSRF 経由の中間サーバーが `Retry-After: 2147483647` のような極端な値を返した場合、プロセスが事実上永遠にブロックされる。値の型変換前にヘッダーの整合性チェックもなく、`Retry-After` 値が非数値・負数の場合のフォールバック処理もない。
- **影響**: gfo プロセスが長時間（最大 `int` の上限まで）ハングアップする。CI/CDパイプラインや長時間実行ジョブが完全に停止する。
- **推奨修正**:
  1. `MAX_RETRY_AFTER = 300` 程度の定数を定義し、`wait = min(int(resp.headers.get("Retry-After", 60)), MAX_RETRY_AFTER)` のように上限を設ける。
  2. 上限を超えた場合は `RateLimitError` を再送出するか、警告メッセージを出力して上限値で待機する。
  3. `int()` 変換前に `ValueError` を捕捉し、非数値・負数の場合のフォールバック処理を追加する。
- **テスト**:
  - `Retry-After: 999999` を返すモックレスポンスで `time.sleep` に渡される値が上限以内であることを検証するテスト
  - `Retry-After: invalid` のレスポンスでデフォルト値が使われることを検証するテスト
- **検出回数**: 3/3

---

### [R4-03] 🟡 paginate_link_header の next_url に対するSSRF検証不足

- **ファイル**: `src/gfo/http.py` L163–171, L243–249
- **説明**: `paginate_link_header()` では Link ヘッダーから抽出した `next_url` を、`paginate_response_body()` では JSON ボディの `next` フィールドの値を、いずれも検証なしに `client._session.get(next_url, timeout=30)` へ渡している。攻撃者が制御するサーバーが `Link: <http://169.254.169.254/latest/meta-data/>; rel="next"` や `next` フィールドに内部ネットワーク URL を設定した場合、クライアントの認証情報（セッションヘッダー、Basic 認証）を付けてそのURLにリクエストが送信される（SSRF）。
- **影響**: クラウド環境（AWS/GCP/Azure）のインスタンスメタデータ漏洩（AWS IMDSv1, GCP metadata等）、内部ネットワークサービスへのプローブ、認証トークンのリーク。信頼できないサーバーが相手の場合に特に危険。
- **推奨修正**:
  1. `_validate_next_url(base_url: str, next_url: str) -> None` のような共通検証関数を実装し、`next_url` が `client._base_url` と同一オリジン（scheme + host）であることを検証する。
  2. `urllib.parse.urlparse` でスキームが `https`/`http` かつホストが `base_url` のホストと一致することを確認する。
  3. プライベートIPアドレス範囲（RFC1918）へのリダイレクトをブロックする。
  4. ホストが一致しない場合はページネーションを中断するか `NetworkError` を送出する。
- **テスト**:
  - `Link: <http://169.254.169.254/latest/meta-data>; rel="next"` を返すモックサーバーで SSRF が発生しないことを検証するテスト
  - `next_url` として `http://169.254.169.254/` を返すモックで例外が送出されることを確認するテスト
  - `next_url` がベースURLと異なるホストを指す場合に中断されることを確認するテスト
- **検出回数**: 3/3

---

### [R4-04] 🟡 git_clone の URL にトークン埋め込みされた場合のエラー漏洩

- **ファイル**: `src/gfo/git_util.py` L80–95
- **説明**: `git_clone()` は `url` を検証せず `["git", "clone", url]` にそのまま渡す。`https://oauth2:TOKEN@github.com/...` 形式の認証付き URL が渡された場合、clone 失敗時の `result.stderr` に git がその URL をそのまま出力することがあり、`GitCommandError` にトークンが平文で含まれる。また、`timeout=None` であり長時間実行が中断不可。
  ```python
  raise GitCommandError(result.stderr.strip())
  ```
  なお、`shell=False` のため直接のシェルインジェクションは防がれている点は評価できる。
- **影響**: トークンがターミナル出力・ログ・スタックトレースを通じて外部に漏洩する可能性がある。
- **推奨修正**:
  1. `GitCommandError` に渡す前に、`result.stderr` 内の `https?://[^@\s]+@` にマッチする認証情報をマスクする正規表現置換を適用する（例: `re.sub(r'://[^@]+@', '://***@', stderr)`）。
  2. `_mask_api_key()` と同様のマスク関数を `git_util.py` にも実装し、`run_git()` と `git_clone()` 両方の `stderr` に適用する。
  3. URL に認証情報を埋め込まず、代わりに `git credential` 機構や credential helper の使用を推奨する。
- **テスト**:
  - `https://user:SECRET@example.com/repo.git` の clone が失敗したとき、`GitCommandError` メッセージに `SECRET` が含まれないことを検証するテスト
  - `stderr` に認証情報入り URL が含まれる場合に `GitCommandError` メッセージからトークンが除去されることを確認するテスト
- **検出回数**: 3/3

---

### [R4-05] 🟡 probe_unknown_host での HTTP フォールバックによる MITM リスク

- **ファイル**: `src/gfo/detect.py` L187–223, L261–264
- **説明**: `detect_service()` では `scheme` を次のロジックで決定している。
  ```python
  scheme = "https" if remote_url.startswith("https") else "http"
  probed = probe_unknown_host(result.host, scheme=scheme)
  ```
  SSH リモート URL（`git@github.com:...`）の場合、`startswith("https")` が偽となり `scheme="http"` で `probe_unknown_host()` が呼ばれる。`probe_unknown_host()` 自体はトークンを送信しないが、HTTP プローブのため TLS 保護がなく、MITM 攻撃によりプローブレスポンスが改ざんされ誤ったサービス種別が検出される可能性がある。誤ったサービス種別が返された場合、後続の API リクエストが誤ったエンドポイントに送信されるリスクがある。また、`probe_unknown_host()` 内の `except Exception: pass` はネットワークエラーを完全に隠蔽する点も問題を悪化させる。
- **影響**: SSH リモートを使用するリポジトリでプローブが HTTP で行われ、内部ネットワーク上での傍受が可能。MITM 攻撃によりサービス種別を偽装されると、後続の API リクエストが誤ったエンドポイントに送信されるリスクがある。なお、プローブ自体はトークンを送信しないため、直接的な認証情報漏洩はない。
- **推奨修正**:
  1. `probe_unknown_host()` では常に HTTPS を優先し、失敗時のみ HTTP にフォールバックする設計とする。
  2. SSH remote URL の場合は `scheme="https"` をデフォルトとする（ホストは SSH も HTTPS も同一ドメインが多いため）。
  3. `probe_unknown_host()` の `scheme` パラメータを廃止するか、`"https"` のみ許可するバリデーションを加える。
  4. HTTP プローブ結果は HTTPS と比較して信頼性低として扱う。
- **テスト**:
  - SSH URL から検出した場合、`probe_unknown_host` が HTTPS で呼ばれることを検証するテスト
  - SSH リモートURL（`git@host:owner/repo.git`）でも `probe_unknown_host` が HTTPS でプローブすることを確認するテスト
- **検出回数**: 3/3

---

### [R4-06] 🟡 Windows 環境での credentials.toml パーミッション設定が不完全

- **ファイル**: `src/gfo/auth.py` L69–85
- **説明**: Windows 環境での `credentials.toml` パーミッション設定に複数の問題がある。
  1. `check=False` で `icacls` の結果を検証していないため、失敗してもサイレントに無視される。
  2. `os.getlogin()` は一部の Windows 環境（サービスアカウント、WSL経由、sudo、コンテナ等）で `OSError` を送出するが、`except OSError: pass` で握りつぶしている。
  3. `icacls /grant:r USER:R` は読み取り権限のみ付与するが、書き込み権限（`W`、`M`、`F`）を明示的に剥奪していない（`/inheritance:r` で継承は除去されるが、既存の書き込み ACE は残る場合がある）。
  4. `os.getlogin()` は現在のプロセスオーナーと一致しない場合がある。`os.environ.get("USERNAME")` または `getpass.getuser()` の方が信頼性が高い。
  結果として、権限設定が意図通りに行われていないにもかかわらず、警告なくトークンが書き込まれる。
- **影響**: 他のローカルユーザーが `credentials.toml` を読み取れる可能性がある。Windows 環境でトークン漏洩が発生しうる。
- **推奨修正**:
  1. `icacls` の `returncode` を確認してエラーをログ出力・警告として通知する（`check=True` または明示的な `returncode` 確認）。
  2. `os.getlogin()` を `getpass.getuser()` に置換し、フォールバックを強化する。
  3. `icacls /reset` でACLをリセットした後、現在ユーザーのみに必要な権限を付与するフローを検討する。
  4. 管理者グループの書き込み権限も明示的に除去するオプションを検討する。
- **テスト**:
  - `icacls` 失敗時に警告が出力されることを検証するテスト
  - `os.getlogin()` が `OSError` を送出する環境でも `save_token()` が例外なく完了することを確認するテスト
- **検出回数**: 3/3

---

### [R4-07] 🟢 NetworkError のエラーメッセージに接続先URLが含まれる可能性

- **ファイル**: `src/gfo/http.py` L72–75, L92–95, L166–169, L244–247
- **説明**: `requests.ConnectionError` や `requests.Timeout` の `str(e)` をそのまま `NetworkError` に渡している。`requests` の `ConnectionError` メッセージには接続先URL（`https://api-server/endpoint?apiKey=...`）が含まれる場合がある。`_mask_api_key` は `_handle_response` 内でのみ適用されており、接続エラー時には呼ばれない。また、`_mask_api_key()` は `apiKey=xxx` のパターンのみをマスクしており、将来的に他の `auth_params`（例: `access_token=xxx`）が追加された場合、マスク漏れが発生する。
- **影響**: 接続エラー時のログ・スタックトレースに APIキーが含まれる可能性がある（主に Backlog の `apiKey` パラメータ）。拡張性の観点で将来リスクがある。
- **推奨修正**:
  1. `NetworkError` 生成前にも `HttpClient._mask_api_key(str(e))` を適用するか、接続エラーのメッセージを固定文字列（接続先ホスト名のみ含む形式）に統一する。
  2. `_mask_api_key()` を汎用的な `_mask_sensitive_params(url: str, sensitive_keys: list[str])` に拡張し、`_auth_params` のキー一覧を `HttpClient` が保持してマスク対象として渡す設計とする。
- **テスト**:
  - `apiKey` を含む URL への接続失敗時、`NetworkError` メッセージに `apiKey=` の値が含まれないことを検証するテスト
  - `auth_params={"access_token": "secret"}` のとき、エラーURL に `access_token=secret` が含まれないことを検証するテスト
- **検出回数**: 2/3

---

### [R4-08] 🟢 detect.py における DetectionError メッセージへの URL 埋め込み

- **ファイル**: `src/gfo/detect.py` L88, L133, L158, L170, L181
- **説明**: `_parse_url()` や各パスパーサーで失敗した場合、`remote_url` や `path` をそのままエラーメッセージに埋め込む。
  ```python
  raise DetectionError(f"Cannot parse URL: {remote_url}")
  ```
  `remote_url` が `https://oauth2:TOKEN@host/path.git` 形式の認証情報埋め込みURLの場合、`DetectionError` メッセージにトークンが平文で含まれる。
- **影響**: ログ・UI 表示経由でのトークン漏洩（軽微: 認証情報埋め込みURLは稀なユースケース）。
- **推奨修正**: エラーメッセージ生成前に URL をサニタイズする（`re.sub(r'://[^@]+@', '://***@', url)` 等）。
- **テスト**: 認証情報埋め込みURLで `_parse_url` が失敗した場合、例外メッセージにパスワード相当部分が含まれないことを検証するテスト。
- **検出回数**: 1/3

---

### [R4-09] 🟢 TLS 検証の明示的設定なし（デフォルト依存）

- **ファイル**: `src/gfo/http.py` L35, `src/gfo/detect.py` L195, L209, L217
- **説明**: `requests.Session()` および `requests.get()` の `verify` パラメータを明示的に指定していない。デフォルトは `True`（TLS検証有効）であるため現状は安全だが、コードの意図が不明確。また、自己署名証明書を使用するセルフホスト環境（Gitea/GitLab等）でユーザーが環境変数 `REQUESTS_CA_BUNDLE` や `CURL_CA_BUNDLE` を意図せず設定してしまった場合の挙動が文書化されていない。将来の変更で `verify=False` が導入されるリスクを防ぐため明示化が望ましい。
- **影響**: 現状は問題なし。ただし将来の変更でTLS検証が無効化されるリスクがある。
- **推奨修正**: `HttpClient.__init__` に `verify: bool | str = True` パラメータを追加し、セルフホスト環境向けに CA バンドルパスを設定可能にしながら、デフォルトでは TLS 検証を強制することを明示する。
- **テスト**: `verify=False` のような設定が `HttpClient` で有効化されないことを確認するテスト（設定値の境界テスト）。
- **検出回数**: 1/3

---

### [R4-10] 🟢 probe_unknown_host で例外を全握りつぶし（SSL エラー含む）

- **ファイル**: `src/gfo/detect.py` L194–222
- **説明**: 各プローブで `except Exception: pass` と全例外をサイレントに無視している。
  ```python
  except Exception:
      pass
  ```
  SSL 証明書エラー（`ssl.SSLError`）、認証エラー、タイムアウト以外の予期しない例外が発生しても検出できない。TLS エラーをサイレントに無視することで、TLS が正しく検証されているかどうかの確認が困難になる。
- **影響**: TLS 検証エラーが無視されることで、MITM 攻撃を受けているときでも gfo が正常に動作しているように見える。
- **推奨修正**:
  1. `requests.exceptions.SSLError` を明示的に捕捉してログ出力（または警告）する。
  2. `except Exception` を `except (requests.ConnectionError, requests.Timeout, requests.RequestException)` に絞り込む。
- **テスト**: SSL エラー時にサイレント無視ではなく適切な警告が発生することを検証するテスト。
- **検出回数**: 1/3

---

### [R4-11] 🟢 paginate_link_header の next_url 変数スコープバグ（DoS 的挙動の副作用）

- **ファイル**: `src/gfo/http.py` L181–187
- **説明**: `paginate_link_header()` のループ内で `next_url` の更新が正しく行われていない可能性がある。
  ```python
  url = match.group(1)  # ← next_url に代入していない
  ```
  `url` ローカル変数に代入しているが、ループの次回イテレーションで参照される `next_url` は更新されていない。これにより実質的にページネーションが最初のページで終了する（機能バグ）と同時に、`next_url is None` のブランチが常に使われ続け、同一 URL に無限リクエストが送られる可能性がある（DoS 的挙動）。また、SSRF チェックが意図通りに機能しない。
- **影響**: ループが break せずに同一パスへの無限リクエストが発生するとサーバー側のレート制限を引き起こす可能性がある。GitHub / Gitea / GitBucket アダプターで 2 ページ目以降が取得できていない可能性がある。
- **推奨修正**: `url = match.group(1)` を `next_url = match.group(1)` に修正する（1行修正で機能バグ＋セキュリティリスクを両方解消）。
- **テスト**: 2ページ以上の Link ヘッダーを持つレスポンスで、`next_url` が正しく更新されることを検証するテスト。
- **検出回数**: 1/3

---

### [R4-12] 🟢 `_write_credentials_toml` での手動 TOML エスケープの不完全性

- **ファイル**: `src/gfo/auth.py` L129–140
- **説明**: `_write_credentials_toml()` は TOML ライブラリを使わず手動文字列フォーマットでファイルを書き出している。エスケープ対象は `\`、`"`、`\n`、`\t` のみであり、制御文字（`\r`、`\x00`〜`\x1f`など）はエスケープされない。TOML 仕様では基本文字列内の制御文字は禁止されており、これらを含むトークンが書き込まれると `tomllib` での読み込みが失敗する可能性がある。標準の `tomllib` を使って読み込みながら書き出しに非標準の手動実装を使っている非対称性がある。
- **影響**: 特殊文字を含むトークンを保存した後、`load_tokens()` でパースエラーが発生し、認証が機能しなくなる可能性がある。
- **推奨修正**: `tomli-w` 等の TOML ライブラリを使って書き出す、または既存の手動エスケープに TOML 仕様準拠の全制御文字エスケープを追加する。
- **テスト**: `\r`、`\x00`、`\x1f` を含むトークンを保存し、再度 `load_tokens()` で正しく読み出せることを確認するテスト。
- **検出回数**: 1/3

---

### [R4-13] 🟢 paginate 関数でのプライベートメンバー `_session` への直接アクセス

- **ファイル**: `src/gfo/http.py` L165, L243
- **説明**: `paginate_link_header()` と `paginate_response_body()` が `client._session.get(next_url)` でプライベートメンバーに直接アクセスしている。これにより `HttpClient.request()` が提供する認証ヘッダー注入・エラーハンドリング（`_handle_response`）を部分的にバイパスしている。また、`auth_params`（Backlog の `apiKey`）はセッションではなく `merged_params` で毎回注入されるため、`_session.get()` では `auth_params` が URL に付与されず、Backlog で Link ヘッダーページネーションが壊れる可能性がある。
- **影響**: 設計上の保護層が弱まり、将来のコード変更でセキュリティ上の漏れが生じやすくなる。
- **推奨修正**: `HttpClient` に `get_absolute(url: str)` のような絶対 URL を受け取る内部メソッドを追加し、`_session` への直接アクセスを排除する。
- **テスト**: `paginate_link_header` / `paginate_response_body` がページネーション時に認証情報を正しく送信することを確認する結合テスト。
- **検出回数**: 1/3

---

### [R4-14] 🟢 API URL の git config 保存による情報開示リスク

- **ファイル**: `src/gfo/config.py` L162–172
- **説明**: `save_project_config()` が `gfo.api-url` を `git config --local` に保存している。`.git/config` はリポジトリ内のすべての git ユーザーが読み取れるため、内部オンプレミスサーバーの API URL が他の開発者に開示される可能性がある。また、`.git/config` はバージョン管理外であるものの、ツールによって誤ってコミットされるリスクがある。
- **影響**: 内部ネットワークのトポロジー（サーバー名、ポート、パス構造）の漏洩。セキュリティ上の問題としては軽微だが、ペネトレーションテストにおける情報収集に利用されうる。
- **推奨修正**:
  - `api_url` を `git config --local` ではなく `config.toml`（ユーザー設定）に保存する選択肢を検討する。
  - ドキュメントにて「`.git/config` に API URL が保存される」旨を明記する。
- **テスト**: `save_project_config()` が内部 API URL を保存した場合の挙動を確認するテスト。
- **検出回数**: 1/3

---

## サマリーテーブル

| ID | 重大度 | ファイル | 行 | 説明 | 検出回数 |
|----|--------|---------|------|------|----------|
| R4-01 | 🔴 重大 | `adapter/azure_devops.py` | L173–176 | WIQL へのユーザー入力の非サニタイズ埋め込み | 3/3 |
| R4-02 | 🔴 重大 | `http.py` | L80–81 | Retry-After 大値による無制限スリープ（DoS） | 3/3 |
| R4-03 | 🟡 中 | `http.py` | L163–171, L243–249 | paginate の next_url に対する SSRF 検証不足 | 3/3 |
| R4-04 | 🟡 中 | `git_util.py` | L80–95 | git_clone のエラーメッセージへのトークン漏洩リスク | 3/3 |
| R4-05 | 🟡 中 | `detect.py` | L187–223, L261–264 | SSH URL 時の HTTP プローブによる MITM・後続リクエスト誤送信リスク | 3/3 |
| R4-06 | 🟡 中 | `auth.py` | L68–85 | Windows での credentials.toml パーミッション設定が不完全 | 3/3 |
| R4-07 | 🟢 軽微 | `http.py` | L72–75 他 | NetworkError メッセージへの apiKey 漏洩可能性 | 2/3 |
| R4-08 | 🟢 軽微 | `detect.py` | L88 他 | DetectionError メッセージへの認証情報埋め込み URL 露出 | 1/3 |
| R4-09 | 🟢 軽微 | `http.py` L35, `detect.py` | L195, L209, L217 | TLS 検証の明示的設定なし | 1/3 |
| R4-10 | 🟢 軽微 | `detect.py` | L194–222 | probe_unknown_host で SSL エラーを全握りつぶし | 1/3 |
| R4-11 | 🟢 軽微 | `http.py` | L181–187 | next_url 未更新バグ（DoS 的挙動の副作用） | 1/3 |
| R4-12 | 🟢 軽微 | `auth.py` | L129–140 | 手動 TOML エスケープの不完全性（制御文字未対応） | 1/3 |
| R4-13 | 🟢 軽微 | `http.py` | L165, L243 | プライベートメンバー `_session` への直接アクセス | 1/3 |
| R4-14 | 🟢 軽微 | `config.py` | L162–172 | API URL の git config 保存による情報開示リスク | 1/3 |

---

## 推奨アクション (優先度順)

1. **[R4-01] WIQL インジェクション対策**: `assignee`・`label` のシングルクォートエスケープ（`'` → `''`）実装。Azure DevOps の WIQL はサーバーサイド評価のため、最優先で対処する。Azure DevOps の WIQL パラメータバインディングの利用可否も調査する。
2. **[R4-02] Retry-After 上限設定**: `MAX_RETRY_AFTER = 300` 定数を定義し `min(wait, MAX_RETRY_AFTER)` で上限クリップ。簡単な1行修正で重大リスクを排除できる。`ValueError` ハンドリングも合わせて追加する。
3. **[R4-03] SSRF 対策**: `paginate_link_header` / `paginate_response_body` の `next_url` に対し `_base_url` と同一オリジン検証を追加する。`urllib.parse` で同一ホスト確認を実装する。
4. **[R4-11] next_url バグ修正**: `url = match.group(1)` を `next_url = match.group(1)` に修正（1行修正で機能バグ＋セキュリティリスクを両方解消）。R4-03 の SSRF 対策と合わせて対処する。
5. **[R4-04] git_clone エラーメッセージのサニタイズ**: `result.stderr` の認証情報マスク関数を追加し、`GitCommandError` に渡す前に適用する。
6. **[R4-05] HTTP プローブの廃止/制限**: SSH URL の場合も HTTPS プローブに統一し、HTTP フォールバックを廃止する。`probe_unknown_host()` の `scheme` パラメータを `"https"` 固定またはバリデーション追加する。
7. **[R4-06] Windows パーミッション設定の堅牢化**: `os.getlogin()` を `getpass.getuser()` に置換し、`icacls` 失敗時の警告出力を追加する。ACL リセットフローも検討する。
8. **[R4-07] NetworkError メッセージのサニタイズ**: 接続エラー時も `apiKey` をマスクし、`_mask_api_key()` を汎用的な `_mask_sensitive_params()` に拡張する。
9. **[R4-12] TOML 書き出しの修正**: `_write_credentials_toml()` に全制御文字エスケープを追加するか、`tomli-w` ライブラリへ移行する。
10. **[R4-10] probe 例外絞り込み**: `except Exception` を requests 系例外に絞り、SSL エラーは警告出力するように変更する。
11. **[R4-08] DetectionError メッセージのサニタイズ**: URL から認証情報部分を除去してからエラーメッセージに埋め込む。
12. **[R4-13] `_session` 直接アクセスの排除**: `HttpClient` に内部絶対 URL リクエストメソッドを追加してカプセル化を強化する。
13. **[R4-09] TLS 検証の明示化**: `HttpClient` に `verify` パラメータを追加し、デフォルト `True` を明示する。
14. **[R4-14] API URL 保存先の見直し**: ドキュメントへの明記、または `config.toml` への移行を検討する。

---

## 次ラウンドへの申し送り

- **Round 5（入力バリデーション・データ整合性）**: `create_issue` / `create_pull_request` 等のユーザー入力（`title`, `body`, `branch` 名等）に対するバリデーション欠如を調査する。特に `branch` 名への特殊文字注入（スラッシュ、ドット等）が API パスに影響しないかを確認する。
- **WIQL インジェクション（R4-01）**: Azure DevOps WIQL 仕様上パラメータ束縛が使用できないため、入力値の正規化方針をプロジェクトとして決定する必要がある。早急な修正タスクの作成を推奨する。
- **paginate next_url バグ（R4-11）**: `paginate_link_header` が実際には 2 ページ目以降を取得できていない可能性があり、GitHub / Gitea / GitBucket アダプターの統合テストで実データを使った検証が必要。
- **SSRF（R4-03）**: 今後 self-hosted サービス対応（Gitea/GitLab オンプレ等）が拡大するにつれリスクが高まる。`HttpClient` クラスのリファクタリング計画と合わせて検討を推奨する。
- **認証情報の秘匿設計**: `GitCommandError` 経由の間接漏洩（R4-04）は見落とされやすい。今後の機能追加でリスクが拡大しないよう、トークンマスクを横断的な方針として確立することを推奨する。
- **Windows 環境テスト（R4-06）**: 現在の CI に Windows ランナーを追加することで自動検証できる。Windows 固有のパーミッション処理に対するモックテストの整備を次ラウンドで検討する。
- **`create_adapter` での token ライフタイム管理**: トークンがメモリ上に長期保持されるケースの調査（`HttpClient` インスタンスの寿命とトークンの扱い）。
- **レート制限の複数回リトライ設計**: 現在は 429 時に 1 回のみ再送を試みるが、バックオフ戦略（指数バックオフ）の導入を次ラウンドで検討する。
