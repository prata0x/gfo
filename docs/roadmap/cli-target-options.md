# `--host` 廃止・リモート解決改善

## 1. 背景

### `--host` の問題点

`--remote` / `--host` グローバルオプション（コミット 90bf009）実装後、`--host` の設計上の問題が明らかになった。

| オプション | 取得元 | host | owner/repo | ユースケース |
|---|---|---|---|---|
| (なし) | origin | origin | origin | 通常利用 |
| `--remote NAME` | 指定リモート | リモート URL | リモート URL | マルチリモート環境 |
| `--host HOST` | origin + 上書き | **指定値** | **origin** | 同一 owner/repo ミラーのみ |

**`--host` は host だけを上書きし、owner/repo は origin 依存のまま。**
同一 owner/repo のミラー以外では使えない中途半端な抽象度となっている。

一方 `--remote` は git リモートから host/owner/repo を完全に取得できるため、リモートさえ登録すれば任意のサービスを操作可能。

### origin が存在しない環境の問題

現在の gfo は `get_remote_url(remote="origin")` をデフォルトで呼ぶため、`origin` という名前のリモートが存在しないと `--remote` なしでは失敗する。他のツールはフォールバック機構を持っており、gfo の「origin 固定」は比較的硬い設計。

---

## 2. 他ツール調査結果

### gh (GitHub CLI)

- **`-R, --repo [HOST/]OWNER/REPO`**: git 管理外でも任意のリポジトリを指定可能
- **`GH_REPO` 環境変数**: 同じ `[HOST/]OWNER/REPO` 形式
- **自動リモート解決**: `upstream` → `github` → `origin` → アルファベット順の最初のリモート
- origin が存在しなくても他のリモートにフォールバックする
- 複数リモート検出時、対話的に選択を求めて結果を永続保存

### glab (GitLab CLI)

- **`-R, --repo HOST/OWNER/REPO`**: `OWNER/REPO`、`GROUP/NAMESPACE/REPO`、フル URL も受付
- **`remote_alias` 設定**: `glab config set remote_alias origin` でデフォルトリモート名を変更可能
- git remote から自動検出 → デフォルトホスト → 最初の認証済みホストの順でフォールバック

### tea (Gitea CLI)

- **`-r, --repo SLUG`**: リポジトリスラッグを上書き
- **`-R, --remote NAME`**: 指定リモートからログイン情報を自動検出
- `$PWD` の git リポジトリからコンテキストを自動取得

### 比較表

| | gh | glab | tea | gfo (現状) |
|---|---|---|---|---|
| リポジトリ直接指定 | `--repo [HOST/]OWNER/REPO` | `--repo HOST/OWNER/REPO` | `--repo SLUG` | なし |
| リモート名指定 | 自動解決（origin 必須でない） | `remote_alias` 設定 | `--remote NAME` | `--remote NAME` |
| origin 不在時 | 他リモートにフォールバック | フォールバックあり | — | **失敗する** |

---

## 3. 検討した案と決定

### `--host` の代替案

| 案 | 概要 | メリット | デメリット |
|---|---|---|---|
| **A. 現状維持** | `--host` を残す | 追加作業ゼロ | 中途半端な抽象度。将来 `--owner`/`--repo` との組み合わせ爆発 |
| **B. `--target HOST/OWNER/REPO`** | 1オプションで完全指定 | git 管理外でも動く。`--remote` との棲み分けが明確 | Azure DevOps / Backlog のパス構造が合わない。service_type の自動検出が必要 |
| **C. `--host` + `--owner` + `--repo`** | 個別オプションで新設 | 明示的。Azure DevOps 拡張も自然 | オプション数が多い。部分指定の組み合わせルールが複雑 |
| **D. `--remote` のみ** | `--host` を廃止し何も追加しない | 最もシンプル。オプション体系が一本化 | git 管理外では使えない |

### 決定: D案（`--remote` のみ）を採用

