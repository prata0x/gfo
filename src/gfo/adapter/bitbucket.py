"""Bitbucket Cloud アダプター。GitServiceAdapter の全メソッドを Bitbucket REST API v2 で実装する。"""

from __future__ import annotations

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
from urllib.parse import quote

from gfo.exceptions import GfoError, NotSupportedError
from gfo.http import paginate_response_body


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
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_issue(data: dict) -> Issue:
        try:
            raw_state = data["state"]
            state = "open" if raw_state in ("new", "open") else "closed"

            assignee = data.get("assignee")
            nickname = assignee.get("nickname") if isinstance(assignee, dict) else None
            assignees = [nickname] if nickname else []

            return Issue(
                number=data["id"],
                title=data["title"],
                body=data.get("content", {}).get("raw"),
                state=state,
                author=data["reporter"]["nickname"],
                assignees=assignees,
                labels=[],
                url=data["links"]["html"]["href"],
                created_at=data["created_on"],
                updated_at=data.get("updated_on"),
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    @staticmethod
    def _to_repository(data: dict) -> Repository:
        try:
            clone_url = ""
            for link in data.get("links", {}).get("clone", []):
                if link.get("name") == "https":
                    clone_url = link["href"]
                    break

            return Repository(
                name=data["slug"],
                full_name=data["full_name"],
                description=data.get("description"),
                private=data.get("is_private", False),
                default_branch=data.get("mainbranch", {}).get("name") if data.get("mainbranch") else None,
                clone_url=clone_url,
                url=data["links"]["html"]["href"],
            )
        except (KeyError, TypeError) as e:
            raise GfoError(f"Unexpected API response: missing field {e}") from e

    # --- PR ---

    def list_pull_requests(self, *, state: str = "open", limit: int = 30) -> list[PullRequest]:
        state_map = {"open": "OPEN", "closed": "DECLINED", "merged": "MERGED"}
        params: dict = {}
        if state != "all":
            params["state"] = state_map.get(state, state.upper())
        results = paginate_response_body(
            self._client, f"{self._repos_path()}/pullrequests",
            params=params, limit=limit,
        )
        return [self._to_pull_request(r) for r in results]

    def create_pull_request(self, *, title: str, body: str = "",
                            base: str, head: str,
                            draft: bool = False) -> PullRequest:
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
        self._client.put(
            f"{self._repos_path()}/pullrequests/{number}",
            json={"state": "DECLINED"},
        )

    def get_pr_checkout_refspec(self, number: int, *,
                                pr: PullRequest | None = None) -> str:
        if pr is None:
            pr = self.get_pull_request(number)
        return pr.source_branch

    # --- Issue ---

    def list_issues(self, *, state: str = "open",
                    assignee: str | None = None,
                    label: str | None = None,
                    limit: int = 30) -> list[Issue]:
        conditions: list[str] = []
        if state == "open":
            conditions.append('(state="new" OR state="open")')
        elif state != "all":
            conditions.append(f'state="{state}"')
        if assignee is not None:
            escaped = assignee.replace('"', '\\"')
            conditions.append(f'assignee.nickname="{escaped}"')
        params: dict = {}
        if conditions:
            params["q"] = " AND ".join(conditions)
        results = paginate_response_body(
            self._client, f"{self._repos_path()}/issues",
            params=params, limit=limit,
        )
        return [self._to_issue(r) for r in results]

    def create_issue(self, *, title: str, body: str = "",
                     assignee: str | None = None,
                     label: str | None = None, **kwargs) -> Issue:
        payload: dict = {"title": title, "content": {"raw": body}}
        if assignee is not None:
            payload["assignee"] = {"nickname": assignee}
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

    # --- Repository ---

    def list_repositories(self, *, owner: str | None = None,
                          limit: int = 30) -> list[Repository]:
        o = owner if owner is not None else self._owner
        results = paginate_response_body(
            self._client, f"/repositories/{quote(o, safe='')}", limit=limit,
        )
        return [self._to_repository(r) for r in results]

    def create_repository(self, *, name: str, private: bool = False,
                          description: str = "") -> Repository:
        payload = {"scm": "git", "is_private": private, "description": description}
        resp = self._client.post(f"/repositories/{quote(self._owner, safe='')}/{quote(name, safe='')}", json=payload)
        return self._to_repository(resp.json())

    def get_repository(self, owner: str | None = None,
                       name: str | None = None) -> Repository:
        o = owner if owner is not None else self._owner
        n = name if name is not None else self._repo
        resp = self._client.get(f"/repositories/{quote(o, safe='')}/{quote(n, safe='')}")
        return self._to_repository(resp.json())

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
