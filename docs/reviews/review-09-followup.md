# gfo Review Report — Round 9: フォローアップ・新規バグ発見

## 概要
- レビュー日: 2026-03-09
- 前回（review-08）から継続する第9ラウンド
- 対象: Round 8 の全修正適用後の現状ソースコード
- 発見事項: 重大 1 / 中 4 / 軽微 3

---

## 発見事項

---

### [R9-01] 🔴 `BitbucketAdapter` で `GfoError` が未インポート

- **ファイル**: `src/gfo/adapter/bitbucket.py` L54, L77, L98
- **説明**: `_to_pull_request`、`_to_issue`、`_to_repository` の各メソッドの `except` ブロックで `GfoError` を `raise` しているが、ファイル先頭の import セクションに `GfoError` が含まれていない。
  ```python
  # import されているのは
  from gfo.exceptions import NotSupportedError
  # GfoError は import されていない

  # しかし使用されている
  raise GfoError(f"Unexpected API response: missing field {e}") from e  # L54, L77, L98
  ```
- **影響**: Bitbucket アダプター使用時に PR / Issue / リポジトリの API レスポンス解析でフィールド欠落が発生した場合、`NameError: name 'GfoError' is not defined` が発生し、元の例外ではなく別の例外が送出される。Bitbucket を使用するすべてのユーザーに影響する潜在的なクラッシュ。
- **推奨修正**: import 行に `GfoError` を追加する。
  ```python
  from gfo.exceptions import GfoError, NotSupportedError
  ```
- **テスト**: Bitbucket の `_to_pull_request` / `_to_issue` / `_to_repository` に不完全な dict を渡したとき `GfoError` が送出されることを確認するテスト。

---

### [R9-02] 🟡 `_resolve_host_without_repo` のエラーメッセージが f-string 未使用

- **ファイル**: `src/gfo/commands/repo.py` L65
- **説明**: エラーメッセージに `{host}` という変数参照を含めているが、文字列リテラルに `f` プレフィックスがないため、変数が展開されず文字通り `{host}` と表示される。
  ```python
  raise ConfigError(
      f"Could not determine service type for host '{host}'. "
      "Configure it in config.toml: [hosts.{host}] type = \"...\""  # ← f-string でない
  )
  ```
  2行目の文字列が `f"..."` でないため、ユーザーには実際のホスト名ではなく `[hosts.{host}]` という文字列が表示される。
- **影響**: ユーザーが `gfo repo list --host myserver.example.com` を実行してサービス種別が不明なとき、TOML 設定のサンプルに実際のホスト名が表示されず、設定方法がわかりにくい。
- **推奨修正**: 文字列を連結ではなくまとめて f-string にするか、2行目にも `f` プレフィックスを付ける。
  ```python
  raise ConfigError(
      f"Could not determine service type for host '{host}'. "
      f"Configure it in config.toml: [hosts.{host}] type = \"...\""
  )
  ```

---

### [R9-03] 🟡 `BacklogAdapter._to_issue` で `ValueError` が捕捉されない

- **ファイル**: `src/gfo/adapter/backlog.py` L100
- **説明**: Backlog の issueKey（例: `"PROJECT-123"`）から Issue 番号を抽出する際、`int()` 変換の失敗を `except (KeyError, TypeError)` で捕捉しているが `ValueError` が含まれていない。
  ```python
  number=int(data["issueKey"].split("-")[-1]) if isinstance(data.get("issueKey"), str) else data["id"],
  ```
  `issueKey` が `"PROJECT"` のようにハイフン区切りの数値部分がない場合、`int("PROJECT")` で `ValueError` が発生し、外側の `except (KeyError, TypeError)` には捕捉されない。
- **影響**: 想定外の issueKey フォーマット（Backlog のカスタマイズや将来の API 変更）で `ValueError` が未捕捉のまま伝播し、コマンドがクラッシュする。
- **推奨修正**: `except` に `ValueError` を追加するか、変換ロジックを安全にする。
  ```python
  except (KeyError, TypeError, ValueError) as e:
      raise GfoError(f"Unexpected API response: missing field {e}") from e
  ```

---

### [R9-04] 🟡 SSL 証明書検証がハードコードで無効化できない

