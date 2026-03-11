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

## 防御的コーディング

- フィールド存在を無条件に前提しない → `data.get("field") or default`
- `assignee` 等は `isinstance(val, dict)` チェック必須
- `_to_*` 内の KeyError/TypeError は必ず GfoError でラップ
