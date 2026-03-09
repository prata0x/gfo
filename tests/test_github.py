"""GitHubAdapter のテスト。"""

from __future__ import annotations

import responses

from gfo.adapter.github import GitHubAdapter
from gfo.http import HttpClient

BASE = "https://api.github.com"
OWNER = "myorg"
REPO = "myrepo"
REPOS_PATH = f"{BASE}/repos/{OWNER}/{REPO}"


def _make_adapter() -> GitHubAdapter:
    client = HttpClient(BASE, auth_header={"Authorization": "Bearer tok"})
    return GitHubAdapter(client, OWNER, REPO)


def _make_label(name: str) -> dict:
    return {"name": name, "color": "ff0000", "description": None}


def _make_milestone(number: int) -> dict:
    return {
        "number": number,
        "title": f"v{number}.0",
        "description": None,
        "state": "open",
        "due_on": None,
    }


# ── list_labels ──


class TestListLabels:
    @responses.activate
    def test_returns_all_labels_when_limit_zero(self):
        """limit=0（デフォルト）で全件取得する（R36-01）。"""
        page1 = [_make_label(f"label-{i}") for i in range(30)]
        page2 = [_make_label(f"label-{i}") for i in range(30, 50)]
        responses.add(
            responses.GET,
            f"{REPOS_PATH}/labels",
            json=page1,
            headers={"Link": f'<{REPOS_PATH}/labels?page=2>; rel="next"'},
        )
        responses.add(
            responses.GET,
            f"{REPOS_PATH}/labels?page=2",
            json=page2,
        )

        adapter = _make_adapter()
        labels = adapter.list_labels()

        assert len(labels) == 50
        assert labels[0].name == "label-0"
        assert labels[49].name == "label-49"

    @responses.activate
    def test_respects_limit(self):
        """limit を指定すると指定件数で打ち切る（R36-01）。"""
        page1 = [_make_label(f"label-{i}") for i in range(30)]
        responses.add(
            responses.GET,
            f"{REPOS_PATH}/labels",
            json=page1,
            headers={"Link": f'<{REPOS_PATH}/labels?page=2>; rel="next"'},
        )

        adapter = _make_adapter()
        labels = adapter.list_labels(limit=10)

        assert len(labels) == 10
        # 2ページ目は取得されていない
        assert len(responses.calls) == 1


# ── list_milestones ──


class TestListMilestones:
    @responses.activate
    def test_returns_all_milestones_when_limit_zero(self):
        """limit=0（デフォルト）で全件取得する（R36-01）。"""
        page1 = [_make_milestone(i) for i in range(1, 31)]
        page2 = [_make_milestone(i) for i in range(31, 51)]
        responses.add(
            responses.GET,
            f"{REPOS_PATH}/milestones",
            json=page1,
            headers={"Link": f'<{REPOS_PATH}/milestones?page=2>; rel="next"'},
        )
        responses.add(
            responses.GET,
            f"{REPOS_PATH}/milestones?page=2",
            json=page2,
        )

        adapter = _make_adapter()
        milestones = adapter.list_milestones()

        assert len(milestones) == 50
        assert milestones[0].number == 1
        assert milestones[49].number == 50

    @responses.activate
    def test_respects_limit(self):
        """limit を指定すると指定件数で打ち切る（R36-01）。"""
        page1 = [_make_milestone(i) for i in range(1, 31)]
        responses.add(
            responses.GET,
            f"{REPOS_PATH}/milestones",
            json=page1,
            headers={"Link": f'<{REPOS_PATH}/milestones?page=2>; rel="next"'},
        )

        adapter = _make_adapter()
        milestones = adapter.list_milestones(limit=5)

        assert len(milestones) == 5
        assert len(responses.calls) == 1
