# ドキュメントレビュー: docs/ (76b4712..c4fbefd)

**対象コミット**: 76b4712 → c4fbefd（10 コミット）
**レビュー日**: 2026-03-19
**対象**: `docs/` 配下 11 ファイル（変更 10 + 新規 1）

## 対象コミット一覧

| コミット | 概要 |
|---|---|
| `83669f8` | feat!: update サブコマンドを edit にリネーム（全 8 コマンド） |
| `b0ce8f4` | feat!: comment コマンドを pr/issue サブコマンドに移動 |
| `2b28bc4` | feat!: review コマンドを pr サブコマンドに移動 |
| `90d12b3` | feat!: pr merge の --method を --merge/--squash/--rebase 個別フラグに変更 |
| `e897578` | feat: view/list サブコマンドに --web/-w オプションを追加 |
| `15a4255` | feat: pr create に --reviewer/--assignee/--label/--milestone/--fill オプションを追加 |
| `b974ec1` | feat: release create に --target オプションを追加 |
| `2a740c5` | docs: auth-multi-account ロードマップ追加 & auth-logout をリナンバー |
| `2638849` | feat!: credentials.toml をマルチアカウント対応の新形式に変更 |
| `c4fbefd` | feat: auth logout サブコマンドを追加 |

## 変更ファイル一覧

| ファイル | 変更種別 |
|---|---|
| `docs/commands.md` | 大規模更新（edit リネーム, comment/review 移動, 新コマンド追加） |
| `docs/commands.ja.md` | 同上（日本語版） |
| `docs/authentication.md` | マルチアカウント対応追加, credentials.toml 新形式 |
| `docs/authentication.ja.md` | 同上（日本語版） |
| `docs/cli-alignment.md` | 完了ステータス更新, ロードマップ番号変更 |
| `docs/cli-comparison.md` | edit リネーム反映, comment/review 配置変更, 新機能反映 |
| `docs/integration-testing.md` | update → edit 表記修正 |
| `docs/integration-testing.ja.md` | 同上（日本語版） |
| `docs/spec.md` | release create --target 追加, edit 表記修正 |
| `docs/roadmap/8-auth-multi-account.md` | **新規追加**（マルチアカウント設計ドキュメント） |
| `docs/roadmap/9-auth-logout.md` | リネーム（旧 8-auth-logout.md → 9） |

---

## 評価サマリー

### 良い点

- **EN/JA の同期が完璧**: `commands.md` / `commands.ja.md`、`authentication.md` / `authentication.ja.md`、`integration-testing.md` / `integration-testing.ja.md` すべてで英語版と日本語版の内容が正確に対応している
- **破壊的変更の反映が網羅的**: `update → edit` リネームが commands, cli-comparison, integration-testing の全箇所で漏れなく反映されている
- **コマンド移動の文書化が丁寧**: `comment` / `review` の独立コマンド廃止 → pr/issue サブコマンド化に伴い、旧セクションの削除と新セクションの追加が正確に行われている
- **credentials.toml の新形式ドキュメントが明確**: authentication.md / authentication.ja.md で新しいテーブル形式の TOML 記法が分かりやすく記載されている
- **トークン解決順序の文書化**: 5 段階の解決順序が authentication.md に明記され、実装 (`auth.py:_resolve_account_name`) と完全に一致
- **roadmap/8-auth-multi-account.md の設計ドキュメントが充実**: 新フォーマット、解決順序、実装手順が網羅的に記載されている

---

## 指摘事項

### P1: 実装との不整合（修正必須）

#### 1. spec.md: `pr merge` が旧 `--method` 形式のまま

**箇所**: `docs/spec.md:157-162`

```
gfo pr merge <number> [--method merge|squash|rebase]
```

**実装**: `cli.py` では `--merge` / `--squash` / `--rebase` の相互排他フラグに変更済み。`--method` は存在しない。

**修正案**:

```
gfo pr merge <number> [--merge | --squash | --rebase]
```

#### 2. spec.md: `pr create` に新オプションが未記載

**箇所**: `docs/spec.md:135`

```
gfo pr create [--title T] [--body B] [--base BRANCH] [--head BRANCH] [--draft]
```

**実装**: `cli.py` に `--reviewer`, `--assignee`, `--label`, `--milestone`, `--fill` が追加済み。

**修正案**:

```
gfo pr create [--title T] [--body B] [--base BRANCH] [--head BRANCH] [--draft] [--reviewer USER] [--assignee USER] [--label NAME] [--milestone NAME] [--fill]
```

#### 3. spec.md: `auth login` に `--account` が未記載

**箇所**: `docs/spec.md:90`

```
gfo auth login [--host HOST] [--token TOKEN]
```

**実装**: `cli.py` に `--account` オプションが追加済み（`default="default"`）。

**修正案**:

```
gfo auth login [--host HOST] [--token TOKEN] [--account ACCOUNT]
```

#### 4. spec.md: `auth switch` / `auth logout` サブコマンドが未記載

**箇所**: `docs/spec.md:83-108`（auth セクション）

auth セクションに `login` と `status` しか記載されていない。`switch` と `logout` は実装済みだが spec.md に反映されていない。

#### 5. spec.md: credentials.toml が旧フラット形式のまま

