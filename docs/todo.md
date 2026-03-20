# gfo 実装 TODO

`docs/feature-gap-analysis.md` の機能ギャップを変更ファイル単位でグループ化した実装計画。

---

## 9. 新コマンド: `auth token` / `completion`

**変更ファイル**: `cli.py`, `commands/auth_cmd.py`, テスト

### 9a. `auth token`

現在の認証情報からトークンを取得して標準出力に出力。パイプ連携用。

```python
# commands/auth_cmd.py handle_token():
token = resolve_token(host)
print(token)
```

### 9b. `completion`

**変更ファイル**: `cli.py` (新サブコマンド登録)

argparse ベースでシェル補完スクリプトを生成。bash / zsh / fish 対応。

---

## 10. `--web` オプション共通追加

**変更ファイル**: `cli.py`, `commands/pr.py`, `commands/issue.py`, `commands/release.py`, `commands/browse.py`, テスト

`pr create`, `pr list`, `issue create`, `release view` 等に `--web` / `-w` オプションを追加。既存の `browse` コマンドの URL 構築ロジックを流用してブラウザで開く。

---

## 11. `config` コマンド

**変更ファイル**: `cli.py`, `commands/` (新規ファイル), `config.py`, テスト

デフォルトのエディタ、出力形式、リポジトリ設定等をローカルに保存・管理。設計要検討。
