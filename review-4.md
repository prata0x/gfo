# コードレビュー: Phase 1-6 (0e2d591..HEAD)

**対象**: 12コミット、76ファイル、+13,239行
**レビュー日**: 2026-03-18

---

## 総合サマリー

| 重要度 | アダプター層 | コマンド層 | テスト品質 | 横断的品質 | ドキュメント | **合計** |
|--------|-------------|-----------|-----------|-----------|-------------|---------|
| Critical | 1 | 1 | 1 | 3 | 4 | **10** |
| Warning | 10 | 12 | 7 | 12 | 6 | **47** |
| Info | 8 | 7 | 9 | 7 | 3 | **34** |

**全体評価**: アダプター層の設計は堅実であり、9サービスに対する統一インターフェース提供という目的を十分に達成している。主なリスクはファイル I/O 周りのセキュリティとドキュメント-実装間の不整合に集中。

---

## 最優先で対応すべき項目 (Critical)

### SEC-01: `download_release_asset` のパストラバーサル脆弱性
- **ファイル**: `src/gfo/adapter/github.py` L399-404, `src/gfo/adapter/gitea.py` L390-396, `src/gfo/adapter/gitlab.py`
- API レスポンスの `asset_name` をそのまま `os.path.join(output_dir, asset_name)` に使用。悪意あるアセット名（例: `../../.bashrc`）で任意の場所に書き込み可能。
- **修正**: `os.path.basename(asset_name)` でサニタイズし、結果パスが `output_dir` 内にあることを検証する。

### SEC-02: GitLab `migrate_repository` のトークン URL 埋め込み
- GitLab の `migrate_repository` で `auth_token` を URL に直接埋め込み（`://oauth2:{auth_token}@`）。API ログやエラーレスポンスでトークン漏洩リスク。
- **修正**: エラー時のマスク処理を追加。

### SEC-03: `upload_file` / `upload_multipart` のリトライ時ファイル内容消失
- **ファイル**: `src/gfo/http.py` L155-199
- `_retry_loop` 内のラムダクロージャで `f.read()` を呼ぶが、リトライ時にファイルポインタが末尾のまま。リトライ時に空データが送信される。
- **修正**: リトライ前に `f.seek(0)` を追加、または毎回ファイルを再度開く。

### ADAPTER-01: GitLab `upload_release_asset` が HttpClient の内部 API に直接依存
- **ファイル**: `src/gfo/adapter/gitlab.py`
- `self._client._retry_loop` と `self._client._session.post` を直接呼び出し。カプセル化違反。
- **修正**: HttpClient に `upload_multipart_gitlab` 等のパブリックメソッドを追加。

### TEST-01: GitHub `pin_issue`/`unpin_issue` の REST API が公式に存在しない可能性
- **ファイル**: `src/gfo/adapter/github.py` L1582-1586, `tests/test_adapters/test_github.py`
- GitHub REST API v3 に `/repos/{owner}/{repo}/issues/{number}/pin` は未公開。GraphQL API でのみ対応。テストはモックで通るが実 API では 404 になる可能性が高い。
- **修正**: GraphQL 対応に変更するか、制限をドキュメントに明記。

### DOC-01: `gfo package view`/`gfo package delete` の引数がドキュメントと実装で不一致
- **ファイル**: `docs/commands.md` L2134-2167, `docs/commands.ja.md` L2134-2167
- ドキュメント: `gfo package view NAME [--type TYPE] [--version VERSION]`
- 実装: `package_type` と `name` が位置引数、`version` も位置引数（必須）
- **修正**: ドキュメントを `gfo package view PACKAGE_TYPE NAME [--version VERSION]` に修正。

### DOC-02: `gfo label clone` の引数がドキュメントと実装で不一致
- **ファイル**: `docs/commands.md` L948, `docs/commands.ja.md` L948
- ドキュメント: `gfo label clone SOURCE_REPO [--host HOST] [--overwrite]`
- 実装: `--from SOURCE`（required=True）。`--host` は実装に存在しない。
- **修正**: ドキュメントを `gfo label clone --from SOURCE [--overwrite]` に修正。

### DOC-03: Review の対応サービスが実装と不一致
- **ファイル**: `docs/commands.md` L1105, `docs/commands.ja.md` L1105
- ドキュメント: `GitHub, GitLab` のみ
- 実装: Gitea, Forgejo, Azure DevOps, Bitbucket (approve only) も対応済み
- **修正**: 対応サービスを更新。

### DOC-04: README Feature Support Matrix で Review の Gitea/Forgejo が誤って x
- **ファイル**: `README.md` L181, `README.ja.md` L181
- Gitea/Forgejo は `list_reviews`/`create_review` を完全実装済みだが x と記載。
- **修正**: Review 行を `○` に更新。

---

## アダプター層レビュー

