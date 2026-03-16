"""GitBucket アダプター。GitHubAdapter を継承し、GitBucket 固有の非互換を補正する。

GitBucket は GitHub API v3 互換の自己ホスト型 Git サーバー。
ただし以下の非互換がある:
- create_pull_request / create_release: レスポンスが JSON 二重エンコード文字列
- close_issue: PATCH /issues/{number} が未実装のため非対応
"""

from __future__ import annotations

import json
import urllib.parse

from gfo.exceptions import GfoError, NotSupportedError
from gfo.http import paginate_link_header

from .base import (
    BranchProtection,
    DeployKey,
    Issue,
    Notification,
    Organization,
    PullRequest,
    Release,
    Repository,
    Review,
    SshKey,
    Tag,
    WikiPage,
)
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
        """GitBucket は PATCH /issues/{number} 未実装のため非対応。"""
        raise NotSupportedError("GitBucket", "issue close")

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

    def delete_repository(self) -> None:
        """GitBucket は DELETE /repos API 未実装のため非対応。"""
        raise NotSupportedError("GitBucket", "repo delete")

    # --- Tag（/tags エンドポイントが二重エンコード JSON を返すため /git/refs/tags を使用）---

    def list_tags(self, *, limit: int = 30) -> list[Tag]:
        """GitBucket の GET /tags は二重エンコード JSON を返すため GET /git/refs/tags を使用。"""
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/git/refs/tags",
            limit=limit,
        )
        tags = []
        for item in results:
            ref = item.get("ref", "")
            name = ref[len("refs/tags/") :] if ref.startswith("refs/tags/") else ref
            sha = (item.get("object") or {}).get("sha") or ""
            tags.append(Tag(name=name, sha=sha, message="", url=""))
        return tags

    def create_tag(self, *, name: str, ref: str, message: str = "") -> Tag:
        """GitBucket は POST /git/refs 未実装のため非対応。"""
        raise NotSupportedError("GitBucket", "tag creation via API (use git push)")

    def delete_release(self, *, tag: str) -> None:
        """GitBucket はリリースをタグ名で直接削除する（数値 ID を返さないため）。"""
        self._client.delete(f"{self._repos_path()}/releases/{urllib.parse.quote(tag, safe='')}")

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

    # --- Browse ---

    def get_web_url(self, resource: str = "repo", number: int | None = None) -> str:
        base = f"{self._web_base_url()}/{self._owner}/{self._repo}"
        if resource == "pr":
            return f"{base}/pulls/{number}"
        if resource == "issue":
            return f"{base}/issues/{number}"
        if resource == "settings":
            return f"{base}/settings"
        return base

    # --- Issue update（PATCH /issues/{number} 未実装）---

    def update_issue(
        self,
        number: int,
        *,
        title: str | None = None,
        body: str | None = None,
        state: str | None = None,
        assignee: str | None = None,
        label: str | None = None,
    ) -> Issue:
        raise NotSupportedError("GitBucket", "issue update")

    # --- Search（検索 API 未実装）---

    def search_repositories(self, query: str, *, limit: int = 30) -> list[Repository]:
        raise NotSupportedError("GitBucket", "search operations")

    def search_issues(self, query: str, *, limit: int = 30) -> list[Issue]:
        raise NotSupportedError("GitBucket", "search operations")

    # --- Wiki（GitBucket 未実装）---

    def list_wiki_pages(self, *, limit: int = 30) -> list[WikiPage]:
        raise NotSupportedError("GitBucket", "wiki operations")

    def get_wiki_page(self, page_id: int | str) -> WikiPage:
        raise NotSupportedError("GitBucket", "wiki operations")

    def create_wiki_page(self, *, title: str, content: str) -> WikiPage:
        raise NotSupportedError("GitBucket", "wiki operations")

    def update_wiki_page(
        self,
        page_id: int | str,
        *,
        title: str | None = None,
        content: str | None = None,
    ) -> WikiPage:
        raise NotSupportedError("GitBucket", "wiki operations")

    def delete_wiki_page(self, page_id: int | str) -> None:
        raise NotSupportedError("GitBucket", "wiki operations")

    # --- Review（Reviews API なし）---

    def list_reviews(self, number: int) -> list[Review]:
        raise NotSupportedError("GitBucket", "review operations")

    def create_review(self, number: int, *, state: str, body: str = "") -> Review:
        raise NotSupportedError("GitBucket", "review operations")

    # --- BranchProtection（GitBucket 未実装）---

    def list_branch_protections(self, *, limit: int = 30) -> list[BranchProtection]:
        raise NotSupportedError("GitBucket", "branch-protect operations")

    def get_branch_protection(self, branch: str) -> BranchProtection:
        raise NotSupportedError("GitBucket", "branch-protect operations")

    def set_branch_protection(self, branch: str, **kwargs) -> BranchProtection:
        raise NotSupportedError("GitBucket", "branch-protect operations")

    def remove_branch_protection(self, branch: str) -> None:
        raise NotSupportedError("GitBucket", "branch-protect operations")

    # --- Notification（GitBucket 未実装）---

    def list_notifications(
        self, *, unread_only: bool = False, limit: int = 30
    ) -> list[Notification]:
        raise NotSupportedError("GitBucket", "notification operations")

    def mark_notification_read(self, notification_id: str) -> None:
        raise NotSupportedError("GitBucket", "notification operations")

    def mark_all_notifications_read(self) -> None:
        raise NotSupportedError("GitBucket", "notification operations")

    # --- Organization（GitBucket 未実装）---

    def list_organizations(self, *, limit: int = 30) -> list[Organization]:
        raise NotSupportedError("GitBucket", "org operations")

    def get_organization(self, name: str) -> Organization:
        raise NotSupportedError("GitBucket", "org operations")

    def list_org_members(self, name: str, *, limit: int = 30) -> list[str]:
        raise NotSupportedError("GitBucket", "org operations")

    def list_org_repos(self, name: str, *, limit: int = 30) -> list[Repository]:
        raise NotSupportedError("GitBucket", "org operations")

    # --- SSH Key（GitBucket 未実装）---

    def list_ssh_keys(self, *, limit: int = 30) -> list[SshKey]:
        raise NotSupportedError("GitBucket", "ssh-key operations")

    def create_ssh_key(self, *, title: str, key: str) -> SshKey:
        raise NotSupportedError("GitBucket", "ssh-key operations")

    def delete_ssh_key(self, *, key_id: int | str) -> None:
        raise NotSupportedError("GitBucket", "ssh-key operations")

    # --- Deploy key（GitBucket 未実装）---

    def list_deploy_keys(self, *, limit: int = 30) -> list[DeployKey]:
        raise NotSupportedError("GitBucket", "deploy key operations")

    def create_deploy_key(self, *, title: str, key: str, read_only: bool = True) -> DeployKey:
        raise NotSupportedError("GitBucket", "deploy key operations")

    def delete_deploy_key(self, *, key_id: int) -> None:
        raise NotSupportedError("GitBucket", "deploy key operations")
