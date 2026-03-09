# gfo Review Report — Round 27: gitea / gogs / base / auth_cmd 精査

## 概要

- **レビュー日**: 2026-03-09
- **対象**:
  - `src/gfo/adapter/gitea.py`
  - `src/gfo/adapter/gogs.py`
  - `src/gfo/adapter/forgejo.py`
  - `src/gfo/adapter/gitbucket.py`
  - `src/gfo/adapter/base.py`
  - `src/gfo/commands/auth_cmd.py`
  - `tests/test_adapters/test_gitea.py`
  - `tests/test_adapters/test_gogs.py`
  - `tests/test_commands/test_init.py`
  - `tests/test_commands/test_auth_cmd.py`

- **発見事項**: 新規 10 件（重大 1 / 中 4 / 軽微 5）

---

## 修正済み・問題なし確認（OK）

| 確認項目 | 結果 |
|---------|------|
| `auth_cmd.py` `handle_login` の `AuthError` 未処理 | OK — `AuthError` は `GfoError` のサブクラスのため、CLI の `except GfoError` ハンドラで適切に処理される |
| `auth_cmd.py` 空トークン検証 | OK — `handle_login` は `save_token` に委譲し、`save_token` 側で検証する設計。正しい分離 |

---

## 新規発見事項

---

### [R27-01] 🔴 `adapter/gitea.py` — `list_issues` フィルタ後 limit 未満問題（R13-03 継続）

- **ファイル**: `src/gfo/adapter/gitea.py` L71-84
- **説明**: `paginate_link_header` で `limit` 個取得後、PR を除外するフィルタを適用するため、返却件数が `limit` 未満になる場合がある。GitHub も同様。この設計は API 仕様（Gitea は issue/PR を区別する専用パラメータがない）によるトレードオフで、完全な修正は難しい。
- **影響**: ユーザーが指定した `limit` 個のイシューが取得できない場合がある。
- **現状**: 既知課題 R13-03 の継続。設計上の制約として文書化することを推奨。

---

### [R27-02] 🟡 `adapter/gitea.py` L155-159 — `list_labels` の `limit` 未指定でデフォルト 30 件上限

- **ファイル**: `src/gfo/adapter/gitea.py` L155-159
- **現在のコード**:
  ```python
  def list_labels(self) -> list[Label]:
      results = paginate_link_header(
          self._client, f"{self._repos_path()}/labels", per_page_key="limit",
      )
  ```
- **説明**: `paginate_link_header` の `limit` パラメータが指定されておらず、デフォルト 30 件で上限が設定される。ラベルが 30 件以上あるリポジトリでは全件取得できない。
- **影響**: 30 件超のラベルを持つリポジトリで結果が切り詰められる。
- **推奨修正**: `limit=0`（無制限）を指定してすべてのラベルを取得する。

---

### [R27-03] 🟡 `adapter/gitea.py` L173-177 — `list_milestones` も同様

- **ファイル**: `src/gfo/adapter/gitea.py` L173-177
- **説明**: R27-02 と同様。マイルストーンが 30 件以上のリポジトリで全件取得できない。
- **推奨修正**: `limit=0` を指定する。

---

### [R27-04] 🟡 `tests/test_commands/test_auth_cmd.py` L99-107 — テストコメントが実装と矛盾

- **ファイル**: `tests/test_commands/test_auth_cmd.py` L99-107
- **現在のコード**:
  ```python
  def test_empty_token_from_getpass_saved(self):
      """getpass が空文字を返した場合、空トークンで save_token が呼ばれる。"""
  ```
- **説明**: テストは `save_token` をモックしているため実際の動作をテストしていない。コメントは「空トークンで save_token が呼ばれる」と説明するが、実際の `save_token()` は空トークンで `AuthError` を送出する。コメントが誤解を招く。
- **影響**: メンテナー誤解リスク。実際の動作はテストされていない。
- **推奨修正**: テスト名とコメントを「handle_login は save_token にトークン検証を委譲する（空文字チェックは save_token 側）」と改名して意図を明確化。

---

### [R27-05] 🟢 `adapter/base.py` L25-34 — `Issue` dataclass に `updated_at` フィールドがない

- **ファイル**: `src/gfo/adapter/base.py` L25-34
- **説明**: `PullRequest` や `Release` には `updated_at` フィールドがあるが、`Issue` には `updated_at` がない。GitHub API 等は issue の更新日時を返すが、現在は取得できない。
- **影響**: Issue の更新日時情報が利用できない。
- **推奨修正**: `Issue` dataclass に `updated_at: str | None = None` を追加（既存コードとの後方互換性を保つ）。

---

