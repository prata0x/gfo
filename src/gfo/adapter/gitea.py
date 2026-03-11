"""Gitea アダプター。GitServiceAdapter の全メソッドを Gitea REST API v1 で実装する。"""

from __future__ import annotations

import base64
from urllib.parse import quote

from gfo.exceptions import NotFoundError
from gfo.http import paginate_link_header

from .base import (
    Branch,
    Comment,
    CommitStatus,
    DeployKey,
    GitHubLikeAdapter,
    GitServiceAdapter,
    Issue,
    Label,
    Milestone,
    Pipeline,
    PullRequest,
    Release,
    Repository,
    Review,
    Tag,
    Webhook,
    WikiPage,
)
from .registry import register


@register("gitea")
class GiteaAdapter(GitHubLikeAdapter, GitServiceAdapter):
    service_name = "Gitea"

    def _repos_path(self) -> str:
        return f"/repos/{quote(self._owner, safe='')}/{quote(self._repo, safe='')}"

    # --- PR ---

    def list_pull_requests(self, *, state: str = "open", limit: int = 30) -> list[PullRequest]:
        api_state = "closed" if state == "merged" else state
        params = {"state": api_state}
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/pulls",
            params=params,
            limit=limit,
            per_page_key="limit",
        )
        prs = [self._to_pull_request(r) for r in results]
        if state == "merged":
            prs = [pr for pr in prs if pr.state == "merged"]
        return prs

    def create_pull_request(
        self, *, title: str, body: str = "", base: str, head: str, draft: bool = False
    ) -> PullRequest:
        payload = {"title": title, "body": body, "base": base, "head": head, "draft": draft}
        resp = self._client.post(f"{self._repos_path()}/pulls", json=payload)
        return self._to_pull_request(resp.json())

    def get_pull_request(self, number: int) -> PullRequest:
        resp = self._client.get(f"{self._repos_path()}/pulls/{number}")
        return self._to_pull_request(resp.json())

    def merge_pull_request(self, number: int, *, method: str = "merge") -> None:
        self._client.post(
            f"{self._repos_path()}/pulls/{number}/merge",
            json={"Do": method},
        )

    def close_pull_request(self, number: int) -> None:
        self._client.patch(
            f"{self._repos_path()}/pulls/{number}",
            json={"state": "closed"},
        )

    def get_pr_checkout_refspec(self, number: int, *, pr: PullRequest | None = None) -> str:
        return f"refs/pull/{number}/head"

    # --- Issue ---

    def list_issues(
        self,
        *,
        state: str = "open",
        assignee: str | None = None,
        label: str | None = None,
        limit: int = 30,
    ) -> list[Issue]:
        params: dict = {"state": state, "type": "issues"}
        if assignee is not None:
            params["assignee"] = assignee
        if label is not None:
            params["labels"] = label
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/issues",
            params=params,
            limit=limit,
            per_page_key="limit",
        )
        return [self._to_issue(r) for r in results if not r.get("pull_request")]

    def create_issue(
        self,
        *,
        title: str,
        body: str = "",
        assignee: str | None = None,
        label: str | None = None,
        **kwargs,
    ) -> Issue:
        payload: dict = {"title": title, "body": body}
        if assignee is not None:
            payload["assignees"] = [assignee]
        if label is not None:
            payload["labels"] = [label]
        resp = self._client.post(f"{self._repos_path()}/issues", json=payload)
        return self._to_issue(resp.json())

    def get_issue(self, number: int) -> Issue:
        resp = self._client.get(f"{self._repos_path()}/issues/{number}")
        return self._to_issue(resp.json())

    def close_issue(self, number: int) -> None:
        self._client.patch(
            f"{self._repos_path()}/issues/{number}",
            json={"state": "closed"},
        )

    def delete_issue(self, number: int) -> None:
        self._client.delete(f"{self._repos_path()}/issues/{number}")

    # --- Repository ---

    def list_repositories(self, *, owner: str | None = None, limit: int = 30) -> list[Repository]:
        if owner is not None:
            path = f"/users/{quote(owner, safe='')}/repos"
        else:
            path = "/user/repos"
        results = paginate_link_header(self._client, path, limit=limit, per_page_key="limit")
        return [self._to_repository(r) for r in results]

    def create_repository(
        self, *, name: str, private: bool = False, description: str = ""
    ) -> Repository:
        payload = {"name": name, "private": private, "description": description}
        resp = self._client.post("/user/repos", json=payload)
        return self._to_repository(resp.json())

    def get_repository(self, owner: str | None = None, name: str | None = None) -> Repository:
        o = owner if owner is not None else self._owner
        n = name if name is not None else self._repo
        resp = self._client.get(f"/repos/{quote(o, safe='')}/{quote(n, safe='')}")
        return self._to_repository(resp.json())

    def delete_repository(self) -> None:
        self._client.delete(self._repos_path())

    # --- Release ---

    def list_releases(self, *, limit: int = 30) -> list[Release]:
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/releases",
            limit=limit,
            per_page_key="limit",
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
        payload = {
            "tag_name": tag,
            "name": title,
            "body": notes,
            "draft": draft,
            "prerelease": prerelease,
        }
        resp = self._client.post(f"{self._repos_path()}/releases", json=payload)
        return self._to_release(resp.json())

    def delete_release(self, *, tag: str) -> None:
        resp = self._client.get(f"{self._repos_path()}/releases/tags/{quote(tag, safe='')}")
        release_id = resp.json()["id"]
        self._client.delete(f"{self._repos_path()}/releases/{release_id}")

    # --- Label ---

    def list_labels(self, *, limit: int = 0) -> list[Label]:
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/labels",
            per_page_key="limit",
            limit=limit,
        )
        return [self._to_label(r) for r in results]

    def create_label(
        self, *, name: str, color: str | None = None, description: str | None = None
    ) -> Label:
        payload: dict = {"name": name}
        if color is not None:
            payload["color"] = color
        if description is not None:
            payload["description"] = description
        resp = self._client.post(f"{self._repos_path()}/labels", json=payload)
        return self._to_label(resp.json())

    def delete_label(self, *, name: str) -> None:
        resp = self._client.get(f"{self._repos_path()}/labels")
        for label in resp.json():
            if label.get("name") == name:
                self._client.delete(f"{self._repos_path()}/labels/{label['id']}")
                return
        raise NotFoundError()

    # --- Milestone ---

    def list_milestones(self, *, limit: int = 0) -> list[Milestone]:
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/milestones",
            per_page_key="limit",
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
            payload["due_on"] = due_date
        resp = self._client.post(f"{self._repos_path()}/milestones", json=payload)
        return self._to_milestone(resp.json())

    def delete_milestone(self, *, number: int) -> None:
        self._client.delete(f"{self._repos_path()}/milestones/{number}")

    # --- Comment ---

    def list_comments(self, resource: str, number: int, *, limit: int = 30) -> list[Comment]:
        # Gitea も GitHub と同様に issues/comments エンドポイントを使う
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/issues/{number}/comments",
            limit=limit,
            per_page_key="limit",
        )
        return [self._to_comment(r) for r in results]

    def create_comment(self, resource: str, number: int, *, body: str) -> Comment:
        resp = self._client.post(
            f"{self._repos_path()}/issues/{number}/comments",
            json={"body": body},
        )
        return self._to_comment(resp.json())

    def update_comment(self, resource: str, comment_id: int, *, body: str) -> Comment:
        resp = self._client.patch(
            f"{self._repos_path()}/issues/comments/{comment_id}",
            json={"body": body},
        )
        return self._to_comment(resp.json())

    def delete_comment(self, resource: str, comment_id: int) -> None:
        self._client.delete(f"{self._repos_path()}/issues/comments/{comment_id}")

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
            payload["title"] = title
        if body is not None:
            payload["body"] = body
        if base is not None:
            payload["base"] = base
        resp = self._client.patch(f"{self._repos_path()}/pulls/{number}", json=payload)
        return self._to_pull_request(resp.json())

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
            payload["title"] = title
        if body is not None:
            payload["body"] = body
        if assignee is not None:
            payload["assignees"] = [assignee]
        resp = self._client.patch(f"{self._repos_path()}/issues/{number}", json=payload)
        return self._to_issue(resp.json())

    # --- Review ---

    def list_reviews(self, number: int) -> list[Review]:
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/pulls/{number}/reviews",
            limit=0,
            per_page_key="limit",
        )
        return [self._to_review(r) for r in results]

    def create_review(self, number: int, *, state: str, body: str = "") -> Review:
        payload: dict = {"event": state.upper()}
        if body:
            payload["body"] = body
        resp = self._client.post(
            f"{self._repos_path()}/pulls/{number}/reviews",
            json=payload,
        )
        return self._to_review(resp.json())

    # --- Branch ---

    def list_branches(self, *, limit: int = 30) -> list[Branch]:
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/branches",
            limit=limit,
            per_page_key="limit",
        )
        return [self._to_branch(r) for r in results]

    def create_branch(self, *, name: str, ref: str) -> Branch:
        resp = self._client.post(
            f"{self._repos_path()}/branches",
            json={"new_branch_name": name, "old_branch_name": ref},
        )
        return self._to_branch(resp.json())

    def delete_branch(self, *, name: str) -> None:
        self._client.delete(f"{self._repos_path()}/branches/{quote(name, safe='')}")

    # --- Tag ---

    def list_tags(self, *, limit: int = 30) -> list[Tag]:
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/tags",
            limit=limit,
            per_page_key="limit",
        )
        return [self._to_tag(r) for r in results]

    def create_tag(self, *, name: str, ref: str, message: str = "") -> Tag:
        payload: dict = {"tag_name": name, "target": ref}
        if message:
            payload["message"] = message
        resp = self._client.post(f"{self._repos_path()}/tags", json=payload)
        return self._to_tag(resp.json())

    def delete_tag(self, *, name: str) -> None:
        self._client.delete(f"{self._repos_path()}/tags/{quote(name, safe='')}")

    # --- CommitStatus ---

    def list_commit_statuses(self, ref: str, *, limit: int = 30) -> list[CommitStatus]:
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/statuses/{quote(ref, safe='')}",
            limit=limit,
            per_page_key="limit",
        )
        return [self._to_commit_status(r) for r in results]

    def create_commit_status(
        self,
        ref: str,
        *,
        state: str,
        context: str = "",
        description: str = "",
        target_url: str = "",
    ) -> CommitStatus:
        payload: dict = {"state": state}
        if context:
            payload["context"] = context
        if description:
            payload["description"] = description
        if target_url:
            payload["target_url"] = target_url
        resp = self._client.post(
            f"{self._repos_path()}/statuses/{quote(ref, safe='')}",
            json=payload,
        )
        return self._to_commit_status(resp.json())

    # --- File ---

    def get_file_content(self, path: str, *, ref: str | None = None) -> tuple[str, str]:
        params: dict = {}
        if ref is not None:
            params["ref"] = ref
        resp = self._client.get(
            f"{self._repos_path()}/contents/{quote(path, safe='/')}",
            params=params,
        )
        data = resp.json()
        try:
            content = base64.b64decode(data["content"]).decode("utf-8")
            sha = data["sha"]
        except (KeyError, TypeError) as e:
            from gfo.exceptions import GfoError

            raise GfoError(f"Unexpected API response: {e}") from e
        return content, sha

    def create_or_update_file(
        self,
        path: str,
        *,
        content: str,
        message: str,
        sha: str | None = None,
        branch: str | None = None,
    ) -> str | None:
        payload: dict = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        }
        if sha is not None:
            payload["sha"] = sha
        if branch is not None:
            payload["branch"] = branch
        if sha is not None:
            resp = self._client.put(
                f"{self._repos_path()}/contents/{quote(path, safe='/')}",
                json=payload,
            )
        else:
            resp = self._client.post(
                f"{self._repos_path()}/contents/{quote(path, safe='/')}",
                json=payload,
            )
        sha = (resp.json().get("commit") or {}).get("sha")
        return str(sha) if sha else None

    def delete_file(
        self,
        path: str,
        *,
        sha: str,
        message: str,
        branch: str | None = None,
    ) -> None:
        payload: dict = {"message": message, "sha": sha}
        if branch is not None:
            payload["branch"] = branch
        self._client.delete(
            f"{self._repos_path()}/contents/{quote(path, safe='/')}",
            json=payload,
        )

    # --- Fork ---

    def fork_repository(self, *, organization: str | None = None) -> Repository:
        payload: dict = {}
        if organization is not None:
            payload["organization"] = organization
        resp = self._client.post(f"{self._repos_path()}/forks", json=payload)
        return self._to_repository(resp.json())

    # --- Webhook ---

    def list_webhooks(self, *, limit: int = 30) -> list[Webhook]:
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/hooks",
            limit=limit,
            per_page_key="limit",
        )
        return [self._to_webhook(r) for r in results]

    def create_webhook(self, *, url: str, events: list[str], secret: str | None = None) -> Webhook:
        config: dict = {"url": url, "content_type": "json"}
        if secret is not None:
            config["secret"] = secret
        payload: dict = {"config": config, "events": events, "active": True, "type": "gitea"}
        resp = self._client.post(f"{self._repos_path()}/hooks", json=payload)
        return self._to_webhook(resp.json())

    def delete_webhook(self, *, hook_id: int) -> None:
        self._client.delete(f"{self._repos_path()}/hooks/{hook_id}")

    # --- DeployKey ---

    def list_deploy_keys(self, *, limit: int = 30) -> list[DeployKey]:
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/keys",
            limit=limit,
            per_page_key="limit",
        )
        return [self._to_deploy_key(r) for r in results]

    def create_deploy_key(self, *, title: str, key: str, read_only: bool = True) -> DeployKey:
        payload = {"title": title, "key": key, "read_only": read_only}
        resp = self._client.post(f"{self._repos_path()}/keys", json=payload)
        return self._to_deploy_key(resp.json())

    def delete_deploy_key(self, *, key_id: int) -> None:
        self._client.delete(f"{self._repos_path()}/keys/{key_id}")

    # --- Collaborator ---

    def list_collaborators(self, *, limit: int = 30) -> list[str]:
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/collaborators",
            limit=limit,
            per_page_key="limit",
        )
        try:
            return [r["login"] for r in results]
        except (KeyError, TypeError) as e:
            from gfo.exceptions import GfoError

            raise GfoError(f"Unexpected API response: {e}") from e

    def add_collaborator(self, *, username: str, permission: str = "write") -> None:
        self._client.put(
            f"{self._repos_path()}/collaborators/{quote(username, safe='')}",
            json={"permission": permission},
        )

    def remove_collaborator(self, *, username: str) -> None:
        self._client.delete(f"{self._repos_path()}/collaborators/{quote(username, safe='')}")

    # --- Pipeline (Gitea Actions API - 1.19+) ---

    def list_pipelines(self, *, ref: str | None = None, limit: int = 30) -> list[Pipeline]:
        params: dict = {}
        if ref is not None:
            params["branch"] = ref
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/actions/runs",
            params=params,
            limit=limit,
            per_page_key="limit",
        )
        return [self._to_pipeline_data(r) for r in results]

    def get_pipeline(self, pipeline_id: int | str) -> Pipeline:
        resp = self._client.get(f"{self._repos_path()}/actions/runs/{pipeline_id}")
        return self._to_pipeline_data(resp.json())

    def cancel_pipeline(self, pipeline_id: int | str) -> None:
        self._client.post(f"{self._repos_path()}/actions/runs/{pipeline_id}/cancel", json={})

    @staticmethod
    def _to_pipeline_data(data: dict) -> Pipeline:
        from gfo.exceptions import GfoError

        try:
            status_map = {
                "success": "success",
                "failure": "failure",
                "running": "running",
                "waiting": "pending",
                "queued": "pending",
                "cancelled": "cancelled",
            }
            status = status_map.get(data.get("status", "queued"), "pending")
            return Pipeline(
                id=data["id"],
                status=status,
                ref=data.get("head_branch") or "",
                url=data.get("html_url") or "",
                created_at=data.get("created") or "",
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: {e}") from e

    # --- User ---

    def get_current_user(self) -> dict:
        resp = self._client.get("/user")
        return dict(resp.json())

    # --- Search ---

    def search_repositories(self, query: str, *, limit: int = 30) -> list[Repository]:
        results = paginate_link_header(
            self._client,
            "/repos/search",
            params={"q": query},
            limit=limit,
            per_page_key="limit",
        )
        return [self._to_repository(r) for r in results]

    def search_issues(self, query: str, *, limit: int = 30) -> list[Issue]:
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/issues",
            params={"type": "issues", "state": "open", "q": query},
            limit=limit,
            per_page_key="limit",
        )
        return [self._to_issue(r) for r in results if not r.get("pull_request")]

    # --- Wiki ---

    def list_wiki_pages(self, *, limit: int = 30) -> list[WikiPage]:
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/wiki/pages",
            limit=limit,
            per_page_key="limit",
        )
        return [self._to_wiki_page_data(r) for r in results]

    def get_wiki_page(self, page_id: int | str) -> WikiPage:
        resp = self._client.get(f"{self._repos_path()}/wiki/page/{quote(str(page_id), safe='')}")
        return self._to_wiki_page_data(resp.json())

    def create_wiki_page(self, *, title: str, content: str) -> WikiPage:
        # Gitea 1.22+: content は base64 エンコードが必要
        resp = self._client.post(
            f"{self._repos_path()}/wiki/new",
            json={
                "title": title,
                "content_base64": base64.b64encode(content.encode()).decode(),
            },
        )
        return self._to_wiki_page_data(resp.json())

    def update_wiki_page(
        self,
        page_id: int | str,
        *,
        title: str | None = None,
        content: str | None = None,
    ) -> WikiPage:
        # まず現在のページを取得してタイトルを継承
        resp = self._client.get(f"{self._repos_path()}/wiki/page/{quote(str(page_id), safe='')}")
        current = resp.json()
        current_title = title if title is not None else current.get("title", "")
        if content is not None:
            current_content_b64 = base64.b64encode(content.encode()).decode()
        else:
            current_content_b64 = current.get("content_base64") or ""
        payload: dict = {
            "title": current_title,
            "content_base64": current_content_b64,
        }
        resp = self._client.patch(
            f"{self._repos_path()}/wiki/page/{quote(str(page_id), safe='')}",
            json=payload,
        )
        # PATCH レスポンスの content がリクエスト値と一致しない場合（Gitea 1.22 バグ）はリクエスト値で上書き
        result = self._to_wiki_page_data(resp.json())
        if content is not None:
            from dataclasses import replace

            result = replace(result, content=content)
        return result

    def delete_wiki_page(self, page_id: int | str) -> None:
        self._client.delete(f"{self._repos_path()}/wiki/page/{quote(str(page_id), safe='')}")

    @staticmethod
    def _to_wiki_page_data(data: dict) -> WikiPage:
        from gfo.exceptions import GfoError

        try:
            # Gitea 1.22+: content は content_base64（base64エンコード）
            content_b64 = data.get("content_base64") or ""
            if content_b64:
                content = base64.b64decode(content_b64).decode("utf-8", errors="replace")
            else:
                content = data.get("content") or ""
            # sub_url が存在すればそれを id として使用（Gitea 1.22+）
            page_id: int | str = data.get("sub_url") or 0
            return WikiPage(
                id=page_id,
                title=data.get("title") or "",
                content=content,
                url=data.get("html_url") or "",
                updated_at=data.get("last_commit", {}).get("created"),
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: {e}") from e
