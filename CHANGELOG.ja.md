# 変更履歴

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
