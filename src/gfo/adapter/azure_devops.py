"""Azure DevOps アダプター。GitServiceAdapter の全メソッドを Azure DevOps REST API v7.1 で実装する。"""

from __future__ import annotations

from urllib.parse import quote

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
from gfo.exceptions import GfoError, NotSupportedError
from gfo.http import paginate_top_skip

import json as _json


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
        return ref[len("refs/heads/"):]
    return ref


@register("azure-devops")
class AzureDevOpsAdapter(GitServiceAdapter):
    service_name = "Azure DevOps"

    def __init__(self, client, owner: str, repo: str, *, organization: str, project_key: str, **kwargs):
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
                url=(f"{data['repository']['webUrl']}/pullrequest/{data['pullRequestId']}"
                     if (data.get("repository") or {}).get("webUrl") else data.get("url", "")),
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
            self._client, f"{self._git_path()}/pullrequests",
            params=params, limit=limit, result_key="value",
        )
        return [self._to_pull_request(r) for r in results]

    def create_pull_request(self, *, title: str, body: str = "",
                            base: str, head: str,
                            draft: bool = False) -> PullRequest:
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

    def get_pr_checkout_refspec(self, number: int, *,
                                pr: PullRequest | None = None) -> str:
        return f"refs/pull/{number}/head"

    # --- Issue (Work Item) ---

    def list_issues(self, *, state: str = "open",
                    assignee: str | None = None,
                    label: str | None = None,
                    limit: int = 30) -> list[Issue]:
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
            batch_ids = ids[i:i + 200]
            ids_str = ",".join(str(x) for x in batch_ids)
            resp = self._client.get(
                f"{self._wit_path()}/workitems",
                params={"ids": ids_str, "$expand": "None"},
            )
            batch_body = resp.json()
            if not isinstance(batch_body, dict):
                raise GfoError(f"Unexpected API response from workitems endpoint: {type(batch_body)}")
            for item in batch_body.get("value", []):
                results.append(self._to_issue(item))

        return results[:limit] if limit > 0 else results

    def create_issue(self, *, title: str, body: str = "",
                     assignee: str | None = None,
                     label: str | None = None,
                     work_item_type: str = "Task",
                     **kwargs) -> Issue:
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

    def delete_issue(self, number: int) -> None:
        self._client.delete(f"{self._wit_path()}/workitems/{number}")

    # --- Repository ---

    def list_repositories(self, *, owner: str | None = None,
                          limit: int = 30) -> list[Repository]:
        if owner is not None:
            raise NotSupportedError(
                self.service_name,
                "filtering repositories by owner "
                "(repositories are scoped to the configured project)",
            )
        results = paginate_top_skip(
            self._client, "/git/repositories",
            limit=limit, result_key="value",
        )
        return [self._to_repository(r, self._project) for r in results]

    def create_repository(self, *, name: str, private: bool = False,
                          description: str = "") -> Repository:
        payload = {"name": name, "project": {"id": self._project}}
        resp = self._client.post("/git/repositories", json=payload)
        return self._to_repository(resp.json(), self._project)

    def get_repository(self, owner: str | None = None,
                       name: str | None = None) -> Repository:
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

    # --- NotSupported ---

    def list_releases(self, *, limit: int = 30) -> list[Release]:
        raise NotSupportedError(self.service_name, "releases")

    def create_release(self, *, tag: str, title: str = "",
                       notes: str = "", draft: bool = False,
                       prerelease: bool = False) -> Release:
        raise NotSupportedError(self.service_name, "releases")

    def list_labels(self, *, limit: int = 0) -> list[Label]:
        raise NotSupportedError(self.service_name, "labels")

    def create_label(self, *, name: str, color: str | None = None,
                     description: str | None = None) -> Label:
        raise NotSupportedError(self.service_name, "labels")

    def list_milestones(self, *, limit: int = 0) -> list[Milestone]:
        raise NotSupportedError(self.service_name, "milestones")

    def create_milestone(self, *, title: str,
                         description: str | None = None,
                         due_date: str | None = None) -> Milestone:
        raise NotSupportedError(self.service_name, "milestones")
