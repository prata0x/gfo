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
