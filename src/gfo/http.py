"""HTTP クライアントとページネーション関数を提供するモジュール。"""

from __future__ import annotations

import email.utils
import os
import re
import sys
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import requests

import gfo.exceptions
from gfo.i18n import _


def _max_retry_after_seconds() -> int:
    """GFO_RETRY_AFTER_MAX の値を返す。未設定なら 300 秒。

    一部 API (GitHub Secondary rate limit など) は Retry-After に長めの値
    (3600 秒等) を返すことがあり、デフォルト 300 で clamp すると過剰リトライで
    レート制限を再度踏むため、運用上 externalize できるようにしておく。
    """
    val = os.environ.get("GFO_RETRY_AFTER_MAX", "").strip()
    if not val:
        return 300
    try:
        n = int(val)
    except ValueError:
        return 300
    return max(0, n)


_MAX_RETRY_AFTER = _max_retry_after_seconds()
# HttpError 例外メッセージに載せるレスポンス body の上限（バイト換算ではなく文字数）。
# 巨大エラーボディが例外文字列・JSON 出力・ターミナルを圧迫するのを防ぐ。
_MAX_ERROR_BODY_CHARS = 4096


def _max_download_bytes() -> int:
    """GFO_MAX_DOWNLOAD_BYTES の値を返す。未設定なら 5 GiB。0 は無制限。

    不正な値が設定されている場合は警告を出し、既定値にフォールバックする
    (silent fallback だとユーザーが上限を設定したつもりで効いていない事故が起きるため)。
    """
    val = os.environ.get("GFO_MAX_DOWNLOAD_BYTES", "").strip()
    default = 5 * 1024 * 1024 * 1024  # 5 GiB
    if not val:
        return default
    try:
        n = int(val)
    except ValueError:
        import warnings

        warnings.warn(
            f"GFO_MAX_DOWNLOAD_BYTES={val!r} is not a valid integer; using default 5 GiB.",
            stacklevel=2,
        )
        return default
    return max(0, n)


_INSECURE_ENV = os.environ.get("GFO_INSECURE", "").lower() in ("1", "true", "yes")
_VERIFY_SSL = not _INSECURE_ENV

# クラウド固定ホストでは GFO_INSECURE を無視して常に TLS 検証する。
# 自己署名証明書ユーザーが意図せずクラウドホストの認証情報を MITM に晒すのを防ぐ。
_CLOUD_HOSTS_TLS_FORCED = {
    "github.com",
    "api.github.com",
    "uploads.github.com",
    "gitlab.com",
    "bitbucket.org",
    "api.bitbucket.org",
    "dev.azure.com",
}
_CLOUD_HOST_SUFFIXES_TLS_FORCED = (".backlog.com", ".backlog.jp", ".visualstudio.com")


def _is_cloud_host_tls_forced(host: str | None) -> bool:
    """クラウド固定ホスト（GFO_INSECURE で TLS 無効化を許さないホスト）かを判定する。"""
    if not host:
        return False
    # 末尾ドット付き FQDN（例: "github.com."）も同一ホストとして正規化する。
    # 正規化しないとクラウド固定ホストの TLS 強制判定を素通りしてしまう。
    h = host.lower().rstrip(".")
    if h in _CLOUD_HOSTS_TLS_FORCED:
        return True
    return any(h.endswith(s) for s in _CLOUD_HOST_SUFFIXES_TLS_FORCED)


def _verify_for_url(url: str) -> bool:
    """指定 URL に対する TLS 検証フラグを返す。クラウド固定ホストでは常に True。"""
    target_host = urlparse(url).hostname
    if _is_cloud_host_tls_forced(target_host):
        return True
    return _VERIFY_SSL


if _INSECURE_ENV:
    # 起動時警告: クラウド固定ホストでは無効化されない旨をユーザーに通知する。
    print(
        _(
            "Warning: GFO_INSECURE is set; TLS verification is disabled for self-hosted hosts. "
            "Cloud-hosted services (github.com, gitlab.com, bitbucket.org, dev.azure.com, "
            "*.backlog.com/jp, *.visualstudio.com) still enforce TLS verification."
        ),
        file=sys.stderr,
    )


