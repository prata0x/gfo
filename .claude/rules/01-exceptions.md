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
│   ├── ValidationError     # 400/422（JSON body パース済み details 付き）
│   └── ServerError         # 5xx
├── NetworkError            # ConnectionError/Timeout/SSLError
├── NotSupportedError       # サービスが非対応の操作
├── PartialFailureError     # 一括処理（batch / migrate）で 1 件以上失敗
└── UnsupportedServiceError # 未知のサービス種別
```

## 使い分け

| 状況 | 例外 |
|---|---|
| バリデーション失敗（設定値不正） | `ConfigError` |
| トークン未設定 | `AuthError` |
| API レスポンス構造が予期しない | `GfoError`（KeyError/TypeError/AttributeError をラップ） |
| HTTP 内部のバリデーション | `ValueError`（そのまま OK） |
| 一括処理の部分失敗（結果出力後の exit code シグナル） | `PartialFailureError` |

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

## エラーメッセージの i18n（必須）

ユーザー向け例外（`GfoError` / `ConfigError` / `AuthError` / `DetectionError` /
`HttpError` 系）に渡すメッセージは必ず `_()` を通し、`.po` に ja 訳を追加する:

```python
raise ConfigError(_("No tokens configured for host: {host}").format(host=host))
```

- f-string を直接渡さない（msgid はリテラルである必要がある。`_("...").format(...)` を使う）
- `tests/test_i18n_lint.py` が `src/gfo/` 配下全モジュールを AST 検査で強制し、
  あわせて全 `_()` msgid が `gfo.po` に登録されていること（未訳の混入なし）も検査する
- 内部契約エラー（`ValueError` 等、上表参照）と `NotSupportedError` /
  `UnsupportedServiceError`（識別子を受け取り内部で i18n 済みテンプレートに埋め込む）は対象外
