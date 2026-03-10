# gfo コードレビュー 全体サマリー

## 概要

| 項目 | 内容 |
|------|------|
| レビュー期間 | R1〜R44（44ラウンド） |
| 対象コミット | `69c4d59`（review-01-tasks.md 追加）〜 `cc6bd29`（R44 修正完了） |
| 総コミット数 | 214 コミット |
| 変更ファイル数 | 104 ファイル |
| 変更行数 | +14,735 / −1,077 行 |
| 最終テスト数 | 1,016 テスト |
| 最終カバレッジ | 99%（`__main__.py` 4行のみ未カバー） |

---

## 変更カテゴリ別サマリー

### バグ修正（135 コミット）

#### コア・HTTP

| 修正内容 | コミット例 |
|---------|-----------|
| `paginate_link_header` の `next_url` 代入漏れ | R1-01 |
| `paginate` の `_session` 直接呼び出し → `get_absolute` に置換 | R1-11 |
| `paginate_page_param` の X-Next-Page 非整数値で ValueError 防止 | R3-07 |
| `paginate_top_skip/response_body` の非 dict レスポンス対応 | R3-12 |
| Link ヘッダーの `rel="Next"` 大文字小文字非感知マッチ | R3-14 |
| `limit` 負値ガードと `per_page/limit` 連動最適化 | R6-01/R6-22 |
| SSLError 等の `RequestException` サブクラスを `NetworkError` に統一 | R10 |
| `paginate_response_body` で非文字列 `next_url` の AttributeError 防止 | R44 前修正 |
| `paginate_*` 全メソッドで非 JSON レスポンスを安全に処理 | R44 前修正 |

#### 検出（detect.py）

| 修正内容 | コミット例 |
|---------|-----------|
| HTTP remote URL の scheme 判定デッドコード修正（`http` 固定） | R1-01 |
| `detect_service` git config ショートカットで host も上書き・不一致警告 | R1-08 |
| `probe_unknown_host` の Gitea/Forgejo/Gogs 判定精度改善 | R1-07 |
| SSH regex でハイフン入りユーザー名に対応 | R6-09 |
| HTTPS URL の userinfo をホスト抽出前にスキップ | R44 前修正 |
| ホスト名の大文字小文字正規化（`lower()`）を全箇所に適用 | R7/R10 |
| `_BACKLOG_PATH_RE` と `_GITBUCKET_PATH_RE` の重複正規表現を統合 | R7-22 |
| `_GITBUCKET_PATH_RE` dead alias を削除 | R43 |

#### 設定・認証（config.py / auth.py）

| 修正内容 | コミット例 |
|---------|-----------|
| `load_user_config` の `PermissionError` を `ConfigError` に変換 | R6-20 |
| `resolve_project_config` の remote URL 解析を `try/except` で保護 | R1-04 |
| `resolve_project_config` の remote URL 失敗時に git config へフォールバック | R23-01 |
| `build_clone_url` バリデーション追加・ハードコードホストを引数化 | R23/R44 |
| `get_auth_status` の env var エントリの host 形式を統一し重複排除 | R7-20/R44-01 |
| `save_token()` の二重 falsy チェックを簡略化 | R44-02 |
| `build_default_api_url` エラーメッセージに `gfo init` 提案 | R7 |

#### 初期化（commands/init.py）

| 修正内容 | コミット例 |
|---------|-----------|
| 非対話 init で `detect_from_url` を先行呼び出しし organization を渡す | R1-05 |
| 対話 init で organization 未解決時のエラーを手動入力にフォールバック | R1-12 |
| 手動入力パスで Azure DevOps の organization を追加入力させる | R10 |
| non-interactive モードで URL 検出の `project_key` を `api_url` 構築に使用 | R44 前修正 |
| 対話モードで `detect_service` の `GitCommandError` を手動入力へフォールバック | R44 前修正 |
| `else` ブランチで 2 回目の `build_default_api_url` 失敗時のエラーメッセージ改善 | R44 前修正 |

#### CLI・コマンド共通

