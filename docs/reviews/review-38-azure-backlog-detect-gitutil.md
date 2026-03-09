# gfo Review Report — Round 38: azure_devops / backlog / detect / git_util 精査

## 概要

- **レビュー日**: 2026-03-09
- **対象**:
  - `src/gfo/adapter/azure_devops.py`
  - `src/gfo/adapter/backlog.py`
  - `src/gfo/detect.py`
  - `src/gfo/git_util.py`
  - `src/gfo/cli.py`（確認のみ）
  - `src/gfo/config.py`（確認のみ）

- **発見事項**: 新規 7 件（重大 0 / 中 2 / 軽微 5）

---

## エージェントレビューで誤報された項目（問題なし確認）

| 確認項目 | 結果 |
|---------|------|
| `config.py` L248 — Azure DevOps API URL に `/{project}` が含まれるのは誤り | OK — Azure DevOps REST API v7.x はプロジェクトスコープの API に `https://dev.azure.com/{org}/{project}/_apis/...` の形式を使用する。アダプターが `/git/repositories/{repo}` などを付加するため正しい |
| `azure_devops.py` L78 — `updated_at=data.get("closedDate")` で open PR が常に None | OK（API 制限）— Azure DevOps PR API の基本レスポンスに「最終更新日時」フィールドがない。`closedDate` は close/merge 時刻を表しており、open PR では None が最善 |
| `cli.py` L202-212 — requests 例外が未捕捉 | OK — `HttpClient` が `requests.RequestException` を `NetworkError`（`GfoError` サブクラス）に変換する。`GfoError` catch で全ケース捕捉済み |
| `cli.py` L193 — `args.command` のチェック不完全 | OK — argparse が常に command を設定する。実害なし |

---

## 新規発見事項

---

### [R38-01] 🟡 `detect.py` L196 — エラーメッセージで `path` が未マスク

- **ファイル**: `src/gfo/detect.py` L196
- **現在のコード**:
  ```python
  raise DetectionError(f"Cannot parse path: {path}")   # ← path がそのまま
  ```
- **説明**: 同関数の L148、L173、L185 では `_mask_credentials(path)` を使用して認証情報（例：`https://user:pass@host/...`）をマスクしているが、L196 だけ未マスク。認証情報を含む URL がエラーメッセージに露出する可能性がある。
- **推奨修正**:
  ```python
  raise DetectionError(f"Cannot parse path: {_mask_credentials(path)}")
  ```

---

### [R38-02] 🟡 `azure_devops.py` L199 — `limit=0`（全件取得）時の WIQL が Azure DevOps デフォルト制限（200件）に抑制される

- **ファイル**: `src/gfo/adapter/azure_devops.py` L199
- **現在のコード**:
  ```python
  wiql_params = {"$top": limit} if limit > 0 else {}
  ```
- **説明**: `limit=0`（全件取得）の場合、`$top` を指定しない空の params を渡す。Azure DevOps WIQL API は `$top` 未指定時にデフォルト 200 件を返す。結果として `limit=0` でも最大 200 件しか取得されない。他のアダプターは `paginate_page_param`/`paginate_offset` が `limit=0` で全件取得を行う設計だが、azure_devops では動作しない。Azure DevOps WIQL の `$top` 最大値は 20000。
- **推奨修正**:
  ```python
  wiql_params = {"$top": limit} if limit > 0 else {"$top": 20000}
  ```

---

### [R38-03] 🟢 `backlog.py` L130 — `Repository.url` が web URL ではなく clone URL と同一

- **ファイル**: `src/gfo/adapter/backlog.py` L129-130
- **現在のコード**:
  ```python
  clone_url=data.get("httpUrl", ""),
  url=data.get("httpUrl", ""),   # ← clone URL と同一
  ```
- **説明**: `Repository.url` は他のアダプターではリポジトリの **web ページ URL** を設定する（GitHub: `html_url`、GitLab: `web_url`、Azure DevOps: `webUrl`）。Backlog の `httpUrl` は HTTPS clone URL（例: `https://host/git/PROJ/repo.git`）であり、web URL とは異なる。Backlog の web URL は clone URL から `.git` サフィックスを除いた形式（`https://host/git/PROJ/repo`）。
- **推奨修正**:
  ```python
  clone_url=data.get("httpUrl", ""),
  url=data.get("httpUrl", "").removesuffix(".git"),
  ```

---

