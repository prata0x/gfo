"""Gogs アダプター。GiteaAdapter を継承し、非対応操作を NotSupportedError でオーバーライドする。"""

from __future__ import annotations

import urllib.parse
from urllib.parse import quote

from gfo.exceptions import NotSupportedError

from .base import (
    BranchProtection,
    CheckRun,
    Comment,
    CommitStatus,
    CompareResult,
    GpgKey,
    Label,
    Milestone,
    Notification,
    Pipeline,
    PullRequest,
    PullRequestCommit,
    PullRequestFile,
    Release,
    ReleaseAsset,
    Repository,
    Review,
    Secret,
    Tag,
    TagProtection,
    Variable,
    Webhook,
    WikiPage,
)
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

    def reopen_pull_request(self, number: int) -> None:
        raise NotSupportedError(
            "Gogs", "pull request operations", web_url=self._pr_url(f"pulls/{number}")
        )

    def get_pr_checkout_refspec(self, number: int, *, pr: PullRequest | None = None) -> str:
        raise NotSupportedError(
            "Gogs", "pull request operations", web_url=self._pr_url(f"pulls/{number}")
        )

    def get_pull_request_diff(self, number: int) -> str:
        raise NotSupportedError(
            "Gogs", "pull request operations", web_url=self._pr_url(f"pulls/{number}")
        )

    def list_pull_request_checks(self, number: int) -> list[CheckRun]:
        raise NotSupportedError("Gogs", "pull request operations", web_url=self._pr_url())

    def list_pull_request_files(self, number: int) -> list[PullRequestFile]:
        raise NotSupportedError("Gogs", "pull request operations", web_url=self._pr_url())

    def list_pull_request_commits(self, number: int) -> list[PullRequestCommit]:
        raise NotSupportedError("Gogs", "pull request operations", web_url=self._pr_url())

    def list_requested_reviewers(self, number: int) -> list[str]:
        raise NotSupportedError("Gogs", "pull request operations", web_url=self._pr_url())

    def request_reviewers(self, number: int, reviewers: list[str]) -> None:
        raise NotSupportedError("Gogs", "pull request operations", web_url=self._pr_url())

    def remove_reviewers(self, number: int, reviewers: list[str]) -> None:
        raise NotSupportedError("Gogs", "pull request operations", web_url=self._pr_url())

    def update_pull_request_branch(self, number: int) -> None:
        raise NotSupportedError("Gogs", "pull request operations", web_url=self._pr_url())

    def enable_auto_merge(self, number: int, *, merge_method: str | None = None) -> None:
        raise NotSupportedError("Gogs", "pull request operations", web_url=self._pr_url())

    def dismiss_review(self, number: int, review_id: int, *, message: str = "") -> None:
        raise NotSupportedError("Gogs", "pull request operations", web_url=self._pr_url())

    def mark_pull_request_ready(self, number: int) -> None:
        raise NotSupportedError("Gogs", "pull request operations", web_url=self._pr_url())

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

    def update_label(
        self,
        *,
        name: str,
        new_name: str | None = None,
        color: str | None = None,
        description: str | None = None,
    ) -> Label:
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

    def get_milestone(self, number: int) -> Milestone:
        raise NotSupportedError("Gogs", "milestone operations")

    def update_milestone(
        self,
        number: int,
        *,
        title: str | None = None,
        description: str | None = None,
        due_date: str | None = None,
        state: str | None = None,
    ) -> Milestone:
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

    def get_release(self, *, tag: str) -> Release:
        raise NotSupportedError("Gogs", "release operations")

    def update_release(
        self,
        *,
        tag: str,
        title: str | None = None,
        notes: str | None = None,
        draft: bool | None = None,
        prerelease: bool | None = None,
    ) -> Release:
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

    # --- Tag（Gogs 0.13: create/delete 未対応）---

    def create_tag(self, *, name: str, ref: str, message: str = "") -> Tag:
        raise NotSupportedError("Gogs", "tag creation")

    def delete_tag(self, *, name: str) -> None:
        raise NotSupportedError("Gogs", "tag deletion")

    # --- Branch（Gogs 0.13: POST/DELETE 未対応）---

    def create_branch(self, *, name: str, ref: str):
        raise NotSupportedError("Gogs", "branch creation")

    def delete_branch(self, *, name: str) -> None:
        raise NotSupportedError("Gogs", "branch deletion")

    # --- CommitStatus（Gogs 0.13 未対応）---

    def create_commit_status(
        self,
        ref: str,
        *,
        state: str,
        context: str = "",
        description: str = "",
        target_url: str = "",
    ) -> CommitStatus:
        raise NotSupportedError("Gogs", "commit status")

    def list_commit_statuses(self, ref: str, *, limit: int = 30) -> list[CommitStatus]:
        raise NotSupportedError("Gogs", "commit status")

    # --- File CRUD（Gogs 0.13: POST/DELETE 未対応）---

    def create_or_update_file(
        self,
        path: str,
        *,
        content: str,
        message: str,
        sha: str | None = None,
        branch: str | None = None,
    ) -> None:
        raise NotSupportedError("Gogs", "file write operations")

    def delete_file(
        self,
        path: str,
        *,
        sha: str,
        message: str,
        branch: str | None = None,
    ) -> None:
        raise NotSupportedError("Gogs", "file write operations")

    # --- Webhook（type: "gogs" を使用）---

    def create_webhook(
        self,
        *,
        url: str,
        events: list[str] | None = None,
        secret: str | None = None,
    ) -> Webhook:
        config: dict = {"url": url, "content_type": "json"}
        if secret is not None:
            config["secret"] = secret
        payload: dict = {
            "config": config,
            "events": events or ["push"],
            "active": True,
            "type": "gogs",
        }
        resp = self._client.post(f"{self._repos_path()}/hooks", json=payload)
        return self._to_webhook(resp.json())

    # --- Secret / Variable（Gogs 0.13 未対応）---

    def list_secrets(self, *, limit: int = 30) -> list[Secret]:
        raise NotSupportedError("Gogs", "secret operations")

    def set_secret(self, name: str, value: str) -> Secret:
        raise NotSupportedError("Gogs", "secret operations")

    def delete_secret(self, name: str) -> None:
        raise NotSupportedError("Gogs", "secret operations")

    def list_variables(self, *, limit: int = 30) -> list[Variable]:
        raise NotSupportedError("Gogs", "variable operations")

    def set_variable(self, name: str, value: str, *, masked: bool = False) -> Variable:
        raise NotSupportedError("Gogs", "variable operations")

    def get_variable(self, name: str) -> Variable:
        raise NotSupportedError("Gogs", "variable operations")

    def delete_variable(self, name: str) -> None:
        raise NotSupportedError("Gogs", "variable operations")

    # --- GPG Key（Gogs 0.13 未対応）---

    def list_gpg_keys(self, *, limit: int = 30) -> list[GpgKey]:
        raise NotSupportedError("Gogs", "gpg-key operations")

    def create_gpg_key(self, *, armored_key: str) -> GpgKey:
        raise NotSupportedError("Gogs", "gpg-key operations")

    def delete_gpg_key(self, *, key_id: int | str) -> None:
        raise NotSupportedError("Gogs", "gpg-key operations")

    # --- TagProtection（Gogs 0.13 未対応）---

    def list_tag_protections(self, *, limit: int = 30) -> list[TagProtection]:
        raise NotSupportedError("Gogs", "tag-protect operations")

    def create_tag_protection(
        self, pattern: str, *, create_access_level: str | None = None
    ) -> TagProtection:
        raise NotSupportedError("Gogs", "tag-protect operations")

    def delete_tag_protection(self, protection_id: int | str) -> None:
        raise NotSupportedError("Gogs", "tag-protect operations")

    # --- BranchProtection（Gogs 0.13 未対応）---

    def list_branch_protections(self, *, limit: int = 30) -> list[BranchProtection]:
        raise NotSupportedError("Gogs", "branch-protect operations")

    def get_branch_protection(self, branch: str) -> BranchProtection:
        raise NotSupportedError("Gogs", "branch-protect operations")

    def set_branch_protection(
        self,
        branch: str,
        *,
        require_reviews: int | None = None,
        require_status_checks: list[str] | None = None,
        enforce_admins: bool | None = None,
        allow_force_push: bool | None = None,
        allow_deletions: bool | None = None,
    ) -> BranchProtection:
        raise NotSupportedError("Gogs", "branch-protect operations")

    def remove_branch_protection(self, branch: str) -> None:
        raise NotSupportedError("Gogs", "branch-protect operations")

    # --- Notification（Gogs 0.13 未対応）---

    def list_notifications(
        self, *, unread_only: bool = False, limit: int = 30
    ) -> list[Notification]:
        raise NotSupportedError("Gogs", "notification operations")

    def mark_notification_read(self, notification_id: str) -> None:
        raise NotSupportedError("Gogs", "notification operations")

    def mark_all_notifications_read(self) -> None:
        raise NotSupportedError("Gogs", "notification operations")

    # --- Wiki（Gogs 0.13 未対応）---

    def list_wiki_pages(self, *, limit: int = 30) -> list[WikiPage]:
        raise NotSupportedError("Gogs", "wiki operations")

    def get_wiki_page(self, page_id: int | str) -> WikiPage:
        raise NotSupportedError("Gogs", "wiki operations")

    def create_wiki_page(self, *, title: str, content: str) -> WikiPage:
        raise NotSupportedError("Gogs", "wiki operations")

    def update_wiki_page(
        self,
        page_id: int | str,
        *,
        title: str | None = None,
        content: str | None = None,
    ) -> WikiPage:
        raise NotSupportedError("Gogs", "wiki operations")

    def delete_wiki_page(self, page_id: int | str) -> None:
        raise NotSupportedError("Gogs", "wiki operations")

    # --- Repo update/archive/languages/topics/compare（Gogs 0.13 未対応）---

    def update_repository(
        self, *, description=None, private=None, default_branch=None
    ) -> Repository:
        raise NotSupportedError("Gogs", "repo update")

    def archive_repository(self) -> None:
        raise NotSupportedError("Gogs", "repo archive")

    def get_languages(self) -> dict[str, int | float]:
        raise NotSupportedError("Gogs", "repo languages")

    def list_topics(self) -> list[str]:
        raise NotSupportedError("Gogs", "repo topics")

    def set_topics(self, topics: list[str]) -> list[str]:
        raise NotSupportedError("Gogs", "repo topics")

    def add_topic(self, topic: str) -> list[str]:
        raise NotSupportedError("Gogs", "repo topics")

    def remove_topic(self, topic: str) -> list[str]:
        raise NotSupportedError("Gogs", "repo topics")

    def compare(self, base: str, head: str) -> CompareResult:
        raise NotSupportedError("Gogs", "repo compare")

    def migrate_repository(
        self,
        clone_url: str,
        name: str,
        *,
        private: bool = False,
        description: str = "",
        mirror: bool = False,
        auth_token: str | None = None,
    ) -> Repository:
        raise NotSupportedError("Gogs", "repo migrate")

    # --- Release assets（Gogs 0.13: Release 非対応のため）---

    def get_latest_release(self) -> Release:
        raise NotSupportedError("Gogs", "release operations")

    def list_release_assets(self, *, tag: str) -> list[ReleaseAsset]:
        raise NotSupportedError("Gogs", "release operations")

    def upload_release_asset(
        self, *, tag: str, file_path: str, name: str | None = None
    ) -> ReleaseAsset:
        raise NotSupportedError("Gogs", "release operations")

    def download_release_asset(self, *, tag: str, asset_id: int | str, output_dir: str) -> str:
        raise NotSupportedError("Gogs", "release operations")

    def delete_release_asset(self, *, tag: str, asset_id: int | str) -> None:
        raise NotSupportedError("Gogs", "release operations")