class HttpClient:
    """認証付き HTTP クライアント。アダプターごとに 1 インスタンス生成する。"""

    def __init__(
        self,
        base_url: str,
        auth_header: dict[str, str] | None = None,
        auth_params: dict[str, str] | None = None,
        basic_auth: tuple[str, str] | None = None,
        extra_headers: dict[str, str] | None = None,
        default_params: dict[str, str] | None = None,
        max_retries: int = 1,
    ):
        """初期化。auth_header / auth_params / basic_auth は排他。

        Args:
            max_retries: 429 レートリミット時の最大リトライ回数。デフォルト 1。
                         0 を指定するとリトライなしで即座に RateLimitError を送出する。
                         再送後も 429 が継続する場合は RateLimitError を呼び出し元に伝播する。
        """
        auth_count = sum(x is not None for x in (auth_header, auth_params, basic_auth))
        if auth_count > 1:
            raise ValueError("auth_header, auth_params, basic_auth are mutually exclusive.")
        self._base_url = base_url.rstrip("/")
        self._auth_params: dict[str, str] = auth_params or {}
        self._default_params: dict[str, str] = default_params or {}
        self._max_retries = max_retries
        self._session = requests.Session()
        # クラウド固定ホストでは GFO_INSECURE を無視して常に TLS 検証する
        base_host = urlparse(self._base_url).hostname
        if _is_cloud_host_tls_forced(base_host):
            self._session.verify = True
        else:
            self._session.verify = _VERIFY_SSL
        if auth_header:
            self._session.headers.update(auth_header)
        if basic_auth:
            self._session.auth = basic_auth
        if extra_headers:
            self._session.headers.update(extra_headers)

    @property
    def base_url(self) -> str:
        """API ベース URL（読み取り専用）。"""
        return self._base_url

    def _retry_loop(self, resp_fn: Callable[[], requests.Response]) -> requests.Response:
        """リトライループ共通実装。resp_fn を実行し 429 時は待機して再試行する。"""
        for attempt in range(self._max_retries + 1):
            try:
                resp = resp_fn()
            except requests.RequestException as e:
                raise gfo.exceptions.NetworkError(self._mask_api_key(str(e))) from e

            try:
                self._handle_response(resp)
                return resp
            except gfo.exceptions.RateLimitError:
                if attempt >= self._max_retries:
                    raise
                wait = self._parse_retry_after(resp.headers.get("Retry-After"))
                time.sleep(wait)

        raise AssertionError("unreachable")  # pragma: no cover

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        data: str | None = None,
        headers: dict[str, str] | None = None,
        timeout: int = 30,
    ) -> requests.Response:
        """HTTP リクエストを実行する。

        429 レートリミット時は Retry-After 秒待機して最大 max_retries 回再送する。
        再送後も 429 が継続する場合は RateLimitError を呼び出し元に伝播する。
        """
        url = self._base_url + path
        merged_params = {**self._default_params, **self._auth_params, **(params or {})}
        return self._retry_loop(
            lambda: self._session.request(
                method,
                url,
                params=merged_params,
                json=json,
                data=data,
                headers=headers,
                timeout=timeout,
            )
        )

    def get(self, path: str, **kwargs: Any) -> requests.Response:
        """GET リクエスト。"""
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> requests.Response:
        """POST リクエスト。"""
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> requests.Response:
        """PUT リクエスト。"""
        return self.request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs: Any) -> requests.Response:
        """PATCH リクエスト。"""
        return self.request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> requests.Response:
        """DELETE リクエスト。"""
        return self.request("DELETE", path, **kwargs)

    def request_stream(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: int = 300,
        chunk_size: int = 65536,
    ) -> Iterator[bytes]:
        """ストリーミング GET/POST 用ジェネレータ。

        path は base_url からの相対パス、または絶対 URL を受け付ける。
        絶対 URL が base_url と別オリジンの場合、認証ヘッダ / Cookie / auth_params を
        一切送信しない（外部ホストへのトークン漏えい防止）。

        `_session.request(stream=True)` で応答を取り、`_handle_response()` で
        ステータス検査後、`resp.iter_content(chunk_size)` を順に yield する。
        呼び出し側は `for chunk in client.request_stream(...): ...` で消費する。

        404/429/5xx は `_handle_response` 経由で適切な HttpError を送出する。
        ネットワーク例外は `NetworkError` でラップする。
        """
        is_absolute = path.startswith(("http://", "https://"))
        url = path if is_absolute else self._base_url + path
        same_origin = (not is_absolute) or _validate_same_origin(self._base_url, url)
        try:
            if same_origin:
                merged_params = {**self._default_params, **self._auth_params, **(params or {})}
                resp = self._session.request(
                    method,
                    url,
                    params=merged_params,
                    headers=headers,
                    stream=True,
                    timeout=timeout,
                )
            else:
                # 別オリジン: Session 経由だと Authorization / Cookie が自動付与
                # されるため、requests.request を直接呼んで認証情報を遮断する。
                ext_headers = dict(headers) if headers else {}
                resp = requests.request(
                    method,
                    url,
                    params=params,
                    headers=ext_headers,
                    stream=True,
                    timeout=timeout,
                    verify=_verify_for_url(url),
                )
        except requests.RequestException as e:
            raise gfo.exceptions.NetworkError(self._mask_api_key(str(e))) from e
        try:
            self._handle_response(resp)
        except BaseException:
            resp.close()
            raise
        return self._iter_chunks(resp, chunk_size)

    @staticmethod
    def _iter_chunks(resp: requests.Response, chunk_size: int) -> Iterator[bytes]:
        """ストリーミング応答のチャンクを順に yield する内部ヘルパー。"""
        try:
            for chunk in resp.iter_content(chunk_size=chunk_size):
                if chunk:
                    yield chunk
        finally:
            resp.close()

    def download_file(
        self,
        url: str,
        output_path: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: int = 300,
    ) -> None:
        """ストリーミングダウンロード。

        URL が base_url と別オリジンの場合は認証ヘッダ / Cookie / auth_params を
        一切送信しない（`request_stream` のクロスオリジン判定に委譲）。
        """
        # 累積バイト数が GFO_MAX_DOWNLOAD_BYTES（既定 5 GiB）を超えたら中断する。
        # 悪意のサーバや侵害された CDN が無限ストリームを返した際の DoS 防止。
        max_bytes = _max_download_bytes()
        total = 0
        with open(output_path, "wb") as f:
            for chunk in self.request_stream(
                "GET", url, headers=headers, timeout=timeout, chunk_size=65536
            ):
                total += len(chunk)
                if max_bytes > 0 and total > max_bytes:
                    # 部分書き込みファイルは残さない
                    try:
                        f.close()
                        os.unlink(output_path)
                    except OSError:
                        pass
                    raise gfo.exceptions.GfoError(
                        f"Download exceeded GFO_MAX_DOWNLOAD_BYTES ({max_bytes} bytes); aborted."
                    )
                f.write(chunk)

    def upload_file(
        self,
        path: str,
        file_path: str,
        *,
        name: str | None = None,
        content_type: str = "application/octet-stream",
        timeout: int = 300,
    ) -> requests.Response:
        """ファイルアップロード（raw binary）。GitHub 用。

        ファイル全体をメモリに読み込まず、`data=` にファイルオブジェクトを渡して
        requests にチャンク送信させる。リトライ時はファイルを再 open することで
        ストリーミング位置をリセットする。
        """
        import os

        fname = name or os.path.basename(file_path)
        url = self._base_url + path
        merged_params = {**self._default_params, **self._auth_params, "name": fname}
        upload_headers = {"Content-Type": content_type}

        def _post() -> requests.Response:
            with open(file_path, "rb") as f:
                return self._session.post(
                    url,
                    params=merged_params,
                    data=f,
                    headers=upload_headers,
                    timeout=timeout,
                )

        return self._retry_loop(_post)

    def upload_file_absolute(
        self,
        url: str,
        file_path: str,
        *,
        name: str | None = None,
        content_type: str = "application/octet-stream",
        params: dict[str, Any] | None = None,
        timeout: int = 300,
    ) -> requests.Response:
        """絶対 URL に対してファイルアップロード（raw binary）。GitHub Release Asset 用。

        upload_file と同様にファイルオブジェクトをストリーミングし、リトライ時に
        再 open する。
        """
        import os

        fname = name or os.path.basename(file_path)
        merged_params = {
            **self._default_params,
            **self._auth_params,
            "name": fname,
            **(params or {}),
        }
        upload_headers = {"Content-Type": content_type}

        def _post() -> requests.Response:
            with open(file_path, "rb") as f:
                return self._session.post(
                    url,
                    params=merged_params,
                    data=f,
                    headers=upload_headers,
                    timeout=timeout,
                    # 呼び出し側指定の絶対 URL。クラウド固定ホスト宛なら GFO_INSECURE
                    # でも TLS 検証を強制する（self-hosted base での upload 先漏えい防止）。
                    verify=_verify_for_url(url),
                )

        return self._retry_loop(_post)

    def upload_multipart(
        self,
        path: str,
        file_path: str,
        *,
        field_name: str = "attachment",
        name: str | None = None,
        timeout: int = 300,
    ) -> requests.Response:
        """multipart/form-data アップロード。Gitea / GitLab 用。

        ファイルオブジェクトを multipart の files= に渡してストリーミング送信する。
        リトライ時は再 open することで読み込み位置をリセットする。
        """
        import os

        fname = name or os.path.basename(file_path)
        url = self._base_url + path
        merged_params = {**self._default_params, **self._auth_params}

        def _post() -> requests.Response:
            with open(file_path, "rb") as f:
                return self._session.post(
                    url,
                    params=merged_params,
                    files={field_name: (fname, f)},
                    timeout=timeout,
                )

        return self._retry_loop(_post)

    def get_absolute(
        self, url: str, *, params: dict[str, Any] | None = None, timeout: int = 30
    ) -> requests.Response:
        """絶対 URL に対して GET リクエストを実行する。認証パラメータ・リトライを適用する。

        params を指定すると default_params を上書きできる（異なる api-version が必要な場合等）。
        429 レートリミット時は Retry-After 秒待機して最大 max_retries 回再送する。
        再送後も 429 が継続する場合は RateLimitError を呼び出し元に伝播する。
        """
        merged_params = {**self._default_params, **self._auth_params, **(params or {})}
        return self._retry_loop(
            # 呼び出し側指定の絶対 URL。クラウド固定ホスト宛なら GFO_INSECURE でも
            # TLS 検証を強制する（self-hosted base からの absolute URL 取得時の保護）。
            lambda: self._session.get(
                url, params=merged_params, timeout=timeout, verify=_verify_for_url(url)
            )
        )

    def _handle_response(self, response: requests.Response) -> None:
        """ステータスコードを検査し、適切なエラーを送出する。"""
        code = response.status_code
        if 200 <= code < 300:
            return
        url = self._mask_api_key(response.url)
        # 429 / その他 4xx はコンストラクタに追加情報を渡すため個別分岐。
        if code == 429:
            retry_after = response.headers.get("Retry-After")
            raise gfo.exceptions.RateLimitError(
                self._parse_retry_after(retry_after) if retry_after else None, url
            )
        # 401/403/404/5xx は lookup_http_exception でテーブル引き。
        cls = gfo.exceptions.lookup_http_exception(code)
        if cls is gfo.exceptions.NotFoundError:
            raise gfo.exceptions.NotFoundError(url)
        if cls is gfo.exceptions.AuthenticationError:
            raise gfo.exceptions.AuthenticationError(code, url)
        if cls is gfo.exceptions.ServerError:
            raise gfo.exceptions.ServerError(code, url)
        # その他 (汎用 4xx 等) は HttpError として body 付きで送出。
        body = response.text
        if len(body) > _MAX_ERROR_BODY_CHARS:
            body = (
                body[:_MAX_ERROR_BODY_CHARS]
                + f"... [truncated {len(body) - _MAX_ERROR_BODY_CHARS} chars]"
            )
        raise gfo.exceptions.HttpError(code, body, url)

    @staticmethod
    def _parse_retry_after(value: str | None, default: int = 60) -> int:
        """Retry-After ヘッダー値を秒数に変換する。

        RFC 7231 では秒数整数と HTTP 日時形式（例: Mon, 09 Mar 2026 15:30:00 GMT）の
        両方を許容する。値は 1 以上 _MAX_RETRY_AFTER 以下にクランプする。
        """
        if value is None:
            return default
        # 秒数形式
        try:
            return max(1, min(int(value), _MAX_RETRY_AFTER))
        except ValueError:
            pass
        # RFC 7231 HTTP-date 形式
        try:
            dt = email.utils.parsedate_to_datetime(value)
            diff = int((dt - datetime.now(UTC)).total_seconds())
            return max(1, min(diff, _MAX_RETRY_AFTER))
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _mask_api_key(url: str) -> str:
        """URL 内の apiKey=xxx を apiKey=*** に置換する。"""
        return re.sub(r"apiKey=[^&]+", "apiKey=***", url)


