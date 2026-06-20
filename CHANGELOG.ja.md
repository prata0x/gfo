# 変更履歴

## [0.10.1] - 2026-06-21

### 修正
- Azure DevOps timeline: time entry を加算で集計するよう統一し、レコードの取りこぼしを是正
- フィルタ付き `list`: `limit` をフィルタ前ではなくフィルタ後に適用し、該当項目の取りこぼしを是正
- Gitea `label delete` / `label update`: ラベル一覧を全件ページネートして取得し、取りこぼしを是正
- `pr` requested reviewers: `output()` の誤用による `list[str]` でのクラッシュを是正

### セキュリティ
- `gfo api`: PATH を相対パスに限定し、絶対 URL / 外部ホスト指定時に認証トークンが送出されないようにした
- HTTP host 検証: 末尾ドット付き host を正規化し、絶対 URL ごとに TLS 検証を行う
- `release --pattern`: アセットダウンロード時のパストラバーサルを防止

## [0.10.0] - 2026-05-12

### 追加
- `auth login`: `--token-stdin`（標準入力から読み込み、CI 推奨）と `--token-file PATH` オプションを追加
- `GFO_ALLOW_INSECURE_HTTP` 環境変数: `api_url` での `http://` を opt-in で許可（`localhost` / `127.0.0.1` / `::1` 以外）
- `GFO_ALLOW_PRIVATE_HOSTS` 環境変数: プライベート / ループバック / リンクローカル IP への API プローブを opt-in で許可（社内 Gitea/GitLab 自動検出に必要）
- `GFO_MAX_DOWNLOAD_BYTES` 環境変数: ストリーミングダウンロードのサイズ上限（既定 5 GiB、`0` で無制限）

### 修正
- `pr list --state merged`（GitHub / Gitea）: closed PR が大量にある場合に件数が不足する不具合を修正。全 closed PR をページネートしてからフィルタするよう変更
- `_resolve_label_ids`（Gitea）: サーバー実装に依存する `limit=0` 挙動に頼らず全ラベルをページネートするよう修正
- `_resolve_user_ids`（GitLab）: 未解決ユーザーを警告で握りつぶさず `GfoError` を送出（assignee/reviewer 同期のサイレント部分失敗を防止）
- `list_contributors`（Gitea）: `NotFoundError` のみキャッチし、認証/サーバー/ネットワークエラーは伝播（未対応と誤報告しないよう修正）
- `list_pull_request_files` / `list_requested_reviewers`（Azure DevOps）: `.get()` 前にレスポンスが `dict` であることを検証し、想定外の型は `GfoError` で送出
- `detect_service`: remote URL が取得できない場合に保存済み git config にフォールバック（bare リポジトリ / origin 未設定 CI で動作）
- `gfo config set/get` のキーに閉じ引用符がないとき、素の `ValueError` ではなく `ConfigError` を送出
- `git_checkout_branch`: locale 依存の stderr マッチを廃止し `git rev-parse --verify` で判定（非英語ロケールでも動作）
- `repo compare`（GitLab）: `additions` / `deletions` の行数カウントを実装（従来は常に `0`）
- `batch pr create`: 例外捕捉を `GfoError` 系に絞り、プログラミングバグを「failed」として握りつぶさず顕在化させるよう変更

### セキュリティ
- `download_file`: クロスオリジン URL からのダウンロード時に認証ヘッダ / Cookie / 認証パラメータを送らない（GitLab `direct_asset_url` 等の外部ホストへの PAT 漏えい防止）
- `download_file`: `GFO_MAX_DOWNLOAD_BYTES`（既定 5 GiB）の上限を強制し、超過時は部分書き込みファイルを削除（悪意あるサーバーによる DoS 抑止）
- `download_release_asset` / `download_artifact` / `download_run_logs`: `Path.is_relative_to` による厳格な path traversal 防御、ユーザー入力 ID の basename 正規化を追加
- `GitLab.migrate_repository`: 例外型を保ったまま `args` を書き換え、全例外パスで `auth_token` をマスク
- `HttpError`: エラーメッセージ中のレスポンス body を 4096 文字で切り詰め（巨大 body による DoS 防止）
- `detect.py` プローブ: `/api/*/version` プローブでリダイレクトを無効化（リダイレクト経由の情報漏えい防止）
- `auth login --token`: プロセスリストから可視で安全でない旨の警告を表示（`--token-stdin` / `--token-file` を推奨）