### [R38-04] 🟢 `git_util.py` L130 — git clone 失敗時に `stderr` が空だとエラーメッセージが空

- **ファイル**: `src/gfo/git_util.py` L130
- **現在のコード**:
  ```python
  raise GitCommandError(_mask_credentials(result.stderr.strip()))
  ```
- **説明**: `result.stderr` が空文字列の場合（git が stdout にのみ出力するケース等）、`GitCommandError("")` が送出されてユーザーにメッセージが表示されない。returncode を含めた情報を提供すべき。
- **推奨修正**:
  ```python
  raw = result.stderr.strip() or result.stdout.strip() or f"exited with code {result.returncode}"
  raise GitCommandError(_mask_credentials(raw))
  ```

---

### [R38-05] 🟢 `detect.py` L204 — `import requests` が冗長（モジュールレベルで既に import 済み）

- **ファイル**: `src/gfo/detect.py` L11, L204
- **現在のコード**:
  ```python
  # L11（モジュールレベル）
  import requests

  # L204（probe_unknown_host 内）
  def probe_unknown_host(host: str, scheme: str = "https") -> str | None:
      import requests   # ← 冗長
  ```
- **説明**: モジュールレベルで既に `import requests` が行われている（L11）。関数内の `import requests` は冗長。
- **推奨修正**: L204 の `import requests` を削除する。

---

### [R38-06] 🟢 `backlog.py` L101 — `except` に不要な `AttributeError` が含まれる

- **ファイル**: `src/gfo/adapter/backlog.py` L100-103
- **現在のコード**:
  ```python
  try:
      number = int(issue_key.split("-")[-1]) if isinstance(issue_key, str) else data["id"]
  except (ValueError, AttributeError):
      number = data["id"]
  ```
- **説明**: `isinstance(issue_key, str)` チェック済みのため、`issue_key.split("-")` で `AttributeError` は発生しない。`ValueError` のみ捕捉すれば十分。
- **推奨修正**:
  ```python
  except ValueError:
      number = data["id"]
  ```

---

### [R38-07] 🟢 テスト — R38-01〜06 の修正確認テストなし

- **ファイル**: `tests/test_detect.py`, `tests/test_git_util.py`
- **説明**:
  - R38-01: `detect.py` L196 のマスク確認テスト
  - R38-02: `list_issues(limit=0)` が `$top=20000` を WIQL に渡すことのテスト
  - R38-04: git clone 失敗時に stderr が空でも意味あるエラーになるテスト
- **推奨修正**: R38-01〜06 修正後に対応テストを追加する。

---

## 全問題サマリー（R38）

| ID | 重大度 | ファイル | 概要 | 状態 |
|----|--------|---------|------|------|
| **R38-01** | 🟡 中 | `detect.py` L196 | エラーメッセージで `path` 未マスク | ✅ 修正済み |
| **R38-02** | 🟡 中 | `azure_devops.py` L199 | `limit=0` 時 WIQL `$top` 未指定で200件制限 | ✅ 修正済み |
| **R38-03** | 🟢 軽微 | `backlog.py` L130 | `Repository.url` が clone URL と同一 | ✅ 修正済み |
| **R38-04** | 🟢 軽微 | `git_util.py` L130 | stderr 空時のエラーメッセージが空 | ✅ 修正済み |
| **R38-05** | 🟢 軽微 | `detect.py` L204 | `import requests` 冗長 | ✅ 修正済み |
| **R38-06** | 🟢 軽微 | `backlog.py` L101 | `AttributeError` 捕捉が冗長 | ✅ 修正済み |
| **R38-07** | 🟢 軽微 | テスト各種 | R38-01〜06 の修正確認テストなし | ✅ 修正済み |

---

## 推奨アクション（優先度順）

1. ~~**[R38-01]**~~ ✅ 修正済み
2. ~~**[R38-02]**~~ ✅ 修正済み
3. ~~**[R38-03]**~~ ✅ 修正済み
4. ~~**[R38-04]**~~ ✅ 修正済み
5. ~~**[R38-05]**~~ ✅ 修正済み
6. ~~**[R38-06]**~~ ✅ 修正済み
7. ~~**[R38-07]**~~ ✅ 修正済み

## 修正コミット（R38）

| コミット | 修正内容 |
|---------|---------|
| （次のコミット） | R38-01〜07 — detect/azure/backlog/git_util 修正・テスト追加 |
