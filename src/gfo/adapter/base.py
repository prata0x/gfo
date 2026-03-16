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

    def get_pr_checkout_refspec(self, number: int, *, pr: PullRequest | None = None) -> str:
        """PR チェックアウト用の refspec を返す。

        サブクラスでオーバーライド可能。
        デフォルト実装は NotSupportedError を送出する。
        """
        raise NotSupportedError(self.service_name, "pr checkout")

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

    def delete_issue(self, number: int) -> None:
        raise NotSupportedError(self.service_name, "issue delete")

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

    # --- Label ---
    @abstractmethod
    def list_labels(self, *, limit: int = 0) -> list[Label]: ...

    @abstractmethod
    def create_label(
        self, *, name: str, color: str | None = None, description: str | None = None
    ) -> Label: ...

    def delete_label(self, *, name: str) -> None:
        raise NotSupportedError(self.service_name, "label delete")

    # --- Milestone ---
    @abstractmethod
    def list_milestones(self, *, limit: int = 0) -> list[Milestone]: ...

    @abstractmethod
    def create_milestone(
        self, *, title: str, description: str | None = None, due_date: str | None = None
    ) -> Milestone: ...

    def delete_milestone(self, *, number: int) -> None:
        raise NotSupportedError(self.service_name, "milestone delete")

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

    # --- User ---
    def get_current_user(self) -> dict:
        raise NotSupportedError(self.service_name, "user whoami")

    # --- Search ---
    def search_repositories(self, query: str, *, limit: int = 30) -> list[Repository]:
        raise NotSupportedError(self.service_name, "search repos")

    def search_issues(self, query: str, *, limit: int = 30) -> list[Issue]:
        raise NotSupportedError(self.service_name, "search issues")

    # --- SSH Key ---
    def list_ssh_keys(self, *, limit: int = 30) -> list[SshKey]:
        raise NotSupportedError(self.service_name, "ssh-key list")

    def create_ssh_key(self, *, title: str, key: str) -> SshKey:
        raise NotSupportedError(self.service_name, "ssh-key create")

    def delete_ssh_key(self, *, key_id: int | str) -> None:
        raise NotSupportedError(self.service_name, "ssh-key delete")

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
