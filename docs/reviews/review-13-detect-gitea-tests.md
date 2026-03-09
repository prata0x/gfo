# gfo Review Report — Round 13: detect.py / Gitea / テスト品質

## 概要
- レビュー日: 2026-03-09
- 対象: `gogs.py`, `forgejo.py`, `gitbucket.py`, `gitea.py`, `detect.py` の精読 + テスト品質確認
- コミット差分なし（R9〜R12 の修正は引き続き未実施）
- 発見事項: 重大 1 / 中 2 / 軽微 2

---

## R9〜R12 未修正問題（全件継続）

git log に新コミットなし。R9-01〜R12-07 の 22 件は引き続き未修正。

---

## 新規発見事項

---

### [R13-01] 🔴 `test_backlog.py` の `TestCloseIssue` がバグのある URL をモックし誤動作を正しい動作として検証

- **ファイル**: `tests/test_adapters/test_backlog.py` L416-423 および `src/gfo/adapter/backlog.py` L249-250
- **説明**: R12-01 で指摘した `BacklogAdapter.close_issue` の API パス誤り（`/issues/{number}` が正しくは `/issues/{project_key}-{number}` であるべき）に対して、テストがその誤ったパスをモック URL として設定しており、バグのある実装を「正しい動作」として検証している。
  ```python
  # test_backlog.py L416-423
  class TestCloseIssue:
      def test_close(self, mock_responses, backlog_adapter):
          mock_responses.add(
              responses.PATCH, f"{ISSUES_PATH}/3",   # ← /issues/3 （バグの URL）
              json=_issue_data(id=3, status_id=4), status=200,
          )
          backlog_adapter.close_issue(3)
          # ← /issues/TEST-3 であるべき
  ```
  `ISSUES_PATH = f"{BASE}/issues"` なので `f"{ISSUES_PATH}/3"` = `https://.../issues/3`。正しくは `https://.../issues/TEST-3` をモックすべき。このテストは R12-01 の実装バグが存在しても PASS し続ける。
- **影響**: テストが実装のバグを検出できない。実装を修正した場合にテストが FAIL し、修正の整合性が取れていないことを示す二重の問題になる。本番で Backlog を使用するユーザーは誤った Issue がクローズされるリスクを負っている。
- **推奨修正（セット）**: `backlog.py` と `test_backlog.py` を同時に修正する。
  ```python
  # backlog.py
  def close_issue(self, number: int) -> None:
      self._client.patch(
          f"/issues/{self._project_key}-{number}",
          json={"statusId": _STATUS_CLOSED_ID},
      )

  # test_backlog.py
  mock_responses.add(
      responses.PATCH, f"{BASE}/issues/TEST-3",   # プロジェクトキー付き
      json=_issue_data(id=3, status_id=4), status=200,
  )
  ```

---

### [R13-02] 🟡 `probe_unknown_host` が `requests.get(..., verify=True)` を直接呼び出し SSL 検証が常に有効

- **ファイル**: `src/gfo/detect.py` L214-248
- **説明**: `probe_unknown_host` 関数は `HttpClient` を使わず `requests.get()` を直接呼び出している。`verify=True` がハードコードされており、R9-04 で提案された `GFO_INSECURE=1` 環境変数による SSL 検証無効化を将来追加しても `probe_unknown_host` には適用されない。
  ```python
  resp = requests.get(f"{base}/api/v1/version", timeout=5, verify=True)
  ```
  `HttpClient` を使わないのは、プローブ時点では認証情報もベース URL も決まっていないためだが、SSL 検証の設定は `HttpClient` とは独立して制御できる。
- **影響**: R9-04 の修正（SSL 証明書検証の設定化）を実施しても、`probe_unknown_host` の HTTP リクエストは引き続き SSL 検証が強制され、セルフサイン証明書環境のホストをプローブできない。企業内の未知ホストの自動検出が失敗し続ける。
- **推奨修正**: 環境変数を直接参照する一行を追加する。
  ```python
  import os
  _verify_ssl = not os.environ.get("GFO_INSECURE", "").lower() in ("1", "true", "yes")

  resp = requests.get(f"{base}/api/v1/version", timeout=5, verify=_verify_ssl)
  ```
  R9-04 の対応と合わせて同一 PR で修正することが望ましい。

---

### [R13-03] 🟡 `GiteaAdapter.list_issues` がフィルタ後に `limit` 未満になる可能性

