"""http.py の HttpClient とページネーション関数をテストするモジュール。"""

from datetime import UTC

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
    _extract_next_link,
    _validate_same_origin,
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


class TestTlsVerifyPolicy:
    """GFO_INSECURE 環境変数の挙動。クラウド固定ホストでは無効化されない。"""

    def test_self_hosted_respects_gfo_insecure(self, monkeypatch):
        """self-hosted ホストでは GFO_INSECURE=1 が反映される。"""
        monkeypatch.setenv("GFO_INSECURE", "1")
        # _VERIFY_SSL はモジュールロード時に評価されるため、ここでは
        # _is_cloud_host_tls_forced の判定ロジック自体を検証する
        from gfo.http import _is_cloud_host_tls_forced

        assert _is_cloud_host_tls_forced("internal.example.com") is False
        assert _is_cloud_host_tls_forced("gitea.local") is False

    def test_cloud_hosts_are_protected(self):
        """クラウド固定ホストでは _is_cloud_host_tls_forced が True を返す。"""
        from gfo.http import _is_cloud_host_tls_forced

        # 主要クラウドホスト
        assert _is_cloud_host_tls_forced("github.com") is True
        assert _is_cloud_host_tls_forced("api.github.com") is True
        assert _is_cloud_host_tls_forced("uploads.github.com") is True
        assert _is_cloud_host_tls_forced("gitlab.com") is True
        assert _is_cloud_host_tls_forced("bitbucket.org") is True
        assert _is_cloud_host_tls_forced("api.bitbucket.org") is True
        assert _is_cloud_host_tls_forced("dev.azure.com") is True
        # サフィックスマッチ
        assert _is_cloud_host_tls_forced("myspace.backlog.com") is True
        assert _is_cloud_host_tls_forced("myspace.backlog.jp") is True
        assert _is_cloud_host_tls_forced("dev.myorg.visualstudio.com") is True

    def test_case_insensitive(self):
        """大文字小文字を区別せず判定する。"""
        from gfo.http import _is_cloud_host_tls_forced

        assert _is_cloud_host_tls_forced("GitHub.com") is True
        assert _is_cloud_host_tls_forced("MYSPACE.BACKLOG.COM") is True

    def test_trailing_dot_fqdn_normalized(self):
        """末尾ドット付き FQDN もクラウド固定ホストとして判定する（TLS 強制すり抜け防止）。"""
        from gfo.http import _is_cloud_host_tls_forced

        assert _is_cloud_host_tls_forced("github.com.") is True
        assert _is_cloud_host_tls_forced("api.github.com.") is True
        assert _is_cloud_host_tls_forced("GitHub.com.") is True
        assert _is_cloud_host_tls_forced("myspace.backlog.com.") is True

    def test_trailing_dot_verify_forced_under_insecure(self, monkeypatch):
        """GFO_INSECURE 相当 (_VERIFY_SSL=False) でも末尾ドット cloud host は TLS 検証する。"""
        import gfo.http

        monkeypatch.setattr(gfo.http, "_VERIFY_SSL", False)
        assert gfo.http._verify_for_url("https://github.com./o/r") is True
        # self-hosted は従来どおり _VERIFY_SSL に従う
        assert gfo.http._verify_for_url("https://internal.example.com/x") is False

    def test_none_returns_false(self):
        from gfo.http import _is_cloud_host_tls_forced

        assert _is_cloud_host_tls_forced(None) is False
        assert _is_cloud_host_tls_forced("") is False

    def test_cloud_host_client_always_verifies(self, monkeypatch):
        """クラウドホストの HttpClient は GFO_INSECURE 関係なく verify=True。"""
        # _VERIFY_SSL はモジュールロード時に決まるため monkeypatch で直接差し替える
        import gfo.http

        monkeypatch.setattr(gfo.http, "_VERIFY_SSL", False)
        c = HttpClient("https://github.com")
        assert c._session.verify is True

    def test_self_hosted_client_uses_verify_ssl(self, monkeypatch):
        """self-hosted ホストの HttpClient は _VERIFY_SSL 値に従う。"""
        import gfo.http

        monkeypatch.setattr(gfo.http, "_VERIFY_SSL", False)
        c = HttpClient("https://internal.example.com")
        assert c._session.verify is False

        monkeypatch.setattr(gfo.http, "_VERIFY_SSL", True)
        c2 = HttpClient("https://internal.example.com")
        assert c2._session.verify is True


