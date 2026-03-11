"""Bitbucket Cloud アダプター。GitServiceAdapter の全メソッドを Bitbucket REST API v2 で実装する。"""  # noqa: E501

from __future__ import annotations

from urllib.parse import quote

from gfo.exceptions import GfoError, NotSupportedError
from gfo.http import paginate_response_body

from .base import (
    Branch,
    Comment,
    CommitStatus,
    DeployKey,
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


@register("bitbucket")
class BitbucketAdapter(GitServiceAdapter):
    service_name = "Bitbucket Cloud"

    def _repos_path(self) -> str:
        return f"/repositories/{quote(self._owner, safe='')}/{quote(self._repo, safe='')}"

    # --- 変換ヘルパー ---

    @staticmethod
    def _to_pull_request(data: dict) -> PullRequest:
        try:
            raw_state = data["state"]
            state_map = {
                "OPEN": "open",
                "DECLINED": "closed",
                "SUPERSEDED": "closed",
                "MERGED": "merged",
            }
            state = state_map.get(raw_state, raw_state.lower())

            return PullRequest(
                number=data["id"],
                title=data["title"],
                body=data.get("description"),
                state=state,
                author=data["author"]["nickname"],
                source_branch=data["source"]["branch"]["name"],
                target_branch=data["destination"]["branch"]["name"],
                draft=False,
                url=data["links"]["html"]["href"],
                created_at=data["created_on"],
                updated_at=data.get("updated_on"),
            )
        except (KeyError, TypeError, AttributeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_issue(data: dict) -> Issue:
        try:
            raw_state = data["state"]
            state = "open" if raw_state in ("new", "open") else "closed"

            assignee = data.get("assignee")
            nickname = assignee.get("nickname") if isinstance(assignee, dict) else None
            assignees = [nickname] if nickname else []

            component = data.get("component")
            labels = (
                [component["name"]] if isinstance(component, dict) and component.get("name") else []
            )

            return Issue(
                number=data["id"],
                title=data["title"],
                body=(data.get("content") or {}).get("raw"),
                state=state,
                author=data["reporter"]["nickname"],
                assignees=assignees,
                labels=labels,
                url=(
                    (data["links"].get("html") or data["links"].get("self") or {}).get("href", "")
                ),
                created_at=data["created_on"],
                updated_at=data.get("updated_on"),
            )
        except (KeyError, TypeError, AttributeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_repository(data: dict) -> Repository:
        try:
            clone_url = ""
            for link in (data.get("links") or {}).get("clone", []):
                if link.get("name") == "https":
                    clone_url = link["href"]
                    break

            return Repository(
                name=data["slug"],
                full_name=data["full_name"],
                description=data.get("description"),
                private=data.get("is_private", False),
                default_branch=data.get("mainbranch", {}).get("name")
                if data.get("mainbranch")
                else None,
                clone_url=clone_url,
                url=data["links"]["html"]["href"],
            )
        except (KeyError, TypeError, AttributeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    # --- PR ---

    def list_pull_requests(self, *, state: str = "open", limit: int = 30) -> list[PullRequest]:
        state_map = {"open": "OPEN", "closed": "DECLINED", "merged": "MERGED"}
        params: dict = {}
        if state != "all":
            params["state"] = state_map.get(state, state.upper())
        results = paginate_response_body(
            self._client,
            f"{self._repos_path()}/pullrequests",
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
            "source": {"branch": {"name": head}},
            "destination": {"branch": {"name": base}},
        }
        resp = self._client.post(f"{self._repos_path()}/pullrequests", json=payload)
        return self._to_pull_request(resp.json())

    def get_pull_request(self, number: int) -> PullRequest:
        resp = self._client.get(f"{self._repos_path()}/pullrequests/{number}")
        return self._to_pull_request(resp.json())

    def merge_pull_request(self, number: int, *, method: str = "merge") -> None:
        _METHOD_MAP = {
            "merge": "merge_commit",
            "squash": "squash",
            "rebase": "fast_forward",
        }
        merge_strategy = _METHOD_MAP.get(method, "merge_commit")
        self._client.post(
            f"{self._repos_path()}/pullrequests/{number}/merge",
            json={"merge_strategy": merge_strategy},
        )

    def close_pull_request(self, number: int) -> None:
        self._client.post(
            f"{self._repos_path()}/pullrequests/{number}/decline",
        )

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
        conditions: list[str] = []
        if state == "open":
            conditions.append('(state="new" OR state="open")')
        elif state == "closed":
            # Bitbucket のクローズ相当の全状態を包含する
            # （resolved / on hold / invalid / duplicate / wontfix / closed）
            conditions.append('(state != "new" AND state != "open")')
        elif state != "all":
            conditions.append(f'state="{state}"')
        if assignee is not None:
            escaped = assignee.replace('"', '\\"')
            conditions.append(f'assignee.nickname="{escaped}"')
        if label is not None:
            escaped_label = label.replace('"', '\\"')
            conditions.append(f'component.name="{escaped_label}"')
        params: dict = {}
        if conditions:
            params["q"] = " AND ".join(conditions)
        results = paginate_response_body(
            self._client,
            f"{self._repos_path()}/issues",
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
        payload: dict = {"title": title, "content": {"raw": body}}
        if assignee is not None:
            payload["assignee"] = {"nickname": assignee}
        if label is not None:
            payload["component"] = {"name": label}
        resp = self._client.post(f"{self._repos_path()}/issues", json=payload)
        return self._to_issue(resp.json())

    def get_issue(self, number: int) -> Issue:
        resp = self._client.get(f"{self._repos_path()}/issues/{number}")
        return self._to_issue(resp.json())

    def close_issue(self, number: int) -> None:
        self._client.put(
            f"{self._repos_path()}/issues/{number}",
            json={"state": "resolved"},
        )

    def delete_issue(self, number: int) -> None:
        self._client.delete(f"{self._repos_path()}/issues/{number}")

    # --- Repository ---

    def list_repositories(self, *, owner: str | None = None, limit: int = 30) -> list[Repository]:
        o = owner if owner is not None else self._owner
        results = paginate_response_body(
            self._client,
            f"/repositories/{quote(o, safe='')}",
            limit=limit,
        )
        return [self._to_repository(r) for r in results]

    def create_repository(
        self, *, name: str, private: bool = False, description: str = ""
    ) -> Repository:
        payload = {"scm": "git", "is_private": private, "description": description}
        resp = self._client.post(
            f"/repositories/{quote(self._owner, safe='')}/{quote(name, safe='')}", json=payload
        )
        return self._to_repository(resp.json())

    def get_repository(self, owner: str | None = None, name: str | None = None) -> Repository:
        o = owner if owner is not None else self._owner
        n = name if name is not None else self._repo
        resp = self._client.get(f"/repositories/{quote(o, safe='')}/{quote(n, safe='')}")
        return self._to_repository(resp.json())

    def delete_repository(self) -> None:
        self._client.delete(self._repos_path())

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

    # --- 変換ヘルパー（拡張） ---

    @staticmethod
    def _to_comment(data: dict) -> Comment:
        from gfo.exceptions import GfoError

        try:
            author = (data.get("user") or {}).get("nickname") or ""
            # content.raw フィールド
            content = data.get("content") or {}
            body = content.get("raw") or ""
            return Comment(
                id=data["id"],
                body=body,
                author=author,
                url=(data.get("links") or {}).get("html", {}).get("href") or "",
                created_at=data.get("created_on") or "",
                updated_at=data.get("updated_on"),
            )
        except (KeyError, TypeError, AttributeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_branch(data: dict) -> Branch:
        from gfo.exceptions import GfoError

        try:
            target = data.get("target") or {}
            return Branch(
                name=data["name"],
                sha=target.get("hash") or "",
                protected=False,
                url=(data.get("links") or {}).get("html", {}).get("href") or "",
            )
        except (KeyError, TypeError, AttributeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_tag(data: dict) -> Tag:
        from gfo.exceptions import GfoError

        try:
            target = data.get("target") or {}
            return Tag(
                name=data["name"],
                sha=target.get("hash") or "",
                message=data.get("message") or "",
                url=(data.get("links") or {}).get("html", {}).get("href") or "",
            )
        except (KeyError, TypeError, AttributeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_commit_status(data: dict) -> CommitStatus:
        from gfo.exceptions import GfoError

        try:
            state_map = {
                "SUCCESSFUL": "success",
                "FAILED": "failure",
                "INPROGRESS": "pending",
                "STOPPED": "error",
            }
            raw = data.get("state", "INPROGRESS")
            return CommitStatus(
                state=state_map.get(raw, raw.lower()),
                context=data.get("key") or "",
                description=data.get("description") or "",
                target_url=data.get("url") or "",
                created_at=data.get("created_on") or "",
            )
        except (KeyError, TypeError, AttributeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_webhook(data: dict) -> Webhook:
        from gfo.exceptions import GfoError

        try:
            events = tuple(data.get("events") or [])
            return Webhook(
                id=data["uuid"].strip("{}") if data.get("uuid") else data.get("id", 0),
                url=data.get("url") or "",
                events=events,
                active=data.get("active", True),
            )
        except (KeyError, TypeError, AttributeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_deploy_key(data: dict) -> DeployKey:
        from gfo.exceptions import GfoError

        try:
            return DeployKey(
                id=data["id"],
                title=data.get("label") or "",
                key=data.get("key") or "",
                read_only=not data.get("can_push", False),  # Bitbucket では read-only がデフォルト
            )
        except (KeyError, TypeError, AttributeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_pipeline(data: dict) -> Pipeline:
        from gfo.exceptions import GfoError

        try:
            state_obj = data.get("state") or {}
            stage = (state_obj.get("stage") or {}).get("name", "")
            result = (state_obj.get("result") or {}).get("name", "")
            status_map = {
                "COMPLETED_SUCCESSFUL": "success",
                "COMPLETED_FAILED": "failure",
                "COMPLETED_ERROR": "failure",
                "COMPLETED_STOPPED": "cancelled",
                "IN_PROGRESS": "running",
                "PENDING": "pending",
            }
            key = f"{stage}_{result}" if result else stage
            status = status_map.get(key, "pending")
            return Pipeline(
                id=data.get("build_number") or data.get("uuid", ""),
                status=status,
                ref=(data.get("target") or {}).get("ref_name") or "",
                url=(data.get("links") or {}).get("self", [{}])[0].get("href")
                if isinstance((data.get("links") or {}).get("self"), list)
                else "",
                created_at=data.get("created_on") or "",
            )
        except (KeyError, TypeError, AttributeError, IndexError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    # --- Comment ---

    def list_comments(self, resource: str, number: int, *, limit: int = 30) -> list[Comment]:
        if resource == "pr":
            path = f"{self._repos_path()}/pullrequests/{number}/comments"
        else:
            path = f"{self._repos_path()}/issues/{number}/comments"
        results = paginate_response_body(self._client, path, limit=limit)
        return [self._to_comment(r) for r in results]

    def create_comment(self, resource: str, number: int, *, body: str) -> Comment:
        if resource == "pr":
            path = f"{self._repos_path()}/pullrequests/{number}/comments"
        else:
            path = f"{self._repos_path()}/issues/{number}/comments"
        payload = {"content": {"raw": body}}
        resp = self._client.post(path, json=payload)
        return self._to_comment(resp.json())

    def update_comment(self, resource: str, comment_id: int, *, body: str) -> Comment:
        # Bitbucket issue/PR comment update には issue_number/PR_number が URL に必要だが
        # このシグネチャでは持てないため NSE
        raise NotSupportedError(
            self.service_name, "comment update (requires issue/PR number in URL)"
        )

    def delete_comment(self, resource: str, comment_id: int) -> None:
        raise NotSupportedError(
            self.service_name, "comment delete (requires issue/PR number in URL)"
        )

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
            payload["description"] = body
        if base is not None:
            payload["destination"] = {"branch": {"name": base}}
        resp = self._client.put(f"{self._repos_path()}/pullrequests/{number}", json=payload)
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
            payload["content"] = {"raw": body}
        if assignee is not None:
            payload["assignee"] = {"nickname": assignee}
        if label is not None:
            payload["component"] = {"name": label}
        resp = self._client.put(f"{self._repos_path()}/issues/{number}", json=payload)
        return self._to_issue(resp.json())

    # --- Review (Bitbucket PR approve) ---

    def list_reviews(self, number: int) -> list[Review]:
        resp = self._client.get(f"{self._repos_path()}/pullrequests/{number}")
        data = resp.json()
        results = []
        for participant in data.get("participants") or []:
            user = participant.get("user") or {}
            approved = participant.get("approved", False)
            if approved:
                results.append(
                    Review(
                        id=0,
                        state="approved",
                        body="",
                        author=user.get("nickname") or "",
                        url="",
                    )
                )
        return results

    def create_review(self, number: int, *, state: str, body: str = "") -> Review:
        if state.upper() == "APPROVE":
            self._client.post(
                f"{self._repos_path()}/pullrequests/{number}/approve",
                json={},
            )
            return Review(id=0, state="approved", body=body, author="", url="")
        elif state.upper() == "REQUEST_CHANGES":
            self._client.post(
                f"{self._repos_path()}/pullrequests/{number}/request-changes",
                json={},
            )
            return Review(id=0, state="changes_requested", body=body, author="", url="")
        else:
            resp = self._client.post(
                f"{self._repos_path()}/pullrequests/{number}/comments",
                json={"content": {"raw": body}},
            )
            comment = resp.json()
            user = (comment.get("user") or {}).get("nickname") or ""
            return Review(
                id=comment.get("id") or 0,
                state="commented",
                body=body,
                author=user,
                url="",
            )

    # --- Branch ---

    def list_branches(self, *, limit: int = 30) -> list[Branch]:
        results = paginate_response_body(
            self._client,
            f"{self._repos_path()}/refs/branches",
            limit=limit,
        )
        return [self._to_branch(r) for r in results]

    def create_branch(self, *, name: str, ref: str) -> Branch:
        payload = {"name": name, "target": {"hash": ref}}
        resp = self._client.post(f"{self._repos_path()}/refs/branches", json=payload)
        return self._to_branch(resp.json())

    def delete_branch(self, *, name: str) -> None:
        self._client.delete(f"{self._repos_path()}/refs/branches/{quote(name, safe='')}")

    # --- Tag ---

    def list_tags(self, *, limit: int = 30) -> list[Tag]:
        results = paginate_response_body(
            self._client,
            f"{self._repos_path()}/refs/tags",
            limit=limit,
        )
        return [self._to_tag(r) for r in results]

    def create_tag(self, *, name: str, ref: str, message: str = "") -> Tag:
        payload: dict = {"name": name, "target": {"hash": ref}}
        if message:
            payload["message"] = message
        resp = self._client.post(f"{self._repos_path()}/refs/tags", json=payload)
        return self._to_tag(resp.json())

    def delete_tag(self, *, name: str) -> None:
        self._client.delete(f"{self._repos_path()}/refs/tags/{quote(name, safe='')}")

    # --- CommitStatus ---

    def list_commit_statuses(self, ref: str, *, limit: int = 30) -> list[CommitStatus]:
        results = paginate_response_body(
            self._client,
            f"{self._repos_path()}/commit/{quote(ref, safe='')}/statuses",
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
        state_map = {
            "success": "SUCCESSFUL",
            "failure": "FAILED",
            "pending": "INPROGRESS",
            "error": "FAILED",
        }
        payload: dict = {
            "state": state_map.get(state, "INPROGRESS"),
            "key": context or "gfo",
            "url": target_url or "https://example.com",  # Bitbucket は url 必須
        }
        if description:
            payload["description"] = description
        resp = self._client.post(
            f"{self._repos_path()}/commit/{quote(ref, safe='')}/statuses/build",
            json=payload,
        )
        return self._to_commit_status(resp.json())

    # --- File (Bitbucket src API) ---

    def get_file_content(self, path: str, *, ref: str | None = None) -> tuple[str, str]:
        ref_part = quote(ref or "HEAD", safe="")
        resp = self._client.get(
            f"{self._repos_path()}/src/{ref_part}/{quote(path, safe='/')}",
        )
        # Bitbucket src API はテキスト直接を返す
        content = resp.text if hasattr(resp, "text") else resp.content.decode("utf-8")
        return content, ""

    def create_or_update_file(
        self,
        path: str,
        *,
        content: str,
        message: str,
        sha: str | None = None,
        branch: str | None = None,
    ) -> str | None:
        # Bitbucket は multipart form data で送信
        data: dict = {path: content, "message": message}
        if branch is not None:
            data["branch"] = branch
        self._client.post(f"{self._repos_path()}/src", data=data)
        # Bitbucket src API は commit SHA を返さない
        return None

    def delete_file(
        self,
        path: str,
        *,
        sha: str,
        message: str,
        branch: str | None = None,
    ) -> None:
        data: dict = {path: "", "message": message}
        if branch is not None:
            data["branch"] = branch
        self._client.post(f"{self._repos_path()}/src", data=data)

    # --- Fork ---

    def fork_repository(self, *, organization: str | None = None) -> Repository:
        payload: dict = {}
        if organization is not None:
            payload["workspace"] = {"slug": organization}
        resp = self._client.post(f"{self._repos_path()}/forks", json=payload)
        return self._to_repository(resp.json())

    # --- Webhook ---

    def list_webhooks(self, *, limit: int = 30) -> list[Webhook]:
        results = paginate_response_body(
            self._client,
            f"{self._repos_path()}/hooks",
            limit=limit,
        )
        return [self._to_webhook(r) for r in results]

    def create_webhook(self, *, url: str, events: list[str], secret: str | None = None) -> Webhook:
        payload: dict = {"url": url, "events": events, "active": True}
        if secret is not None:
            payload["secret_set"] = True
            payload["secret"] = secret
        resp = self._client.post(f"{self._repos_path()}/hooks", json=payload)
        return self._to_webhook(resp.json())

    def delete_webhook(self, *, hook_id: int) -> None:
        self._client.delete(f"{self._repos_path()}/hooks/{hook_id}")

    # --- DeployKey ---

    def list_deploy_keys(self, *, limit: int = 30) -> list[DeployKey]:
        results = paginate_response_body(
            self._client,
            f"{self._repos_path()}/deploy-keys",
            limit=limit,
        )
        return [self._to_deploy_key(r) for r in results]

    def create_deploy_key(self, *, title: str, key: str, read_only: bool = True) -> DeployKey:
        payload = {"label": title, "key": key}
        resp = self._client.post(f"{self._repos_path()}/deploy-keys", json=payload)
        return self._to_deploy_key(resp.json())

    def delete_deploy_key(self, *, key_id: int) -> None:
        self._client.delete(f"{self._repos_path()}/deploy-keys/{key_id}")

    # --- Collaborator ---

    def list_collaborators(self, *, limit: int = 30) -> list[str]:
        # リポジトリレベルのコラボレーター一覧（read:repository:bitbucket スコープで取得可能）
        results = paginate_response_body(
            self._client,
            f"/repositories/{quote(self._owner, safe='')}/{quote(self._repo, safe='')}/permissions-config/users",
            limit=limit,
        )
        try:
            return [
                (r.get("user") or {}).get("nickname") or ""
                for r in results
                if (r.get("user") or {}).get("nickname")
            ]
        except (KeyError, TypeError, AttributeError) as e:
            from gfo.exceptions import GfoError

            raise GfoError(f"Unexpected API response: {e}") from e

    def add_collaborator(self, *, username: str, permission: str = "write") -> None:
        raise NotSupportedError(self.service_name, "collaborator add (use Bitbucket web interface)")

    def remove_collaborator(self, *, username: str) -> None:
        raise NotSupportedError(
            self.service_name, "collaborator remove (use Bitbucket web interface)"
        )

    # --- Pipeline (Bitbucket Pipelines) ---

    def list_pipelines(self, *, ref: str | None = None, limit: int = 30) -> list[Pipeline]:
        params: dict = {}
        if ref is not None:
            params["target.ref_name"] = ref
        results = paginate_response_body(
            self._client,
            f"{self._repos_path()}/pipelines",
            params=params,
            limit=limit,
        )
        return [self._to_pipeline(r) for r in results]

    def get_pipeline(self, pipeline_id: int | str) -> Pipeline:
        resp = self._client.get(f"{self._repos_path()}/pipelines/{pipeline_id}")
        return self._to_pipeline(resp.json())

    def cancel_pipeline(self, pipeline_id: int | str) -> None:
        self._client.post(
            f"{self._repos_path()}/pipelines/{pipeline_id}/stopPipeline",
            json={},
        )

    # --- User ---

    def get_current_user(self) -> dict:
        resp = self._client.get("/user")
        return dict(resp.json())

    # --- Search ---

    def search_repositories(self, query: str, *, limit: int = 30) -> list[Repository]:
        results = paginate_response_body(
            self._client,
            f"/repositories/{quote(self._owner, safe='')}",
            params={"q": f'name ~ "{query}"'},
            limit=limit,
        )
        return [self._to_repository(r) for r in results]

    def search_issues(self, query: str, *, limit: int = 30) -> list[Issue]:
        results = paginate_response_body(
            self._client,
            f"{self._repos_path()}/issues",
            params={"q": f'title ~ "{query}"'},
            limit=limit,
        )
        return [self._to_issue(r) for r in results]
