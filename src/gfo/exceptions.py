"""gfo の全カスタム例外を集約するモジュール。"""

from enum import IntEnum

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
        self.hint = _("Run 'gfo init' to configure manually.")


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

    def __init__(self, status_code: int, message: str, url: str = ""):
        self.status_code = status_code
        self.url = url
        super().__init__(
            _("HTTP {status_code}: {message}").format(status_code=status_code, message=message)
        )


class AuthenticationError(HttpError):
    """401/403 認証エラー。"""

    error_code = "auth_failed"
    exit_code = ExitCode.AUTH

    def __init__(self, status_code: int, url: str = ""):
        super().__init__(
            status_code,
            _("Authentication failed. Check your token with 'gfo auth status'."),
            url,
        )
        self.hint = _("Check your token with 'gfo auth status'.")


class NotFoundError(HttpError):
    """404 リソース未発見。"""

    error_code = "not_found"
    exit_code = ExitCode.NOT_FOUND

    def __init__(self, url: str = ""):
        super().__init__(404, _("Resource not found."), url)


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


class ServerError(HttpError):
    """5xx サーバーエラー。"""

    error_code = "server_error"
    exit_code = ExitCode.GENERAL

    def __init__(self, status_code: int, url: str = ""):
        super().__init__(status_code, _("Server error. Please try again later."), url)


class NetworkError(GfoError):
    """ネットワーク接続エラー（ConnectionError, Timeout, SSLError 等）。"""

    error_code = "network_error"
    exit_code = ExitCode.NETWORK


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
        if web_url:
            self.hint = web_url


class UnsupportedServiceError(GfoError):
    """未知のサービス種別。"""

    error_code = "unsupported_service"
    exit_code = ExitCode.GENERAL

    def __init__(self, service_type: str):
        super().__init__(
            _("Unsupported service type: {service_type}").format(service_type=service_type)
        )