_DEFAULT_PORTS: dict[str, int] = {"http": 80, "https": 443}


def _extract_next_link(link: str) -> str | None:
    """RFC 5988 Link ヘッダーから rel=next の URL を抽出する。

    `<url>; rel="next"` の形式に加え、パラメータの順序が異なる
    `<url>; title="x"; rel="next"` のような形式にも対応する。
    """
    for entry in link.split(","):
        url_match = re.match(r"\s*<([^>]+)>", entry)
        if url_match and re.search(r';\s*rel\s*=\s*"?next"?', entry, re.IGNORECASE):
            return url_match.group(1)
    return None


def _validate_same_origin(base_url: str, next_url: str) -> bool:
    """next_url が base_url と同一オリジン（scheme + host + port）であることを検証する。"""
    base = urlparse(base_url)
    target = urlparse(next_url)
    base_port = base.port or _DEFAULT_PORTS.get(base.scheme)
    target_port = target.port or _DEFAULT_PORTS.get(target.scheme)
    return (
        base.scheme == target.scheme
        and base.hostname == target.hostname
        and base_port == target_port
    )


def paginate_link_header(
    client: HttpClient,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    per_page: int = 100,
    per_page_key: str = "per_page",
    limit: int = 30,
) -> list[dict[str, Any]]:
    """Link header ベースのページネーション（GitHub / Gitea / GitBucket 用）。

    per_page デフォルトは 100 (GitHub / Gitea の API 上限)。大量取得時の
    HTTP ラウンドトリップ削減のため。limit < per_page の場合は limit に
    クランプされるので小規模リクエストでは影響なし。
    """
    if limit < 0:
        raise ValueError("limit must be non-negative")
    if 0 < limit < per_page:
        per_page = limit
    params = dict(params or {})
    params[per_page_key] = per_page
    results: list[dict[str, Any]] = []
    next_url: str | None = None

    while True:
        if next_url is None:
            resp = client.get(path, params=params)
        else:
            resp = client.get_absolute(next_url)

        try:
            page_data = resp.json()
        except ValueError:
            # 非 JSON レスポンス（200 で HTML 等を返すサーバー）の場合は終了
            break
        if not isinstance(page_data, list) or not page_data:
            break
        results.extend(page_data)
        if limit > 0 and len(results) >= limit:
            results = results[:limit]
            break

        link = resp.headers.get("Link", "")
        next_url = _extract_next_link(link)
        if not next_url:
            break
        if not _validate_same_origin(client.base_url, next_url):
            break

    return results


