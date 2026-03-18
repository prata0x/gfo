from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from gfo.exceptions import GfoError, NotSupportedError


@dataclass(frozen=True, slots=True)
class PullRequest:
    number: int
    title: str
    body: str | None
    state: str  # "open" | "closed" | "merged"
    author: str
    source_branch: str
    target_branch: str
    draft: bool
    url: str
    created_at: str  # ISO 8601
    updated_at: str | None = None


@dataclass(frozen=True, slots=True)
class Issue:
    number: int
    title: str
    body: str | None
    state: str  # "open" | "closed"
    author: str
    assignees: list[str]
    labels: list[str]
    url: str
    created_at: str
    updated_at: str | None = None


@dataclass(frozen=True, slots=True)
class IssueTemplate:
    name: str
    title: str
    body: str
    about: str
    labels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Repository:
    name: str
    full_name: str  # "owner/repo"
    description: str | None
    private: bool
    default_branch: str | None
    clone_url: str
    url: str


@dataclass(frozen=True, slots=True)
class Release:
    tag: str
    title: str
    body: str | None
    draft: bool
    prerelease: bool
    url: str
    created_at: str


@dataclass(frozen=True, slots=True)
class Label:
    name: str
    color: str | None
    description: str | None


@dataclass(frozen=True, slots=True)
class Milestone:
    number: int
    title: str
    description: str | None
    state: str  # "open" | "closed"
    due_date: str | None


@dataclass(frozen=True, slots=True)
class Comment:
    id: int
    body: str
    author: str
    url: str
    created_at: str
    updated_at: str | None = None


@dataclass(frozen=True, slots=True)
class Review:
    id: int
    state: str  # "approved" | "changes_requested" | "commented"
    body: str
    author: str
    url: str
    submitted_at: str | None = None


@dataclass(frozen=True, slots=True)
class Branch:
    name: str
    sha: str
    protected: bool
    url: str


@dataclass(frozen=True, slots=True)
class Tag:
    name: str
    sha: str
    message: str
    url: str


@dataclass(frozen=True, slots=True)
class CommitStatus:
    state: str  # "success" | "failure" | "pending" | "error"
    context: str
    description: str
    target_url: str
    created_at: str


@dataclass(frozen=True, slots=True)
class Webhook:
    id: int
    url: str
    events: tuple[str, ...]
    active: bool


@dataclass(frozen=True, slots=True)
class DeployKey:
    id: int
    title: str
    key: str
    read_only: bool


@dataclass(frozen=True, slots=True)
class WikiPage:
    id: int | str  # 数値 ID または sub_url 文字列（Gitea 系）
    title: str
    content: str
    url: str
    updated_at: str | None = None


@dataclass(frozen=True, slots=True)
class Pipeline:
    id: int | str
    status: str  # "success" | "failure" | "running" | "pending" | "cancelled"
    ref: str
    url: str
    created_at: str


@dataclass(frozen=True, slots=True)
class SshKey:
    id: int | str  # GitHub/GitLab/Gitea 系は int、Bitbucket は UUID 文字列
    title: str
    key: str
    created_at: str


@dataclass(frozen=True, slots=True)
class GpgKey:
    id: int | str
    primary_key_id: str
    public_key: str
    emails: tuple[str, ...]
    created_at: str


@dataclass(frozen=True, slots=True)
class Organization:
    name: str  # ログイン名 / グループパス / ワークスペーススラッグ
    display_name: str  # 表示名（フルネーム）
    description: str | None
    url: str


@dataclass(frozen=True, slots=True)
class Notification:
    id: str
    title: str
    reason: str
    unread: bool
    repository: str
    url: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class BranchProtection:
    branch: str
    require_reviews: int  # 0 = 無効
    require_status_checks: tuple[str, ...]
    enforce_admins: bool
    allow_force_push: bool
    allow_deletions: bool


@dataclass(frozen=True, slots=True)
class TagProtection:
    id: int | str
    pattern: str
    create_access_level: str


@dataclass(frozen=True, slots=True)
class Secret:
    name: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class Variable:
    name: str
    value: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class CheckRun:
    name: str
    status: str  # "success" | "failure" | "pending" | "running"
    conclusion: str  # 詳細。不明なら ""
    url: str
    started_at: str


@dataclass(frozen=True, slots=True)
class PullRequestFile:
    filename: str
    status: str  # "added" | "modified" | "deleted" | "renamed"
    additions: int
    deletions: int


