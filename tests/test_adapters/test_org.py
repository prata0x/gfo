"""全アダプターの Organization テスト。"""

from __future__ import annotations

import pytest
import responses

from gfo.exceptions import AuthenticationError, NotFoundError, NotSupportedError

# --- ヘルパー ---


def _github_org_data(**overrides):
    data = {
        "login": "my-org",
        "name": "My Organization",
        "description": "An org",
        "html_url": "https://github.com/my-org",
    }
    data.update(overrides)
    return data


def _github_repo_data(**overrides):
    data = {
        "name": "repo1",
        "full_name": "my-org/repo1",
        "description": "A repo",
        "private": False,
        "default_branch": "main",
        "clone_url": "https://github.com/my-org/repo1.git",
        "html_url": "https://github.com/my-org/repo1",
    }
    data.update(overrides)
    return data


def _gitlab_group_data(**overrides):
    data = {
        "id": 1,
        "path": "my-group",
        "full_name": "My Group",
        "name": "My Group",
        "description": "A group",
        "web_url": "https://gitlab.com/groups/my-group",
    }
    data.update(overrides)
    return data


def _gitlab_project_data(**overrides):
    data = {
        "path": "proj1",
        "path_with_namespace": "my-group/proj1",
        "description": "A project",
        "visibility": "public",
        "default_branch": "main",
        "http_url_to_repo": "https://gitlab.com/my-group/proj1.git",
        "web_url": "https://gitlab.com/my-group/proj1",
    }
    data.update(overrides)
    return data


def _bitbucket_workspace_data(**overrides):
    data = {
        "workspace": {
            "slug": "my-ws",
            "name": "My Workspace",
            "links": {"html": {"href": "https://bitbucket.org/my-ws"}},
        },
    }
    data.update(overrides)
    return data


def _gitea_org_data(**overrides):
    data = {
        "username": "my-org",
        "full_name": "My Organization",
        "description": "An org",
        "website": "https://gitea.example.com/my-org",
    }
    data.update(overrides)
    return data


# --- GitHub ---


class TestGitHubOrg:
    @responses.activate
    def test_list(self, github_adapter):
        responses.add(
            responses.GET,
            "https://api.github.com/user/orgs",
            json=[_github_org_data()],
        )
        orgs = github_adapter.list_organizations()
        assert len(orgs) == 1
        assert orgs[0].name == "my-org"
        assert orgs[0].display_name == "My Organization"

    @responses.activate
    def test_view(self, github_adapter):
        responses.add(
            responses.GET,
            "https://api.github.com/orgs/my-org",
            json=_github_org_data(),
        )
        org = github_adapter.get_organization("my-org")
        assert org.name == "my-org"
        assert org.description == "An org"

    @responses.activate
    def test_members(self, github_adapter):
        responses.add(
            responses.GET,
            "https://api.github.com/orgs/my-org/members",
            json=[{"login": "alice"}, {"login": "bob"}],
        )
        members = github_adapter.list_org_members("my-org")
        assert members == ["alice", "bob"]

    @responses.activate
    def test_repos(self, github_adapter):
        responses.add(
            responses.GET,
            "https://api.github.com/orgs/my-org/repos",
            json=[_github_repo_data()],
        )
        repos = github_adapter.list_org_repos("my-org")
        assert len(repos) == 1
        assert repos[0].name == "repo1"

    @responses.activate
    def test_list_empty(self, github_adapter):
        responses.add(responses.GET, "https://api.github.com/user/orgs", json=[])
        assert github_adapter.list_organizations() == []

    @responses.activate
    def test_view_404(self, github_adapter):
        responses.add(responses.GET, "https://api.github.com/orgs/missing", status=404)
        with pytest.raises(NotFoundError):
            github_adapter.get_organization("missing")

    @responses.activate
    def test_list_403(self, github_adapter):
        responses.add(responses.GET, "https://api.github.com/user/orgs", status=403)
        with pytest.raises(AuthenticationError):
            github_adapter.list_organizations()


# --- GitLab ---


