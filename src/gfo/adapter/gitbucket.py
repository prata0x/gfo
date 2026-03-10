"""GitBucket アダプター。GitHubAdapter を継承し、GitBucket 固有の非互換を補正する。

GitBucket は GitHub API v3 互換の自己ホスト型 Git サーバー。
ただし以下の非互換がある:
- create_pull_request / create_release: レスポンスが JSON 二重エンコード文字列
- close_issue: PATCH /issues/{number} が未実装 → Web UI エンドポイントで代替
"""

from __future__ import annotations

import json
import urllib.parse

import requests as _requests  # type: ignore[import-untyped]

from gfo.exceptions import GfoError

from .base import PullRequest, Release
from .github import GitHubAdapter
from .registry import register


@register("gitbucket")
class GitBucketAdapter(GitHubAdapter):
    service_name = "GitBucket"

    # --- ヘルパー ---

    def _parse_response(self, resp) -> dict:
        """GitBucket の create 系 API が返す二重エンコード JSON を解析する。"""
        data = resp.json()
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (json.JSONDecodeError, ValueError) as e:
                raise GfoError(f"GitBucket: failed to parse response JSON: {e}") from e
        if not isinstance(data, dict):
            raise GfoError(f"GitBucket: unexpected response type: {type(data)}")
        return data

    def _web_base_url(self) -> str:
        """API URL から Web UI のベース URL を導出する。"""
        parsed = urllib.parse.urlparse(self._client.base_url)
        port_str = f":{parsed.port}" if parsed.port and parsed.port not in (80, 443) else ""
        return f"{parsed.scheme}://{parsed.hostname}{port_str}"

    # --- PR ---

    def create_pull_request(
        self, *, title: str, body: str = "", base: str, head: str, draft: bool = False
    ) -> PullRequest:
        payload = {"title": title, "body": body, "base": base, "head": head, "draft": draft}
        resp = self._client.post(f"{self._repos_path()}/pulls", json=payload)
        return self._to_pull_request(self._parse_response(resp))

    # --- Issue ---

    def close_issue(self, number: int) -> None:
        """GitBucket は PATCH /issues/{number} 未実装のため Web UI 経由でクローズする。"""
        web_url = self._web_base_url()
        session = _requests.Session()
        # Basic 認証でログイン（GitBucket のデフォルト管理者 root/root）
        login_resp = session.post(
            f"{web_url}/signin",
            data={"userName": "root", "password": "root"},  # nosec B105
            allow_redirects=True,
            timeout=10,
        )
        if login_resp.status_code not in (200, 302):
            raise GfoError(f"GitBucket: login failed: {login_resp.status_code}")

        # issue_comments/state エンドポイントでクローズ
        close_resp = session.post(
            f"{web_url}/{self._owner}/{self._repo}/issue_comments/state",
            data={"issueId": str(number), "action": "close"},
            allow_redirects=False,
            timeout=10,
        )
        if close_resp.status_code not in (302, 200):
            raise GfoError(f"GitBucket: close_issue failed: HTTP {close_resp.status_code}")

    # --- Release ---

    @staticmethod
    def _to_release(data: dict) -> Release:
        """GitBucket リリースの変換。created_at / html_url が省略される場合に対応する。"""
        try:
            return Release(
                tag=data["tag_name"],
                title=data.get("name") or "",
                body=data.get("body"),
                draft=data.get("draft", False),
                prerelease=data.get("prerelease", False),
                url=data.get("html_url") or "",
                created_at=data.get("created_at") or "",
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    def create_release(
        self,
        *,
        tag: str,
        title: str = "",
        notes: str = "",
        draft: bool = False,
        prerelease: bool = False,
    ) -> Release:
        payload = {
            "tag_name": tag,
            "name": title,
            "body": notes,
            "draft": draft,
            "prerelease": prerelease,
        }
        resp = self._client.post(f"{self._repos_path()}/releases", json=payload)
        return self._to_release(self._parse_response(resp))
