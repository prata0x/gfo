---
paths:
  - "tests/**"
---

# テスト規約

## HTTP モック

```python
@responses.activate
def test_something(adapter):
    responses.add(responses.GET, "https://api.example.com/...", json={...})
    result = adapter.some_method()
    assert result.field == "value"
```

- **`assert_all_requests_are_fired=True` がデフォルト**
  - 登録したモックが呼ばれなかった場合、テストが失敗する
  - 不要なモックは登録しないこと

## テストファイル配置

| テスト種別 | 配置先 |
|---|---|
| アダプターテスト | `tests/test_adapters/test_{service}.py` |
| コマンドテスト | `tests/test_commands/test_{command}.py` |

## コマンドテスト

- `tests/test_commands/conftest.py` の `make_args()` でコマンド引数オブジェクトを作成

## アダプターフィクスチャ

- `tests/test_adapters/conftest.py` に全サービスの `client` + `adapter` ペアを定義

## コマンドテスト: `patch_adapter`

- `tests/test_commands/conftest.py` の `patch_adapter(module_path)` 共通ヘルパーを使うこと
- ファイルごとに独自の `_patch` ヘルパーを重複定義しないこと

## 必須テストパターン

- **`fmt="json"` テスト**: 各コマンドに最低1つ必須
- **エラー伝搬テスト**: adapter が `HttpError` を投げた場合の伝搬を検証すること
- **アダプターテスト最低要件**: 404/403 エラーテスト + 空リスト `[]` テスト

## 統合テスト

- **`safe_temporary_directory()`**: `tests/integration/conftest.py` のヘルパーを使うこと（`TemporaryDirectory` を直接使わない）
  - 理由: Windows ファイルロック対策 + Python 3.11 互換（`ignore_cleanup_errors` 未対応）
- **API 反映ラグ**: set/delete 直後の get/list に `time.sleep(3)` を入れること
  - GitHub/Bitbucket で確認済みの反映遅延への対策
- **プライベート API 依存**: TODO コメント付きで最小限に抑えること
- **git 操作時の GCM 抑制**: `subprocess.run` で `git clone`/`git push` 等を実行する場合、環境変数に `GCM_INTERACTIVE=never` と `GIT_TERMINAL_PROMPT=0` を設定すること
  - 理由: Windows の Git Credential Manager (GCM) が `GIT_ASKPASS` より先に介入し、ブラウザで認証ページを開いてしまう