- **ファイル**: `src/gfo/http.py` L47
- **説明**: `self._session.verify = True` がハードコードされており、セルフサイン証明書を使用するオンプレミス Git サーバー（企業内 GitLab、Gitea、Backlog 等）に対して SSL エラーが発生しても回避する手段がない。
  ```python
  self._session.verify = True  # 変更不可
  ```
- **影響**: 企業内イントラネット等のセルフサイン証明書環境でサービスを利用するユーザーが `ssl.SSLError` で接続できない。ワークアラウンドとして環境変数やオプションが提供されていないため、ユーザー側での対処が困難。
- **推奨修正**: `HttpClient.__init__` に `verify: bool = True` パラメータを追加し、`create_http_client` と config 解決経由で制御可能にするか、環境変数 `GFO_INSECURE=1` で無効化できるようにする。
  ```python
  insecure = os.environ.get("GFO_INSECURE", "").lower() in ("1", "true", "yes")
  self._session.verify = not insecure
  ```
- **テスト**: `GFO_INSECURE=1` 設定時に `session.verify` が `False` になることを確認するテスト。

---

### [R9-05] 🟡 `config.py` の `resolve_project_config` が `except Exception` で全例外を握りつぶす

- **ファイル**: `src/gfo/config.py` L128
- **説明**: remote URL の解析失敗を許容するための `try/except` が `except Exception:` と広範に定義されており、`PermissionError`、`MemoryError`、`SystemExit` などの予期しない例外も無音で `owner = ""` 等に初期化されてしまう。
  ```python
  try:
      remote_url = gfo.git_util.get_remote_url(cwd=cwd)
      detect_result = gfo.detect.detect_from_url(remote_url)
      owner = detect_result.owner
      # ...
  except Exception:      # ← 広すぎる
      owner = ""
  ```
- **影響**: git コマンドの実行権限エラーやメモリ不足など、本来ユーザーに通知すべき問題が黙って無視され、owner/repo が空のまま後続処理でエラーが別の形で現れる（デバッグが困難になる）。
- **推奨修正**: 例外の種類を限定する。
  ```python
  from gfo.exceptions import DetectionError, ConfigError, GfoError
  from gfo.git_util import GitCommandError

  except (DetectionError, ConfigError, GfoError, GitCommandError, ValueError):
      owner = ""
  ```

---

### [R9-06] 🟢 `format_json` が単一要素リストをオブジェクトとして返す（一貫性の欠如）

- **ファイル**: `src/gfo/output.py` L91
- **説明**: `--format json` 時に件数が1件の場合は JSON オブジェクト（`{...}`）を返し、2件以上の場合は JSON 配列（`[...]`）を返す。呼び出し側スクリプトが常に同じ型を期待できない。
  ```python
  data = dicts[0] if len(dicts) == 1 else dicts  # ← 件数で型が変わる
  ```
- **影響**: `gfo pr list --format json | jq '.[].title'` が1件のとき失敗し、`gfo pr list --format json | jq '.title'` が複数件のとき失敗する。スクリプトでの利用が困難になる。
- **推奨修正**: 常に配列を返す（または `--format json-one` のような別フォーマットを追加する）。
  ```python
  return json.dumps(dicts, indent=2, ensure_ascii=False, default=str)
  ```

---

### [R9-07] 🟢 `detect.py` の `_mask_credentials` 正規表現でパスワードに `@` が含まれる場合に不完全なマスク

- **ファイル**: `src/gfo/detect.py` L15付近
- **説明**: URL 中の認証情報をマスクする正規表現が `r"://[^@\s]+@"` であり、パスワードに URL エンコードされていない `@` が含まれる場合（例: `user:pass@word@host`）、最初の `@` までをマスクし残りが露出する。
- **影響**: 認証情報を含む URL がエラーメッセージやログに表示される際に、マスクが不完全となりパスワードの一部が漏洩する可能性がある。実際の使用では URL エンコードされていることがほとんどだが、一部のツールが生の `@` を含む URL を渡す可能性がある。
- **推奨修正**: より広くマスクする正規表現を使用する。
  ```python
  re.sub(r"://[^/\s]*@", "://***@", text)
  ```

---

### [R9-08] 🟢 `BacklogAdapter` のインスタンスキャッシュが複数プロジェクト間で混在する可能性