@dataclass(frozen=True, slots=True)
class PullRequestCommit:
    sha: str
    message: str
    author: str
    created_at: str


@dataclass(frozen=True, slots=True)
class CompareFile:
    filename: str
    status: str  # "added" | "modified" | "deleted" | "renamed"
    additions: int
    deletions: int


@dataclass(frozen=True, slots=True)
class CompareResult:
    total_commits: int
    ahead_by: int
    behind_by: int
    files: tuple[CompareFile, ...]


@dataclass(frozen=True, slots=True)
class ReleaseAsset:
    id: int | str
    name: str
    size: int
    download_url: str
    created_at: str


@dataclass(frozen=True, slots=True)
class Reaction:
    id: int | str
    content: str  # "+1", "-1", "laugh", "heart", etc.
    user: str
    created_at: str


@dataclass(frozen=True, slots=True)
class TimelineEvent:
    id: int | str
    event: str  # "labeled", "assigned", "closed", etc.
    actor: str
    created_at: str
    detail: str


@dataclass(frozen=True, slots=True)
class Commit:
    sha: str
    message: str
    author: str
    url: str
    created_at: str


@dataclass(frozen=True, slots=True)
class Package:
    name: str
    type: str  # "npm", "maven", "container", "pypi", etc.
    version: str
    owner: str
    url: str
    created_at: str


@dataclass(frozen=True, slots=True)
class TimeEntry:
    id: int | str
    user: str
    duration: int  # seconds
    created_at: str


@dataclass(frozen=True, slots=True)
class PushMirror:
    id: int | str
    remote_name: str
    remote_address: str
    interval: str
    created_at: str
    last_update: str | None = None
    last_error: str | None = None


@dataclass(frozen=True, slots=True)
class WikiRevision:
    sha: str
    author: str
    message: str
    created_at: str


