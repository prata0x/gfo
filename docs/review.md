# gfo コードレビュー 全体サマリー

## 概要

| 項目 | 内容 |
|------|------|
| レビュー期間 | 44ラウンド |
| 対象コミット | `69c4d59`（review-01-tasks.md 追加）〜 `cc6bd29`（最終修正完了） |
| 総コミット数 | 214 コミット |
| 変更ファイル数 | 104 ファイル |
| 変更行数 | +14,735 / −1,077 行 |
| 最終テスト数 | 1,016 テスト |
| 最終カバレッジ | 99%（`__main__.py` 4行のみ未カバー） |

---

## 変更カテゴリ別サマリー

### バグ修正（135 コミット）

#### コア・HTTP

| 修正内容 |
|---------|
| `paginate_link_header` の `next_url` 代入漏れ |
| `paginate` の `_session` 直接呼び出し → `get_absolute` に置換 |
| `paginate_page_param` の X-Next-Page 非整数値で ValueError 防止 |
| `paginate_top_skip/response_body` の非 dict レスポンス対応 |
| Link ヘッダーの `rel="Next"` 大文字小文字非感知マッチ |
| `limit` 負値ガードと `per_page/limit` 連動最適化 |
| SSLError 等の `RequestException` サブクラスを `NetworkError` に統一 |
| `paginate_response_body` で非文字列 `next_url` の AttributeError 防止 |
| `paginate_*` 全メソッドで非 JSON レスポンスを安全に処理 |

#### 検出（detect.py）

| 修正内容 |
|---------|
| HTTP remote URL の scheme 判定デッドコード修正（`http` 固定） |
| `detect_service` git config ショートカットで host も上書き・不一致警告 |
| `probe_unknown_host` の Gitea/Forgejo/Gogs 判定精度改善 |
| SSH regex でハイフン入りユーザー名に対応 |
| HTTPS URL の userinfo をホスト抽出前にスキップ |
| ホスト名の大文字小文字正規化（`lower()`）を全箇所に適用 |
| `_BACKLOG_PATH_RE` と `_GITBUCKET_PATH_RE` の重複正規表現を統合 |
| `_GITBUCKET_PATH_RE` dead alias を削除 |

#### 設定・認証（config.py / auth.py）

| 修正内容 |
|---------|
| `load_user_config` の `PermissionError` を `ConfigError` に変換 |
| `resolve_project_config` の remote URL 解析を `try/except` で保護 |
| `resolve_project_config` の remote URL 失敗時に git config へフォールバック |
| `build_clone_url` バリデーション追加・ハードコードホストを引数化 |
| `get_auth_status` の env var エントリの host 形式を統一し重複排除 |
| `save_token()` の二重 falsy チェックを簡略化 |
| `build_default_api_url` エラーメッセージに `gfo init` 提案 |

#### 初期化（commands/init.py）

| 修正内容 |
|---------|
| 非対話 init で `detect_from_url` を先行呼び出しし organization を渡す |
| 対話 init で organization 未解決時のエラーを手動入力にフォールバック |
| 手動入力パスで Azure DevOps の organization を追加入力させる |
| non-interactive モードで URL 検出の `project_key` を `api_url` 構築に使用 |
| 対話モードで `detect_service` の `GitCommandError` を手動入力へフォールバック |
| `else` ブランチで 2 回目の `build_default_api_url` 失敗時のエラーメッセージ改善 |

#### CLI・コマンド共通

| 修正内容 |
|---------|
| argparse 内部 API `_subparsers._group_actions` の参照を排除 |
| `--limit` 引数に正数バリデーションを追加 |
| `issue/milestone/pr create` で空タイトルを拒否 |
| `init` 対話モードで空の `service_type/host` を拒否 |
| 予期しない例外を catch-all で捕捉してユーザー向けメッセージを表示 |
| `_positive_int` エラーメッセージを統一 |
| 入力値の `strip()` 処理を全コマンドで一貫化 |
| `_resolve_host_without_repo` でホスト解決順序を修正 |
| git リポジトリ外で `GitCommandError` をデフォルトホストへフォールバック |