- **ファイル**: `src/gfo/adapter/gitea.py` L80-84
- **説明**: `list_issues` は `paginate_link_header(..., limit=limit)` で最大 `limit` 件を取得した後、`"pull_request" not in r` でフィルタリングする。`type: "issues"` パラメータをサーバーに渡しているため、通常 PR は含まれないが、Gitea の旧バージョンや特定条件下で PR が混入する場合、有効な Issue の件数が `limit` を下回る可能性がある。
  ```python
  results = paginate_link_header(
      self._client, f"{self._repos_path()}/issues",
      params=params, limit=limit, per_page_key="limit",
  )
  return [self._to_issue(r) for r in results if "pull_request" not in r]
  # limit=30 を要求しても実際に返る件数が 30 未満になりうる
  ```
  Gitea 同様の `GogsAdapter`（`GiteaAdapter` を継承）にも同じ問題が潜在的に存在する。
- **影響**: `gfo issue list --limit 30` を実行しても 30 件未満の Issue しか返らないことがある。
- **推奨修正**: フィルタ後の件数不足を補うために `limit` を超過取得してからスライスするか、フィルタの有効性をドキュメントに明記して既知の制約として扱う。または `type=issues` パラメータへの依存を信頼するなら、フィルタ自体が不要かを検討する。

---

### [R13-04] 🟢 `detect.py` L231: `RequestException` が包含する例外を重複記述

- **ファイル**: `src/gfo/detect.py` L231
- **説明**: `probe_unknown_host` 内の `except` 節で `requests.ConnectionError`、`requests.Timeout`、`requests.RequestException` を列挙しているが、`RequestException` は `ConnectionError` と `Timeout` の基底クラスであり、前の 2 つは `RequestException` に包含されて冗長になっている。
  ```python
  except (requests.ConnectionError, requests.Timeout, requests.RequestException):
      pass
  # → requests.RequestException だけで同じ効果
  ```
  同様のパターンが L239、L247 にも存在する。
- **影響**: コードの意図が分かりにくくなる（意図的に細分化しているのか誤りなのか）。実害はないが静的解析ツールが警告を出す。
- **推奨修正**: `except requests.RequestException:` に統一する。

---

### [R13-05] 🟢 `detect.py` L266: 警告に `print()` を使用（`warnings.warn()` との不一致）

- **ファイル**: `src/gfo/detect.py` L265-270
- **説明**: git config の `gfo.type` と URL から検出されたサービス種別が食い違うときに警告を `print(..., file=sys.stderr)` で出力している。一方 `auth.py` L91-95 ではアイコン設定失敗の警告に `warnings.warn()` を使用しており、プロジェクト内で 2 種類の警告方法が混在する。
  ```python
  print(
      f"warning: gfo.type={saved_type!r} but URL suggests {result.service_type!r}; "
      "using git config value.",
      file=sys.stderr,
  )
  ```
  `warnings.warn()` を使うと Python の警告フィルタ（`-W` フラグ、`PYTHONWARNINGS` 環境変数）による制御や `warnings.catch_warnings()` を使ったテスト時の検証が可能になる。
- **影響**: 警告のテストが困難（`capfd` でキャプチャは可能だが `pytest.warns()` が使えない）。警告フィルタで抑制できない。
- **推奨修正**:
  ```python
  import warnings
  warnings.warn(
      f"gfo.type={saved_type!r} but URL suggests {result.service_type!r}; "
      "using git config value.",
      stacklevel=2,
  )
  ```

---

## 全問題サマリーテーブル（R9〜R13 未修正・新規）

