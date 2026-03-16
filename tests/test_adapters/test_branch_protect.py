"""全アダプターの BranchProtection テスト。"""

from __future__ import annotations

import json

import pytest
import responses

from gfo.exceptions import NotSupportedError

# --- GitHub ---


class TestGitHubBranchProtect:
    @responses.activate
    def test_get(self, github_adapter):
        responses.add(
            responses.GET,
            "https://api.github.com/repos/test-owner/test-repo/branches/main/protection",
            json={
                "required_pull_request_reviews": {"required_approving_review_count": 2},
                "required_status_checks": {"strict": True, "contexts": ["ci/test"]},
                "enforce_admins": {"enabled": True},
                "restrictions": None,
                "allow_force_pushes": {"enabled": False},
                "allow_deletions": {"enabled": False},
            },
        )
        bp = github_adapter.get_branch_protection("main")
        assert bp.branch == "main"
        assert bp.require_reviews == 2
        assert bp.require_status_checks == ("ci/test",)
        assert bp.enforce_admins is True
        assert bp.allow_force_push is False

    @responses.activate
    def test_set(self, github_adapter):
        # GET 現在値
        responses.add(
            responses.GET,
            "https://api.github.com/repos/test-owner/test-repo/branches/main/protection",
            json={
                "required_pull_request_reviews": None,
                "required_status_checks": None,
                "enforce_admins": {"enabled": False},
                "allow_force_pushes": {"enabled": False},
                "allow_deletions": {"enabled": False},
            },
        )
        # PUT
        responses.add(
            responses.PUT,
            "https://api.github.com/repos/test-owner/test-repo/branches/main/protection",
            json={
                "required_pull_request_reviews": {"required_approving_review_count": 1},
                "required_status_checks": None,
                "enforce_admins": {"enabled": False},
                "allow_force_pushes": {"enabled": False},
                "allow_deletions": {"enabled": False},
            },
        )
        bp = github_adapter.set_branch_protection("main", require_reviews=1)
        assert bp.require_reviews == 1
        req_body = json.loads(responses.calls[1].request.body)
        assert req_body["required_pull_request_reviews"]["required_approving_review_count"] == 1

    @responses.activate
    def test_remove(self, github_adapter):
        responses.add(
            responses.DELETE,
            "https://api.github.com/repos/test-owner/test-repo/branches/main/protection",
            status=204,
        )
        github_adapter.remove_branch_protection("main")

    @responses.activate
    def test_list(self, github_adapter):
        responses.add(
            responses.GET,
            "https://api.github.com/repos/test-owner/test-repo/branches",
            json=[
                {"name": "main", "protected": True},
                {"name": "dev", "protected": False},
            ],
        )
        responses.add(
            responses.GET,
            "https://api.github.com/repos/test-owner/test-repo/branches/main/protection",
            json={
                "required_pull_request_reviews": None,
                "required_status_checks": None,
                "enforce_admins": False,
                "allow_force_pushes": False,
                "allow_deletions": False,
            },
        )
        bps = github_adapter.list_branch_protections()
        assert len(bps) == 1
        assert bps[0].branch == "main"


# --- GitLab ---


class TestGitLabBranchProtect:
    @responses.activate
    def test_list(self, gitlab_adapter):
        responses.add(
            responses.GET,
            "https://gitlab.com/api/v4/projects/test-owner%2Ftest-repo/protected_branches",
            json=[{"name": "main", "allow_force_push": False, "required_approvals": 1}],
        )
        bps = gitlab_adapter.list_branch_protections()
        assert len(bps) == 1
        assert bps[0].branch == "main"
        assert bps[0].require_reviews == 1

    @responses.activate
    def test_get(self, gitlab_adapter):
        responses.add(
            responses.GET,
            "https://gitlab.com/api/v4/projects/test-owner%2Ftest-repo/protected_branches/main",
            json={"name": "main", "allow_force_push": True, "required_approvals": 0},
        )
        bp = gitlab_adapter.get_branch_protection("main")
        assert bp.allow_force_push is True

    @responses.activate
    def test_set(self, gitlab_adapter):
        responses.add(
            responses.POST,
            "https://gitlab.com/api/v4/projects/test-owner%2Ftest-repo/protected_branches",
            json={"name": "main", "allow_force_push": False, "required_approvals": 2},
        )
        bp = gitlab_adapter.set_branch_protection("main", require_reviews=2)
        assert bp.require_reviews == 2

    @responses.activate
    def test_remove(self, gitlab_adapter):
        responses.add(
            responses.DELETE,
            "https://gitlab.com/api/v4/projects/test-owner%2Ftest-repo/protected_branches/main",
            status=204,
        )
        gitlab_adapter.remove_branch_protection("main")


