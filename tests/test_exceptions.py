"""exceptions.py の全エラー型をテストするモジュール。"""

import pytest

from gfo.exceptions import (
    AuthenticationError,
    AuthError,
    ConfigError,
    DetectionError,
    GfoError,
    GitCommandError,
    HttpError,
    NetworkError,
    NotFoundError,
    NotSupportedError,
    RateLimitError,
    ServerError,
    UnsupportedServiceError,
)


class TestGfoError:
    def test_base_exception(self):
        err = GfoError("something went wrong")
        assert str(err) == "something went wrong"
        assert isinstance(err, Exception)


class TestGitCommandError:
    def test_message_format(self):
        err = GitCommandError("branch not found")
        assert str(err) == "Git error: branch not found"
        assert isinstance(err, GfoError)


class TestDetectionError:
    def test_default_message(self):
        err = DetectionError()
        assert "Could not detect git forge service." in str(err)
        assert "Run 'gfo init' to configure manually." in str(err)

    def test_custom_message(self):
        err = DetectionError("No remote URL configured.")
        msg = str(err)
        assert "Could not detect git forge service." in msg
        assert "No remote URL configured." in msg
        assert "Run 'gfo init' to configure manually." in msg

    def test_inherits_gfo_error(self):
        assert isinstance(DetectionError(), GfoError)


class TestConfigError:
    def test_message(self):
        err = ConfigError("missing key")
        assert str(err) == "missing key"
        assert isinstance(err, GfoError)


class TestAuthError:
    def test_message_format(self):
        err = AuthError("github.com")
        msg = str(err)
        assert "No token found for github.com." in msg
        assert "gfo auth login --host github.com" in msg
        assert isinstance(err, GfoError)


class TestHttpError:
    def test_attributes(self):
        err = HttpError(500, "Internal Server Error", "https://api.example.com")
        assert err.status_code == 500
        assert err.url == "https://api.example.com"
        assert str(err) == "HTTP 500: Internal Server Error"

    def test_default_url(self):
        err = HttpError(400, "Bad Request")
        assert err.url == ""

    def test_inherits_gfo_error(self):
        assert isinstance(HttpError(400, "Bad Request"), GfoError)


class TestAuthenticationError:
    def test_401(self):
        err = AuthenticationError(401, "https://api.github.com")
        assert err.status_code == 401
        assert err.url == "https://api.github.com"
        assert "Authentication failed" in str(err)

    def test_403(self):
        err = AuthenticationError(403)
        assert err.status_code == 403
        assert isinstance(err, HttpError)
        assert isinstance(err, GfoError)


class TestNotFoundError:
    def test_message(self):
        err = NotFoundError("https://api.github.com/repos/x/y")
        assert err.status_code == 404
        assert err.url == "https://api.github.com/repos/x/y"
        assert "Resource not found" in str(err)

    def test_inherits_http_error(self):
        assert isinstance(NotFoundError(), HttpError)
        assert isinstance(NotFoundError(), GfoError)


class TestRateLimitError:
    def test_without_retry_after(self):
        err = RateLimitError()
        assert err.status_code == 429
        assert "Rate limit exceeded." in str(err)
        assert "Retry after" not in str(err)

    def test_with_retry_after(self):
        err = RateLimitError(retry_after=60, url="https://api.github.com")
        assert "Rate limit exceeded." in str(err)
        assert "Retry after 60s." in str(err)
        assert err.url == "https://api.github.com"

    def test_inherits_http_error(self):
        assert isinstance(RateLimitError(), HttpError)
        assert isinstance(RateLimitError(), GfoError)


class TestServerError:
    def test_500(self):
        err = ServerError(500, "https://api.github.com")
        assert err.status_code == 500
        assert err.url == "https://api.github.com"
        assert "Server error" in str(err)

    def test_502(self):
        err = ServerError(502)
        assert err.status_code == 502
        assert isinstance(err, HttpError)
        assert isinstance(err, GfoError)


class TestNetworkError:
    def test_message(self):
        err = NetworkError("Connection refused")
        assert str(err) == "Connection refused"
        assert isinstance(err, GfoError)


class TestNotSupportedError:
    def test_attributes_and_message(self):
        err = NotSupportedError("Gitea", "draft PR", "https://gitea.example.com")
        assert err.service == "Gitea"
        assert err.operation == "draft PR"
        assert err.web_url == "https://gitea.example.com"
        assert "Gitea does not support draft PR" in str(err)
        assert "Use the web interface instead." in str(err)

    def test_web_url_none(self):
        err = NotSupportedError("Gitea", "draft PR")
        assert err.web_url is None

    def test_inherits_gfo_error(self):
        assert isinstance(NotSupportedError("X", "Y"), GfoError)


class TestUnsupportedServiceError:
    def test_message(self):
        err = UnsupportedServiceError("bitbucket")
        assert str(err) == "Unsupported service type: bitbucket"
        assert isinstance(err, GfoError)


class TestCatchByBaseClass:
    """HttpError サブクラスを GfoError で catch できることを確認。"""

    def test_catch_authentication_error_as_gfo_error(self):
        with pytest.raises(GfoError):
            raise AuthenticationError(401)

    def test_catch_not_found_as_http_error(self):
        with pytest.raises(HttpError):
            raise NotFoundError()

    def test_catch_rate_limit_as_gfo_error(self):
        with pytest.raises(GfoError):
            raise RateLimitError()

    def test_catch_server_error_as_http_error(self):
        with pytest.raises(HttpError):
            raise ServerError(503)