| ID | 重大度 | ファイル | 概要 |
|----|--------|---------|------|
| R9-01 | 🔴 重大 | `bitbucket.py` | `GfoError` 未インポート → `NameError` |
| R10-01 | 🔴 重大 | `detect.py` L16 | import が関数定義の後（PEP 8 違反） |
| R12-01 | 🔴 重大 | `backlog.py` L250 | `close_issue` のパスが `/issues/{n}` で誤 Issue をクローズ |
| **R13-01** | 🔴 重大 | `test_backlog.py` L418 | `TestCloseIssue` が R12-01 のバグ URL をモック → バグを検出しない |
| R9-02 | 🟡 中 | `commands/repo.py` L65 | f-string 欠落 |
| R9-03 | 🟡 中 | `backlog.py` L100 | `ValueError` 未捕捉 |
| R9-04 | 🟡 中 | `http.py` L47 | SSL 証明書検証ハードコード |
| R9-05 | 🟡 中 | `config.py` L128 | `except Exception` 広範捕捉 |
| R9-06 | 🟡 中 | `output.py` L91 | 単一要素でオブジェクト返却 |
| R9-07 | 🟡 中 | `detect.py` L15 | `_mask_credentials` 正規表現不完全 |
| R10-02 | 🟡 中 | `commands/init.py` L138 | `except Exception` 広範捕捉 |
| R11-01 | 🟡 中 | `git_util.py` / `detect.py` | `_mask_credentials` 重複定義 |
| R11-02 | 🟡 中 | `http.py` | リトライループ重複 |
| R11-03 | 🟡 中 | `commands/pr.py` L63 | `handle_checkout` でブランチ既存時エラー未処理 |
| R12-02 | 🟡 中 | `gitlab.py` L255 | `create_release` で `prerelease` が API に渡らない |
| R12-03 | 🟡 中 | `azure_devops.py` L73 | PR の `url` が API URL（ブラウザ不可） |
| R12-04 | 🟡 中 | `cli.py` L96 | `--priority` に `type=int` なし |
| R12-05 | 🟡 中 | `azure_devops.py` L197 | WIQL 件数が 200 でキャップ |
| **R13-02** | 🟡 中 | `detect.py` L214 | `probe_unknown_host` の SSL 検証ハードコード |
| **R13-03** | 🟡 中 | `gitea.py` L84 | `list_issues` がフィルタ後に `limit` 未満になりうる |
| R10-03 | 🟢 軽微 | `http.py` L103, L149 | 到達不可能な `return resp` |
| R11-04 | 🟢 軽微 | `commands/issue.py` | `get_adapter()` が config を返さない設計の限界 |
| R11-05 | 🟢 軽微 | `config.py` L14 | `ProjectConfig` が `frozen=True` でない |
| R12-06 | 🟢 軽微 | `backlog.py` L256 | `list_repositories` がページネーション未使用 |
| R12-07 | 🟢 軽微 | `auth_cmd.py` L60 | 区切り線の長さが表示幅ベースでない |
| **R13-04** | 🟢 軽微 | `detect.py` L231 | `RequestException` が冗長に重複記述 |
| **R13-05** | 🟢 軽微 | `detect.py` L265 | 警告に `print()` を使用（`warnings.warn()` と不一致） |

---

## 推奨アクション（優先度順）

### 即時対応（1行〜数行で修正可能）

1. **[R9-01]** `bitbucket.py` L15 — `from gfo.exceptions import GfoError, NotSupportedError`
2. **[R12-01][R13-01]** `backlog.py` L250 + `test_backlog.py` L418 — セットで修正。`close_issue` のパスを `f"/issues/{self._project_key}-{number}"` に、テストのモック URL を `f"{BASE}/issues/TEST-3"` に変更
3. **[R10-01]** `detect.py` L16 — import 行を L10 付近の import ブロックに移動
4. **[R12-04]** `cli.py` L96 — `add_argument("--priority", type=int)`
5. **[R9-02]** `commands/repo.py` L65 — f-string プレフィックス追加
6. **[R9-03]** `backlog.py` L110 — `except (KeyError, TypeError, ValueError)` に変更

### 中期対応（設計変更が必要）

7. **[R9-04][R13-02]** SSL 証明書検証を設定化 — `HttpClient` + `probe_unknown_host` の両方に同時適用
8. **[R12-02]** `gitlab.py` — `create_release` に `upcoming_release` 追加
9. **[R12-03]** `azure_devops.py` — PR の web URL を `repository.webUrl` から構成
10. **[R12-05]** `azure_devops.py` L197 — WIQL `$top` キャップ解除
11. **[R9-05][R10-02]** `config.py` + `init.py` — `except Exception` 限定例外化
12. **[R11-01][R9-07]** `_mask_credentials` 統合・正規表現改善

### 軽微なクリーンアップ

13. **[R13-04]** `detect.py` — `except requests.RequestException:` に統一
14. **[R13-05]** `detect.py` — `print()` を `warnings.warn()` に変更
15. **[R13-03]** `gitea.py` — `list_issues` の件数不足問題をドキュメント化またはフィルタ方法を改善

---

## 次ラウンドへの申し送り

- **未読ファイル**: `commands/milestone.py`、`commands/init.py`（全体）、`tests/test_detect.py`、`tests/test_http.py` はまだ詳細確認が完了していない
- **R12-01 + R13-01 はセット修正必須**: `close_issue` 実装とテストを同時に修正しないと、テストが PASS しても本番では誤動作が継続する
- **テスト品質の問題パターン**: R13-01 のようにテスト自体が誤動作を正しい動作として検証しているケースが他にも存在する可能性がある。特に Backlog の `get_issue`（`f"/issues/{project_key}-{number}"` を使う実装）と `close_issue`（修正前は `/issues/{number}`）の整合性確認が必要
