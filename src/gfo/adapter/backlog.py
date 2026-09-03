"""Backlog アダプター。GitServiceAdapter の全メソッドを Backlog REST API v2 で実装する。"""

from __future__ import annotations

import urllib.parse
import warnings
from typing import TYPE_CHECKING, Any

from gfo.exceptions import GfoError, NotFoundError, NotSupportedError
from gfo.i18n import _

if TYPE_CHECKING:
    from gfo.http import HttpClient
from gfo.http import paginate_offset

from .base import GitServiceAdapter, _wrap_conversion_error
from .models import (
    Branch,
    Comment,
    Issue,
    Label,
    Milestone,
    Notification,
    PullRequest,
    Release,
    Repository,
    Tag,
    TimeEntry,
    Webhook,
    WikiPage,
)
from .registry import register

# Backlog PR / Issue ステータス ID 定数
_STATUS_CLOSED_ID = 4  # closed
_STATUS_MERGED_ID = 5  # merged（PR 固定値; カスタムの場合は動的解決で上書き）
# PR の open 相当（1=Open/2=処理中相当/3=処理済み相当）。
# `/projects/{projectKey}/statuses` は Issue 用ステータス一覧であり（#194 参照）、
# プロジェクトごとのカスタムステータス（id>=5）を含みうる。PR のステータス空間が
# Issue と同一かどうかは未確認のため、Issue 用エンドポイントの結果を PR の
# statusId[] フィルタへ流用せず、固定値に留める。
_PR_OPEN_STATUS_IDS = [1, 2, 3]

# Backlog Webhook の activityTypeIds（Backlog が API 全体で使う固定の Activity
# Type ID 番号体系。イベント種別ごとに番号が割り当てられ、サービスによる変動は
# ない）。gfo の汎用イベント名から対応する Activity Type ID 群へのマッピング。
_ACTIVITY_TYPE_IDS: dict[str, tuple[int, ...]] = {
    "issues": (1, 2, 4, 14),  # Issue Created/Updated/Deleted/Multi Updated
    "issue_comment": (3,),  # Issue Commented
    "pull_request": (18, 19, 21),  # Pull Request Added/Updated/Deleted
    "pull_request_review_comment": (20,),  # Comment Added on Pull Request
    "push": (12,),  # Git Pushed
    "wiki": (5, 6, 7),  # Wiki Created/Updated/Deleted
}


def _events_to_activity_type_ids(events: list[str]) -> list[int]:
    """gfo の汎用イベント名を Backlog の activityTypeIds へ変換する。

    未対応のイベント名は無視して警告する（Backlog 側に対応する Activity Type
    が存在しないため）。
    """
    ids: set[int] = set()
    for event in events:
        mapped = _ACTIVITY_TYPE_IDS.get(event)
        if mapped is None:
            warnings.warn(
                _("Backlog does not support webhook event '{event}'; ignored").format(event=event),
                stacklevel=3,
            )
            continue
        ids.update(mapped)
    return sorted(ids)


def _activity_type_ids_to_events(ids: list[int]) -> tuple[str, ...]:
    """Backlog の activityTypeIds を gfo の汎用イベント名へ変換する（表示用）。

    どの汎用イベント名にも属さない ID は、そのまま数値の文字列として残す。
    """
    events: list[str] = []
    for id_ in ids:
        name = next((n for n, mapped in _ACTIVITY_TYPE_IDS.items() if id_ in mapped), str(id_))
        if name not in events:
            events.append(name)
    return tuple(events)