### 破壊的変更
- `api_url` は既定で `https://` のみ受理（従来: スキーム不問）。`GFO_ALLOW_INSECURE_HTTP=1` で平文 HTTP を opt-in 許可、`localhost` / `127.0.0.1` / `::1` は常に許可
- 未知ホストのサービス検出で、プライベート / ループバック / リンクローカル IP へのプローブを既定で拒否。`GFO_ALLOW_PRIVATE_HOSTS=1` で復元可能（社内 Gitea/GitLab 自動検出に必要）
- `GFO_INSECURE` はクラウドサービス（github.com / gitlab.com / bitbucket.org / dev.azure.com / *.backlog.com / *.backlog.jp / *.visualstudio.com）の TLS 検証を無効化しなくなった。設定時、起動時に stderr に警告を表示
- `auth login --token TOKEN`: 非推奨化（警告を出しつつ動作は維持）。`--token-stdin` / `--token-file` への移行を推奨

## [0.9.0] - 2026-04-06

### 追加
- `repo create`: `org/repo` 形式の name で組織リポジトリの作成に対応（例: `gfo repo create my-org/my-repo --private`）
- `repo create`: GitHub/GitLab 組織リポジトリ向けに `--internal` visibility フラグを追加
- `repo migrate`: `--name` に `org/repo` 形式を指定して組織にリポジトリを移行可能に
- `repo migrate`: `--public` および `--internal` visibility フラグを追加（従来は `--private` のみ）

### 修正
- `--account` フラグをグローバルフラグとして正しくホイスト（`auth`/`init` サブコマンドは独自の `--account` を持つため除外）
- `_hoist_global_flags`: グローバルフラグの値をサブコマンドと誤認する問題を修正（例: `--format json auth` で `json` をサブコマンドと誤認しなくなった）

### 破壊的変更
- `Repository.private: bool` を `Repository.visibility: str`（`"public"`, `"private"`, `"internal"`）に変更
- `repo list` の出力カラムが `private` から `visibility` に変更
- `create_repository` / `migrate_repository` アダプターメソッドのシグネチャ変更: `private: bool` → `visibility: str`、`organization: str | None` を追加

## [0.8.0] - 2026-03-29

### 追加
- i18n: 日本語翻訳 250 エントリを追加し全 `_()` 文字列をカバー
- `gfo -h` ヘルプ出力を再設計: サブコマンドのグルーピング・説明、はじめにセクション、使用例、対応サービス一覧、環境変数の完全リスト
- `config get/set/unset` ヘルプ: ドット含みキーの引用符ルールを追記
- `commands.md` / `commands.ja.md`: 短縮オプション 75 件をドキュメントに追記

### 修正
- `GiteaAdapter.create_review`: `APPROVE` ではなく `APPROVED` イベント名を送信するよう修正（Gitea/Forgejo API の要件）
- `-R`/`--repo` 指定時に git config の `gfo.owner`/`gfo.repo` で上書きされる問題を修正
- Gogs 検出: バージョン `0.x` を Gogs として正しく判別（従来は Gitea と誤検出）
- `--remote`, `--repo`, `-R` フラグをグローバルフラグとしてホイストし、サブコマンドの後に配置しても動作するよう修正
- git リポジトリ検出: `"can only be used inside a git repository"` エラーメッセージの認識を追加
- `normalize_host`: URL 形式でポート付きホストを渡した場合にポート番号を保持するよう修正（例: `http://localhost:3000`）
- `--host` オプション: `init`, `auth login/switch/token/logout` で URL からホスト名を自動抽出
- エラーメッセージに `--non-interactive` と `--repo HOST/OWNER/REPO` の使用例を追記

## [0.7.0] - 2026-03-25

### 追加
- CLI 短縮オプション: 全サブコマンドに 75 個のショートフラグを追加
- `read_file_arg` ヘルパー: `--body-file` / `--notes-file` のファイル読み込みを統一し、エラーハンドリングを共通化
- mypy strict モード: `disallow_untyped_defs = true` を有効化し型安全性を強化
- 書き込み/削除ハンドラに成功メッセージを追加（`file put`, `file delete`, `branch delete`, `tag delete`, `webhook delete` 等）

