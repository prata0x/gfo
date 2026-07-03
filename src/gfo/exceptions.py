"""gfo の全カスタム例外を集約するモジュール。"""

from __future__ import annotations

from enum import IntEnum
from typing import Any

from gfo.i18n import _


class ExitCode(IntEnum):
    """CLI 終了コード。エージェントがリトライ判断や分岐に利用する。"""

    SUCCESS = 0
    GENERAL = 1
    AUTH = 2
    NOT_FOUND = 3
    RATE_LIMIT = 4
    NOT_SUPPORTED = 5
    CONFIG = 6
    NETWORK = 7
    PARTIAL_FAILURE = 8


class GfoError(Exception):
    """gfo の基底例外。全カスタム例外はこれを継承する。"""

    error_code: str = "general_error"
    exit_code: ExitCode = ExitCode.GENERAL
    hint: str | None = None


class GitCommandError(GfoError):
    """git コマンド実行の失敗。"""

    error_code = "git_error"
    exit_code = ExitCode.GENERAL

    def __init__(self, message: str):
        super().__init__(_("Git error: {message}").format(message=message))
        self.hint = _(
            "Run this command inside a git repository, "
            "or use '--repo HOST/OWNER/REPO' to specify the target directly."
        )


class DetectionError(GfoError):
    """サービス自動検出の失敗。"""

    error_code = "config_error"
    exit_code = ExitCode.CONFIG

    def __init__(self, message: str = ""):
        msg = _("Could not detect git forge service.")
        if message:
            msg += f" {message}"
        msg += " " + _("Run 'gfo init' to configure manually.")
        super().__init__(msg)
        self.hint = _(
            "Run 'gfo init --non-interactive --type <type> --host <host>' "
            "or use '--repo HOST/OWNER/REPO' to specify directly."
        )


class ConfigError(GfoError):
    """設定の解決失敗。"""

    error_code = "config_error"
    exit_code = ExitCode.CONFIG


class AuthError(GfoError):
    """認証情報の解決失敗。"""

    error_code = "auth_failed"
    exit_code = ExitCode.AUTH

    def __init__(self, host: str, message: str | None = None):
        if message:
            super().__init__(message)
        else:
            super().__init__(
                _(
                    "No token found for {host}. Run 'gfo auth login --host {host}' to configure."
                ).format(host=host)
            )
        self.hint = _("Run 'gfo auth login --host {host}'").format(host=host)


class HttpError(GfoError):
    """HTTP リクエストのエラー（基底）。"""

    def __init__(self, status_code: int, message: str, url: str = "", details: Any = None):
        self.status_code = status_code
        self.url = url
        # エラーレスポンスの JSON body をパースした構造化詳細。
        # --format json 出力時に details フィールドとして載せる（人間可読 message と対）。
        self.details = details
        super().__init__(
            _("HTTP {status_code}: {message}").format(status_code=status_code, message=message)
        )


class AuthenticationError(HttpError):
    """401/403 認証エラー。

    401（トークン自体が無効）と 403（トークンは有効だがスコープ/権限不足）は
    原因が異なるため、status_code に応じてメッセージを分岐する。
    """

    error_code = "auth_failed"
    exit_code = ExitCode.AUTH

    def __init__(self, status_code: int, url: str = ""):
        if status_code == 403:
            message = _(
                "Permission denied. Your token may be valid but lack the required "
                "scope for this operation. See 'Token Creation Instructions by "
                "Service' in docs/authentication.md."
            )
            hint = message
        else:
            message = _("Authentication failed. Check your token with 'gfo auth status'.")
            hint = _("Check your token with 'gfo auth status'.")
        super().__init__(status_code, message, url)
        self.hint = hint


class NotFoundError(HttpError):
    """404 リソース未発見。"""

    error_code = "not_found"
    exit_code = ExitCode.NOT_FOUND

    def __init__(self, url: str = "", detail: str | None = None):
        # detail 指定時は具体的なリソース情報（例: "Tag 'v1' not found"）を message に載せる。
        # 未指定なら "Resource not found." の汎用メッセージ。
        message = detail if detail else _("Resource not found.")
        super().__init__(404, message, url)


