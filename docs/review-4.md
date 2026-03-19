# Review 4: コミット 76b4712..c4fbefd

## 対象コミット（10件）

| コミット | 概要 |
|---|---|
| 83669f8 | `update` サブコマンドを `edit` にリネーム（全 8 コマンド） |
| b0ce8f4 | `comment` コマンドを `pr`/`issue` サブコマンドに移動 |
| 2b28bc4 | `review` コマンドを `pr` サブコマンドに移動 |
| 90d12b3 | `pr merge` の `--method` を `--merge`/`--squash`/`--rebase` 個別フラグに変更 |
| e897578 | `view`/`list` サブコマンドに `--web`/`-w` オプションを追加 |
| 15a4255 | `pr create` に `--reviewer`/`--assignee`/`--label`/`--milestone`/`--fill` オプションを追加 |
| b974ec1 | `release create` に `--target` オプションを追加 |
| 2a740c5 | auth-multi-account ロードマップ追加 & auth-logout をリナンバー |
| 2638849 | credentials.toml をマルチアカウント対応の新形式に変更 |
| c4fbefd | `auth logout` サブコマンドを追加 |

## 変更規模

- **59 ファイル変更** (+3,367 / -767 行)
- プロダクションコード: アダプター 9 ファイル、コマンド 10 ファイル、コアモジュール 4 ファイル
- テストコード: 22 ファイル
- ドキュメント: 10 ファイル

---

## 総合評価

全体として品質の高い変更群。CLI の命名統一（`update` → `edit`）、コマンド階層の再構成（`comment`/`review` → `pr`/`issue` サブコマンド化）、マルチアカウント認証と、いずれも設計が一貫している。テストカバレッジも十分で、各変更に対応するテストが網羅されている。

以下、カテゴリごとの詳細レビュー。

---

## 1. CLI 命名統一: `update` → `edit` (83669f8)

### 良い点
- `gh` CLI との整合性を取る妥当な判断
- 全 8 コマンド（pr, issue, repo, release, label, milestone, wiki, comment）を漏れなく一括リネーム
- `_DISPATCH` テーブル、`_OUTPUT_MAP`（schema.py）も同期更新済み

### 指摘なし

---

## 2. コマンド階層の再構成: comment/review → pr/issue サブコマンド (b0ce8f4, 2b28bc4)

### 良い点
- `gfo comment list pr 1` → `gfo pr comment list 1` への移行は直感的
- `comment.py` を `_dispatch()` による共通処理化で PR/Issue 両対応にしたのは綺麗な設計
- `review.py` にも `handle_review()` ディスパッチャを追加し、同じパターンに統一

### 指摘事項

#### [低] schema.py の OUTPUT_MAP が不正確
`("pr", "comment")` と `("issue", "comment")` の型が `list[Comment]` になっているが、`create`/`edit` アクション時は単一の `Comment` を返し、`delete` 時は `None` を返す。サブコマンド内でアクションが分岐するため、単一の型では正確に表現できない。`("pr", "review")` も同様に `list[Review]` だが、`create` 時は `Review`、`dismiss` 時は `None`。

現時点で schema が実行時に動的利用されていなければ実害はないが、将来 OpenAPI 生成やバリデーションに利用する場合は問題になりうる。

---

## 3. pr merge のフラグ変更: --method → --merge/--squash/--rebase (90d12b3)

### 良い点
- `mutually_exclusive_group` で排他制約を正しく設定
- デフォルト動作（フラグなし → `merge`）が明確
- `gh pr merge` と同じ UX に揃えている

### 指摘なし

---

## 4. --web/-w オプション (e897578)

### 良い点
- `get_web_url()` のシグネチャを `number: int | str | None` に拡張し、リスト URL（`number=None`）とリリースタグ（`str`）に対応
- 全 9 サービスアダプターの `get_web_url()` に release/milestone サポートを追加
- 非対応サービス（Bitbucket release/milestone、Azure DevOps release/milestone 等）では `NotSupportedError` を適切に raise
- テスト（test_browse.py）が全サービス × 全リソース × list/detail で網羅的

### 指摘事項

#### [低] webbrowser.open の重複パターン
各コマンドハンドラ（pr.py, issue.py, milestone.py, release.py, repo.py）で `--web` の処理が毎回同じパターンでインライン実装されている:

```python
if getattr(args, "web", False):
    import webbrowser
    adapter = get_adapter()
    webbrowser.open(adapter.get_web_url("pr", args.number))
    return
```

現時点では小さなコード重複だが、6 箇所以上ある。ただし、各ハンドラで引数の取り方が微妙に違う（`args.number`、`args.tag`、引数なし等）ため、共通化するとかえって複雑になる可能性もあり、現状のままでも許容範囲。

