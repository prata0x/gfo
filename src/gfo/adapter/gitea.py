"""Gitea アダプター。GitServiceAdapter の全メソッドを Gitea REST API v1 で実装する。"""

from __future__ import annotations

import base64
from urllib.parse import quote

from gfo.exceptions import NotFoundError
from gfo.http import paginate_link_header

from .base import (
    Branch,
    BranchProtection,
    CheckRun,
    Comment,
    CommitStatus,
    CompareFile,
    CompareResult,
    DeployKey,
    GitHubLikeAdapter,
    GitServiceAdapter,
    Issue,
    Label,
    Milestone,
    Notification,
    Organization,
    Pipeline,
    PullRequest,
    PullRequestCommit,
    PullRequestFile,
    Release,
    Repository,
    Review,
    Secret,
    SshKey,
    Tag,
    Variable,
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

    def reopen_pull_request(self, number: int) -> None:
        self._client.patch(
            f"{self._repos_path()}/pulls/{number}",
            json={"state": "open"},
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

    def reopen_issue(self, number: int) -> None:
        self._client.patch(
            f"{self._repos_path()}/issues/{number}",
            json={"state": "open"},
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

    def update_repository(self, *, description=None, private=None, default_branch=None):
        payload = {}
        if description is not None:
            payload["description"] = description
        if private is not None:
            payload["private"] = private
        if default_branch is not None:
            payload["default_branch"] = default_branch
        resp = self._client.patch(self._repos_path(), json=payload)
        return self._to_repository(resp.json())

    def archive_repository(self):
        self._client.patch(self._repos_path(), json={"archived": True})

    def get_languages(self):
        resp = self._client.get(f"{self._repos_path()}/languages")
        return dict(resp.json())

    # --- Topics ---

    def list_topics(self):
        resp = self._client.get(f"{self._repos_path()}/topics")
        return list(resp.json().get("topics") or [])

    def set_topics(self, topics):
        resp = self._client.put(f"{self._repos_path()}/topics", json={"topics": topics})
        return list(resp.json().get("topics") or [])

    def add_topic(self, topic):
        self._client.put(f"{self._repos_path()}/topics/{quote(topic, safe='')}")
        return self.list_topics()

    def remove_topic(self, topic):
        self._client.delete(f"{self._repos_path()}/topics/{quote(topic, safe='')}")
        return self.list_topics()

    # --- Compare ---

    def compare(self, base, head):
        resp = self._client.get(
            f"{self._repos_path()}/compare/{quote(base, safe='')}...{quote(head, safe='')}"
        )
        data = resp.json()
        files = tuple(
            CompareFile(
                filename=f.get("filename", ""),
                status=f.get("status", "modified"),
                additions=f.get("additions", 0),
                deletions=f.get("deletions", 0),
            )
            for f in (data.get("files") or [])
        )
        return CompareResult(
            total_commits=data.get("total_commits", 0),
            ahead_by=data.get("total_commits", 0),
            behind_by=0,
            files=files,
        )

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

    def get_release(self, *, tag: str) -> Release:
        resp = self._client.get(f"{self._repos_path()}/releases/tags/{quote(tag, safe='')}")
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
        resp = self._client.get(f"{self._repos_path()}/releases/tags/{quote(tag, safe='')}")
        release_id = resp.json()["id"]
        payload: dict = {}
        if title is not None:
            payload["name"] = title
        if notes is not None:
            payload["body"] = notes
        if draft is not None:
            payload["draft"] = draft
        if prerelease is not None:
            payload["prerelease"] = prerelease
        resp = self._client.patch(f"{self._repos_path()}/releases/{release_id}", json=payload)
        return self._to_release(resp.json())

    def get_latest_release(self):
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/releases",
            limit=1,
            per_page_key="limit",
        )
        if not results:
            from gfo.exceptions import NotFoundError

            raise NotFoundError()
        return self._to_release(results[0])

    def list_release_assets(self, *, tag):
        resp = self._client.get(f"{self._repos_path()}/releases/tags/{quote(tag, safe='')}")
        assets = resp.json().get("assets") or []
        return [self._to_release_asset(a) for a in assets]

    def upload_release_asset(self, *, tag, file_path, name=None):
        resp = self._client.get(f"{self._repos_path()}/releases/tags/{quote(tag, safe='')}")
        release_id = resp.json()["id"]
        resp = self._client.upload_multipart(
            f"{self._repos_path()}/releases/{release_id}/assets",
            file_path,
            field_name="attachment",
        )
        return self._to_release_asset(resp.json())

    def download_release_asset(self, *, tag, asset_id, output_dir):
        import os

        resp = self._client.get(f"{self._repos_path()}/releases/tags/{quote(tag, safe='')}")
        release_id = resp.json()["id"]
        meta_resp = self._client.get(
            f"{self._repos_path()}/releases/{release_id}/assets/{asset_id}"
        )
        data = meta_resp.json()
        asset_name = data.get("name") or f"asset-{asset_id}"
        output_path = os.path.join(output_dir, asset_name)
        url = (
            data.get("browser_download_url")
            or f"{self._client.base_url}{self._repos_path()}/releases/{release_id}/assets/{asset_id}"
        )
        self._client.download_file(url, output_path)
        return output_path

    def delete_release_asset(self, *, tag, asset_id):
        resp = self._client.get(f"{self._repos_path()}/releases/tags/{quote(tag, safe='')}")
        release_id = resp.json()["id"]
        self._client.delete(f"{self._repos_path()}/releases/{release_id}/assets/{asset_id}")

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

    def update_label(
        self,
        *,
        name: str,
        new_name: str | None = None,
        color: str | None = None,
        description: str | None = None,
    ) -> Label:
        resp = self._client.get(f"{self._repos_path()}/labels")
        label_id = None
        for label in resp.json():
            if label.get("name") == name:
                label_id = label["id"]
                break
        if label_id is None:
            raise NotFoundError()
        payload: dict = {}
        if new_name is not None:
            payload["name"] = new_name
        if color is not None:
            payload["color"] = color.removeprefix("#")
        if description is not None:
            payload["description"] = description
        resp = self._client.patch(f"{self._repos_path()}/labels/{label_id}", json=payload)
        return self._to_label(resp.json())

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

    def get_milestone(self, number: int) -> Milestone:
        resp = self._client.get(f"{self._repos_path()}/milestones/{number}")
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
        payload: dict = {}
        if title is not None:
            payload["title"] = title
        if description is not None:
            payload["description"] = description
        if due_date is not None:
            payload["due_on"] = due_date
        if state is not None:
            payload["state"] = state
        resp = self._client.patch(f"{self._repos_path()}/milestones/{number}", json=payload)
        return self._to_milestone(resp.json())

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

    def get_pull_request_diff(self, number: int) -> str:
        resp = self._client.get(f"{self._repos_path()}/pulls/{number}.diff")
        return str(resp.text)

    def list_pull_request_checks(self, number: int) -> list[CheckRun]:
        resp = self._client.get(f"{self._repos_path()}/pulls/{number}")
        sha = resp.json()["head"]["sha"]
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/statuses/{sha}",
            limit=0,
            per_page_key="limit",
        )
        return [self._to_check_run(r) for r in results]

    def list_pull_request_files(self, number: int) -> list[PullRequestFile]:
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/pulls/{number}/files",
            limit=0,
            per_page_key="limit",
        )
        return [self._to_pull_request_file(r) for r in results]

    def list_pull_request_commits(self, number: int) -> list[PullRequestCommit]:
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/pulls/{number}/commits",
            limit=0,
            per_page_key="limit",
        )
        return [self._to_pull_request_commit(r) for r in results]

    def list_requested_reviewers(self, number: int) -> list[str]:
        resp = self._client.get(f"{self._repos_path()}/pulls/{number}")
        reviewers = resp.json().get("requested_reviewers") or []
        return [r["login"] for r in reviewers]

    def request_reviewers(self, number: int, reviewers: list[str]) -> None:
        self._client.post(
            f"{self._repos_path()}/pulls/{number}/requested_reviewers",
            json={"reviewers": reviewers},
        )

    def remove_reviewers(self, number: int, reviewers: list[str]) -> None:
        self._client.delete(
            f"{self._repos_path()}/pulls/{number}/requested_reviewers",
            json={"reviewers": reviewers},
        )

    def update_pull_request_branch(self, number: int) -> None:
        self._client.post(f"{self._repos_path()}/pulls/{number}/update", json={})

    def enable_auto_merge(self, number: int, *, merge_method: str | None = None) -> None:
        self._client.post(
            f"{self._repos_path()}/pulls/{number}/merge",
            json={"Do": merge_method or "merge", "merge_when_checks_succeed": True},
        )

    def dismiss_review(self, number: int, review_id: int, *, message: str = "") -> None:
        self._client.post(
            f"{self._repos_path()}/pulls/{number}/reviews/{review_id}/dismissals",
            json={"message": message},
        )

    def mark_pull_request_ready(self, number: int) -> None:
        self._client.patch(
            f"{self._repos_path()}/pulls/{number}",
            json={"state": "open"},
        )

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

    def test_webhook(self, *, hook_id: int) -> None:
        self._client.post(f"{self._repos_path()}/hooks/{hook_id}/tests")

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

    # --- Secret ---

    def list_secrets(self, *, limit: int = 30) -> list[Secret]:
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/actions/secrets",
            limit=limit,
            per_page_key="limit",
        )
        return [
            Secret(name=d["name"], created_at=d.get("created_at") or "", updated_at="")
            for d in results
        ]

    def set_secret(self, name: str, value: str) -> Secret:
        self._client.put(
            f"{self._repos_path()}/actions/secrets/{quote(name, safe='')}",
            json={"data": value},
        )
        return Secret(name=name, created_at="", updated_at="")

    def delete_secret(self, name: str) -> None:
        self._client.delete(f"{self._repos_path()}/actions/secrets/{quote(name, safe='')}")

    # --- Variable ---

    def list_variables(self, *, limit: int = 30) -> list[Variable]:
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/actions/variables",
            limit=limit,
            per_page_key="limit",
        )
        return [
            Variable(
                name=d["name"],
                value=d.get("data") or d.get("value") or "",
                created_at="",
                updated_at="",
            )
            for d in results
        ]

    def set_variable(self, name: str, value: str, *, masked: bool = False) -> Variable:
        from gfo.exceptions import NotFoundError

        try:
            self._client.get(f"{self._repos_path()}/actions/variables/{quote(name, safe='')}")
            self._client.put(
                f"{self._repos_path()}/actions/variables/{quote(name, safe='')}",
                json={"name": name, "value": value},
            )
        except NotFoundError:
            self._client.post(
                f"{self._repos_path()}/actions/variables",
                json={"name": name, "value": value},
            )
        return Variable(name=name, value=value, created_at="", updated_at="")

    def get_variable(self, name: str) -> Variable:
        resp = self._client.get(f"{self._repos_path()}/actions/variables/{quote(name, safe='')}")
        data = resp.json()
        return Variable(
            name=data["name"],
            value=data.get("data") or data.get("value") or "",
            created_at="",
            updated_at="",
        )

    def delete_variable(self, name: str) -> None:
        self._client.delete(f"{self._repos_path()}/actions/variables/{quote(name, safe='')}")

    # --- BranchProtection ---

    def list_branch_protections(self, *, limit: int = 30) -> list[BranchProtection]:
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/branch_protections",
            limit=limit,
            per_page_key="limit",
        )
        return [self._to_branch_protection(d) for d in results]

    def get_branch_protection(self, branch: str) -> BranchProtection:
        resp = self._client.get(f"{self._repos_path()}/branch_protections/{quote(branch, safe='')}")
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
        payload: dict = {"branch_name": branch}
        if require_reviews is not None:
            payload["required_approvals"] = require_reviews
        if require_status_checks is not None:
            payload["status_check_contexts"] = require_status_checks
        if allow_force_push is not None:
            payload["enable_force_push"] = allow_force_push
        resp = self._client.post(f"{self._repos_path()}/branch_protections", json=payload)
        return self._to_branch_protection(resp.json())

    def remove_branch_protection(self, branch: str) -> None:
        self._client.delete(f"{self._repos_path()}/branch_protections/{quote(branch, safe='')}")

    @staticmethod
    def _to_branch_protection(data: dict) -> BranchProtection:
        from gfo.exceptions import GfoError

        try:
            return BranchProtection(
                branch=data.get("branch_name") or data.get("rule_name") or "",
                require_reviews=data.get("required_approvals", 0) or 0,
                require_status_checks=tuple(data.get("status_check_contexts") or []),
                enforce_admins=False,
                allow_force_push=data.get("enable_force_push", False),
                allow_deletions=False,
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    # --- Notification ---

    def list_notifications(
        self, *, unread_only: bool = False, limit: int = 30
    ) -> list[Notification]:
        params: dict = {}
        if unread_only:
            params["status-types"] = "unread"
        results = paginate_link_header(
            self._client, "/notifications", params=params, limit=limit, per_page_key="limit"
        )
        return [self._to_notification(d) for d in results]

    def mark_notification_read(self, notification_id: str) -> None:
        self._client.patch(f"/notifications/threads/{notification_id}", json={"status": "read"})

    def mark_all_notifications_read(self) -> None:
        self._client.put("/notifications", json={"status": "read"})

    @staticmethod
    def _to_notification(data: dict) -> Notification:
        from gfo.exceptions import GfoError

        try:
            subject = data.get("subject") or {}
            repo = data.get("repository") or {}
            return Notification(
                id=str(data["id"]),
                title=subject.get("title") or "",
                reason=data.get("reason") or subject.get("type") or "",
                unread=data.get("unread", False),
                repository=repo.get("full_name") or "",
                url=subject.get("html_url") or subject.get("url") or "",
                updated_at=data.get("updated_at") or "",
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    # --- Organization ---

    def list_organizations(self, *, limit: int = 30) -> list[Organization]:
        results = paginate_link_header(
            self._client, "/user/orgs", limit=limit, per_page_key="limit"
        )
        return [self._to_organization(d) for d in results]

    def get_organization(self, name: str) -> Organization:
        resp = self._client.get(f"/orgs/{quote(name, safe='')}")
        return self._to_organization(resp.json())

    def list_org_members(self, name: str, *, limit: int = 30) -> list[str]:
        results = paginate_link_header(
            self._client,
            f"/orgs/{quote(name, safe='')}/members",
            limit=limit,
            per_page_key="limit",
        )
        try:
            return [r["login"] for r in results]
        except (KeyError, TypeError) as e:
            from gfo.exceptions import GfoError

            raise GfoError(f"Unexpected API response: {e}") from e

    def list_org_repos(self, name: str, *, limit: int = 30) -> list[Repository]:
        results = paginate_link_header(
            self._client,
            f"/orgs/{quote(name, safe='')}/repos",
            limit=limit,
            per_page_key="limit",
        )
        return [self._to_repository(r) for r in results]

    def _to_organization(self, data: dict) -> Organization:
        from urllib.parse import urlparse

        from gfo.exceptions import GfoError

        try:
            org_name = data.get("username") or data.get("login") or ""
            parsed = urlparse(self._client.base_url)
            port_str = f":{parsed.port}" if parsed.port else ""
            web_base = f"{parsed.scheme}://{parsed.hostname}{port_str}"
            url = f"{web_base}/{org_name}" if org_name else ""
            return Organization(
                name=org_name,
                display_name=data.get("full_name") or org_name,
                description=data.get("description"),
                url=url,
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    # --- SSH Key ---

    def list_ssh_keys(self, *, limit: int = 30) -> list[SshKey]:
        results = paginate_link_header(
            self._client, "/user/keys", limit=limit, per_page_key="limit"
        )
        return [self._to_ssh_key(d) for d in results]

    def create_ssh_key(self, *, title: str, key: str) -> SshKey:
        resp = self._client.post("/user/keys", json={"title": title, "key": key})
        return self._to_ssh_key(resp.json())

    def delete_ssh_key(self, *, key_id: int | str) -> None:
        self._client.delete(f"/user/keys/{key_id}")

    @staticmethod
    def _to_ssh_key(data: dict) -> SshKey:
        from gfo.exceptions import GfoError

        try:
            return SshKey(
                id=data["id"],
                title=data.get("title") or "",
                key=data.get("key") or "",
                created_at=data.get("created_at") or "",
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    # --- Browse ---

    def get_web_url(self, resource: str = "repo", number: int | None = None) -> str:
        from urllib.parse import urlparse

        parsed = urlparse(self._client.base_url)
        port_str = f":{parsed.port}" if parsed.port else ""
        web_base = f"{parsed.scheme}://{parsed.hostname}{port_str}"
        base = f"{web_base}/{self._owner}/{self._repo}"
        if resource == "pr":
            return f"{base}/pulls/{number}"
        if resource == "issue":
            return f"{base}/issues/{number}"
        if resource == "settings":
            return f"{base}/settings"
        return base

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
