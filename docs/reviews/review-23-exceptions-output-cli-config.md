# gfo Review Report — Round 23: exceptions / output / cli / config 精査

## 概要

- **レビュー日**: 2026-03-09
- **対象**:
  - `src/gfo/exceptions.py` — 例外クラス定義
  - `src/gfo/output.py` — 出力モジュール
  - `src/gfo/cli.py` — CLI エントリポイント
  - `src/gfo/config.py` — 設定モジュール
  - `tests/test_commands/test_repo.py`、`test_release.py`、`test_auth_cmd.py`

- **発見事項**: 新規 7 件（重大 1 / 中 4 / 軽微 2）、既知課題 2 件の現状確認

---

## 既知残課題の現状確認

| ID | 状態 |
|----|------|
| R16-02 | `auth.py` `get_auth_status()` の env var エントリ host 形式が `"env:github"` と `"github.com"` で不統一 — **継続中** |
| R13-03 | `gitea.py` `list_issues` フィルタ後 limit 未満 — **継続中（設計決定待ち）** |

---

## 修正済み・問題なし確認（OK）

| ファイル | 確認項目 | 結果 |
|---------|---------|------|
| `exceptions.py` | 例外階層・メッセージ・属性 | OK — 継承階層・エラーメッセージは適切 |
| `output.py` テスト | テーブル/JSON/plain フォーマット | OK — 既存テスト全通過 |
| `release.py` コマンド | タグ・タイトル・ノート処理 | OK — テスト 9 件全通過 |

---

## 新規発見事項

---

### [R23-01] 🔴 `config.py` L116 — `resolve_project_config` の条件分岐ロジックが逆になっている

- **ファイル**: `src/gfo/config.py` L116
- **現在のコード**:
  ```python
  if saved_type and saved_host:
      # git config から既知の type/host がある場合、remote URL から owner/repo を取得
      try:
          remote_url = gfo.git_util.get_remote_url(cwd=cwd)
          detect_result = gfo.detect.detect_from_url(remote_url)
          owner = detect_result.owner
          repo = detect_result.repo
          ...
      except (...):
          owner = ""
          repo = ""
  else:
      # 未設定なら detect_service() で全自動検出
      detect_result = gfo.detect.detect_service(cwd=cwd)
      ...
  ```
- **説明**: `if saved_type and saved_host:` ブランチは「git config に type/host が保存済み」のケースを処理している。このとき `detect_from_url()` で owner/repo だけを補完するのは意図的な設計のように見える。ただし `except` でキャッチされる例外の種類と URL 解析失敗時の owner="" フォールバックが、後続の API 呼び出しで空の owner/repo を送信する問題を引き起こす可能性がある。コメントが実装と不一致になっており意図の確認が必要。
- **影響**: git config に type/host が保存されているが remote URL が取れない環境（CI/CD や bare リポジトリ等）で、owner="" repo="" のまま API 呼び出しが行われる可能性がある。
- **推奨修正**: `except` 時のフォールバックに config.toml の `[repo]` セクションから owner/repo を読み込む処理を追加するか、ConfigError を送出する。

---

### [R23-02] 🟡 `auth.py` L140 — `get_auth_status` の host 形式不統一（R16-02 詳細確認）

- **ファイル**: `src/gfo/auth.py` L140
- **現在のコード**:
  ```python
  result.append({
      "host": f"env:{service_type}",  # 例: "env:github"
      "source": f"env:{env_var}",     # 例: "env:GITHUB_TOKEN"
  })
  ```
- **説明**: credentials.toml エントリの `host` は `"github.com"` 形式だが、環境変数エントリは `"env:github"` 形式。`gfo auth status` 出力で一貫性を欠く。
- **影響**: UI/UX の混乱。host フィールドの意味が一貫しない。
- **推奨修正**: `_SERVICE_DEFAULT_HOSTS` 辞書を追加して実ホスト名に変換する。

---

### [R23-03] 🟡 `output.py` L44 — 空データ時の出力が stdout/stderr で不統一

- **ファイル**: `src/gfo/output.py` L44-49
- **現在のコード**:
  ```python
  if not items:
      if fmt == "json":
          print("[]")          # stdout
      else:
          print("No results found.", file=sys.stderr)  # stderr
      return
  ```
- **説明**: JSON 形式では stdout に `[]` を出力するが、table/plain 形式では stderr に "No results found." を出力する。パイプ処理で stderr を無視する場合に結果が食い違う。
- **影響**: `gfo issue list | jq` のようなパイプ処理で table/plain の場合、出力なしになる。
- **推奨修正**: 全形式で stdout に統一する（table/plain も `[]` か空行を stdout に出力）、または全形式で stderr に統一する。

