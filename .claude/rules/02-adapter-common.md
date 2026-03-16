---
paths:
  - "src/gfo/adapter/**"
  - "tests/test_adapters/**"
---

# アダプター共通規約

## 継承ツリーと登録

```
GitServiceAdapter (ABC, adapter/base.py)
├── GitHubAdapter           @register("github")
├── GitLabAdapter           @register("gitlab")
├── BitbucketAdapter        @register("bitbucket")
├── BacklogAdapter          @register("backlog")
├── AzureDevOpsAdapter      @register("azure-devops")
└── GiteaAdapter            @register("gitea")
    ├── ForgejoAdapter      @register("forgejo")
    ├── GogsAdapter         @register("gogs")
    └── GitBucketAdapter    @register("gitbucket")
```

`GitHubLikeAdapter`（`adapter/base.py`）は GitHub/Gitea 系の共通 `_to_*` 変換ヘルパー Mixin。

## データクラス規約

すべて `frozen=True, slots=True` の `@dataclass`:
`PullRequest`, `Issue`, `Repository`, `Release`, `Label`, `Milestone`

## create_or_update_file の戻り値

戻り値型: `str | None`。**commit SHA を返せるアダプターは必ず返すこと。**

| アダプター | 返す値 |
|---|---|
| GitHub / Gitea / Forgejo | `commit.sha`（PUT/POST レスポンス） |
| Azure DevOps | `commits[0].commitId`（pushes API レスポンス） |
| GitLab / Bitbucket / Gogs / その他 | `None`（API が SHA を返さない） |

理由: ブランチ HEAD の伝播遅延を回避するため。commit SHA を `ref` に指定すればオブジェクトを直接参照できる。

## ページネーション方式（`http.py`）

| 方式 | 使用サービス |
|---|---|
| `Link` ヘッダ | GitHub 形式 |
| `X-Next-Page` ヘッダ | GitLab 形式 |
| `startPosition` クエリパラメータ | Backlog 形式 |
| `continuationToken` | Azure DevOps 形式 |
| オフセット形式（汎用） | Gitea 系 |

## 出力・フィルタ規約

- **`--jq` 対応必須**: 全ハンドラで `jq` 引数を出力に接続すること（シグネチャだけ広げて未接続は禁止）
- **`list[str]` / `dict` を返すハンドラ**: `output()` は使えない → `apply_jq_filter` を直接適用すること
- **limit 適用順序**: フィルタ後に limit を適用すること（フィルタ前に適用すると結果が過少になる）

## upsert パターン

- **set 系メソッド**（`set_variable`, `set_secret` 等）: GET で存在チェック → PUT（更新）/ POST（新規作成）を使い分けること
  - POST のみだと既存リソースで API エラーになる

## メソッド・コード規約

- **メソッドシグネチャ**: `**kwargs` で受けず、`base.py` と同じ明示的キーワード引数にすること
- **`from __future__ import annotations`**: 全 `commands/*.py` に必須
- **Organization.url**: API URL ではなく Web URL を返すこと
- **削除/書き込みハンドラ**: 成功メッセージを `print()` すること（既存の label/release/issue に倣う）

## 防御的コーディング

- フィールド存在を無条件に前提しない → `data.get("field") or default`
- `assignee` 等は `isinstance(val, dict)` チェック必須
- `_to_*` 内の KeyError/TypeError は必ず GfoError でラップ