class TestDownloadFileSizeLimit:
    """download_file は GFO_MAX_DOWNLOAD_BYTES を超えたら中断する。"""

    @responses.activate
    def test_within_limit_succeeds(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GFO_MAX_DOWNLOAD_BYTES", "1024")
        responses.add(
            responses.GET,
            f"{BASE}/file.bin",
            body=b"X" * 512,
            status=200,
        )
        c = HttpClient(BASE)
        out = tmp_path / "x.bin"
        c.download_file(f"{BASE}/file.bin", str(out))
        assert out.stat().st_size == 512

    @responses.activate
    def test_exceeds_limit_aborts(self, tmp_path, monkeypatch):
        from gfo.exceptions import GfoError

        monkeypatch.setenv("GFO_MAX_DOWNLOAD_BYTES", "100")
        responses.add(
            responses.GET,
            f"{BASE}/big.bin",
            body=b"X" * 1024,
            status=200,
        )
        c = HttpClient(BASE)
        out = tmp_path / "big.bin"
        with pytest.raises(GfoError, match="exceeded GFO_MAX_DOWNLOAD_BYTES"):
            c.download_file(f"{BASE}/big.bin", str(out))
        # 部分書き込みファイルは削除される
        assert not out.exists()

    @responses.activate
    def test_zero_disables_limit(self, tmp_path, monkeypatch):
        """GFO_MAX_DOWNLOAD_BYTES=0 のとき、大きなレスポンスでも中断しない (無制限)。"""
        monkeypatch.setenv("GFO_MAX_DOWNLOAD_BYTES", "0")
        responses.add(
            responses.GET,
            f"{BASE}/file.bin",
            body=b"X" * (10 * 1024 * 1024),  # 10 MiB
            status=200,
        )
        c = HttpClient(BASE)
        out = tmp_path / "x.bin"
        c.download_file(f"{BASE}/file.bin", str(out))
        assert out.stat().st_size == 10 * 1024 * 1024

    @responses.activate
    def test_invalid_env_falls_back_to_default(self, tmp_path, monkeypatch, recwarn):
        """GFO_MAX_DOWNLOAD_BYTES='invalid' は 5 GiB デフォルトにフォールバック + warning。"""
        monkeypatch.setenv("GFO_MAX_DOWNLOAD_BYTES", "invalid")
        responses.add(
            responses.GET,
            f"{BASE}/file.bin",
            body=b"X" * 1024,
            status=200,
        )
        c = HttpClient(BASE)
        out = tmp_path / "x.bin"
        c.download_file(f"{BASE}/file.bin", str(out))
        assert out.stat().st_size == 1024
        # 警告メッセージが発火されていること (フォールバック告知)
        warnings_text = " ".join(str(w.message) for w in recwarn.list)
        assert "GFO_MAX_DOWNLOAD_BYTES" in warnings_text
        assert "invalid" in warnings_text

    @responses.activate
    def test_boundary_equal_and_over(self, tmp_path, monkeypatch):
        """境界値: body サイズ == max_bytes は成功、+1 で失敗。"""
        from gfo.exceptions import GfoError

        monkeypatch.setenv("GFO_MAX_DOWNLOAD_BYTES", "1024")
        # 1024 バイトちょうど → 成功 (累積バイト数が max_bytes を「超えた」場合のみ中断)
        responses.add(
            responses.GET,
            f"{BASE}/exact.bin",
            body=b"X" * 1024,
            status=200,
        )
        c = HttpClient(BASE)
        out_ok = tmp_path / "exact.bin"
        c.download_file(f"{BASE}/exact.bin", str(out_ok))
        assert out_ok.stat().st_size == 1024
        # 1025 バイト → 失敗
        responses.add(
            responses.GET,
            f"{BASE}/over.bin",
            body=b"X" * 1025,
            status=200,
        )
        out_ng = tmp_path / "over.bin"
        with pytest.raises(GfoError, match="exceeded GFO_MAX_DOWNLOAD_BYTES"):
            c.download_file(f"{BASE}/over.bin", str(out_ng))


class TestMaxDownloadBytesBoundary:
    """`_max_download_bytes` の境界値・無効値のフォールバック挙動。"""

    def test_zero_returns_zero(self, monkeypatch):
        monkeypatch.setenv("GFO_MAX_DOWNLOAD_BYTES", "0")
        from gfo.http import _max_download_bytes

        assert _max_download_bytes() == 0

    def test_one_returns_one(self, monkeypatch):
        monkeypatch.setenv("GFO_MAX_DOWNLOAD_BYTES", "1")
        from gfo.http import _max_download_bytes

        assert _max_download_bytes() == 1

    def test_negative_clamped_to_zero(self, monkeypatch):
        """負の値は max(0, n) で 0 (無制限) に丸められる。"""
        monkeypatch.setenv("GFO_MAX_DOWNLOAD_BYTES", "-100")
        from gfo.http import _max_download_bytes

        # 負の値は 0 に切り上げ (= 無制限扱い)
        assert _max_download_bytes() == 0


class TestInsecureEnvWarning:
    """GFO_INSECURE=1 のとき、起動時に stderr で警告が出ること。"""

    def test_insecure_env_emits_startup_warning(self, monkeypatch, capsys):
        """GFO_INSECURE=1 で gfo.http をリロードすると stderr に警告が出力される。"""
        import importlib

        import gfo.http

        monkeypatch.setenv("GFO_INSECURE", "1")
        importlib.reload(gfo.http)
        captured = capsys.readouterr()
        assert "GFO_INSECURE" in captured.err
        # クラウドホストは TLS 検証を強制する旨が含まれている
        assert "Cloud" in captured.err or "github.com" in captured.err
        # テスト後にもとの状態 (GFO_INSECURE 未設定) に戻す
        monkeypatch.delenv("GFO_INSECURE")
        importlib.reload(gfo.http)


class TestErrorBodyTruncation:
    """HttpError の body は大きすぎる場合に切り詰められる。"""

    @responses.activate
    def test_large_error_body_is_truncated(self):
        """4 KB を超えるエラーボディは先頭で切り詰められて [truncated N chars] が付く。"""
        from gfo.http import _MAX_ERROR_BODY_CHARS

        big_body = "X" * (_MAX_ERROR_BODY_CHARS * 2)
        responses.add(responses.GET, f"{BASE}/items", body=big_body, status=400)
        c = HttpClient(BASE)
        with pytest.raises(HttpError) as exc_info:
            c.get("/items")
        msg = str(exc_info.value)
        assert "truncated" in msg
        # 元の body 長さは含まれない（切り詰められた）
        assert big_body not in msg

    @responses.activate
    def test_small_error_body_is_not_truncated(self):
        """通常サイズのエラーボディはそのまま例外に載る。"""
        responses.add(responses.GET, f"{BASE}/items", body="short error", status=400)
        c = HttpClient(BASE)
        with pytest.raises(HttpError) as exc_info:
            c.get("/items")
        assert "short error" in str(exc_info.value)
        assert "truncated" not in str(exc_info.value)

    @responses.activate
    def test_truncation_preserves_prefix_and_counts_dropped_chars(self):
        """切り詰め時、先頭 _MAX_ERROR_BODY_CHARS 文字はそのまま残り、
        メッセージ末尾の `[truncated N chars]` の N が正しい drop 数になっていること。"""
        import re

        from gfo.http import _MAX_ERROR_BODY_CHARS

        extra = 73  # 適当な追加長 (N の検証用)
        big_body = "X" * (_MAX_ERROR_BODY_CHARS + extra)
        responses.add(responses.GET, f"{BASE}/items", body=big_body, status=400)
        c = HttpClient(BASE)
        with pytest.raises(HttpError) as exc_info:
            c.get("/items")
        msg = str(exc_info.value)
        # 先頭 _MAX_ERROR_BODY_CHARS 文字 (全部 X) はそのまま残る
        assert "X" * _MAX_ERROR_BODY_CHARS in msg
        # [truncated N chars] の N が drop 数 = extra と一致する
        m = re.search(r"\[truncated (\d+) chars\]", msg)
        assert m is not None
        assert int(m.group(1)) == extra


class TestDownloadFileCrossOrigin:
    """download_file は別オリジン URL に対しては認証情報を送らない。

    GitLab の release asset link は direct_asset_url に外部 URL を持てるため、
    そのまま PAT を送ると外部ホストへトークン漏えいする。
    """

    @responses.activate
    def test_same_origin_includes_authorization(self, tmp_path):
        """同一オリジンへのダウンロードは Authorization ヘッダを送る。"""
        responses.add(
            responses.GET,
            "https://gitlab.example.com/api/v4/projects/1/releases",
            body=b"data",
            status=200,
        )
        c = HttpClient(
            "https://gitlab.example.com/api/v4",
            auth_header={"PRIVATE-TOKEN": "secret-pat"},
        )
        out = tmp_path / "x.bin"
        c.download_file("https://gitlab.example.com/api/v4/projects/1/releases", str(out))
        sent = responses.calls[0].request
        assert sent.headers.get("PRIVATE-TOKEN") == "secret-pat"

    @responses.activate
    def test_cross_origin_strips_authorization(self, tmp_path):
        """別オリジンへのダウンロードでは PRIVATE-TOKEN / Authorization を送らない。"""
        responses.add(
            responses.GET,
            "https://attacker.example.com/evil.zip",
            body=b"data",
            status=200,
        )
        c = HttpClient(
            "https://gitlab.example.com/api/v4",
            auth_header={"PRIVATE-TOKEN": "secret-pat"},
        )
        out = tmp_path / "x.bin"
        c.download_file("https://attacker.example.com/evil.zip", str(out))
        sent = responses.calls[0].request
        # 認証ヘッダが送られていないことを確認
        assert "PRIVATE-TOKEN" not in sent.headers
        assert "Authorization" not in sent.headers

    @responses.activate
    def test_cross_origin_strips_basic_auth(self, tmp_path):
        """別オリジンへのダウンロードでは Basic 認証も送らない。"""
        responses.add(
            responses.GET,
            "https://attacker.example.com/evil.zip",
            body=b"data",
            status=200,
        )
        c = HttpClient(
            "https://bitbucket.example.com/api",
            basic_auth=("alice", "secret-pat"),
        )
        out = tmp_path / "x.bin"
        c.download_file("https://attacker.example.com/evil.zip", str(out))
        sent = responses.calls[0].request
        assert "Authorization" not in sent.headers

    @responses.activate
    def test_cross_origin_strips_auth_params(self, tmp_path):
        """別オリジンへのダウンロードでは auth_params (Backlog apiKey) も送らない。"""
        responses.add(
            responses.GET,
            "https://attacker.example.com/evil.zip",
            body=b"data",
            status=200,
        )
        c = HttpClient(
            "https://myspace.backlog.com/api/v2",
            auth_params={"apiKey": "secret-key"},
        )
        out = tmp_path / "x.bin"
        c.download_file("https://attacker.example.com/evil.zip", str(out))
        sent = responses.calls[0].request
        assert "apiKey" not in (sent.url or "")

    def test_cross_origin_to_cloud_host_uses_verify_true(self, tmp_path):
        """別オリジンでもクラウド固定ホストへのダウンロードは verify=True で送られる。

        `gfo.http.requests.request` を直接 patch して、kwargs の verify が
        True (= TLS 検証有効) になっていることを確認する。
        """
        from unittest.mock import MagicMock
        from unittest.mock import patch as upatch

        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.iter_content.return_value = [b"data"]
        fake_resp.url = "https://api.github.com/release/asset.zip"
        c = HttpClient(
            "https://gitlab.example.com/api/v4",
            auth_header={"PRIVATE-TOKEN": "secret-pat"},
        )
        out = tmp_path / "x.bin"
        with upatch("gfo.http.requests.request", return_value=fake_resp) as mock_req:
            c.download_file("https://api.github.com/release/asset.zip", str(out))
        # クラウド固定ホスト (api.github.com) なので verify=True で送られる
        assert mock_req.call_args.kwargs.get("verify") is True


# ── request_stream ──


class TestRequestStream:
    """`HttpClient.request_stream` のストリーミング応答とエラーハンドリング。"""

    @responses.activate
    def test_same_origin_yields_chunks_in_order(self):
        """同一オリジンの相対パス GET で複数チャンクが順に yield される。"""
        responses.add(
            responses.GET,
            f"{BASE}/stream",
            body=b"abcdefghij",
            status=200,
        )
        c = HttpClient(BASE)
        chunks = list(c.request_stream("GET", "/stream", chunk_size=4))
        # body 全体が結合できること
        assert b"".join(chunks) == b"abcdefghij"

    @responses.activate
    def test_same_origin_sends_auth(self):
        """同一オリジンへの request_stream は Authorization ヘッダを送る。"""
        responses.add(
            responses.GET,
            f"{BASE}/stream",
            body=b"data",
            status=200,
        )
        c = HttpClient(BASE, auth_header={"Authorization": "Bearer tok"})
        list(c.request_stream("GET", "/stream"))
        sent = responses.calls[0].request
        assert sent.headers.get("Authorization") == "Bearer tok"

    @responses.activate
    def test_cross_origin_strips_auth(self):
        """別オリジンの絶対 URL へ request_stream を呼ぶと認証ヘッダは送られない。"""
        responses.add(
            responses.GET,
            "https://attacker.example.com/evil.bin",
            body=b"data",
            status=200,
        )
        c = HttpClient(
            "https://gitlab.example.com/api/v4",
            auth_header={"PRIVATE-TOKEN": "secret-pat"},
        )
        list(c.request_stream("GET", "https://attacker.example.com/evil.bin"))
        sent = responses.calls[0].request
        assert "PRIVATE-TOKEN" not in sent.headers
        assert "Authorization" not in sent.headers

    @responses.activate
    def test_404_raises_not_found_error(self):
        """404 応答は NotFoundError として送出される。"""
        responses.add(
            responses.GET,
            f"{BASE}/missing",
            json={"message": "not found"},
            status=404,
        )
        c = HttpClient(BASE)
        with pytest.raises(NotFoundError):
            c.request_stream("GET", "/missing")

    @responses.activate
    def test_429_raises_rate_limit_error(self):
        """429 応答は RateLimitError として送出される（リトライなし）。"""
        responses.add(
            responses.GET,
            f"{BASE}/limited",
            json={"message": "rate limited"},
            status=429,
            headers={"Retry-After": "1"},
        )
        c = HttpClient(BASE, max_retries=0)
        with pytest.raises(RateLimitError):
            c.request_stream("GET", "/limited")


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

    @responses.activate
    def test_ssl_error_raises_network_error(self):
        """SSLError 等の RequestException サブクラスも NetworkError に変換される。"""
        from requests.exceptions import SSLError

        responses.add(responses.GET, f"{BASE}/x", body=SSLError("certificate verify failed"))
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
        monkeypatch.setattr("gfo.http.time.sleep", lambda v: sleep_values.append(v))
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

    @responses.activate
    def test_429_retry_then_connection_error(self, monkeypatch):
        import requests as req

        monkeypatch.setattr("gfo.http.time.sleep", lambda _: None)
        responses.add(
            responses.GET,
            f"{BASE}/x",
            status=429,
            headers={"Retry-After": "1"},
        )
        responses.add(
            responses.GET,
            f"{BASE}/x",
            body=req.ConnectionError("disconnected"),
        )
        c = HttpClient(BASE)
        with pytest.raises(NetworkError):
            c.get("/x")

    @responses.activate
    def test_429_retry_then_timeout(self, monkeypatch):
        from requests.exceptions import ReadTimeout

        monkeypatch.setattr("gfo.http.time.sleep", lambda _: None)
        responses.add(
            responses.GET,
            f"{BASE}/x",
            status=429,
            headers={"Retry-After": "1"},
        )
        responses.add(responses.GET, f"{BASE}/x", body=ReadTimeout("timeout"))
        c = HttpClient(BASE)
        with pytest.raises(NetworkError):
            c.get("/x")


# ── _parse_retry_after ──


class TestParseRetryAfter:
    def test_integer_seconds(self):
        assert HttpClient._parse_retry_after("30") == 30

    def test_zero_clamps_to_one(self):
        assert HttpClient._parse_retry_after("0") == 1

    def test_negative_clamps_to_one(self):
        assert HttpClient._parse_retry_after("-5") == 1

    def test_none_returns_default(self):
        assert HttpClient._parse_retry_after(None) == 60
        assert HttpClient._parse_retry_after(None, default=10) == 10

    def test_invalid_string_returns_default(self):
        assert HttpClient._parse_retry_after("invalid") == 60

    def test_http_date_future(self, monkeypatch):
        """HTTP-date 形式（未来の日時）が秒数に変換される。"""
        from datetime import datetime

        future = datetime(2099, 1, 1, 0, 0, 0, tzinfo=UTC)
        monkeypatch.setattr(
            "gfo.http.datetime",
            type(
                "_MockDatetime",
                (),
                {
                    "now": staticmethod(
                        lambda tz=None: future - __import__("datetime").timedelta(seconds=120)
                    )
                },
            )(),
        )
        # HTTP-date で 120 秒後を指定
        import email.utils

        date_str = email.utils.format_datetime(future)
        result = HttpClient._parse_retry_after(date_str)
        assert result == 120

    def test_http_date_past_clamps_to_one(self):
        """HTTP-date が過去の日時を示す場合は 1 秒にクランプされる。"""
        # 過去の日時を指定
        past_date = "Mon, 01 Jan 2000 00:00:00 GMT"
        assert HttpClient._parse_retry_after(past_date) == 1


# ── _mask_api_key ──


class TestMaskApiKey:
    def test_masks_api_key(self):
        url = "https://example.com/api?apiKey=secret123&other=val"
        assert HttpClient._mask_api_key(url) == ("https://example.com/api?apiKey=***&other=val")

    def test_no_api_key_unchanged(self):
        url = "https://example.com/api?foo=bar"
        assert HttpClient._mask_api_key(url) == url


# ── paginate_link_header ──


class TestPaginateNegativeLimit:
    def test_link_header_negative_limit_raises(self):
        c = HttpClient(BASE)
        with pytest.raises(ValueError, match="non-negative"):
            paginate_link_header(c, "/items", limit=-1)

    def test_page_param_negative_limit_raises(self):
        c = HttpClient(BASE)
        with pytest.raises(ValueError, match="non-negative"):
            paginate_page_param(c, "/items", limit=-1)

    def test_response_body_negative_limit_raises(self):
        c = HttpClient(BASE)
        with pytest.raises(ValueError, match="non-negative"):
            paginate_response_body(c, "/items", limit=-1)

    def test_offset_negative_limit_raises(self):
        c = HttpClient(BASE)
        with pytest.raises(ValueError, match="non-negative"):
            paginate_offset(c, "/items", limit=-1)

    def test_top_skip_negative_limit_raises(self):
        c = HttpClient(BASE)
        with pytest.raises(ValueError, match="non-negative"):
            paginate_top_skip(c, "/items", limit=-1)


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

    @responses.activate
    def test_limit_zero_unlimited(self):
        import json as json_mod

        next_url = f"{BASE}/items?page=2&per_page=30"
        call_count = {"n": 0}

        def callback(request):
            call_count["n"] += 1
            if call_count["n"] == 1:
                headers = {"Link": f'<{next_url}>; rel="next"'}
                return (200, headers, json_mod.dumps([{"id": 1}, {"id": 2}]))
            return (200, {}, json_mod.dumps([{"id": 3}, {"id": 4}]))

        responses.add_callback(responses.GET, f"{BASE}/items", callback=callback)
        c = HttpClient(BASE)
        result = paginate_link_header(c, "/items", limit=0)
        assert len(result) == 4
        assert call_count["n"] == 2

    @responses.activate
    def test_custom_per_page_key(self):
        """per_page_key="limit" 指定時にリクエスト URL に limit= が使われる。"""
        responses.add(responses.GET, f"{BASE}/items", json=[{"id": 1}])
        c = HttpClient(BASE)
        paginate_link_header(c, "/items", per_page_key="limit", per_page=20, limit=30)
        assert "limit=20" in responses.calls[0].request.url
        assert "per_page=" not in responses.calls[0].request.url

    @responses.activate
    def test_second_page_connection_error(self):
        import json as json_mod

        import requests as req_lib

        next_url = f"{BASE}/items?page=2"

        def callback(request):
            headers = {"Link": f'<{next_url}>; rel="next"'}
            return (200, headers, json_mod.dumps([{"id": 1}]))

        responses.add_callback(responses.GET, f"{BASE}/items", callback=callback)
        responses.add(responses.GET, next_url, body=req_lib.ConnectionError("refused"))
        c = HttpClient(BASE)
        with pytest.raises(NetworkError):
            paginate_link_header(c, "/items", limit=10)

    @responses.activate
    def test_per_page_limited_to_limit(self):
        """limit=2 のとき per_page が 2 に切り詰められる。"""
        responses.add(responses.GET, f"{BASE}/items", json=[{"id": 1}, {"id": 2}])
        c = HttpClient(BASE)
        paginate_link_header(c, "/items", per_page=30, limit=2)
        assert "per_page=2" in responses.calls[0].request.url

    @responses.activate
    def test_three_pages(self):
        """3 ページ以上の連鎖ページネーションが正しく結合される。"""
        import json as json_mod

        page2_url = f"{BASE}/items?page=2"
        page3_url = f"{BASE}/items?page=3"
        call_count = {"n": 0}

        def callback(request):
            call_count["n"] += 1
            if call_count["n"] == 1:
                headers = {"Link": f'<{page2_url}>; rel="next"'}
                return (200, headers, json_mod.dumps([{"id": 1}]))
            if call_count["n"] == 2:
                headers = {"Link": f'<{page3_url}>; rel="next"'}
                return (200, headers, json_mod.dumps([{"id": 2}]))
            return (200, {}, json_mod.dumps([{"id": 3}]))

        responses.add_callback(responses.GET, f"{BASE}/items", callback=callback)
        c = HttpClient(BASE)
        result = paginate_link_header(c, "/items", limit=0)
        assert len(result) == 3
        assert call_count["n"] == 3

    @responses.activate
    def test_non_json_response_stops_pagination(self):
        """200 で非 JSON レスポンスを返した場合、ループを終了して空リストを返す。"""
        responses.add(
            responses.GET,
            f"{BASE}/items",
            body="<html>not json</html>",
            status=200,
            content_type="text/html",
        )
        c = HttpClient(BASE)
        result = paginate_link_header(c, "/items", limit=10)
        assert result == []

    @responses.activate
    def test_cross_origin_next_link_stops_pagination(self):
        """Link ヘッダーの next URL が異なるオリジンの場合はページネーションを停止する。"""
        import json as json_mod

        cross_origin_url = "https://evil.com/items?page=2"

        def callback(request):
            headers = {"Link": f'<{cross_origin_url}>; rel="next"'}
            return (200, headers, json_mod.dumps([{"id": 1}]))

        responses.add_callback(responses.GET, f"{BASE}/items", callback=callback)
        c = HttpClient(BASE)
        result = paginate_link_header(c, "/items", limit=10)
        assert result == [{"id": 1}]


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

    @responses.activate
    def test_empty_response(self):
        responses.add(responses.GET, f"{BASE}/items", json=[])
        c = HttpClient(BASE)
        result = paginate_page_param(c, "/items", limit=10)
        assert result == []

    @responses.activate
    def test_limit_zero_unlimited(self):
        responses.add(
            responses.GET,
            f"{BASE}/items",
            json=[{"id": 1}, {"id": 2}],
            headers={"X-Next-Page": "2"},
        )
        responses.add(
            responses.GET,
            f"{BASE}/items",
            json=[{"id": 3}, {"id": 4}],
        )
        c = HttpClient(BASE)
        result = paginate_page_param(c, "/items", limit=0)
        assert len(result) == 4

    @responses.activate
    def test_per_page_limited_to_limit(self):
        """limit=2 のとき per_page が 2 に切り詰められる。"""
        responses.add(responses.GET, f"{BASE}/items", json=[{"id": 1}, {"id": 2}])
        c = HttpClient(BASE)
        paginate_page_param(c, "/items", per_page=20, limit=2)
        assert "per_page=2" in responses.calls[0].request.url

    @responses.activate
    def test_next_page_header_non_integer_stops_pagination(self):
        """X-Next-Page が整数でない場合はページネーションを停止する。"""
        responses.add(
            responses.GET,
            f"{BASE}/items",
            json=[{"id": 1}],
            headers={"X-Next-Page": "invalid"},
        )
        c = HttpClient(BASE)
        result = paginate_page_param(c, "/items", limit=10)
        assert result == [{"id": 1}]

    @responses.activate
    def test_non_json_response_stops_pagination(self):
        """200 で非 JSON レスポンスが返ったときページネーションを停止して空リストを返す。"""
        responses.add(
            responses.GET,
            f"{BASE}/items",
            body="<html>not json</html>",
            content_type="text/html",
            status=200,
        )
        c = HttpClient(BASE)
        result = paginate_page_param(c, "/items", limit=10)
        assert result == []


# ── paginate_response_body ──


class TestPaginateResponseBody:
    @responses.activate
    def test_single_page(self):
        responses.add(responses.GET, f"{BASE}/items", json={"values": [{"id": 1}]})
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

    @responses.activate
    def test_limit_zero_unlimited(self):
        next_url = f"{BASE}/items?page=2"
        responses.add(
            responses.GET,
            f"{BASE}/items",
            json={"values": [{"id": 1}, {"id": 2}], "next": next_url},
        )
        responses.add(
            responses.GET,
            next_url,
            json={"values": [{"id": 3}, {"id": 4}]},
        )
        c = HttpClient(BASE)
        result = paginate_response_body(c, "/items", limit=0)
        assert len(result) == 4

    @responses.activate
    def test_non_dict_body_stops_pagination(self):
        """レスポンスボディが dict でない場合はページネーションを停止する。"""
        responses.add(responses.GET, f"{BASE}/items", json=[1, 2, 3])
        c = HttpClient(BASE)
        result = paginate_response_body(c, "/items", limit=10)
        assert result == []

    @responses.activate
    def test_limit_truncates_results(self):
        """結果が limit を超える場合に切り詰められる。"""
        next_url = f"{BASE}/items?page=2"
        responses.add(
            responses.GET,
            f"{BASE}/items",
            json={"values": [{"id": 1}, {"id": 2}, {"id": 3}], "next": next_url},
        )
        c = HttpClient(BASE)
        result = paginate_response_body(c, "/items", limit=2)
        assert len(result) == 2

    @responses.activate
    def test_cross_origin_next_url_stops_pagination(self):
        """next URL が異なるオリジンの場合はページネーションを停止する。"""
        cross_origin_url = "https://evil.com/items?page=2"
        responses.add(
            responses.GET,
            f"{BASE}/items",
            json={"values": [{"id": 1}], "next": cross_origin_url},
        )
        c = HttpClient(BASE)
        result = paginate_response_body(c, "/items", limit=10)
        assert result == [{"id": 1}]

    @responses.activate
    def test_non_json_response_stops_pagination(self):
        """200 で非 JSON レスポンスが返ったときページネーションを停止して空リストを返す。"""
        responses.add(
            responses.GET,
            f"{BASE}/items",
            body="<html>not json</html>",
            content_type="text/html",
            status=200,
        )
        c = HttpClient(BASE)
        result = paginate_response_body(c, "/items", limit=10)
        assert result == []

    @responses.activate
    def test_non_string_next_url_stops_pagination(self):
        """next フィールドが文字列以外（整数等）の場合はページネーションを停止する（R29修正確認）。"""
        responses.add(
            responses.GET,
            f"{BASE}/items",
            json={"values": [{"id": 1}], "next": 42},
        )
        c = HttpClient(BASE)
        result = paginate_response_body(c, "/items", limit=10)
        assert result == [{"id": 1}]


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

    @responses.activate
    def test_empty_response(self):
        responses.add(responses.GET, f"{BASE}/items", json=[])
        c = HttpClient(BASE)
        result = paginate_offset(c, "/items", count=20, limit=10)
        assert result == []

    @responses.activate
    def test_non_json_response_stops_pagination(self):
        """200 で非 JSON レスポンスが返ったときページネーションを停止して空リストを返す。"""
        responses.add(
            responses.GET,
            f"{BASE}/items",
            body="<html>not json</html>",
            content_type="text/html",
            status=200,
        )
        c = HttpClient(BASE)
        result = paginate_offset(c, "/items", count=20, limit=10)
        assert result == []


# ── paginate_top_skip ──


class TestPaginateTopSkip:
    @responses.activate
    def test_single_page(self):
        responses.add(responses.GET, f"{BASE}/items", json={"value": [{"id": 1}]})
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

    @responses.activate
    def test_non_dict_body_stops_pagination(self):
        """レスポンスボディが dict でない場合はページネーションを停止する。"""
        responses.add(responses.GET, f"{BASE}/items", json=[1, 2, 3])
        c = HttpClient(BASE)
        result = paginate_top_skip(c, "/items", top=30, limit=10)
        assert result == []

    @responses.activate
    def test_non_json_response_stops_pagination(self):
        """200 で非 JSON レスポンスが返ったときページネーションを停止して空リストを返す。"""
        responses.add(
            responses.GET,
            f"{BASE}/items",
            body="<html>not json</html>",
            content_type="text/html",
            status=200,
        )
        c = HttpClient(BASE)
        result = paginate_top_skip(c, "/items", top=30, limit=10)
        assert result == []


# ── _validate_same_origin ──


class TestValidateSameOrigin:
    def test_same_origin(self):
        assert (
            _validate_same_origin(
                "https://api.example.com/v1/items",
                "https://api.example.com/v1/items?page=2",
            )
            is True
        )

    def test_different_host_blocked(self):
        assert (
            _validate_same_origin(
                "https://api.example.com/v1",
                "https://api.evil.com/v1",
            )
            is False
        )

    def test_different_scheme_blocked(self):
        assert (
            _validate_same_origin(
                "https://api.example.com/v1",
                "http://api.example.com/v1",
            )
            is False
        )

    def test_different_port_blocked(self):
        assert (
            _validate_same_origin(
                "https://api.example.com:8080/v1",
                "https://api.example.com:9000/v1",
            )
            is False
        )

    def test_subdomain_blocked(self):
        assert (
            _validate_same_origin(
                "https://api.example.com/v1",
                "https://evil.example.com/v1",
            )
            is False
        )

    def test_implicit_vs_explicit_default_port(self):
        """https://host と https://host:443 は同一オリジン。"""
        assert (
            _validate_same_origin(
                "https://api.example.com/v1",
                "https://api.example.com:443/v1",
            )
            is True
        )

    def test_http_default_port(self):
        """http://host と http://host:80 は同一オリジン。"""
        assert (
            _validate_same_origin(
                "http://api.example.com/v1",
                "http://api.example.com:80/v1",
            )
            is True
        )


# ── _extract_next_link ──


class TestExtractNextLink:
    def test_basic(self):
        link = '<https://api.example.com/items?page=2>; rel="next"'
        assert _extract_next_link(link) == "https://api.example.com/items?page=2"

    def test_with_prev(self):
        link = '<https://api.example.com/items?page=1>; rel="prev", <https://api.example.com/items?page=3>; rel="next"'
        assert _extract_next_link(link) == "https://api.example.com/items?page=3"

    def test_param_order_variation(self):
        """rel が URL の直後でなくても正しく抽出する（RFC 5988 順序非依存）。"""
        link = '<https://api.example.com/items?page=2>; title="Page 2"; rel="next"'
        assert _extract_next_link(link) == "https://api.example.com/items?page=2"

    def test_no_next(self):
        link = '<https://api.example.com/items?page=1>; rel="prev"'
        assert _extract_next_link(link) is None

    def test_empty_string(self):
        assert _extract_next_link("") is None


# ── upload_file リトライ (C-02) ──


class TestUploadFileRetry:
    @responses.activate
    def test_upload_file_retry_sends_data_on_second_attempt(self, tmp_path, monkeypatch):
        """429 → 200 リトライで2回目もファイルデータが送信されることを検証する。"""
        # Retry-After:0 は下限 1s にクランプされるため実 sleep を無効化する (検証対象は body)。
        monkeypatch.setattr("gfo.http.time.sleep", lambda _: None)
        test_file = tmp_path / "test.bin"
        test_file.write_bytes(b"hello world")
        client = HttpClient(BASE, auth_header={"Authorization": "Bearer tok"}, max_retries=1)
        responses.add(
            responses.POST,
            f"{BASE}/upload",
            status=429,
            headers={"Retry-After": "0"},
        )
        responses.add(
            responses.POST,
            f"{BASE}/upload",
            json={"ok": True},
            status=200,
        )
        resp = client.upload_file("/upload", str(test_file))
        assert resp.status_code == 200
        # 2回目のリクエストのボディが空でないことを検証
        assert responses.calls[1].request.body == b"hello world"

    @responses.activate
    def test_upload_multipart_retry_sends_data_on_second_attempt(self, tmp_path, monkeypatch):
        """429 → 200 リトライで multipart でも2回目にデータが送信されることを検証する。"""
        # Retry-After:0 は下限 1s にクランプされるため実 sleep を無効化する (検証対象は body)。
        monkeypatch.setattr("gfo.http.time.sleep", lambda _: None)
        test_file = tmp_path / "test.bin"
        test_file.write_bytes(b"binary data")
        client = HttpClient(BASE, auth_header={"Authorization": "Bearer tok"}, max_retries=1)
        responses.add(
            responses.POST,
            f"{BASE}/upload",
            status=429,
            headers={"Retry-After": "0"},
        )
        responses.add(
            responses.POST,
            f"{BASE}/upload",
            json={"ok": True},
            status=200,
        )
        resp = client.upload_multipart("/upload", str(test_file))
        assert resp.status_code == 200
        # 2回目のリクエストのボディが空でないことを検証
        assert b"binary data" in responses.calls[1].request.body

    @responses.activate
    def test_upload_file_absolute(self, tmp_path):
        """upload_file_absolute が絶対 URL にアップロードすることを検証する。"""
        test_file = tmp_path / "asset.zip"
        test_file.write_bytes(b"zip content")
        client = HttpClient(BASE, auth_header={"Authorization": "Bearer tok"})
        upload_url = "https://uploads.github.com/repos/o/r/releases/1/assets"
        responses.add(
            responses.POST,
            upload_url,
            json={"id": 1, "name": "asset.zip"},
            status=201,
        )
        resp = client.upload_file_absolute(upload_url, str(test_file), name="asset.zip")
        assert resp.status_code == 201
        assert responses.calls[0].request.body == b"zip content"

    def test_upload_file_absolute_forces_tls_for_cloud_url(self, tmp_path, monkeypatch):
        """self-hosted base (_VERIFY_SSL=False) でも cloud 宛 absolute upload は verify=True。"""
        from unittest.mock import MagicMock

        import gfo.http

        monkeypatch.setattr(gfo.http, "_VERIFY_SSL", False)
        test_file = tmp_path / "a.zip"
        test_file.write_bytes(b"x")
        client = HttpClient("https://internal.example.com")  # self-hosted base
        captured: dict = {}
        fake_resp = MagicMock()
        fake_resp.status_code = 201

        def fake_post(url, **kwargs):
            captured.update(kwargs)
            return fake_resp

        monkeypatch.setattr(client._session, "post", fake_post)
        client.upload_file_absolute(
            "https://uploads.github.com/repos/o/r/releases/1/assets",
            str(test_file),
            name="a.zip",
        )
        assert captured["verify"] is True

    def test_get_absolute_forces_tls_for_cloud_url(self, monkeypatch):
        """self-hosted base (_VERIFY_SSL=False) でも cloud 宛 absolute GET は verify=True。"""
        from unittest.mock import MagicMock

        import gfo.http

        monkeypatch.setattr(gfo.http, "_VERIFY_SSL", False)
        client = HttpClient("https://internal.example.com")  # self-hosted base
        captured: dict = {}
        fake_resp = MagicMock()
        fake_resp.status_code = 200

        def fake_get(url, **kwargs):
            captured.update(kwargs)
            return fake_resp

        monkeypatch.setattr(client._session, "get", fake_get)
        client.get_absolute("https://api.github.com/repos/o/r/releases")
        assert captured["verify"] is True

    @responses.activate
    def test_upload_multipart_name_override(self, tmp_path):
        """upload_multipart の name パラメータでファイル名をオーバーライドできることを検証する。"""
        test_file = tmp_path / "original.bin"
        test_file.write_bytes(b"data")
        client = HttpClient(BASE, auth_header={"Authorization": "Bearer tok"})
        responses.add(
            responses.POST,
            f"{BASE}/upload",
            json={"ok": True},
            status=200,
        )
        client.upload_multipart("/upload", str(test_file), name="renamed.bin")
        assert b"renamed.bin" in responses.calls[0].request.body


# ── Retry-After 境界値テスト ──


class TestRetryAfterEdgeCases:
    def test_retry_after_empty_string(self):
        """空文字列 → int 変換失敗 → HTTP-date パースも失敗 → デフォルト値にフォールバック。"""
        assert HttpClient._parse_retry_after("") == 60
        assert HttpClient._parse_retry_after("", default=30) == 30

    def test_retry_after_malformed_http_date(self):
        """不完全な日時形式 → デフォルト値にフォールバック。"""
        # 月名なし・不完全な日時
        assert HttpClient._parse_retry_after("Mon, 99") == 60
        # 完全に無効な日時文字列
        assert HttpClient._parse_retry_after("not-a-date-at-all") == 60
        # 部分的な HTTP-date (タイムゾーンなし等)
        assert HttpClient._parse_retry_after("2025-13-45T99:99:99") == 60

    def test_retry_after_large_seconds_clamped(self):
        """_MAX_RETRY_AFTER (300) を超える値はクランプされる。"""
        from gfo.http import _MAX_RETRY_AFTER

        assert HttpClient._parse_retry_after("999999") == _MAX_RETRY_AFTER
        assert HttpClient._parse_retry_after("301") == _MAX_RETRY_AFTER
        assert HttpClient._parse_retry_after("300") == 300
        assert HttpClient._parse_retry_after("299") == 299
