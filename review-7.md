# Review 7

## Findings

### 1. High: `download_release_asset` にパストラバーサル脆弱性

- 該当コード: `src/gfo/adapter/github.py` `download_release_asset`, `src/gfo/adapter/gitea.py` `download_release_asset`, `src/gfo/adapter/gitlab.py` `download_release_asset`
- API レスポンスの `name` フィールドをサニタイズせず `os.path.join(output_dir, asset_name)` に渡している。
- 悪意あるリリースアセット名（例: `../../.bashrc`）により、`output_dir` の外にファイルを書き込むパストラバーサル攻撃が成立する。
- GitHub:
  ```python
  asset_name = meta_resp.json().get("name", f"asset-{asset_id}")
  output_path = os.path.join(output_dir, asset_name)
  ```
- Gitea・GitLab も同一パターン。
- 修正案: `os.path.basename(asset_name)` でディレクトリ成分を除去し、さらに解決後パスが `output_dir` 配下であることを検証する。

### 2. High: `upload_file` のリトライ時にファイルポインタがリセットされない

- 該当コード: `src/gfo/http.py:168-178`
- `_retry_loop()` に渡すラムダ内で `f.read()` を呼び出しているため、429 リトライ時にファイルポインタが末尾のまま空データを POST する。
  ```python
  with open(file_path, "rb") as f:
      return self._retry_loop(
          lambda: self._session.post(
              url,
              params=merged_params,
              data=f.read(),  # ← 2回目以降は b"" を送信
              headers=upload_headers,
              timeout=timeout,
          )
      )
  ```
- 修正案: ラムダ内で `f.seek(0)` を呼び出す、またはリトライのたびにファイルを再度開く。

### 3. High: `ServiceSpec` に `slots=True` がない

- 該当コード: `src/gfo/commands/__init__.py:25`
- プロジェクト規約ではすべてのデータクラスに `frozen=True, slots=True` が必須だが、`ServiceSpec` は `@dataclass(frozen=True)` のみで `slots=True` が欠落している。
  ```python
  @dataclass(frozen=True)
  class ServiceSpec:
  ```
- `BatchPrResult`（`batch.py:14`）と `MigrateResult`（`issue.py:20`）は正しく `frozen=True, slots=True` が付与されている。

### 4. Medium: `pr merge/close/reopen/update-branch/ready` に成功メッセージがない

- 該当コード: `src/gfo/commands/pr.py:46-54, 55-59, 61-65, 129-133, 135-139`
- 規約「削除/書き込みハンドラは成功メッセージを `print()` すること」に違反。
- 同じコマンド体系の `issue delete`（`issue.py:94`）や `release delete`（`release.py:43-44`）は正しく成功メッセージを出力している。
- 該当ハンドラ一覧:
  - `handle_merge` — merge/auto-merge 完了後に出力なし
  - `handle_close` — close 完了後に出力なし
  - `handle_reopen` — reopen 完了後に出力なし
  - `handle_update_branch` — branch 更新完了後に出力なし
  - `handle_ready` — ready 状態変更後に出力なし

### 5. Medium: `issue close/reopen` にも成功メッセージがない

- 該当コード: `src/gfo/commands/issue.py:78-83, 84-89`
- `handle_close` と `handle_reopen` はアダプターを呼んだ後に何も出力しない。
- 対照的に `handle_delete`（`issue.py:94`）は `print(_("Deleted issue ...")` を出力している。

### 6. Medium: `issue reaction remove` / `issue depends add/remove` に成功メッセージがない

- 該当コード: `src/gfo/commands/issue.py:123, 131, 138`
- `handle_reaction` の `remove` アクション、`handle_depends` の `add`/`remove` アクションが書き込み操作後に成功メッセージを出力しない。

### 7. Medium: `pr reviewers add/remove` に成功メッセージがない

- 該当コード: `src/gfo/commands/pr.py:120-126`
- `reviewers add` と `reviewers remove` が操作後にフィードバックなし。

### 8. Medium: `ci trigger` のエラーメッセージが i18n 未対応

- 該当コード: `src/gfo/commands/ci.py:37`
- `ConfigError(f"Invalid input format: '{item}'. Expected KEY=VALUE.")` が `_()` で囲まれていない。
- 同ファイル内で `from gfo.i18n import _` がインポートされておらず、他のエラーメッセージとの一貫性がない。

### 9. Medium: `ssh_key_delete` と `gpg_key_delete` の CLI 引数に `type=int` がない

- 該当コード: `src/gfo/cli.py:724, 736`
  ```python
  ssh_key_delete.add_argument("id")       # type=int なし
  gpg_key_delete.add_argument("id")       # type=int なし
  ```
- 同種の他コマンド（`webhook_delete:454`, `deploy_key_delete:468`）では `type=int` が指定されている。
- アダプターのシグネチャは `key_id: int | str` なので動作はするが、一貫性を欠く。

### 10. Low: review-3 の指摘が未修正のまま残存

- 以下の review-3 指摘事項がすべて未修正:
  - **Issue migrate が closed issue を open で再作成する**（`issue.py:257-274`）: `create_issue()` 後に `issue.state == "closed"` であれば `dst.close_issue()` を呼ぶ処理がない。
  - **コメント移行が 30 件で切り捨てられる**（`issue.py:265`）: `src.list_comments("issue", number)` に `limit=0` が渡されていない。
  - **`parse_service_spec()` が GitLab サブグループに対応していない**（`__init__.py:147-156`）: `owner/repo` の 2 セグメント固定のまま。

### 11. Low: `api.py` の `json.loads()` に `JSONDecodeError` ハンドリングがない

- 該当コード: `src/gfo/commands/api.py:39`
  ```python
  json_data = json.loads(data) if data else None
  ```
- 不正な JSON 入力時にユーザーフレンドリーでない `json.JSONDecodeError` トレースバックが表示される。
- `ConfigError` でラップすべき。

---

## Validation

```
$ pytest -x --tb=short
2611 passed, 1 skipped, 2 warnings in 8.84s
```

全テストがパスしているため、上記の指摘は既存テストでカバーされていない振る舞いの問題である。