# --- Gitea ---


class TestGiteaBranchProtect:
    @responses.activate
    def test_list(self, gitea_adapter):
        responses.add(
            responses.GET,
            "https://gitea.example.com/api/v1/repos/test-owner/test-repo/branch_protections",
            json=[
                {
                    "branch_name": "main",
                    "required_approvals": 1,
                    "status_check_contexts": ["ci"],
                    "enable_force_push": False,
                }
            ],
        )
        bps = gitea_adapter.list_branch_protections()
        assert len(bps) == 1
        assert bps[0].branch == "main"
        assert bps[0].require_status_checks == ("ci",)

    @responses.activate
    def test_get(self, gitea_adapter):
        responses.add(
            responses.GET,
            "https://gitea.example.com/api/v1/repos/test-owner/test-repo/branch_protections/main",
            json={
                "branch_name": "main",
                "required_approvals": 0,
                "status_check_contexts": [],
                "enable_force_push": True,
            },
        )
        bp = gitea_adapter.get_branch_protection("main")
        assert bp.allow_force_push is True

    @responses.activate
    def test_set(self, gitea_adapter):
        responses.add(
            responses.POST,
            "https://gitea.example.com/api/v1/repos/test-owner/test-repo/branch_protections",
            json={
                "branch_name": "main",
                "required_approvals": 2,
                "status_check_contexts": [],
                "enable_force_push": False,
            },
        )
        bp = gitea_adapter.set_branch_protection("main", require_reviews=2)
        assert bp.require_reviews == 2

    @responses.activate
    def test_remove(self, gitea_adapter):
        responses.add(
            responses.DELETE,
            "https://gitea.example.com/api/v1/repos/test-owner/test-repo/branch_protections/main",
            status=204,
        )
        gitea_adapter.remove_branch_protection("main")


# --- Forgejo ---


class TestForgejoBranchProtect:
    @responses.activate
    def test_list(self, forgejo_adapter):
        responses.add(
            responses.GET,
            "https://forgejo.example.com/api/v1/repos/test-owner/test-repo/branch_protections",
            json=[
                {
                    "branch_name": "main",
                    "required_approvals": 0,
                    "status_check_contexts": [],
                    "enable_force_push": False,
                }
            ],
        )
        bps = forgejo_adapter.list_branch_protections()
        assert len(bps) == 1


# --- Bitbucket ---


class TestBitbucketBranchProtect:
    @responses.activate
    def test_list(self, bitbucket_adapter):
        responses.add(
            responses.GET,
            "https://api.bitbucket.org/2.0/repositories/test-workspace/test-repo/branch-restrictions",
            json={
                "values": [
                    {"pattern": "main", "kind": "force", "id": 1},
                    {"pattern": "main", "kind": "delete", "id": 2},
                ],
                "pagelen": 10,
            },
        )
        bps = bitbucket_adapter.list_branch_protections()
        assert len(bps) == 1
        assert bps[0].branch == "main"
        assert bps[0].allow_force_push is False
        assert bps[0].allow_deletions is False

    @responses.activate
    def test_remove(self, bitbucket_adapter):
        responses.add(
            responses.GET,
            "https://api.bitbucket.org/2.0/repositories/test-workspace/test-repo/branch-restrictions",
            json={
                "values": [{"pattern": "main", "kind": "force", "id": 1}],
                "pagelen": 10,
            },
        )
        responses.add(
            responses.DELETE,
            "https://api.bitbucket.org/2.0/repositories/test-workspace/test-repo/branch-restrictions/1",
            status=204,
        )
        bitbucket_adapter.remove_branch_protection("main")


# --- NotSupported ---


class TestBranchProtectNotSupported:
    def test_azure_devops_list(self, azure_devops_adapter):
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.list_branch_protections()

    def test_azure_devops_get(self, azure_devops_adapter):
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.get_branch_protection("main")

    def test_azure_devops_set(self, azure_devops_adapter):
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.set_branch_protection("main")

    def test_azure_devops_remove(self, azure_devops_adapter):
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.remove_branch_protection("main")

    def test_gogs_list(self, gogs_adapter):
        with pytest.raises(NotSupportedError):
            gogs_adapter.list_branch_protections()

    def test_gitbucket_list(self, gitbucket_adapter):
        with pytest.raises(NotSupportedError):
            gitbucket_adapter.list_branch_protections()

    def test_backlog_list(self, backlog_adapter):
        with pytest.raises(NotSupportedError):
            backlog_adapter.list_branch_protections()
