from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from gfo.exceptions import NotSupportedError


@dataclass(frozen=True, slots=True)
class PullRequest:
    number: int
    title: str
    body: str | None
    state: str          # "open" | "closed" | "merged"
    author: str
    source_branch: str
    target_branch: str
    draft: bool
    url: str
    created_at: str     # ISO 8601
    updated_at: str | None


@dataclass(frozen=True, slots=True)
class Issue:
    number: int
    title: str
    body: str | None
    state: str          # "open" | "closed"
    author: str
    assignees: list[str]
    labels: list[str]
    url: str
    created_at: str


@dataclass(frozen=True, slots=True)
class Repository:
    name: str
    full_name: str      # "owner/repo"
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
    state: str          # "open" | "closed"
    due_date: str | None


class GitServiceAdapter(ABC):
    """Git サービスアダプターの抽象基底クラス。"""

    service_name: str

    def __init__(self, client, owner: str, repo: str, **kwargs):
        self._client = client
        self._owner = owner
        self._repo = repo

    # --- PR ---
    @abstractmethod
    def list_pull_requests(self, *, state: str = "open",
                           limit: int = 30) -> list[PullRequest]: ...

    @abstractmethod
    def create_pull_request(self, *, title: str, body: str = "",
                            base: str, head: str,
                            draft: bool = False) -> PullRequest: ...

    @abstractmethod
    def get_pull_request(self, number: int) -> PullRequest: ...

    @abstractmethod
    def merge_pull_request(self, number: int, *,
                           method: str = "merge") -> None: ...

    @abstractmethod
    def close_pull_request(self, number: int) -> None: ...

    def get_pr_checkout_refspec(self, number: int, *,
                                pr: PullRequest | None = None) -> str:
        """PR チェックアウト用の refspec を返す。

        サブクラスでオーバーライド可能。
        デフォルト実装は NotSupportedError を送出する。
        """
        raise NotSupportedError(self.service_name, "pr checkout")

    # --- Issue ---
    @abstractmethod
    def list_issues(self, *, state: str = "open",
                    assignee: str | None = None,
                    label: str | None = None,
                    limit: int = 30) -> list[Issue]: ...

    @abstractmethod
    def create_issue(self, *, title: str, body: str = "",
                     assignee: str | None = None,
                     label: str | None = None,
                     **kwargs) -> Issue: ...

    @abstractmethod
    def get_issue(self, number: int) -> Issue: ...

    @abstractmethod
    def close_issue(self, number: int) -> None: ...

    # --- Repository ---
    @abstractmethod
    def list_repositories(self, *, owner: str | None = None,
                          limit: int = 30) -> list[Repository]: ...

    @abstractmethod
    def create_repository(self, *, name: str, private: bool = False,
                          description: str = "") -> Repository: ...

    @abstractmethod
    def get_repository(self, owner: str | None = None,
                       name: str | None = None) -> Repository:
        """リポジトリ情報を取得する。

        owner, name が None の場合は self._owner, self._repo を使用する。
        """
        ...

    # --- Release ---
    @abstractmethod
    def list_releases(self, *, limit: int = 30) -> list[Release]: ...

    @abstractmethod
    def create_release(self, *, tag: str, title: str = "",
                       notes: str = "", draft: bool = False,
                       prerelease: bool = False) -> Release: ...

    # --- Label ---
    @abstractmethod
    def list_labels(self) -> list[Label]: ...

    @abstractmethod
    def create_label(self, *, name: str, color: str | None = None,
                     description: str | None = None) -> Label: ...

    # --- Milestone ---
    @abstractmethod
    def list_milestones(self) -> list[Milestone]: ...

    @abstractmethod
    def create_milestone(self, *, title: str,
                         description: str | None = None,
                         due_date: str | None = None) -> Milestone: ...
