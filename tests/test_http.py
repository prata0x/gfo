"""http.py の HttpClient とページネーション関数をテストするモジュール。"""

import pytest
import responses

from gfo.exceptions import (
    AuthenticationError,
    HttpError,
    NetworkError,
    NotFoundError,
    RateLimitError,
    ServerError,
)
from gfo.http import (
    HttpClient,
    paginate_link_header,
    paginate_offset,
    paginate_page_param,
    paginate_response_body,
    paginate_top_skip,
)

BASE = "https://api.example.com"


# ── HttpClient 初期化 ──


class TestHttpClientInit:
    def test_base_url_trailing_slash_stripped(self):
        c = HttpClient("https://api.example.com/")
        assert c.base_url == "https://api.example.com"

    def test_auth_header_set(self):
        c = HttpClient(BASE, auth_header={"Authorization": "Bearer tok"})
        assert c._session.headers["Authorization"] == "Bearer tok"

    def test_basic_auth_set(self):
        c = HttpClient(BASE, basic_auth=("user", "pass"))
        assert c._session.auth == ("user", "pass")

    def test_extra_headers_set(self):
        c = HttpClient(BASE, extra_headers={"X-Custom": "val"})
        assert c._session.headers["X-Custom"] == "val"

    def test_mutually_exclusive_auth_raises(self):
        with pytest.raises(ValueError, match="mutually exclusive"):
            HttpClient(
                BASE,
                auth_header={"Authorization": "Bearer tok"},
                basic_auth=("u", "p"),
            )

    def test_mutually_exclusive_three_raises(self):
        with pytest.raises(ValueError, match="mutually exclusive"):
            HttpClient(
                BASE,
                auth_header={"Authorization": "Bearer tok"},
                auth_params={"apiKey": "k"},
                basic_auth=("u", "p"),
            )


# ── 基本リクエスト ──


class TestBasicRequests:
    @responses.activate
    def test_get(self):
        responses.add(responses.GET, f"{BASE}/items", json={"ok": True})
        c = HttpClient(BASE)
        resp = c.get("/items")
        assert resp.json() == {"ok": True}

    @responses.activate
    def test_post(self):
        responses.add(responses.POST, f"{BASE}/items", json={"id": 1}, status=201)
        c = HttpClient(BASE)
        resp = c.post("/items", json={"name": "x"})
        assert resp.status_code == 201

    @responses.activate
    def test_put(self):
        responses.add(responses.PUT, f"{BASE}/items/1", json={"ok": True})
        c = HttpClient(BASE)
        resp = c.put("/items/1", json={"name": "y"})
        assert resp.json() == {"ok": True}

    @responses.activate
    def test_patch(self):
        responses.add(responses.PATCH, f"{BASE}/items/1", json={"ok": True})
        c = HttpClient(BASE)
        resp = c.patch("/items/1", json={"name": "z"})
        assert resp.json() == {"ok": True}

    @responses.activate
    def test_delete(self):
        responses.add(responses.DELETE, f"{BASE}/items/1", status=204)
        c = HttpClient(BASE)
        resp = c.delete("/items/1")
        assert resp.status_code == 204


# ── パラメータマージ ──


class TestParamsMerge:
    @responses.activate
    def test_default_and_auth_and_request_params_merged(self):
        responses.add(responses.GET, f"{BASE}/x", json=[])
        c = HttpClient(
            BASE,
            auth_params={"apiKey": "secret"},
            default_params={"api-version": "7.1"},
        )
        c.get("/x", params={"state": "open"})
        assert responses.calls[0].request.params == {
            "api-version": "7.1",
            "apiKey": "secret",
            "state": "open",
        }

    @responses.activate
    def test_request_params_override(self):
        responses.add(responses.GET, f"{BASE}/x", json=[])
        c = HttpClient(BASE, default_params={"page": "1"})
        c.get("/x", params={"page": "2"})
        assert responses.calls[0].request.params["page"] == "2"


# ── エラーハンドリング ──