#### アダプター共通・基底クラス

| 修正内容 |
|---------|
| 全アダプター `_to_*` メソッドに `KeyError/TypeError` ラッピングを追加 |
| `null` フィールドで `AttributeError` が `try/except` を素通りするバグを修正 |
| `or {}` パターンの `AttributeError` を `_to_*` メソッド全体で捕捉 |
| 全アダプターの `_to_issue()` に `updated_at` を追加 |
| `list_labels/milestones` に `limit` 引数追加・`PullRequest.updated_at` デフォルト修正 |
| `get_pr_checkout_refspec` に `refs/` プレフィックスを追加 |
| 非 ASCII `owner/repo` の URL エンコーディング対応 |
| `get_repository` に URL エンコードを追加（backlog/azure_devops/bitbucket） |
| `list_repositories` の `owner` URL エンコード修正 |
| `get_adapter` ヘルパーでコマンドハンドラの定型2行を集約 |

#### GitHub / GitHubLike

| 修正内容 |
|---------|
| `list_labels/list_milestones` をページネーション対応 |
| `_to_*` 変換メソッドの重複を `GitHubLikeAdapter` で解消 |

#### GitLab

| 修正内容 |
|---------|
| `_to_pull_request` に `"locked"` state マッピングを追加 |
| `merge_pull_request` の squash/rebase マッピングを GitLab API 仕様に修正 |
| `_to_release` の `draft` を `False` 固定に修正 |
| `list_repositories` の URL 構築を `params` ベースに変更 |
| `create_label` で color に `#` プレフィックスが含まれる場合の二重 `##` を防止 |
| `_to_issue` の冗長な no-op 代入を削除 |
| `merge_pull_request` 不正 method → `GfoError` |
| `_to_milestone` で GitLab の `state="active"` を `"open"` に変換 |
| `state=all` 時に無効な API パラメータを送らないよう修正 |
| rebase エンドポイント修正 |
| `limit=0` のバグ修正 |

#### Bitbucket

| 修正内容 |
|---------|
| `close_issue` の state 値を `"resolved"` に修正 |
| `_to_issue` の deleted user assignee で `KeyError` を防止 |
| `create_issue` で label を component に反映・`_to_issue` で `component→labels` 変換 |
| `list_issues(state="closed")` が resolved 状態を含まなかったバグを修正 |
| `list_issues` の `assignee` フィルタが無視されていた問題を修正 |
| `state=all` 時に無効な API パラメータを送らないよう修正 |
| `assignee` 空文字チェックを追加 |
| `close_pull_request` を正しい `/decline` エンドポイントに修正 |
| repository メソッドの URL エンコード修正 |
| `merge_method` 無視バグを修正 |

#### Backlog

| 修正内容 |
|---------|
| `create_issue` で `issue_type/priority` が None のとき `GfoError` を raise |
| `get_issue` を `issueKey` 形式（`PROJECT_KEY-N`）で取得 |
| `_to_pull_request` の `merged` 判定を動的 `status_id` 参照に変更 |
| `list_pull_requests` で `merged_id` を list に統一 |
| `_to_issue` の `issueKey` 末尾を int にキャスト |
| `create_issue` の `issueTypes/priorities` 応答を防御的に検証 |
| `_ensure_project_id` → `GfoError` |
| `_resolve_merged_status_id` の list 検証 + `KeyError` スキップ |
| `createdUser null` 時の `AttributeError` を修正 |
| Backlog のマジックナンバーをモジュール定数に置換 |

#### Azure DevOps

| 修正内容 |
|---------|
| WIQL クエリのシングルクォートをエスケープ |
| PR state 辞書参照を `.get()` で KeyError 対策 |
| WIQL インジェクション対策 — `_wiql_escape()` ヘルパー追加 |
| `list_issues` の WIQL/workitems レスポンスを防御的に検証 |
| `merge_pull_request` の `lastMergeSourceCommit` KeyError を修正 |
| `merge_pull_request` の非 dict レスポンス時 `AttributeError` を修正 |
| `defaultBranch` が null のとき `GfoError` になるバグを修正 |
| `list_issues` の `limit=0` バグ修正 |
| `_to_repository` を `@staticmethod` に変更 |
| `work_item_type` を URL エンコードするよう修正 |
| `list_repositories` が `owner` 指定を無言で無視していたバグを修正 |
| repo create クラッシュを修正 |
| `updated_at` を PR/Issue に追加 |

