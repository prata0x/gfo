# gfo Review Report — Round 18: GitBucket / Azure DevOps / auth_cmd / output 品質

## 概要
- レビュー日: 2026-03-09
- 対象: `adapter/gitbucket.py`, `adapter/azure_devops.py`, `commands/release.py`, `commands/auth_cmd.py`, `output.py`, `tests/test_azure_devops.py`
- 既知修正済み課題の確認 + 新規発見 5 件（軽微 5）

---

## 修正済み課題の確認

| ID | ファイル | 確認内容 | 状態 |
|----|---------|---------|------|
| R12-03 | `azure_devops.py` L73-74 | `repository.webUrl` + `pullRequestId` から web URL を構築。フォールバックあり | ✅ 修正完了 |
| R12-05 | `azure_devops.py` L198 | `params={"$top": limit}` — `min(limit, 200)` キャップなし | ✅ 修正完了 |
| R9-06 | `output.py` L91 | `data = dicts` — 常に配列を返す | ✅ 修正完了 |

---

## 新規発見事項

---

### [R18-01] 🟢 `adapter/gitbucket.py` — API 互換性のコメント欠落

- **ファイル**: `src/gfo/adapter/gitbucket.py`
- **現在のコード**:
  ```python
  """GitBucket アダプター。GitHubAdapter を継承し、service_name のみオーバーライドする。"""
  @register("gitbucket")
  class GitBucketAdapter(GitHubAdapter):
      service_name = "GitBucket"
  ```
- **説明**: GitBucket は GitHub API v3 互換だが、完全互換ではない（ラベル色フォーマット、一部エンドポイントの差異）。現在の実装はコメントがなく、今後の開発者が GitBucket 固有の差異を調べる手がかりがない。
- **推奨修正**: クラス docstring に互換性注記を追加。

---

### [R18-02] 🟢 `tests/test_azure_devops.py` L327 — WIQL `$top` パラメータ値の検証なし

- **ファイル**: `tests/test_adapters/test_azure_devops.py` L314-327
- **説明**: `list_issues()` は `$top=limit` を WIQL クエリに渡すが（R12-05 修正済み）、テストでは `$top` の値を検証していない。R12-05 の修正が正しく機能しているか自動検証できない。
  ```python
  # 現在のテスト
  wiql_body = json.loads(mock_responses.calls[0].request.body)
  assert "NOT IN ('Closed', 'Done', 'Removed')" in wiql_body["query"]
  # ← $top パラメータ検証なし
  ```
- **推奨修正**: WIQL リクエストのクエリパラメータを検証するテストを追加。
  ```python
  from urllib.parse import parse_qs, urlparse
  qs = parse_qs(urlparse(mock_responses.calls[0].request.url).query)
  assert qs.get("$top") == ["30"]  # デフォルト limit=30
  ```

---

### [R18-03] 🟢 `commands/release.py` L22 — エラーメッセージが不親切

- **ファイル**: `src/gfo/commands/release.py` L22
- **現在のコード**:
  ```python
  raise ConfigError("tag must not be empty.")
  ```
- **説明**: `--tag` を省略した場合に表示されるエラーメッセージが簡素すぎる。ユーザーが修正方法を即座に判断できない。
- **推奨修正**:
  ```python
  raise ConfigError("--tag is required. Use --tag <tag> to specify a release tag.")
  ```

---

### [R18-04] 🟢 `commands/auth_cmd.py` L50-52 — 列幅の上限制限なし

- **ファイル**: `src/gfo/commands/auth_cmd.py` L45-52
- **説明**: `handle_status()` の列幅が各エントリの文字列長の最大値で決まる。`get_auth_status()` が長い host 名や source 名を返した場合（例: 長い環境変数名）、表示幅が端末を超える可能性がある。
- **影響**: 軽微。通常の使用では端末幅を超えないが、長い環境変数名（`VERY_LONG_ENV_VAR_NAME_FOR_GITLAB_TOKEN` など）で崩れる。
- **推奨修正**: 各列の上限を設定する。
  ```python
  col_widths["host"] = min(max(col_widths["host"], 4), 50)
  col_widths["source"] = min(max(col_widths["source"], 6), 40)
  ```

---

### [R18-05] 🟢 `tests/test_azure_devops.py` — PR URL 生成テストが `repository.webUrl` パターンのみ

- **ファイル**: `tests/test_adapters/test_azure_devops.py`
- **説明**: R12-03 の修正で `repository.webUrl` が存在しない場合のフォールバックも実装されているが（`data.get("url", "")`）、フォールバックパターン（`repository` が存在しない / `webUrl` が空）のテストがない。修正済みのフォールバックロジックが検証されていない。
- **推奨修正**: フォールバック時のテストを追加。

---

## 全問題サマリー（R18）

| ID | 重大度 | ファイル | 概要 |
|----|--------|---------|------|
| **R18-01** | 🟢 軽微 | `adapter/gitbucket.py` | API 互換性コメント欠落 |
| **R18-02** | 🟢 軽微 | `test_azure_devops.py` | WIQL `$top` パラメータ値を検証していない |
| **R18-03** | 🟢 軽微 | `commands/release.py` L22 | エラーメッセージが不親切 |
| **R18-04** | 🟢 軽微 | `commands/auth_cmd.py` L50 | 列幅の上限制限なし |
| **R18-05** | 🟢 軽微 | `test_azure_devops.py` | PR URL フォールバックテストなし |
| R16-02 | 🟡 中 | `auth.py` L117 | host 形式混在（継続） |

---

## 推奨アクション

1. **[R18-03]** `commands/release.py` L22 — エラーメッセージを `"--tag is required. Use --tag <tag>."` に変更（1行）
2. **[R18-01]** `adapter/gitbucket.py` — API 互換性コメント追加（2〜3行）
3. **[R18-02]** `test_azure_devops.py` — `$top` パラメータ値の検証を `test_open` に追加
4. **[R18-04]** `commands/auth_cmd.py` — 列幅上限を追加
5. **[R18-05]** `test_azure_devops.py` — PR URL フォールバックテスト追加
