# gfo ロードマップ

既存の Git ホスティング CLI ツールの機能と gfo の現状を比較し、未実装で適用可能な機能を 9 サービスの API 対応状況とともに整理したドキュメント群。

調査日: 2026-03-17

## Phase 別ドキュメント

各機能の API 対応表・エンドポイント・実装方針・実装詳細は以下にまとめている。

| Phase | テーマ | ドキュメント |
|:-----:|--------|-------------|
| 1 | 既存コマンドの補完 | [phase1-crud-completion.md](phase1-crud-completion.md) |
| 2 | PR 操作の拡充 | [phase2-pr-operations.md](phase2-pr-operations.md) |
| 3 | Release / Repo 管理の拡充 | [phase3-release-repo.md](phase3-release-repo.md) |
| 4 | CI / セキュリティ / 組織 | [phase4-ci-security-org.md](phase4-ci-security-org.md) |
| 5 | Issue 拡張 / 検索 / ニッチ機能 | [phase5-issue-search-niche.md](phase5-issue-search-niche.md) |
| 6 | マルチサービス CLI ならではの機能 | [phase6-future-vision.md](phase6-future-vision.md) |

---

## サービス別 API 対応サマリー

全 55 機能（#22 Raw API call 除外で 54 機能を母数として集計）。

| サービス | ○ | △ | × | 対応率 |
|----------|:-:|:-:|:-:|:------:|
| **GitHub** | 45 | 3 | 6 | 86% |
| **GitLab** | 45 | 6 | 3 | 89% |
| **Bitbucket** | 14 | 10 | 30 | 35% |
| **Azure DevOps** | 24 | 15 | 15 | 58% |
| **Gitea** | 52 | 1 | 1 | 97% |
| **Forgejo** | 50 | 3 | 1 | 95% |
| **Gogs** | 3 | 2 | 49 | 7% |
| **GitBucket** | 9 | 3 | 42 | 19% |
| **Backlog** | 4 | 9 | 41 | 16% |

> ○=1点、△=0.5点で対応率算出。#22 Raw API call は全サービス共通のため母数（54）から除外

### 凡例

| 記号 | 意味 |
|------|------|
| ○ | API が存在し実装可能 |
| △ | 部分的にサポート / 制限あり |
| × | API が存在しない |

※ ○のサービスについて、API エンドポイントが標準的・自明な場合は補足説明を省略している。

---

## CLI ツール別コマンド対応表

各 CLI ツールが持つ主要コマンドの比較。gfo が既に実装済みのものも含む。

