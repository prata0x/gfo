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
| API レスポンス構造が予期しない | `GfoError`（KeyError/TypeError をラップ） |
| HTTP 内部のバリデーション | `ValueError`（そのまま OK） |

## `_to_*` 内のラップパターン（必須）

```python
try:
    return PullRequest(number=data["number"], ...)
except (KeyError, TypeError) as e:
    raise GfoError(f"Unexpected API response: missing field {e}") from e
```