#### [低] release view --web --latest のダブルフェッチ
`release.py:handle_view()` で `--web --latest` の場合、`get_latest_release()` で API を叩いてタグ名を取得した後 `return` する。同じ関数の後半（非 --web パス）でも `--latest` の場合に `get_latest_release()` を再度呼ぶが、--web パスでは早期 return するので問題はない。ただし、--web なしのパスでは `get_web_url` を呼ばないため影響なし。

---

## 5. pr create の拡張オプション (15a4255)

### 良い点
- `--reviewer`/`--assignee` は `action="append"` で複数指定可能
- サービスごとに対応状況が異なる実装を各アダプターで適切に処理:
  - GitHub: PR 作成後に issues API で labels/assignees/milestone を PATCH、別途 reviewers API を POST
  - GitLab: `create_pull_request()` のペイロードに直接 `reviewer_ids`/`assignee_ids`/`labels`/`milestone_id` を含める
  - Gitea: labels は ID 解決（`_resolve_label_ids`）、milestone もタイトルから ID 解決
  - Bitbucket: reviewers のみ対応（ペイロードに直接含める）
  - Azure DevOps: reviewers のみ対応（作成後に個別 PUT）
  - Backlog/GitBucket/Gogs: 未対応オプションは無視（サイレントに無視）
- `--fill` で最後のコミットの body を使う実装、`get_last_commit_body()` を `git_util.py` に追加
- ラベル/マイルストーン名が見つからない場合は `GfoError` で明確にエラー

### 指摘事項

#### [中] 未対応オプションのサイレント無視
Backlog、GitBucket、Gogs で `reviewers`/`assignees`/`labels`/`milestone` がサイレントに無視される。ユーザーが `--reviewer alice` を指定しても何もフィードバックがない。`warnings.warn()` や `NotSupportedError` でユーザーに通知する方が親切。

ただし、`gh` CLI も非対応オプションを無視するケースがあるため、設計方針としてはあり。

#### [中] create_pull_request の戻り値が追加操作を反映しない
GitHub アダプターで `create_pull_request()` は PR 作成直後の `PullRequest` オブジェクトを返すが、その後 labels/assignees/milestone の PATCH や reviewers の POST を行っている。戻り値にはこれらの追加情報が反映されていない。Gitea でも reviewers は PR 作成後に設定されるため同様。

CLI の `output(pr, ...)` で表示される内容には labels 等のフィールドが含まれない可能性がある。実害は表示上の問題のみで機能的には問題なし。

#### [低] base.py の抽象メソッドシグネチャ変更の互換性
`create_pull_request()` の抽象メソッドに `reviewers`/`assignees`/`labels`/`milestone` が追加された。全サブクラスが更新済みであることは差分から確認できる。外部でサブクラスを作成しているユーザーがいれば破壊的変更だが、内部プロジェクトなので問題なし。

---

## 6. release create --target (b974ec1)

### 良い点
- GitHub/Gitea/GitBucket は `target_commitish`、GitLab は `ref` に正しくマッピング
- `target=None` 時はペイロードにキーを含めない（既存動作を変更しない）
- GitLab は既存の `ref = repo.default_branch or "main"` を `target or repo.default_branch or "main"` に変更し、`--target` 指定時のみオーバーライド
- Backlog/Azure DevOps/Gogs はリリース非対応なので `NotSupportedError` のまま

### 指摘なし

---

## 7. マルチアカウント認証 (2638849, c4fbefd)

### 良い点
- credentials.toml の形式を `"host" = "token"` (フラット) から `[tokens."host"]` セクション (ネスト) に変更
- アカウント解決の優先順位が明確:
  1. `--account` ContextVar
  2. `git config gfo.account`
  3. `config.toml` の `hosts.{host}.account`
  4. `_default` キー
  5. フォールバック `"default"`
- `save_token()`/`switch_account()`/`list_accounts()`/`remove_token()` の CRUD が完備
- `remove_token()` で最後のアカウント削除時にホストごと削除するロジックが正しく実装
- `_default` が削除対象アカウントを指していた場合の自動フォールバック
- パーミッション設定を `_set_credentials_permissions()` に共通化
- TOML エスケープも `_escape_toml_value()` に共通化
- テストが非常に充実（resolve_token のアカウント解決 6 パターン、switch/list/remove のエッジケース）

### 指摘事項

#### [高] 旧形式 credentials.toml の後方互換性なし
`load_tokens()` のフィルタが `isinstance(v, dict)` のみを通すため、旧形式の `"github.com" = "ghp_abc"` は完全に無視される。既存ユーザーがアップデートすると、設定済みトークンが「消える」ように見える。

```python
return {
    str(k): {str(ak): str(av) for ak, av in v.items()}
    for k, v in tokens.items()
    if isinstance(v, dict)
}
```

