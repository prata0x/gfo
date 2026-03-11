# 変更履歴

このプロジェクトの主な変更はすべてこのファイルに記録します。

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