| 修正内容 | コミット例 |
|---------|-----------|
| argparse 内部 API `_subparsers._group_actions` の参照を排除 | R1-06 |
| `--limit` 引数に正数バリデーションを追加 | R3-01 |
| `issue/milestone/pr create` で空タイトルを拒否 | R3-02/03/13 |
| `init` 対話モードで空の `service_type/host` を拒否 | R3-15 |
| 予期しない例外を catch-all で捕捉してユーザー向けメッセージを表示 | R10 |
| `_positive_int` エラーメッセージを統一 | R29-01 |
| 入力値の `strip()` 処理を全コマンドで一貫化 | R31/R32 |
| `_resolve_host_without_repo` でホスト解決順序を修正 | R38 前修正 |
| git リポジトリ外で `GitCommandError` をデフォルトホストへフォールバック | R44 前修正 |

#### アダプター共通・基底クラス

| 修正内容 | コミット例 |
|---------|-----------|
| 全アダプター `_to_*` メソッドに `KeyError/TypeError` ラッピングを追加 | R3-05 |
| `null` フィールドで `AttributeError` が `try/except` を素通りするバグを修正 | R10 |
| `or {}` パターンの `AttributeError` を `_to_*` メソッド全体で捕捉 | R44 前修正 |
| 全アダプターの `_to_issue()` に `updated_at` を追加 | R37-01/02 |
| `list_labels/milestones` に `limit` 引数追加・`PullRequest.updated_at` デフォルト修正 | R36-01〜03 |
| `get_pr_checkout_refspec` に `refs/` プレフィックスを追加 | R44 前修正 |
| 非 ASCII `owner/repo` の URL エンコーディング対応 | R6-14 |
| `get_repository` に URL エンコードを追加（backlog/azure_devops/bitbucket） | R33-01〜03 |
| `list_repositories` の `owner` URL エンコード修正 | R41-01〜03 |
| `get_adapter` ヘルパーでコマンドハンドラの定型2行を集約 | R7-08 |

#### GitHub / GitHubLike

| 修正内容 | コミット例 |
|---------|-----------|
| `list_labels/list_milestones` をページネーション対応 | R2-23 |
| `_to_*` 変換メソッドの重複を `GitHubLikeAdapter` で解消 | R7-03 |

#### GitLab

| 修正内容 | コミット例 |
|---------|-----------|
| `_to_pull_request` に `"locked"` state マッピングを追加 | R2-05 |
| `merge_pull_request` の squash/rebase マッピングを GitLab API 仕様に修正 | R2-18 |
| `_to_release` の `draft` を `False` 固定に修正 | R2-09 |
| `list_repositories` の URL 構築を `params` ベースに変更 | R2-17 |
| `create_label` で color に `#` プレフィックスが含まれる場合の二重 `##` を防止 | R2-24 |
| `_to_issue` の冗長な no-op 代入を削除 | R2-19 |
| `merge_pull_request` 不正 method → `GfoError` | R10 |
| `_to_milestone` で GitLab の `state="active"` を `"open"` に変換 | R38 前修正 |
| `state=all` 時に無効な API パラメータを送らないよう修正 | R38 前修正 |
| rebase エンドポイント修正 | R26-01 |
| `limit=0` のバグ修正 | R30 |

#### Bitbucket

| 修正内容 | コミット例 |
|---------|-----------|
| `close_issue` の state 値を `"resolved"` に修正 | R2-02 |
| `_to_issue` の deleted user assignee で `KeyError` を防止 | R2-10 |
| `create_issue` で label を component に反映・`_to_issue` で `component→labels` 変換 | R11 |
| `list_issues(state="closed")` が resolved 状態を含まなかったバグを修正 | R44 前修正 |
| `list_issues` の `assignee` フィルタが無視されていた問題を修正 | R38 前修正 |
| `state=all` 時に無効な API パラメータを送らないよう修正 | R38 前修正 |
| `assignee` 空文字チェックを追加 | R26-02 |
| `close_pull_request` を正しい `/decline` エンドポイントに修正 | R44 前修正 |
| repository メソッドの URL エンコード修正 | R42-01/02 |
| `merge_method` 無視バグを修正 | R10 |

#### Backlog