**箇所**: `docs/spec.md:449-455`

```toml
[tokens]
"github.com" = "ghp_xxxx"
"gitlab.example.com" = "glpat-xxxx"
```

**実装**: 新テーブル形式（`[tokens."{host}"]` にアカウント名キー + `_default`）に変更済み。

**修正案**: `authentication.md` と同じ新形式に更新。

#### 6. spec.md: トークン解決順序にアカウント解決が未記載

**箇所**: `docs/spec.md:471-484`

旧形式の解決順序（credentials.toml → 環境変数 → GFO_TOKEN）のみ。マルチアカウント対応のアカウント解決ステップが欠落している。

#### 7. cli-comparison.md: 「レビューは独立コマンド」が不正確

**箇所**: `docs/cli-comparison.md:386`

```
| **コメント/レビュー** | PR コマンドに内包 | — | コメントは pr/issue サブコマンド、レビューは独立コマンド |
```

**実態**: `gfo review` は廃止され、`gfo pr review` に移動済み。同じファイル内の L57 では正しく `Y (pr 内)` と記載されており、L386 と矛盾。

**修正案**:

```
| **コメント/レビュー** | PR コマンドに内包 | — | コメント・レビューとも pr/issue サブコマンド |
```

---

### P2: ステータス更新漏れ（修正推奨）

#### 8. cli-alignment.md: サマリーテーブルの完了マーカー不足

**箇所**: `docs/cli-alignment.md:148, 154, 157, 158`

以下の項目が実装済みだが、サマリーテーブルに `(完了済み)` マーカーがない:

| # | 項目 | 状態 |
|---|---|---|
| 4 | `merge --method` → 個別フラグ | セクション 3 に ✅ あるがサマリーに反映なし |
| 5 | `--web / -w` オプション追加 | セクション未更新、サマリーに反映なし |
| 8 | `auth multi-account` | 実装済みだがサマリーに反映なし |
| 9 | `auth logout` | セクション 7 に ✅ あるがサマリーに反映なし |

#### 9. cli-alignment.md: セクション 4（`--web / -w`）と 6（`release create --target`）に ✅ マーカーなし

**箇所**: `docs/cli-alignment.md:63, 97`

セクション見出しが未完了のままだが、両機能とも実装済み。セクション 3, 5, 7 と同様に ✅ と取り消し線での更新が必要。

#### 10. cli-alignment.md: セクション 1, 2 の「現状」テキストが更新前のまま

**箇所**: `docs/cli-alignment.md:10, 32`

セクション 3, 5 では取り消し線（`~~旧テキスト~~`）で更新されているが、セクション 1 は「**現状**: gfo は全リソースで `update` を使用。」、セクション 2 は「**現状**: gfo は `comment`, `review` を独立トップレベルコマンドとして提供。」のまま。テーブルの gfo 列は更新済みなのでテキストとの不整合がある。

#### 11. spec.md: 「edit を将来バージョンで対応予定」が不正確

**箇所**: `docs/spec.md:315`

```
**注記**: release / label / milestone は edit を将来バージョンで対応予定。
```

`edit`（旧 `update`）は全リソースで実装済み。この注記は削除するか「実装済み」に更新すべき。

---

### P3: ロードマップの鮮度（対応任意）

#### 12. roadmap/9-auth-logout.md: 実装済みだが内容がロードマップのまま

**箇所**: `docs/roadmap/9-auth-logout.md` 全体

`auth logout` は実装済み（`auth.py:remove_token`, `auth_cmd.py:handle_logout`）だが、ロードマップは「これから実装する」形式のまま。

具体的な乖離点:
- L22: `remove_token(host: str) -> bool` → 実装は `remove_token(host: str, account: str | None = None) -> None`
- L46: `--host` のみ記載 → 実装は `--host` + `--account`
- マルチアカウント対応が反映されていない

**対応案**: ステータスを「完了」に更新するか、実装後の仕様で内容を書き換える。

#### 13. roadmap/8-auth-multi-account.md: 実装済みだがステータスが未更新

**箇所**: `docs/roadmap/8-auth-multi-account.md:1-5`

マルチアカウント機能は実装済み（credentials.toml 新形式、auth switch、--account オプション等）だが、ロードマップのステータスフィールドがない。完了を示すマーカーの追加が望ましい。

---

## 修正優先度まとめ

| 優先度 | 件数 | 対象 | 概要 |
|---|---|---|---|
| **P1** | 7 件 | spec.md (6), cli-comparison.md (1) | 実装との不整合。spec.md は複数箇所で旧仕様のまま残存 |
| **P2** | 4 件 | cli-alignment.md (3), spec.md (1) | ステータス更新漏れ。完了マーカーや取り消し線の未反映 |
| **P3** | 2 件 | roadmap/ (2) | ロードマップの鮮度。実装後の内容が未反映 |

**最も影響が大きいのは spec.md**: 6 件の P1 指摘すべてが同一ファイルに集中しており、仕様書としての信頼性に関わる。auth セクション（login の --account、switch / logout の追加）、pr セクション（merge フラグ、create オプション）、認証情報セクション（credentials.toml 新形式、トークン解決順序）の 3 領域を一括で更新すべき。