### 修正
- `GiteaAdapter.create_issue`: ラベル名を `_resolve_label_ids()` で ID に変換するよう修正（Gitea API は整数 ID を要求）
- `--jq` フィルタ: 空文字列チェックを `if jq:` から `if jq is not None:` に修正
- `argparse.FileType` を廃止しファイルパス文字列で受け取るよう変更
- `add_time_entry` の `duration` 型を全アダプターで `int | float` に統一
- 統合テスト: Gitea/Forgejo の `test_02c_repo_contributors`（API 未実装）、GitBucket の `test_40_file_crud`（冪等性）を修正

## [0.6.0] - 2026-03-22

### 追加

- `config` コマンド追加（`get`, `set`, `list`, `unset`, `path` サブコマンド）
- `auth token` コマンド（現在のトークンを表示）
- `completion` コマンド（シェル補完）
- `search code` コマンド（GitHub/GitLab/Bitbucket/Azure DevOps）
- `ci delete` コマンド（GitHub/GitLab/Azure DevOps）
- `release create --generate-notes` オプション（GitHub/GitLab）
- `--web` オプションを `pr`/`issue`/`release` の `create`/`list`/`view` に拡大
- `pr` コマンド拡張: `--draft`, `--ready`, `--milestone`, `subscribe`, `--dry-run`
- `issue` コマンド拡張: `--due-date`, `--template`, `status`, `develop`
- `repo` コマンド拡張: `unarchive`, `list --archived`, `create --readme`
- `pr create` / `issue create` に `--body-file` (`-F`) オプション追加
- `repo create` で `--private` / `--public` フラグを必須に変更

### 修正

- config キー解析でドット含みキーの引用符記法に対応
- レビュー指摘修正: auth token、config `--jq`、limit+フィルタの相互作用、ドキュメント

### テスト

- エッジケース・エラーパスの単体テスト 115 件追加（カバレッジ 90% → 91%）
- CLI 統合テスト追加（private member 依存解消）
- SaaS 統合テスト追加（レート制限対策ディレイ付き）
- 統合テスト修正（GitHub SHA、Bitbucket/Azure DevOps CI 分類、タイミング、subprocess、SSH）

## [0.5.0] - 2026-03-20

### 追加

- `pr list` フィルタオプション: `--author`, `--label`, `--assignee`, `--search`, `--base`, `--head`, `--draft` (B5-1〜B5-7)
- `issue list` フィルタオプション: `--author`, `--milestone`, `--search` (B3-1〜B3-3)
- `issue create --milestone` オプション (B3-4)
- `pr edit` / `issue edit` メタデータオプション: `--add-label`, `--remove-label`, `--add-assignee`, `--remove-assignee`, `--milestone` (B2-1〜B2-7)
- `pr merge --subject` / `--body` でマージコミットメッセージを指定可能に (B1-2)
- `branch view`, `tag view`, `deploy-key view`, `ssh-key view`, `gpg-key view` サブコマンド (F1-1〜F1-5)
- `webhook edit`, `org edit`, `release-asset edit`, `tag-protect edit` サブコマンド (F2-1〜F2-4)
- `pr status` サブコマンド (E1-1)
- `pr lock` / `pr unlock`, `issue lock` / `issue unlock` サブコマンド (E1-5〜E1-6)
- CI 拡張: `ci workflow`, `ci artifact`, `ci download`, `ci watch`（`--timeout` オプション付き）(E1-3〜E1-4, E1-7〜E1-8)
- `issue subscribe` / `issue unsubscribe` サブコマンド (E1-9)
- `secret` / `variable` の org スコープ対応 (E1-10)
- `repo edit --name` でリポジトリリネーム対応 (E1-2)
- `repo sync` サブコマンド（フォーク同期）(E2-1)

### 修正

- コードレビュー指摘事項 19 件を修正（Major 9 件、Minor 8 件、Nitpick 2 件）
- コードレビュー残指摘 7 件を修正

### テスト

- テストコードレビュー指摘事項 20 件を修正（+713 テスト、カバレッジ 88% → 90%）

## [0.4.0] - 2026-03-20

### 破壊的変更

- `update` サブコマンドを `edit` にリネーム（全 8 コマンド: pr, issue, release, label, milestone, repo, wiki, branch-protect）
- `comment` コマンドを `pr comment` / `issue comment` サブコマンドに移動
- `review` コマンドを `pr review` サブコマンドに移動
- `pr merge --method` を `--merge` / `--squash` / `--rebase` 個別フラグに変更
- `credentials.toml` をマルチアカウント対応の新形式に変更