class TestErrorHandling:
    @responses.activate
    def test_401_raises_authentication_error(self):
        responses.add(responses.GET, f"{BASE}/x", status=401)
        c = HttpClient(BASE)
        with pytest.raises(AuthenticationError) as exc_info:
            c.get("/x")
        assert exc_info.value.status_code == 401

    @responses.activate
    def test_403_raises_authentication_error(self):
        responses.add(responses.GET, f"{BASE}/x", status=403)
        c = HttpClient(BASE)
        with pytest.raises(AuthenticationError) as exc_info:
            c.get("/x")
        assert exc_info.value.status_code == 403

    @responses.activate
    def test_404_raises_not_found(self):
        responses.add(responses.GET, f"{BASE}/x", status=404)
        c = HttpClient(BASE)
        with pytest.raises(NotFoundError):
            c.get("/x")

    @responses.activate
    def test_500_raises_server_error(self):
        responses.add(responses.GET, f"{BASE}/x", status=500)
        c = HttpClient(BASE)
        with pytest.raises(ServerError) as exc_info:
            c.get("/x")
        assert exc_info.value.status_code == 500

    @responses.activate
    def test_502_raises_server_error(self):
        responses.add(responses.GET, f"{BASE}/x", status=502)
        c = HttpClient(BASE)
        with pytest.raises(ServerError):
            c.get("/x")

    @responses.activate
    def test_418_raises_http_error(self):
        responses.add(responses.GET, f"{BASE}/x", status=418, body="teapot")
        c = HttpClient(BASE)
        with pytest.raises(HttpError) as exc_info:
            c.get("/x")
        assert exc_info.value.status_code == 418

    @responses.activate
    def test_connection_error_raises_network_error(self):
        import requests as req

        responses.add(
            responses.GET,
            f"{BASE}/x",
            body=req.ConnectionError("connection refused"),
        )
        c = HttpClient(BASE)
        with pytest.raises(NetworkError):
            c.get("/x")

    @responses.activate
    def test_timeout_raises_network_error(self):
        from requests.exceptions import ReadTimeout

        responses.add(responses.GET, f"{BASE}/x", body=ReadTimeout("timed out"))
        c = HttpClient(BASE)
        with pytest.raises(NetworkError):
            c.get("/x")


# ── 429 リトライ ──


class TestRateLimit:
    @responses.activate
    def test_429_retry_success(self, monkeypatch):
        monkeypatch.setattr("gfo.http.time.sleep", lambda _: None)
        responses.add(
            responses.GET,
            f"{BASE}/x",
            status=429,
            headers={"Retry-After": "1"},
        )
        responses.add(responses.GET, f"{BASE}/x", json={"ok": True})
        c = HttpClient(BASE)
        resp = c.get("/x")
        assert resp.json() == {"ok": True}
        assert len(responses.calls) == 2

    @responses.activate
    def test_429_retry_default_wait(self, monkeypatch):
        sleep_values = []
        monkeypatch.setattr(
            "gfo.http.time.sleep", lambda v: sleep_values.append(v)
        )
        responses.add(responses.GET, f"{BASE}/x", status=429)
        responses.add(responses.GET, f"{BASE}/x", json={"ok": True})
        c = HttpClient(BASE)
        c.get("/x")
        assert sleep_values == [60]

    @responses.activate
    def test_429_retry_also_429_raises(self, monkeypatch):
        monkeypatch.setattr("gfo.http.time.sleep", lambda _: None)
        responses.add(
            responses.GET,
            f"{BASE}/x",
            status=429,
            headers={"Retry-After": "1"},
        )
        responses.add(responses.GET, f"{BASE}/x", status=429)
        c = HttpClient(BASE)
        with pytest.raises(RateLimitError):
            c.get("/x")


# ── _mask_api_key ──


class TestMaskApiKey:
    def test_masks_api_key(self):
        url = "https://example.com/api?apiKey=secret123&other=val"
        assert HttpClient._mask_api_key(url) == (
            "https://example.com/api?apiKey=***&other=val"
        )

    def test_no_api_key_unchanged(self):
        url = "https://example.com/api?foo=bar"
        assert HttpClient._mask_api_key(url) == url


# ── paginate_link_header ──


class TestPaginateLinkHeader:
    @responses.activate
    def test_single_page(self):
        responses.add(responses.GET, f"{BASE}/items", json=[{"id": 1}])
        c = HttpClient(BASE)
        result = paginate_link_header(c, "/items", limit=10)
        assert result == [{"id": 1}]

    @responses.activate
    def test_multi_page(self):
        import json as json_mod

        next_url = f"{BASE}/items?page=2&per_page=2"
        call_count = {"n": 0}

        def callback(request):
            call_count["n"] += 1
            if call_count["n"] == 1:
                headers = {"Link": f'<{next_url}>; rel="next"'}
                return (200, headers, json_mod.dumps([{"id": 1}, {"id": 2}]))
            return (200, {}, json_mod.dumps([{"id": 3}]))

        responses.add_callback(responses.GET, f"{BASE}/items", callback=callback)
        c = HttpClient(BASE)
        result = paginate_link_header(c, "/items", per_page=2, limit=10)
        assert len(result) == 3
        assert call_count["n"] == 2

    @responses.activate
    def test_limit_truncates(self):
        responses.add(
            responses.GET,
            f"{BASE}/items",
            json=[{"id": 1}, {"id": 2}, {"id": 3}],
        )
        c = HttpClient(BASE)
        result = paginate_link_header(c, "/items", limit=2)
        assert len(result) == 2

    @responses.activate
    def test_empty_response(self):
        responses.add(responses.GET, f"{BASE}/items", json=[])
        c = HttpClient(BASE)
        result = paginate_link_header(c, "/items", limit=10)
        assert result == []


