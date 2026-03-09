"""HTTP クライアントとページネーション関数を提供するモジュール。"""

from __future__ import annotations

import re
import time
from typing import Any

import requests

import gfo.exceptions


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
        for attempt in range(self._max_retries + 1):
            try:
                resp = self._session.request(
                    method,
                    url,
                    params=merged_params,
                    json=json,
                    data=data,
                    headers=headers,
                    timeout=timeout,
                )
            except requests.ConnectionError as e:
                raise gfo.exceptions.NetworkError(str(e)) from e
            except requests.Timeout as e:
                raise gfo.exceptions.NetworkError(str(e)) from e

            try:
                self._handle_response(resp)
                return resp
            except gfo.exceptions.RateLimitError:
                if attempt >= self._max_retries:
                    raise
                wait = self._parse_retry_after(resp.headers.get("Retry-After"))
                time.sleep(wait)

        return resp  # unreachable; ループは必ず return か raise で終了する

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
        for attempt in range(self._max_retries + 1):
            try:
                resp = self._session.get(url, params=merged_params, timeout=timeout)
            except requests.ConnectionError as e:
                raise gfo.exceptions.NetworkError(str(e)) from e
            except requests.Timeout as e:
                raise gfo.exceptions.NetworkError(str(e)) from e

            try:
                self._handle_response(resp)
                return resp
            except gfo.exceptions.RateLimitError:
                if attempt >= self._max_retries:
                    raise
                wait = self._parse_retry_after(resp.headers.get("Retry-After"))
                time.sleep(wait)

        return resp  # unreachable; ループは必ず return か raise で終了する

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

        RFC 7231 では秒数整数と HTTP 日時形式の両方を許容しているため、
        int() 変換が失敗した場合（日時形式等）は default 秒を返す。
        """
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            return default

    @staticmethod
    def _mask_api_key(url: str) -> str:
        """URL 内の apiKey=xxx を apiKey=*** に置換する。"""
        return re.sub(r"apiKey=[^&]+", "apiKey=***", url)


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
    params = dict(params or {})
    params[per_page_key] = per_page
    results: list[dict] = []
    next_url: str | None = None

    while True:
        if next_url is None:
            resp = client.get(path, params=params)
        else:
            resp = client.get_absolute(next_url)

        page_data = resp.json()
        if not isinstance(page_data, list) or not page_data:
            break
        results.extend(page_data)
        if limit > 0 and len(results) >= limit:
            results = results[:limit]
            break

        link = resp.headers.get("Link", "")
        match = re.search(r'<([^>]+)>;\s*rel="next"', link)
        if not match:
            break
        next_url = match.group(1)

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
    params = dict(params or {})
    params["$top"] = top
    skip = 0
    results: list[dict] = []

    while True:
        params["$skip"] = skip
        resp = client.get(path, params=params)
        body = resp.json()
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