### 追加

- `auth logout` サブコマンド
- `view` / `list` サブコマンドに `--web` / `-w` オプション（ブラウザで開く）
- `pr create` に `--reviewer` / `--assignee` / `--label` / `--milestone` / `--fill` オプション
- `release create` に `--target` オプション

### 修正

- auth.py のレビュー指摘事項を修正（#1, #2, #3, #5, #6, #13）
- コマンドハンドラの不具合を修正（#7, #9, #10, #11, #12, #21, #26）
- `create_pull_request` の不具合を修正（#4, #8）

## [0.3.0] - 2026-03-18

### 追加

- `--repo` グローバルオプション（URL または `HOST/OWNER/REPO` でリポジトリを直接指定）
- `--remote` / `--host` グローバルオプションおよびリモート解決フォールバック（origin → 最初に見つかったリモート）
- Phase 1〜6 マルチサービス機能拡張（50 以上のサブコマンド: PR 操作、リリース・リポジトリ管理、CI・セキュリティ・組織、Issue・検索・ニッチ、一括・移行）
- 全 `add_parser()` / `add_argument()` に `help=_()` を追加し schema 出力のパラメータ説明を完備

### 修正

- schema 出力の description をロケール非依存で常に英語に固定
- バージョン二重管理を解消（hatchling 動的バージョンに統一）

### その他

- 完了済みロードマップを削除

## [0.2.2] - 2026-03-17

### 追加

- `gfo schema` コマンド（P4: 全コマンドの JSON Schema メタデータ）
- 非 TTY 時に自動で JSON 出力へ切り替え（P3: TTY 検出）
- `ExitCode(IntEnum)` による終了コードの細分化（例外ごとに固有コード）
- `--format json` 指定時のエラーを構造化 JSON で stderr に出力

### 修正

- コードレビュー指摘事項の修正（H1-H4, M1-M8, L1-L3）
- 統合テスト実行時に GCM がブラウザを開く問題を修正

### その他

- `docs/roadmap.md` を削除（P1〜P4 実装完了、P5 は見送り）

## [0.2.1] - 2026-03-17

### 追加

- gettext ベースの i18n 対応（デフォルト英語 + 日本語ロケール）
- AI エージェント対応ロードマップ（`docs/roadmap.md`）

### 修正

- Windows で日本語を含む出力が文字化けする問題を修正
- i18n レビュー指摘事項の修正（Windows ロケール正規化、パス区切り、翻訳漏れ）

### その他

- 実装済みロードマップ（`docs/roadmap/`）を削除

## [0.2.0] - 2026-03-17

### 追加

- `gfo browse` コマンド（リポジトリ・PR・Issue をブラウザで開く、全 9 サービス対応）
- `--jq` グローバルオプション（JSON 出力への jq フィルタ適用）
- `gfo ssh-key` コマンド（ユーザー SSH 公開鍵の管理、6 サービス対応）
- `gfo org` コマンド（所属組織の一覧・詳細・メンバー・リポジトリ、7 サービス対応）
- `gfo notification` コマンド（通知の一覧・既読化、5 サービス対応）
- `gfo branch-protect` コマンド（ブランチ保護ルールの管理、5 サービス対応）
- `gfo secret` / `gfo variable` コマンド（CI/CD シークレット・変数の管理、5 サービス対応）

## [0.1.1] - 2026-03-11

### 変更

- PyPI メタデータを補充（readme, keywords, classifiers, urls）
- CHANGELOG を追加し README からリンク

## [0.1.0] - 2026-03-11

### 追加

- 初回リリース
- 9 つの Git ホスティングサービスに対応した統一 CLI（GitHub, GitLab, Bitbucket Cloud, Azure DevOps, Backlog, Gitea, Forgejo, Gogs, GitBucket）
- remote URL からのサービス自動検出
- コマンド: `init`, `auth`, `pr`, `issue`, `repo`, `release`, `label`, `milestone`, `comment`, `review`, `branch`, `tag`, `status`, `file`, `webhook`, `deploy-key`, `collaborator`, `ci`, `user`, `search`, `wiki`
- 出力形式: `table`, `json`, `plain`
- 依存は `requests` のみ — 軽量