### [Warning] GitLab `_to_webhook` の `active` フィールド誤用
- **ファイル**: `src/gfo/adapter/gitlab.py`
- `active=data.get("enable_ssl_verification", True)` — SSL 検証と Webhook のアクティブ状態は異なる概念。
- **修正**: `active=True` に固定するか適切なフィールドを使用。

### [Warning] Bitbucket `delete_file` がファイル内容を空にするだけの可能性
- **ファイル**: `src/gfo/adapter/bitbucket.py` L841-844
- `data = {path: "", "message": message}` は内容を空にする操作であり、ファイル削除にならない可能性。
- **修正**: Bitbucket src API の `files` パラメータを使用してファイル削除する方式に変更。

### [Warning] Backlog 静的メソッド内の冗長なローカルインポート
- **ファイル**: `src/gfo/adapter/backlog.py` L413, L431, L444
- ファイル先頭で既に `from gfo.exceptions import GfoError` をインポート済みなのに、静的メソッド内で再度インポート。
- **修正**: ローカルインポートを削除。

### [Warning] 型アノテーション欠落
- GitLab/Bitbucket の `update_repository`, `archive_repository`, `get_languages` 等のオーバーライド実装で戻り値型が省略。
- Gogs `create_branch` に戻り値型 `-> Branch` がない。
- Backlog `add_time_entry` にパラメータ型がない。

### [Warning] Bitbucket Webhook `id` の型不整合
- **ファイル**: `src/gfo/adapter/bitbucket.py` L438
- `Webhook.id` は `int` 型だが、Bitbucket は UUID 文字列を返す。`delete_webhook(hook_id: int)` と不整合。

### [Warning] Azure DevOps -- Wiki/Variable API が未実装（暗黙的フォールバック）
- Azure DevOps Wiki API や Variable Groups API は利用可能だが NotSupportedError にフォールバック。今後の実装候補として認識。

---

## コマンド層レビュー

### [Warning] `repo.py` がアダプターのプライベート属性 `_owner`, `_repo` に直接アクセス
- **ファイル**: `src/gfo/commands/repo.py` L179, L214, L330, L357, L366
- **修正**: `GitServiceAdapter` に `owner` / `repo` プロパティを追加。

### [Warning] `api.py` で不正 JSON の `json.JSONDecodeError` が未処理
- **ファイル**: `src/gfo/commands/api.py` L39
- ユーザーが不正 JSON を `--data` に渡すとスタックトレースが表示される。
- **修正**: try/except で `ConfigError` に変換。

### [Warning] `ci.py` の i18n 漏れ
- **ファイル**: `src/gfo/commands/ci.py` L40
- `raise ConfigError(f"Invalid input format: ...")` で `_()` 未使用。プロジェクト全体で唯一の例外。

### [Warning] `schema.py` のエラーメッセージが全て i18n 非対応
- **ファイル**: `src/gfo/commands/schema.py` L399, L507, L516, L523, L526

### [Warning] ほとんどのサブパーサーに help テキストがない
- **ファイル**: `src/gfo/cli.py` 多数箇所
- Phase 1-3 で追加されたコマンドに `help=` が指定されていない。Phase 4 以降で追加されたものには付いている。

### [Warning] 確認プロンプトのパターンが5箇所で重複
- **ファイル**: `src/gfo/commands/repo.py` L180-188, L215-223, L331-339; `org.py` L64-72; `package.py` L36-44
- **修正**: 共通ヘルパー関数 `confirm_action()` を用意。

### [Warning] `label.py` `handle_clone` のアダプター生成コードが `create_adapter_from_spec` と重複
- **ファイル**: `src/gfo/commands/label.py` L80-107

### [Warning] `_DISPATCH` と `_OUTPUT_MAP` の不整合リスク
- 新コマンド追加時に一方への追加を忘れるリスク。テストで両者のキー一致を検証すべき。

### [Warning] `batch.py` の広い例外キャッチ (`except Exception`)
- **ファイル**: `src/gfo/commands/batch.py` L62
- **修正**: `except (GfoError, requests.RequestException)` に限定。

### [Warning] `org.py` / `repo.py` の独自出力パターン
- `handle_members`, `handle_languages`, `handle_topics` が `output()` を使わず独自に JSON 出力。
- **修正**: `output()` を dict/list[str] 対応に拡張。

### [Info] `create_parser()` が 740 行超の巨大関数
- 各コマンドモジュールに `register_parser()` を持たせるリファクタリングを検討。

### [Info] ci/tag-protect/ssh-key/gpg-key の `id` 引数に `type` 指定の不統一
- 一部は `type=int`、一部は指定なし。サービスごとの ID 型が異なるため文字列統一を検討。

---

## テスト品質レビュー

**テスト実行結果**: 2611 passed, 1 skipped (全テストグリーン)

