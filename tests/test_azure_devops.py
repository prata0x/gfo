"""AzureDevOpsAdapter のテスト。"""

from __future__ import annotations

import responses

from gfo.adapter.azure_devops import AzureDevOpsAdapter
from gfo.http import HttpClient

BASE = "https://dev.azure.com/myorg/myproject/_apis"
ORG = "myorg"
PROJECT = "myproject"
REPO = "myrepo"


def _make_adapter() -> AzureDevOpsAdapter:
    client = HttpClient(BASE, auth_header={"Authorization": "Bearer tok"})
    return AzureDevOpsAdapter(client, ORG, REPO, organization=ORG, project_key=PROJECT)


# ── list_issues ──


class TestListIssues:
    @responses.activate
    def test_limit_zero_sends_top_20000(self):
        """limit=0（全件取得）のとき WIQL に $top=20000 を渡す（R38-02）。"""
        wiql_url = f"{BASE}/wit/wiql"
        workitems_url = f"{BASE}/wit/workitems"

        responses.add(
            responses.POST,
            wiql_url,
            json={"workItems": [{"id": 1}, {"id": 2}]},
        )
        responses.add(
            responses.GET,
            workitems_url,
            json={
                "value": [
                    {
                        "id": 1,
                        "fields": {
                            "System.Title": "Issue 1",
                            "System.State": "Active",
                            "System.CreatedBy": {"uniqueName": "alice"},
                            "System.CreatedDate": "2026-01-01T00:00:00Z",
                            "System.ChangedDate": "2026-02-01T00:00:00Z",
                            "System.Tags": "",
                        },
                    },
                    {
                        "id": 2,
                        "fields": {
                            "System.Title": "Issue 2",
                            "System.State": "Active",
                            "System.CreatedBy": {"uniqueName": "bob"},
                            "System.CreatedDate": "2026-01-02T00:00:00Z",
                            "System.ChangedDate": "2026-02-02T00:00:00Z",
                            "System.Tags": "",
                        },
                    },
                ]
            },
        )

        adapter = _make_adapter()
        issues = adapter.list_issues(limit=0)

        assert len(issues) == 2
        # $top=20000 が WIQL リクエストの params に含まれることを確認（$ は %24 にエンコードされる）
        wiql_call = responses.calls[0]
        assert "%24top=20000" in wiql_call.request.url

    @responses.activate
    def test_limit_positive_sends_top_limit(self):
        """limit>0 のとき WIQL に $top=limit を渡す。"""
        wiql_url = f"{BASE}/wit/wiql"

        responses.add(
            responses.POST,
            wiql_url,
            json={"workItems": []},
        )

        adapter = _make_adapter()
        issues = adapter.list_issues(limit=10)

        assert len(issues) == 0
        wiql_call = responses.calls[0]
        assert "%24top=10" in wiql_call.request.url
