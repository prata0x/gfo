"""Azure DevOps アダプター。GitServiceAdapter の全メソッドを Azure DevOps REST API v7.1 で実装する。"""

from __future__ import annotations

import base64
import json as _json
from urllib.parse import quote, urlparse

import requests

from gfo.exceptions import GfoError, NotSupportedError
from gfo.http import paginate_top_skip

from .base import (
    Branch,
    BranchProtection,
    CheckRun,
    Comment,
    Commit,
    CommitStatus,
    CompareFile,
    CompareResult,
    DeployKey,
    GitServiceAdapter,
    Issue,
    IssueTemplate,
    Label,
    Milestone,
    Organization,
    Pipeline,
    PullRequest,
    PullRequestCommit,
    PullRequestFile,
    Release,
    Repository,
    Review,
    Tag,
    TimeEntry,
    TimelineEvent,
    Webhook,
)
from .registry import register


def _wiql_escape(value: str) -> str:
    """WIQL クエリ文字列内のシングルクォートをエスケープする。"""
    return value.replace("'", "''")


_PR_STATE_TO_API = {"open": "active", "closed": "abandoned", "merged": "completed"}
_PR_STATE_FROM_API = {"active": "open", "abandoned": "closed", "completed": "merged"}

_CLOSED_STATES = frozenset({"Closed", "Done", "Removed"})


def _add_refs_prefix(branch: str) -> str:
    if branch.startswith("refs/heads/"):
        return branch
    return f"refs/heads/{branch}"


def _strip_refs_prefix(ref: str) -> str:
    if ref.startswith("refs/heads/"):
        return ref[len("refs/heads/") :]
    return ref