def paginate_page_param(
    client: HttpClient,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    per_page: int = 100,
    limit: int = 30,
    next_page_header: str = "X-Next-Page",
) -> list[dict[str, Any]]:
    """ページパラメータ + ヘッダーベースのページネーション（GitLab 用）。

    per_page デフォルトは 100 (GitLab API 上限)。大量取得時の
    HTTP ラウンドトリップ削減のため。
    """
    if limit < 0:
        raise ValueError("limit must be non-negative")
    if 0 < limit < per_page:
        per_page = limit
    params = dict(params or {})
    params["per_page"] = per_page
    params["page"] = 1
    results: list[dict[str, Any]] = []

    while True:
        resp = client.get(path, params=params)
        try:
            page_data = resp.json()
        except ValueError:
            break
        if not isinstance(page_data, list) or not page_data:
            break
        results.extend(page_data)
        if limit > 0 and len(results) >= limit:
            results = results[:limit]
            break

        next_page = resp.headers.get(next_page_header, "")
        if not next_page:
            break
        try:
            params["page"] = int(next_page)
        except ValueError:
            break

    return results


def paginate_response_body(
    client: HttpClient,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    limit: int = 30,
    values_key: str = "values",
    next_key: str = "next",
) -> list[dict[str, Any]]:
    """レスポンスボディベースのページネーション（Bitbucket Cloud 用）。"""
    if limit < 0:
        raise ValueError("limit must be non-negative")
    results: list[dict[str, Any]] = []
    next_url: str | None = None
    first = True

    while True:
        if first:
            resp = client.get(path, params=params)
            first = False
        else:
            # ループ不変式: next_url は 1 周目以降必ずセットされている。
            # `assert` は `python -O` で剥がれるため、明示的に break で保護する。
            if next_url is None:
                break
            resp = client.get_absolute(next_url)

        try:
            body = resp.json()
        except ValueError:
            break
        if not isinstance(body, dict):
            break
        page_data = body.get(values_key, [])
        if not page_data:
            break
        results.extend(page_data)
        if limit > 0 and len(results) >= limit:
            results = results[:limit]
            break

        next_url = body.get(next_key)
        if not next_url or not isinstance(next_url, str):
            break
        if not _validate_same_origin(client.base_url, next_url):
            break

    return results


