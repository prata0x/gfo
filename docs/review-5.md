# Review 5

対象範囲: 76b4712 から c4fbefd

## Findings

### 1. High: 任意のアカウント名を保存できる体裁なのに、TOML へ bare key のまま書き出しており再読込できない

- 該当箇所: [src/gfo/auth.py](src/gfo/auth.py#L74), [src/gfo/auth.py](src/gfo/auth.py#L287), [src/gfo/auth.py](src/gfo/auth.py#L293)
- 問題: `save_token()` は `account` を自由入力で受け取りますが、`_write_credentials_toml()` ではアカウント名をクォートせず `me@example.com = "..."` のように書き出しています。TOML の bare key では `@` や `.` を含む名前を表現できないため、保存直後の `load_tokens()` が `ConfigError` で壊れます。
- 再現: `gfo auth login --host github.com --account me@example.com --token ...` を実行すると、次回の `auth status` や通常のトークン解決で credentials.toml の parse に失敗します。実際に `save_token("github.com", "secret-token", account="me@example.com")` を最小再現すると、`Expected '=' after a key in a key/value pair` で読めなくなりました。
- 影響: マルチアカウント機能が、メールアドレスや `work.prod` のような自然なアカウント名で即座に壊れます。CLI 上はアカウント名の制約を案内していないため、ユーザーが踏みやすい不具合です。

### 2. High: 予約キー `_default` をアカウント名として受け入れてしまい、保存済みトークンを不可視化する

- 該当箇所: [src/gfo/auth.py](src/gfo/auth.py#L74), [src/gfo/auth.py](src/gfo/auth.py#L112), [src/gfo/auth.py](src/gfo/auth.py#L179)
- 問題: 新フォーマットでは `_default` を「現在の既定アカウント名」を表す内部キーとして使っていますが、`save_token()` 側で同名アカウントを禁止していません。そのため `account="_default"` で保存すると、内部ポインタと実データが衝突し、`list_accounts()` と `get_auth_status()` のどちらからも見えない壊れた状態になります。
- 再現: `save_token("github.com", "secret-token", account="_default")` を実行すると、ファイルには `_default = "secret-token"` しか残らず、`list_accounts("github.com")` は空配列、`get_auth_status()` も空になります。
- 影響: 保存直後のトークンが管理画面や一覧から消え、`switch_account()` や `remove_token()` の操作対象にもならなくなります。予約語衝突を防げていないので、データ破損に近い挙動です。

### 3. Medium: アカウント解決で設定エラーを握りつぶし、誤った既定アカウントへ静かにフォールバックする

- 該当箇所: [src/gfo/auth.py](src/gfo/auth.py#L298), [src/gfo/auth.py](src/gfo/auth.py#L320), [src/gfo/auth.py](src/gfo/auth.py#L327), [src/gfo/auth.py](src/gfo/auth.py#L330)
- 問題: `_resolve_account_name()` は `git_config_get()` と `get_host_config()` の両方を `except Exception` で握りつぶしています。ここには `ConfigError` も含まれるため、`config.toml` の parse 失敗や設定不整合が起きてもエラーにならず、`tokens.{host}._default` へ silently fallback します。
- 再現: `get_host_config()` が `ConfigError("broken config")` を送出する状況で `_resolve_account_name()` を呼ぶと、例外は表に出ず `_default` 側のアカウント名が返ります。
- 影響: ユーザーは設定が壊れていることに気づけないまま、意図しない別アカウントのトークンで API を叩きます。認証対象を切り替える機能でこれはかなり危険です。

### 4. Medium: `repo view --web OWNER/NAME` が明示したリポジトリを無視して現在のリポジトリを開く

- 該当箇所: [src/gfo/commands/repo.py](src/gfo/commands/repo.py#L162), [src/gfo/commands/repo.py](src/gfo/commands/repo.py#L164), [src/gfo/commands/repo.py](src/gfo/commands/repo.py#L172)
- 問題: `handle_view()` は `--web` が付くと早期 return し、その前に `args.repo` を一切解釈していません。そのため通常表示では `gfo repo view other-owner/other-repo` が見られるのに、`gfo repo view other-owner/other-repo --web` は常に現在コンテキストのリポジトリ URL を開きます。
- 根拠: 実装は `adapter.get_web_url("repo")` を固定で呼ぶだけです。追加されたテストも [tests/test_commands/test_repo.py](tests/test_commands/test_repo.py#L1003) のとおり `repo=None` ケースしか見ておらず、この回帰を拾えていません。
- 影響: 別リポジトリをブラウザで確認したいユースケースで誤った URL を開きます。コマンドライン引数を受け付けているぶん、ユーザーの期待を明確に裏切る挙動です。

## Notes

- フルテストは実行していません。
- 1, 2, 3 は Python スニペットで最小再現を確認しました。