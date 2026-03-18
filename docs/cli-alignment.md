# gfo コマンド名アラインメント検討

gfo のコマンド/サブコマンド/オプション名を他ツール（gh, glab, tea, fj）と比較し、
寄せるべきもの・現状維持すべきものを整理する。

---

## 1. サブコマンド名: `update` → `edit`

**現状**: gfo は全リソースで `update` を使用。

| リソース | gh | glab | tea | fj | gfo (現在) |
|---|---|---|---|---|---|
| pr | `edit` | `update` | `edit` | `edit` | `edit` |
| issue | `edit` | `update` | `edit` | `edit` | `edit` |
| repo | `edit` | — | — | — | `edit` |
| release | `edit` | — | `edit` | — | `edit` |
| label | `edit` | — | `edit` | — | `edit` |
| milestone | — | — | — | — | `edit` |
| comment | — | — | — | — | `edit` |
| wiki | — | — | — | — | `edit` |

**判定: `edit` に変更**

- gh / tea / fj の 3 ツールが `edit` で一致。`update` は glab のみ。
- 対象: pr, issue, repo, release, label, milestone, comment, wiki

---

## 2. `comment` / `review` の配置: 独立コマンド → pr/issue サブコマンド化

**現状**: gfo は `comment`, `review` を独立トップレベルコマンドとして提供。

| 機能 | gh | glab | tea | fj | gfo (現在) |
|---|---|---|---|---|---|
| PR コメント | `pr comment` | `mr note` | — | — | `comment create --type pr` |
| Issue コメント | `issue comment` | `issue note` | — | — | `comment create --type issue` |
| PR レビュー | `pr review` | `mr approve` | `pr approve/reject` | — | `review create` |

**判定: pr/issue のサブコマンドに移動**

- 他ツールは全て pr/issue 内のサブコマンドとして提供。独立コマンドは gfo だけ。
- `gfo pr comment list/create/edit/delete` + `gfo issue comment list/create/edit/delete`
- `gfo pr review list/create/dismiss`
- 独立コマンド `gfo comment` / `gfo review` は廃止

---

## 3. `merge --method` → 個別フラグ

**現状**: gfo は `merge --method merge/squash/rebase`。

| オプション | gh | glab | tea | fj | gfo (現在) |
|---|---|---|---|---|---|
| マージ | `--merge` | — (デフォルト) | `--style merge` | `--merge` | `--method merge` |
| スカッシュ | `--squash` | `--squash` | `--style squash` | `--squash` | `--method squash` |
| リベース | `--rebase` | `--rebase` | `--style rebase` | `--rebase` | `--method rebase` |

**判定: 個別フラグに変更**

- gh / glab / fj が個別フラグ方式で一致。`--method` を使っているのは gfo のみ。
- `--merge`, `--squash`, `--rebase` の 3 フラグに変更（排他）。

---

## 4. `--web` オプション追加

**現状**: gfo は `browse` 独立コマンドのみ。

| ツール | 実装方式 |
|---|---|
| gh | `browse` コマンド + 各コマンドに `--web` / `-w` オプション |
| glab | `--web` / `-w` オプションのみ |
| tea | `--browse` / `-b` オプションのみ |
| fj | — |

**判定: `--web` / `-w` オプションを追加**

- gh / glab が `--web` で一致。
- 既存の `browse` コマンドはそのまま維持し、`--web` を併設。

---

## 5. `pr create` オプション追加

**現状**: gfo の `pr create` は `--title`, `--body`, `--base`, `--head`, `--draft` のみ。

| オプション | gh | glab | tea | fj | gfo (現在) |
|---|---|---|---|---|---|
| `--reviewer` | Y | Y | — | — | — |
| `--assignee` | Y | Y | — | — | — |
| `--label` | Y | Y | Y | Y | — |
| `--milestone` | Y | Y | Y | — | — |
| `--fill` (自動入力) | Y | Y | — | — | — |

**判定: 追加**

- gh / glab が全てサポート。`--label` は 4 ツール全てが対応。
- ユーザーの期待値が高い基本オプション群。

---

## 6. `release create --target` 追加

**現状**: gfo の `release create` に `--target` (参照先 ref) がない。

| オプション | gh | glab | tea | fj | gfo (現在) |
|---|---|---|---|---|---|
| ターゲット ref | `--target` | `--ref` | `--target` | — | — |

**判定: `--target` として追加**

- gh / tea が `--target`、glab が `--ref`。多数派の `--target` を採用。

---

## 7. `auth logout` 追加

**現状**: gfo の `auth` は `login` / `status` のみ。

| サブコマンド | gh | glab | tea | fj | gfo (現在) |
|---|---|---|---|---|---|
| logout | Y | Y | — | — | — |

**判定: 追加**

- gh / glab が対応。認証管理の基本機能として必要。

---

## 変更なし

| 項目 | 現状 | 理由 |
|---|---|---|
| `--format` | `--format` (`table`/`json`/`plain`) | 他ツール間でコンセンサスが弱い（glab/tea は `--output`、gh/fj は `--json`）。`--format` は `docker`/`kubectl` 等でも一般的 |
| `pr reviewers` | `reviewers list/add/remove` | glab の `revoke` は承認取り消し（単一アクション）で機能が異なる。gfo は CRUD 管理で上位互換 |
| `ci trigger` | `ci trigger` | glab と一致。gh は別体系 (`workflow run`) |
| `ci logs` | `ci logs` | 3 ツールとも全て異なる形式。`logs` が最も明瞭 |
| `notification` | `notification` | tea / fj / gfo で多数派。gh の `status` が例外 |
| `browse` コマンド | `browse` | `--web` オプション追加と併設で維持 |

---

## 変更サマリー

### 破壊的変更（リネーム・移動）

| # | 変更内容 | 影響範囲 |
|---|---|---|
| 1 | `update` → `edit` (完了済み) | pr, issue, repo, release, label, milestone, comment, wiki |
| 2 | `comment` を pr/issue サブコマンドに移動 (完了済み) | comment コマンド廃止、pr/issue に統合 |
| 3 | `review` を pr サブコマンドに移動 (完了済み) | review コマンド廃止、pr に統合 |
| 4 | `merge --method` → `--merge/--squash/--rebase` | pr merge |

### 機能追加

| # | 変更内容 | 影響範囲 |
|---|---|---|
| 5 | `--web` / `-w` オプション追加 | pr view, issue view 等の各コマンド |
| 6 | `pr create` に `--reviewer/--assignee/--label/--milestone/--fill` 追加 | pr create |
| 7 | `release create --target` 追加 | release create |
| 8 | `auth logout` 追加 | auth |