class RateLimitError(HttpError):
    """429 レート制限超過。"""

    error_code = "rate_limited"
    exit_code = ExitCode.RATE_LIMIT

    def __init__(self, retry_after: int | None = None, url: str = ""):
        msg = _("Rate limit exceeded.")
        if retry_after:
            msg += " " + _("Retry after {retry_after}s.").format(retry_after=retry_after)
        super().__init__(429, msg, url)
        if retry_after:
            self.hint = _("Retry after {retry_after}s.").format(retry_after=retry_after)


class ValidationError(HttpError):
    """400/422 リクエスト内容のバリデーションエラー。

    サービスがフィールド別のエラーを JSON body で返すケース（GitHub の 422 等）。
    パース済み body は details に載る。
    """

    error_code = "validation_error"
    exit_code = ExitCode.GENERAL

    def __init__(self, status_code: int, message: str, url: str = "", details: Any = None):
        super().__init__(status_code, message, url, details)
        self.hint = _("Check the request parameters for invalid or missing values.")


class ServerError(HttpError):
    """5xx サーバーエラー。"""

    error_code = "server_error"
    exit_code = ExitCode.GENERAL

    def __init__(self, status_code: int, url: str = ""):
        super().__init__(status_code, _("Server error. Please try again later."), url)
        self.hint = _("Please try again later.")


class NetworkError(GfoError):
    """ネットワーク接続エラー（ConnectionError, Timeout, SSLError 等）。"""

    error_code = "network_error"
    exit_code = ExitCode.NETWORK

    def __init__(self, message: str = ""):
        super().__init__(message or _("Network error."))
        self.hint = _("Check your network connection and try again.")


class NotSupportedError(GfoError):
    """サービスが対応していない操作。"""

    error_code = "not_supported"
    exit_code = ExitCode.NOT_SUPPORTED

    def __init__(self, service: str, operation: str, web_url: str | None = None):
        self.service = service
        self.operation = operation
        self.web_url = web_url
        super().__init__(
            _("{service} does not support {operation}. Use the web interface instead.").format(
                service=service, operation=operation
            )
        )
        # web_url が渡されなかった場合でも、対象リポジトリの Web UI への
        # 汎用的な導線だけは提示する（個別の URL までは特定できないため）。
        self.hint = web_url or _(
            "Run 'gfo repo view --web' to open the repository in your browser."
        )


class PartialFailureError(GfoError):
    """一括処理（batch / migrate 等）で 1 件以上が失敗した。

    個々の失敗は結果リスト（status / success / error フィールド）に集約済みで、
    stdout への結果出力後に raise される。exit code で失敗を検知できるようにする
    ためのシグナルであり、全件失敗の場合もこの例外を用いる。
    """

    error_code = "partial_failure"
    exit_code = ExitCode.PARTIAL_FAILURE

    def __init__(self, failed: int, total: int):
        self.failed = failed
        self.total = total
        super().__init__(
            _("{failed} of {total} operations failed.").format(failed=failed, total=total)
        )
        self.hint = _("Inspect the status/error fields of each item in the output for details.")


class UnsupportedServiceError(GfoError):
    """未知のサービス種別。"""

    error_code = "unsupported_service"
    exit_code = ExitCode.GENERAL

    def __init__(self, service_type: str):
        super().__init__(
            _("Unsupported service type: {service_type}").format(service_type=service_type)
        )


# HTTP ステータスコード → 標準的な HttpError 系例外クラスのマッピング。
# 追加引数 (retry_after, body 等) が必要なクラスはこのテーブルでは扱わず、
# 呼び出し側で個別に分岐する (RateLimitError / 汎用 HttpError 本体)。
_SIMPLE_HTTP_EXCEPTIONS: dict[int, type[HttpError]] = {
    401: AuthenticationError,
    403: AuthenticationError,
    404: NotFoundError,
}


def lookup_http_exception(status_code: int) -> type[HttpError] | None:
    """HTTP ステータスコードから対応する HttpError 系例外クラスを返す。

    - 401 / 403 / 404 のような単純な status → exception 対応はテーブル参照。
    - 5xx は range で一括 `ServerError` にマップする。
    - 429 / 400 / 422 / 汎用 4xx などコンストラクタに追加引数（retry_after,
      body, details 等）が必要なケースは `None` を返し、呼び出し側で個別に組み立てる。
    """
    cls = _SIMPLE_HTTP_EXCEPTIONS.get(status_code)
    if cls is not None:
        return cls
    if 500 <= status_code < 600:
        return ServerError
    return None
