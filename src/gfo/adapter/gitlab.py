"""GitLab アダプター。GitServiceAdapter の全メソッドを GitLab REST API v4 で実装する。"""

from __future__ import annotations

import base64
from urllib.parse import quote

from gfo.exceptions import GfoError, NotFoundError, NotSupportedError
from gfo.http import paginate_page_param

from .base import (
    Branch,
    BranchProtection,
    CheckRun,
    Comment,
    CommitStatus,
    CompareFile,
    CompareResult,
    DeployKey,
    GitServiceAdapter,
    GpgKey,
    Issue,
    IssueTemplate,
    Label,
    Milestone,
    Notification,
    Organization,
    Pipeline,
    PullRequest,
    PullRequestCommit,
    PullRequestFile,
    Release,
    ReleaseAsset,
    Repository,
    Review,
    Secret,
    SshKey,
    Tag,
    TagProtection,
    Variable,
    Webhook,
    WikiPage,
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

    def reopen_pull_request(self, number: int) -> None:
        self._client.put(
            f"{self._project_path()}/merge_requests/{number}",
            json={"state_event": "reopen"},
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

    def reopen_issue(self, number: int) -> None:
        self._client.put(
            f"{self._project_path()}/issues/{number}",
            json={"state_event": "reopen"},
        )

    def delete_issue(self, number: int) -> None:
        self._client.delete(f"{self._project_path()}/issues/{number}")

    def list_issue_templates(self) -> list[IssueTemplate]:
        try:
            resp = self._client.get(f"{self._project_path()}/templates/issues")
        except Exception:
            return []
        templates: list[IssueTemplate] = []
        for t in resp.json():
            templates.append(
                IssueTemplate(
                    name=t.get("name") or "",
                    title="",
                    body=t.get("content") or "",
                    about=t.get("description") or "",
                    labels=tuple(),
                )
            )
        return templates

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

    def update_repository(self, *, description=None, private=None, default_branch=None):
        payload = {}
        if description is not None:
            payload["description"] = description
        if private is not None:
            payload["visibility"] = "private" if private else "public"
        if default_branch is not None:
            payload["default_branch"] = default_branch
        resp = self._client.put(self._project_path(), json=payload)
        return self._to_repository(resp.json())

    def archive_repository(self):
        self._client.post(f"{self._project_path()}/archive")

    def get_languages(self):
        resp = self._client.get(f"{self._project_path()}/languages")
        return dict(resp.json())

    # --- Topics ---

    def list_topics(self):
        resp = self._client.get(self._project_path())
        return list(resp.json().get("topics", []))

    def set_topics(self, topics):
        resp = self._client.put(self._project_path(), json={"topics": topics})
        return list(resp.json().get("topics", []))

    def add_topic(self, topic):
        current = self.list_topics()
        if topic not in current:
            current.append(topic)
        return self.set_topics(current)

    def remove_topic(self, topic):
        current = self.list_topics()
        if topic in current:
            current.remove(topic)
        return self.set_topics(current)

    # --- Compare ---

    def compare(self, base, head):
        resp = self._client.get(
            f"{self._project_path()}/repository/compare",
            params={"from": base, "to": head},
        )
        data = resp.json()
        commits = data.get("commits") or []
        diffs = data.get("diffs") or []
        files = tuple(
            CompareFile(
                filename=d.get("new_path") or d.get("old_path") or "",
                status="added"
                if d.get("new_file")
                else "deleted"
                if d.get("deleted_file")
                else "renamed"
                if d.get("renamed_file")
                else "modified",
                additions=0,
                deletions=0,
            )
            for d in diffs
        )
        return CompareResult(
            total_commits=len(commits),
            ahead_by=len(commits),
            behind_by=0,
            files=files,
        )

    def migrate_repository(
        self,
        clone_url: str,
        name: str,
        *,
        private: bool = False,
        description: str = "",
        mirror: bool = False,
        auth_token: str | None = None,
    ) -> Repository:
        payload: dict = {
            "name": name,
            "import_url": clone_url,
            "visibility": "private" if private else "public",
        }
        if description:
            payload["description"] = description
        if mirror:
            payload["mirror"] = True
        if auth_token:
            payload["import_url"] = clone_url.replace("://", f"://oauth2:{auth_token}@")
        resp = self._client.post("/projects", json=payload)
        return self._to_repository(resp.json())

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

    def get_release(self, *, tag: str) -> Release:
        resp = self._client.get(f"{self._project_path()}/releases/{quote(tag, safe='')}")
        return self._to_release(resp.json())

    def update_release(
        self,
        *,
        tag: str,
        title: str | None = None,
        notes: str | None = None,
        draft: bool | None = None,
        prerelease: bool | None = None,
    ) -> Release:
        payload: dict = {}
        if title is not None:
            payload["name"] = title
        if notes is not None:
            payload["description"] = notes
        if prerelease is not None:
            payload["upcoming_release"] = prerelease
        # GitLab は draft をサポートしないため無視
        resp = self._client.put(
            f"{self._project_path()}/releases/{quote(tag, safe='')}",
            json=payload,
        )
        return self._to_release(resp.json())

    def get_latest_release(self):
        results = paginate_page_param(
            self._client,
            f"{self._project_path()}/releases",
            limit=1,
        )
        if not results:
            from gfo.exceptions import NotFoundError

            raise NotFoundError()
        return self._to_release(results[0])

    # --- Release Assets ---

    def list_release_assets(self, *, tag):
        results = paginate_page_param(
            self._client,
            f"{self._project_path()}/releases/{quote(tag, safe='')}/assets/links",
            limit=0,
        )
        return [
            ReleaseAsset(
                id=r["id"],
                name=r.get("name") or "",
                size=0,
                download_url=r.get("url") or r.get("direct_asset_url") or "",
                created_at="",
            )
            for r in results
        ]

    def upload_release_asset(self, *, tag, file_path, name=None):
        import os

        fname = name or os.path.basename(file_path)
        # Step 1: Upload to project uploads
        url = f"{self._project_path()}/uploads"
        with open(file_path, "rb") as f:
            files = {"file": (fname, f)}
            upload_resp = self._client._retry_loop(
                lambda: self._client._session.post(
                    self._client.base_url + url,
                    files=files,
                    timeout=300,
                )
            )
        self._client._handle_response(upload_resp)
        upload_data = upload_resp.json()
        file_url = upload_data.get("full_path") or upload_data.get("url") or ""
        if not file_url.startswith("http"):
            file_url = self._client.base_url.rsplit("/api/v4", 1)[0] + file_url
        # Step 2: Create release link
        link_resp = self._client.post(
            f"{self._project_path()}/releases/{quote(tag, safe='')}/assets/links",
            json={"name": fname, "url": file_url},
        )
        link_data = link_resp.json()
        return ReleaseAsset(
            id=link_data["id"],
            name=link_data.get("name") or fname,
            size=0,
            download_url=link_data.get("url") or link_data.get("direct_asset_url") or "",
            created_at="",
        )

    def download_release_asset(self, *, tag, asset_id, output_dir):
        import os

        resp = self._client.get(
            f"{self._project_path()}/releases/{quote(tag, safe='')}/assets/links/{asset_id}"
        )
        data = resp.json()
        url = data.get("direct_asset_url") or data.get("url") or ""
        asset_name = data.get("name") or f"asset-{asset_id}"
        output_path = os.path.join(output_dir, asset_name)
        self._client.download_file(url, output_path)
        return output_path

    def delete_release_asset(self, *, tag, asset_id):
        self._client.delete(
            f"{self._project_path()}/releases/{quote(tag, safe='')}/assets/links/{asset_id}"
        )

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

    def update_label(
        self,
        *,
        name: str,
        new_name: str | None = None,
        color: str | None = None,
        description: str | None = None,
    ) -> Label:
        quoted = quote(name, safe="")
        payload: dict = {}
        if new_name is not None:
            payload["name"] = new_name
        if color is not None:
            payload["color"] = f"#{color.removeprefix('#')}"
        if description is not None:
            payload["description"] = description
        resp = self._client.put(f"{self._project_path()}/labels/{quoted}", json=payload)
        return self._to_label(resp.json())

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

    def _resolve_milestone_id(self, number: int) -> int:
        """iid から GitLab 内部 ID を解決する。"""
        resp = self._client.get(f"{self._project_path()}/milestones", params={"iid[]": number})
        milestones = resp.json()
        if not milestones:
            raise NotFoundError(f"{self._project_path()}/milestones?iid[]={number}")
        return int(milestones[0]["id"])

    def get_milestone(self, number: int) -> Milestone:
        global_id = self._resolve_milestone_id(number)
        resp = self._client.get(f"{self._project_path()}/milestones/{global_id}")
        return self._to_milestone(resp.json())

    def update_milestone(
        self,
        number: int,
        *,
        title: str | None = None,
        description: str | None = None,
        due_date: str | None = None,
        state: str | None = None,
    ) -> Milestone:
        global_id = self._resolve_milestone_id(number)
        payload: dict = {}
        if title is not None:
            payload["title"] = title
        if description is not None:
            payload["description"] = description
        if due_date is not None:
            payload["due_date"] = due_date
        if state is not None:
            state_map = {"closed": "close", "open": "activate"}
            payload["state_event"] = state_map.get(state, state)
        resp = self._client.put(f"{self._project_path()}/milestones/{global_id}", json=payload)
        return self._to_milestone(resp.json())

    # --- 変換ヘルパー（追加分） ---

    @staticmethod
    def _to_comment(data: dict) -> Comment:
        try:
            author = data.get("author") or {}
            return Comment(
                id=data["id"],
                body=data.get("body") or "",
                author=author.get("username") or "",
                url="",  # GitLab notes に html_url なし
                created_at=data.get("created_at") or "",
                updated_at=data.get("updated_at"),
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_review(data: dict) -> Review:
        try:
            state_map = {"approved": "approved", "unapproved": "changes_requested"}
            raw_state = data.get("state", "approved")
            return Review(
                id=data.get("id") or 0,
                state=state_map.get(raw_state, raw_state),
                body="",
                author=(data.get("user") or {}).get("username") or "",
                url="",
                submitted_at=data.get("submitted_at"),
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_branch(data: dict) -> Branch:
        try:
            commit = data.get("commit") or {}
            return Branch(
                name=data["name"],
                sha=commit.get("id") or "",
                protected=data.get("protected", False),
                url=data.get("web_url") or "",
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_tag(data: dict) -> Tag:
        try:
            commit = data.get("commit") or {}
            return Tag(
                name=data["name"],
                sha=commit.get("id") or "",
                message=data.get("message") or "",
                url=data.get("web_url") or "",
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_commit_status(data: dict) -> CommitStatus:
        try:
            state_map = {
                "success": "success",
                "failed": "failure",
                "pending": "pending",
                "running": "pending",
                "canceled": "error",
            }
            raw = data.get("status", "pending")
            return CommitStatus(
                state=state_map.get(raw, raw),
                context=data.get("name") or "",
                description=data.get("description") or "",
                target_url=data.get("target_url") or "",
                created_at=data.get("created_at") or "",
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_webhook(data: dict) -> Webhook:
        try:
            # GitLab webhook の events は boolean フィールド集合
            events = tuple(
                k.replace("_events", "")
                for k in (
                    "push_events",
                    "issues_events",
                    "merge_requests_events",
                    "tag_push_events",
                    "note_events",
                    "confidential_note_events",
                    "job_events",
                    "pipeline_events",
                    "wiki_page_events",
                    "releases_events",
                )
                if data.get(k, False)
            )
            return Webhook(
                id=data["id"],
                url=data.get("url") or "",
                events=events,
                active=data.get("enable_ssl_verification", True),
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
                read_only=not data.get("can_push", False),
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_pipeline(data: dict) -> Pipeline:
        try:
            status_map = {
                "success": "success",
                "failed": "failure",
                "running": "running",
                "pending": "pending",
                "canceled": "cancelled",
                "skipped": "cancelled",
            }
            raw = data.get("status", "pending")
            return Pipeline(
                id=data["id"],
                status=status_map.get(raw, raw),
                ref=data.get("ref") or "",
                url=data.get("web_url") or "",
                created_at=data.get("created_at") or "",
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_wiki_page(data: dict) -> WikiPage:
        try:
            return WikiPage(
                id=0,  # GitLab Wiki には数値IDなし、slugを使う
                title=data.get("title") or "",
                content=data.get("content") or "",
                url=data.get("web_url") or "",
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    # --- Comment ---

    def list_comments(self, resource: str, number: int, *, limit: int = 30) -> list[Comment]:
        if resource == "pr":
            path = f"{self._project_path()}/merge_requests/{number}/notes"
        else:
            path = f"{self._project_path()}/issues/{number}/notes"
        results = paginate_page_param(self._client, path, limit=limit)
        return [self._to_comment(r) for r in results]

    def create_comment(self, resource: str, number: int, *, body: str) -> Comment:
        if resource == "pr":
            path = f"{self._project_path()}/merge_requests/{number}/notes"
        else:
            path = f"{self._project_path()}/issues/{number}/notes"
        resp = self._client.post(path, json={"body": body})
        return self._to_comment(resp.json())

    def update_comment(self, resource: str, comment_id: int, *, body: str) -> Comment:
        raise NotSupportedError(
            self.service_name, "comment update (GitLab requires issue/MR number)"
        )

    def delete_comment(self, resource: str, comment_id: int) -> None:
        raise NotSupportedError(
            self.service_name, "comment delete (GitLab requires issue/MR number)"
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
            payload["target_branch"] = base
        resp = self._client.put(f"{self._project_path()}/merge_requests/{number}", json=payload)
        return self._to_pull_request(resp.json())

    # --- PR diff / checks / files / commits ---

    def get_pull_request_diff(self, number: int) -> str:
        resp = self._client.get(f"{self._project_path()}/merge_requests/{number}/diffs")
        diffs = resp.json()
        parts: list[str] = []
        for d in diffs:
            parts.append(f"--- a/{d['old_path']}\n+++ b/{d['new_path']}")
            parts.append(d.get("diff", ""))
        return "\n".join(parts)

    def list_pull_request_checks(self, number: int) -> list[CheckRun]:
        status_map = {
            "success": "success",
            "failed": "failure",
            "running": "running",
            "pending": "pending",
            "canceled": "cancelled",
            "cancelled": "cancelled",
            "skipped": "skipped",
            "manual": "pending",
            "created": "pending",
        }
        items = paginate_page_param(
            self._client,
            f"{self._project_path()}/merge_requests/{number}/pipelines",
        )
        return [
            CheckRun(
                name=p.get("ref") or str(p["id"]),
                status=status_map.get(p.get("status", ""), p.get("status", "")),
                conclusion=status_map.get(p.get("status", ""), p.get("status", "")),
                url=p.get("web_url", ""),
                started_at=p.get("created_at", ""),
            )
            for p in items
        ]

    def list_pull_request_files(self, number: int) -> list[PullRequestFile]:
        resp = self._client.get(f"{self._project_path()}/merge_requests/{number}/changes")
        changes = resp.json().get("changes", [])
        result: list[PullRequestFile] = []
        for c in changes:
            if c.get("new_file"):
                status = "added"
            elif c.get("deleted_file"):
                status = "deleted"
            elif c.get("renamed_file"):
                status = "renamed"
            else:
                status = "modified"
            diff_text = c.get("diff", "")
            additions = sum(
                1
                for line in diff_text.splitlines()
                if line.startswith("+") and not line.startswith("+++")
            )
            deletions = sum(
                1
                for line in diff_text.splitlines()
                if line.startswith("-") and not line.startswith("---")
            )
            result.append(
                PullRequestFile(
                    filename=c["new_path"],
                    status=status,
                    additions=additions,
                    deletions=deletions,
                )
            )
        return result

    def list_pull_request_commits(self, number: int) -> list[PullRequestCommit]:
        items = paginate_page_param(
            self._client,
            f"{self._project_path()}/merge_requests/{number}/commits",
        )
        return [
            PullRequestCommit(
                sha=c["id"],
                message=c["message"],
                author=c.get("author_name", ""),
                created_at=c.get("created_at", ""),
            )
            for c in items
        ]

    # --- PR reviewers ---

    def list_requested_reviewers(self, number: int) -> list[str]:
        resp = self._client.get(f"{self._project_path()}/merge_requests/{number}")
        reviewers = resp.json().get("reviewers", [])
        return [r["username"] for r in reviewers]

    def _resolve_user_ids(self, usernames: list[str]) -> list[int]:
        """ユーザー名のリストをユーザー ID のリストに変換する。"""
        ids: list[int] = []
        for name in usernames:
            resp = self._client.get("/users", params={"username": name})
            users = resp.json()
            if users:
                ids.append(users[0]["id"])
        return ids

    def request_reviewers(self, number: int, reviewers: list[str]) -> None:
        mr_resp = self._client.get(f"{self._project_path()}/merge_requests/{number}")
        current_ids = [r["id"] for r in mr_resp.json().get("reviewers", [])]
        new_ids = self._resolve_user_ids(reviewers)
        merged = list(dict.fromkeys(current_ids + new_ids))
        self._client.put(
            f"{self._project_path()}/merge_requests/{number}",
            json={"reviewer_ids": merged},
        )

    def remove_reviewers(self, number: int, reviewers: list[str]) -> None:
        mr_resp = self._client.get(f"{self._project_path()}/merge_requests/{number}")
        current_ids = [r["id"] for r in mr_resp.json().get("reviewers", [])]
        remove_ids = set(self._resolve_user_ids(reviewers))
        remaining = [uid for uid in current_ids if uid not in remove_ids]
        self._client.put(
            f"{self._project_path()}/merge_requests/{number}",
            json={"reviewer_ids": remaining},
        )

    # --- PR branch / auto-merge / ready / review dismiss ---

    def update_pull_request_branch(self, number: int) -> None:
        self._client.put(f"{self._project_path()}/merge_requests/{number}/rebase")

    def enable_auto_merge(self, number: int, *, merge_method: str | None = None) -> None:
        payload: dict = {"merge_when_pipeline_succeeds": True}
        if merge_method == "squash":
            payload["squash"] = True
        self._client.put(
            f"{self._project_path()}/merge_requests/{number}/merge",
            json=payload,
        )

    def mark_pull_request_ready(self, number: int) -> None:
        resp = self._client.get(f"{self._project_path()}/merge_requests/{number}")
        title: str = resp.json()["title"]
        for prefix in ("Draft: ", "WIP: "):
            if title.startswith(prefix):
                title = title[len(prefix) :]
                break
        self._client.put(
            f"{self._project_path()}/merge_requests/{number}",
            json={"title": title},
        )

    def dismiss_review(self, number: int, review_id: int, *, message: str = "") -> None:
        raise NotSupportedError(self.service_name, "review dismiss")

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
            payload["description"] = body
        if assignee is not None:
            payload["assignee_username"] = assignee
        if label is not None:
            payload["labels"] = label
        resp = self._client.put(f"{self._project_path()}/issues/{number}", json=payload)
        return self._to_issue(resp.json())

    # --- Review (Approvals) ---

    def list_reviews(self, number: int) -> list[Review]:
        resp = self._client.get(f"{self._project_path()}/merge_requests/{number}/approvals")
        data = resp.json()
        results = []
        for approver in data.get("approved_by") or []:
            user = approver.get("user") or {}
            results.append(
                Review(
                    id=0,
                    state="approved",
                    body="",
                    author=user.get("username") or "",
                    url="",
                )
            )
        return results

    def create_review(self, number: int, *, state: str, body: str = "") -> Review:
        if state.upper() == "APPROVE":
            self._client.post(f"{self._project_path()}/merge_requests/{number}/approve", json={})
            return Review(id=0, state="approved", body=body, author="", url="")
        elif state.upper() == "REQUEST_CHANGES":
            self._client.post(f"{self._project_path()}/merge_requests/{number}/unapprove", json={})
            return Review(id=0, state="changes_requested", body=body, author="", url="")
        else:
            # コメントとして作成
            resp = self._client.post(
                f"{self._project_path()}/merge_requests/{number}/notes",
                json={"body": body},
            )
            note = resp.json()
            return Review(
                id=note.get("id") or 0,
                state="commented",
                body=body,
                author=(note.get("author") or {}).get("username") or "",
                url="",
            )

    # --- Branch ---

    def list_branches(self, *, limit: int = 30) -> list[Branch]:
        results = paginate_page_param(
            self._client,
            f"{self._project_path()}/repository/branches",
            limit=limit,
        )
        return [self._to_branch(r) for r in results]

    def create_branch(self, *, name: str, ref: str) -> Branch:
        resp = self._client.post(
            f"{self._project_path()}/repository/branches",
            json={"branch": name, "ref": ref},
        )
        return self._to_branch(resp.json())

    def delete_branch(self, *, name: str) -> None:
        self._client.delete(f"{self._project_path()}/repository/branches/{quote(name, safe='')}")

    # --- Tag ---

    def list_tags(self, *, limit: int = 30) -> list[Tag]:
        results = paginate_page_param(
            self._client,
            f"{self._project_path()}/repository/tags",
            limit=limit,
        )
        return [self._to_tag(r) for r in results]

    def create_tag(self, *, name: str, ref: str, message: str = "") -> Tag:
        payload: dict = {"tag_name": name, "ref": ref}
        if message:
            payload["message"] = message
        resp = self._client.post(f"{self._project_path()}/repository/tags", json=payload)
        return self._to_tag(resp.json())

    def delete_tag(self, *, name: str) -> None:
        self._client.delete(f"{self._project_path()}/repository/tags/{quote(name, safe='')}")

    # --- CommitStatus ---

    def list_commit_statuses(self, ref: str, *, limit: int = 30) -> list[CommitStatus]:
        results = paginate_page_param(
            self._client,
            f"{self._project_path()}/repository/commits/{quote(ref, safe='')}/statuses",
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
        # GitLab: "success" / "failed" / "pending" / "running" / "canceled"
        state_map = {
            "success": "success",
            "failure": "failed",
            "error": "failed",
            "pending": "pending",
        }
        gl_state = state_map.get(state, state)
        payload: dict = {"state": gl_state}
        if context:
            payload["name"] = context
        if description:
            payload["description"] = description
        if target_url:
            payload["target_url"] = target_url
        resp = self._client.post(
            f"{self._project_path()}/statuses/{quote(ref, safe='')}",
            json=payload,
        )
        return self._to_commit_status(resp.json())

    # --- File ---

    def get_file_content(self, path: str, *, ref: str | None = None) -> tuple[str, str]:
        params: dict = {}
        if ref is not None:
            params["ref"] = ref
        resp = self._client.get(
            f"{self._project_path()}/repository/files/{quote(path, safe='')}",
            params=params,
        )
        data = resp.json()
        try:
            content = base64.b64decode(data["content"]).decode("utf-8")
            sha = data.get("blob_id") or data.get("commit_id") or ""
        except (KeyError, TypeError) as e:
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
            "commit_message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "encoding": "base64",
        }
        if branch is not None:
            payload["branch"] = branch
        encoded_path = quote(path, safe="")
        # sha の有無で create vs update を判定
        if sha is not None:
            self._client.put(
                f"{self._project_path()}/repository/files/{encoded_path}",
                json=payload,
            )
        else:
            self._client.post(
                f"{self._project_path()}/repository/files/{encoded_path}",
                json=payload,
            )
        # GitLab の files API は commit SHA を返さない
        return None

    def delete_file(
        self,
        path: str,
        *,
        sha: str,
        message: str,
        branch: str | None = None,
    ) -> None:
        payload: dict = {"commit_message": message}
        if branch is not None:
            payload["branch"] = branch
        self._client.delete(
            f"{self._project_path()}/repository/files/{quote(path, safe='')}",
            json=payload,
        )

    # --- Fork ---

    def fork_repository(self, *, organization: str | None = None) -> Repository:
        payload: dict = {}
        if organization is not None:
            payload["namespace_path"] = organization
        resp = self._client.post(f"{self._project_path()}/fork", json=payload)
        return self._to_repository(resp.json())

    # --- Webhook ---

    def list_webhooks(self, *, limit: int = 30) -> list[Webhook]:
        results = paginate_page_param(
            self._client,
            f"{self._project_path()}/hooks",
            limit=limit,
        )
        return [self._to_webhook(r) for r in results]

    def create_webhook(self, *, url: str, events: list[str], secret: str | None = None) -> Webhook:
        payload: dict = {"url": url}
        event_map = {
            "push": "push_events",
            "issues": "issues_events",
            "merge_requests": "merge_requests_events",
            "tag_push": "tag_push_events",
            "note": "note_events",
            "pipeline": "pipeline_events",
            "job": "job_events",
        }
        for event in events:
            key = event_map.get(event, f"{event}_events")
            payload[key] = True
        if secret is not None:
            payload["token"] = secret
        resp = self._client.post(f"{self._project_path()}/hooks", json=payload)
        return self._to_webhook(resp.json())

    def delete_webhook(self, *, hook_id: int) -> None:
        self._client.delete(f"{self._project_path()}/hooks/{hook_id}")

    def test_webhook(self, *, hook_id: int) -> None:
        self._client.post(f"{self._project_path()}/hooks/{hook_id}/test/push_events")

    # --- DeployKey ---

    def list_deploy_keys(self, *, limit: int = 30) -> list[DeployKey]:
        results = paginate_page_param(
            self._client,
            f"{self._project_path()}/deploy_keys",
            limit=limit,
        )
        return [self._to_deploy_key(r) for r in results]

    def create_deploy_key(self, *, title: str, key: str, read_only: bool = True) -> DeployKey:
        payload = {"title": title, "key": key, "can_push": not read_only}
        resp = self._client.post(f"{self._project_path()}/deploy_keys", json=payload)
        return self._to_deploy_key(resp.json())

    def delete_deploy_key(self, *, key_id: int) -> None:
        self._client.delete(f"{self._project_path()}/deploy_keys/{key_id}")

    # --- Collaborator ---

    def list_collaborators(self, *, limit: int = 30) -> list[str]:
        results = paginate_page_param(
            self._client,
            f"{self._project_path()}/members",
            limit=limit,
        )
        try:
            return [r["username"] for r in results]
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: {e}") from e

    def add_collaborator(self, *, username: str, permission: str = "write") -> None:
        # GitLab ではまずユーザー ID を取得する
        resp = self._client.get("/users", params={"username": username})
        users = resp.json()
        if not users:
            raise GfoError(f"User '{username}' not found")
        user_id = users[0]["id"]
        access_level_map = {"read": 20, "write": 30, "admin": 40}
        access_level = access_level_map.get(permission, 30)
        self._client.post(
            f"{self._project_path()}/members",
            json={"user_id": user_id, "access_level": access_level},
        )

    def remove_collaborator(self, *, username: str) -> None:
        resp = self._client.get("/users", params={"username": username})
        users = resp.json()
        if not users:
            raise GfoError(f"User '{username}' not found")
        user_id = users[0]["id"]
        self._client.delete(f"{self._project_path()}/members/{user_id}")

    # --- Pipeline ---

    def list_pipelines(self, *, ref: str | None = None, limit: int = 30) -> list[Pipeline]:
        params: dict = {}
        if ref is not None:
            params["ref"] = ref
        results = paginate_page_param(
            self._client,
            f"{self._project_path()}/pipelines",
            params=params,
            limit=limit,
        )
        return [self._to_pipeline(r) for r in results]

    def get_pipeline(self, pipeline_id: int | str) -> Pipeline:
        resp = self._client.get(f"{self._project_path()}/pipelines/{pipeline_id}")
        return self._to_pipeline(resp.json())

    def cancel_pipeline(self, pipeline_id: int | str) -> None:
        self._client.post(f"{self._project_path()}/pipelines/{pipeline_id}/cancel", json={})

    def trigger_pipeline(
        self, ref: str, *, workflow: str | None = None, inputs: dict | None = None
    ) -> Pipeline:
        payload: dict = {"ref": ref}
        if inputs:
            payload["variables"] = [{"key": k, "value": v} for k, v in inputs.items()]
        resp = self._client.post(f"{self._project_path()}/pipeline", json=payload)
        return self._to_pipeline(resp.json())

    def retry_pipeline(self, pipeline_id: int | str) -> Pipeline:
        resp = self._client.post(f"{self._project_path()}/pipelines/{pipeline_id}/retry")
        return self._to_pipeline(resp.json())

    def get_pipeline_logs(self, pipeline_id: int | str, *, job_id: int | str | None = None) -> str:
        if job_id is not None:
            resp = self._client.get(f"{self._project_path()}/jobs/{job_id}/trace")
            return str(resp.text)
        jobs_resp = self._client.get(f"{self._project_path()}/pipelines/{pipeline_id}/jobs")
        logs = []
        for job in jobs_resp.json():
            try:
                resp = self._client.get(f"{self._project_path()}/jobs/{job['id']}/trace")
                logs.append(f"=== {job.get('name', job['id'])} ===\n{resp.text}")
            except Exception:
                logs.append(f"=== {job.get('name', job['id'])} ===\n(log unavailable)")
        return "\n".join(logs)

    # --- User ---

    def get_current_user(self) -> dict:
        resp = self._client.get("/user")
        return dict(resp.json())

    # --- Secret (masked Variable) ---

    def list_secrets(self, *, limit: int = 30) -> list[Secret]:
        results = paginate_page_param(
            self._client, f"{self._project_path()}/variables", limit=limit
        )
        masked = [d for d in results if d.get("masked")]
        return [Secret(name=d["key"], created_at="", updated_at="") for d in masked]

    def set_secret(self, name: str, value: str) -> Secret:
        var = self.set_variable(name, value, masked=True)
        return Secret(name=var.name, created_at=var.created_at, updated_at=var.updated_at)

    def delete_secret(self, name: str) -> None:
        self.delete_variable(name)

    # --- Variable ---

    def list_variables(self, *, limit: int = 30) -> list[Variable]:
        results = paginate_page_param(
            self._client, f"{self._project_path()}/variables", limit=limit
        )
        return [
            Variable(
                name=d["key"],
                value=d.get("value") or "",
                created_at="",
                updated_at="",
            )
            for d in results
        ]

    def set_variable(self, name: str, value: str, *, masked: bool = False) -> Variable:
        payload: dict = {"key": name, "value": value, "masked": masked}
        try:
            self._client.get(f"{self._project_path()}/variables/{quote(name, safe='')}")
            self._client.put(
                f"{self._project_path()}/variables/{quote(name, safe='')}",
                json=payload,
            )
        except NotFoundError:
            self._client.post(f"{self._project_path()}/variables", json=payload)
        return Variable(name=name, value=value, created_at="", updated_at="")

    def get_variable(self, name: str) -> Variable:
        resp = self._client.get(f"{self._project_path()}/variables/{quote(name, safe='')}")
        data = resp.json()
        return Variable(
            name=data["key"],
            value=data.get("value") or "",
            created_at="",
            updated_at="",
        )

    def delete_variable(self, name: str) -> None:
        self._client.delete(f"{self._project_path()}/variables/{quote(name, safe='')}")

    # --- BranchProtection ---

    def list_branch_protections(self, *, limit: int = 30) -> list[BranchProtection]:
        results = paginate_page_param(
            self._client, f"{self._project_path()}/protected_branches", limit=limit
        )
        return [self._to_branch_protection(d) for d in results]

    def get_branch_protection(self, branch: str) -> BranchProtection:
        resp = self._client.get(
            f"{self._project_path()}/protected_branches/{quote(branch, safe='')}"
        )
        return self._to_branch_protection(resp.json())

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
        payload: dict = {"name": branch}
        if allow_force_push is not None:
            payload["allow_force_push"] = allow_force_push
        if require_reviews is not None:
            payload["required_approvals"] = require_reviews
        resp = self._client.post(f"{self._project_path()}/protected_branches", json=payload)
        return self._to_branch_protection(resp.json())

    def remove_branch_protection(self, branch: str) -> None:
        self._client.delete(f"{self._project_path()}/protected_branches/{quote(branch, safe='')}")

    @staticmethod
    def _to_branch_protection(data: dict) -> BranchProtection:
        return BranchProtection(
            branch=data.get("name") or "",
            require_reviews=data.get("required_approvals", 0) or 0,
            require_status_checks=(),
            enforce_admins=False,
            allow_force_push=data.get("allow_force_push", False),
            allow_deletions=False,
        )

    # --- Notification (TODO) ---

    def list_notifications(
        self, *, unread_only: bool = False, limit: int = 30
    ) -> list[Notification]:
        params: dict = {}
        if unread_only:
            params["state"] = "pending"
        results = paginate_page_param(self._client, "/todos", params=params, limit=limit)
        return [self._to_notification(d) for d in results]

    def mark_notification_read(self, notification_id: str) -> None:
        self._client.post(f"/todos/{notification_id}/mark_as_done", json={})

    def mark_all_notifications_read(self) -> None:
        self._client.post("/todos/mark_as_done", json={})

    @staticmethod
    def _to_notification(data: dict) -> Notification:
        try:
            project = data.get("project") or {}
            return Notification(
                id=str(data["id"]),
                title=data.get("body") or "",
                reason=data.get("target_type") or "",
                unread=data.get("state") == "pending",
                repository=project.get("path_with_namespace") or "",
                url=data.get("target_url") or "",
                updated_at=data.get("updated_at") or "",
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    # --- Organization (Group) ---

    def list_organizations(self, *, limit: int = 30) -> list[Organization]:
        results = paginate_page_param(self._client, "/groups", limit=limit)
        return [self._to_organization(d) for d in results]

    def get_organization(self, name: str) -> Organization:
        resp = self._client.get(f"/groups/{quote(name, safe='')}")
        return self._to_organization(resp.json())

    def list_org_members(self, name: str, *, limit: int = 30) -> list[str]:
        results = paginate_page_param(
            self._client, f"/groups/{quote(name, safe='')}/members", limit=limit
        )
        try:
            return [r["username"] for r in results]
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: {e}") from e

    def list_org_repos(self, name: str, *, limit: int = 30) -> list[Repository]:
        results = paginate_page_param(
            self._client, f"/groups/{quote(name, safe='')}/projects", limit=limit
        )
        return [self._to_repository(r) for r in results]

    @staticmethod
    def _to_organization(data: dict) -> Organization:
        try:
            return Organization(
                name=data.get("path") or data.get("full_path") or "",
                display_name=data.get("full_name") or data.get("name") or "",
                description=data.get("description"),
                url=data.get("web_url") or "",
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    def create_organization(
        self, name: str, *, display_name: str | None = None, description: str | None = None
    ) -> Organization:
        payload: dict = {"name": display_name or name, "path": name}
        if description:
            payload["description"] = description
        resp = self._client.post("/groups", json=payload)
        data = resp.json()
        return Organization(
            name=data.get("path") or data["name"],
            display_name=data.get("name") or "",
            description=data.get("description"),
            url=data.get("web_url") or "",
        )

    def delete_organization(self, name: str) -> None:
        self._client.delete(f"/groups/{quote(name, safe='')}")

    # --- SSH Key ---

    def list_ssh_keys(self, *, limit: int = 30) -> list[SshKey]:
        results = paginate_page_param(self._client, "/user/keys", limit=limit)
        return [self._to_ssh_key(d) for d in results]

    def create_ssh_key(self, *, title: str, key: str) -> SshKey:
        resp = self._client.post("/user/keys", json={"title": title, "key": key})
        return self._to_ssh_key(resp.json())

    def delete_ssh_key(self, *, key_id: int | str) -> None:
        self._client.delete(f"/user/keys/{key_id}")

    @staticmethod
    def _to_ssh_key(data: dict) -> SshKey:
        try:
            return SshKey(
                id=data["id"],
                title=data.get("title") or "",
                key=data.get("key") or "",
                created_at=data.get("created_at") or "",
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    # --- GPG Key ---

    def list_gpg_keys(self, *, limit: int = 30) -> list[GpgKey]:
        results = paginate_page_param(self._client, "/user/gpg_keys", limit=limit)
        return [self._to_gpg_key(r) for r in results]

    def create_gpg_key(self, *, armored_key: str) -> GpgKey:
        resp = self._client.post("/user/gpg_keys", json={"key": armored_key})
        return self._to_gpg_key(resp.json())

    def delete_gpg_key(self, *, key_id: int | str) -> None:
        self._client.delete(f"/user/gpg_keys/{key_id}")

    @staticmethod
    def _to_gpg_key(data: dict) -> GpgKey:
        return GpgKey(
            id=data["id"],
            primary_key_id=data.get("primary_key_id") or "",
            public_key=data.get("key") or "",
            emails=tuple(),
            created_at=data.get("created_at") or "",
        )

    # --- Tag Protection ---

    def list_tag_protections(self, *, limit: int = 30) -> list[TagProtection]:
        results = paginate_page_param(
            self._client, f"{self._project_path()}/protected_tags", limit=limit
        )
        return [
            TagProtection(
                id=r["name"],
                pattern=r["name"],
                create_access_level=str(
                    (r.get("create_access_levels") or [{}])[0].get("access_level", "")
                ),
            )
            for r in results
        ]

    def create_tag_protection(
        self, pattern: str, *, create_access_level: str | None = None
    ) -> TagProtection:
        payload: dict = {"name": pattern}
        if create_access_level is not None:
            payload["create_access_level"] = create_access_level
        resp = self._client.post(f"{self._project_path()}/protected_tags", json=payload)
        data = resp.json()
        return TagProtection(
            id=data["name"],
            pattern=data["name"],
            create_access_level=str(
                (data.get("create_access_levels") or [{}])[0].get("access_level", "")
            ),
        )

    def delete_tag_protection(self, protection_id: int | str) -> None:
        self._client.delete(
            f"{self._project_path()}/protected_tags/{quote(str(protection_id), safe='')}"
        )

    # --- Browse ---

    def get_web_url(self, resource: str = "repo", number: int | None = None) -> str:
        # API base_url から Web URL を導出: https://gitlab.com/api/v4 → https://gitlab.com
        from urllib.parse import urlparse

        parsed = urlparse(self._client.base_url)
        web_base = f"{parsed.scheme}://{parsed.hostname}"
        if parsed.port:
            web_base = f"{web_base}:{parsed.port}"
        base = f"{web_base}/{self._owner}/{self._repo}"
        if resource == "pr":
            return f"{base}/-/merge_requests/{number}"
        if resource == "issue":
            return f"{base}/-/issues/{number}"
        if resource == "settings":
            return f"{base}/-/settings/general"
        return base

    # --- Search ---

    def search_repositories(self, query: str, *, limit: int = 30) -> list[Repository]:
        results = paginate_page_param(
            self._client,
            "/projects",
            params={"search": query, "owned": "false", "membership": "false"},
            limit=limit,
        )
        return [self._to_repository(r) for r in results]

    def search_issues(self, query: str, *, limit: int = 30) -> list[Issue]:
        results = paginate_page_param(
            self._client,
            f"{self._project_path()}/issues",
            params={"search": query},
            limit=limit,
        )
        return [self._to_issue(r) for r in results]

    # --- Wiki ---

    def list_wiki_pages(self, *, limit: int = 30) -> list[WikiPage]:
        results = paginate_page_param(
            self._client,
            f"{self._project_path()}/wikis",
            limit=limit,
        )
        return [self._to_wiki_page(r) for r in results]

    def get_wiki_page(self, page_id: int | str) -> WikiPage:
        resp = self._client.get(
            f"{self._project_path()}/wikis/{quote(str(page_id), safe='')}",
            params={"render_html": "false"},
        )
        return self._to_wiki_page(resp.json())

    def create_wiki_page(self, *, title: str, content: str) -> WikiPage:
        resp = self._client.post(
            f"{self._project_path()}/wikis",
            json={"title": title, "content": content},
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
            payload["title"] = title
        if content is not None:
            payload["content"] = content
        resp = self._client.put(
            f"{self._project_path()}/wikis/{quote(str(page_id), safe='')}",
            json=payload,
        )
        return self._to_wiki_page(resp.json())

    def delete_wiki_page(self, page_id: int | str) -> None:
        self._client.delete(f"{self._project_path()}/wikis/{quote(str(page_id), safe='')}")
