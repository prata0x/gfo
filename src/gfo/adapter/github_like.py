"""GitHub API 互換サービス（GitHub/Gitea 系）向け共通変換 Mixin。

`GitHubAdapter`・`GiteaAdapter`・`GitBucketAdapter`・`ForgejoAdapter` が共有する
`_to_*` 静的メソッドを集約する。API レスポンスのフィールド名が GitHub/Gitea で
一致しているため、コードを共通化できる。
"""

from __future__ import annotations

from abc import ABC

from gfo.adapter._helpers import _wrap_conversion_error
from gfo.adapter.models import (
    Branch,
    CheckRun,
    Comment,
    CommitStatus,
    DeployKey,
    Issue,
    Label,
    Milestone,
    PullRequest,
    PullRequestCommit,
    PullRequestFile,
    Release,
    ReleaseAsset,
    Repository,
    Review,
    Tag,
    Webhook,
)


class GitHubLikeAdapter(ABC):  # noqa: B024 - 抽象メソッドを持たない変換ヘルパー Mixin (ABC は直接インスタンス化防止のため)
    """GitHub API 互換サービス（GitHub/Gitea 系）向け共通変換ヘルパー。

    GitHubAdapter・GiteaAdapter・GitBucketAdapter・ForgejoAdapter が共有する
    6 つの `_to_*` 静的メソッドをここに集約する。API レスポンスのフィールド名が
    GitHub / Gitea で一致しているためコードが共通化できる。
    """

    @staticmethod
    @_wrap_conversion_error
    def _to_pull_request(data: dict) -> PullRequest:
        merged = data.get("merged_at") is not None
        if data["state"] == "closed" and merged:
            state = "merged"
        else:
            state = data["state"]

        return PullRequest(
            number=data["number"],
            title=data["title"],
            body=data.get("body"),
            state=state,
            author=data["user"]["login"],
            source_branch=data["head"]["ref"],
            target_branch=data["base"]["ref"],
            draft=data.get("draft", False),
            url=data["html_url"],
            created_at=data["created_at"],
            updated_at=data.get("updated_at"),
        )

    @staticmethod
    @_wrap_conversion_error
    def _to_issue(data: dict) -> Issue:
        return Issue(
            number=data["number"],
            title=data["title"],
            body=data.get("body"),
            state=data["state"],
            author=data["user"]["login"],
            assignees=[a["login"] for a in (data.get("assignees") or [])],
            labels=[lb["name"] for lb in (data.get("labels") or [])],
            url=data.get("html_url") or "",
            created_at=data["created_at"],
            updated_at=data.get("updated_at"),
        )

    @staticmethod
    @_wrap_conversion_error
    def _to_repository(data: dict) -> Repository:
        return Repository(
            name=data["name"],
            full_name=data["full_name"],
            description=data.get("description"),
            visibility=data.get("visibility") or ("private" if data.get("private") else "public"),
            default_branch=data.get("default_branch"),
            clone_url=data["clone_url"],
            url=data["html_url"],
        )

    @staticmethod
    @_wrap_conversion_error
    def _to_release(data: dict) -> Release:
        return Release(
            tag=data["tag_name"],
            title=data.get("name") or "",
            body=data.get("body"),
            draft=data.get("draft", False),
            prerelease=data.get("prerelease", False),
            url=data.get("html_url") or "",
            created_at=data["created_at"],
        )

    @staticmethod
    @_wrap_conversion_error
    def _to_label(data: dict) -> Label:
        return Label(
            name=data["name"],
            color=data.get("color"),
            description=data.get("description"),
        )

    @staticmethod
    @_wrap_conversion_error
    def _to_milestone(data: dict) -> Milestone:
        return Milestone(
            number=data.get("number") or data["id"],
            title=data["title"],
            description=data.get("description"),
            state=data["state"],
            due_date=data.get("due_on"),
        )

    @staticmethod
    @_wrap_conversion_error
    def _to_comment(data: dict) -> Comment:
        return Comment(
            id=data["id"],
            body=data.get("body") or "",
            author=data["user"]["login"],
            url=data.get("html_url") or "",
            created_at=data["created_at"],
            updated_at=data.get("updated_at"),
        )

    @staticmethod
    @_wrap_conversion_error
    def _to_review(data: dict) -> Review:
        state_map = {
            "APPROVED": "approved",
            "CHANGES_REQUESTED": "changes_requested",
            "COMMENTED": "commented",
            "PENDING": "pending",
            "DISMISSED": "dismissed",
        }
        raw_state = data.get("state", "commented")
        state = state_map.get(raw_state.upper(), raw_state.lower())
        return Review(
            id=data["id"],
            state=state,
            body=data.get("body") or "",
            author=data["user"]["login"],
            url=data.get("html_url") or "",
            submitted_at=data.get("submitted_at"),
        )

    @staticmethod
    @_wrap_conversion_error
    def _to_branch(data: dict) -> Branch:
        commit = data.get("commit") or {}
        sha = commit.get("sha") or commit.get("id") or ""
        return Branch(
            name=data["name"],
            sha=sha,
            protected=data.get("protected", False),
            url=data.get("_links", {}).get("html") or "",
        )

    @staticmethod
    @_wrap_conversion_error
    def _to_tag(data: dict) -> Tag:
        commit = data.get("commit") or {}
        sha = commit.get("sha") or ""
        return Tag(
            name=data["name"],
            sha=sha,
            message="",
            url=data.get("zipball_url") or "",
        )

    @staticmethod
    @_wrap_conversion_error
    def _to_commit_status(data: dict) -> CommitStatus:
        # GitHub は "state"、Gitea は "status" を使用する
        state = data.get("state") or data.get("status") or ""
        return CommitStatus(
            state=state,
            context=data.get("context") or "",
            description=data.get("description") or "",
            target_url=data.get("target_url") or "",
            created_at=data.get("created_at") or "",
        )

    @staticmethod
    @_wrap_conversion_error
    def _to_webhook(data: dict) -> Webhook:
        config = data.get("config") or {}
        url = config.get("url") or data.get("url") or ""
        events = tuple(data.get("events") or [])
        return Webhook(
            id=data["id"],
            url=url,
            events=events,
            active=data.get("active", True),
        )

    @staticmethod
    @_wrap_conversion_error
    def _to_deploy_key(data: dict) -> DeployKey:
        return DeployKey(
            id=data["id"],
            title=data.get("title") or "",
            key=data.get("key") or "",
            read_only=data.get("read_only", True),
        )

    @staticmethod
    @_wrap_conversion_error
    def _to_check_run(data: dict) -> CheckRun:
        status_map = {
            "success": "success",
            "failure": "failure",
            "pending": "pending",
            "error": "failure",
        }
        state = data.get("state") or data.get("status") or ""
        return CheckRun(
            name=data.get("context") or data.get("name") or "",
            status=status_map.get(state, state),
            conclusion="",
            url=data.get("target_url") or data.get("url") or "",
            started_at=data.get("created_at") or "",
        )

    @staticmethod
    @_wrap_conversion_error
    def _to_release_asset(data: dict) -> ReleaseAsset:
        return ReleaseAsset(
            id=data["id"],
            name=data["name"],
            size=data.get("size") or 0,
            download_url=data.get("browser_download_url") or "",
            created_at=data.get("created_at") or "",
        )

    @staticmethod
    @_wrap_conversion_error
    def _to_pull_request_file(data: dict) -> PullRequestFile:
        return PullRequestFile(
            filename=data.get("filename") or "",
            status=data.get("status") or "modified",
            additions=data.get("additions") or 0,
            deletions=data.get("deletions") or 0,
        )

    @staticmethod
    @_wrap_conversion_error
    def _to_pull_request_commit(data: dict) -> PullRequestCommit:
        commit = data.get("commit") or {}
        author_info = commit.get("author") or {}
        user = data.get("author") or {}
        author = user.get("login") or author_info.get("name") or ""
        return PullRequestCommit(
            sha=data.get("sha") or "",
            message=commit.get("message") or "",
            author=author,
            created_at=author_info.get("date") or "",
        )