| 修正内容 | コミット例 |
|---------|-----------|
| `create_issue` で `issue_type/priority` が None のとき `GfoError` を raise | R2-04 |
| `get_issue` を `issueKey` 形式（`PROJECT_KEY-N`）で取得 | R2-15 |
| `_to_pull_request` の `merged` 判定を動的 `status_id` 参照に変更 | R2-16 |
| `list_pull_requests` で `merged_id` を list に統一 | R10 |
| `_to_issue` の `issueKey` 末尾を int にキャスト | R1-03 |
| `create_issue` の `issueTypes/priorities` 応答を防御的に検証 | R12 |
| `_ensure_project_id` → `GfoError` | R10 |
| `_resolve_merged_status_id` の list 検証 + `KeyError` スキップ | R10 |
| `createdUser null` 時の `AttributeError` を修正 | R44 前修正 |
| Backlog のマジックナンバーをモジュール定数に置換 | R7-11 |

#### Azure DevOps

| 修正内容 | コミット例 |
|---------|-----------|
| WIQL クエリのシングルクォートをエスケープ | R2-12 |
| PR state 辞書参照を `.get()` で KeyError 対策 | R2-03 |
| WIQL インジェクション対策 — `_wiql_escape()` ヘルパー追加 | R4-01 |
| `list_issues` の WIQL/workitems レスポンスを防御的に検証 | R17 |
| `merge_pull_request` の `lastMergeSourceCommit` KeyError を修正 | R10 |
| `merge_pull_request` の非 dict レスポンス時 `AttributeError` を修正 | R44 前修正 |
| `defaultBranch` が null のとき `GfoError` になるバグを修正 | R44 |
| `list_issues` の `limit=0` バグ修正 | R25 |
| `_to_repository` を `@staticmethod` に変更 | R7-14 |
| `work_item_type` を URL エンコードするよう修正 | R38 前修正 |
| `list_repositories` が `owner` 指定を無言で無視していたバグを修正 | R10 |
| repo create クラッシュを修正 | R10 |
| `updated_at` を PR/Issue に追加 | R28 |

#### Gitea / Forgejo

| 修正内容 | コミット例 |
|---------|-----------|
| `list_issues` に `type=issues` パラメータを追加 | R2-07 |
| `merge_pull_request` を `PUT → POST` に修正 | R44 前修正 |
| `list_labels/milestones` の全件取得（ページネーション対応） | R27 |

#### Gogs

| 修正内容 | コミット例 |
|---------|-----------|
| `get_pr_checkout_refspec` を `NotSupportedError` でオーバーライド | R2-22 |
| 全メソッドに型ヒントを追加 | R7-05 |
| `web_url` URL エンコード | R34-01 |
| port 修正 | R27 |

#### GitBucket

| 修正内容 | コミット例 |
|---------|-----------|
| `label color` バグ修正 | R28 |

#### セキュリティ（R4 集中修正）

| 修正内容 | コミット例 |
|---------|-----------|
| WIQL インジェクション対策 | R4-01 |
| `http.py` セキュリティ強化（SSRF 対策等） | R4-02/03/07/09 |
| `git_util.py` エラーメッセージの認証情報マスク | R4-04 |
| `detect.py` セキュリティ強化 | R4-05/08/09/10 |
| Windows パーミッション堅牢化と TOML 制御文字エスケープ | R4-06/12 |

---

### テスト強化（29 コミット）

| 主要内容 | ラウンド |
|---------|---------|
| ForgejoAdapter テスト強化 | R-04 |
| GitBucketAdapter テスト強化 | R-05 |
| auth_cmd テスト強化 | R-06 |
| label_cmd テスト強化 | R-07 |
| milestone_cmd テスト強化 | R-08 |
| セキュリティ修正テスト追加（29件） | R5 |
| カバレッジ 99% まで引き上げ | R6（カバレッジ集中） |
| `get_adapter/get_default_branch` 残り分岐カバレッジ | R6後 |
| `http/detect` クロスオリジン・非dict・ValueError カバレッジ | R6後 |
| `save_token` 空/空白バリデーションテスト | R6後 |
| `auth/gogs/backlog` TOML エラー・icacls 非ゼロカバレッジ | R6後 |
| `gitlab` 3階層サブグループ `_project_path()` テスト | R6-08 |
| `config` shost 部分設定・PermissionError テスト | R6-13/20 |
| Bitbucket list_issues カスタム state フィルタ | R44 前 |
| output dead assignment 除去・テスト整理 | R43 |
| `format_json` else ブランチデッドコード除去 | R44 前 |