### [Warning] JSON 出力テスト・エラー伝搬テストの欠落 (テスト規約違反)
以下のコマンドテストに `fmt="json"` テストとエラー伝搬テストがない:
- `tests/test_commands/test_package.py`
- `tests/test_commands/test_wiki.py` (TestHandleRevisions)
- `tests/test_commands/test_search.py` (TestHandlePrs, TestHandleCommits)
- `tests/test_commands/test_review.py` (TestHandleDismiss)

### [Warning] Backlog/GitBucket 向け Phase 2-5 新機能の NotSupportedError テスト不足
- PR 拡張機能（diff/checks/files/commits）の NotSupportedError テストが GPG key/tag protect と同レベルで網羅されていない。

### [Warning] `test_ci.py` -- `ref=""` ケースのテストなし
### [Warning] `test_gpg_key.py` / `test_tag_protect.py` -- 422 validation error テストなし

### [Info] 良好なテスト設計
- `test_service_spec.py` -- 20近いエラーパターンを網羅（非常に良好）
- `test_issue_migrate.py` -- 部分的失敗、空 assignee 等のエッジケースを網羅（良好）
- `test_batch.py` -- dry-run、空 repos、部分的失敗を網羅（良好）
- テスト間依存なし、フィクスチャ/ヘルパーの活用も適切

---

## 横断的品質レビュー

### [Warning] 広範な `except Exception` によるエラー抑制
- `github.py` `list_issue_templates` -- `except Exception: return []`
- `gitlab.py` `list_issue_templates` -- `except Exception: return []`
- `gitea.py` `list_issue_templates` -- `except Exception: return []`
- 認証エラーでも空リストが返される。
- **修正**: `except (NotFoundError, NotSupportedError)` に限定。

### [Warning] `GfoError` 直接使用（例外体系の逸脱）
- `github.py` L685, `gitea.py` L923: `raise GfoError(...)` → `ConfigError` が適切。

### [Warning] DRY 違反: `_to_gpg_key` が3アダプターで重複
- GitHub/Gitea/GitLab で同一コード。`GitHubLikeAdapter` に共通化すべき。

### [Warning] DRY 違反: リリースアセット操作の重複パターン
- GitHub/Gitea 間で `list_release_assets`, `download_release_asset`, `delete_release_asset` がほぼ同一。

### [Warning] N+1 API 呼び出し: `get_pipeline_logs`
- 全サービスの `get_pipeline_logs` で各ジョブに対して個別 API 呼び出し。ジョブ数が多い場合にレートリミットリスク。

### [Warning] `issue migrate --all` で全 Issue を一括メモリロード
- `limit=0` で全件取得後、各 Issue を再取得（N+2問題）。

---

## ドキュメント整合性レビュー

### [Warning] 未記載オプション
| コマンド | 未記載オプション |
|---------|---------------|
| `gfo search prs` | `--state {open,closed,merged,all}` |
| `gfo search commits` | `--author`, `--since`, `--until` |
| `gfo repo transfer` | `--team-id ID` |
| `gfo repo mirror add` | `--auth-token TOKEN` |

### [Warning] `gfo repo mirror sync` にドキュメント上の `MIRROR_ID` 引数が実装に存在しない
- ドキュメント: `gfo repo mirror sync [MIRROR_ID]`
- 実装: 引数なし

### [Warning] `gfo ci` の対応サービス記載漏れ
- ドキュメント: `GitHub, GitLab, Gitea, Forgejo`
- 実装: Bitbucket, Azure DevOps も対応済み

### [Info] ロードマップのステータスは全て整合
- 全55項目が完了マーク、実装コードと対応済み。

### [Info] README.md / README.ja.md / commands.md / commands.ja.md の日英整合は問題なし

---

## 改善優先度

### P0 (セキュリティ・即対応)
1. `download_release_asset` のパストラバーサル対策
2. `upload_file` / `upload_multipart` のリトライ対応
3. GitLab `migrate_repository` のトークンマスク処理

### P1 (ドキュメント不整合・ユーザー影響大)
4. `gfo package view/delete` のドキュメント修正
5. `gfo label clone` のドキュメント修正
6. Review の対応サービス表・Feature Matrix 修正
7. 未記載オプションの追加（search, repo transfer, repo mirror）

### P2 (コード品質)
8. `api.py` の JSON パースエラー処理
9. `except Exception` の限定化
10. `repo.py` のプライベート属性アクセス → プロパティ化
11. GitLab `upload_release_asset` のカプセル化違反修正
12. 確認プロンプトの共通化
13. テスト規約準拠（JSON/エラー伝搬テスト追加）

### P3 (リファクタリング)
14. `_to_gpg_key` / リリースアセット操作の DRY 化
15. `help=` テキストの統一追加
16. `output()` の dict/list[str] 対応
17. `_DISPATCH` と `_OUTPUT_MAP` の一致検証テスト
