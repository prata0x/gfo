# 変更履歴

このプロジェクトの主な変更はすべてこのファイルに記録します。

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
