---
paths:
  - "src/gfo/**"
  - "tests/**"
---

# 例外体系

## 例外ツリー

```
GfoError
├── GitCommandError         # git コマンド実行失敗
├── DetectionError          # サービス自動検出失敗
├── ConfigError             # 設定解決失敗・バリデーションエラー
├── AuthError               # 認証情報なし
├── HttpError               # HTTP エラー基底
│   ├── AuthenticationError # 401/403
│   ├── NotFoundError       # 404
│   ├── RateLimitError      # 429
│   └── ServerError         # 5xx
├── NetworkError            # ConnectionError/Timeout/SSLError
├── NotSupportedError       # サービスが非対応の操作
└── UnsupportedServiceError # 未知のサービス種別
```

## 使い分け

| 状況 | 例外 |
|---|---|
| バリデーション失敗（設定値不正） | `ConfigError` |
| トークン未設定 | `AuthError` |
| API レスポンス構造が予期しない | `GfoError`（KeyError/TypeError/AttributeError をラップ） |
| HTTP 内部のバリデーション | `ValueError`（そのまま OK） |

## `_to_*` 内のラップパターン（必須）

`_to_*` 変換メソッドは `@_wrap_conversion_error` デコレータでラップする:

```python
@staticmethod
@_wrap_conversion_error
def _to_pull_request(data: dict) -> PullRequest:
    return PullRequest(number=data["number"], ...)
```

デコレータは `(KeyError, TypeError, AttributeError)` を捕捉し、
`GfoError("Unexpected API response: missing field {e}")` に変換する。
`AttributeError` も含めるのは、`data["user"]` が想定外に `str` 等で来て
`.get("login")` が `AttributeError` を投げるなど、API レスポンス形式違いで
発生し得るため一貫して `GfoError` でラップしたいから。

`ValueError` や `IndexError` 等の追加例外も捕捉する必要があるケースだけ
手書きの try/except を残す (デコレータでは捕捉しないため)。
