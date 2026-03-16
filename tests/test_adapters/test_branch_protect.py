"""全アダプターの BranchProtection テスト。"""

from __future__ import annotations

import json

import pytest
import responses

from gfo.exceptions import AuthenticationError, NotFoundError, NotSupportedError

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

    @responses.activate
    def test_list_empty(self, github_adapter):
        responses.add(
            responses.GET,
            "https://api.github.com/repos/test-owner/test-repo/branches",
            json=[],
        )
        assert github_adapter.list_branch_protections() == []

    @responses.activate
    def test_get_404(self, github_adapter):
        responses.add(
            responses.GET,
            "https://api.github.com/repos/test-owner/test-repo/branches/main/protection",
            status=404,
        )
        with pytest.raises(NotFoundError):
            github_adapter.get_branch_protection("main")

    @responses.activate
    def test_remove_403(self, github_adapter):
        responses.add(
            responses.DELETE,
            "https://api.github.com/repos/test-owner/test-repo/branches/main/protection",
            status=403,
        )
        with pytest.raises(AuthenticationError):
            github_adapter.remove_branch_protection("main")


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

    @responses.activate
    def test_list_empty(self, gitlab_adapter):
        responses.add(
            responses.GET,
            "https://gitlab.com/api/v4/projects/test-owner%2Ftest-repo/protected_branches",
            json=[],
        )
        assert gitlab_adapter.list_branch_protections() == []

    @responses.activate
    def test_get_404(self, gitlab_adapter):
        responses.add(
            responses.GET,
            "https://gitlab.com/api/v4/projects/test-owner%2Ftest-repo/protected_branches/main",
            status=404,
        )
        with pytest.raises(NotFoundError):
            gitlab_adapter.get_branch_protection("main")

    @responses.activate
    def test_remove_403(self, gitlab_adapter):
        responses.add(
            responses.DELETE,
            "https://gitlab.com/api/v4/projects/test-owner%2Ftest-repo/protected_branches/main",
            status=403,
        )
        with pytest.raises(AuthenticationError):
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

    @responses.activate
    def test_list_empty(self, gitea_adapter):
        responses.add(
            responses.GET,
            "https://gitea.example.com/api/v1/repos/test-owner/test-repo/branch_protections",
            json=[],
        )
        assert gitea_adapter.list_branch_protections() == []

    @responses.activate
    def test_get_404(self, gitea_adapter):
        responses.add(
            responses.GET,
            "https://gitea.example.com/api/v1/repos/test-owner/test-repo/branch_protections/main",
            status=404,
        )
        with pytest.raises(NotFoundError):
            gitea_adapter.get_branch_protection("main")

    @responses.activate
    def test_remove_403(self, gitea_adapter):
        responses.add(
            responses.DELETE,
            "https://gitea.example.com/api/v1/repos/test-owner/test-repo/branch_protections/main",
            status=403,
        )
        with pytest.raises(AuthenticationError):
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

    @responses.activate
    def test_get(self, forgejo_adapter):
        responses.add(
            responses.GET,
            "https://forgejo.example.com/api/v1/repos/test-owner/test-repo/branch_protections/main",
            json={
                "branch_name": "main",
                "required_approvals": 1,
                "status_check_contexts": ["ci"],
                "enable_force_push": False,
            },
        )
        bp = forgejo_adapter.get_branch_protection("main")
        assert bp.branch == "main"
        assert bp.require_reviews == 1
        assert bp.allow_force_push is False

    @responses.activate
    def test_remove(self, forgejo_adapter):
        responses.add(
            responses.DELETE,
            "https://forgejo.example.com/api/v1/repos/test-owner/test-repo/branch_protections/main",
            status=204,
        )
        forgejo_adapter.remove_branch_protection("main")

    @responses.activate
    def test_list_empty(self, forgejo_adapter):
        responses.add(
            responses.GET,
            "https://forgejo.example.com/api/v1/repos/test-owner/test-repo/branch_protections",
            json=[],
        )
        assert forgejo_adapter.list_branch_protections() == []

    @responses.activate
    def test_get_404(self, forgejo_adapter):
        responses.add(
            responses.GET,
            "https://forgejo.example.com/api/v1/repos/test-owner/test-repo/branch_protections/main",
            status=404,
        )
        with pytest.raises(NotFoundError):
            forgejo_adapter.get_branch_protection("main")


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
    def test_get(self, bitbucket_adapter):
        """get_branch_protection は全制限を取得し force/delete でフィルタする。"""
        responses.add(
            responses.GET,
            "https://api.bitbucket.org/2.0/repositories/test-workspace/test-repo/branch-restrictions",
            json={
                "values": [
                    {"pattern": "main", "kind": "force", "id": 1},
                    {"pattern": "main", "kind": "delete", "id": 2},
                    {"pattern": "develop", "kind": "force", "id": 3},
                ],
                "pagelen": 10,
            },
        )
        bp = bitbucket_adapter.get_branch_protection("main")
        assert bp.branch == "main"
        assert bp.allow_force_push is False
        assert bp.allow_deletions is False

    @responses.activate
    def test_get_no_restrictions(self, bitbucket_adapter):
        """制限がないブランチでは force_push / deletions ともに許可。"""
        responses.add(
            responses.GET,
            "https://api.bitbucket.org/2.0/repositories/test-workspace/test-repo/branch-restrictions",
            json={"values": [], "pagelen": 10},
        )
        bp = bitbucket_adapter.get_branch_protection("main")
        assert bp.allow_force_push is True
        assert bp.allow_deletions is True

    @responses.activate
    def test_set(self, bitbucket_adapter):
        """set_branch_protection は force/delete ルールを POST し結果を get で取得。"""
        # POST force
        responses.add(
            responses.POST,
            "https://api.bitbucket.org/2.0/repositories/test-workspace/test-repo/branch-restrictions",
            json={"pattern": "main", "kind": "force", "id": 10},
            status=201,
        )
        # POST delete
        responses.add(
            responses.POST,
            "https://api.bitbucket.org/2.0/repositories/test-workspace/test-repo/branch-restrictions",
            json={"pattern": "main", "kind": "delete", "id": 11},
            status=201,
        )
        # get_branch_protection 内で GET
        responses.add(
            responses.GET,
            "https://api.bitbucket.org/2.0/repositories/test-workspace/test-repo/branch-restrictions",
            json={
                "values": [
                    {"pattern": "main", "kind": "force", "id": 10},
                    {"pattern": "main", "kind": "delete", "id": 11},
                ],
                "pagelen": 10,
            },
        )
        bp = bitbucket_adapter.set_branch_protection(
            "main", allow_force_push=False, allow_deletions=False
        )
        assert bp.allow_force_push is False
        assert bp.allow_deletions is False
        # POST が 2 回呼ばれたことを確認
        post_calls = [c for c in responses.calls if c.request.method == "POST"]
        assert len(post_calls) == 2

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

    @responses.activate
    def test_list_empty(self, bitbucket_adapter):
        responses.add(
            responses.GET,
            "https://api.bitbucket.org/2.0/repositories/test-workspace/test-repo/branch-restrictions",
            json={"values": [], "pagelen": 10},
        )
        assert bitbucket_adapter.list_branch_protections() == []

    @responses.activate
    def test_list_404(self, bitbucket_adapter):
        responses.add(
            responses.GET,
            "https://api.bitbucket.org/2.0/repositories/test-workspace/test-repo/branch-restrictions",
            status=404,
        )
        with pytest.raises(NotFoundError):
            bitbucket_adapter.list_branch_protections()

    @responses.activate
    def test_list_403(self, bitbucket_adapter):
        responses.add(
            responses.GET,
            "https://api.bitbucket.org/2.0/repositories/test-workspace/test-repo/branch-restrictions",
            status=403,
        )
        with pytest.raises(AuthenticationError):
            bitbucket_adapter.list_branch_protections()


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