class TestGitLabOrg:
    @responses.activate
    def test_list(self, gitlab_adapter):
        responses.add(
            responses.GET,
            "https://gitlab.com/api/v4/groups",
            json=[_gitlab_group_data()],
        )
        orgs = gitlab_adapter.list_organizations()
        assert len(orgs) == 1
        assert orgs[0].name == "my-group"
        assert orgs[0].display_name == "My Group"

    @responses.activate
    def test_view(self, gitlab_adapter):
        responses.add(
            responses.GET,
            "https://gitlab.com/api/v4/groups/my-group",
            json=_gitlab_group_data(),
        )
        org = gitlab_adapter.get_organization("my-group")
        assert org.name == "my-group"

    @responses.activate
    def test_members(self, gitlab_adapter):
        responses.add(
            responses.GET,
            "https://gitlab.com/api/v4/groups/my-group/members",
            json=[{"username": "alice"}, {"username": "bob"}],
        )
        members = gitlab_adapter.list_org_members("my-group")
        assert members == ["alice", "bob"]

    @responses.activate
    def test_repos(self, gitlab_adapter):
        responses.add(
            responses.GET,
            "https://gitlab.com/api/v4/groups/my-group/projects",
            json=[_gitlab_project_data()],
        )
        repos = gitlab_adapter.list_org_repos("my-group")
        assert len(repos) == 1
        assert repos[0].name == "proj1"

    @responses.activate
    def test_list_empty(self, gitlab_adapter):
        responses.add(responses.GET, "https://gitlab.com/api/v4/groups", json=[])
        assert gitlab_adapter.list_organizations() == []

    @responses.activate
    def test_view_404(self, gitlab_adapter):
        responses.add(
            responses.GET,
            "https://gitlab.com/api/v4/groups/missing",
            status=404,
        )
        with pytest.raises(NotFoundError):
            gitlab_adapter.get_organization("missing")


# --- Bitbucket ---


class TestBitbucketOrg:
    @responses.activate
    def test_list(self, bitbucket_adapter):
        responses.add(
            responses.GET,
            "https://api.bitbucket.org/2.0/user/permissions/workspaces",
            json={"values": [_bitbucket_workspace_data()], "pagelen": 10},
        )
        orgs = bitbucket_adapter.list_organizations()
        assert len(orgs) == 1
        assert orgs[0].name == "my-ws"
        assert orgs[0].display_name == "My Workspace"

    @responses.activate
    def test_view(self, bitbucket_adapter):
        responses.add(
            responses.GET,
            "https://api.bitbucket.org/2.0/workspaces/my-ws",
            json={
                "slug": "my-ws",
                "name": "My Workspace",
                "links": {"html": {"href": "https://bitbucket.org/my-ws"}},
            },
        )
        org = bitbucket_adapter.get_organization("my-ws")
        assert org.name == "my-ws"

    @responses.activate
    def test_members(self, bitbucket_adapter):
        responses.add(
            responses.GET,
            "https://api.bitbucket.org/2.0/workspaces/my-ws/members",
            json={
                "values": [
                    {"user": {"nickname": "alice"}},
                    {"user": {"nickname": "bob"}},
                ],
                "pagelen": 10,
            },
        )
        members = bitbucket_adapter.list_org_members("my-ws")
        assert members == ["alice", "bob"]

    @responses.activate
    def test_repos(self, bitbucket_adapter):
        bb_repo = {
            "slug": "repo1",
            "full_name": "my-ws/repo1",
            "description": "",
            "is_private": False,
            "mainbranch": {"name": "main"},
            "links": {
                "html": {"href": "https://bitbucket.org/my-ws/repo1"},
                "clone": [{"name": "https", "href": "https://bitbucket.org/my-ws/repo1.git"}],
            },
        }
        responses.add(
            responses.GET,
            "https://api.bitbucket.org/2.0/repositories/my-ws",
            json={"values": [bb_repo], "pagelen": 10},
        )
        repos = bitbucket_adapter.list_org_repos("my-ws")
        assert len(repos) == 1
        assert repos[0].name == "repo1"

    @responses.activate
    def test_list_empty(self, bitbucket_adapter):
        responses.add(
            responses.GET,
            "https://api.bitbucket.org/2.0/user/permissions/workspaces",
            json={"values": [], "pagelen": 10},
        )
        assert bitbucket_adapter.list_organizations() == []

    @responses.activate
    def test_view_404(self, bitbucket_adapter):
        responses.add(
            responses.GET,
            "https://api.bitbucket.org/2.0/workspaces/missing",
            status=404,
        )
        with pytest.raises(NotFoundError):
            bitbucket_adapter.get_organization("missing")


# --- Gitea ---