class GitHubLikeAdapter(ABC):
    """GitHub API 互換サービス（GitHub/Gitea 系）向け共通変換ヘルパー。

    GitHubAdapter・GiteaAdapter・GitBucketAdapter・ForgejoAdapter が共有する
    6 つの `_to_*` 静的メソッドをここに集約する。API レスポンスのフィールド名が
    GitHub / Gitea で一致しているためコードが共通化できる。
    """

    @staticmethod
    def _to_pull_request(data: dict) -> PullRequest:
        try:
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
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_issue(data: dict) -> Issue:
        try:
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
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_repository(data: dict) -> Repository:
        try:
            return Repository(
                name=data["name"],
                full_name=data["full_name"],
                description=data.get("description"),
                private=data["private"],
                default_branch=data.get("default_branch"),
                clone_url=data["clone_url"],
                url=data["html_url"],
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_release(data: dict) -> Release:
        try:
            return Release(
                tag=data["tag_name"],
                title=data.get("name") or "",
                body=data.get("body"),
                draft=data.get("draft", False),
                prerelease=data.get("prerelease", False),
                url=data.get("html_url") or "",
                created_at=data["created_at"],
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_label(data: dict) -> Label:
        try:
            return Label(
                name=data["name"],
                color=data.get("color"),
                description=data.get("description"),
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_milestone(data: dict) -> Milestone:
        try:
            return Milestone(
                number=data.get("number") or data["id"],
                title=data["title"],
                description=data.get("description"),
                state=data["state"],
                due_date=data.get("due_on"),
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_comment(data: dict) -> Comment:
        try:
            return Comment(
                id=data["id"],
                body=data.get("body") or "",
                author=data["user"]["login"],
                url=data.get("html_url") or "",
                created_at=data["created_at"],
                updated_at=data.get("updated_at"),
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_review(data: dict) -> Review:
        try:
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
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_branch(data: dict) -> Branch:
        try:
            commit = data.get("commit") or {}
            sha = commit.get("sha") or commit.get("id") or ""
            return Branch(
                name=data["name"],
                sha=sha,
                protected=data.get("protected", False),
                url=data.get("_links", {}).get("html") or "",
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_tag(data: dict) -> Tag:
        try:
            commit = data.get("commit") or {}
            sha = commit.get("sha") or ""
            return Tag(
                name=data["name"],
                sha=sha,
                message="",
                url=data.get("zipball_url") or "",
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_commit_status(data: dict) -> CommitStatus:
        try:
            # GitHub は "state"、Gitea は "status" を使用する
            state = data.get("state") or data.get("status") or ""
            return CommitStatus(
                state=state,
                context=data.get("context") or "",
                description=data.get("description") or "",
                target_url=data.get("target_url") or "",
                created_at=data.get("created_at") or "",
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_webhook(data: dict) -> Webhook:
        try:
            config = data.get("config") or {}
            url = config.get("url") or data.get("url") or ""
            events = tuple(data.get("events") or [])
            return Webhook(
                id=data["id"],
                url=url,
                events=events,
                active=data.get("active", True),
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_deploy_key(data: dict) -> DeployKey:
        try:
            return DeployKey(
                id=data["id"],
                title=data.get("title") or "",
                key=data.get("key") or "",
                read_only=data.get("read_only", True),
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_check_run(data: dict) -> CheckRun:
        try:
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
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_release_asset(data: dict) -> ReleaseAsset:
        try:
            return ReleaseAsset(
                id=data["id"],
                name=data["name"],
                size=data.get("size") or 0,
                download_url=data.get("browser_download_url") or "",
                created_at=data.get("created_at") or "",
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_pull_request_file(data: dict) -> PullRequestFile:
        try:
            return PullRequestFile(
                filename=data.get("filename") or "",
                status=data.get("status") or "modified",
                additions=data.get("additions") or 0,
                deletions=data.get("deletions") or 0,
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_pull_request_commit(data: dict) -> PullRequestCommit:
        try:
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
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e


class GitServiceAdapter(ABC):
    """Git サービスアダプターの抽象基底クラス。"""

    service_name: str

    def __init__(self, client, owner: str, repo: str, **kwargs):
        # **kwargs はサービス固有パラメータ（BacklogAdapter の project_key、
        # AzureDevOpsAdapter の organization 等）をサブクラスが super().__init__() で
        # 受け渡す際に吸収するためのもの。基底クラスでは使用しない。
        self._client = client
        self._owner = owner
        self._repo = repo

    @property
    def owner(self) -> str:
        """リポジトリオーナー名（読み取り専用）。"""
        return self._owner

    @property
    def repo(self) -> str:
        """リポジトリ名（読み取り専用）。"""
        return self._repo

    # --- PR ---
    @abstractmethod
    def list_pull_requests(self, *, state: str = "open", limit: int = 30) -> list[PullRequest]: ...

    @abstractmethod
    def create_pull_request(
        self, *, title: str, body: str = "", base: str, head: str, draft: bool = False
    ) -> PullRequest: ...

    @abstractmethod
    def get_pull_request(self, number: int) -> PullRequest: ...

    @abstractmethod
    def merge_pull_request(self, number: int, *, method: str = "merge") -> None: ...

    @abstractmethod
    def close_pull_request(self, number: int) -> None: ...

    def reopen_pull_request(self, number: int) -> None:
        raise NotSupportedError(self.service_name, "pr reopen")

    def get_pr_checkout_refspec(self, number: int, *, pr: PullRequest | None = None) -> str:
        """PR チェックアウト用の refspec を返す。

        サブクラスでオーバーライド可能。
        デフォルト実装は NotSupportedError を送出する。
        """
        raise NotSupportedError(self.service_name, "pr checkout")

    def get_pull_request_diff(self, number: int) -> str:
        raise NotSupportedError(self.service_name, "pr diff")

    def list_pull_request_checks(self, number: int) -> list[CheckRun]:
        raise NotSupportedError(self.service_name, "pr checks")

    def list_pull_request_files(self, number: int) -> list[PullRequestFile]:
        raise NotSupportedError(self.service_name, "pr files")

    def list_pull_request_commits(self, number: int) -> list[PullRequestCommit]:
        raise NotSupportedError(self.service_name, "pr commits")

    def list_requested_reviewers(self, number: int) -> list[str]:
        raise NotSupportedError(self.service_name, "pr reviewers list")

    def request_reviewers(self, number: int, reviewers: list[str]) -> None:
        raise NotSupportedError(self.service_name, "pr reviewers add")

    def remove_reviewers(self, number: int, reviewers: list[str]) -> None:
        raise NotSupportedError(self.service_name, "pr reviewers remove")

    def update_pull_request_branch(self, number: int) -> None:
        raise NotSupportedError(self.service_name, "pr update-branch")

    def enable_auto_merge(self, number: int, *, merge_method: str | None = None) -> None:
        raise NotSupportedError(self.service_name, "pr auto-merge")

    def dismiss_review(self, number: int, review_id: int, *, message: str = "") -> None:
        raise NotSupportedError(self.service_name, "review dismiss")

    def mark_pull_request_ready(self, number: int) -> None:
        raise NotSupportedError(self.service_name, "pr ready")

    # --- Issue ---
    @abstractmethod
    def list_issues(
        self,
        *,
        state: str = "open",
        assignee: str | None = None,
        label: str | None = None,
        limit: int = 30,
    ) -> list[Issue]: ...

    @abstractmethod
    def create_issue(
        self,
        *,
        title: str,
        body: str = "",
        assignee: str | None = None,
        label: str | None = None,
        **kwargs,
    ) -> Issue: ...

    @abstractmethod
    def get_issue(self, number: int) -> Issue: ...

    @abstractmethod
    def close_issue(self, number: int) -> None: ...

    def reopen_issue(self, number: int) -> None:
        raise NotSupportedError(self.service_name, "issue reopen")

    def delete_issue(self, number: int) -> None:
        raise NotSupportedError(self.service_name, "issue delete")

    def list_issue_templates(self) -> list[IssueTemplate]:
        raise NotSupportedError(self.service_name, "issue-template list")

    # --- Repository ---
    @abstractmethod
    def list_repositories(
        self, *, owner: str | None = None, limit: int = 30
    ) -> list[Repository]: ...

    @abstractmethod
    def create_repository(
        self, *, name: str, private: bool = False, description: str = ""
    ) -> Repository: ...

    @abstractmethod
    def get_repository(self, owner: str | None = None, name: str | None = None) -> Repository:
        """リポジトリ情報を取得する。

        owner, name が None の場合は self._owner, self._repo を使用する。
        """
        ...

    def delete_repository(self) -> None:
        """リポジトリを削除する。引数なし（self._owner, self._repo を使用）。"""
        raise NotSupportedError(self.service_name, "repo delete")

    def update_repository(
        self,
        *,
        description: str | None = None,
        private: bool | None = None,
        default_branch: str | None = None,
    ) -> Repository:
        raise NotSupportedError(self.service_name, "repo update")

    def archive_repository(self) -> None:
        raise NotSupportedError(self.service_name, "repo archive")

    def get_languages(self) -> dict[str, int | float]:
        raise NotSupportedError(self.service_name, "repo languages")

    def list_topics(self) -> list[str]:
        raise NotSupportedError(self.service_name, "repo topics list")

    def set_topics(self, topics: list[str]) -> list[str]:
        raise NotSupportedError(self.service_name, "repo topics set")

    def add_topic(self, topic: str) -> list[str]:
        """トピックを追加する。

        list_topics() + set_topics() を使うデフォルト実装。
        サービス固有の API がある場合はオーバーライドすること。
        """
        topics = self.list_topics()
        if topic not in topics:
            topics.append(topic)
            return self.set_topics(topics)
        return topics

    def remove_topic(self, topic: str) -> list[str]:
        """トピックを削除する。

        list_topics() + set_topics() を使うデフォルト実装。
        サービス固有の API がある場合はオーバーライドすること。
        """
        topics = self.list_topics()
        if topic in topics:
            topics.remove(topic)
            return self.set_topics(topics)
        return topics

    def compare(self, base: str, head: str) -> CompareResult:
        raise NotSupportedError(self.service_name, "repo compare")

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
        raise NotSupportedError(self.service_name, "repo migrate")

    # --- Release ---
    @abstractmethod
    def list_releases(self, *, limit: int = 30) -> list[Release]: ...

    @abstractmethod
    def create_release(
        self,
        *,
        tag: str,
        title: str = "",
        notes: str = "",
        draft: bool = False,
        prerelease: bool = False,
    ) -> Release: ...

    def delete_release(self, *, tag: str) -> None:
        raise NotSupportedError(self.service_name, "release delete")

    def get_release(self, *, tag: str) -> Release:
        raise NotSupportedError(self.service_name, "release view")

    def update_release(
        self,
        *,
        tag: str,
        title: str | None = None,
        notes: str | None = None,
        draft: bool | None = None,
        prerelease: bool | None = None,
    ) -> Release:
        raise NotSupportedError(self.service_name, "release update")

    def get_latest_release(self) -> Release:
        raise NotSupportedError(self.service_name, "release latest")

    def list_release_assets(self, *, tag: str) -> list[ReleaseAsset]:
        raise NotSupportedError(self.service_name, "release asset list")

    def upload_release_asset(
        self, *, tag: str, file_path: str, name: str | None = None
    ) -> ReleaseAsset:
        raise NotSupportedError(self.service_name, "release asset upload")

    def download_release_asset(self, *, tag: str, asset_id: int | str, output_dir: str) -> str:
        """アセットをダウンロードし、保存先パスを返す。"""
        raise NotSupportedError(self.service_name, "release asset download")

    def delete_release_asset(self, *, tag: str, asset_id: int | str) -> None:
        raise NotSupportedError(self.service_name, "release asset delete")

    # --- Label ---
    @abstractmethod
    def list_labels(self, *, limit: int = 0) -> list[Label]: ...

    @abstractmethod
    def create_label(
        self, *, name: str, color: str | None = None, description: str | None = None
    ) -> Label: ...

    def delete_label(self, *, name: str) -> None:
        raise NotSupportedError(self.service_name, "label delete")

    def update_label(
        self,
        *,
        name: str,
        new_name: str | None = None,
        color: str | None = None,
        description: str | None = None,
    ) -> Label:
        raise NotSupportedError(self.service_name, "label update")

    # --- Milestone ---
    @abstractmethod
    def list_milestones(self, *, limit: int = 0) -> list[Milestone]: ...

    @abstractmethod
    def create_milestone(
        self, *, title: str, description: str | None = None, due_date: str | None = None
    ) -> Milestone: ...

    def delete_milestone(self, *, number: int) -> None:
        raise NotSupportedError(self.service_name, "milestone delete")

    def get_milestone(self, number: int) -> Milestone:
        raise NotSupportedError(self.service_name, "milestone view")

    def update_milestone(
        self,
        number: int,
        *,
        title: str | None = None,
        description: str | None = None,
        due_date: str | None = None,
        state: str | None = None,
    ) -> Milestone:
        raise NotSupportedError(self.service_name, "milestone update")

    # --- Comment ---
    @abstractmethod
    def list_comments(self, resource: str, number: int, *, limit: int = 30) -> list[Comment]: ...

    @abstractmethod
    def create_comment(self, resource: str, number: int, *, body: str) -> Comment: ...

    def update_comment(self, resource: str, comment_id: int, *, body: str) -> Comment:
        raise NotSupportedError(self.service_name, "comment update")

    def delete_comment(self, resource: str, comment_id: int) -> None:
        raise NotSupportedError(self.service_name, "comment delete")

    # --- PR update ---
    @abstractmethod
    def update_pull_request(
        self,
        number: int,
        *,
        title: str | None = None,
        body: str | None = None,
        base: str | None = None,
    ) -> PullRequest: ...

    # --- Issue update ---
    @abstractmethod
    def update_issue(
        self,
        number: int,
        *,
        title: str | None = None,
        body: str | None = None,
        assignee: str | None = None,
        label: str | None = None,
    ) -> Issue: ...

    # --- Review ---
    def list_reviews(self, number: int) -> list[Review]:
        raise NotSupportedError(self.service_name, "review list")

    def create_review(self, number: int, *, state: str, body: str = "") -> Review:
        raise NotSupportedError(self.service_name, "review create")

    # --- Branch ---
    @abstractmethod
    def list_branches(self, *, limit: int = 30) -> list[Branch]: ...

    @abstractmethod
    def create_branch(self, *, name: str, ref: str) -> Branch: ...

    def delete_branch(self, *, name: str) -> None:
        raise NotSupportedError(self.service_name, "branch delete")

    # --- Tag ---
    def list_tags(self, *, limit: int = 30) -> list[Tag]:
        raise NotSupportedError(self.service_name, "tag list")

    def create_tag(self, *, name: str, ref: str, message: str = "") -> Tag:
        raise NotSupportedError(self.service_name, "tag create")

    def delete_tag(self, *, name: str) -> None:
        raise NotSupportedError(self.service_name, "tag delete")

    # --- CommitStatus ---
    def list_commit_statuses(self, ref: str, *, limit: int = 30) -> list[CommitStatus]:
        raise NotSupportedError(self.service_name, "commit status list")

    def create_commit_status(
        self,
        ref: str,
        *,
        state: str,
        context: str = "",
        description: str = "",
        target_url: str = "",
    ) -> CommitStatus:
        raise NotSupportedError(self.service_name, "commit status create")

    # --- File ---
    def get_file_content(self, path: str, *, ref: str | None = None) -> tuple[str, str]:
        """ファイル内容と SHA を返す。Returns (content, sha)。"""
        raise NotSupportedError(self.service_name, "file get")

    def create_or_update_file(
        self,
        path: str,
        *,
        content: str,
        message: str,
        sha: str | None = None,
        branch: str | None = None,
    ) -> str | None:
        """ファイルを作成または更新する。Returns: commit SHA（サービスが返さない場合は None）。"""
        raise NotSupportedError(self.service_name, "file put")

    def delete_file(
        self,
        path: str,
        *,
        sha: str,
        message: str,
        branch: str | None = None,
    ) -> None:
        raise NotSupportedError(self.service_name, "file delete")

    # --- Fork ---
    def fork_repository(self, *, organization: str | None = None) -> Repository:
        raise NotSupportedError(self.service_name, "repo fork")

    # --- Webhook ---
    def list_webhooks(self, *, limit: int = 30) -> list[Webhook]:
        raise NotSupportedError(self.service_name, "webhook list")

    def create_webhook(self, *, url: str, events: list[str], secret: str | None = None) -> Webhook:
        raise NotSupportedError(self.service_name, "webhook create")

    def delete_webhook(self, *, hook_id: int) -> None:
        raise NotSupportedError(self.service_name, "webhook delete")

    def test_webhook(self, *, hook_id: int) -> None:
        raise NotSupportedError(self.service_name, "webhook test")

    # --- DeployKey ---
    def list_deploy_keys(self, *, limit: int = 30) -> list[DeployKey]:
        raise NotSupportedError(self.service_name, "deploy-key list")

    def create_deploy_key(self, *, title: str, key: str, read_only: bool = True) -> DeployKey:
        raise NotSupportedError(self.service_name, "deploy-key create")

    def delete_deploy_key(self, *, key_id: int) -> None:
        raise NotSupportedError(self.service_name, "deploy-key delete")

    # --- Collaborator ---
    def list_collaborators(self, *, limit: int = 30) -> list[str]:
        raise NotSupportedError(self.service_name, "collaborator list")

    def add_collaborator(self, *, username: str, permission: str = "write") -> None:
        raise NotSupportedError(self.service_name, "collaborator add")

    def remove_collaborator(self, *, username: str) -> None:
        raise NotSupportedError(self.service_name, "collaborator remove")

    # --- Pipeline (CI) ---
    def list_pipelines(self, *, ref: str | None = None, limit: int = 30) -> list[Pipeline]:
        raise NotSupportedError(self.service_name, "ci list")

    def get_pipeline(self, pipeline_id: int | str) -> Pipeline:
        raise NotSupportedError(self.service_name, "ci view")

    def cancel_pipeline(self, pipeline_id: int | str) -> None:
        raise NotSupportedError(self.service_name, "ci cancel")

    def trigger_pipeline(
        self, ref: str, *, workflow: str | None = None, inputs: dict | None = None
    ) -> Pipeline:
        raise NotSupportedError(self.service_name, "ci trigger")

    def retry_pipeline(self, pipeline_id: int | str) -> Pipeline:
        raise NotSupportedError(self.service_name, "ci retry")

    def get_pipeline_logs(self, pipeline_id: int | str, *, job_id: int | str | None = None) -> str:
        raise NotSupportedError(self.service_name, "ci logs")

    # --- User ---
    def get_current_user(self) -> dict:
        raise NotSupportedError(self.service_name, "user whoami")

    # --- Search ---
    def search_repositories(self, query: str, *, limit: int = 30) -> list[Repository]:
        raise NotSupportedError(self.service_name, "search repos")

    def search_issues(self, query: str, *, limit: int = 30) -> list[Issue]:
        raise NotSupportedError(self.service_name, "search issues")

    # --- Secret ---
    def list_secrets(self, *, limit: int = 30) -> list[Secret]:
        raise NotSupportedError(self.service_name, "secret list")

    def set_secret(self, name: str, value: str) -> Secret:
        raise NotSupportedError(self.service_name, "secret set")

    def delete_secret(self, name: str) -> None:
        raise NotSupportedError(self.service_name, "secret delete")

    # --- Variable ---
    def list_variables(self, *, limit: int = 30) -> list[Variable]:
        raise NotSupportedError(self.service_name, "variable list")

    def set_variable(self, name: str, value: str, *, masked: bool = False) -> Variable:
        raise NotSupportedError(self.service_name, "variable set")

    def get_variable(self, name: str) -> Variable:
        raise NotSupportedError(self.service_name, "variable get")

    def delete_variable(self, name: str) -> None:
        raise NotSupportedError(self.service_name, "variable delete")

    # --- BranchProtection ---
    def list_branch_protections(self, *, limit: int = 30) -> list[BranchProtection]:
        raise NotSupportedError(self.service_name, "branch-protect list")

    def get_branch_protection(self, branch: str) -> BranchProtection:
        raise NotSupportedError(self.service_name, "branch-protect view")

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
        raise NotSupportedError(self.service_name, "branch-protect set")

    def remove_branch_protection(self, branch: str) -> None:
        raise NotSupportedError(self.service_name, "branch-protect remove")

    # --- TagProtection ---
    def list_tag_protections(self, *, limit: int = 30) -> list[TagProtection]:
        raise NotSupportedError(self.service_name, "tag-protect list")

    def create_tag_protection(
        self, pattern: str, *, create_access_level: str | None = None
    ) -> TagProtection:
        raise NotSupportedError(self.service_name, "tag-protect create")

    def delete_tag_protection(self, protection_id: int | str) -> None:
        raise NotSupportedError(self.service_name, "tag-protect delete")

    # --- Notification ---
    def list_notifications(
        self, *, unread_only: bool = False, limit: int = 30
    ) -> list[Notification]:
        raise NotSupportedError(self.service_name, "notification list")

    def mark_notification_read(self, notification_id: str) -> None:
        raise NotSupportedError(self.service_name, "notification read")

    def mark_all_notifications_read(self) -> None:
        raise NotSupportedError(self.service_name, "notification read --all")

    # --- Organization ---
    def list_organizations(self, *, limit: int = 30) -> list[Organization]:
        raise NotSupportedError(self.service_name, "org list")

    def get_organization(self, name: str) -> Organization:
        raise NotSupportedError(self.service_name, "org view")

    def list_org_members(self, name: str, *, limit: int = 30) -> list[str]:
        """メンバーのユーザー名一覧を返す。"""
        raise NotSupportedError(self.service_name, "org members")

    def list_org_repos(self, name: str, *, limit: int = 30) -> list[Repository]:
        raise NotSupportedError(self.service_name, "org repos")

    def create_organization(
        self, name: str, *, display_name: str | None = None, description: str | None = None
    ) -> Organization:
        raise NotSupportedError(self.service_name, "org create")

    def delete_organization(self, name: str) -> None:
        raise NotSupportedError(self.service_name, "org delete")

    # --- SSH Key ---
    def list_ssh_keys(self, *, limit: int = 30) -> list[SshKey]:
        raise NotSupportedError(self.service_name, "ssh-key list")

    def create_ssh_key(self, *, title: str, key: str) -> SshKey:
        raise NotSupportedError(self.service_name, "ssh-key create")

    def delete_ssh_key(self, *, key_id: int | str) -> None:
        raise NotSupportedError(self.service_name, "ssh-key delete")

    # --- GPG Key ---
    def list_gpg_keys(self, *, limit: int = 30) -> list[GpgKey]:
        raise NotSupportedError(self.service_name, "gpg-key list")

    def create_gpg_key(self, *, armored_key: str) -> GpgKey:
        raise NotSupportedError(self.service_name, "gpg-key create")

    def delete_gpg_key(self, *, key_id: int | str) -> None:
        raise NotSupportedError(self.service_name, "gpg-key delete")

    # --- Browse ---
    def get_web_url(self, resource: str = "repo", number: int | None = None) -> str:
        """Web ブラウザで開くための URL を返す。

        Args:
            resource: "repo" | "pr" | "issue" | "settings"
            number: PR / Issue 番号（resource が "pr" / "issue" の場合に必須）

        Returns:
            完全な URL 文字列
        """
        raise NotSupportedError(self.service_name, "browse")

    # --- Wiki ---
    def list_wiki_pages(self, *, limit: int = 30) -> list[WikiPage]:
        raise NotSupportedError(self.service_name, "wiki list")

    def get_wiki_page(self, page_id: int | str) -> WikiPage:
        raise NotSupportedError(self.service_name, "wiki view")

    def create_wiki_page(self, *, title: str, content: str) -> WikiPage:
        raise NotSupportedError(self.service_name, "wiki create")

    def update_wiki_page(
        self,
        page_id: int | str,
        *,
        title: str | None = None,
        content: str | None = None,
    ) -> WikiPage:
        raise NotSupportedError(self.service_name, "wiki update")

    def delete_wiki_page(self, page_id: int | str) -> None:
        raise NotSupportedError(self.service_name, "wiki delete")

    def list_wiki_revisions(self, page_name: str) -> list[WikiRevision]:
        raise NotSupportedError(self.service_name, "wiki revisions")

    # --- Issue Reaction ---
    def list_issue_reactions(self, number: int) -> list[Reaction]:
        raise NotSupportedError(self.service_name, "issue reaction list")

    def add_issue_reaction(self, number: int, reaction: str) -> Reaction:
        raise NotSupportedError(self.service_name, "issue reaction add")

    def remove_issue_reaction(self, number: int, reaction: str) -> None:
        raise NotSupportedError(self.service_name, "issue reaction remove")

    # --- Issue Dependency ---
    def list_issue_dependencies(self, number: int) -> list[Issue]:
        raise NotSupportedError(self.service_name, "issue depends list")

    def add_issue_dependency(self, number: int, depends_on: int) -> None:
        raise NotSupportedError(self.service_name, "issue depends add")

    def remove_issue_dependency(self, number: int, depends_on: int) -> None:
        raise NotSupportedError(self.service_name, "issue depends remove")

    # --- Issue Timeline ---
    def get_issue_timeline(self, number: int, *, limit: int = 30) -> list[TimelineEvent]:
        raise NotSupportedError(self.service_name, "issue timeline")

    # --- Issue Pin ---
    def pin_issue(self, number: int) -> None:
        raise NotSupportedError(self.service_name, "issue pin")

    def unpin_issue(self, number: int) -> None:
        raise NotSupportedError(self.service_name, "issue unpin")

    # --- Search PR / Commit ---
    def search_pull_requests(
        self, query: str, *, state: str | None = None, limit: int = 30
    ) -> list[PullRequest]:
        raise NotSupportedError(self.service_name, "search prs")

    def search_commits(
        self,
        query: str,
        *,
        author: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 30,
    ) -> list[Commit]:
        raise NotSupportedError(self.service_name, "search commits")

    # --- Package ---
    def list_packages(self, *, package_type: str | None = None, limit: int = 30) -> list[Package]:
        raise NotSupportedError(self.service_name, "package list")

    def get_package(self, package_type: str, name: str, *, version: str | None = None) -> Package:
        raise NotSupportedError(self.service_name, "package view")

    def delete_package(self, package_type: str, name: str, version: str) -> None:
        raise NotSupportedError(self.service_name, "package delete")

    # --- Time Tracking ---
    def list_time_entries(self, issue_number: int) -> list[TimeEntry]:
        raise NotSupportedError(self.service_name, "issue time list")

    def add_time_entry(self, issue_number: int, duration: int) -> TimeEntry:
        raise NotSupportedError(self.service_name, "issue time add")

    def delete_time_entry(self, issue_number: int, entry_id: int | str) -> None:
        raise NotSupportedError(self.service_name, "issue time delete")

    # --- Push Mirror ---
    def list_push_mirrors(self) -> list[PushMirror]:
        raise NotSupportedError(self.service_name, "repo mirror list")

    def create_push_mirror(
        self,
        remote_address: str,
        *,
        interval: str = "8h",
        sync_on_commit: bool = True,
        auth_token: str | None = None,
    ) -> PushMirror:
        raise NotSupportedError(self.service_name, "repo mirror add")

    def delete_push_mirror(self, mirror_name: str) -> None:
        raise NotSupportedError(self.service_name, "repo mirror remove")

    def sync_mirror(self) -> None:
        raise NotSupportedError(self.service_name, "repo mirror sync")

    # --- Repo Transfer ---
    def transfer_repository(self, new_owner: str, *, team_ids: list[int] | None = None) -> None:
        raise NotSupportedError(self.service_name, "repo transfer")

    # --- Repo Star ---
    def star_repository(self) -> None:
        raise NotSupportedError(self.service_name, "repo star")

    def unstar_repository(self) -> None:
        raise NotSupportedError(self.service_name, "repo unstar")
