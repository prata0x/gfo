# 設計判断の記録

gfo の CRUD 一貫性分析において、設計上の理由で意図的に提供しないコマンドを記録する。

---

## CRUD 非対応コマンド（設計上の理由で対応不要）

| コマンド | 理由 |
|---|---|
| `secret view` | シークレットは暗号化済みで読み取り不可（全サービス共通仕様） |
| `status edit` | コミットステータスは追記モデル（GitHub/GitLab 共通） |
| `pr review edit` | 投稿済みレビュー本文の編集 API が全サービスで未提供 |
| `issue time edit` | 時間エントリの修正 API が未提供。delete → re-add で代替 |
| `notification delete` | 通知の削除 API が未提供。mark-read のみ（全サービス共通） |
| `collaborator edit` | `collaborator add` の再実行で権限変更可能。専用 edit は不要 |

---

## PR edit レビュアー操作について

`pr edit --add-reviewer` / `--remove-reviewer` は提供しない。`pr reviewers add` / `pr reviewers remove` で既にカバーしている。