---

### [R23-04] 🟢 `output.py` L68 — `dataclasses.asdict()` に非 dataclass が渡された場合の例外処理不備

- **ファイル**: `src/gfo/output.py` L68
- **説明**: `dataclasses.asdict()` は dataclass 以外に対して `TypeError` を送出するが、`output()` 関数では入力型のチェックを行っていない。呼び出し側が誤った型を渡した場合、不明確なエラーメッセージになる。
- **影響**: 軽微。通常の使用では発生しない。
- **推奨修正**: `dataclasses.is_dataclass(item)` でチェックするか、`TypeError` をキャッチして分かりやすいメッセージを出す。

---

### [R23-05] 🟡 `cli.py` — 統合テスト（test_cli.py）のカバレッジ 0%

- **ファイル**: `src/gfo/cli.py`
- **説明**: `main()` 関数、`create_parser()` 関数、`_DISPATCH` テーブルのエラーハンドリングがテストされていない。サブコマンド未指定時の挙動、不正なコマンドライン、dispatch テーブルの網羅が未検証。
- **影響**: CLI のリグレッションを検出できない。
- **推奨修正**: `test_cli.py` に `main(['--version'])`、`main([])`（help 表示）、`main(['pr', 'list', '--help'])` 等の基本的な統合テストを追加。

---

### [R23-06] 🟡 `config.py` L191 — `build_clone_url` / `build_default_api_url` のバリデーション不足

- **ファイル**: `src/gfo/config.py` L191-234
- **説明**: `build_clone_url(service_type, host, owner, name)` で `owner`、`name` の空文字チェックがない。空文字の場合、`https://github.com//name.git` のような壊れた URL が返される。
- **影響**: 空 owner/repo で URL を構築して API 呼び出しが失敗する（デバッグが困難）。
- **推奨修正**: `owner` / `name` が空の場合は `ConfigError` を送出する。

---

### [R23-07] 🟢 `commands/release.py` L21 — 空タグ strip 処理が後処理で行われない

- **ファイル**: `src/gfo/commands/release.py` L21
- **現在のコード**:
  ```python
  if not args.tag or not args.tag.strip():
      raise ConfigError(...)
  title = args.title or args.tag  # args.tag が "   " の場合、strip されないまま使われる
  ```
- **説明**: `args.tag.strip()` で空白タグを検出しているが、L24 で `args.tag` をそのまま title に使用している。`args.tag = "   "` の場合は L22 で raise されるため実際には問題ないが、コードの意図が不明確。
- **影響**: 軽微。現状は raise で阻止される。
- **推奨修正**: `args.tag = args.tag.strip()` を検証前に実行してコードを明確化。

---

## 全問題サマリー（R23）

| ID | 重大度 | ファイル | 概要 |
|----|--------|---------|------|
| **R23-01** | 🔴 重大 | `config.py` L116 | `resolve_project_config` の except 時 owner="" フォールバック問題 |
| **R23-02** | 🟡 中 | `auth.py` L140 | `get_auth_status` host 形式不統一（R16-02 継続） |
| **R23-03** | 🟡 中 | `output.py` L44 | 空データ時の stdout/stderr 不統一 |
| **R23-04** | 🟢 軽微 | `output.py` L68 | `dataclasses.asdict()` 非 dataclass 例外処理不備 |
| **R23-05** | 🟡 中 | `cli.py` | テストカバレッジ 0%（統合テスト不在） |
| **R23-06** | 🟡 中 | `config.py` L191 | `build_clone_url` 等に owner/name 空文字チェックなし |
| **R23-07** | 🟢 軽微 | `release.py` L21 | 空タグ strip 処理が事前に行われない |
| R16-02 | 🟡 中 | `auth.py` | host 形式不統一（継続） |
| R13-03 | 🟡 中 | `gitea.py` | フィルタ後 limit 未満（継続） |

---

## 推奨アクション（優先度順）

1. **[R23-01]** `config.py` L116 — except 時のフォールバック処理を改善（ConfigError 送出 or config.toml から owner/repo 読み込み）
2. **[R23-05]** `test_cli.py` 新規作成 — CLI 統合テストを追加
3. **[R23-03]** `output.py` L44 — 空データ時の stdout 統一
4. **[R23-06]** `config.py` L191 — `build_clone_url` に空文字チェックを追加
5. **[R23-02]** `auth.py` — host 形式統一（R16-02 対応）
6. **[R23-07]** `release.py` L21 — `args.tag.strip()` を事前実行
7. **[R23-04]** `output.py` L68 — dataclass チェック追加