def paginate_offset(
    client: HttpClient,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    count: int = 100,
    limit: int = 30,
    count_key: str = "count",
    offset_key: str = "offset",
) -> list[dict[str, Any]]:
    """オフセットベースのページネーション（Backlog 用）。

    count デフォルトは 100 (Backlog API 上限)。ラウンドトリップ削減のため。
    """
    if limit < 0:
        raise ValueError("limit must be non-negative")
    if 0 < limit < count:
        count = limit
    params = dict(params or {})
    params[count_key] = count
    offset = 0
    results: list[dict[str, Any]] = []

    while True:
        params[offset_key] = offset
        resp = client.get(path, params=params)
        try:
            page_data = resp.json()
        except ValueError:
            break
        if not isinstance(page_data, list) or not page_data:
            break
        results.extend(page_data)
        if limit > 0 and len(results) >= limit:
            results = results[:limit]
            break
        if len(page_data) < count:
            break
        offset += count

    return results


def paginate_top_skip(
    client: HttpClient,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    top: int = 100,
    limit: int = 30,
    result_key: str = "value",
) -> list[dict[str, Any]]:
    """$top+$skip ベースのページネーション（Azure DevOps 用）。

    top デフォルトは 100。ラウンドトリップ削減のため。
    """
    if limit < 0:
        raise ValueError("limit must be non-negative")
    if 0 < limit < top:
        top = limit
    params = dict(params or {})
    params["$top"] = top
    skip = 0
    results: list[dict[str, Any]] = []

    while True:
        params["$skip"] = skip
        resp = client.get(path, params=params)
        try:
            body = resp.json()
        except ValueError:
            break
        if not isinstance(body, dict):
            break
        page_data = body.get(result_key, [])
        if not page_data:
            break
        results.extend(page_data)
        if limit > 0 and len(results) >= limit:
            results = results[:limit]
            break
        if len(page_data) < top:
            break
        skip += top

    return results
