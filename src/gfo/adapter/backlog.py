"""Backlog アダプター。GitServiceAdapter の全メソッドを Backlog REST API v2 で実装する。"""

from __future__ import annotations

import urllib.parse

from gfo.exceptions import GfoError, NotSupportedError
from gfo.http import paginate_offset

from .base import (
    Branch,
    Comment,
    GitServiceAdapter,
    Issue,
    Label,
    Milestone,
    PullRequest,
    Release,
    Repository,
    Tag,
    Webhook,
    WikiPage,
)
from .registry import register

# Backlog PR / Issue ステータス ID 定数
_STATUS_OPEN_IDS = [1, 2, 3]  # open / in-progress / resolved (open 扱い)
_STATUS_CLOSED_ID = 4  # closed
_STATUS_MERGED_ID = 5  # merged（PR 固定値; カスタムの場合は動的解決で上書き）


@register("backlog")
class BacklogAdapter(GitServiceAdapter):
    service_name = "Backlog"

    def __init__(self, client, owner: str, repo: str, *, project_key: str, **kwargs):
        super().__init__(client, owner, repo, **kwargs)
        self._project_key = project_key
        self._project_id: int | None = None
        self._merged_status_id: int | None = None

    def _pr_path(self) -> str:
        return f"/projects/{self._project_key}/git/repositories/{urllib.parse.quote(self._repo, safe='')}/pullRequests"

    def _ensure_project_id(self) -> int:
        """プロジェクト ID を取得してキャッシュする。"""
        if self._project_id is None:
            resp = self._client.get(f"/projects/{self._project_key}")
            try:
                self._project_id = resp.json()["id"]
            except (KeyError, TypeError) as e:
                raise GfoError(f"Unexpected API response from project endpoint: {e}") from e
        return self._project_id

    def _resolve_merged_status_id(self) -> int | None:
        """PR ステータス一覧から Merged 相当の statusId を動的に判定する。"""
        if self._merged_status_id is not None:
            return self._merged_status_id
        resp = self._client.get(f"/projects/{self._project_key}/statuses")
        statuses = resp.json()
        if not isinstance(statuses, list):
            raise GfoError(f"Unexpected API response from statuses endpoint: {type(statuses)}")
        for status in statuses:
            try:
                if "merged" in status["name"].lower():
                    self._merged_status_id = status["id"]
                    return self._merged_status_id
            except (KeyError, TypeError, AttributeError):
                continue
        return None

    # --- 変換ヘルパー ---

    @staticmethod
    def _to_pull_request(data: dict, merged_status_id: int | None = None) -> PullRequest:
        try:
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
        except (KeyError, TypeError, AttributeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_issue(data: dict) -> Issue:
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
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_repository(data: dict) -> Repository:
        try:
            return Repository(
                name=data["name"],
                full_name=data.get("displayName", data["name"]),
                description=data.get("description"),
                private=True,
                default_branch=None,
                clone_url=data.get("httpUrl", ""),
                url=data.get("httpUrl", "").removesuffix(".git"),
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    # --- PR ---

    def list_pull_requests(self, *, state: str = "open", limit: int = 30) -> list[PullRequest]:
        params: dict = {}
        merged_id: int | None = None
        if state == "merged":
            merged_id = self._resolve_merged_status_id()
            if merged_id is not None:
                params["statusId[]"] = [merged_id]
        elif state == "open":
            params["statusId[]"] = _STATUS_OPEN_IDS
        elif state == "closed":
            params["statusId[]"] = [_STATUS_CLOSED_ID]
        else:
            # state="all": 動的 merged_status_id が必要
            merged_id = self._resolve_merged_status_id()
        results = paginate_offset(self._client, self._pr_path(), params=params, limit=limit)
        return [self._to_pull_request(r, merged_id) for r in results]

    def create_pull_request(
        self, *, title: str, body: str = "", base: str, head: str, draft: bool = False
    ) -> PullRequest:
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

    def merge_pull_request(self, number: int, *, method: str = "merge") -> None:
        hostname = urllib.parse.urlparse(self._client.base_url).hostname
        raise NotSupportedError(
            "Backlog",
            "pull request merge",
            web_url=f"https://{hostname}/git/{self._project_key}/{self._repo}/pullRequests/{number}",
        )

    def close_pull_request(self, number: int) -> None:
        self._client.patch(f"{self._pr_path()}/{number}", json={"statusId": _STATUS_CLOSED_ID})

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
    ) -> list[Issue]:
        project_id = self._ensure_project_id()
        params: dict = {"projectId[]": project_id}
        if state == "open":
            params["statusId[]"] = _STATUS_OPEN_IDS
        elif state == "closed":
            params["statusId[]"] = [_STATUS_CLOSED_ID]
        if assignee:
            params["assigneeUserId[]"] = assignee
        if label:
            params["keyword"] = label
        results = paginate_offset(self._client, "/issues", params=params, limit=limit)
        return [self._to_issue(r) for r in results]

    def create_issue(
        self,
        *,
        title: str,
        body: str = "",
        assignee: str | None = None,
        label: str | None = None,
        issue_type: int | None = None,
        priority: int | None = None,
        **kwargs,
    ) -> Issue:
        project_id = self._ensure_project_id()

        if issue_type is None:
            resp = self._client.get(f"/projects/{self._project_key}/issueTypes")
            types = resp.json()
            if not isinstance(types, list):
                raise GfoError(f"Unexpected API response from issueTypes endpoint: {type(types)}")
            try:
                issue_type = types[0]["id"] if types else None
            except (KeyError, TypeError) as e:
                raise GfoError(f"Unexpected API response from issueTypes endpoint: {e}") from e

        if priority is None:
            resp = self._client.get("/priorities")
            priorities = resp.json()
            if not isinstance(priorities, list):
                raise GfoError(
                    f"Unexpected API response from priorities endpoint: {type(priorities)}"
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
                raise GfoError(f"Unexpected API response from priorities endpoint: {e}") from e

        if issue_type is None:
            raise GfoError(
                "Cannot create issue: no issue types found for project "
                f"'{self._project_key}'. Configure issue types in Backlog."
            )
        if priority is None:
            raise GfoError(
                "Cannot create issue: no priorities found. Configure priorities in Backlog."
            )

        payload: dict = {
            "projectId": project_id,
            "summary": title,
            "issueTypeId": issue_type,
            "priorityId": priority,
        }
        if body:
            payload["description"] = body
        if assignee:
            payload["assigneeUserId"] = assignee

        resp = self._client.post("/issues", json=payload)
        return self._to_issue(resp.json())

    def get_issue(self, number: int) -> Issue:
        resp = self._client.get(f"/issues/{self._project_key}-{number}")
        return self._to_issue(resp.json())

    def close_issue(self, number: int) -> None:
        self._client.patch(
            f"/issues/{self._project_key}-{number}", json={"statusId": _STATUS_CLOSED_ID}
        )

    def delete_issue(self, number: int) -> None:
        self._client.delete(f"/issues/{self._project_key}-{number}")

    # --- Repository ---

    def list_repositories(self, *, owner: str | None = None, limit: int = 30) -> list[Repository]:
        if owner is not None:
            raise NotSupportedError(
                self.service_name,
                "filtering repositories by owner "
                "(repositories are scoped to the configured project)",
            )
        results = paginate_offset(
            self._client,
            f"/projects/{self._project_key}/git/repositories",
            limit=limit,
        )
        return [self._to_repository(r) for r in results]

    def create_repository(
        self, *, name: str, private: bool = False, description: str = ""
    ) -> Repository:
        payload: dict = {"name": name}
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
    ) -> Release:
        raise NotSupportedError(self.service_name, "releases")

    def list_labels(self, *, limit: int = 0) -> list[Label]:
        raise NotSupportedError(self.service_name, "labels")

    def create_label(
        self, *, name: str, color: str | None = None, description: str | None = None
    ) -> Label:
        raise NotSupportedError(self.service_name, "labels")

    def list_milestones(self, *, limit: int = 0) -> list[Milestone]:
        raise NotSupportedError(self.service_name, "milestones")

    def create_milestone(
        self, *, title: str, description: str | None = None, due_date: str | None = None
    ) -> Milestone:
        raise NotSupportedError(self.service_name, "milestones")

    # --- 変換ヘルパー（Comment / Branch / Tag / Webhook / WikiPage）---

    @staticmethod
    def _to_comment(data: dict) -> Comment:
        from gfo.exceptions import GfoError

        try:
            created_user = data.get("createdUser") or {}
            return Comment(
                id=data["id"],
                body=data.get("content") or "",
                author=created_user.get("userId") or "",
                url="",
                created_at=data.get("created") or "",
                updated_at=data.get("updated"),
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_branch(data: dict) -> Branch:
        from gfo.exceptions import GfoError

        try:
            return Branch(
                name=data["name"],
                sha=data.get("commit", {}).get("id") or "",
                protected=False,
                url="",
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_tag(data: dict) -> Tag:
        from gfo.exceptions import GfoError

        try:
            return Tag(
                name=data["name"],
                sha=data.get("commit", {}).get("id") or "",
                message="",
                url="",
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_webhook(data: dict) -> Webhook:
        from gfo.exceptions import GfoError

        try:
            # Backlog webhook の allEvent または events フィールド
            events = tuple(data.get("events") or [])
            return Webhook(
                id=data["id"],
                url=(data.get("hookUrl") or ""),
                events=events,
                active=True,
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_wiki_page(data: dict) -> WikiPage:
        from gfo.exceptions import GfoError

        try:
            return WikiPage(
                id=data["id"],
                title=data.get("name") or "",
                content=data.get("content") or "",
                url="",
                updated_at=data.get("updated"),
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

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
    ) -> PullRequest:
        payload: dict = {}
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
    ) -> Issue:
        payload: dict = {}
        if title is not None:
            payload["summary"] = title
        if body is not None:
            payload["description"] = body
        if assignee is not None:
            payload["assigneeUserId"] = assignee
        resp = self._client.patch(f"/issues/{self._project_key}-{number}", json=payload)
        return self._to_issue(resp.json())

    # --- Branch ---

    def list_branches(self, *, limit: int = 30) -> list[Branch]:
        results = paginate_offset(
            self._client,
            f"/projects/{self._project_key}/git/repositories/{urllib.parse.quote(self._repo, safe='')}/branches",
            limit=limit,
        )
        return [self._to_branch(r) for r in results]

    def create_branch(self, *, name: str, ref: str) -> Branch:
        resp = self._client.post(
            f"/projects/{self._project_key}/git/repositories/{urllib.parse.quote(self._repo, safe='')}/branches",
            json={"name": name, "startPoint": ref},
        )
        return self._to_branch(resp.json())

    def delete_branch(self, *, name: str) -> None:
        self._client.delete(
            f"/projects/{self._project_key}/git/repositories/{urllib.parse.quote(self._repo, safe='')}/branches/{urllib.parse.quote(name, safe='')}"
        )

    # --- Tag ---

    def list_tags(self, *, limit: int = 30) -> list[Tag]:
        results = paginate_offset(
            self._client,
            f"/projects/{self._project_key}/git/repositories/{urllib.parse.quote(self._repo, safe='')}/tags",
            limit=limit,
        )
        return [self._to_tag(r) for r in results]

    def create_tag(self, *, name: str, ref: str, message: str = "") -> Tag:
        payload: dict = {"name": name, "startPoint": ref}
        if message:
            payload["message"] = message
        resp = self._client.post(
            f"/projects/{self._project_key}/git/repositories/{urllib.parse.quote(self._repo, safe='')}/tags",
            json=payload,
        )
        return self._to_tag(resp.json())

    # --- Webhook ---

    def list_webhooks(self, *, limit: int = 30) -> list[Webhook]:
        resp = self._client.get(f"/projects/{self._project_key}/webhooks")
        hooks = resp.json()
        if isinstance(hooks, list):
            return [self._to_webhook(h) for h in hooks[: limit if limit > 0 else None]]
        return []

    def create_webhook(self, *, url: str, events: list[str], secret: str | None = None) -> Webhook:
        payload: dict = {"hookUrl": url, "allEvent": True if not events else False}
        if events:
            payload["events"] = [{"type": e} for e in events]
        if secret is not None:
            payload["secret"] = secret
        resp = self._client.post(f"/projects/{self._project_key}/webhooks", json=payload)
        return self._to_webhook(resp.json())

    def delete_webhook(self, *, hook_id: int) -> None:
        self._client.delete(f"/projects/{self._project_key}/webhooks/{hook_id}")

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
                from gfo.exceptions import GfoError

                raise GfoError(f"Unexpected API response: {e}") from e
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

    def get_current_user(self) -> dict:
        resp = self._client.get("/users/myself")
        return dict(resp.json())

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
        payload: dict = {}
        if title is not None:
            payload["name"] = title
        if content is not None:
            payload["content"] = content
        resp = self._client.patch(f"/wikis/{page_id}", json=payload)
        return self._to_wiki_page(resp.json())

    def delete_wiki_page(self, page_id: int | str) -> None:
        self._client.delete(f"/wikis/{page_id}")
