"""GitLab アダプター。GitServiceAdapter の全メソッドを GitLab REST API v4 で実装する。"""

from __future__ import annotations

from urllib.parse import quote

from gfo.exceptions import GfoError, NotFoundError
from gfo.http import paginate_page_param

from .base import (
    GitServiceAdapter,
    Issue,
    Label,
    Milestone,
    PullRequest,
    Release,
    Repository,
)
from .registry import register


@register("gitlab")
class GitLabAdapter(GitServiceAdapter):
    service_name = "GitLab"

    def _project_path(self) -> str:
        return f"/projects/{quote(self._owner + '/' + self._repo, safe='')}"

    # --- 変換ヘルパー ---

    @staticmethod
    def _to_pull_request(data: dict) -> PullRequest:
        try:
            state_map = {
                "opened": "open",
                "closed": "closed",
                "merged": "merged",
                "locked": "closed",
            }
            state = state_map.get(data["state"], data["state"])

            return PullRequest(
                number=data["iid"],
                title=data["title"],
                body=data.get("description"),
                state=state,
                author=data["author"]["username"],
                source_branch=data["source_branch"],
                target_branch=data["target_branch"],
                draft=data.get("draft", False),
                url=data["web_url"],
                created_at=data["created_at"],
                updated_at=data.get("updated_at"),
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_issue(data: dict) -> Issue:
        try:
            state = data["state"]
            if state == "opened":
                state = "open"

            return Issue(
                number=data["iid"],
                title=data["title"],
                body=data.get("description"),
                state=state,
                author=data["author"]["username"],
                assignees=[a["username"] for a in data.get("assignees", [])],
                labels=data.get("labels", []),
                url=data["web_url"],
                created_at=data["created_at"],
                updated_at=data.get("updated_at"),
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_repository(data: dict) -> Repository:
        try:
            return Repository(
                name=data["path"],
                full_name=data["path_with_namespace"],
                description=data.get("description"),
                private=data.get("visibility") == "private",
                default_branch=data.get("default_branch"),
                clone_url=data["http_url_to_repo"],
                url=data["web_url"],
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_release(data: dict) -> Release:
        try:
            return Release(
                tag=data["tag_name"],
                title=data.get("name") or "",
                body=data.get("description"),
                draft=False,
                prerelease=data.get("upcoming_release", False),
                url=(data.get("_links") or {}).get("self") or data.get("web_url", ""),
                created_at=data["created_at"],
            )
        except (KeyError, TypeError, AttributeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_label(data: dict) -> Label:
        try:
            color = data.get("color")
            if color and color.startswith("#"):
                color = color[1:]
            return Label(
                name=data["name"],
                color=color,
                description=data.get("description"),
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_milestone(data: dict) -> Milestone:
        try:
            raw_state = data["state"]
            state = "open" if raw_state == "active" else raw_state
            return Milestone(
                number=data["iid"],
                title=data["title"],
                description=data.get("description"),
                state=state,
                due_date=data.get("due_date"),
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    # --- PR (Merge Request) ---

    def list_pull_requests(self, *, state: str = "open", limit: int = 30) -> list[PullRequest]:
        params: dict = {"state": "opened" if state == "open" else state}
        results = paginate_page_param(
            self._client,
            f"{self._project_path()}/merge_requests",
            params=params,
            limit=limit,
        )
        return [self._to_pull_request(r) for r in results]

    def create_pull_request(
        self, *, title: str, body: str = "", base: str, head: str, draft: bool = False
    ) -> PullRequest:
        payload = {
            "title": title,
            "description": body,
            "target_branch": base,
            "source_branch": head,
            "draft": draft,
        }
        resp = self._client.post(f"{self._project_path()}/merge_requests", json=payload)
        return self._to_pull_request(resp.json())

    def get_pull_request(self, number: int) -> PullRequest:
        resp = self._client.get(f"{self._project_path()}/merge_requests/{number}")
        return self._to_pull_request(resp.json())

    def merge_pull_request(self, number: int, *, method: str = "merge") -> None:
        allowed_methods = {"merge", "squash", "rebase"}
        if method not in allowed_methods:
            raise GfoError(f"method must be one of {sorted(allowed_methods)}, got {method!r}")
        if method == "rebase":
            # GitLab rebase は /merge ではなく専用の /rebase エンドポイントを使用
            self._client.put(
                f"{self._project_path()}/merge_requests/{number}/rebase",
                json={},
            )
            return
        payload: dict = {}
        if method == "squash":
            payload["squash"] = True
        # method == "merge" はデフォルト動作（追加 payload なし）
        self._client.put(
            f"{self._project_path()}/merge_requests/{number}/merge",
            json=payload,
        )

    def close_pull_request(self, number: int) -> None:
        self._client.put(
            f"{self._project_path()}/merge_requests/{number}",
            json={"state_event": "close"},
        )

    def get_pr_checkout_refspec(self, number: int, *, pr: PullRequest | None = None) -> str:
        return f"refs/merge-requests/{number}/head"

    # --- Issue ---

    def list_issues(
        self,
        *,
        state: str = "open",
        assignee: str | None = None,
        label: str | None = None,
        limit: int = 30,
    ) -> list[Issue]:
        params: dict = {"state": "opened" if state == "open" else state}
        if assignee is not None:
            params["assignee_username"] = assignee
        if label is not None:
            params["labels"] = label
        results = paginate_page_param(
            self._client,
            f"{self._project_path()}/issues",
            params=params,
            limit=limit,
        )
        return [self._to_issue(r) for r in results]

    def create_issue(
        self,
        *,
        title: str,
        body: str = "",
        assignee: str | None = None,
        label: str | None = None,
        **kwargs,
    ) -> Issue:
        payload: dict = {"title": title, "description": body}
        if assignee is not None:
            payload["assignee_username"] = assignee
        if label is not None:
            payload["labels"] = label
        resp = self._client.post(f"{self._project_path()}/issues", json=payload)
        return self._to_issue(resp.json())

    def get_issue(self, number: int) -> Issue:
        resp = self._client.get(f"{self._project_path()}/issues/{number}")
        return self._to_issue(resp.json())

    def close_issue(self, number: int) -> None:
        self._client.put(
            f"{self._project_path()}/issues/{number}",
            json={"state_event": "close"},
        )

    def delete_issue(self, number: int) -> None:
        self._client.delete(f"{self._project_path()}/issues/{number}")

    # --- Repository ---

    def list_repositories(self, *, owner: str | None = None, limit: int = 30) -> list[Repository]:
        if owner is not None:
            path = f"/users/{quote(owner, safe='')}/projects"
            params: dict = {}
        else:
            path = "/projects"
            params = {"owned": "true", "membership": "true"}
        results = paginate_page_param(self._client, path, params=params, limit=limit)
        return [self._to_repository(r) for r in results]

    def create_repository(
        self, *, name: str, private: bool = False, description: str = ""
    ) -> Repository:
        visibility = "private" if private else "public"
        payload = {"name": name, "visibility": visibility, "description": description}
        resp = self._client.post("/projects", json=payload)
        return self._to_repository(resp.json())

    def get_repository(self, owner: str | None = None, name: str | None = None) -> Repository:
        o = owner if owner is not None else self._owner
        n = name if name is not None else self._repo
        resp = self._client.get(f"/projects/{quote(o + '/' + n, safe='')}")
        return self._to_repository(resp.json())

    def delete_repository(self) -> None:
        self._client.delete(self._project_path())

    # --- Release ---

    def list_releases(self, *, limit: int = 30) -> list[Release]:
        results = paginate_page_param(
            self._client,
            f"{self._project_path()}/releases",
            limit=limit,
        )
        return [self._to_release(r) for r in results]

    def create_release(
        self,
        *,
        tag: str,
        title: str = "",
        notes: str = "",
        draft: bool = False,
        prerelease: bool = False,
    ) -> Release:
        payload: dict = {
            "tag_name": tag,
            "name": title,
            "description": notes,
        }
        if prerelease:
            payload["upcoming_release"] = True
        # GitLab はタグが存在しない場合 ref (ブランチ名等) が必要
        repo = self.get_repository()
        payload["ref"] = repo.default_branch or "main"
        resp = self._client.post(f"{self._project_path()}/releases", json=payload)
        return self._to_release(resp.json())

    def delete_release(self, *, tag: str) -> None:
        self._client.delete(f"{self._project_path()}/releases/{quote(tag, safe='')}")

    # --- Label ---

    def list_labels(self, *, limit: int = 0) -> list[Label]:
        results = paginate_page_param(
            self._client,
            f"{self._project_path()}/labels",
            limit=limit,
        )
        return [self._to_label(r) for r in results]

    def create_label(
        self, *, name: str, color: str | None = None, description: str | None = None
    ) -> Label:
        payload: dict = {"name": name}
        if color is not None:
            payload["color"] = f"#{color.lstrip('#')}"
        if description is not None:
            payload["description"] = description
        resp = self._client.post(f"{self._project_path()}/labels", json=payload)
        return self._to_label(resp.json())

    def delete_label(self, *, name: str) -> None:
        self._client.delete(f"{self._project_path()}/labels/{quote(name, safe='')}")

    # --- Milestone ---

    def list_milestones(self, *, limit: int = 0) -> list[Milestone]:
        results = paginate_page_param(
            self._client,
            f"{self._project_path()}/milestones",
            limit=limit,
        )
        return [self._to_milestone(r) for r in results]

    def create_milestone(
        self, *, title: str, description: str | None = None, due_date: str | None = None
    ) -> Milestone:
        payload: dict = {"title": title}
        if description is not None:
            payload["description"] = description
        if due_date is not None:
            payload["due_date"] = due_date
        resp = self._client.post(f"{self._project_path()}/milestones", json=payload)
        return self._to_milestone(resp.json())

    def delete_milestone(self, *, number: int) -> None:
        # GitLab の DELETE は iid ではなくグローバル id が必要なため、
        # iid (= number) でフィルタしてグローバル id を解決する。
        resp = self._client.get(f"{self._project_path()}/milestones", params={"iid[]": number})
        milestones = resp.json()
        if not milestones:
            raise NotFoundError(f"{self._project_path()}/milestones?iid[]={number}")
        global_id = milestones[0]["id"]
        self._client.delete(f"{self._project_path()}/milestones/{global_id}")
