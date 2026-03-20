# gfo 実装 TODO

`docs/feature-gap-analysis.md` の機能ギャップを変更ファイル単位でグループ化した実装計画。

---

## 10. `--web` オプション共通追加

**変更ファイル**: `cli.py`, `commands/pr.py`, `commands/issue.py`, `commands/release.py`, `commands/browse.py`, テスト

`pr create`, `pr list`, `issue create`, `release view` 等に `--web` / `-w` オプションを追加。既存の `browse` コマンドの URL 構築ロジックを流用してブラウザで開く。

---

## 11. `config` コマンド

**変更ファイル**: `cli.py`, `commands/` (新規ファイル), `config.py`, テスト

デフォルトのエディタ、出力形式、リポジトリ設定等をローカルに保存・管理。設計要検討。
