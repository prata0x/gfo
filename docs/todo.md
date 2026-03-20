# gfo 実装 TODO

`docs/feature-gap-analysis.md` の機能ギャップを変更ファイル単位でグループ化した実装計画。

---

## 6. `ci delete`

**変更ファイル**: `cli.py`, `commands/ci.py`, `adapter/base.py`, 各アダプター (GitHub/GitLab/Azure DevOps), テスト

`delete_pipeline_run()` を `adapter/base.py` に追加。3 サービス対応。

```python
# adapter/base.py
def delete_pipeline_run(self, run_id: int) -> None:
    raise NotSupportedError("ci delete")
```

---

## 7. `search code`

**変更ファイル**: `cli.py`, `commands/search.py`, `adapter/base.py`, 各アダプター (GitHub/GitLab/Bitbucket/Azure DevOps), テスト

`search_code()` を `adapter/base.py` に追加。4 サービス対応。検索 API のインターフェースがサービスごとに異なる。

---

## 8. `release create --generate-notes`

**変更ファイル**: `cli.py`, `commands/release.py`, `adapter/base.py`, 各アダプター (GitHub/GitLab), テスト

`create_release()` に `generate_notes` パラメータを追加。または事前に `generate_release_notes()` でノートを生成して `notes` に渡す。

- GitHub: `generate_release_notes: true` パラメータ
- GitLab: `/repository/changelog` エンドポイントで事前生成

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