| 機能カテゴリ | gh | glab | tea | fj | gfo 実装状況 |
|-------------|:--:|:----:|:---:|:--:|:-----------|
| **PR CRUD** | ○ | ○ | ○ | ○ | ○ 実装済み |
| PR reopen | ○ | ○ | ○ | × | ○ 実装済み |
| PR diff | ○ | ○ | × | × | ○ 実装済み |
| PR checks/status | ○ | ○ | × | ○ | ○ 実装済み |
| PR files | ○ | ○ | × | × | ○ 実装済み |
| PR commits | ○ | ○ | × | × | ○ 実装済み |
| PR requested reviewers | ○ | ○ | × | × | ○ 実装済み |
| PR update branch | ○ | ○ | × | × | ○ 実装済み |
| PR ready (draft解除) | ○ | ○ | × | × | ○ 実装済み |
| PR review/approve | ○ | ○ | ○ | × | ○ 実装済み |
| PR checkout | ○ | ○ | ○ | ○ | ○ 実装済み |
| PR merge | ○ | ○ | ○ | ○ | ○ 実装済み |
| **Issue CRUD** | ○ | ○ | ○ | ○ | ○ 実装済み |
| Issue reopen | ○ | ○ | ○ | × | ○ 実装済み |
| Issue reactions | ○ | ○ | × | × | ○ 実装済み |
| Issue pin/unpin | ○ | × | × | × | ○ 実装済み |
| Issue dependencies | × | △ | × | × | ○ 実装済み |
| Issue timeline | ○ | △ | × | × | ○ 実装済み |
| Issue comment | ○ | ○ | ○ | ○ | ○ 実装済み |
| **Issue migrate** | × | × | × | × | ○ 実装済み |
| **Issue templates** | × | ○ | × | × | ○ 実装済み |
| **Repo CRUD** | ○ | ○ | ○ | ○ | ○ 実装済み |
| Repo update/edit | ○ | ○ | ○ | × | ○ 実装済み |
| Repo archive | ○ | ○ | × | × | ○ 実装済み |
| Repo migrate | × | ○ | ○ | ○ | ○ 実装済み |
| Repo topics | ○ | △ | × | × | ○ 実装済み |
| Repo compare | ○ | ○ | × | × | ○ 実装済み |
| Repo languages | ○ | ○ | × | × | ○ 実装済み |
| Repo transfer | ○ | ○ | × | × | ○ 実装済み |
| Repo fork | ○ | ○ | ○ | ○ | ○ 実装済み |
| **Release CRUD** | ○ | ○ | ○ | × | ○ 実装済み |
| Release view | ○ | ○ | × | × | ○ 実装済み |
| Release latest | ○ | △ | × | × | ○ 実装済み |
| Release edit/update | ○ | × | ○ | × | ○ 実装済み |
| Release assets | ○ | ○ | ○ | × | ○ 実装済み |
| **Label CRUD** | ○ | ○ | ○ | △ | ○ 実装済み |
| Label clone | ○ | × | × | × | ○ 実装済み |
| **Milestone CRUD** | × | ○ | ○ | × | ○ 実装済み |
| Milestone close/reopen | × | × | ○ | × | ○ 実装済み |
| **CI/Actions** | ○ | ○ | ○ | ○ | ○ 実装済み |
| CI trigger | ○ | ○ | × | ○ | ○ 実装済み |
| CI retry | ○ | ○ | × | × | ○ 実装済み |
| CI logs | ○ | ○ | × | × | ○ 実装済み |
| **Secret/Variable** | ○ | ○ | ○ | ○ | ○ 実装済み |
| **SSH Key** | ○ | ○ | × | ○ | ○ 実装済み |
| **GPG Key** | ○ | ○ | × | ○ | ○ 実装済み |
| **Webhook** | × | × | ○ | × | ○ 実装済み |
| Webhook test | ○ | ○ | × | × | ○ 実装済み |
| **Tag protections** | △ | ○ | × | × | ○ 実装済み |
| **Notification** | ○ | × | ○ | × | ○ 実装済み |
| **Organization** | ○ | × | ○ | ○ | ○ 実装済み |
| **Branch protect** | × | × | ○ | × | ○ 実装済み |
| **Wiki** | × | × | × | ○ | ○ 実装済み |
| Wiki revisions | × | × | × | × | ○ 実装済み |
| **Browse** | ○ | × | ○ | ○ | ○ 実装済み |
| **Search** | ○ | ○ | ○ | ○ | ○ 実装済み（repos/issues/prs/commits） |
| **Package management** | ○ | ○ | × | × | ○ 実装済み |
| **Push mirrors** | × | ○ | × | × | ○ 実装済み |
| **Time tracking** | × | ○ | ○ | × | ○ 実装済み |
| **Raw API call** | ○ | ○ | ○ | × | ○ 実装済み |
| **User whoami** | × | × | ○ | ○ | ○ 実装済み |
| **Collaborator** | × | × | × | × | ○ 実装済み |
| **Deploy Key** | ○ | ○ | × | × | ○ 実装済み |
| **Commit Status** | × | × | × | × | ○ 実装済み |
| **File API** | × | × | × | × | ○ 実装済み |
| **Star/Unstar** | × | × | × | ○ | ○ 実装済み |
| **Batch PR create** | × | × | × | × | ○ 実装済み |

---

## 対象外: サービス固有機能

以下は特定サービスに強く依存するため、マルチサービスツールとしての gfo では優先度が低い。

