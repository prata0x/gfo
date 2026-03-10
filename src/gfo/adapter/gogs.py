"""Gogs アダプター。GiteaAdapter を継承し、非対応操作を NotSupportedError でオーバーライドする。"""

from __future__ import annotations

import urllib.parse
from urllib.parse import quote

from gfo.exceptions import NotSupportedError

from .base import Comment, Label, Milestone, Pipeline, PullRequest, Release, Review
from .gitea import GiteaAdapter
from .registry import register


@register("gogs")
class GogsAdapter(GiteaAdapter):
    """Gitea を継承。PR / Label / Milestone 操作を NotSupportedError でオーバーライド。"""

    service_name = "Gogs"

    def _web_url(self) -> str:
        """Web UI のベース URL を構築する。"""
        parsed = urllib.parse.urlparse(self._client.base_url)
        port = f":{parsed.port}" if parsed.port is not None else ""
        return f"{parsed.scheme}://{parsed.hostname}{port}"

    def _pr_url(self, suffix: str = "pulls") -> str:
        owner = quote(self._owner, safe="")
        repo = quote(self._repo, safe="")
        return f"{self._web_url()}/{owner}/{repo}/{suffix}"

    # --- PR（非サポート）---

    def list_pull_requests(self, *, state: str = "open", limit: int = 30) -> list[PullRequest]:
        raise NotSupportedError("Gogs", "pull request operations", web_url=self._pr_url())

    def create_pull_request(
        self, *, title: str, body: str = "", base: str, head: str, draft: bool = False
    ) -> PullRequest:
        raise NotSupportedError("Gogs", "pull request operations", web_url=self._pr_url("compare"))

    def get_pull_request(self, number: int) -> PullRequest:
        raise NotSupportedError(
            "Gogs", "pull request operations", web_url=self._pr_url(f"pulls/{number}")
        )

    def merge_pull_request(self, number: int, *, method: str = "merge") -> None:
        raise NotSupportedError(
            "Gogs", "pull request operations", web_url=self._pr_url(f"pulls/{number}")
        )

    def close_pull_request(self, number: int) -> None:
        raise NotSupportedError(
            "Gogs", "pull request operations", web_url=self._pr_url(f"pulls/{number}")
        )

    def get_pr_checkout_refspec(self, number: int, *, pr: PullRequest | None = None) -> str:
        raise NotSupportedError(
            "Gogs", "pull request operations", web_url=self._pr_url(f"pulls/{number}")
        )

    # --- Issue ---

    def delete_issue(self, number: int) -> None:
        raise NotSupportedError("Gogs", "issue delete")

    # --- Label（非サポート）---

    def list_labels(self, *, limit: int = 0) -> list[Label]:
        raise NotSupportedError("Gogs", "label operations")

    def create_label(
        self, *, name: str, color: str | None = None, description: str | None = None
    ) -> Label:
        raise NotSupportedError("Gogs", "label operations")

    def delete_label(self, *, name: str) -> None:
        raise NotSupportedError("Gogs", "label operations")

    # --- Milestone（非サポート）---

    def list_milestones(self, *, limit: int = 0) -> list[Milestone]:
        raise NotSupportedError("Gogs", "milestone operations")

    def create_milestone(
        self, *, title: str, description: str | None = None, due_date: str | None = None
    ) -> Milestone:
        raise NotSupportedError("Gogs", "milestone operations")

    def delete_milestone(self, *, number: int) -> None:
        raise NotSupportedError("Gogs", "milestone operations")

    # --- Release（非サポート）---

    def list_releases(self, *, limit: int = 30) -> list[Release]:
        raise NotSupportedError("Gogs", "release operations")

    def create_release(
        self,
        *,
        tag: str,
        title: str = "",
        notes: str = "",
        draft: bool = False,
        prerelease: bool = False,
    ) -> Release:
        raise NotSupportedError("Gogs", "release operations")

    def delete_release(self, *, tag: str) -> None:
        raise NotSupportedError("Gogs", "release operations")

    # --- PR update（PR 非対応）---

    def update_pull_request(
        self,
        number: int,
        *,
        title: str | None = None,
        body: str | None = None,
        base: str | None = None,
    ) -> PullRequest:
        raise NotSupportedError("Gogs", "pull request operations", web_url=self._pr_url())

    # --- Comment（更新・削除は非対応）---

    def update_comment(self, resource: str, comment_id: int, *, body: str) -> Comment:
        raise NotSupportedError("Gogs", "comment update")

    def delete_comment(self, resource: str, comment_id: int) -> None:
        raise NotSupportedError("Gogs", "comment delete")

    # --- Review（PR 非対応のため）---

    def list_reviews(self, number: int) -> list[Review]:
        raise NotSupportedError("Gogs", "pull request operations", web_url=self._pr_url())

    def create_review(self, number: int, *, state: str, body: str = "") -> Review:
        raise NotSupportedError("Gogs", "pull request operations", web_url=self._pr_url())

    # --- Pipeline（CI なし）---

    def list_pipelines(self, *, ref: str | None = None, limit: int = 30) -> list[Pipeline]:
        raise NotSupportedError("Gogs", "ci operations")

    def get_pipeline(self, pipeline_id: int | str) -> Pipeline:
        raise NotSupportedError("Gogs", "ci operations")

    def cancel_pipeline(self, pipeline_id: int | str) -> None:
        raise NotSupportedError("Gogs", "ci operations")