class TestGiteaOrg:
    @responses.activate
    def test_list(self, gitea_adapter):
        responses.add(
            responses.GET,
            "https://gitea.example.com/api/v1/user/orgs",
            json=[_gitea_org_data()],
        )
        orgs = gitea_adapter.list_organizations()
        assert len(orgs) == 1
        assert orgs[0].name == "my-org"

    @responses.activate
    def test_view(self, gitea_adapter):
        responses.add(
            responses.GET,
            "https://gitea.example.com/api/v1/orgs/my-org",
            json=_gitea_org_data(),
        )
        org = gitea_adapter.get_organization("my-org")
        assert org.name == "my-org"

    @responses.activate
    def test_members(self, gitea_adapter):
        responses.add(
            responses.GET,
            "https://gitea.example.com/api/v1/orgs/my-org/members",
            json=[{"login": "alice"}],
        )
        members = gitea_adapter.list_org_members("my-org")
        assert members == ["alice"]

    @responses.activate
    def test_repos(self, gitea_adapter):
        gitea_repo = {
            "name": "repo1",
            "full_name": "my-org/repo1",
            "description": "",
            "private": False,
            "default_branch": "main",
            "clone_url": "https://gitea.example.com/my-org/repo1.git",
            "html_url": "https://gitea.example.com/my-org/repo1",
        }
        responses.add(
            responses.GET,
            "https://gitea.example.com/api/v1/orgs/my-org/repos",
            json=[gitea_repo],
        )
        repos = gitea_adapter.list_org_repos("my-org")
        assert len(repos) == 1

    @responses.activate
    def test_list_empty(self, gitea_adapter):
        responses.add(
            responses.GET,
            "https://gitea.example.com/api/v1/user/orgs",
            json=[],
        )
        assert gitea_adapter.list_organizations() == []

    @responses.activate
    def test_view_404(self, gitea_adapter):
        responses.add(
            responses.GET,
            "https://gitea.example.com/api/v1/orgs/missing",
            status=404,
        )
        with pytest.raises(NotFoundError):
            gitea_adapter.get_organization("missing")


# --- Forgejo ---


class TestForgejoOrg:
    @responses.activate
    def test_list(self, forgejo_adapter):
        responses.add(
            responses.GET,
            "https://forgejo.example.com/api/v1/user/orgs",
            json=[_gitea_org_data()],
        )
        orgs = forgejo_adapter.list_organizations()
        assert len(orgs) == 1

    @responses.activate
    def test_view(self, forgejo_adapter):
        responses.add(
            responses.GET,
            "https://forgejo.example.com/api/v1/orgs/my-org",
            json=_gitea_org_data(),
        )
        org = forgejo_adapter.get_organization("my-org")
        assert org.name == "my-org"
        assert org.display_name == "My Organization"

    @responses.activate
    def test_list_empty(self, forgejo_adapter):
        responses.add(
            responses.GET,
            "https://forgejo.example.com/api/v1/user/orgs",
            json=[],
        )
        assert forgejo_adapter.list_organizations() == []


# --- Gogs ---


class TestGogsOrg:
    @responses.activate
    def test_list(self, gogs_adapter):
        responses.add(
            responses.GET,
            "https://gogs.example.com/api/v1/user/orgs",
            json=[_gitea_org_data()],
        )
        orgs = gogs_adapter.list_organizations()
        assert len(orgs) == 1

    @responses.activate
    def test_view(self, gogs_adapter):
        responses.add(
            responses.GET,
            "https://gogs.example.com/api/v1/orgs/my-org",
            json=_gitea_org_data(),
        )
        org = gogs_adapter.get_organization("my-org")
        assert org.name == "my-org"
        assert org.display_name == "My Organization"

    @responses.activate
    def test_list_empty(self, gogs_adapter):
        responses.add(
            responses.GET,
            "https://gogs.example.com/api/v1/user/orgs",
            json=[],
        )
        assert gogs_adapter.list_organizations() == []


# --- Azure DevOps ---


