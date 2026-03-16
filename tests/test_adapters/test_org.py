"""全アダプターの Organization テスト。"""

from __future__ import annotations

import pytest
import responses

from gfo.exceptions import NotSupportedError

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


# --- Azure DevOps ---


class TestAzureDevOpsOrg:
    @responses.activate
    def test_list(self, azure_devops_adapter):
        responses.add(
            responses.GET,
            "https://dev.azure.com/test-org/test-project/_apis/projects",
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
            "https://dev.azure.com/test-org/test-project/_apis/projects/MyProject",
            json={
                "name": "MyProject",
                "description": "desc",
                "url": "https://dev.azure.com/org/MyProject",
            },
        )
        org = azure_devops_adapter.get_organization("MyProject")
        assert org.name == "MyProject"

    def test_members_not_supported(self, azure_devops_adapter):
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.list_org_members("MyProject")


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
