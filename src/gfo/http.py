"""HTTP クライアントとページネーション関数を提供するモジュール。"""

from __future__ import annotations

import email.utils
import os
import re
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import requests

import gfo.exceptions

_MAX_RETRY_AFTER = 300
_VERIFY_SSL = os.environ.get("GFO_INSECURE", "").lower() not in ("1", "true", "yes")


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
            raise ValueError(
                "auth_header, auth_params, basic_auth are mutually exclusive."
            )
        self._base_url = base_url.rstrip("/")
        self._auth_params: dict[str, str] = auth_params or {}
        self._default_params: dict[str, str] = default_params or {}
        self._max_retries = max_retries
        self._session = requests.Session()
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
            except requests.ConnectionError as e:
                raise gfo.exceptions.NetworkError(self._mask_api_key(str(e))) from e
            except requests.Timeout as e:
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
        params: dict | None = None,
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
        return self._retry_loop(lambda: self._session.request(
            method, url,
            params=merged_params, json=json, data=data,
            headers=headers, timeout=timeout,
        ))

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

    def get_absolute(self, url: str, *, timeout: int = 30) -> requests.Response:
        """絶対 URL に対して GET リクエストを実行する。認証パラメータ・リトライを適用する。

        429 レートリミット時は Retry-After 秒待機して最大 max_retries 回再送する。
        再送後も 429 が継続する場合は RateLimitError を呼び出し元に伝播する。
        """
        merged_params = {**self._default_params, **self._auth_params}
        return self._retry_loop(
            lambda: self._session.get(url, params=merged_params, timeout=timeout)
        )

    def _handle_response(self, response: requests.Response) -> None:
        """ステータスコードを検査し、適切なエラーを送出する。"""
        code = response.status_code
        if 200 <= code < 300:
            return
        url = self._mask_api_key(response.url)
        if code in (401, 403):
            raise gfo.exceptions.AuthenticationError(code, url)
        if code == 404:
            raise gfo.exceptions.NotFoundError(url)
        if code == 429:
            retry_after = response.headers.get("Retry-After")
            raise gfo.exceptions.RateLimitError(
                self._parse_retry_after(retry_after) if retry_after else None, url
            )
        if 500 <= code < 600:
            raise gfo.exceptions.ServerError(code, url)
        raise gfo.exceptions.HttpError(code, response.text, url)

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
            diff = int((dt - datetime.now(timezone.utc)).total_seconds())
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
    return (base.scheme == target.scheme
            and base.hostname == target.hostname
            and base_port == target_port)


def paginate_link_header(
    client: HttpClient,
    path: str,
    *,
    params: dict | None = None,
    per_page: int = 30,
    per_page_key: str = "per_page",
    limit: int = 30,
) -> list[dict]:
    """Link header ベースのページネーション（GitHub / Gitea / GitBucket 用）。"""
    if limit < 0:
        raise ValueError("limit must be non-negative")
    if 0 < limit < per_page:
        per_page = limit
    params = dict(params or {})
    params[per_page_key] = per_page
    results: list[dict] = []
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
    params: dict | None = None,
    per_page: int = 20,
    limit: int = 30,
    next_page_header: str = "X-Next-Page",
) -> list[dict]:
    """ページパラメータ + ヘッダーベースのページネーション（GitLab 用）。"""
    if limit < 0:
        raise ValueError("limit must be non-negative")
    if 0 < limit < per_page:
        per_page = limit
    params = dict(params or {})
    params["per_page"] = per_page
    params["page"] = 1
    results: list[dict] = []

    while True:
        resp = client.get(path, params=params)
        page_data = resp.json()
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
    params: dict | None = None,
    limit: int = 30,
    values_key: str = "values",
    next_key: str = "next",
) -> list[dict]:
    """レスポンスボディベースのページネーション（Bitbucket Cloud 用）。"""
    if limit < 0:
        raise ValueError("limit must be non-negative")
    results: list[dict] = []
    next_url: str | None = None
    first = True

    while True:
        if first:
            resp = client.get(path, params=params)
            first = False
        else:
            resp = client.get_absolute(next_url)

        body = resp.json()
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
        if not next_url:
            break
        if not _validate_same_origin(client.base_url, next_url):
            break

    return results


def paginate_offset(
    client: HttpClient,
    path: str,
    *,
    params: dict | None = None,
    count: int = 20,
    limit: int = 30,
    count_key: str = "count",
    offset_key: str = "offset",
) -> list[dict]:
    """オフセットベースのページネーション（Backlog 用）。"""
    if limit < 0:
        raise ValueError("limit must be non-negative")
    if 0 < limit < count:
        count = limit
    params = dict(params or {})
    params[count_key] = count
    offset = 0
    results: list[dict] = []

    while True:
        params[offset_key] = offset
        resp = client.get(path, params=params)
        page_data = resp.json()
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
    params: dict | None = None,
    top: int = 30,
    limit: int = 30,
    result_key: str = "value",
) -> list[dict]:
    """$top+$skip ベースのページネーション（Azure DevOps 用）。"""
    if limit < 0:
        raise ValueError("limit must be non-negative")
    if 0 < limit < top:
        top = limit
    params = dict(params or {})
    params["$top"] = top
    skip = 0
    results: list[dict] = []

    while True:
        params["$skip"] = skip
        resp = client.get(path, params=params)
        body = resp.json()
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
