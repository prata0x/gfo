# gfo Review Report — Round 14: http.py / config.py / output.py / azure_devops.py

## 概要
- レビュー日: 2026-03-09
- 対象: `http.py`, `config.py`, `output.py`, `commands/init.py`, `azure_devops.py`, `milestone.py`, `test_detect.py`, `test_http.py`
- R9〜R13 の未修正課題の現状確認 + 新規発見事項
- 発見事項: 重大 0 / 中 7 / 軽微 4

---

## R9〜R13 未修正課題（継続）の現状確認

| ID | ファイル | 現在の実装 | 状態 |
|----|---------|-----------|------|
| R9-04+R13-02 | `http.py` L47, `detect.py` L215/236/244 | `verify=True` ハードコード | **未修正** |
| R9-05+R10-02 | `config.py` L128, `init.py` L138 | `except Exception:` | **未修正** |
| R9-06 | `output.py` L91 | `dicts[0] if len(dicts)==1 else dicts` | **未修正** |
| R11-01+R9-07 | `git_util.py` L14, `detect.py` L14 | 同一関数が重複定義 | **未修正** |
| R11-02 | `http.py` | リトライロジック重複 | **未修正** |
| R10-03 | `http.py` L103, L149 | `return resp  # unreachable` | **未修正** |
| R12-03 | `azure_devops.py` L73 | `url=data.get("url", "")` が API URL | **未修正** |
| R12-05 | `azure_devops.py` L197 | `min(limit, 200)` キャップ | **未修正** |

---

## 新規発見事項

---

### [R14-01] 🟡 `commands/init.py` の対話モードでユーザー入力 `service_type` を検証しない

- **ファイル**: `src/gfo/commands/init.py` L99-100
- **説明**: 非インタラクティブモード（L38-42）では `service_type` が `_VALID_SERVICE_TYPES` に含まれるか検証しているが、対話モードでは `input()` で受け取ったままアダプター生成に渡す。不正な文字列が渡ると `create_adapter()` で `KeyError` や分かりにくいエラーになる。
  ```python
  if service_type is None:
      service_type = input("Service type (github/gitlab/bitbucket/...): ").strip()
      # ← 検証なし
  ```
- **推奨修正**:
  ```python
  if service_type is None:
      service_type = input("Service type (github/gitlab/bitbucket/...): ").strip()
      if service_type not in _VALID_SERVICE_TYPES:
          raise ConfigError(f"Invalid service type: {service_type!r}. Choose from: {', '.join(_VALID_SERVICE_TYPES)}")
  ```

---

### [R14-02] 🟡 `output.py` L91 — JSON 出力が 1件でオブジェクト、複数件で配列（R9-06 の詳細確認）

- **ファイル**: `src/gfo/output.py` L88-92
- **説明**: 確認済みの通り `dicts[0] if len(dicts) == 1 else dicts` により、1件の場合に配列でなくオブジェクトを返す。
  ```python
  data = dicts[0] if len(dicts) == 1 else dicts
  ```
- **推奨修正**: 常に配列を返す。
  ```python
  data = dicts
  ```

---

### [R14-03] 🟡 `http.py` L103, L149 — 到達不可能な `return resp`（R10-03 の詳細確認）

- **ファイル**: `src/gfo/http.py` L103, L149
- **説明**: リトライループは必ず `return resp`（正常時）または `raise`（エラー/リトライ上限）で終了する。ループ外の `return resp` は到達不可能。
- **推奨修正**: 2箇所とも削除する。mypy の型チェックが壊れる場合は `raise AssertionError("unreachable")` に置換する。

---

### [R14-04] 🟡 `config.py` L128 / `init.py` L138 — `except Exception` 広範捕捉（R9-05+R10-02 の詳細確認）

- **ファイル**: `src/gfo/config.py` L128, `src/gfo/commands/init.py` L138
- **説明**: `detect_from_url()` / `get_remote_url()` 呼び出しの失敗を許容するための `try/except` が `except Exception:` と広範すぎる。`ImportError`、`MemoryError`、`SystemExit` 等も無音で飲み込む。
- **推奨修正**:
  ```python
  # config.py
  from gfo.exceptions import DetectionError, ConfigError
  from gfo.git_util import GitCommandError
  except (DetectionError, ConfigError, GitCommandError, ValueError, OSError):

  # init.py（detect_from_url のみ）
  except (DetectionError, ValueError, OSError):
  ```