| 機能 | サービス / CLI | 理由 |
|------|---------------|------|
| Gist / Snippet | GitHub / GitLab | サービス固有のコード共有機能 |
| Codespace | GitHub | クラウド開発環境 |
| Projects v2 | GitHub | プロジェクト管理ボード |
| Runner 管理 | GitLab | CI ランナーインフラ |
| Extension / Plugin | gh / glab | CLI 拡張機構（アーキテクチャ変更が必要） |
| Changelog 生成 | GitLab | リリースノート自動生成 |
| Copilot / Duo | GitHub / GitLab | AI アシスタント |
| Incident / Iteration | GitLab | GitLab 固有のプロジェクト管理 |
| Stack (stacked MR) | GitLab | スタック型 MR ワークフロー |
| Attestation | GitHub | ソフトウェアサプライチェーンセキュリティ |
| Ruleset | GitHub | リポジトリルール管理 |
| Cache | GitHub | Actions キャッシュ管理 |
| AGit flow | Forgejo (fj) | Forgejo 固有の PR 作成方式 |
| Admin users | tea | Gitea 管理者向け機能。gfo はエンドユーザー向け |
| User follow/block | fj | SNS 的操作。Git Forge 操作の本質ではない |
| Org team 管理 | fj | 組織内チーム・権限管理。複雑で統一 API が困難 |
| Repo create-from-template | tea | テンプレート仕様がサービスごとに大きく異なる |
| ActivityPub | Forgejo | フェデレーション機能。Forgejo 固有 |
| Quota management | Forgejo | インスタンス管理向け。エンドユーザー向けではない |
| Issue attachments | Forgejo/Gitea | Issue への添付ファイル管理。対応サービスが限定的 |
| Repo flags | Forgejo | Forgejo 固有のリポジトリフラグ機能 |
| Git hooks (server-side) | Forgejo/Gitea | サーバーサイド Git フック管理。管理者向け |
| OAuth2 app 管理 | Forgejo/Gitea | OAuth2 アプリケーション管理。開発者向け |
| User email 管理 | Forgejo/Gitea | メールアドレス管理。アカウント設定向け |
| スタック PR 管理 | Graphite, ghstack, spr 等 | git ブランチ操作が中心。API 操作のみでは完結しない |
| CI ローカル実行 | act, gitlab-ci-local | Docker 依存のローカル実行。リモート API 操作ではない |
| CI lint/validate | lighttiger2505/lab | GitLab のみ対応 (#51)。マルチサービスでは優先度低 |
| PR バルクマージ/承認 | gomerge | TUI 操作。CLI コマンドとしては設計が異なる |
| コードレビューコメント埋め込み | mustard-cli | Bitbucket Server 専用。アーカイブ済み |
| Workspace/Project 管理 | gildas/bb | Bitbucket 固有のワークスペース概念 |

---

## 参考: 調査した CLI ツール一覧

### GitHub 向け

| ツール | URL | 備考 |
|--------|-----|------|
| gh | github.com/cli/cli | 公式。最も機能豊富 |
| hub | github.com/mislav/hub | 旧公式。git ラッパー型 |
| Graphite (gt) | graphite.dev | スタック PR 管理。商用 |
| ghstack | github.com/ezyang/ghstack | Meta 製スタック PR |
| spr | github.com/ejoffe/spr | 軽量スタック PR |
| stack-pr | github.com/modular/stack-pr | Modular 製スタック PR |
| charcoal | github.com/danerwilliams/charcoal | Graphite OSS フォーク |

### GitLab 向け

| ツール | URL | 備考 |
|--------|-----|------|
| glab | gitlab.com/gitlab-org/cli | 公式。CI/CD 関連が充実 |
| lab (zaquestion) | github.com/zaquestion/lab | git ラッパー型 |
| lab (lighttiger2505) | github.com/lighttiger2505/lab | テンプレート管理・CI lint |

### Bitbucket 向け

| ツール | URL | 備考 |
|--------|-----|------|
| bb (craftamap) | github.com/craftamap/bb | gh 風 UX |
| bb (gildas) | github.com/gildas/bitbucket-cli | パイプライン操作が充実 |
| bkt (avivsinai) | github.com/avivsinai/bitbucket-cli | Cloud + Data Center 両対応。拡張機構 |
| bbt | codeberg.org/romaintb/bbt | 軽量 Bitbucket CLI |

### Azure DevOps 向け

| ツール | URL | 備考 |
|--------|-----|------|
| az devops | github.com/Azure/azure-devops-cli-extension | Microsoft 公式拡張 |
| doing-cli | ing-bank.github.io/doing-cli | ワンコマンド Issue+PR 作成 |

### Gitea / Forgejo / Gogs 向け

| ツール | URL | 備考 |
|--------|-----|------|
| tea | gitea.com/gitea/tea | Gitea 公式。タイムトラッキング・リポジトリ移行など独自機能あり |
| fj | codeberg.org/forgejo-contrib/forgejo-cli | Forgejo 向け。Rust 製。forgejo-contrib でインキュベーション中 |
| sip | gitea.com/jolheiser/sip | 対話型 Gitea CLI |
| codeberg-cli (berg) | codeberg.org/Aviac/codeberg-cli | Forgejo 向け。広範な機能 |
| bashup/gitea-cli | github.com/bashup/gitea-cli | Bash 製。カスタムコマンド拡張可能 |

### GitBucket / Backlog 向け

| ツール | URL | 備考 |
|--------|-----|------|
| gbutil | github.com/SIkebe/gitbucket-utility | Issue 移動・バックアップ |
| gitb | github.com/vvatanabe/gitb | Backlog Git 操作。Nulab 公式ブログ掲載 |
| shufo/backlog-cli | github.com/shufo/backlog-cli | gh 風 UX の Backlog CLI |

### マルチサービス対応

| ツール | URL | 対応サービス | 備考 |
|--------|-----|-------------|------|
| gcli | github.com/herrhotzenplotz/gcli | GitHub/GitLab/Gitea/Forgejo/Bugzilla | gfo の最も近い競合。C 言語製 |
| git-town | github.com/git-town/git-town | GitHub/GitLab/Gitea/Bitbucket/Forgejo | ブランチライフサイクル自動化 |
| git-forge (Leleat) | github.com/Leleat/git-forge | GitHub/GitLab/Gitea/Forgejo | フォージ不問の抽象化設計 |
| multi-gitter | github.com/lindell/multi-gitter | GitHub/GitLab/Gitea/Bitbucket | マルチリポ一括変更 |

### 特化型ツール

| ツール | URL | 機能 |
|--------|-----|------|
| reviewdog | github.com/reviewdog/reviewdog | lint 結果 → PR コメント |
| semantic-release | github.com/semantic-release | 自動バージョニング + リリース |
| git-cliff | git-cliff.org | CHANGELOG 生成 |
| act | github.com/nektos/act | GitHub Actions ローカル実行 |
| gitlab-ci-local | github.com/firecow/gitlab-ci-local | GitLab CI ローカル実行 |
| git-bug | github.com/git-bug/git-bug | 分散バグトラッカー。サービス間ブリッジ |