---

### リファクタリング（13 コミット）

| 主要内容 | ラウンド |
|---------|---------|
| `HttpClient` 生成ロジックを `create_http_client()` に共通化 | R-02 |
| `GitHubLikeAdapter` で `_to_*` 変換メソッドの重複を解消 | R7-03 |
| `get_adapter` ヘルパーでコマンドハンドラ定型2行を集約 | R7-08 |
| `handle_clone` の clone URL 構築を `build_clone_url` に集約 | R7-09 |
| プライベート関数を公開 API に変更 | R7-10/18 |
| `Backlog` マジックナンバーをモジュール定数に置換 | R7-11 |
| `AzureDevOpsAdapter._to_repository` を `@staticmethod` に変更 | R7-14 |
| `stype/shost` 省略変数名を `saved_type/saved_host` に変更 | R7-17 |
| `get_auth_status` の `seen_hosts` env var 追加・テスト helper 化 | R44 |
| `DetectResult` を `frozen=True` に変更し `dataclasses.replace()` を使用 | R7-04 |
| `_BACKLOG_PATH_RE` と `_GITBUCKET_PATH_RE` の重複正規表現を統合 | R7-22 |
| `_GITBUCKET_PATH_RE` dead alias を削除 | R43 |
| `output.py` dead assignment 除去 | R43 |

---

### ドキュメント（36 コミット）

- `docs/reviews/review-01-tasks.md` 〜 `review-44-auth-detect.md` の全44ファイル
- 各レビューの修正完了状態・修正コミット欄の更新
- `resolve_project_config` コメント誤り修正
- `create_adapter` の設計理由コメント追記
- `config.py ⇔ detect.py` 循環依存コメント追記

---

### インフラ（2 コミット）

| 内容 | コミット |
|------|---------|
| `pytest-cov` 導入・カバレッジ計測設定（`pyproject.toml` 更新） | `bfc9ed2` |
| `.gitignore` に coverage 関連ファイルを追加 | `fdec7c8` |

---

## 修正対象モジュール別サマリー

| モジュール | 主要修正内容 |
|-----------|------------|
| `detect.py` | scheme バグ・SSH 正規表現・ホスト名正規化・probe 精度向上 |
| `http.py` | paginate 全系統の堅牢化・SSLError 統一・limit 検証 |
| `config.py` | resolve_project_config 保護・build_clone_url 改善・PermissionError |
| `auth.py` | get_auth_status 重複排除・Windows パーミッション・TOML エスケープ |
| `commands/init.py` | Azure org 入力・フォールバック改善・non-interactive detect 修正 |
| `commands/` 共通 | strip 一貫化・空タイトル拒否・limit バリデーション・catch-all |
| `adapter/gitlab.py` | state マッピング・squash/rebase・create_label・URL 構築 |
| `adapter/bitbucket.py` | close_issue・label/component・state=all・URL エンコード |
| `adapter/backlog.py` | issueKey 形式・merged 動的判定・issueTypes 防御的検証 |
| `adapter/azure_devops.py` | WIQL インジェクション・KeyError 対策・limit=0・URL エンコード |
| `adapter/gitea.py` | list_issues type=issues・labels/milestones ページネーション |
| `adapter/gogs.py` | get_pr_checkout_refspec・URL エンコード・型ヒント |
| `adapter/base.py` | updated_at 追加・limit 引数・URL エンコード共通化 |

---

## レビューラウンド一覧