@register("backlog")
class BacklogAdapter(GitServiceAdapter):
    service_name = "Backlog"

    def __init__(
        self, client: HttpClient, owner: str, repo: str, *, project_key: str, **kwargs: object
    ) -> None:
        super().__init__(client, owner, repo, **kwargs)
        self._project_key = project_key
        self._project_id: int | None = None
        self._merged_status_id: int | None = None
        self._statuses: list[dict[str, Any]] | None = None

    def _pr_path(self) -> str:
        return f"/projects/{self._project_key}/git/repositories/{urllib.parse.quote(self._repo, safe='')}/pullRequests"

    def _ensure_project_id(self) -> int:
        """プロジェクト ID を取得してキャッシュする。"""
        if self._project_id is None:
            resp = self._client.get(f"/projects/{self._project_key}")
            try:
                self._project_id = resp.json()["id"]
            except (KeyError, TypeError) as e:
                raise GfoError(
                    _("Unexpected API response from {endpoint} endpoint: {error}").format(
                        endpoint="project", error=e
                    )
                ) from e
        return self._project_id

    def _fetch_statuses(self) -> list[dict[str, Any]]:
        """プロジェクトのステータス一覧（生データ）を取得してキャッシュする。"""
        if self._statuses is not None:
            return self._statuses
        resp = self._client.get(f"/projects/{self._project_key}/statuses")
        statuses = resp.json()
        if not isinstance(statuses, list):
            raise GfoError(
                _("Unexpected API response from {endpoint} endpoint: {error}").format(
                    endpoint="statuses", error=type(statuses)
                )
            )
        self._statuses = statuses
        return statuses

    def _resolve_merged_status_id(self) -> int | None:
        """PR ステータス一覧から Merged 相当の statusId を動的に判定する。"""
        if self._merged_status_id is not None:
            return self._merged_status_id
        for status in self._fetch_statuses():
            try:
                if "merged" in status["name"].lower():
                    self._merged_status_id = status["id"]
                    return self._merged_status_id
            except (KeyError, TypeError, AttributeError):
                continue
        return None

    def _resolve_all_status_ids(self) -> list[int]:
        """プロジェクトの全ステータス ID 一覧を返す。

        標準4ステータスに加え、プロジェクト設定で追加されたカスタムステータス
        （id は 5 以降の任意の値）を含む。「open」扱いの statusId[] を組み立てる際、
        固定リストではなくこの一覧から closed/merged 相当を除いた ID を使うことで、
        カスタムステータスの課題・PR も一覧から取りこぼさないようにする。
        """
        ids: list[int] = []
        for status in self._fetch_statuses():
            try:
                ids.append(status["id"])
            except (KeyError, TypeError):
                continue
        if not ids:
            # 全件が不正な形式だった場合、statusId[] が空になり絞り込みなし
            # (--state open で closed/merged まで返る) へ静かに劣化してしまう。
            raise GfoError(
                _("Unexpected API response from {endpoint} endpoint: {error}").format(
                    endpoint="statuses", error="no valid status entries"
                )
            )
        return ids

    # --- 変換ヘルパー ---

    @staticmethod
    @_wrap_conversion_error
    def _to_pull_request(data: dict[str, Any], merged_status_id: int | None = None) -> PullRequest:
        status_id = (data.get("status") or {}).get("id", 1)
        if status_id == _STATUS_CLOSED_ID:
            state = "closed"
        elif merged_status_id is not None and status_id == merged_status_id:
            state = "merged"
        elif merged_status_id is None and status_id == _STATUS_MERGED_ID:
            state = "merged"
        else:
            state = "open"

        created_user = data.get("createdUser") or {}
        return PullRequest(
            number=data["number"],
            title=data["summary"],
            body=data.get("description"),
            state=state,
            author=created_user.get("userId", ""),
            source_branch=data.get("branch", ""),
            target_branch=data.get("base", ""),
            draft=False,
            url=data.get("url", ""),
            created_at=data.get("created", ""),
            updated_at=data.get("updated"),
        )

    @staticmethod
    def _to_issue(data: dict[str, Any]) -> Issue:
        try:
            status_id = (data.get("status") or {}).get("id", 1)
            state = "closed" if status_id == _STATUS_CLOSED_ID else "open"

            created_user = data.get("createdUser") or {}
            assignee = data.get("assignee")
            assignees = [assignee["userId"]] if assignee and "userId" in assignee else []

            issue_key = data.get("issueKey")
            try:
                number = int(issue_key.split("-")[-1]) if isinstance(issue_key, str) else data["id"]
            except ValueError:
                number = data["id"]

            return Issue(
                number=number,
                title=data["summary"],
                body=data.get("description"),
                state=state,
                author=created_user.get("userId", ""),
                assignees=assignees,
                labels=[],
                url=data.get("url", ""),
                created_at=data.get("created", ""),
                updated_at=data.get("updated"),
            )
        except (KeyError, TypeError, ValueError, AttributeError) as e:
            raise GfoError(
                _("Unexpected API response: missing field {error}").format(error=e)
            ) from e

    @staticmethod
    @_wrap_conversion_error
    def _to_repository(data: dict[str, Any]) -> Repository:
        return Repository(
            name=data["name"],
            full_name=data.get("displayName", data["name"]),
            description=data.get("description"),
            visibility="private",
            default_branch=None,
            clone_url=data.get("httpUrl", ""),
            url=data.get("httpUrl", "").removesuffix(".git"),
        )

    # --- PR ---

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
    ) -> list[PullRequest]:
        self._warn_unsupported_params(
            "pr list",
            author=author,
            label=label,
            assignee=assignee,
            search=search,
            base=base,
            head=head,
            draft=draft,
            milestone=milestone,
        )
        params: dict[str, Any] = {}
        merged_id: int | None = None
        if state == "merged":
            merged_id = self._resolve_merged_status_id()
            if merged_id is not None:
                params["statusId[]"] = [merged_id]
        elif state == "open":
            params["statusId[]"] = _PR_OPEN_STATUS_IDS
        elif state == "closed":
            params["statusId[]"] = [_STATUS_CLOSED_ID]
        else:
            # state="all": 動的 merged_status_id が必要
            merged_id = self._resolve_merged_status_id()
        results = paginate_offset(self._client, self._pr_path(), params=params, limit=limit)
        return [self._to_pull_request(r, merged_id) for r in results]

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
    ) -> PullRequest:
        self._warn_unsupported_params(
            "pull requests",
            reviewers=reviewers,
            assignees=assignees,
            labels=labels,
            milestone=milestone,
        )
        payload = {
            "summary": title,
            "description": body,
            "base": base,
            "branch": head,
        }
        resp = self._client.post(self._pr_path(), json=payload)
        return self._to_pull_request(resp.json(), self._resolve_merged_status_id())

    def get_pull_request(self, number: int) -> PullRequest:
        resp = self._client.get(f"{self._pr_path()}/{number}")
        return self._to_pull_request(resp.json(), self._resolve_merged_status_id())

    def merge_pull_request(
        self,
        number: int,
        *,
        method: str = "merge",
        title: str | None = None,
        message: str | None = None,
    ) -> None:
        hostname = urllib.parse.urlparse(self._client.base_url).hostname
        raise NotSupportedError(
            "Backlog",
            "pull request merge",
            web_url=f"https://{hostname}/git/{self._project_key}/{self._repo}/pullRequests/{number}",
        )

    def close_pull_request(self, number: int) -> None:
        self._client.patch(f"{self._pr_path()}/{number}", json={"statusId": _STATUS_CLOSED_ID})

    def reopen_pull_request(self, number: int) -> None:
        self._client.patch(f"{self._pr_path()}/{number}", json={"statusId": 1})

    def get_pr_checkout_refspec(self, number: int, *, pr: PullRequest | None = None) -> str:
        if pr is None:
            pr = self.get_pull_request(number)
        return pr.source_branch

    # --- Issue ---

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
    ) -> list[Issue]:
        self._warn_unsupported_params("issue list", author=author, milestone=milestone)
        project_id = self._ensure_project_id()
        params: dict[str, Any] = {"projectId[]": project_id}
        if state == "open":
            all_ids = self._resolve_all_status_ids()
            params["statusId[]"] = [i for i in all_ids if i != _STATUS_CLOSED_ID]
        elif state == "closed":
            params["statusId[]"] = [_STATUS_CLOSED_ID]
        if assignee:
            params["assigneeUserId[]"] = assignee
        if search:
            params["keyword"] = search
            if label:
                warnings.warn(
                    _("Backlog does not support search and label simultaneously; label ignored"),
                    stacklevel=2,
                )
        elif label:
            params["keyword"] = label
        results = paginate_offset(self._client, "/issues", params=params, limit=limit)
        return [self._to_issue(r) for r in results]

    def create_issue(  # type: ignore[override]  # issue_type, priority 追加引数
        self,
        *,
        title: str,
        body: str = "",
        assignee: str | None = None,
        label: str | None = None,
        milestone: str | None = None,
        due_date: str | None = None,
        issue_type: int | None = None,
        priority: int | None = None,
        **kwargs: object,
    ) -> Issue:
        self._warn_unsupported_params("issue create", milestone=milestone)
        project_id = self._ensure_project_id()

        if issue_type is None:
            resp = self._client.get(f"/projects/{self._project_key}/issueTypes")
            types = resp.json()
            if not isinstance(types, list):
                raise GfoError(
                    _("Unexpected API response from {endpoint} endpoint: {error}").format(
                        endpoint="issueTypes", error=type(types)
                    )
                )
            try:
                issue_type = types[0]["id"] if types else None
            except (KeyError, TypeError) as e:
                raise GfoError(
                    _("Unexpected API response from {endpoint} endpoint: {error}").format(
                        endpoint="issueTypes", error=e
                    )
                ) from e

        if priority is None:
            resp = self._client.get("/priorities")
            priorities = resp.json()
            if not isinstance(priorities, list):
                raise GfoError(
                    _("Unexpected API response from {endpoint} endpoint: {error}").format(
                        endpoint="priorities", error=type(priorities)
                    )
                )
            try:
                # "中" (Normal) を優先、なければ先頭
                priority = next(
                    (
                        p["id"]
                        for p in priorities
                        if "中" in p.get("name", "") or p.get("name", "").lower() == "normal"
                    ),
                    priorities[0]["id"] if priorities else None,
                )
            except (KeyError, TypeError) as e:
                raise GfoError(
                    _("Unexpected API response from {endpoint} endpoint: {error}").format(
                        endpoint="priorities", error=e
                    )
                ) from e

        if issue_type is None:
            raise GfoError(
                _(
                    "Cannot create issue: no issue types found for project "
                    "'{project}'. Configure issue types in Backlog."
                ).format(project=self._project_key)
            )
        if priority is None:
            raise GfoError(
                _("Cannot create issue: no priorities found. Configure priorities in Backlog.")
            )

        payload: dict[str, Any] = {
            "projectId": project_id,
            "summary": title,
            "issueTypeId": issue_type,
            "priorityId": priority,
        }
        if body:
            payload["description"] = body
        if assignee:
            payload["assigneeUserId"] = assignee
        if due_date:
            payload["dueDate"] = due_date

        resp = self._client.post("/issues", json=payload)
        return self._to_issue(resp.json())

    def get_issue(self, number: int) -> Issue:
        resp = self._client.get(f"/issues/{self._project_key}-{number}")
        return self._to_issue(resp.json())

    def close_issue(self, number: int) -> None:
        self._client.patch(
            f"/issues/{self._project_key}-{number}", json={"statusId": _STATUS_CLOSED_ID}
        )

    def reopen_issue(self, number: int) -> None:
        self._client.patch(f"/issues/{self._project_key}-{number}", json={"statusId": 1})

    def delete_issue(self, number: int) -> None:
        self._client.delete(f"/issues/{self._project_key}-{number}")

    # --- Repository ---

    def list_repositories(
        self,
        *,
        owner: str | None = None,
        limit: int = 30,
        archived: bool | None = None,
        visibility: str | None = None,
    ) -> list[Repository]:
        if owner is not None:
            raise NotSupportedError(
                self.service_name,
                "filtering repositories by owner "
                "(repositories are scoped to the configured project)",
            )
        self._warn_unsupported_params("repo list", archived=archived, visibility=visibility)
        results = paginate_offset(
            self._client,
            f"/projects/{self._project_key}/git/repositories",
            limit=limit,
        )
        return [self._to_repository(r) for r in results]

    def create_repository(
        self,
        *,
        name: str,
        visibility: str = "public",
        description: str = "",
        auto_init: bool = False,
        organization: str | None = None,
    ) -> Repository:
        self._warn_unsupported_params("repo create", auto_init=auto_init)
        # visibility, organization は Backlog ではプロジェクトスコープのため無視
        payload: dict[str, Any] = {"name": name}
        if description:
            payload["description"] = description
        resp = self._client.post(f"/projects/{self._project_key}/git/repositories", json=payload)
        return self._to_repository(resp.json())

    def get_repository(self, owner: str | None = None, name: str | None = None) -> Repository:
        n = name if name is not None else self._repo
        resp = self._client.get(
            f"/projects/{self._project_key}/git/repositories/{urllib.parse.quote(n, safe='')}"
        )
        return self._to_repository(resp.json())

    def delete_repository(self) -> None:
        self._client.delete(
            f"/projects/{self._project_key}/git/repositories/"
            f"{urllib.parse.quote(self._repo, safe='')}"
        )

    # --- NotSupported ---

    def list_releases(self, *, limit: int = 30) -> list[Release]:
        raise NotSupportedError(self.service_name, "releases")

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
    ) -> Release:
        raise NotSupportedError(self.service_name, "releases")

    def list_labels(self, *, limit: int = 0) -> list[Label]:
        raise NotSupportedError(self.service_name, "labels")

    def create_label(
        self, *, name: str, color: str | None = None, description: str | None = None
    ) -> Label:
        raise NotSupportedError(self.service_name, "labels")

    def list_milestones(self, *, state: str = "open", limit: int = 0) -> list[Milestone]:
        raise NotSupportedError(self.service_name, "milestones")

    def create_milestone(
        self, *, title: str, description: str | None = None, due_date: str | None = None
    ) -> Milestone:
        raise NotSupportedError(self.service_name, "milestones")

    def update_milestone(
        self,
        number: int,
        *,
        title: str | None = None,
        description: str | None = None,
        due_date: str | None = None,
        state: str | None = None,
    ) -> Milestone:
        payload: dict[str, Any] = {}
        if title is not None:
            payload["name"] = title
        if description is not None:
            payload["description"] = description
        if due_date is not None:
            payload["releaseDueDate"] = due_date
        if state is not None:
            payload["archived"] = state == "closed"
        resp = self._client.patch(f"/projects/{self._project_key}/versions/{number}", json=payload)
        data = resp.json()
        return Milestone(
            number=data["id"],
            title=data.get("name") or "",
            description=data.get("description"),
            state="closed" if data.get("archived") else "open",
            due_date=data.get("releaseDueDate"),
        )

    # --- 変換ヘルパー（Comment / Branch / Tag / Webhook / WikiPage）---

    @staticmethod
    @_wrap_conversion_error
    def _to_comment(data: dict[str, Any]) -> Comment:

        created_user = data.get("createdUser") or {}
        return Comment(
            id=data["id"],
            body=data.get("content") or "",
            author=created_user.get("userId") or "",
            url="",
            created_at=data.get("created") or "",
            updated_at=data.get("updated"),
        )

    def _branch_web_url(self, name: str) -> str:
        hostname = urllib.parse.urlparse(self._client.base_url).hostname
        # ブランチ名に # ? % 等の特殊文字や / を含む場合に正しいページへ到達するよう
        # quote する（/ は階層区切りとして維持）。
        return f"https://{hostname}/git/{self._project_key}/{self._repo}/tree/{urllib.parse.quote(name, safe='/')}"

    def _tag_web_url(self, name: str) -> str:
        return self._branch_web_url(name)

    @staticmethod
    @_wrap_conversion_error
    def _to_branch(data: dict[str, Any], default_url: str = "") -> Branch:

        return Branch(
            name=data["name"],
            sha=data.get("commit", {}).get("id") or "",
            protected=False,
            url=data.get("url") or default_url,
        )

    @staticmethod
    @_wrap_conversion_error
    def _to_tag(data: dict[str, Any], default_url: str = "") -> Tag:

        return Tag(
            name=data["name"],
            sha=data.get("commit", {}).get("id") or "",
            message="",
            url=data.get("url") or default_url,
        )

    @staticmethod
    @_wrap_conversion_error
    def _to_webhook(data: dict[str, Any]) -> Webhook:
        # Backlog webhook レスポンスの events 相当は activityTypeIds（数値配列）。
        events = _activity_type_ids_to_events(data.get("activityTypeIds") or [])
        return Webhook(
            id=data["id"],
            url=(data.get("hookUrl") or ""),
            events=events,
            active=True,
        )

    @staticmethod
    @_wrap_conversion_error
    def _to_wiki_page(data: dict[str, Any]) -> WikiPage:

        return WikiPage(
            id=data["id"],
            title=data.get("name") or "",
            content=data.get("content") or "",
            url="",
            updated_at=data.get("updated"),
        )

    # --- Comment ---

    def list_comments(self, resource: str, number: int, *, limit: int = 30) -> list[Comment]:
        if resource == "pr":
            path = f"{self._pr_path()}/{number}/comments"
        else:
            path = f"/issues/{self._project_key}-{number}/comments"
        results = paginate_offset(self._client, path, limit=limit)
        return [self._to_comment(r) for r in results]

    def create_comment(self, resource: str, number: int, *, body: str) -> Comment:
        if resource == "pr":
            path = f"{self._pr_path()}/{number}/comments"
        else:
            path = f"/issues/{self._project_key}-{number}/comments"
        resp = self._client.post(path, json={"content": body})
        return self._to_comment(resp.json())

    def update_comment(self, resource: str, comment_id: int, *, body: str) -> Comment:
        if resource == "pr":
            resp = self._client.patch(
                f"{self._pr_path()}/comments/{comment_id}",
                json={"content": body},
            )
        else:
            resp = self._client.patch(
                f"/issues/comments/{comment_id}",
                json={"content": body},
            )
        return self._to_comment(resp.json())

    def delete_comment(self, resource: str, comment_id: int) -> None:
        if resource == "pr":
            self._client.delete(f"{self._pr_path()}/comments/{comment_id}")
        else:
            self._client.delete(f"/issues/comments/{comment_id}")

    # --- PR update ---

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
    ) -> PullRequest:
        self._warn_unsupported_params(
            "pr edit",
            add_labels=add_labels,
            remove_labels=remove_labels,
            add_assignees=add_assignees,
            remove_assignees=remove_assignees,
            milestone=milestone,
            draft=draft,
        )
        payload: dict[str, Any] = {}
        if title is not None:
            payload["summary"] = title
        if body is not None:
            payload["description"] = body
        if base is not None:
            payload["base"] = base
        resp = self._client.patch(f"{self._pr_path()}/{number}", json=payload)
        return self._to_pull_request(resp.json(), self._resolve_merged_status_id())

    # --- Issue update ---

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
    ) -> Issue:
        self._warn_unsupported_params(
            "issue edit",
            add_labels=add_labels,
            remove_labels=remove_labels,
            add_assignees=add_assignees,
            remove_assignees=remove_assignees,
            milestone=milestone,
        )
        payload: dict[str, Any] = {}
        if title is not None:
            payload["summary"] = title
        if body is not None:
            payload["description"] = body
        if assignee is not None:
            payload["assigneeUserId"] = assignee
        if due_date is not None:
            payload["dueDate"] = due_date
        resp = self._client.patch(f"/issues/{self._project_key}-{number}", json=payload)
        return self._to_issue(resp.json())

    # --- Branch ---

    def get_branch(self, name: str) -> Branch:
        # Backlog API には単一ブランチ取得エンドポイントがないため一覧から検索
        results = paginate_offset(
            self._client,
            f"/projects/{self._project_key}/git/repositories/{urllib.parse.quote(self._repo, safe='')}/branches",
            limit=0,
        )
        for r in results:
            if r.get("name") == name:
                return self._to_branch(r, self._branch_web_url(name))

        raise NotFoundError(detail=f"Branch '{name}' not found")

    def list_branches(self, *, limit: int = 30) -> list[Branch]:
        results = paginate_offset(
            self._client,
            f"/projects/{self._project_key}/git/repositories/{urllib.parse.quote(self._repo, safe='')}/branches",
            limit=limit,
        )
        return [self._to_branch(r, self._branch_web_url(r["name"])) for r in results]

    def create_branch(self, *, name: str, ref: str) -> Branch:
        resp = self._client.post(
            f"/projects/{self._project_key}/git/repositories/{urllib.parse.quote(self._repo, safe='')}/branches",
            json={"name": name, "startPoint": ref},
        )
        return self._to_branch(resp.json(), self._branch_web_url(name))

    def delete_branch(self, *, name: str) -> None:
        self._client.delete(
            f"/projects/{self._project_key}/git/repositories/{urllib.parse.quote(self._repo, safe='')}/branches/{urllib.parse.quote(name, safe='')}"
        )

    # --- Tag ---

    def get_tag(self, name: str) -> Tag:
        # Backlog API には単一タグ取得エンドポイントがないため一覧から検索
        results = paginate_offset(
            self._client,
            f"/projects/{self._project_key}/git/repositories/{urllib.parse.quote(self._repo, safe='')}/tags",
            limit=0,
        )
        for r in results:
            if r.get("name") == name:
                return self._to_tag(r, self._tag_web_url(name))

        raise NotFoundError(detail=f"Tag '{name}' not found")

    def list_tags(self, *, limit: int = 30) -> list[Tag]:
        results = paginate_offset(
            self._client,
            f"/projects/{self._project_key}/git/repositories/{urllib.parse.quote(self._repo, safe='')}/tags",
            limit=limit,
        )
        return [self._to_tag(r, self._tag_web_url(r["name"])) for r in results]

    def create_tag(self, *, name: str, ref: str, message: str = "") -> Tag:
        payload: dict[str, Any] = {"name": name, "startPoint": ref}
        if message:
            payload["message"] = message
        resp = self._client.post(
            f"/projects/{self._project_key}/git/repositories/{urllib.parse.quote(self._repo, safe='')}/tags",
            json=payload,
        )
        return self._to_tag(resp.json(), self._tag_web_url(name))

    # --- Webhook ---

    def list_webhooks(self, *, limit: int = 30) -> list[Webhook]:
        resp = self._client.get(f"/projects/{self._project_key}/webhooks")
        hooks = resp.json()
        if isinstance(hooks, list):
            return [self._to_webhook(h) for h in hooks[: limit if limit > 0 else None]]
        return []

    def create_webhook(self, *, url: str, events: list[str], secret: str | None = None) -> Webhook:
        self._warn_unsupported_params("webhook create", secret=secret)
        payload: dict[str, Any] = {"hookUrl": url, "allEvent": not events}
        if events:
            activity_type_ids = _events_to_activity_type_ids(events)
            if not activity_type_ids:
                raise GfoError(
                    _("None of the given webhook events are supported by Backlog: {events}").format(
                        events=", ".join(events)
                    )
                )
            payload["activityTypeIds"] = activity_type_ids
        resp = self._client.post(f"/projects/{self._project_key}/webhooks", json=payload)
        return self._to_webhook(resp.json())

    def delete_webhook(self, *, hook_id: int) -> None:
        self._client.delete(f"/projects/{self._project_key}/webhooks/{hook_id}")

    def update_webhook(
        self,
        hook_id: int,
        *,
        url: str | None = None,
        events: list[str] | None = None,
        secret: str | None = None,
        active: bool | None = None,
    ) -> Webhook:
        self._warn_unsupported_params("webhook edit", secret=secret)
        if active is not None:
            # active=False（--inactive）は _warn_unsupported_params の truthy
            # チェックでは検知できないため、None チェックで個別に警告する。
            warnings.warn(
                _("{service} does not support active on webhook edit").format(
                    service=self.service_name
                ),
                stacklevel=2,
            )
        payload: dict[str, Any] = {}
        if url is not None:
            payload["hookUrl"] = url
        if events is not None:
            payload["allEvent"] = not events
            if events:
                activity_type_ids = _events_to_activity_type_ids(events)
                if not activity_type_ids:
                    raise GfoError(
                        _(
                            "None of the given webhook events are supported by Backlog: {events}"
                        ).format(events=", ".join(events))
                    )
                payload["activityTypeIds"] = activity_type_ids
            else:
                payload["activityTypeIds"] = []
        resp = self._client.patch(f"/projects/{self._project_key}/webhooks/{hook_id}", json=payload)
        return self._to_webhook(resp.json())

    # --- Collaborator ---

    def list_collaborators(self, *, limit: int = 30) -> list[str]:
        resp = self._client.get(f"/projects/{self._project_key}/users")
        users = resp.json()
        if isinstance(users, list):
            try:
                return [
                    u["userId"] for u in users[: limit if limit > 0 else None] if u.get("userId")
                ]
            except (KeyError, TypeError) as e:
                raise GfoError(_("Unexpected API response: {error}").format(error=e)) from e
        return []

    def add_collaborator(self, *, username: str, permission: str = "write") -> None:
        # Backlog ではユーザー ID が必要
        self._client.post(
            f"/projects/{self._project_key}/users",
            json={"userId": username},
        )

    def remove_collaborator(self, *, username: str) -> None:
        self._client.delete(
            f"/projects/{self._project_key}/users",
            json={"userId": username},
        )

    # --- User ---

    def get_current_user(self) -> dict[str, Any]:
        resp = self._client.get("/users/myself")
        return dict(resp.json())

    # --- Notification ---

    def list_notifications(
        self, *, unread_only: bool = False, limit: int = 30
    ) -> list[Notification]:
        params: dict[str, Any] = {}
        if unread_only:
            params["resourceAlreadyRead"] = "false"
        results = paginate_offset(self._client, "/notifications", params=params, limit=limit)
        return [self._to_notification(d) for d in results]

    def mark_notification_read(self, notification_id: str) -> None:
        self._client.post(f"/notifications/{notification_id}/markAsRead", json={})

    def mark_all_notifications_read(self) -> None:
        self._client.post("/notifications/markAsRead", json={})

    @staticmethod
    @_wrap_conversion_error
    def _to_notification(data: dict[str, Any]) -> Notification:
        comment = data.get("comment") or {}
        issue = comment.get("issue") or data.get("issue") or {}
        return Notification(
            id=str(data["id"]),
            title=issue.get("summary") or comment.get("content") or "",
            reason="notification",
            unread=not data.get("resourceAlreadyRead", False),
            repository="",
            url="",
            updated_at=data.get("created") or "",
        )

    # --- Browse ---

    def get_web_url(self, resource: str = "repo", number: int | str | None = None) -> str:
        hostname = urllib.parse.urlparse(self._client.base_url).hostname
        base = f"https://{hostname}/git/{self._project_key}/{self._repo}"
        if resource == "pr":
            return f"{base}/pullRequests" if number is None else f"{base}/pullRequests/{number}"
        if resource == "issue":
            raise NotSupportedError(
                self.service_name,
                "browse issue (Backlog uses string-format issue keys like PROJ-123)",
            )
        if resource == "release":
            raise NotSupportedError(self.service_name, "browse release")
        if resource == "milestone":
            raise NotSupportedError(self.service_name, "browse milestone")
        if resource == "settings":
            raise NotSupportedError(self.service_name, "browse settings")
        return base

    # --- Search ---

    def search_repositories(self, query: str, *, limit: int = 30) -> list[Repository]:
        results = paginate_offset(
            self._client,
            f"/projects/{self._project_key}/git/repositories",
            limit=0,
        )
        filtered = [r for r in results if query.lower() in r.get("name", "").lower()]
        return [self._to_repository(r) for r in filtered[: limit if limit > 0 else None]]

    def search_issues(self, query: str, *, limit: int = 30) -> list[Issue]:
        project_id = self._ensure_project_id()
        results = paginate_offset(
            self._client,
            "/issues",
            params={"projectId[]": project_id, "keyword": query},
            limit=limit,
        )
        return [self._to_issue(r) for r in results]

    # --- Wiki ---

    def list_wiki_pages(self, *, limit: int = 30) -> list[WikiPage]:
        resp = self._client.get("/wikis", params={"projectIdOrKey": self._project_key})
        pages = resp.json()
        if isinstance(pages, list):
            return [self._to_wiki_page(p) for p in pages[: limit if limit > 0 else None]]
        return []

    def get_wiki_page(self, page_id: int | str) -> WikiPage:
        resp = self._client.get(f"/wikis/{page_id}")
        return self._to_wiki_page(resp.json())

    def create_wiki_page(self, *, title: str, content: str) -> WikiPage:
        project_id = self._ensure_project_id()
        resp = self._client.post(
            "/wikis",
            json={"projectId": project_id, "name": title, "content": content},
        )
        return self._to_wiki_page(resp.json())

    def update_wiki_page(
        self,
        page_id: int | str,
        *,
        title: str | None = None,
        content: str | None = None,
    ) -> WikiPage:
        payload: dict[str, Any] = {}
        if title is not None:
            payload["name"] = title
        if content is not None:
            payload["content"] = content
        resp = self._client.patch(f"/wikis/{page_id}", json=payload)
        return self._to_wiki_page(resp.json())

    def delete_wiki_page(self, page_id: int | str) -> None:
        self._client.delete(f"/wikis/{page_id}")

    # --- Time Tracking ---

    def add_time_entry(self, issue_number: int, duration: int | float) -> TimeEntry:
        hours = round(duration / 3600, 2)
        # 他の issue 操作と同じく issueKey 形式（PROJECT-番号）でアクセスする。
        # 生の番号だと別 issue を更新するか 404 になる。
        issue_key = f"{self._project_key}-{issue_number}"
        # actualHours の PATCH は上書きであり、base の「加算」契約に反する。
        # 現在値を GET してから加算する read-modify-write にする。
        resp = self._client.get(f"/issues/{issue_key}")
        current = resp.json().get("actualHours") or 0
        try:
            new_total = round(float(current) + hours, 2)
        except (TypeError, ValueError):
            new_total = hours
        self._client.patch(f"/issues/{issue_key}", json={"actualHours": new_total})
        return TimeEntry(id=0, user="", duration=int(duration), created_at="")