### [R27-06] 🟢 `adapter/gogs.py` L20-23 — `_web_url` のポート 0 の扱い

- **ファイル**: `src/gfo/adapter/gogs.py` L20-23
- **説明**: `if parsed.port` は port が 0 の場合も False になり、ポート省略と同じ扱いになる。port=0 は無効な URL なので実用上影響はない。
- **推奨修正**: `if parsed.port is not None` に変更（防御的コーディング）。

---

### [R27-07] 🟢 `tests/test_adapters/test_gitea.py` — `list_pull_requests(state="merged")` の limit=0 テストなし

- **ファイル**: `tests/test_adapters/test_gitea.py`
- **説明**: `merged` フィルタリング後の件数が limit 未満になるケースのテストがない。R13-03 関連。
- **推奨修正**: 低優先度。R27-01 の設計決定後に追加。

---

### [R27-08] 🟢 `adapter/base.py` — `get_pr_checkout_refspec` の GogsAdapter 向け非明示的動作

- **ファイル**: `src/gfo/adapter/base.py` / `src/gfo/adapter/gogs.py`
- **説明**: `GogsAdapter` は `get_pr_checkout_refspec` をオーバーライドしておらず、基底クラスの `NotSupportedError` 送出実装を継承する。動作的に問題はないが、Gogs がこのメソッドをサポートしないことが明示されていない。
- **影響**: 軽微。動作は正しい。

---

### [R27-09] 🟢 `tests/test_adapters/test_gogs.py` — PR/release での `limit=0` テスト不足

- **ファイル**: `tests/test_adapters/test_gogs.py`
- **説明**: `list_issues` の `limit=0`（全件取得）テストは存在するが、`list_pull_requests` 等で同様のテストがない。
- **影響**: 軽微。

---

### [R27-10] 🟡 `adapter/gitea.py` / `tests/test_adapters/test_gitea.py` — `list_labels`/`list_milestones` に対するテストでの limit=0 の動作確認不足

- **ファイル**: `tests/test_adapters/test_gitea.py`
- **説明**: R27-02/03 の修正（`limit=0` への変更）に対応したテストが必要。
- **推奨修正**: R27-02/03 修正後にテストを追加。

---

## 全問題サマリー（R27）

| ID | 重大度 | ファイル | 概要 | 状態 |
|----|--------|---------|------|------|
| **R27-01** | 🔴 重大 | `gitea.py` | `list_issues` フィルタ後 limit 未満（R13-03 継続） | 設計制約として継続 |
| **R27-02** | 🟡 中 | `gitea.py` L155 | `list_labels` の limit 未指定（30 件上限） | ✅ 修正済み |
| **R27-03** | 🟡 中 | `gitea.py` L173 | `list_milestones` の limit 未指定（30 件上限） | ✅ 修正済み |
| **R27-04** | 🟡 中 | `test_auth_cmd.py` L99 | テストコメントが実装と矛盾 | ✅ 修正済み |
| **R27-05** | 🟢 軽微 | `base.py` | `Issue` に `updated_at` フィールドなし | ✅ 修正済み |
| **R27-06** | 🟢 軽微 | `gogs.py` L23 | `_web_url` のポート 0 扱い | ✅ 修正済み |
| **R27-07** | 🟢 軽微 | `test_gitea.py` | merged limit=0 テストなし | 保留 |
| **R27-08** | 🟢 軽微 | `base.py`/`gogs.py` | `get_pr_checkout_refspec` の非明示的継承 | 許容 |
| **R27-09** | 🟢 軽微 | `test_gogs.py` | PR/release の limit=0 テスト不足 | 保留 |
| **R27-10** | 🟡 中 | `test_gitea.py` | `list_labels`/`list_milestones` の limit=0 テスト不足 | ✅ 修正済み |
| R13-03 | 🟡 中 | `gitea.py` | フィルタ後 limit 未満（継続） | 設計制約として継続 |

---

## 推奨アクション（優先度順）

1. ~~**[R27-02]**~~ ✅ 修正済み
2. ~~**[R27-03]**~~ ✅ 修正済み
3. ~~**[R27-04]**~~ ✅ 修正済み
4. ~~**[R27-05]**~~ ✅ 修正済み
5. ~~**[R27-06]**~~ ✅ 修正済み
6. ~~**[R27-10]**~~ ✅ 修正済み
7. **[R27-07/09]** テストカバレッジ追加（低優先度・保留）

## 修正コミット（R27）

| コミット | 修正内容 |
|---------|---------|
| `f0f74f3` | R27-02/03/04/05/06/10 — gitea labels/milestones 全件取得・Issue updated_at・gogs port 修正・テスト追加 |