#### Gitea / Forgejo

| 修正内容 |
|---------|
| `list_issues` に `type=issues` パラメータを追加 |
| `merge_pull_request` を `PUT → POST` に修正 |
| `list_labels/milestones` の全件取得（ページネーション対応） |

#### Gogs

| 修正内容 |
|---------|
| `get_pr_checkout_refspec` を `NotSupportedError` でオーバーライド |
| 全メソッドに型ヒントを追加 |
| `web_url` URL エンコード |
| port 修正 |

#### GitBucket

| 修正内容 |
|---------|
| `label color` バグ修正 |

#### セキュリティ集中修正

| 修正内容 |
|---------|
| WIQL インジェクション対策 |
| `http.py` セキュリティ強化（SSRF 対策等） |
| `git_util.py` エラーメッセージの認証情報マスク |
| `detect.py` セキュリティ強化 |
| Windows パーミッション堅牢化と TOML 制御文字エスケープ |

---

### テスト強化（29 コミット）

| 主要内容 |
|---------|
| ForgejoAdapter テスト強化 |
| GitBucketAdapter テスト強化 |
| auth_cmd テスト強化 |
| label_cmd テスト強化 |
| milestone_cmd テスト強化 |
| セキュリティ修正テスト追加（29件） |
| カバレッジ 99% まで引き上げ |
| `get_adapter/get_default_branch` 残り分岐カバレッジ |
| `http/detect` クロスオリジン・非dict・ValueError カバレッジ |
| `save_token` 空/空白バリデーションテスト |
| `auth/gogs/backlog` TOML エラー・icacls 非ゼロカバレッジ |
| `gitlab` 3階層サブグループ `_project_path()` テスト |
| `config` shost 部分設定・PermissionError テスト |
| Bitbucket list_issues カスタム state フィルタ |
| output dead assignment 除去・テスト整理 |
| `format_json` else ブランチデッドコード除去 |

---

### リファクタリング（13 コミット）

| 主要内容 |
|---------|
| `HttpClient` 生成ロジックを `create_http_client()` に共通化 |
| `GitHubLikeAdapter` で `_to_*` 変換メソッドの重複を解消 |
| `get_adapter` ヘルパーでコマンドハンドラ定型2行を集約 |
| `handle_clone` の clone URL 構築を `build_clone_url` に集約 |
| プライベート関数を公開 API に変更 |
| `Backlog` マジックナンバーをモジュール定数に置換 |
| `AzureDevOpsAdapter._to_repository` を `@staticmethod` に変更 |
| `stype/shost` 省略変数名を `saved_type/saved_host` に変更 |
| `get_auth_status` の `seen_hosts` env var 追加・テスト helper 化 |
| `DetectResult` を `frozen=True` に変更し `dataclasses.replace()` を使用 |
| `_BACKLOG_PATH_RE` と `_GITBUCKET_PATH_RE` の重複正規表現を統合 |
| `_GITBUCKET_PATH_RE` dead alias を削除 |
| `output.py` dead assignment 除去 |

---

### ドキュメント（36 コミット）

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

## テストカバレッジ推移

| フェーズ | テスト数 | カバレッジ |
|---------|---------|-----------|
| pytest-cov 導入前 | 不明 | 不明 |
| カバレッジ集中強化後 | 〜900+ | 〜95% |
| 追加テスト後 | 〜950+ | 〜98% |
| 最終（完了時） | **1,016** | **99%** |

残り未カバー行: `src/gfo/__main__.py` 4行のみ（構造上テスト不可）

---

## 参照ドキュメント

- アーキテクチャ設計: [`docs/design.md`](design.md)
- 実装計画: [`docs/plan.md`](plan.md)