理由:
1. **`--host` の実ユースケースが薄い**: 同一 owner/repo ミラーは `--remote` で対応可能（ミラー先を remote に追加すればよい）
2. **gfo は「git リポジトリの forge を操作するツール」** という設計思想。git 非依存で任意リポジトリを操作する方向性はスコープ外
3. 破壊的変更は `--host` 削除だけ。リリース直後なので影響は最小限
4. YAGNI: 実際に git 管理外から操作したい要望が出たときに B 案を検討すればよい

### `--repo HOST/OWNER/REPO` は将来検討

将来 git 管理外からの操作が必要になった場合に検討する。
その際の懸念点:
- Azure DevOps: `HOST/ORG/PROJECT/REPO` の4階層パス
- Backlog: `HOST/PROJECT/REPO` + スペースキー
- gfo はサービス非依存のため `HOST` を必須にする必要がある（gh は GitHub 前提で省略可）

### リモート解決のフォールバック案

| 案 | 動作 | メリット | デメリット |
|---|---|---|---|
| **案1. origin 固定（現状）** | origin のみ | 最も単純。予測可能 | origin がないと失敗 |
| **案2. origin → 最初のリモート** | origin を試し、なければ `.git/config` の最初のリモートを使用 | 非対話で完結。CI/スクリプトで安全 | 最初のリモートが意図と異なる可能性 |
| **案3. origin → 対話的選択** | origin を試し、なければユーザーに選ばせる | 確実に正しいリモートが選ばれる | CI/スクリプト環境で問題。gh は GitHub 専用だから投資価値があるが gfo では過剰 |

**推奨: 案2（origin → 最初のリモート）**

理由:
- 非対話で完結し、CI/スクリプト環境で安全に動作する
- `--remote` で明示指定できるため柔軟性は十分
- gh のように `upstream` / `github` を特別扱いする必要はない（gfo はサービス非依存）

---

## 4. 作業項目

### 4.1 `--host` 廃止（破壊的変更）

- [ ] `cli.py`: `--host` (`dest="global_host"`) オプションの削除
- [ ] `_context.py`: `cli_host` ContextVar の削除
- [ ] `detect.py`: `detect_service()` 内の `cli_host` 参照ロジックの削除
- [ ] `cli.py:main()`: `cli_host` 設定ロジックの削除
- [ ] テスト: `--host` 関連テストの削除・更新

### 4.2 リモート解決のフォールバック実装

- [ ] `git_util.py`: `get_remote_url()` に origin が見つからない場合のフォールバック追加（最初のリモートを使用）
- [ ] `git_util.py`: `get_default_branch()` も同様にフォールバック対応
- [ ] テスト: origin 不在時のフォールバック動作テスト追加

### 4.3 ドキュメント更新

- [ ] `docs/commands.md` / `docs/commands.ja.md`: `--host` オプションの記載削除
- [ ] `docs/spec.md`: `--host` 関連の記載更新
- [ ] `README.md` / `README.ja.md`: `--host` 記載があれば削除

### 4.4 ルールファイル更新

- [ ] `.claude/rules/09-config-auth.md`: `--remote` / `--host` セクションから `--host` 関連を削除し、フォールバック動作を記載

---

## 5. 未決事項

### `--repo HOST/OWNER/REPO` の設計メモ

将来このオプションを追加する場合の検討事項:

- **パース形式**: スラッシュ区切りだと Azure DevOps の `HOST/ORG/PROJECT/REPO` が4セグメントになる
  - 案A: `HOST/PATH` として host 以降をサービス依存でパース
  - 案B: URL 形式 (`https://dev.azure.com/org/project/_git/repo`) をそのまま受け付ける（既存の `detect_from_url()` を流用可能）
- **service_type の自動検出**: host から既知ホストテーブル + API プローブで判定する既存ロジックが使える
- **認証**: git config に依存しないため、`credentials.toml` または環境変数からの解決が必要
