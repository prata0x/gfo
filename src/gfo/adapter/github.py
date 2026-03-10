"""GitHub アダプター。GitServiceAdapter の全メソッドを GitHub REST API で実装する。"""

from __future__ import annotations

import base64
from urllib.parse import quote

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
)
from .registry import register


@register("github")
class GitHubAdapter(GitHubLikeAdapter, GitServiceAdapter):
    service_name = "GitHub"

    def _repos_path(self) -> str:
        return f"/repos/{quote(self._owner, safe='')}/{quote(self._repo, safe='')}"

    # --- PR ---

    def list_pull_requests(self, *, state: str = "open", limit: int = 30) -> list[PullRequest]:
        api_state = (
            "closed" if state == "merged" else state
        )  # GitHub API に merged パラメータはなく closed で代用
        params = {"state": api_state}
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/pulls",
            params=params,
            limit=limit,
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
        self._client.put(
            f"{self._repos_path()}/pulls/{number}/merge",
            json={"merge_method": method},
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
        params: dict = {"state": state}
        if assignee is not None:
            params["assignee"] = assignee
        if label is not None:
            params["labels"] = label
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/issues",
            params=params,
            limit=limit,
        )
        return [self._to_issue(r) for r in results if "pull_request" not in r]

    def create_issue(
        self,
        *,
        title: str,
        body: str = "",
        assignee: str | None = None,
        label: str | None = None,
        **kwargs,
    ) -> Issue:
        # **kwargs は base.py の抽象メソッドに合わせて受け取るが、GitHub では使用しない
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

    # --- Repository ---

    def list_repositories(self, *, owner: str | None = None, limit: int = 30) -> list[Repository]:
        if owner is not None:
            path = f"/users/{quote(owner, safe='')}/repos"
        else:
            path = "/user/repos"
        results = paginate_link_header(self._client, path, limit=limit)
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
        results = paginate_link_header(self._client, f"{self._repos_path()}/labels", limit=limit)
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
        self._client.delete(f"{self._repos_path()}/labels/{quote(name, safe='')}")

    # --- Milestone ---

    def list_milestones(self, *, limit: int = 0) -> list[Milestone]:
        results = paginate_link_header(
            self._client, f"{self._repos_path()}/milestones", limit=limit
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
        # resource が "pr" または "issue" のどちらでも /issues/{number}/comments エンドポイントを使う
        # （GitHub では PR コメントは issues/comments と同じ）
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/issues/{number}/comments",
            limit=limit,
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
        if label is not None:
            payload["labels"] = [label]
        resp = self._client.patch(f"{self._repos_path()}/issues/{number}", json=payload)
        return self._to_issue(resp.json())

    # --- Review ---

    def list_reviews(self, number: int) -> list[Review]:
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/pulls/{number}/reviews",
            limit=0,
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
        )
        return [self._to_branch(r) for r in results]

    def create_branch(self, *, name: str, ref: str) -> Branch:
        # ref が SHA でなければまず解決
        sha = ref
        if not (len(ref) == 40 and all(c in "0123456789abcdef" for c in ref)):
            resp = self._client.get(f"{self._repos_path()}/git/ref/heads/{quote(ref, safe='')}")
            sha = resp.json()["object"]["sha"]
        self._client.post(
            f"{self._repos_path()}/git/refs",
            json={"ref": f"refs/heads/{name}", "sha": sha},
        )
        resp = self._client.get(f"{self._repos_path()}/branches/{quote(name, safe='')}")
        return self._to_branch(resp.json())

    def delete_branch(self, *, name: str) -> None:
        self._client.delete(f"{self._repos_path()}/git/refs/heads/{quote(name, safe='')}")

    # --- Tag ---

    def list_tags(self, *, limit: int = 30) -> list[Tag]:
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/tags",
            limit=limit,
        )
        return [self._to_tag(r) for r in results]

    def create_tag(self, *, name: str, ref: str, message: str = "") -> Tag:
        # lightweight tag: ref を直接 refs/tags に push
        sha = ref
        if not (len(ref) == 40 and all(c in "0123456789abcdef" for c in ref)):
            resp = self._client.get(f"{self._repos_path()}/git/ref/heads/{quote(ref, safe='')}")
            sha = resp.json()["object"]["sha"]
        self._client.post(
            f"{self._repos_path()}/git/refs",
            json={"ref": f"refs/tags/{name}", "sha": sha},
        )
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/tags",
            limit=0,
        )
        for t in results:
            if t.get("name") == name:
                return self._to_tag(t)
        from gfo.exceptions import GfoError

        raise GfoError(f"Tag '{name}' not found after creation")

    def delete_tag(self, *, name: str) -> None:
        self._client.delete(f"{self._repos_path()}/git/refs/tags/{quote(name, safe='')}")

    # --- CommitStatus ---

    def list_commit_statuses(self, ref: str, *, limit: int = 30) -> list[CommitStatus]:
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/statuses/{quote(ref, safe='')}",
            limit=limit,
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
    ) -> None:
        payload: dict = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        }
        if sha is not None:
            payload["sha"] = sha
        if branch is not None:
            payload["branch"] = branch
        self._client.put(
            f"{self._repos_path()}/contents/{quote(path, safe='/')}",
            json=payload,
        )

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
        )
        return [self._to_webhook(r) for r in results]

    def create_webhook(self, *, url: str, events: list[str], secret: str | None = None) -> Webhook:
        config: dict = {"url": url, "content_type": "json"}
        if secret is not None:
            config["secret"] = secret
        payload: dict = {"config": config, "events": events, "active": True}
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

    # --- Pipeline (CI = GitHub Actions) ---

    def list_pipelines(self, *, ref: str | None = None, limit: int = 30) -> list[Pipeline]:
        params: dict = {}
        if ref is not None:
            params["branch"] = ref
        # /actions/runs はレスポンスが {"workflow_runs": [...]} 形式のためページネーション手動実装
        results: list[dict] = []
        per_page = min(limit, 30) if limit > 0 else 30
        page = 1
        while True:
            req_params = {**params, "per_page": per_page, "page": page}
            resp = self._client.get(
                f"{self._repos_path()}/actions/runs",
                params=req_params,
            )
            body = resp.json()
            page_data: list[dict] = body.get("workflow_runs", []) if isinstance(body, dict) else []
            if not page_data:
                break
            results.extend(page_data)
            if limit > 0 and len(results) >= limit:
                results = results[:limit]
                break
            if len(page_data) < per_page:
                break
            page += 1
        return [self._to_pipeline(r) for r in results]

    def get_pipeline(self, pipeline_id: int | str) -> Pipeline:
        resp = self._client.get(f"{self._repos_path()}/actions/runs/{pipeline_id}")
        return self._to_pipeline(resp.json())

    def cancel_pipeline(self, pipeline_id: int | str) -> None:
        self._client.post(f"{self._repos_path()}/actions/runs/{pipeline_id}/cancel", json={})

    @staticmethod
    def _to_pipeline(data: dict) -> Pipeline:
        from gfo.exceptions import GfoError

        try:
            status_map = {
                "completed": lambda d: {
                    "success": "success",
                    "failure": "failure",
                    "cancelled": "cancelled",
                }.get(d.get("conclusion") or "", "failure"),
                "in_progress": lambda d: "running",
                "queued": lambda d: "pending",
                "waiting": lambda d: "pending",
            }
            raw_status = data.get("status", "queued")
            mapper = status_map.get(raw_status)
            status = mapper(data) if mapper else raw_status
            return Pipeline(
                id=data["id"],
                status=status,
                ref=data.get("head_branch") or "",
                url=data.get("html_url") or "",
                created_at=data.get("created_at") or "",
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: {e}") from e

    # --- User ---

    def get_current_user(self) -> dict:
        resp = self._client.get("/user")
        return dict(resp.json())

    # --- Search ---

    def search_repositories(self, query: str, *, limit: int = 30) -> list[Repository]:
        # /search/repositories はレスポンスが {"items": [...]} 形式のためページネーション手動実装
        results: list[dict] = []
        per_page = min(limit, 30) if limit > 0 else 30
        page = 1
        while True:
            resp = self._client.get(
                "/search/repositories",
                params={"q": query, "per_page": per_page, "page": page},
            )
            body = resp.json()
            page_data: list[dict] = body.get("items", []) if isinstance(body, dict) else []
            if not page_data:
                break
            results.extend(page_data)
            if limit > 0 and len(results) >= limit:
                results = results[:limit]
                break
            if len(page_data) < per_page:
                break
            page += 1
        return [self._to_repository(r) for r in results]

    def search_issues(self, query: str, *, limit: int = 30) -> list[Issue]:
        # /search/issues はレスポンスが {"items": [...]} 形式のためページネーション手動実装
        results: list[dict] = []
        per_page = min(limit, 30) if limit > 0 else 30
        page = 1
        while True:
            resp = self._client.get(
                "/search/issues",
                params={"q": query, "per_page": per_page, "page": page},
            )
            body = resp.json()
            page_data: list[dict] = body.get("items", []) if isinstance(body, dict) else []
            if not page_data:
                break
            results.extend(page_data)
            if limit > 0 and len(results) >= limit:
                results = results[:limit]
                break
            if len(page_data) < per_page:
                break
            page += 1
        return [self._to_issue(r) for r in results if "pull_request" not in r]
