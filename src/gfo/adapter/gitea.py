"""Gitea アダプター。GitServiceAdapter の全メソッドを Gitea REST API v1 で実装する。"""

from __future__ import annotations

import base64
from urllib.parse import quote

import requests

from gfo.exceptions import GfoError, NotFoundError
from gfo.http import paginate_link_header

from .base import (
    Artifact,
    Branch,
    BranchProtection,
    CheckRun,
    Comment,
    Commit,
    CommitStatus,
    CompareFile,
    CompareResult,
    DeployKey,
    GitHubLikeAdapter,
    GitServiceAdapter,
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
from .registry import register


@register("gitea")
class GiteaAdapter(GitHubLikeAdapter, GitServiceAdapter):
    service_name = "Gitea"

    def _repos_path(self) -> str:
        return f"/repos/{quote(self._owner, safe='')}/{quote(self._repo, safe='')}"

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
    ) -> list[PullRequest]:
        self._warn_unsupported_params("pr list", draft=draft)
        api_state = "closed" if state == "merged" else state
        params: dict = {"state": api_state}
        if author:
            params["poster"] = author
        if label:
            params["labels"] = label
        if assignee:
            params["assignee"] = assignee
        if search:
            params["q"] = search
        if base:
            params["base"] = base
        if head:
            params["head"] = head
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
        payload: dict = {"title": title, "body": body, "base": base, "head": head, "draft": draft}
        if assignees:
            payload["assignees"] = assignees
        if labels:
            payload["labels"] = self._resolve_label_ids(labels)
        if milestone:
            payload["milestone"] = self._resolve_milestone_id_by_title(milestone)
        resp = self._client.post(f"{self._repos_path()}/pulls", json=payload)
        pr = self._to_pull_request(resp.json())
        if reviewers:
            self.request_reviewers(pr.number, reviewers)
        return pr

    def _resolve_label_ids(self, names: list[str]) -> list[int]:
        """ラベル名のリストを ID のリストに変換する。"""
        resp = self._client.get(f"{self._repos_path()}/labels", params={"limit": 0})
        all_labels = resp.json()
        name_to_id = {lb["name"]: lb["id"] for lb in all_labels}
        ids = []
        for name in names:
            if name in name_to_id:
                ids.append(name_to_id[name])
            else:
                raise GfoError(f"Label not found: {name}")
        return ids

    def _resolve_milestone_id_by_title(self, title: str) -> int:
        """milestone タイトルから ID を解決する。"""
        for ms in self.list_milestones():
            if ms.title == title:
                return ms.number
        raise GfoError(f"Milestone not found: {title}")

    def get_pull_request(self, number: int) -> PullRequest:
        resp = self._client.get(f"{self._repos_path()}/pulls/{number}")
        return self._to_pull_request(resp.json())

    def merge_pull_request(
        self,
        number: int,
        *,
        method: str = "merge",
        title: str | None = None,
        message: str | None = None,
    ) -> None:
        payload: dict = {"Do": method}
        if title is not None:
            payload["MergeTitleField"] = title
        if message is not None:
            payload["MergeMessageField"] = message
        self._client.post(
            f"{self._repos_path()}/pulls/{number}/merge",
            json=payload,
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

    def lock_pull_request(self, number: int, *, reason: str | None = None) -> None:
        self.lock_issue(number, reason=reason)

    def unlock_pull_request(self, number: int) -> None:
        self.unlock_issue(number)

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
        author: str | None = None,
        milestone: str | None = None,
        search: str | None = None,
    ) -> list[Issue]:
        params: dict = {"state": state, "type": "issues"}
        if assignee is not None:
            params["assignee"] = assignee
        if label is not None:
            params["labels"] = label
        if author is not None:
            params["created_by"] = author
        if milestone is not None:
            params["milestones"] = milestone
        if search is not None:
            params["q"] = search
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
        milestone: str | None = None,
        **kwargs,
    ) -> Issue:
        payload: dict = {"title": title, "body": body}
        if assignee is not None:
            payload["assignees"] = [assignee]
        if label is not None:
            payload["labels"] = [label]
        if milestone is not None:
            payload["milestone"] = self._resolve_milestone_id_by_title(milestone)
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

    def list_issue_templates(self) -> list[IssueTemplate]:
        try:
            resp = self._client.get(f"{self._repos_path()}/issue_templates")
        except (GfoError, requests.RequestException, KeyError, ValueError):
            return []
        templates: list[IssueTemplate] = []
        for t in resp.json() or []:
            templates.append(
                IssueTemplate(
                    name=t.get("name") or "",
                    title=t.get("title") or "",
                    body=t.get("content") or t.get("body") or "",
                    about=t.get("about") or "",
                    labels=tuple(t.get("labels") or []),
                )
            )
        return templates

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

    def update_repository(
        self,
        *,
        name: str | None = None,
        description: str | None = None,
        private: bool | None = None,
        default_branch: str | None = None,
    ) -> Repository:
        payload: dict = {}
        if name is not None:
            payload["name"] = name
        if description is not None:
            payload["description"] = description
        if private is not None:
            payload["private"] = private
        if default_branch is not None:
            payload["default_branch"] = default_branch
        resp = self._client.patch(self._repos_path(), json=payload)
        return self._to_repository(resp.json())

    def archive_repository(self) -> None:
        self._client.patch(self._repos_path(), json={"archived": True})

    def get_languages(self) -> dict[str, int | float]:
        resp = self._client.get(f"{self._repos_path()}/languages")
        return dict(resp.json())

    # --- Topics ---

    def list_topics(self) -> list[str]:
        resp = self._client.get(f"{self._repos_path()}/topics")
        return list(resp.json().get("topics") or [])

    def set_topics(self, topics: list[str]) -> list[str]:
        resp = self._client.put(f"{self._repos_path()}/topics", json={"topics": topics})
        return list(resp.json().get("topics") or [])

    def add_topic(self, topic: str) -> list[str]:
        self._client.put(f"{self._repos_path()}/topics/{quote(topic, safe='')}")
        return self.list_topics()

    def remove_topic(self, topic: str) -> list[str]:
        self._client.delete(f"{self._repos_path()}/topics/{quote(topic, safe='')}")
        return self.list_topics()

    # --- Compare ---

    def compare(self, base: str, head: str) -> CompareResult:
        """2つのコミット/ブランチを比較する。

        Gitea API の制約により behind_by は常に 0 を返す。
        ahead_by は total_commits と同値を返す。
        """
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
            "clone_addr": clone_url,
            "repo_name": name,
            "repo_owner": self._owner,
            "private": private,
            "mirror": mirror,
            "service": "git",
        }
        if description:
            payload["description"] = description
        if auth_token:
            payload["auth_token"] = auth_token
        resp = self._client.post("/repos/migrate", json=payload)
        return self._to_repository(resp.json())

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
        target: str | None = None,
    ) -> Release:
        payload = {
            "tag_name": tag,
            "name": title,
            "body": notes,
            "draft": draft,
            "prerelease": prerelease,
        }
        if target:
            payload["target_commitish"] = target
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

        from gfo.exceptions import GfoError

        resp = self._client.get(f"{self._repos_path()}/releases/tags/{quote(tag, safe='')}")
        release_id = resp.json()["id"]
        meta_resp = self._client.get(
            f"{self._repos_path()}/releases/{release_id}/assets/{asset_id}"
        )
        data = meta_resp.json()
        asset_name = os.path.basename(data.get("name") or f"asset-{asset_id}")
        output_path = os.path.join(output_dir, asset_name)
        if not os.path.realpath(output_path).startswith(os.path.realpath(output_dir)):
            raise GfoError(f"Invalid asset name: {asset_name}")
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

    def update_release_asset(self, *, tag, asset_id, name=None):
        resp = self._client.get(f"{self._repos_path()}/releases/tags/{quote(tag, safe='')}")
        release_id = resp.json()["id"]
        payload: dict = {}
        if name is not None:
            payload["name"] = name
        resp = self._client.patch(
            f"{self._repos_path()}/releases/{release_id}/assets/{asset_id}", json=payload
        )
        return self._to_release_asset(resp.json())

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
        add_labels: list[str] | None = None,
        remove_labels: list[str] | None = None,
        add_assignees: list[str] | None = None,
        remove_assignees: list[str] | None = None,
        milestone: str | None = None,
    ) -> PullRequest:
        payload: dict = {}
        if title is not None:
            payload["title"] = title
        if body is not None:
            payload["body"] = body
        if base is not None:
            payload["base"] = base
        if add_labels or remove_labels or add_assignees or remove_assignees:
            pr_resp = self._client.get(f"{self._repos_path()}/pulls/{number}")
            pr_data = pr_resp.json()
            if add_labels or remove_labels:
                current_names = {lb["name"] for lb in pr_data.get("labels") or []}
                if add_labels:
                    current_names.update(add_labels)
                if remove_labels:
                    current_names -= set(remove_labels)
                if current_names:
                    payload["labels"] = self._resolve_label_ids(sorted(current_names))
                else:
                    payload["labels"] = []
            if add_assignees or remove_assignees:
                current = {a["login"] for a in pr_data.get("assignees") or []}
                if add_assignees:
                    current.update(add_assignees)
                if remove_assignees:
                    current -= set(remove_assignees)
                payload["assignees"] = sorted(current)
        if milestone is not None:
            payload["milestone"] = self._resolve_milestone_id_by_title(milestone)
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
        add_labels: list[str] | None = None,
        remove_labels: list[str] | None = None,
        add_assignees: list[str] | None = None,
        remove_assignees: list[str] | None = None,
        milestone: str | None = None,
    ) -> Issue:
        payload: dict = {}
        if title is not None:
            payload["title"] = title
        if body is not None:
            payload["body"] = body
        if assignee is not None:
            payload["assignees"] = [assignee]
        if add_labels or remove_labels or add_assignees or remove_assignees:
            issue_resp = self._client.get(f"{self._repos_path()}/issues/{number}")
            issue_data = issue_resp.json()
            if add_labels or remove_labels:
                current_names = {lb["name"] for lb in issue_data.get("labels") or []}
                if add_labels:
                    current_names.update(add_labels)
                if remove_labels:
                    current_names -= set(remove_labels)
                if current_names:
                    payload["labels"] = self._resolve_label_ids(sorted(current_names))
                else:
                    payload["labels"] = []
            if add_assignees or remove_assignees:
                current = {a["login"] for a in issue_data.get("assignees") or []}
                if add_assignees:
                    current.update(add_assignees)
                if remove_assignees:
                    current -= set(remove_assignees)
                payload["assignees"] = sorted(current)
        if milestone is not None:
            payload["milestone"] = self._resolve_milestone_id_by_title(milestone)
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

    def get_branch(self, name: str) -> Branch:
        resp = self._client.get(f"{self._repos_path()}/branches/{quote(name, safe='')}")
        return self._to_branch(resp.json())

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

    def get_tag(self, name: str) -> Tag:
        resp = self._client.get(f"{self._repos_path()}/tags/{quote(name, safe='')}")
        return self._to_tag(resp.json())

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

    def update_webhook(
        self,
        hook_id: int,
        *,
        url: str | None = None,
        events: list[str] | None = None,
        secret: str | None = None,
        active: bool | None = None,
    ) -> Webhook:
        payload: dict = {}
        if url is not None or secret is not None:
            config: dict = {}
            if url is not None:
                config["url"] = url
            config["content_type"] = "json"
            if secret is not None:
                config["secret"] = secret
            payload["config"] = config
        if events is not None:
            payload["events"] = events
        if active is not None:
            payload["active"] = active
        resp = self._client.patch(f"{self._repos_path()}/hooks/{hook_id}", json=payload)
        return self._to_webhook(resp.json())

    # --- DeployKey ---

    def get_deploy_key(self, key_id: int) -> DeployKey:
        resp = self._client.get(f"{self._repos_path()}/keys/{key_id}")
        return self._to_deploy_key(resp.json())

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

    def trigger_pipeline(
        self, ref: str, *, workflow: str | None = None, inputs: dict | None = None
    ) -> Pipeline:
        from gfo.exceptions import GfoError

        if not workflow:
            raise GfoError("Gitea requires --workflow to trigger a pipeline.")
        payload: dict = {"ref": ref}
        if inputs:
            payload["inputs"] = inputs
        self._client.post(
            f"{self._repos_path()}/actions/workflows/{quote(workflow, safe='')}/dispatches",
            json=payload,
        )
        return Pipeline(id=0, status="pending", ref=ref, url="", created_at="")

    def retry_pipeline(self, pipeline_id: int | str) -> Pipeline:
        self._client.post(f"{self._repos_path()}/actions/runs/{pipeline_id}/rerun", json={})
        return self.get_pipeline(pipeline_id)

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

    def list_workflows(self, *, limit: int = 30) -> list[Workflow]:
        results: list[dict] = []
        per_page = min(limit, 30) if limit > 0 else 30
        page = 1
        while True:
            resp = self._client.get(
                f"{self._repos_path()}/actions/workflows",
                params={"limit": per_page, "page": page},
            )
            body = resp.json()
            page_data: list[dict] = body.get("workflows", []) if isinstance(body, dict) else []
            if not page_data:
                break
            results.extend(page_data)
            if limit > 0 and len(results) >= limit:
                results = results[:limit]
                break
            if len(page_data) < per_page:
                break
            page += 1
        return [self._to_workflow_data(r) for r in results]

    def enable_workflow(self, workflow_id: int | str) -> None:
        self._client.put(
            f"{self._repos_path()}/actions/workflows/{workflow_id}/enable",
            json={},
        )

    def disable_workflow(self, workflow_id: int | str) -> None:
        self._client.put(
            f"{self._repos_path()}/actions/workflows/{workflow_id}/disable",
            json={},
        )

    def list_artifacts(self, run_id: int | str, *, limit: int = 30) -> list[Artifact]:
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/actions/runs/{run_id}/artifacts",
            limit=limit,
            per_page_key="limit",
        )
        return [self._to_artifact_data(r) for r in results]

    def download_artifact(
        self, run_id: int | str, artifact_id: int | str, *, output_dir: str = "."
    ) -> str:
        import os

        resp = self._client.get(f"{self._repos_path()}/actions/artifacts/{artifact_id}")
        data = resp.json()
        name = os.path.basename(data.get("name", f"artifact-{artifact_id}"))
        output_path = os.path.join(output_dir, f"{name}.zip")
        if not os.path.realpath(output_path).startswith(os.path.realpath(output_dir)):
            raise GfoError(f"Invalid artifact name: {name}")
        url = f"{self._client.base_url}{self._repos_path()}/actions/artifacts/{artifact_id}/zip"
        self._client.download_file(url, output_path)
        return output_path

    def download_run_logs(
        self, run_id: int | str, *, job_id: int | str | None = None, output_dir: str = "."
    ) -> str:
        import os

        output_path = os.path.join(output_dir, f"logs-{run_id}.zip")
        url = f"{self._client.base_url}{self._repos_path()}/actions/runs/{run_id}/logs"
        self._client.download_file(url, output_path)
        return output_path

    @staticmethod
    def _to_workflow_data(data: dict) -> Workflow:
        try:
            state = "active" if data.get("state") == "active" else "disabled"
            return Workflow(
                id=data["id"],
                name=data.get("name") or "",
                path=data.get("path") or "",
                state=state,
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: {e}") from e

    @staticmethod
    def _to_artifact_data(data: dict) -> Artifact:
        try:
            return Artifact(
                id=data["id"],
                name=data.get("name") or "",
                size=data.get("size_in_bytes") or data.get("size") or 0,
                url=data.get("archive_download_url") or data.get("url") or "",
                created_at=data.get("created_at") or "",
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: {e}") from e

    # --- User ---

    def get_current_user(self) -> dict:
        resp = self._client.get("/user")
        return dict(resp.json())

    # --- Secret ---

    def _secrets_base_path(self, scope: str | None) -> str:
        if scope:
            return f"/orgs/{quote(scope, safe='')}/actions/secrets"
        return f"{self._repos_path()}/actions/secrets"

    def list_secrets(self, *, scope: str | None = None, limit: int = 30) -> list[Secret]:
        base = self._secrets_base_path(scope)
        results = paginate_link_header(
            self._client,
            base,
            limit=limit,
            per_page_key="limit",
        )
        return [
            Secret(name=d["name"], created_at=d.get("created_at") or "", updated_at="")
            for d in results
        ]

    def set_secret(self, name: str, value: str, *, scope: str | None = None) -> Secret:
        base = self._secrets_base_path(scope)
        self._client.put(
            f"{base}/{quote(name, safe='')}",
            json={"data": value},
        )
        return Secret(name=name, created_at="", updated_at="")

    def delete_secret(self, name: str, *, scope: str | None = None) -> None:
        base = self._secrets_base_path(scope)
        self._client.delete(f"{base}/{quote(name, safe='')}")

    # --- Variable ---

    def _variables_base_path(self, scope: str | None) -> str:
        if scope:
            return f"/orgs/{quote(scope, safe='')}/actions/variables"
        return f"{self._repos_path()}/actions/variables"

    def list_variables(self, *, scope: str | None = None, limit: int = 30) -> list[Variable]:
        base = self._variables_base_path(scope)
        results = paginate_link_header(
            self._client,
            base,
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

    def set_variable(
        self, name: str, value: str, *, scope: str | None = None, masked: bool = False
    ) -> Variable:
        from gfo.exceptions import NotFoundError

        base = self._variables_base_path(scope)
        try:
            self._client.get(f"{base}/{quote(name, safe='')}")
            self._client.put(
                f"{base}/{quote(name, safe='')}",
                json={"name": name, "value": value},
            )
        except NotFoundError:
            self._client.post(
                base,
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

    def delete_variable(self, name: str, *, scope: str | None = None) -> None:
        base = self._variables_base_path(scope)
        self._client.delete(f"{base}/{quote(name, safe='')}")

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

    def create_organization(
        self, name: str, *, display_name: str | None = None, description: str | None = None
    ) -> Organization:
        payload: dict = {"username": name}
        if display_name:
            payload["full_name"] = display_name
        if description:
            payload["description"] = description
        resp = self._client.post("/orgs", json=payload)
        return self._to_organization(resp.json())

    def delete_organization(self, name: str) -> None:
        self._client.delete(f"/orgs/{quote(name, safe='')}")

    def update_organization(
        self,
        name: str,
        *,
        display_name: str | None = None,
        description: str | None = None,
    ) -> Organization:
        payload: dict = {}
        if display_name is not None:
            payload["full_name"] = display_name
        if description is not None:
            payload["description"] = description
        resp = self._client.patch(f"/orgs/{quote(name, safe='')}", json=payload)
        return self._to_organization(resp.json())

    # --- SSH Key ---

    def get_ssh_key(self, key_id: int | str) -> SshKey:
        resp = self._client.get(f"/user/keys/{key_id}")
        return self._to_ssh_key(resp.json())

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

    # --- GPG Key ---

    def get_gpg_key(self, key_id: int | str) -> GpgKey:
        resp = self._client.get(f"/user/gpg_keys/{key_id}")
        return self._to_gpg_key(resp.json())

    def list_gpg_keys(self, *, limit: int = 30) -> list[GpgKey]:
        results = paginate_link_header(
            self._client, "/user/gpg_keys", limit=limit, per_page_key="limit"
        )
        return [self._to_gpg_key(r) for r in results]

    def create_gpg_key(self, *, armored_key: str) -> GpgKey:
        resp = self._client.post("/user/gpg_keys", json={"armored_public_key": armored_key})
        return self._to_gpg_key(resp.json())

    def delete_gpg_key(self, *, key_id: int | str) -> None:
        self._client.delete(f"/user/gpg_keys/{key_id}")

    @staticmethod
    def _to_gpg_key(data: dict) -> GpgKey:
        return GpgKey(
            id=data["id"],
            primary_key_id=data.get("primary_key_id") or "",
            public_key=data.get("public_key") or data.get("raw_key") or "",
            emails=tuple(e.get("email", "") for e in (data.get("emails") or [])),
            created_at=data.get("created_at") or "",
        )

    # --- Tag Protection ---

    def list_tag_protections(self, *, limit: int = 30) -> list[TagProtection]:
        resp = self._client.get(f"/repos/{self._owner}/{self._repo}/tag_protections")
        return [
            TagProtection(
                id=r["id"],
                pattern=r.get("name_pattern") or "",
                create_access_level=r.get("whitelist_teams") or "",
            )
            for r in (resp.json() or [])
        ]

    def create_tag_protection(
        self, pattern: str, *, create_access_level: str | None = None
    ) -> TagProtection:
        payload: dict = {"name_pattern": pattern}
        if create_access_level is not None:
            payload["whitelist_teams"] = create_access_level
        resp = self._client.post(f"/repos/{self._owner}/{self._repo}/tag_protections", json=payload)
        data = resp.json()
        return TagProtection(
            id=data["id"],
            pattern=data.get("name_pattern") or "",
            create_access_level=data.get("whitelist_teams") or "",
        )

    def delete_tag_protection(self, protection_id: int | str) -> None:
        self._client.delete(f"/repos/{self._owner}/{self._repo}/tag_protections/{protection_id}")

    def update_tag_protection(
        self,
        protection_id: int | str,
        *,
        pattern: str | None = None,
        create_access_level: str | None = None,
    ) -> TagProtection:
        payload: dict = {}
        if pattern is not None:
            payload["name_pattern"] = pattern
        if create_access_level is not None:
            payload["whitelist_teams"] = create_access_level
        resp = self._client.patch(
            f"/repos/{self._owner}/{self._repo}/tag_protections/{protection_id}", json=payload
        )
        data = resp.json()
        return TagProtection(
            id=data["id"],
            pattern=data.get("name_pattern") or "",
            create_access_level=data.get("whitelist_teams") or "",
        )

    # --- Browse ---

    def get_web_url(self, resource: str = "repo", number: int | str | None = None) -> str:
        from urllib.parse import urlparse

        parsed = urlparse(self._client.base_url)
        port_str = f":{parsed.port}" if parsed.port else ""
        web_base = f"{parsed.scheme}://{parsed.hostname}{port_str}"
        base = f"{web_base}/{self._owner}/{self._repo}"
        if resource == "pr":
            return f"{base}/pulls" if number is None else f"{base}/pulls/{number}"
        if resource == "issue":
            return f"{base}/issues" if number is None else f"{base}/issues/{number}"
        if resource == "release":
            return f"{base}/releases" if number is None else f"{base}/releases/tag/{number}"
        if resource == "milestone":
            return f"{base}/milestones" if number is None else f"{base}/milestones/{number}"
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

    # --- Issue Reaction ---

    def list_issue_reactions(self, number: int) -> list[Reaction]:
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/issues/{number}/reactions",
            limit=0,
            per_page_key="limit",
        )
        return [
            Reaction(
                id=r.get("id") or 0,
                content=r.get("content") or "",
                user=(r.get("user") or {}).get("login") or "",
                created_at=r.get("created_at") or "",
            )
            for r in results
        ]

    def add_issue_reaction(self, number: int, reaction: str) -> Reaction:
        resp = self._client.post(
            f"{self._repos_path()}/issues/{number}/reactions",
            json={"content": reaction},
        )
        r = resp.json()
        return Reaction(
            id=r.get("id") or 0,
            content=r.get("content") or "",
            user=(r.get("user") or {}).get("login") or "",
            created_at=r.get("created_at") or "",
        )

    def remove_issue_reaction(self, number: int, reaction: str) -> None:
        self._client.delete(
            f"{self._repos_path()}/issues/{number}/reactions",
            json={"content": reaction},
        )

    # --- Issue Dependency ---

    def list_issue_dependencies(self, number: int) -> list[Issue]:
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/issues/{number}/dependencies",
            limit=0,
            per_page_key="limit",
        )
        return [self._to_issue(r) for r in results]

    def add_issue_dependency(self, number: int, depends_on: int) -> None:
        self._client.post(
            f"{self._repos_path()}/issues/{number}/dependencies",
            json={"id": depends_on},
        )

    def remove_issue_dependency(self, number: int, depends_on: int) -> None:
        self._client.delete(
            f"{self._repos_path()}/issues/{number}/dependencies",
            json={"id": depends_on},
        )

    # --- Issue Timeline ---

    def get_issue_timeline(self, number: int, *, limit: int = 30) -> list[TimelineEvent]:
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/issues/{number}/timeline",
            limit=limit,
            per_page_key="limit",
        )
        return [
            TimelineEvent(
                id=e.get("id") or 0,
                event=e.get("type") or "",
                actor=(e.get("user") or {}).get("login") or "",
                created_at=e.get("created_at") or "",
                detail=e.get("body") or (e.get("label") or {}).get("name") or "",
            )
            for e in results
        ]

    # --- Issue Lock ---

    def lock_issue(self, number: int, *, reason: str | None = None) -> None:
        self._client.put(
            f"{self._repos_path()}/issues/{number}/lock",
            json={},
        )

    def unlock_issue(self, number: int) -> None:
        self._client.delete(f"{self._repos_path()}/issues/{number}/lock")

    # --- Issue Subscribe ---

    def subscribe_issue(self, number: int) -> None:
        user = self.get_current_user()
        username = user["login"]
        self._client.put(
            f"{self._repos_path()}/issues/{number}/subscriptions/{quote(username, safe='')}",
            json={},
        )

    def unsubscribe_issue(self, number: int) -> None:
        user = self.get_current_user()
        username = user["login"]
        self._client.delete(
            f"{self._repos_path()}/issues/{number}/subscriptions/{quote(username, safe='')}",
        )

    # --- Issue Pin ---

    def pin_issue(self, number: int) -> None:
        self._client.post(f"{self._repos_path()}/issues/{number}/pin", json={})

    def unpin_issue(self, number: int) -> None:
        self._client.delete(f"{self._repos_path()}/issues/{number}/pin")

    # --- Search PR / Commit ---

    def search_pull_requests(
        self, query: str, *, state: str | None = None, limit: int = 30
    ) -> list[PullRequest]:
        params: dict = {}
        if query:
            params["q"] = query
        if state and state != "all":
            params["state"] = state
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/pulls",
            params=params,
            limit=limit,
            per_page_key="limit",
        )
        return [self._to_pull_request(r) for r in results]

    def search_commits(
        self,
        query: str,
        *,
        author: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 30,
    ) -> list[Commit]:
        params: dict = {}
        if query:
            params["keyword"] = query
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/git/commits",
            params=params,
            limit=limit,
            per_page_key="limit",
        )
        return [
            Commit(
                sha=c.get("sha") or "",
                message=(c.get("commit") or {}).get("message") or c.get("message") or "",
                author=(c.get("author") or {}).get("login")
                or (c.get("commit") or {}).get("author", {}).get("name")
                or "",
                url=c.get("html_url") or "",
                created_at=(c.get("commit") or {}).get("author", {}).get("date")
                or c.get("created")
                or "",
            )
            for c in results
        ]

    # --- Package ---

    def list_packages(self, *, package_type: str | None = None, limit: int = 30) -> list[Package]:
        params: dict = {}
        if package_type:
            params["type"] = package_type
        results = paginate_link_header(
            self._client,
            f"/packages/{quote(self._owner, safe='')}",
            params=params,
            limit=limit,
            per_page_key="limit",
        )
        return [
            Package(
                name=p.get("name") or "",
                type=p.get("type") or "",
                version=p.get("version") or "",
                owner=p.get("owner", {}).get("login") or self._owner,
                url=p.get("html_url") or "",
                created_at=p.get("created_at") or "",
            )
            for p in results
        ]

    def get_package(self, package_type: str, name: str, *, version: str | None = None) -> Package:
        if version:
            resp = self._client.get(
                f"/packages/{quote(self._owner, safe='')}"
                f"/{package_type}/{quote(name, safe='')}/{quote(version, safe='')}"
            )
            p = resp.json()
            return Package(
                name=p.get("name") or "",
                type=p.get("type") or package_type,
                version=p.get("version") or version or "",
                owner=self._owner,
                url=p.get("html_url") or "",
                created_at=p.get("created_at") or "",
            )
        # version 未指定: 一覧から最初の一致を返す
        results = paginate_link_header(
            self._client,
            f"/packages/{quote(self._owner, safe='')}",
            params={"type": package_type, "q": name},
            limit=1,
            per_page_key="limit",
        )
        if not results:
            raise NotFoundError(f"Package '{name}' not found")
        resp_data = results[0]
        return Package(
            name=resp_data.get("name") or "",
            type=resp_data.get("type") or "",
            version=resp_data.get("version") or "",
            owner=resp_data.get("owner", {}).get("login") or self._owner,
            url=resp_data.get("html_url") or "",
            created_at=resp_data.get("created_at") or "",
        )

    def delete_package(self, package_type: str, name: str, version: str) -> None:
        self._client.delete(
            f"/packages/{quote(self._owner, safe='')}"
            f"/{package_type}/{quote(name, safe='')}/{quote(version, safe='')}"
        )

    # --- Time Tracking ---

    def list_time_entries(self, issue_number: int) -> list[TimeEntry]:
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/issues/{issue_number}/times",
            limit=0,
            per_page_key="limit",
        )
        return [
            TimeEntry(
                id=t["id"],
                user=(t.get("user") or {}).get("login") or "",
                duration=t.get("time") or 0,
                created_at=t.get("created") or "",
            )
            for t in results
        ]

    def add_time_entry(self, issue_number: int, duration: int) -> TimeEntry:
        resp = self._client.post(
            f"{self._repos_path()}/issues/{issue_number}/times",
            json={"time": duration},
        )
        t = resp.json()
        return TimeEntry(
            id=t["id"],
            user=(t.get("user") or {}).get("login") or "",
            duration=t.get("time") or 0,
            created_at=t.get("created") or "",
        )

    def delete_time_entry(self, issue_number: int, entry_id: int | str) -> None:
        self._client.delete(f"{self._repos_path()}/issues/{issue_number}/times/{entry_id}")

    # --- Push Mirror ---

    def list_push_mirrors(self) -> list[PushMirror]:
        results = paginate_link_header(
            self._client,
            f"{self._repos_path()}/push_mirrors",
            limit=0,
            per_page_key="limit",
        )
        return [
            PushMirror(
                id=m.get("id") or 0,
                remote_name=m.get("remote_name") or "",
                remote_address=m.get("remote_address") or "",
                interval=m.get("interval") or "",
                created_at=m.get("created_unix") or "",
                last_update=m.get("last_update"),
                last_error=m.get("last_error"),
            )
            for m in results
        ]

    def create_push_mirror(
        self,
        remote_address: str,
        *,
        interval: str = "8h",
        sync_on_commit: bool = True,
        auth_token: str | None = None,
    ) -> PushMirror:
        payload: dict = {
            "remote_address": remote_address,
            "interval": interval,
            "sync_on_commit": sync_on_commit,
        }
        if auth_token:
            payload["remote_password"] = auth_token
        resp = self._client.post(f"{self._repos_path()}/push_mirrors", json=payload)
        m = resp.json()
        return PushMirror(
            id=m.get("id") or 0,
            remote_name=m.get("remote_name") or "",
            remote_address=m.get("remote_address") or "",
            interval=m.get("interval") or "",
            created_at=m.get("created_unix") or "",
            last_update=m.get("last_update"),
            last_error=m.get("last_error"),
        )

    def delete_push_mirror(self, mirror_name: str) -> None:
        self._client.delete(f"{self._repos_path()}/push_mirrors/{mirror_name}")

    def sync_mirror(self) -> None:
        self._client.post(f"{self._repos_path()}/mirror-sync", json={})

    # --- Repo Transfer ---

    def transfer_repository(self, new_owner: str, *, team_ids: list[int] | None = None) -> None:
        payload: dict = {"new_owner": new_owner}
        if team_ids:
            payload["team_ids"] = team_ids
        self._client.post(f"{self._repos_path()}/transfer", json=payload)

    # --- Repo Star ---

    def star_repository(self) -> None:
        self._client.put(f"/user/starred/{self._owner}/{self._repo}", json={})

    def unstar_repository(self) -> None:
        self._client.delete(f"/user/starred/{self._owner}/{self._repo}")

    # --- Wiki Revisions ---

    def list_wiki_revisions(self, page_name: str) -> list[WikiRevision]:
        resp = self._client.get(f"{self._repos_path()}/wiki/revisions/{quote(page_name, safe='')}")
        data = resp.json()
        revisions = data if isinstance(data, list) else data.get("page_revisions") or []
        return [
            WikiRevision(
                sha=r.get("commit_sha") or r.get("sha") or "",
                author=(r.get("commiter") or r.get("committer") or {}).get("name") or "",
                message=r.get("message") or "",
                created_at=r.get("commit_date") or r.get("created") or "",
            )
            for r in revisions
        ]
