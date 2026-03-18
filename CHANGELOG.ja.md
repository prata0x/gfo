# 変更履歴

このプロジェクトの主な変更はすべてこのファイルに記録します。

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