class TestAzureDevOpsOrg:
    @responses.activate
    def test_list(self, azure_devops_adapter):
        responses.add(
            responses.GET,
            "https://dev.azure.com/test-org/_apis/projects",
            json={
                "value": [
                    {
                        "name": "MyProject",
                        "description": "desc",
                        "url": "https://dev.azure.com/org/MyProject",
                    },
                ],
                "count": 1,
            },
        )
        orgs = azure_devops_adapter.list_organizations()
        assert len(orgs) == 1
        assert orgs[0].name == "MyProject"

    @responses.activate
    def test_view(self, azure_devops_adapter):
        responses.add(
            responses.GET,
            "https://dev.azure.com/test-org/_apis/projects/MyProject",
            json={
                "name": "MyProject",
                "description": "desc",
                "url": "https://dev.azure.com/org/MyProject",
            },
        )
        org = azure_devops_adapter.get_organization("MyProject")
        assert org.name == "MyProject"

    @responses.activate
    def test_repos(self, azure_devops_adapter):
        responses.add(
            responses.GET,
            "https://dev.azure.com/test-org/test-project/_apis/git/repositories",
            json={
                "value": [
                    {
                        "name": "repo1",
                        "project": {"name": "MyProject"},
                        "remoteUrl": "https://dev.azure.com/test-org/MyProject/_git/repo1",
                        "webUrl": "https://dev.azure.com/test-org/MyProject/_git/repo1",
                        "defaultBranch": "refs/heads/main",
                    },
                    {
                        "name": "other-repo",
                        "project": {"name": "OtherProject"},
                        "remoteUrl": "https://dev.azure.com/test-org/OtherProject/_git/other-repo",
                        "webUrl": "https://dev.azure.com/test-org/OtherProject/_git/other-repo",
                        "defaultBranch": "refs/heads/main",
                    },
                ],
                "count": 2,
            },
        )
        repos = azure_devops_adapter.list_org_repos("MyProject")
        assert len(repos) == 1
        assert repos[0].name == "repo1"

    @responses.activate
    def test_list_empty(self, azure_devops_adapter):
        responses.add(
            responses.GET,
            "https://dev.azure.com/test-org/_apis/projects",
            json={"value": [], "count": 0},
        )
        assert azure_devops_adapter.list_organizations() == []

    @responses.activate
    def test_view_404(self, azure_devops_adapter):
        responses.add(
            responses.GET,
            "https://dev.azure.com/test-org/_apis/projects/MissingProject",
            status=404,
        )
        with pytest.raises(NotFoundError):
            azure_devops_adapter.get_organization("MissingProject")

    def test_members_not_supported(self, azure_devops_adapter):
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.list_org_members("MyProject")


# --- GitHub create/delete ---


class TestGitHubOrgCreateDelete:
    @responses.activate
    def test_create(self, github_adapter):
        responses.add(
            responses.POST,
            "https://api.github.com/user/orgs",
            json=_github_org_data(),
            status=201,
        )
        org = github_adapter.create_organization(
            "my-org", display_name="My Organization", description="An org"
        )
        assert org.name == "my-org"
        assert org.display_name == "My Organization"

    @responses.activate
    def test_create_minimal(self, github_adapter):
        responses.add(
            responses.POST,
            "https://api.github.com/user/orgs",
            json=_github_org_data(),
            status=201,
        )
        org = github_adapter.create_organization("my-org")
        assert org.name == "my-org"

    @responses.activate
    def test_create_403(self, github_adapter):
        responses.add(responses.POST, "https://api.github.com/user/orgs", status=403)
        with pytest.raises(AuthenticationError):
            github_adapter.create_organization("my-org")

    @responses.activate
    def test_delete(self, github_adapter):
        responses.add(responses.DELETE, "https://api.github.com/orgs/my-org", status=204)
        github_adapter.delete_organization("my-org")

    @responses.activate
    def test_delete_404(self, github_adapter):
        responses.add(responses.DELETE, "https://api.github.com/orgs/missing", status=404)
        with pytest.raises(NotFoundError):
            github_adapter.delete_organization("missing")


# --- GitLab create/delete ---


class TestGitLabOrgCreateDelete:
    @responses.activate
    def test_create(self, gitlab_adapter):
        responses.add(
            responses.POST,
            "https://gitlab.com/api/v4/groups",
            json=_gitlab_group_data(),
            status=201,
        )
        org = gitlab_adapter.create_organization(
            "my-group", display_name="My Group", description="A group"
        )
        assert org.name == "my-group"

    @responses.activate
    def test_create_minimal(self, gitlab_adapter):
        responses.add(
            responses.POST,
            "https://gitlab.com/api/v4/groups",
            json=_gitlab_group_data(),
            status=201,
        )
        org = gitlab_adapter.create_organization("my-group")
        assert org.name == "my-group"

    @responses.activate
    def test_delete(self, gitlab_adapter):
        responses.add(responses.DELETE, "https://gitlab.com/api/v4/groups/my-group", status=202)
        gitlab_adapter.delete_organization("my-group")

    @responses.activate
    def test_delete_404(self, gitlab_adapter):
        responses.add(responses.DELETE, "https://gitlab.com/api/v4/groups/missing", status=404)
        with pytest.raises(NotFoundError):
            gitlab_adapter.delete_organization("missing")


# --- Gitea create/delete ---


