"""Git サービスアダプターの抽象基底クラスと共通ヘルパー。

このモジュールは以下を提供する:
- `GitServiceAdapter`: 全アダプターが継承する抽象基底クラス
- データクラス再エクスポート (`models.py` からの統一エクスポート)
- `GitHubLikeAdapter` 再エクスポート (`github_like.py` からの後方互換)
- `_wrap_conversion_error` / `_mask_token_in_exception` 再エクスポート (`_helpers.py` から)

歴史的経緯で `gfo.adapter.base` から多くの名前を import する箇所があるため、
モジュール分割後も後方互換のため再エクスポートを保つ。
"""

from __future__ import annotations

import warnings
from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
from typing import TYPE_CHECKING, Any, ClassVar

from gfo.adapter._helpers import _mask_token_in_exception, _wrap_conversion_error
from gfo.adapter.models import (
    Artifact,
    Branch,
    BranchProtection,
    CheckRun,
    CodeSearchResult,
    Comment,
    Commit,
    CommitStatus,
    CompareFile,
    CompareResult,
    Contributor,
    DeployKey,
    GpgKey,
    Issue,
    IssueTemplate,
    Label,
    Milestone,
    Notification,
    Organization,
    Package,
    Pipeline,
    PullRequest,
    PullRequestCommit,
    PullRequestFile,
    PushMirror,
    Reaction,
    Release,
    ReleaseAsset,
    Repository,
    Review,
    Secret,
    SshKey,
    Tag,
    TagProtection,
    TimeEntry,
    TimelineEvent,
    Variable,
    Webhook,
    WikiPage,
    WikiRevision,
    Workflow,
)
from gfo.exceptions import GfoError, NotSupportedError

if TYPE_CHECKING:
    from gfo.http import HttpClient

__all__ = [
    "Artifact",
    "Branch",
    "BranchProtection",
    "CheckRun",
    "CodeSearchResult",
    "Comment",
    "Commit",
    "CommitStatus",
    "CompareFile",
    "CompareResult",
    "Contributor",
    "DeployKey",
    "GitHubLikeAdapter",
    "GitServiceAdapter",
    "GpgKey",
    "Issue",
    "IssueTemplate",
    "Label",
    "Milestone",
    "Notification",
    "Organization",
    "Package",
    "Pipeline",
    "PullRequest",
    "PullRequestCommit",
    "PullRequestFile",
    "PushMirror",
    "Reaction",
    "Release",
    "ReleaseAsset",
    "Repository",
    "Review",
    "Secret",
    "SshKey",
    "Tag",
    "TagProtection",
    "TimeEntry",
    "TimelineEvent",
    "Variable",
    "Webhook",
    "WikiPage",
    "WikiRevision",
    "Workflow",
    "_mask_token_in_exception",
    "_wrap_conversion_error",
]


