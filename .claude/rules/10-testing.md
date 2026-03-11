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