class TestGiteaOrgCreateDelete:
    @responses.activate
    def test_create(self, gitea_adapter):
        responses.add(
            responses.POST,
            "https://gitea.example.com/api/v1/orgs",
            json=_gitea_org_data(),
            status=201,
        )
        org = gitea_adapter.create_organization(
            "my-org", display_name="My Organization", description="An org"
        )
        assert org.name == "my-org"

    @responses.activate
    def test_create_minimal(self, gitea_adapter):
        responses.add(
            responses.POST,
            "https://gitea.example.com/api/v1/orgs",
            json=_gitea_org_data(),
            status=201,
        )
        org = gitea_adapter.create_organization("my-org")
        assert org.name == "my-org"

    @responses.activate
    def test_delete(self, gitea_adapter):
        responses.add(responses.DELETE, "https://gitea.example.com/api/v1/orgs/my-org", status=204)
        gitea_adapter.delete_organization("my-org")

    @responses.activate
    def test_delete_404(self, gitea_adapter):
        responses.add(responses.DELETE, "https://gitea.example.com/api/v1/orgs/missing", status=404)
        with pytest.raises(NotFoundError):
            gitea_adapter.delete_organization("missing")


# --- Forgejo create/delete (inherited from Gitea) ---


class TestForgejoOrgCreateDelete:
    @responses.activate
    def test_create(self, forgejo_adapter):
        responses.add(
            responses.POST,
            "https://forgejo.example.com/api/v1/orgs",
            json=_gitea_org_data(),
            status=201,
        )
        org = forgejo_adapter.create_organization("my-org")
        assert org.name == "my-org"

    @responses.activate
    def test_delete(self, forgejo_adapter):
        responses.add(
            responses.DELETE, "https://forgejo.example.com/api/v1/orgs/my-org", status=204
        )
        forgejo_adapter.delete_organization("my-org")


# --- Gogs create/delete (inherited from Gitea) ---


class TestGogsOrgCreateDelete:
    @responses.activate
    def test_create(self, gogs_adapter):
        responses.add(
            responses.POST,
            "https://gogs.example.com/api/v1/orgs",
            json=_gitea_org_data(),
            status=201,
        )
        org = gogs_adapter.create_organization("my-org")
        assert org.name == "my-org"

    @responses.activate
    def test_delete(self, gogs_adapter):
        responses.add(responses.DELETE, "https://gogs.example.com/api/v1/orgs/my-org", status=204)
        gogs_adapter.delete_organization("my-org")


# --- NotSupported ---


class TestOrgNotSupported:
    def test_gitbucket_list(self, gitbucket_adapter):
        with pytest.raises(NotSupportedError):
            gitbucket_adapter.list_organizations()

    def test_gitbucket_view(self, gitbucket_adapter):
        with pytest.raises(NotSupportedError):
            gitbucket_adapter.get_organization("x")

    def test_gitbucket_members(self, gitbucket_adapter):
        with pytest.raises(NotSupportedError):
            gitbucket_adapter.list_org_members("x")

    def test_gitbucket_repos(self, gitbucket_adapter):
        with pytest.raises(NotSupportedError):
            gitbucket_adapter.list_org_repos("x")

    def test_gitbucket_create(self, gitbucket_adapter):
        with pytest.raises(NotSupportedError):
            gitbucket_adapter.create_organization("x")

    def test_gitbucket_delete(self, gitbucket_adapter):
        with pytest.raises(NotSupportedError):
            gitbucket_adapter.delete_organization("x")

    def test_backlog_list(self, backlog_adapter):
        with pytest.raises(NotSupportedError):
            backlog_adapter.list_organizations()

    def test_backlog_view(self, backlog_adapter):
        with pytest.raises(NotSupportedError):
            backlog_adapter.get_organization("x")

    def test_backlog_members(self, backlog_adapter):
        with pytest.raises(NotSupportedError):
            backlog_adapter.list_org_members("x")

    def test_backlog_repos(self, backlog_adapter):
        with pytest.raises(NotSupportedError):
            backlog_adapter.list_org_repos("x")

    def test_backlog_create(self, backlog_adapter):
        with pytest.raises(NotSupportedError):
            backlog_adapter.create_organization("x")

    def test_backlog_delete(self, backlog_adapter):
        with pytest.raises(NotSupportedError):
            backlog_adapter.delete_organization("x")

    def test_bitbucket_create(self, bitbucket_adapter):
        with pytest.raises(NotSupportedError):
            bitbucket_adapter.create_organization("x")

    def test_bitbucket_delete(self, bitbucket_adapter):
        with pytest.raises(NotSupportedError):
            bitbucket_adapter.delete_organization("x")

    def test_azure_devops_create(self, azure_devops_adapter):
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.create_organization("x")

    def test_azure_devops_delete(self, azure_devops_adapter):
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.delete_organization("x")