| ラウンド | テーマ | 主要修正件数 | 状態 |
|---------|-------|------------|------|
| **R-01〜09** | 初期レビュータスク（detect/http/refactor/test/infra） | 9 タスク | ✅ 完了 |
| **R1** | コアバグ修正（paginate・detect・init・backlog） | 13 件 | ✅ 完了 |
| **R2** | コアバグ（gitlab/bitbucket/backlog/azure/gogs） | 13 件 | ✅ 完了 |
| **R3** | アダプター精度（バリデーション・paginate・init） | 22 件 | ✅ 完了 |
| **R4** | 入力バリデーション（セキュリティ強化） | 20 件 | ✅ 完了 |
| **R5** | セキュリティ（WIQL・SSRF・認証情報マスク） | 12 件 | ✅ 完了 |
| **R6** | テストカバレッジ（output・git_util・config・http） | 22 件 | ✅ 完了 |
| **R7** | エッジケース（URL エンコード・refactor・ホスト正規化） | 26 件 | ✅ 完了 |
| **R8** | コード品質（型ヒント・定数・staticmethod・ヘルパー） | 23 件 | ✅ 完了 |
| **R9〜13** | フォローアップ（防御的コーディング・Bitbucket label） | 複数 | ✅ 完了 |
| **R14** | http/config/output 精査 | 9 件 | ✅ 完了 |
| **R15** | git_util/http/commands 精査 | 4 件 | ✅ 完了 |
| **R16** | http/config/auth 精査 | 4 件 | ✅ 完了 |
| **R17** | auth/adapters/tests 精査 | 3 件 | ✅ 完了 |
| **R18** | gitbucket/azure/auth/output 精査 | 4 件 | ✅ 完了 |
| **R19** | commands/cli/detect 精査 | 4 件 | ✅ 完了 |
| **R20** | gogs/forgejo/gitea/bitbucket/auth 精査 | — | ✅ 完了 |
| **R21** | gitlab/gitbucket/http/tests 精査 | 7 件 | ✅ 完了 |
| **R22** | github/backlog/azure-devops/auth 精査 | 複数 | ✅ 完了 |
| **R23** | exceptions/output/cli/config 精査 | 7 件 | ✅ 完了 |
| **R24** | auth/commands/detect/http 精査 | 10 件 | ✅ 完了 |
| **R25** | azure_devops/http/gitea/base 精査 | 8 件 | ✅ 完了 |
| **R26** | github/gitlab/bitbucket/backlog/http 精査 | 8 件 | ✅ 完了 |
| **R27** | gitea/gogs/base/auth/cmd 精査 | 複数 | ✅ 完了 |
| **R28** | forgejo/gitbucket/azure/commands 精査 | 6 件 | ✅ 完了 |
| **R29** | detect/config/cli/output/git_util 精査 | 5 件 | ✅ 完了 |
| **R30** | github/gitlab/backlog/http 精査 | 4 件 | ✅ 完了 |
| **R31** | commands/base/exceptions 精査 | 2 件 | ✅ 完了 |
| **R32** | commands strip 一貫性 精査 | 4 件 | ✅ 完了 |
| **R33** | backlog/bitbucket/azure URL エンコード精査 | 3 件 | ✅ 完了 |
| **R34** | gogs/git_util 精査 | 2 件 | ✅ 完了 |
| **R35** | auth/config/output 精査 | 3 件 | ✅ 完了 |
| **R36** | adapters/base/gitlab/github 精査 | 3 件 | ✅ 完了 |
| **R37** | issue updated_at 精査 | 2 件 | ✅ 完了 |
| **R38** | azure/backlog/detect/git_util 精査 | 7 件 | ✅ 完了 |
| **R39** | commands/repo/release 精査 | 3 件 | ✅ 完了 |
| **R40** | init/label/test 精査 | 3 件 | ✅ 完了 |
| **R41** | list_repositories URL エンコード精査 | 3 件 | ✅ 完了 |
| **R42** | bitbucket URL エンコード精査 | 2 件 | ✅ 完了 |
| **R43** | output dead code 精査 | 3 件 | ✅ 完了 |
| **R44** | auth/detect 精査 | 4 件 | ✅ 完了 |

---

## テストカバレッジ推移

| フェーズ | テスト数 | カバレッジ |
|---------|---------|-----------|
| R-09 以前（pytest-cov 導入前） | 不明 | 不明 |
| R6 カバレッジ集中強化後 | 〜900+ | 〜95% |
| R6 追加テスト後 | 〜950+ | 〜98% |
| 最終（R44 完了時） | **1,016** | **99%** |

残り未カバー行: `src/gfo/__main__.py` 4行のみ（構造上テスト不可）

---

## 参照ドキュメント

- 各ラウンドの詳細: [`docs/reviews/review-01-tasks.md`](reviews/review-01-tasks.md) 〜 [`docs/reviews/review-44-auth-detect.md`](reviews/review-44-auth-detect.md)
- アーキテクチャ設計: [`docs/design.md`](design.md)
- 実装計画: [`docs/plan.md`](plan.md)