# ── paginate_page_param ──


class TestPaginatePageParam:
    @responses.activate
    def test_single_page(self):
        responses.add(responses.GET, f"{BASE}/items", json=[{"id": 1}])
        c = HttpClient(BASE)
        result = paginate_page_param(c, "/items", limit=10)
        assert result == [{"id": 1}]

    @responses.activate
    def test_multi_page(self):
        responses.add(
            responses.GET,
            f"{BASE}/items",
            json=[{"id": 1}],
            headers={"X-Next-Page": "2"},
        )
        responses.add(responses.GET, f"{BASE}/items", json=[{"id": 2}])
        c = HttpClient(BASE)
        result = paginate_page_param(c, "/items", limit=10)
        assert len(result) == 2

    @responses.activate
    def test_limit(self):
        responses.add(
            responses.GET,
            f"{BASE}/items",
            json=[{"id": 1}, {"id": 2}, {"id": 3}],
        )
        c = HttpClient(BASE)
        result = paginate_page_param(c, "/items", limit=2)
        assert len(result) == 2


# ── paginate_response_body ──


class TestPaginateResponseBody:
    @responses.activate
    def test_single_page(self):
        responses.add(
            responses.GET, f"{BASE}/items", json={"values": [{"id": 1}]}
        )
        c = HttpClient(BASE)
        result = paginate_response_body(c, "/items", limit=10)
        assert result == [{"id": 1}]

    @responses.activate
    def test_multi_page(self):
        responses.add(
            responses.GET,
            f"{BASE}/items",
            json={
                "values": [{"id": 1}],
                "next": f"{BASE}/items?page=2",
            },
        )
        responses.add(
            responses.GET,
            f"{BASE}/items?page=2",
            json={"values": [{"id": 2}]},
        )
        c = HttpClient(BASE)
        result = paginate_response_body(c, "/items", limit=10)
        assert len(result) == 2

    @responses.activate
    def test_empty(self):
        responses.add(responses.GET, f"{BASE}/items", json={"values": []})
        c = HttpClient(BASE)
        result = paginate_response_body(c, "/items", limit=10)
        assert result == []


# ── paginate_offset ──


class TestPaginateOffset:
    @responses.activate
    def test_single_page(self):
        responses.add(responses.GET, f"{BASE}/items", json=[{"id": 1}])
        c = HttpClient(BASE)
        result = paginate_offset(c, "/items", count=20, limit=10)
        assert result == [{"id": 1}]

    @responses.activate
    def test_multi_page(self):
        responses.add(responses.GET, f"{BASE}/items", json=[{"id": i} for i in range(20)])
        responses.add(responses.GET, f"{BASE}/items", json=[{"id": 20}])
        c = HttpClient(BASE)
        result = paginate_offset(c, "/items", count=20, limit=0)
        assert len(result) == 21

    @responses.activate
    def test_limit(self):
        responses.add(responses.GET, f"{BASE}/items", json=[{"id": i} for i in range(20)])
        c = HttpClient(BASE)
        result = paginate_offset(c, "/items", count=20, limit=5)
        assert len(result) == 5


# ── paginate_top_skip ──


class TestPaginateTopSkip:
    @responses.activate
    def test_single_page(self):
        responses.add(
            responses.GET, f"{BASE}/items", json={"value": [{"id": 1}]}
        )
        c = HttpClient(BASE)
        result = paginate_top_skip(c, "/items", top=30, limit=10)
        assert result == [{"id": 1}]

    @responses.activate
    def test_multi_page(self):
        responses.add(
            responses.GET,
            f"{BASE}/items",
            json={"value": [{"id": i} for i in range(3)]},
        )
        responses.add(
            responses.GET,
            f"{BASE}/items",
            json={"value": [{"id": 3}]},
        )
        c = HttpClient(BASE)
        result = paginate_top_skip(c, "/items", top=3, limit=0)
        assert len(result) == 4

    @responses.activate
    def test_limit(self):
        responses.add(
            responses.GET,
            f"{BASE}/items",
            json={"value": [{"id": i} for i in range(10)]},
        )
        c = HttpClient(BASE)
        result = paginate_top_skip(c, "/items", top=10, limit=5)
        assert len(result) == 5

    @responses.activate
    def test_empty(self):
        responses.add(responses.GET, f"{BASE}/items", json={"value": []})
        c = HttpClient(BASE)
        result = paginate_top_skip(c, "/items", top=30, limit=10)
        assert result == []