class GitServiceAdapter(ABC):
    """Git サービスアダプターの抽象基底クラス。"""

    service_name: str

    # サブクラスが上書きする Web URL パステーブル。
    # キー: "pr" | "issue" | "release" | "milestone" | "settings" 等。
    # 値: (list_path, detail_path)。detail_path が空文字列の場合は number 指定時も
    # list_path を返す (例: settings はリスト/詳細の区別なし)。
    _WEB_URL_PATHS: ClassVar[dict[str, tuple[str, str]]] = {}

    def __init__(self, client: HttpClient, owner: str, repo: str, **kwargs: object) -> None:
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

    @property
    def client(self) -> HttpClient:
        """内部 HTTP クライアントを返す。

        コマンド層で `asset.download_url` を直接ダウンロードする等、
        adapter にメソッドを生やすほどでもない場合の最小限の出入口。
        """
        return self._client

    def _warn_unsupported_params(self, resource: str, **kwargs: object) -> None:
        """未対応パラメータが渡された場合に警告を出す。"""
        for param, value in kwargs.items():
            if value:
                warnings.warn(
                    f"{self.service_name} does not support {param} on {resource}",
                    stacklevel=3,
                )

    # --- PR ---
    @abstractmethod
    def list_pull_requests(
        self,
        *,
        state: str = "open",
        limit: int = 30,
        author: str | None = None,
        label: str | None = None,
        assignee: str | None = None,
        search: str | None = None,
        base: str | None = None,
        head: str | None = None,
        draft: bool | None = None,
        milestone: str | None = None,
    ) -> list[PullRequest]: ...

    @abstractmethod
    def create_pull_request(
        self,
        *,
        title: str,
        body: str = "",
        base: str,
        head: str,
        draft: bool = False,
        reviewers: list[str] | None = None,
        assignees: list[str] | None = None,
        labels: list[str] | None = None,
        milestone: str | None = None,
    ) -> PullRequest: ...

    @abstractmethod
    def get_pull_request(self, number: int) -> PullRequest: ...

    @abstractmethod
    def merge_pull_request(
        self,
        number: int,
        *,
        method: str = "merge",
        title: str | None = None,
        message: str | None = None,
    ) -> None: ...

    @abstractmethod
    def close_pull_request(self, number: int) -> None: ...

    def reopen_pull_request(self, number: int) -> None:
        raise NotSupportedError(self.service_name, "pr reopen")

    def lock_pull_request(self, number: int, *, reason: str | None = None) -> None:
        raise NotSupportedError(self.service_name, "pr lock")

    def unlock_pull_request(self, number: int) -> None:
        raise NotSupportedError(self.service_name, "pr unlock")

    def get_pr_checkout_refspec(self, number: int, *, pr: PullRequest | None = None) -> str:
        """PR チェックアウト用の refspec を返す。

        サブクラスでオーバーライド可能。
        デフォルト実装は NotSupportedError を送出する。
        """
        raise NotSupportedError(self.service_name, "pr checkout")

    def get_pull_request_diff(self, number: int) -> Iterator[bytes]:
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

    def disable_auto_merge(self, number: int) -> None:
        raise NotSupportedError(self.service_name, "pr disable-auto-merge")

    def dismiss_review(self, number: int, review_id: int, *, message: str = "") -> None:
        raise NotSupportedError(self.service_name, "review dismiss")

    def mark_pull_request_ready(self, number: int) -> None:
        raise NotSupportedError(self.service_name, "pr ready")

    def subscribe_pull_request(self, number: int) -> None:
        raise NotSupportedError(self.service_name, "pr subscribe")

    def unsubscribe_pull_request(self, number: int) -> None:
        raise NotSupportedError(self.service_name, "pr unsubscribe")

    # --- Issue ---
    @abstractmethod
    def list_issues(
        self,
        *,
        state: str = "open",
        assignee: str | None = None,
        label: str | None = None,
        limit: int = 30,
        author: str | None = None,
        milestone: str | None = None,
        search: str | None = None,
    ) -> list[Issue]: ...

    @abstractmethod
    def create_issue(
        self,
        *,
        title: str,
        body: str = "",
        assignee: str | None = None,
        label: str | None = None,
        milestone: str | None = None,
        due_date: str | None = None,
        **kwargs: object,
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
        self,
        *,
        owner: str | None = None,
        limit: int = 30,
        archived: bool | None = None,
        visibility: str | None = None,
    ) -> list[Repository]: ...

    @abstractmethod
    def create_repository(
        self,
        *,
        name: str,
        visibility: str = "public",
        description: str = "",
        auto_init: bool = False,
        organization: str | None = None,
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
        name: str | None = None,
        description: str | None = None,
        private: bool | None = None,
        default_branch: str | None = None,
        archived: bool | None = None,
        allow_merge_commit: bool | None = None,
        allow_squash_merge: bool | None = None,
        allow_rebase_merge: bool | None = None,
        delete_branch_on_merge: bool | None = None,
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

    def list_contributors(self, *, limit: int = 30) -> list[Contributor]:
        raise NotSupportedError(self.service_name, "repo contributors")

    def compare(self, base: str, head: str) -> CompareResult:
        raise NotSupportedError(self.service_name, "repo compare")

    def migrate_repository(
        self,
        clone_url: str,
        name: str,
        *,
        visibility: str = "public",
        description: str = "",
        mirror: bool = False,
        auth_token: str | None = None,
        organization: str | None = None,
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
        target: str | None = None,
        generate_notes: bool = False,
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
        new_tag: str | None = None,
        target: str | None = None,
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

    def update_release_asset(
        self, *, tag: str, asset_id: int | str, name: str | None = None
    ) -> ReleaseAsset:
        raise NotSupportedError(self.service_name, "release asset edit")

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

    def _resolve_milestone_id_by_title(self, title: str) -> int:
        """milestone タイトルから number/ID を解決する。

        list_milestones() をループしてタイトル一致を探す汎用実装。
        API クエリで効率的に解決できるサービスはオーバーライドすること。
        """
        for ms in self.list_milestones():
            if ms.title == title:
                return ms.number
        raise GfoError(f"Milestone not found: {title}")

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
        add_labels: list[str] | None = None,
        remove_labels: list[str] | None = None,
        add_assignees: list[str] | None = None,
        remove_assignees: list[str] | None = None,
        milestone: str | None = None,
        draft: bool | None = None,
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
        add_labels: list[str] | None = None,
        remove_labels: list[str] | None = None,
        add_assignees: list[str] | None = None,
        remove_assignees: list[str] | None = None,
        milestone: str | None = None,
        due_date: str | None = None,
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

    def get_branch(self, name: str) -> Branch:
        raise NotSupportedError(self.service_name, "branch view")

    def delete_branch(self, *, name: str) -> None:
        raise NotSupportedError(self.service_name, "branch delete")

    # --- Tag ---
    def get_tag(self, name: str) -> Tag:
        raise NotSupportedError(self.service_name, "tag view")

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

    def update_webhook(
        self,
        hook_id: int,
        *,
        url: str | None = None,
        events: list[str] | None = None,
        secret: str | None = None,
        active: bool | None = None,
    ) -> Webhook:
        raise NotSupportedError(self.service_name, "webhook edit")

    # --- DeployKey ---
    def list_deploy_keys(self, *, limit: int = 30) -> list[DeployKey]:
        raise NotSupportedError(self.service_name, "deploy-key list")

    def create_deploy_key(self, *, title: str, key: str, read_only: bool = True) -> DeployKey:
        raise NotSupportedError(self.service_name, "deploy-key create")

    def get_deploy_key(self, key_id: int) -> DeployKey:
        raise NotSupportedError(self.service_name, "deploy-key view")

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
        self, ref: str, *, workflow: str | None = None, inputs: dict[str, Any] | None = None
    ) -> Pipeline:
        raise NotSupportedError(self.service_name, "ci trigger")

    def retry_pipeline(self, pipeline_id: int | str) -> Pipeline:
        raise NotSupportedError(self.service_name, "ci retry")

    def get_pipeline_logs(
        self, pipeline_id: int | str, *, job_id: int | str | None = None
    ) -> Iterable[str]:
        raise NotSupportedError(self.service_name, "ci logs")

    def list_workflows(self, *, limit: int = 30) -> list[Workflow]:
        raise NotSupportedError(self.service_name, "ci workflow list")

    def enable_workflow(self, workflow_id: int | str) -> None:
        raise NotSupportedError(self.service_name, "ci workflow enable")

    def disable_workflow(self, workflow_id: int | str) -> None:
        raise NotSupportedError(self.service_name, "ci workflow disable")

    def list_artifacts(self, run_id: int | str, *, limit: int = 30) -> list[Artifact]:
        raise NotSupportedError(self.service_name, "ci artifact list")

    def download_artifact(
        self, run_id: int | str, artifact_id: int | str, *, output_dir: str = "."
    ) -> str:
        raise NotSupportedError(self.service_name, "ci artifact download")

    def delete_pipeline_run(self, run_id: int | str) -> None:
        raise NotSupportedError(self.service_name, "ci delete")

    def download_run_logs(
        self, run_id: int | str, *, job_id: int | str | None = None, output_dir: str = "."
    ) -> str:
        raise NotSupportedError(self.service_name, "ci download")

    # --- User ---
    def get_current_user(self) -> dict[str, Any]:
        raise NotSupportedError(self.service_name, "user whoami")

    def get_current_username(self) -> str:
        user = self.get_current_user()
        for key in ("login", "username", "nickname", "userId"):
            if key in user and user[key]:
                return str(user[key])
        raise GfoError("Cannot determine username from current user response")

    # --- Search ---
    def search_repositories(self, query: str, *, limit: int = 30) -> list[Repository]:
        raise NotSupportedError(self.service_name, "search repos")

    def search_issues(self, query: str, *, limit: int = 30) -> list[Issue]:
        raise NotSupportedError(self.service_name, "search issues")

    def search_code(self, query: str, *, limit: int = 30) -> list[CodeSearchResult]:
        raise NotSupportedError(self.service_name, "search code")

    # --- Secret ---
    def list_secrets(self, *, scope: str | None = None, limit: int = 30) -> list[Secret]:
        raise NotSupportedError(self.service_name, "secret list")

    def set_secret(self, name: str, value: str, *, scope: str | None = None) -> Secret:
        raise NotSupportedError(self.service_name, "secret set")

    def delete_secret(self, name: str, *, scope: str | None = None) -> None:
        raise NotSupportedError(self.service_name, "secret delete")

    # --- Variable ---
    def list_variables(self, *, scope: str | None = None, limit: int = 30) -> list[Variable]:
        raise NotSupportedError(self.service_name, "variable list")

    def set_variable(
        self, name: str, value: str, *, scope: str | None = None, masked: bool = False
    ) -> Variable:
        raise NotSupportedError(self.service_name, "variable set")

    def get_variable(self, name: str, *, scope: str | None = None) -> Variable:
        raise NotSupportedError(self.service_name, "variable get")

    def delete_variable(self, name: str, *, scope: str | None = None) -> None:
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

    def update_tag_protection(
        self,
        protection_id: int | str,
        *,
        pattern: str | None = None,
        create_access_level: str | None = None,
    ) -> TagProtection:
        raise NotSupportedError(self.service_name, "tag-protect edit")

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

    def update_organization(
        self,
        name: str,
        *,
        display_name: str | None = None,
        description: str | None = None,
    ) -> Organization:
        raise NotSupportedError(self.service_name, "org edit")

    # --- SSH Key ---
    def list_ssh_keys(self, *, limit: int = 30) -> list[SshKey]:
        raise NotSupportedError(self.service_name, "ssh-key list")

    def create_ssh_key(self, *, title: str, key: str) -> SshKey:
        raise NotSupportedError(self.service_name, "ssh-key create")

    def get_ssh_key(self, key_id: int | str) -> SshKey:
        raise NotSupportedError(self.service_name, "ssh-key view")

    def delete_ssh_key(self, *, key_id: int | str) -> None:
        raise NotSupportedError(self.service_name, "ssh-key delete")

    # --- GPG Key ---
    def get_gpg_key(self, key_id: int | str) -> GpgKey:
        raise NotSupportedError(self.service_name, "gpg-key view")

    def list_gpg_keys(self, *, limit: int = 30) -> list[GpgKey]:
        raise NotSupportedError(self.service_name, "gpg-key list")

    def create_gpg_key(self, *, armored_key: str) -> GpgKey:
        raise NotSupportedError(self.service_name, "gpg-key create")

    def delete_gpg_key(self, *, key_id: int | str) -> None:
        raise NotSupportedError(self.service_name, "gpg-key delete")

    # --- Browse ---
    def _web_base_url(self) -> str:
        """Web UI のベース URL（owner/repo は含まない）を返す。

        サブクラスでオーバーライドすること。デフォルトは未対応。
        """
        raise NotSupportedError(self.service_name, "browse")

    def get_web_url(self, resource: str = "repo", number: int | str | None = None) -> str:
        """Web ブラウザで開くための URL を返す。

        デフォルト実装は `_web_base_url()` と `_WEB_URL_PATHS` を使う汎用ロジック:
          - resource == "repo": `{web_base}/{owner}/{repo}` を返す
          - resource が `_WEB_URL_PATHS` のキー: (list_path, detail_path) を引いて
            number=None ならリスト URL、number 指定なら詳細 URL を返す
            (detail_path が空文字列なら number 指定時もリスト URL を返す)

        URL 形式が大きく異なるサービス (Bitbucket / Backlog / Azure DevOps 等) は
        個別に override すること。

        Args:
            resource: "repo" | "pr" | "issue" | "release" | "milestone" | "settings"
            number: PR / Issue / Milestone 番号、または Release タグ名。
                    None の場合はリスト URL を返す。

        Returns:
            完全な URL 文字列
        """
        repo_url = f"{self._web_base_url()}/{self._owner}/{self._repo}"
        if resource == "repo":
            return repo_url
        paths = self._WEB_URL_PATHS.get(resource)
        if paths is None:
            raise NotSupportedError(self.service_name, f"browse {resource}")
        list_path, detail_path = paths
        if number is None or not detail_path:
            return f"{repo_url}/{list_path}"
        return f"{repo_url}/{detail_path}/{number}"

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

    # --- Issue Lock ---
    def lock_issue(self, number: int, *, reason: str | None = None) -> None:
        raise NotSupportedError(self.service_name, "issue lock")

    def unlock_issue(self, number: int) -> None:
        raise NotSupportedError(self.service_name, "issue unlock")

    # --- Issue Subscribe ---
    def subscribe_issue(self, number: int) -> None:
        raise NotSupportedError(self.service_name, "issue subscribe")

    def unsubscribe_issue(self, number: int) -> None:
        raise NotSupportedError(self.service_name, "issue unsubscribe")

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

    def add_time_entry(self, issue_number: int, duration: int | float) -> TimeEntry:
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

    # --- Fork Sync ---
    def sync_fork(self, *, branch: str | None = None) -> None:
        raise NotSupportedError(self.service_name, "repo sync")

    # --- Repo Transfer ---
    def transfer_repository(self, new_owner: str, *, team_ids: list[int] | None = None) -> None:
        raise NotSupportedError(self.service_name, "repo transfer")

    # --- Repo Star ---
    def star_repository(self) -> None:
        raise NotSupportedError(self.service_name, "repo star")

    def unstar_repository(self) -> None:
        raise NotSupportedError(self.service_name, "repo unstar")


# 後方互換: 既存コードは `from gfo.adapter.base import GitHubLikeAdapter` の
# 形で参照することが多いため、ここで再 export しておく。
# `_WEB_URL_PATHS` 経由の get_web_url デフォルト実装にも依存しないよう
# `github_like` モジュール側は base.py 完成後にロードされる順序になる。
from gfo.adapter.github_like import GitHubLikeAdapter  # noqa: E402, F401