---

### [R14-05] 🟡 `azure_devops.py` L73 — PR URL が API URL（ブラウザ不可）（R12-03 の詳細確認）

- **ファイル**: `src/gfo/adapter/azure_devops.py` L73
- **説明**: API レスポンスの `url` フィールドは `https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}/pullrequests/{id}` 形式で、ブラウザで直接開けない。`repository.webUrl` と PR ID から組み立てた web URL を使うべき。
  ```python
  url=data.get("url", ""),  # ← API URL
  ```
- **推奨修正**:
  ```python
  repo_web = data.get("repository", {}).get("webUrl", "")
  pr_id = data["pullRequestId"]
  url = f"{repo_web}/pullrequest/{pr_id}" if repo_web else data.get("url", ""),
  ```

---

### [R14-06] 🟡 `azure_devops.py` L197 — `$top` が `min(limit, 200)` でキャップ（R12-05 の詳細確認）

- **ファイル**: `src/gfo/adapter/azure_devops.py` L197
- **説明**: Azure DevOps WIQL API の仕様として `$top` の最大値は 200。`min(limit, 200)` により `limit > 200` の要求が 200 件で打ち切られ、L215 `results[:limit]` でも補完されない。
  ```python
  params={"$top": min(limit, 200)},
  ```
- **推奨修正**: `$top=limit` でAPIに渡し、200 件超えの場合は複数回 fetch するか、制限として明記してドキュメント化する。簡易対応として `$top: limit` のみ変更し、200 件の上限はAPI制約として受け入れる。

---

### [R14-07] 🟡 `http.py` L47 — SSL 証明書検証ハードコード（R9-04+R13-02 の詳細確認）

- **ファイル**: `src/gfo/http.py` L47
- **説明**: `self._session.verify = True` ハードコード。加えて `detect.py` の `probe_unknown_host` でも同様（R13-02）。`GFO_INSECURE=1` 環境変数が実装されていない。
  ```python
  self._session.verify = True
  ```
- **推奨修正**:
  ```python
  import os
  _verify_ssl = os.environ.get("GFO_INSECURE", "").lower() not in ("1", "true", "yes")
  self._session.verify = _verify_ssl
  ```
  `detect.py` の `probe_unknown_host` 内の `verify=True` 3箇所も同様に `_verify_ssl` 変数を参照する。

---

### [R14-08] 🟢 `test_detect.py` — SSL 検証失敗シナリオのテスト欠落

- **ファイル**: `tests/test_detect.py`
- **説明**: すべてのテストが `@responses.activate` モックで実行されており、自己署名証明書環境でのSSL検証失敗（R9-04+R13-02 修正後の `GFO_INSECURE=1` 動作）をカバーするテストがない。
- **推奨修正**: `GFO_INSECURE=1` 設定時に `requests.get(..., verify=False)` が呼ばれることを確認するテストを追加する。

---

### [R14-09] 🟢 `output.py` — 0件時の出力先が形式によって異なる（潜在的 UX 問題）

- **ファイル**: `src/gfo/output.py`
- **説明**: 0件時に json 形式は `print("[]")` で stdout に出力するが、table/plain 形式は `print("No results found.", file=sys.stderr)` で stderr に出力する。スクリプトで `gfo issue list --format json 2>/dev/null | jq` を使う場合と `gfo issue list 2>/dev/null` では挙動が異なる。
- **影響**: 軽微。現行の動作は意図的とも解釈できるが、ドキュメントに明記されていない。

---

### [R14-10] 🟢 `milestone.py` — 問題なし

全体を確認したが、新規の問題は発見されなかった。`list_milestones`・`create_milestone`・`close_milestone` の各ハンドラは適切に実装されている。

---

## 全問題サマリーテーブル（R9〜R14 未修正・新規）

