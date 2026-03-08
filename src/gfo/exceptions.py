"""gfo の全カスタム例外を集約するモジュール。"""


class GfoError(Exception):
    """gfo の基底例外。全カスタム例外はこれを継承する。"""
    pass


class GitCommandError(GfoError):
    """git コマンド実行の失敗。"""
    def __init__(self, message: str):
        super().__init__(f"Git error: {message}")


class DetectionError(GfoError):
    """サービス自動検出の失敗。"""
    def __init__(self, message: str = ""):
        msg = "Could not detect git forge service."
        if message:
            msg += f" {message}"
        msg += " Run 'gfo init' to configure manually."
        super().__init__(msg)


class ConfigError(GfoError):
    """設定の解決失敗。"""
    pass


class AuthError(GfoError):
    """認証情報の解決失敗。"""
    def __init__(self, host: str):
        super().__init__(
            f"No token found for {host}. "
            f"Run 'gfo auth login --host {host}' to configure."
        )


class HttpError(GfoError):
    """HTTP リクエストのエラー（基底）。"""
    def __init__(self, status_code: int, message: str, url: str = ""):
        self.status_code = status_code
        self.url = url
        super().__init__(f"HTTP {status_code}: {message}")


class AuthenticationError(HttpError):
    """401/403 認証エラー。"""
    def __init__(self, status_code: int, url: str = ""):
        super().__init__(
            status_code,
            "Authentication failed. Check your token with 'gfo auth status'.",
            url,
        )


class NotFoundError(HttpError):
    """404 リソース未発見。"""
    def __init__(self, url: str = ""):
        super().__init__(404, "Resource not found.", url)


class RateLimitError(HttpError):
    """429 レート制限超過。"""
    def __init__(self, retry_after: int | None = None, url: str = ""):
        msg = "Rate limit exceeded."
        if retry_after:
            msg += f" Retry after {retry_after}s."
        super().__init__(429, msg, url)


class ServerError(HttpError):
    """5xx サーバーエラー。"""
    def __init__(self, status_code: int, url: str = ""):
        super().__init__(status_code, "Server error. Please try again later.", url)


class NetworkError(GfoError):
    """ネットワーク接続エラー（ConnectionError, Timeout）。"""
    pass


class NotSupportedError(GfoError):
    """サービスが対応していない操作。"""
    def __init__(self, service: str, operation: str, web_url: str | None = None):
        self.service = service
        self.operation = operation
        self.web_url = web_url
        super().__init__(
            f"{service} does not support {operation}. "
            f"Use the web interface instead."
        )


class UnsupportedServiceError(GfoError):
    """未知のサービス種別。"""
    def __init__(self, service_type: str):
        super().__init__(f"Unsupported service type: {service_type}")