- **ファイル**: `src/gfo/adapter/backlog.py` L39-55
- **説明**: `_project_id` と `_merged_status_id` をインスタンス変数としてキャッシュしているが、同一インスタンスを異なるプロジェクト（owner/repo の異なる設定）で再利用した場合に古いキャッシュが使われる。現状の `gfo` は1コマンドにつき1アダプターインスタンスを生成するため実害はないが、将来的に複数リポジトリを並列処理する際に問題になりうる。
- **影響**: 現状は実害なし。ただし将来の拡張時のリスク。
- **推奨修正**: キャッシュキーに `(owner, repo)` または `project_key` を含めるか、設計の制約（1インスタンス1プロジェクト）をクラスのドキュメントに明記する。

---

## サマリーテーブル

| ID | 重大度 | ファイル | 行 | 説明 |
|----|--------|---------|------|------|
| R9-01 | 🔴 重大 | `src/gfo/adapter/bitbucket.py` | L54, L77, L98 | `GfoError` が未インポート → `NameError` が発生 |
| R9-02 | 🟡 中 | `src/gfo/commands/repo.py` | L65 | f-string プレフィックス欠落でエラーメッセージに `{host}` が展開されない |
| R9-03 | 🟡 中 | `src/gfo/adapter/backlog.py` | L100 | `int()` の `ValueError` が `except` で捕捉されない |
| R9-04 | 🟡 中 | `src/gfo/http.py` | L47 | SSL 証明書検証がハードコードで変更不可 |
| R9-05 | 🟡 中 | `src/gfo/config.py` | L128 | `except Exception` による広範な例外握りつぶし |
| R9-06 | 🟢 軽微 | `src/gfo/output.py` | L91 | 単一要素リストが配列でなくオブジェクトとして出力される |
| R9-07 | 🟢 軽微 | `src/gfo/detect.py` | ― | `_mask_credentials` の正規表現が `@` を含むパスワードで不完全なマスク |
| R9-08 | 🟢 軽微 | `src/gfo/adapter/backlog.py` | L39-55 | インスタンスキャッシュが複数プロジェクト間で混在するリスク |

---

## 推奨アクション（優先度順）

1. **[R9-01] `bitbucket.py` に `GfoError` import を追加** — 1行の修正で実行時 `NameError` を防ぐ。Bitbucket ユーザー全員に影響する重大バグ。即時修正が必要。

2. **[R9-02] `repo.py` L65 の f-string 修正** — `"Configure..."` の前に `f` を追加するだけ。ユーザーエクスペリエンスに直結するエラーメッセージの修正。

3. **[R9-03] `backlog.py` の `except` に `ValueError` を追加** — issueKey フォーマットが想定外の場合のクラッシュを防ぐ。

4. **[R9-04] SSL 検証オプションの追加** — 環境変数 `GFO_INSECURE=1` またはコンフィグ設定でセルフサイン証明書環境をサポート。企業ユーザーの利便性向上。

5. **[R9-05] `config.py` の `except Exception` を限定例外に変更** — デバッグ容易性の向上。ただし現行の「remote URL がなくても失敗しない」という設計意図を維持しつつ、捕捉対象を絞る。

6. **[R9-06] `format_json` を常に配列で返すよう修正** — `jq` などとのパイプ利用の一貫性を確保。

7. **[R9-07][R9-08] 軽微なクリーンアップ** — 正規表現の改善とキャッシュ設計の文書化をまとめて対応する。

---

## 次ラウンドへの申し送り

- **テストカバレッジ**: R9-01 の `GfoError` 未インポートが既存テストで検出されなかった理由を調査する。`test_adapters/test_bitbucket.py` でエラーパスのテストが不足している可能性がある。
- **型チェック CI**: mypy を CI に組み込むことで R9-01 のような未定義名参照を自動検出できる。`--strict` モードでの全ファイルスキャンを推奨。
- **`_mask_credentials` の設計**: URL 内の認証情報マスクは gfo のセキュリティに関わる機能であり、URLエンコードされた認証情報のデコード後マスクも検討すべき。
- **`format_json` の API 安定性**: 将来的に `--format json` の出力形式を変更する場合は互換性への影響が大きいため、変更前に利用パターンを文書化しておくことを推奨。