| ID | 重大度 | ファイル | 概要 |
|----|--------|---------|------|
| R9-01 | ✅ 修正済み | `bitbucket.py` | `GfoError` import 追加 |
| R9-02 | ✅ 修正済み | `commands/repo.py` | f-string 修正 |
| R9-03 | ✅ 修正済み | `backlog.py` | `ValueError` 追加 |
| R10-01 | ✅ 修正済み | `detect.py` | import 順序修正 |
| R12-01+R13-01 | ✅ 修正済み | `backlog.py` + `test_backlog.py` | close_issue パス修正 |
| R12-02 | ✅ 修正済み | `gitlab.py` | prerelease → upcoming_release |
| R12-04 | ✅ 修正済み | `cli.py` | --priority type=int |
| R13-04 | ✅ 修正済み | `detect.py` | 冗長 except 統一 |
| R13-05 | ✅ 修正済み | `detect.py` | warnings.warn() 統一 |
| **R9-04+R13-02** | 🟡 中 | `http.py` L47, `detect.py` | SSL 検証ハードコード |
| **R9-05+R10-02** | 🟡 中 | `config.py` L128, `init.py` L138 | `except Exception` 広範捕捉 |
| **R9-06 / R14-02** | 🟡 中 | `output.py` L91 | 1件でオブジェクト返却 |
| **R10-03 / R14-03** | 🟡 中 | `http.py` L103, L149 | 到達不可能な return resp |
| **R11-01+R9-07** | 🟡 中 | `git_util.py`, `detect.py` | `_mask_credentials` 重複定義 |
| **R11-02** | 🟡 中 | `http.py` | リトライループ重複 |
| **R11-03** | 🟡 中 | `commands/pr.py` L63 | checkout でブランチ既存時エラー未処理 |
| **R12-03 / R14-05** | 🟡 中 | `azure_devops.py` L73 | PR URL が API URL |
| **R12-05 / R14-06** | 🟡 中 | `azure_devops.py` L197 | WIQL limit キャップ |
| **R14-04** | 🟡 中 | `config.py`, `init.py` | `except Exception` 広範捕捉（R9-05+R10-02 再確認） |
| **R14-07** | 🟡 中 | `http.py` | SSL ハードコード（R9-04+R13-02 再確認） |
| R9-08 | 🟢 軽微 | `backlog.py` | インスタンスキャッシュ設計（許容） |
| R11-04 | 🟢 軽微 | `commands/issue.py` | get_adapter() 設計制約 |
| R11-05 | 🟢 軽微 | `config.py` L14 | `frozen=True` なし |
| R12-06 | 🟢 軽微 | `backlog.py` | list_repositories ページネーション未使用 |
| R12-07 | 🟢 軽微 | `auth_cmd.py` | 区切り線長さ |
| **R14-01** | 🟢 軽微 | `commands/init.py` | 対話モード service_type 検証なし |
| **R14-08** | 🟢 軽微 | `test_detect.py` | SSL 検証テスト欠落 |
| **R14-09** | 🟢 軽微 | `output.py` | 0件時の出力先が形式で異なる |

---

## 推奨アクション（優先度順）

### 即時対応

1. **[R9-06/R14-02]** `output.py` L91 — `data = dicts` に変更（1行）
2. **[R10-03/R14-03]** `http.py` L103, L149 — 到達不可能な `return resp` を削除（2行）

### 設計変更が必要なもの

3. **[R9-04+R13-02/R14-07]** `http.py` L47 + `detect.py` — `GFO_INSECURE` 環境変数対応（セットで修正）
4. **[R9-05+R10-02/R14-04]** `config.py` L128, `init.py` L138 — `except Exception` 限定化
5. **[R12-03/R14-05]** `azure_devops.py` — PR web URL の組み立て
6. **[R12-05/R14-06]** `azure_devops.py` — WIQL limit キャップ変更
7. **[R11-01+R9-07]** `git_util.py` + `detect.py` — `_mask_credentials` 重複解消

---

## 次ラウンドへの申し送り

- **即時対応 2 件（R9-06, R10-03）は 1 行修正**で対応可能
- **SSL 設定化（R9-04+R13-02）は `http.py` と `detect.py` をセットで修正**しないと片方だけ有効になる
- **`except Exception` 限定化（R9-05+R10-02）**: `DetectionError` / `GitCommandError` が存在するか `gfo/exceptions.py` と `gfo/git_util.py` を確認してから修正する
