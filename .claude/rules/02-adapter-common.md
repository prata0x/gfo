---
paths:
  - "src/gfo/adapter/**"
  - "tests/test_adapters/**"
---

# アダプター共通規約

## 新規アダプター追加チェックリスト

新規サービスをゼロから追加する際は、以下の箇所を俯瞰した上で着手すること
（個々の詳細は本ファイルの各節・`.claude/rules/03-github.md`〜`08-gitea-family.md` の
サービス別ファイルを参照）。

1. **`src/gfo/adapter/{service}.py`**: `GitServiceAdapter`（または `GitHubLikeAdapter` Mixin）を継承し `@register("{service}")` で登録
2. **`src/gfo/adapter/registry.py`**
   - `create_http_client()`（L36〜）: 認証方式の分岐を追加（`auth_header` / `auth_params` / `basic_auth` のいずれか）
   - `create_adapter()`（L68〜）: コンストラクタに追加引数（`project_key` 等）が必要な場合のみ `kwargs` 分岐を追加
3. **`tests/test_adapters/conftest.py`**: 当該サービスの `{service}_client` + `{service}_adapter` フィクスチャを追加
4. **`tests/test_adapters/test_{service}.py`**: 404/403 エラーテスト・空リスト `[]` テストを含む単体テストを新設（`.claude/rules/10-testing.md` 参照）
5. **`CLAUDE.md`**: 「対応サービス」表に識別子・認証環境変数を追記
6. **`.claude/rules/0X-{service}.md`**: サービス固有の癖（ページネーション方式、非対応 API、レスポンス形式の違い等）を新規ルールファイルとして追加
7. **i18n**: ユーザー向け文言を追加した場合 `src/gfo/locale/ja/LC_MESSAGES/gfo.po` に翻訳を追加（`.mo` はビルド時生成のため commit 不要）
8. **`docs/commands.md` / `docs/commands.ja.md`**: 新サービスでのみ有効なオプションや挙動差があれば追記

## 継承ツリーと登録

```
GitServiceAdapter (ABC, adapter/base.py)
├── GitHubAdapter           @register("github")      ※ GitHubLikeAdapter Mixin を併用
│   └── GitBucketAdapter    @register("gitbucket")
├── GitLabAdapter           @register("gitlab")
├── BitbucketAdapter        @register("bitbucket")
├── BacklogAdapter          @register("backlog")
├── AzureDevOpsAdapter      @register("azure-devops")
└── GiteaAdapter            @register("gitea")       ※ GitHubLikeAdapter Mixin を併用
    ├── ForgejoAdapter      @register("forgejo")
    └── GogsAdapter         @register("gogs")
```

- `GitHubAdapter` / `GiteaAdapter` は `class XxxAdapter(GitHubLikeAdapter, GitServiceAdapter)` の多重継承。
- `GitBucketAdapter` は **`GitHubAdapter` のサブクラス**（`GiteaAdapter` ではない。GitBucket は GitHub API 互換のため）。
- `GitHubLikeAdapter`（`adapter/github_like.py`）は GitHub/Gitea 系の共通 `_to_*` 変換ヘルパー Mixin。
  `base.py` 末尾の `GitHubLikeAdapter` は後方互換の再 export であり、定義の実体ではない。

## 共有シンボルの import 経路（正典）

新規アダプターは既存の具象アダプターと同じ経路で import すること:

| シンボル | 経路 |
|---|---|
| `GitServiceAdapter`, `_wrap_conversion_error`, `_mask_token_in_exception` | `from .base import ...`（実体は `_helpers.py` だが `base.py` が再 export） |
| データクラス（`PullRequest` 等） | `from .models import ...` |
| `GitHubLikeAdapter`（GitHub/Gitea 系のみ） | `from .github_like import ...` |

`github_like.py` 自身だけは `base.py` との循環参照回避のため `._helpers` から直接 import している。アダプター実装はこれを真似しないこと。

## データクラス規約

全データクラスは `adapter/models.py` に集約する（標準ライブラリ以外に依存しない）。
すべて `frozen=True, slots=True` の `@dataclass`:
`PullRequest`, `Issue`, `Repository`, `Release`, `Label`, `Milestone` ほか

## list_milestones の state パラメータ

`list_milestones(*, state: str = "open", limit: int = 0)`。GitHub/Gitea は `state` クエリパラメータ
省略時に `open` のみを返す（`state=all` を明示しないと closed マイルストーンが一切取得できない）。
GitLab は `state` パラメータの値が `active`/`closed` のみで `open`/`all` という値は無く、
省略時に全件（active + closed）を返す。そのため `GitLabAdapter.list_milestones()` は
`"open"→"active"`、`"closed"→"closed"`、`"all"→` パラメータ省略、とマッピングしている。
Bitbucket/Backlog/Azure DevOps/Gogs は milestones 自体が `NotSupportedError` のため `state` は未使用。

- 過去バグ（#206）: GitHub/Gitea の `list_milestones()` が `state` を一切送信しておらず、
  closed マイルストーンが `gfo milestone list` にも `_resolve_milestone_id_by_title`
  （`--milestone <title>` でのタイトル解決）にも一切現れなかった。後者は `state="all"` で
  明示的に問い合わせるよう修正済み（`base.py: _resolve_milestone_id_by_title`）。

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

## get_pipeline_logs のジョブ/ステップ一覧取得

`get_pipeline_logs(pipeline_id, *, job_id=None)` の `job_id` 未指定分岐（パイプライン/ビルド全体のログを
まとめて取得するパス）は、ジョブ/ステップ一覧の取得に必ず同一ファイル内の他の一覧系メソッドと同じ
ページネーションヘルパーを使うこと。素の `self._client.get(...)` 1 回だけで完結させてはいけない。

- 過去バグ（#145, #146）: GitLab（`paginate_page_param`）・GitHub（手動 `per_page`/`page` ループ）・
  Azure DevOps（`paginate_top_skip`）・Bitbucket（`paginate_response_body`）の4アダプターすべてで、
  `get_pipeline_logs` だけが自身のファイル内の他メソッドが使うページネーションを素通りしており、
  各サービスのデフォルトページサイズ（GitLab/Gitea: 20件、GitHub: 30〜100件、Azure DevOps: `$top`
  デフォルト100件、Bitbucket: `pagelen` デフォルト値）を超えるジョブ/ステップ数のパイプラインで、
  ページ境界以降のログがエラーも警告も無く黙って欠落していた

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

## HTTP タイムアウト・リトライ

- **タイムアウト**: 全リクエストに `timeout=30` を指定（`requests` のデフォルトは None＝無制限）
- **リトライ**: 429（レート制限）のみ自動リトライ（最大 1 回）。`Retry-After` ヘッダ尊重、未指定時は 60 秒待機
- **その他の HTTP エラー**: リトライなし

## 防御的コーディング

- フィールド存在を無条件に前提しない → `data.get("field") or default`
- `assignee` 等は `isinstance(val, dict)` チェック必須
- `_to_*` 内の KeyError/TypeError は必ず GfoError でラップ