テスト `test_load_tokens_ignores_flat_values` で意図的に空 dict を返すことが確認されている。これが意図的な設計であれば、マイグレーションガイドまたは `gfo auth migrate` コマンドが必要。Breaking change としてコミットメッセージに `feat!:` が付いているので認識はされている。

**推奨**: 旧形式検出時に警告メッセージを表示し、`gfo auth login` で再登録を促す、あるいは自動マイグレーション機能を提供する。

#### [中] `_resolve_account_name` の遅延 import
```python
def _resolve_account_name(host: str, host_accounts: dict[str, str]) -> str:
    ...
    try:
        import gfo.git_util
        git_account = gfo.git_util.git_config_get("gfo.account")
    ...
    try:
        import gfo.config
        host_cfg = gfo.config.get_host_config(host)
```

循環 import 回避のためと思われるが、各呼び出し時に `import` を実行する。Python のモジュールキャッシュにより実行時のパフォーマンス影響は軽微だが、循環依存の存在自体が設計上の注意点。

#### [中] `switch_account` で `"_default"` を引数として渡せる
`switch_account("github.com", "_default")` と呼ぶと、`_default` が通常のアカウント名として扱われる（`account not in host_accounts` チェックは `"_default" in host_accounts` → True なのでパスする）。結果として `_default = "_default"` という奇妙な状態になる。

**推奨**: `if account == "_default": raise ConfigError(...)` のバリデーションを追加。

#### [低] `save_token` のホスト小文字正規化の欠落
`save_token()` は引数 `host` をそのまま使っている。一方、`resolve_token()` は `host = host.lower()` で正規化している。テスト `test_save_token_uppercase_host_normalized` は `save_token` が小文字化することを確認しているが、実装を見ると `save_token` 内に `host = host.lower()` がない。

→ 再確認: `save_token` の先頭に `host = host.lower()` の行が diff には見えないが、テストが通っているということは、`save_token` 内のどこかで正規化されているか、テスト側が小文字で渡している可能性がある。要確認。

---

## 8. auth logout (c4fbefd)

### 良い点
- `--host` 省略時は `detect_service()` でホスト自動検出（login/switch と同じパターン）
- `--account` 指定でアカウント単位の削除、省略でホスト全体削除
- 検出失敗時は `ConfigError` で `--host` の使用を促すメッセージ
- テストカバレッジ（成功・ホスト検出失敗・ConfigError 伝搬・アカウント指定）

### 指摘なし

---

## 9. gfo init --account (2638849 に含まれる)

### 良い点
- `git config gfo.account` にアカウント名を書き込む仕組み
- 対話/非対話の両パスで同じ処理

### 指摘事項

#### [低] init --account の使い方がドキュメント化されていない
`init` の `--account` オプションは `git config gfo.account` を設定するが、ヘルプメッセージが `"Account name to associate"` のみで、マルチアカウント機能との関係が分かりにくい。

---

## 10. テスト

### 良い点
- 新機能すべてに対応するテストが追加されている
- エッジケース（存在しないホスト/アカウント、ラベル/マイルストーン未発見、最後のアカウント削除等）が網羅的
- test_browse.py は全 9 サービス × 全リソースタイプ × list/detail をカバー
- `_new_format_toml`/`_multi_host_toml` ヘルパーでテストの可読性を維持

### 指摘事項

#### [低] DISPATCH テーブルのエントリ数コメントが不正確
`test_cli.py` の `test_dispatch_table_has_68_entries` はアサート値 `145` で `# auth logout 追加` とコメントしているが、関数名は `has_68_entries` のまま。コメントと関数名の乖離が大きい。

---

## 11. ドキュメント

### 良い点
- `commands.md` / `commands.ja.md` が全変更に同期
- `authentication.md` / `authentication.ja.md` がマルチアカウントのワークフローを説明
- ロードマップ `8-auth-multi-account.md` が追加され、今後の計画が明確

---

## まとめ: 指摘一覧

| 重要度 | カテゴリ | 内容 |
|---|---|---|
| 高 | auth | 旧形式 credentials.toml がサイレントに無視される（マイグレーション手段なし） |
| 中 | auth | `switch_account("host", "_default")` で不正な状態になりうる |
| 中 | auth | `_resolve_account_name` の遅延 import（循環依存の兆候） |
| 中 | pr create | 未対応サービスで `--reviewer` 等がサイレントに無視される |
| 中 | pr create | 戻り値が追加操作（labels/reviewers 設定）を反映しない |
| 低 | schema | comment/review の OUTPUT_MAP 型が実際の戻り値と一致しない |
| 低 | web | `webbrowser.open` の処理パターンが 6+ 箇所で重複 |
| 低 | auth | `save_token` のホスト名小文字正規化の有無が不明確 |
| 低 | test | `test_dispatch_table_has_68_entries` の関数名とアサート値が乖離 |
| 低 | docs | `init --account` の用途がドキュメント不足 |