@register("azure-devops")
class AzureDevOpsAdapter(GitServiceAdapter):
    service_name = "Azure DevOps"

    def __init__(
        self, client, owner: str, repo: str, *, organization: str, project_key: str, **kwargs
    ):
        super().__init__(client, owner, repo, **kwargs)
        self._org = organization
        self._project = project_key

    def _git_path(self) -> str:
        return f"/git/repositories/{quote(self._repo, safe='')}"

    def _wit_path(self) -> str:
        return "/wit"

    # --- 変換ヘルパー ---

    @staticmethod
    def _to_pull_request(data: dict) -> PullRequest:
        try:
            return PullRequest(
                number=data["pullRequestId"],
                title=data["title"],
                body=data.get("description"),
                state=_PR_STATE_FROM_API.get(data["status"], "open"),
                author=data["createdBy"]["uniqueName"],
                source_branch=_strip_refs_prefix(data["sourceRefName"]),
                target_branch=_strip_refs_prefix(data["targetRefName"]),
                draft=data.get("isDraft", False),
                url=(
                    f"{data['repository']['webUrl']}/pullrequest/{data['pullRequestId']}"
                    if (data.get("repository") or {}).get("webUrl")
                    else data.get("url", "")
                ),
                created_at=data["creationDate"],
                updated_at=data.get("closedDate"),
            )
        except (KeyError, TypeError, AttributeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_issue(data: dict) -> Issue:
        try:
            fields = data["fields"]
            raw_state = fields.get("System.State", "")
            state = "closed" if raw_state in _CLOSED_STATES else "open"

            assigned_to = fields.get("System.AssignedTo")
            unique_name = assigned_to.get("uniqueName") if assigned_to else None
            assignees = [unique_name] if unique_name else []

            raw_tags = fields.get("System.Tags", "")
            labels = [t.strip() for t in raw_tags.split(";") if t.strip()] if raw_tags else []

            return Issue(
                number=data["id"],
                title=fields["System.Title"],
                body=fields.get("System.Description"),
                state=state,
                author=(fields.get("System.CreatedBy") or {}).get("uniqueName", ""),
                assignees=assignees,
                labels=labels,
                url=data.get("url", ""),
                created_at=fields.get("System.CreatedDate", ""),
                updated_at=fields.get("System.ChangedDate"),
            )
        except (KeyError, TypeError, AttributeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_repository(data: dict, project: str = "") -> Repository:
        try:
            return Repository(
                name=data["name"],
                full_name=f"{project}/{data['name']}",
                description=(data.get("project") or {}).get("description"),
                private=True,
                default_branch=_strip_refs_prefix(data.get("defaultBranch") or ""),
                clone_url=data.get("remoteUrl", ""),
                url=data.get("webUrl", ""),
            )
        except (KeyError, TypeError, AttributeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    # --- PR ---

    def list_pull_requests(self, *, state: str = "open", limit: int = 30) -> list[PullRequest]:
        params: dict = {}
        if state != "all":
            params["searchCriteria.status"] = _PR_STATE_TO_API.get(state, "active")
        results = paginate_top_skip(
            self._client,
            f"{self._git_path()}/pullrequests",
            params=params,
            limit=limit,
            result_key="value",
        )
        return [self._to_pull_request(r) for r in results]

    def create_pull_request(
        self, *, title: str, body: str = "", base: str, head: str, draft: bool = False
    ) -> PullRequest:
        payload = {
            "title": title,
            "description": body,
            "sourceRefName": _add_refs_prefix(head),
            "targetRefName": _add_refs_prefix(base),
            "isDraft": draft,
        }
        resp = self._client.post(f"{self._git_path()}/pullrequests", json=payload)
        return self._to_pull_request(resp.json())

    def get_pull_request(self, number: int) -> PullRequest:
        resp = self._client.get(f"{self._git_path()}/pullrequests/{number}")
        return self._to_pull_request(resp.json())

    def merge_pull_request(self, number: int, *, method: str = "merge") -> None:
        strategy_map = {
            "merge": "noFastForward",
            "squash": "squash",
            "rebase": "rebase",
        }
        strategy = strategy_map.get(method, "noFastForward")
        pr_resp = self._client.get(f"{self._git_path()}/pullrequests/{number}")
        pr_data = pr_resp.json()
        if not isinstance(pr_data, dict):
            raise GfoError(f"Unexpected API response from pullrequests endpoint: {type(pr_data)}")
        last_merge_commit = pr_data.get("lastMergeSourceCommit")
        if not last_merge_commit:
            raise GfoError(
                f"Cannot merge pull request #{number}: lastMergeSourceCommit not found. "
                "The pull request may have no commits or may be in an invalid state."
            )
        payload = {
            "status": "completed",
            "lastMergeSourceCommit": last_merge_commit,
            "completionOptions": {"mergeStrategy": strategy},
        }
        self._client.patch(f"{self._git_path()}/pullrequests/{number}", json=payload)

    def close_pull_request(self, number: int) -> None:
        self._client.patch(
            f"{self._git_path()}/pullrequests/{number}",
            json={"status": "abandoned"},
        )

    def reopen_pull_request(self, number: int) -> None:
        self._client.patch(
            f"{self._git_path()}/pullrequests/{number}",
            json={"status": "active"},
        )

    def get_pr_checkout_refspec(self, number: int, *, pr: PullRequest | None = None) -> str:
        return f"refs/pull/{number}/head"

    def get_pull_request_diff(self, number: int) -> str:
        raise NotSupportedError(self.service_name, "pr diff")

    def list_pull_request_checks(self, number: int) -> list[CheckRun]:
        _STATE_MAP = {
            "succeeded": "success",
            "failed": "failure",
            "pending": "pending",
            "notApplicable": "success",
            "notSet": "pending",
            "error": "failure",
        }
        results = paginate_top_skip(
            self._client,
            f"{self._git_path()}/pullrequests/{number}/statuses",
            result_key="value",
        )
        out: list[CheckRun] = []
        for s in results:
            genre = s.get("context", {}).get("genre", "")
            name = s.get("context", {}).get("name", "")
            full_name = f"{genre}/{name}" if genre else name
            state = _STATE_MAP.get(s.get("state", ""), "pending")
            out.append(
                CheckRun(
                    name=full_name,
                    status=state,
                    conclusion="",
                    url=s.get("targetUrl", ""),
                    started_at=s.get("creationDate", ""),
                )
            )
        return out

    def list_pull_request_files(self, number: int) -> list[PullRequestFile]:
        _CHANGE_MAP = {
            "add": "added",
            "edit": "modified",
            "delete": "deleted",
            "rename": "renamed",
        }
        # 最新のイテレーションを取得
        iters = self._client.get(
            f"{self._git_path()}/pullrequests/{number}/iterations",
        ).json()
        iterations = iters.get("value", [])
        if not iterations:
            return []
        last_id = iterations[-1]["id"]
        resp = self._client.get(
            f"{self._git_path()}/pullrequests/{number}/iterations/{last_id}/changes",
        ).json()
        out: list[PullRequestFile] = []
        for entry in resp.get("changeEntries", []):
            item = entry.get("item", {})
            change_type = entry.get("changeType", "edit")
            # changeType はカンマ区切りで複合値になる場合がある（例: "rename, edit"）
            primary = change_type.split(",")[0].strip().lower()
            out.append(
                PullRequestFile(
                    filename=item.get("path", ""),
                    status=_CHANGE_MAP.get(primary, "modified"),
                    additions=0,
                    deletions=0,
                )
            )
        return out

    def list_pull_request_commits(self, number: int) -> list[PullRequestCommit]:
        results = paginate_top_skip(
            self._client,
            f"{self._git_path()}/pullrequests/{number}/commits",
            result_key="value",
        )
        return [
            PullRequestCommit(
                sha=c.get("commitId", ""),
                message=c.get("comment", ""),
                author=c.get("author", {}).get("name", ""),
                created_at=c.get("author", {}).get("date", ""),
            )
            for c in results
        ]

    def list_requested_reviewers(self, number: int) -> list[str]:
        resp = self._client.get(
            f"{self._git_path()}/pullrequests/{number}/reviewers",
        ).json()
        return [r.get("displayName", "") for r in resp.get("value", [])]

    def request_reviewers(self, number: int, reviewers: list[str]) -> None:
        for reviewer in reviewers:
            self._client.put(
                f"{self._git_path()}/pullrequests/{number}/reviewers/{quote(reviewer, safe='')}",
                json={"vote": 0},
            )

    def remove_reviewers(self, number: int, reviewers: list[str]) -> None:
        for reviewer in reviewers:
            self._client.delete(
                f"{self._git_path()}/pullrequests/{number}/reviewers/{quote(reviewer, safe='')}",
            )

    def enable_auto_merge(self, number: int, *, merge_method: str | None = None) -> None:
        _MERGE_STRATEGY = {
            "merge": "noFastForward",
            "squash": "squash",
            "rebase": "rebaseMerge",
        }
        pr_resp = self._client.get(
            f"{self._git_path()}/pullrequests/{number}",
        ).json()
        created_by_id = pr_resp.get("createdBy", {}).get("id", "")
        strategy = _MERGE_STRATEGY.get(merge_method or "", "noFastForward")
        self._client.patch(
            f"{self._git_path()}/pullrequests/{number}",
            json={
                "autoCompleteSetBy": {"id": created_by_id},
                "completionOptions": {"mergeStrategy": strategy},
            },
        )

    def mark_pull_request_ready(self, number: int) -> None:
        self._client.patch(
            f"{self._git_path()}/pullrequests/{number}",
            json={"isDraft": False},
        )

    def dismiss_review(self, number: int, review_id: int, *, message: str = "") -> None:
        self._client.put(
            f"{self._git_path()}/pullrequests/{number}/reviewers/{review_id}",
            json={"vote": 0},
        )

    # --- Issue (Work Item) ---

    def list_issues(
        self,
        *,
        state: str = "open",
        assignee: str | None = None,
        label: str | None = None,
        limit: int = 30,
    ) -> list[Issue]:
        conditions = [f"[System.TeamProject] = '{_wiql_escape(self._project)}'"]
        if state == "open":
            conditions.append("[System.State] NOT IN ('Closed', 'Done', 'Removed')")
        elif state == "closed":
            conditions.append("[System.State] IN ('Closed', 'Done', 'Removed')")
        if assignee:
            conditions.append(f"[System.AssignedTo] = '{_wiql_escape(assignee)}'")
        if label:
            conditions.append(f"[System.Tags] CONTAINS '{_wiql_escape(label)}'")

        wiql = "SELECT [System.Id] FROM WorkItems WHERE " + " AND ".join(conditions)  # nosec B608 - conditions built from internal values only, no user input
        wiql_params = {"$top": limit} if limit > 0 else {"$top": 20000}
        wiql_resp = self._client.post(
            f"{self._wit_path()}/wiql",
            json={"query": wiql},
            params=wiql_params,
        )
        wiql_body = wiql_resp.json()
        if not isinstance(wiql_body, dict):
            raise GfoError(f"Unexpected API response from WIQL endpoint: {type(wiql_body)}")
        try:
            ids = [wi["id"] for wi in wiql_body.get("workItems", [])]
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response from WIQL endpoint: {e}") from e
        if not ids:
            return []

        results: list[Issue] = []
        for i in range(0, len(ids), 200):
            # limit > 0 の場合、WIQL が $top で件数を制限済みだが念のため早期終了
            if limit > 0 and len(results) >= limit:
                break
            batch_ids = ids[i : i + 200]
            ids_str = ",".join(str(x) for x in batch_ids)
            resp = self._client.get(
                f"{self._wit_path()}/workitems",
                params={"ids": ids_str, "$expand": "None"},
            )
            batch_body = resp.json()
            if not isinstance(batch_body, dict):
                raise GfoError(
                    f"Unexpected API response from workitems endpoint: {type(batch_body)}"
                )
            for item in batch_body.get("value", []):
                results.append(self._to_issue(item))

        return results[:limit] if limit > 0 else results

    def create_issue(
        self,
        *,
        title: str,
        body: str = "",
        assignee: str | None = None,
        label: str | None = None,
        work_item_type: str = "Task",
        **kwargs,
    ) -> Issue:
        patch_ops = [
            {"op": "add", "path": "/fields/System.Title", "value": title},
        ]
        if body:
            patch_ops.append({"op": "add", "path": "/fields/System.Description", "value": body})
        if assignee:
            patch_ops.append({"op": "add", "path": "/fields/System.AssignedTo", "value": assignee})
        if label:
            patch_ops.append({"op": "add", "path": "/fields/System.Tags", "value": label})

        resp = self._client.post(
            f"{self._wit_path()}/workitems/${quote(work_item_type, safe='')}",
            data=_json.dumps(patch_ops),
            headers={"Content-Type": "application/json-patch+json"},
        )
        return self._to_issue(resp.json())

    def get_issue(self, number: int) -> Issue:
        resp = self._client.get(f"{self._wit_path()}/workitems/{number}")
        return self._to_issue(resp.json())

    def close_issue(self, number: int) -> None:
        patch_ops = [{"op": "replace", "path": "/fields/System.State", "value": "Closed"}]
        self._client.patch(
            f"{self._wit_path()}/workitems/{number}",
            data=_json.dumps(patch_ops),
            headers={"Content-Type": "application/json-patch+json"},
        )

    def reopen_issue(self, number: int) -> None:
        patch_ops = [{"op": "replace", "path": "/fields/System.State", "value": "New"}]
        self._client.patch(
            f"{self._wit_path()}/workitems/{number}",
            data=_json.dumps(patch_ops),
            headers={"Content-Type": "application/json-patch+json"},
        )

    def delete_issue(self, number: int) -> None:
        self._client.delete(f"{self._wit_path()}/workitems/{number}")

    def list_issue_templates(self) -> list[IssueTemplate]:
        try:
            resp = self._client.get("/wit/workitemtypes")
        except (GfoError, requests.RequestException, KeyError, ValueError):
            return []
        templates: list[IssueTemplate] = []
        for t in resp.json().get("value", []):
            templates.append(
                IssueTemplate(
                    name=t.get("name") or "",
                    title="",
                    body=t.get("description") or "",
                    about=t.get("description") or "",
                    labels=tuple(),
                )
            )
        return templates

    # --- Repository ---

    def list_repositories(self, *, owner: str | None = None, limit: int = 30) -> list[Repository]:
        if owner is not None:
            raise NotSupportedError(
                self.service_name,
                "filtering repositories by owner "
                "(repositories are scoped to the configured project)",
            )
        results = paginate_top_skip(
            self._client,
            "/git/repositories",
            limit=limit,
            result_key="value",
        )
        return [self._to_repository(r, self._project) for r in results]

    def create_repository(
        self, *, name: str, private: bool = False, description: str = ""
    ) -> Repository:
        # project はベース URL に含まれるため payload には含めない
        payload = {"name": name}
        resp = self._client.post("/git/repositories", json=payload)
        return self._to_repository(resp.json(), self._project)

    def get_repository(self, owner: str | None = None, name: str | None = None) -> Repository:
        n = name if name is not None else self._repo
        resp = self._client.get(f"/git/repositories/{quote(n, safe='')}")
        return self._to_repository(resp.json(), self._project)

    def delete_repository(self) -> None:
        resp = self._client.get(self._git_path())
        try:
            repo_id = resp.json()["id"]
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e
        self._client.delete(f"/git/repositories/{repo_id}")

    def update_repository(
        self,
        *,
        description: str | None = None,
        private: bool | None = None,
        default_branch: str | None = None,
    ) -> Repository:
        payload = {}
        if default_branch is not None:
            payload["defaultBranch"] = _add_refs_prefix(default_branch)
        resp = self._client.patch(self._git_path(), json=payload)
        return self._to_repository(resp.json(), self._project)

    def archive_repository(self) -> None:
        self._client.patch(self._git_path(), json={"isDisabled": True})

    def compare(self, base: str, head: str) -> CompareResult:
        resp = self._client.get(
            f"/git/repositories/{quote(self._repo, safe='')}/diffs/commits",
            params={"baseVersion": base, "targetVersion": head},
        )
        data = resp.json()
        changes = data.get("changes") or []
        files = tuple(
            CompareFile(
                filename=c.get("item", {}).get("path", "").lstrip("/"),
                status={
                    "add": "added",
                    "edit": "modified",
                    "delete": "deleted",
                    "rename": "renamed",
                }.get(c.get("changeType", "edit"), "modified"),
                additions=0,
                deletions=0,
            )
            for c in changes
        )
        return CompareResult(
            total_commits=0,
            ahead_by=data.get("aheadCount", 0),
            behind_by=data.get("behindCount", 0),
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
        # まずリポジトリを作成
        repo = self.create_repository(name=name, private=private, description=description)
        # Import Request
        payload: dict = {"parameters": {"gitSource": {"url": clone_url}}}
        if auth_token:
            payload["parameters"]["gitSource"]["username"] = ""
            payload["parameters"]["gitSource"]["password"] = auth_token
        self._client.post(
            f"/git/repositories/{quote(name, safe='')}/importRequests",
            json=payload,
        )
        return repo

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

    # --- 変換ヘルパー（追加型） ---

    @staticmethod
    def _to_comment(data: dict) -> Comment:
        from gfo.exceptions import GfoError

        try:
            # PR Threads の場合は comments 配列の最初のコメント
            if "comments" in data:
                comment_data = (data.get("comments") or [{}])[0]
            else:
                comment_data = data
            # PR thread は author, content フィールド / Work Item comment は createdBy, text フィールド
            author = comment_data.get("author") or comment_data.get("createdBy") or {}
            return Comment(
                id=comment_data.get("id") or data.get("id") or 0,
                body=comment_data.get("content") or comment_data.get("text") or "",
                author=author.get("uniqueName") or author.get("displayName") or "",
                url="",
                created_at=comment_data.get("publishedDate") or "",
                updated_at=comment_data.get("lastUpdatedDate"),
            )
        except (KeyError, TypeError, AttributeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_review(data: dict) -> Review:
        from gfo.exceptions import GfoError

        try:
            vote_map = {
                10: "approved",
                5: "approved",
                0: "commented",
                -5: "changes_requested",
                -10: "changes_requested",
            }
            vote = data.get("vote", 0)
            return Review(
                id=data.get("id") or 0,
                state=vote_map.get(vote, "commented"),
                body="",
                author=data.get("uniqueName") or data.get("displayName") or "",
                url="",
            )
        except (KeyError, TypeError, AttributeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_branch(data: dict) -> Branch:
        from gfo.exceptions import GfoError

        try:
            # AzDO: name は "refs/heads/xxx" 形式
            name = data["name"]
            if name.startswith("refs/heads/"):
                name = name[len("refs/heads/") :]
            return Branch(
                name=name,
                sha=(data.get("objectId") or ""),
                protected=False,
                url="",
            )
        except (KeyError, TypeError, AttributeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_tag(data: dict) -> Tag:
        from gfo.exceptions import GfoError

        try:
            name = data.get("name", "")
            if name.startswith("refs/tags/"):
                name = name[len("refs/tags/") :]
            return Tag(
                name=name,
                sha=data.get("objectId") or "",
                message="",
                url="",
            )
        except (KeyError, TypeError, AttributeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_commit_status(data: dict) -> CommitStatus:
        from gfo.exceptions import GfoError

        try:
            state_map = {
                "succeeded": "success",
                "failed": "failure",
                "pending": "pending",
                "error": "error",
                "notApplicable": "pending",
                "notSet": "pending",
            }
            state_obj = data.get("state", {})
            raw = state_obj if isinstance(state_obj, str) else state_obj.get("state", "pending")
            genre = (data.get("context") or {}).get("genre") or ""
            name = (data.get("context") or {}).get("name") or ""
            context = f"{genre}/{name}" if genre else name
            return CommitStatus(
                state=state_map.get(raw, raw),
                context=context,
                description=data.get("description") or "",
                target_url=data.get("targetUrl") or "",
                created_at=data.get("creationDate") or "",
            )
        except (KeyError, TypeError, AttributeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_webhook(data: dict) -> Webhook:
        from gfo.exceptions import GfoError

        try:
            events = tuple([data.get("eventType") or ""] if data.get("eventType") else [])
            return Webhook(
                id=data.get("id") or 0,
                url=(data.get("consumerInputs") or {}).get("url") or "",
                events=events,
                active=data.get("status") == "enabled",
            )
        except (KeyError, TypeError, AttributeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_pipeline(data: dict) -> Pipeline:
        from gfo.exceptions import GfoError

        try:
            status_map = {
                "completed": lambda d: {
                    "succeeded": "success",
                    "failed": "failure",
                    "canceled": "cancelled",
                }.get(d.get("result", ""), "failure"),
                "inProgress": lambda d: "running",
                "notStarted": lambda d: "pending",
                "cancelling": lambda d: "cancelled",
            }
            raw_status = data.get("status", "notStarted")
            mapper = status_map.get(raw_status)
            status = mapper(data) if mapper else raw_status
            source_branch = _strip_refs_prefix(data.get("sourceBranch") or "")
            return Pipeline(
                id=data["id"],
                status=status,
                ref=source_branch,
                url=data.get("_links", {}).get("web", {}).get("href") or "",
                created_at=data.get("queueTime") or "",
            )
        except (KeyError, TypeError, AttributeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    # --- Comment ---

    def list_comments(self, resource: str, number: int, *, limit: int = 30) -> list[Comment]:
        if resource == "pr":
            resp = self._client.get(f"{self._git_path()}/pullrequests/{number}/threads")
            threads = resp.json().get("value", [])
            result = []
            for thread in threads:
                for comment in thread.get("comments") or []:
                    result.append(self._to_comment(comment))
                    if limit > 0 and len(result) >= limit:
                        return result
            return result
        else:
            # Work Item コメントは 7.1-preview.3 が必要
            resp = self._client.get(
                f"{self._wit_path()}/workitems/{number}/comments",
                params={"api-version": "7.1-preview.3"},
            )
            comments_data = resp.json().get("comments", [])
            return [self._to_comment(c) for c in comments_data[: limit if limit > 0 else None]]

    def create_comment(self, resource: str, number: int, *, body: str) -> Comment:
        if resource == "pr":
            # PR コメントは Thread を作成する
            payload = {
                "comments": [{"parentCommentId": 0, "content": body, "commentType": 1}],
                "status": 1,
            }
            resp = self._client.post(
                f"{self._git_path()}/pullrequests/{number}/threads", json=payload
            )
            return self._to_comment(resp.json())
        else:
            payload = {"text": body}
            # Work Item コメントは 7.1-preview.3 が必要
            resp = self._client.post(
                f"{self._wit_path()}/workitems/{number}/comments",
                json=payload,
                params={"api-version": "7.1-preview.3"},
            )
            return self._to_comment(resp.json())

    def update_comment(self, resource: str, comment_id: int, *, body: str) -> Comment:
        # Azure DevOps のコメント更新は thread_id と comment_id の両方が必要で、comment_id のみでは不可
        raise NotSupportedError(
            self.service_name, "comment update (requires thread ID for PR comments)"
        )

    def delete_comment(self, resource: str, comment_id: int) -> None:
        raise NotSupportedError(
            self.service_name, "comment delete (requires thread ID for PR comments)"
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
            payload["targetRefName"] = _add_refs_prefix(base)
        resp = self._client.patch(f"{self._git_path()}/pullrequests/{number}", json=payload)
        return self._to_pull_request(resp.json())

    # --- Issue update (Work Item patch) ---

    def update_issue(
        self,
        number: int,
        *,
        title: str | None = None,
        body: str | None = None,
        assignee: str | None = None,
        label: str | None = None,
    ) -> Issue:
        patch_ops = []
        if title is not None:
            patch_ops.append({"op": "replace", "path": "/fields/System.Title", "value": title})
        if body is not None:
            patch_ops.append({"op": "replace", "path": "/fields/System.Description", "value": body})
        if assignee is not None:
            patch_ops.append(
                {"op": "replace", "path": "/fields/System.AssignedTo", "value": assignee}
            )
        if label is not None:
            patch_ops.append({"op": "replace", "path": "/fields/System.Tags", "value": label})
        resp = self._client.patch(
            f"{self._wit_path()}/workitems/{number}",
            data=_json.dumps(patch_ops),
            headers={"Content-Type": "application/json-patch+json"},
        )
        return self._to_issue(resp.json())

    # --- Review (Reviewers API) ---

    def list_reviews(self, number: int) -> list[Review]:
        resp = self._client.get(f"{self._git_path()}/pullrequests/{number}/reviewers")
        reviewers = resp.json()
        if not isinstance(reviewers, list):
            reviewers = reviewers.get("value", [])
        return [self._to_review(r) for r in reviewers]

    def _connection_data_url(self) -> str:
        """組織レベルの connectionData エンドポイント URL を返す。

        base_url は `https://dev.azure.com/{org}/{project}/_apis` のようなプロジェクト
        スコープ URL だが、connectionData は組織スコープ
        (`https://dev.azure.com/{org}/_apis/connectionData`) で呼ぶ必要がある。
        """
        parsed = urlparse(self._client.base_url)
        return f"{parsed.scheme}://{parsed.netloc}/{self._org}/_apis/connectionData"

    def create_review(self, number: int, *, state: str, body: str = "") -> Review:
        vote_map = {"APPROVE": 10, "REQUEST_CHANGES": -10, "COMMENT": 0}
        vote = vote_map.get(state.upper(), 0)
        # connectionData は組織スコープのため get_absolute で組織レベル URL を直接指定
        # connectionData は api-version=7.1-preview が必要（7.1 だと 400 エラー）
        user_resp = self._client.get_absolute(
            self._connection_data_url(), params={"api-version": "7.1-preview"}
        )
        user_id = (user_resp.json().get("authenticatedUser") or {}).get("id") or ""
        payload = {"vote": vote}
        resp = self._client.put(
            f"{self._git_path()}/pullrequests/{number}/reviewers/{user_id}",
            json=payload,
        )
        return self._to_review(resp.json())

    # --- Branch ---

    def list_branches(self, *, limit: int = 30) -> list[Branch]:
        results = paginate_top_skip(
            self._client,
            f"{self._git_path()}/refs",
            params={"filter": "heads/"},
            limit=limit,
            result_key="value",
        )
        return [self._to_branch(r) for r in results]

    def create_branch(self, *, name: str, ref: str) -> Branch:
        # AzDO refs 更新 API でブランチを作成（pushes API は commit が必要なので使用しない）
        payload = [{"name": f"refs/heads/{name}", "oldObjectId": "0" * 40, "newObjectId": ref}]
        self._client.post(f"{self._git_path()}/refs", json=payload)
        resp = self._client.get(
            f"{self._git_path()}/refs",
            params={"filter": f"heads/{name}"},
        )
        items = resp.json().get("value", [])
        if not items:
            from gfo.exceptions import GfoError

            raise GfoError(f"Branch '{name}' not found after creation")
        return self._to_branch(items[0])

    def delete_branch(self, *, name: str) -> None:
        # 現在の SHA を取得
        resp = self._client.get(
            f"{self._git_path()}/refs",
            params={"filter": f"heads/{name}"},
        )
        items = resp.json().get("value", [])
        if not items:
            from gfo.exceptions import NotFoundError

            raise NotFoundError(f"refs/heads/{name}")
        sha = items[0]["objectId"]
        payload = [{"name": f"refs/heads/{name}", "oldObjectId": sha, "newObjectId": "0" * 40}]
        self._client.post(f"{self._git_path()}/refs", json=payload)

    # --- Tag ---

    def list_tags(self, *, limit: int = 30) -> list[Tag]:
        results = paginate_top_skip(
            self._client,
            f"{self._git_path()}/refs",
            params={"filter": "tags/"},
            limit=limit,
            result_key="value",
        )
        return [self._to_tag(r) for r in results]

    def create_tag(self, *, name: str, ref: str, message: str = "") -> Tag:
        # Lightweight tag: refs 更新 API でタグを作成
        payload = [{"name": f"refs/tags/{name}", "oldObjectId": "0" * 40, "newObjectId": ref}]
        self._client.post(f"{self._git_path()}/refs", json=payload)
        return Tag(name=name, sha=ref, message=message, url="")

    def delete_tag(self, *, name: str) -> None:
        resp = self._client.get(
            f"{self._git_path()}/refs",
            params={"filter": f"tags/{name}"},
        )
        items = resp.json().get("value", [])
        if not items:
            from gfo.exceptions import NotFoundError

            raise NotFoundError(f"refs/tags/{name}")
        sha = items[0]["objectId"]
        payload = [{"name": f"refs/tags/{name}", "oldObjectId": sha, "newObjectId": "0" * 40}]
        self._client.post(f"{self._git_path()}/refs", json=payload)

    # --- CommitStatus ---

    def list_commit_statuses(self, ref: str, *, limit: int = 30) -> list[CommitStatus]:
        resp = self._client.get(f"{self._git_path()}/commits/{quote(ref, safe='')}/statuses")
        statuses = resp.json()
        if isinstance(statuses, dict):
            statuses = statuses.get("value", [])
        return [self._to_commit_status(s) for s in statuses[: limit if limit > 0 else None]]

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
            "success": "succeeded",
            "failure": "failed",
            "pending": "pending",
            "error": "error",
        }
        parts = context.split("/", 1) if "/" in context else ["gfo", context]
        payload: dict = {
            "state": state_map.get(state, state),
            "context": {"name": parts[-1], "genre": parts[0] if len(parts) > 1 else "gfo"},
        }
        if description:
            payload["description"] = description
        if target_url:
            payload["targetUrl"] = target_url
        resp = self._client.post(
            f"{self._git_path()}/commits/{quote(ref, safe='')}/statuses",
            json=payload,
        )
        return self._to_commit_status(resp.json())

    # --- File (Azure DevOps Items API) ---

    def get_file_content(self, path: str, *, ref: str | None = None) -> tuple[str, str]:
        params: dict = {"path": path, "includeContent": "true", "$format": "json"}
        if ref is not None:
            params["versionDescriptor.version"] = ref
            # 40文字の16進数は commit SHA、それ以外はブランチ名として扱う
            is_sha = len(ref) == 40 and all(c in "0123456789abcdef" for c in ref)
            params["versionDescriptor.versionType"] = "commit" if is_sha else "branch"
        resp = self._client.get(f"{self._git_path()}/items", params=params)
        data = resp.json()
        try:
            content = data.get("content") or ""
            # objectId は blob SHA
            sha = data.get("objectId") or ""
        except (KeyError, TypeError, AttributeError) as e:
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
        # AzDO ではファイル作成/更新に pushes API を使う
        branch = branch or "main"
        # 既存ブランチの最新コミット SHA を取得
        refs_resp = self._client.get(
            f"{self._git_path()}/refs",
            params={"filter": f"heads/{branch}"},
        )
        ref_items = refs_resp.json().get("value", [])
        old_oid = ref_items[0]["objectId"] if ref_items else "0" * 40
        change_type = 2 if sha else 1  # 1=add, 2=edit
        payload = {
            "refUpdates": [{"name": f"refs/heads/{branch}", "oldObjectId": old_oid}],
            "commits": [
                {
                    "comment": message,
                    "changes": [
                        {
                            "changeType": change_type,
                            "item": {"path": f"/{path}" if not path.startswith("/") else path},
                            "newContent": {
                                "content": base64.b64encode(content.encode()).decode(),
                                "contentType": "base64encoded",
                            },
                        }
                    ],
                }
            ],
        }
        resp = self._client.post(f"{self._git_path()}/pushes", json=payload)
        commits = resp.json().get("commits", [])
        return commits[0].get("commitId") if commits else None

    def delete_file(
        self,
        path: str,
        *,
        sha: str,
        message: str,
        branch: str | None = None,
    ) -> None:
        branch = branch or "main"
        refs_resp = self._client.get(
            f"{self._git_path()}/refs",
            params={"filter": f"heads/{branch}"},
        )
        ref_items = refs_resp.json().get("value", [])
        old_oid = ref_items[0]["objectId"] if ref_items else "0" * 40
        payload = {
            "refUpdates": [{"name": f"refs/heads/{branch}", "oldObjectId": old_oid}],
            "commits": [
                {
                    "comment": message,
                    "changes": [
                        {
                            "changeType": 16,  # delete
                            "item": {"path": f"/{path}" if not path.startswith("/") else path},
                        }
                    ],
                }
            ],
        }
        self._client.post(f"{self._git_path()}/pushes", json=payload)

    # --- Webhook (Service Hooks) ---

    def list_webhooks(self, *, limit: int = 30) -> list[Webhook]:
        raise NotSupportedError(self.service_name, "webhook list (use Azure DevOps Service Hooks)")

    def create_webhook(self, *, url: str, events: list[str], secret: str | None = None) -> Webhook:
        raise NotSupportedError(
            self.service_name, "webhook create (use Azure DevOps Service Hooks)"
        )

    def delete_webhook(self, *, hook_id: int) -> None:
        raise NotSupportedError(
            self.service_name, "webhook delete (use Azure DevOps Service Hooks)"
        )

    # --- DeployKey ---

    def list_deploy_keys(self, *, limit: int = 30) -> list[DeployKey]:
        raise NotSupportedError(
            self.service_name, "deploy-key (Azure DevOps uses SSH keys at org level)"
        )

    def create_deploy_key(self, *, title: str, key: str, read_only: bool = True) -> DeployKey:
        raise NotSupportedError(
            self.service_name, "deploy-key (Azure DevOps uses SSH keys at org level)"
        )

    def delete_deploy_key(self, *, key_id: int) -> None:
        raise NotSupportedError(
            self.service_name, "deploy-key (Azure DevOps uses SSH keys at org level)"
        )

    # --- Collaborator ---

    def list_collaborators(self, *, limit: int = 30) -> list[str]:
        raise NotSupportedError(
            self.service_name, "collaborator list (Azure DevOps uses teams/members)"
        )

    def add_collaborator(self, *, username: str, permission: str = "write") -> None:
        raise NotSupportedError(
            self.service_name, "collaborator add (Azure DevOps uses teams/members)"
        )

    def remove_collaborator(self, *, username: str) -> None:
        raise NotSupportedError(
            self.service_name, "collaborator remove (Azure DevOps uses teams/members)"
        )

    # --- Pipeline (Build API) ---

    def list_pipelines(self, *, ref: str | None = None, limit: int = 30) -> list[Pipeline]:
        params: dict = {}
        if ref is not None:
            params["branchName"] = f"refs/heads/{ref}" if not ref.startswith("refs/") else ref
        results = paginate_top_skip(
            self._client,
            "/build/builds",
            params=params,
            limit=limit,
            result_key="value",
        )
        return [self._to_pipeline(r) for r in results]

    def get_pipeline(self, pipeline_id: int | str) -> Pipeline:
        resp = self._client.get(f"/build/builds/{pipeline_id}")
        return self._to_pipeline(resp.json())

    def cancel_pipeline(self, pipeline_id: int | str) -> None:
        self._client.patch(
            f"/build/builds/{pipeline_id}",
            data=_json.dumps([{"op": "replace", "path": "/status", "value": "cancelling"}]),
            headers={"Content-Type": "application/json-patch+json"},
        )

    def trigger_pipeline(
        self, ref: str, *, workflow: str | None = None, inputs: dict | None = None
    ) -> Pipeline:
        payload: dict = {
            "sourceBranch": ref if ref.startswith("refs/") else f"refs/heads/{ref}",
        }
        if workflow:
            payload["definition"] = {"id": int(workflow)}
        resp = self._client.post("/build/builds", json=payload)
        return self._to_pipeline(resp.json())

    def retry_pipeline(self, pipeline_id: int | str) -> Pipeline:
        resp = self._client.patch(
            f"/build/builds/{pipeline_id}",
            json={"retry": True},
        )
        return self._to_pipeline(resp.json())

    def get_pipeline_logs(self, pipeline_id: int | str, *, job_id: int | str | None = None) -> str:
        if job_id is not None:
            resp = self._client.get(f"/build/builds/{pipeline_id}/logs/{job_id}")
            return str(resp.text)
        logs_resp = self._client.get(f"/build/builds/{pipeline_id}/logs")
        log_entries = logs_resp.json().get("value", [])
        logs = []
        for entry in log_entries:
            log_id = entry.get("id", "")
            try:
                resp = self._client.get(f"/build/builds/{pipeline_id}/logs/{log_id}")
                logs.append(f"=== Log {log_id} ===\n{resp.text}")
            except (GfoError, requests.RequestException):
                logs.append(f"=== Log {log_id} ===\n(log unavailable)")
        return "\n".join(logs)

    # --- User ---

    def get_current_user(self) -> dict:
        # /_apis/profile/profiles/me は組織スコープ外のため connectionData を使用
        # connectionData は組織スコープのため get_absolute で組織レベル URL を直接指定
        # connectionData は api-version=7.1-preview が必要（7.1 だと 400 エラー）
        resp = self._client.get_absolute(
            self._connection_data_url(), params={"api-version": "7.1-preview"}
        )
        data = resp.json()
        user = data.get("authenticatedUser") or {}
        return {
            "id": user.get("id", ""),
            "displayName": user.get("providerDisplayName", ""),
            "login": user.get("providerDisplayName", ""),
        }

    # --- BranchProtection (Policy) ---

    def list_branch_protections(self, *, limit: int = 30) -> list[BranchProtection]:
        raise NotSupportedError(
            self.service_name,
            "branch-protect list (Azure DevOps uses policy configurations)",
        )

    def get_branch_protection(self, branch: str) -> BranchProtection:
        raise NotSupportedError(
            self.service_name,
            "branch-protect view (Azure DevOps uses policy configurations)",
        )

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
        raise NotSupportedError(
            self.service_name,
            "branch-protect set (Azure DevOps uses policy configurations)",
        )

    def remove_branch_protection(self, branch: str) -> None:
        raise NotSupportedError(
            self.service_name,
            "branch-protect remove (Azure DevOps uses policy configurations)",
        )

    # --- Organization (Project) ---

    def _org_api_url(self, path: str) -> str:
        """組織レベル API の絶対 URL を構築する。

        Projects API 等はプロジェクト配下ではなく組織直下のエンドポイントを使用する。
        base_url: https://dev.azure.com/{org}/{project}/_apis
        必要:     https://dev.azure.com/{org}/_apis{path}
        """
        base: str = self._client.base_url
        # /{project}/_apis を /_apis に置換
        project_segment = f"/{quote(self._project, safe='')}"
        idx = base.find(project_segment + "/_apis")
        if idx >= 0:
            return base[:idx] + "/_apis" + path
        return base + path

    def list_organizations(self, *, limit: int = 30) -> list[Organization]:
        url = self._org_api_url("/projects")
        resp = self._client.get_absolute(url, params={"$top": str(limit), "api-version": "7.1"})
        data = resp.json()
        results = data.get("value", [])
        return [self._to_organization(d) for d in results]

    def get_organization(self, name: str) -> Organization:
        url = self._org_api_url(f"/projects/{quote(name, safe='')}")
        resp = self._client.get_absolute(url, params={"api-version": "7.1"})
        return self._to_organization(resp.json())

    def list_org_members(self, name: str, *, limit: int = 30) -> list[str]:
        raise NotSupportedError(
            self.service_name,
            "org members (Azure DevOps uses teams for member management)",
        )

    def list_org_repos(self, name: str, *, limit: int = 30) -> list[Repository]:
        results = paginate_top_skip(
            self._client,
            "/git/repositories",
            limit=0,
            result_key="value",
        )
        filtered = [r for r in results if (r.get("project") or {}).get("name") == name]
        return [self._to_repository(r, name) for r in filtered[: limit if limit > 0 else None]]

    def _to_organization(self, data: dict) -> Organization:
        try:
            name = data.get("name") or ""
            # _links.web.href を優先し、なければ dev.azure.com URL を構築
            web_url = ""
            links = data.get("_links") or {}
            web = links.get("web") or {}
            if web.get("href"):
                web_url = web["href"]
            elif name:
                web_url = f"https://dev.azure.com/{self._org}/{name}"
            return Organization(
                name=name,
                display_name=name,
                description=data.get("description"),
                url=web_url,
            )
        except (KeyError, TypeError, AttributeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    # --- Browse ---

    def get_web_url(self, resource: str = "repo", number: int | None = None) -> str:
        base = f"https://dev.azure.com/{self._org}/{self._project}/_git/{self._repo}"
        if resource == "pr":
            return f"{base}/pullrequest/{number}"
        if resource == "issue":
            return f"https://dev.azure.com/{self._org}/{self._project}/_workitems?id={number}"
        if resource == "settings":
            return f"https://dev.azure.com/{self._org}/{self._project}/_settings/repositories"
        return base

    # --- Search ---

    def search_repositories(self, query: str, *, limit: int = 30) -> list[Repository]:
        # AzDO でリポジトリ検索は /git/repositories でフィルタ
        results = paginate_top_skip(
            self._client,
            "/git/repositories",
            limit=0,
            result_key="value",
        )
        filtered = [r for r in results if query.lower() in r.get("name", "").lower()]
        return [
            self._to_repository(r, self._project) for r in filtered[: limit if limit > 0 else None]
        ]

    def search_issues(self, query: str, *, limit: int = 30) -> list[Issue]:
        # WIQL を使って検索
        wiql = f"SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = '{_wiql_escape(self._project)}' AND [System.Title] CONTAINS '{_wiql_escape(query)}'"  # nosec B608
        wiql_params = {"$top": limit} if limit > 0 else {"$top": 200}
        wiql_resp = self._client.post(
            f"{self._wit_path()}/wiql",
            json={"query": wiql},
            params=wiql_params,
        )
        wiql_body = wiql_resp.json()
        if not isinstance(wiql_body, dict):
            from gfo.exceptions import GfoError

            raise GfoError(f"Unexpected API response: {type(wiql_body)}")
        try:
            ids = [wi["id"] for wi in wiql_body.get("workItems", [])]
        except (KeyError, TypeError) as e:
            from gfo.exceptions import GfoError

            raise GfoError(f"Unexpected API response: {e}") from e
        if not ids:
            return []
        ids_str = ",".join(str(x) for x in ids[: limit if limit > 0 else None])
        resp = self._client.get(
            f"{self._wit_path()}/workitems",
            params={"ids": ids_str, "$expand": "None"},
        )
        batch_body = resp.json()
        if not isinstance(batch_body, dict):
            from gfo.exceptions import GfoError

            raise GfoError(f"Unexpected API response: {type(batch_body)}")
        return [self._to_issue(item) for item in batch_body.get("value", [])]

    # --- Issue Dependencies (Work Item Links) ---

    def list_issue_dependencies(self, number):
        resp = self._client.get(
            f"{self._wit_path()}/workitems/{number}", params={"$expand": "relations"}
        )
        data = resp.json()
        deps = []
        for rel in data.get("relations") or []:
            if "System.LinkTypes.Dependency" in (rel.get("rel") or ""):
                url = rel.get("url") or ""
                dep_id = int(url.rsplit("/", 1)[-1]) if "/" in url else 0
                if dep_id:
                    dep = self.get_issue(dep_id)
                    deps.append(dep)
        return deps

    def add_issue_dependency(self, number, depends_on):
        parsed = urlparse(self._client.base_url)
        base = f"{parsed.scheme}://{parsed.hostname}"
        if parsed.port:
            base += f":{parsed.port}"
        target_url = f"{base}/{self._org}/{self._project}/_apis/wit/workitems/{depends_on}"
        patch = [
            {
                "op": "add",
                "path": "/relations/-",
                "value": {"rel": "System.LinkTypes.Dependency-Forward", "url": target_url},
            }
        ]
        self._client.patch(
            f"{self._wit_path()}/workitems/{number}",
            json=patch,
            headers={"Content-Type": "application/json-patch+json"},
        )

    def remove_issue_dependency(self, number, depends_on):
        resp = self._client.get(
            f"{self._wit_path()}/workitems/{number}", params={"$expand": "relations"}
        )
        data = resp.json()
        for i, rel in enumerate(data.get("relations") or []):
            if "System.LinkTypes.Dependency" in (rel.get("rel") or ""):
                url = rel.get("url") or ""
                dep_id = int(url.rsplit("/", 1)[-1]) if "/" in url else 0
                if dep_id == depends_on:
                    patch = [{"op": "remove", "path": f"/relations/{i}"}]
                    self._client.patch(
                        f"{self._wit_path()}/workitems/{number}",
                        json=patch,
                        headers={"Content-Type": "application/json-patch+json"},
                    )
                    return

    # --- Issue Timeline (Work Item Updates) ---

    def get_issue_timeline(self, number, *, limit=30):
        resp = self._client.get(f"{self._wit_path()}/workitems/{number}/updates")
        updates = resp.json().get("value") or []
        events = []
        for u in updates[:limit]:
            fields = u.get("fields") or {}
            detail_parts = []
            for field_name, change in fields.items():
                new_val = change.get("newValue") or ""
                if new_val:
                    detail_parts.append(f"{field_name}: {new_val}")
            if detail_parts:
                events.append(
                    TimelineEvent(
                        id=u.get("id") or 0,
                        event="updated",
                        actor=(u.get("revisedBy") or {}).get("displayName") or "",
                        created_at=(
                            u.get("revisedDate")
                            or u.get("fields", {}).get("System.ChangedDate", {}).get("newValue")
                            or ""
                        ),
                        detail="; ".join(detail_parts[:3]),
                    )
                )
        return events

    # --- Search PRs ---

    def search_pull_requests(self, query, *, state=None, limit=30):
        params = {"searchCriteria.includeLinks": "false"}
        if state and state != "all":
            api_state = _PR_STATE_TO_API.get(state, state)
            params["searchCriteria.status"] = api_state
        results = paginate_top_skip(
            self._client, f"{self._git_path()}/pullrequests", params=params, limit=limit
        )
        prs = [self._to_pull_request(r) for r in results]
        if query:
            query_lower = query.lower()
            prs = [
                p
                for p in prs
                if query_lower in p.title.lower() or (p.body and query_lower in p.body.lower())
            ]
        return prs

    # --- Search Commits ---

    def search_commits(self, query, *, author=None, since=None, until=None, limit=30):
        params = {}
        if author:
            params["searchCriteria.author"] = author
        if since:
            params["searchCriteria.fromDate"] = since
        if until:
            params["searchCriteria.toDate"] = until
        results = paginate_top_skip(
            self._client, f"{self._git_path()}/commits", params=params, limit=limit
        )
        commits = [
            Commit(
                sha=c.get("commitId") or "",
                message=c.get("comment") or "",
                author=(c.get("author") or {}).get("name") or "",
                url=c.get("remoteUrl") or c.get("url") or "",
                created_at=(c.get("author") or {}).get("date") or "",
            )
            for c in results
        ]
        if query:
            query_lower = query.lower()
            commits = [c for c in commits if query_lower in c.message.lower()]
        return commits

    # --- Time Tracking (Completed Work) ---

    def add_time_entry(self, issue_number, duration):
        hours = duration / 3600
        patch = [
            {"op": "add", "path": "/fields/Microsoft.VSTS.Scheduling.CompletedWork", "value": hours}
        ]
        self._client.patch(
            f"{self._wit_path()}/workitems/{issue_number}",
            json=patch,
            headers={"Content-Type": "application/json-patch+json"},
        )
        return TimeEntry(id=0, user="", duration=duration, created_at="")
