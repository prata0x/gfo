"""全アダプターの get_web_url テスト。API 呼び出しなし。"""

from __future__ import annotations

import pytest

from gfo.exceptions import NotSupportedError


class TestGitHubBrowse:
    def test_repo(self, github_adapter):
        assert github_adapter.get_web_url() == "https://github.com/test-owner/test-repo"

    def test_pr(self, github_adapter):
        assert (
            github_adapter.get_web_url("pr", 42)
            == "https://github.com/test-owner/test-repo/pull/42"
        )

    def test_issue(self, github_adapter):
        assert (
            github_adapter.get_web_url("issue", 7)
            == "https://github.com/test-owner/test-repo/issues/7"
        )

    def test_settings(self, github_adapter):
        assert (
            github_adapter.get_web_url("settings")
            == "https://github.com/test-owner/test-repo/settings"
        )


class TestGitLabBrowse:
    def test_repo(self, gitlab_adapter):
        assert gitlab_adapter.get_web_url() == "https://gitlab.com/test-owner/test-repo"

    def test_pr(self, gitlab_adapter):
        assert (
            gitlab_adapter.get_web_url("pr", 42)
            == "https://gitlab.com/test-owner/test-repo/-/merge_requests/42"
        )

    def test_issue(self, gitlab_adapter):
        assert (
            gitlab_adapter.get_web_url("issue", 7)
            == "https://gitlab.com/test-owner/test-repo/-/issues/7"
        )

    def test_settings(self, gitlab_adapter):
        assert (
            gitlab_adapter.get_web_url("settings")
            == "https://gitlab.com/test-owner/test-repo/-/settings/general"
        )


class TestBitbucketBrowse:
    def test_repo(self, bitbucket_adapter):
        assert bitbucket_adapter.get_web_url() == "https://bitbucket.org/test-workspace/test-repo"

    def test_pr(self, bitbucket_adapter):
        assert (
            bitbucket_adapter.get_web_url("pr", 42)
            == "https://bitbucket.org/test-workspace/test-repo/pull-requests/42"
        )

    def test_issue(self, bitbucket_adapter):
        assert (
            bitbucket_adapter.get_web_url("issue", 7)
            == "https://bitbucket.org/test-workspace/test-repo/issues/7"
        )

    def test_settings(self, bitbucket_adapter):
        assert (
            bitbucket_adapter.get_web_url("settings")
            == "https://bitbucket.org/test-workspace/test-repo/admin"
        )


class TestAzureDevOpsBrowse:
    def test_repo(self, azure_devops_adapter):
        assert (
            azure_devops_adapter.get_web_url()
            == "https://dev.azure.com/test-org/test-project/_git/test-repo"
        )

    def test_pr(self, azure_devops_adapter):
        assert (
            azure_devops_adapter.get_web_url("pr", 42)
            == "https://dev.azure.com/test-org/test-project/_git/test-repo/pullrequest/42"
        )

    def test_issue(self, azure_devops_adapter):
        assert (
            azure_devops_adapter.get_web_url("issue", 7)
            == "https://dev.azure.com/test-org/test-project/_workitems?id=7"
        )

    def test_settings(self, azure_devops_adapter):
        assert (
            azure_devops_adapter.get_web_url("settings")
            == "https://dev.azure.com/test-org/test-project/_settings/repositories"
        )


class TestGiteaBrowse:
    def test_repo(self, gitea_adapter):
        assert gitea_adapter.get_web_url() == "https://gitea.example.com/test-owner/test-repo"

    def test_pr(self, gitea_adapter):
        assert (
            gitea_adapter.get_web_url("pr", 42)
            == "https://gitea.example.com/test-owner/test-repo/pulls/42"
        )

    def test_issue(self, gitea_adapter):
        assert (
            gitea_adapter.get_web_url("issue", 7)
            == "https://gitea.example.com/test-owner/test-repo/issues/7"
        )

    def test_settings(self, gitea_adapter):
        assert (
            gitea_adapter.get_web_url("settings")
            == "https://gitea.example.com/test-owner/test-repo/settings"
        )


class TestForgejoBrowse:
    def test_repo(self, forgejo_adapter):
        assert forgejo_adapter.get_web_url() == "https://forgejo.example.com/test-owner/test-repo"

    def test_pr(self, forgejo_adapter):
        assert (
            forgejo_adapter.get_web_url("pr", 42)
            == "https://forgejo.example.com/test-owner/test-repo/pulls/42"
        )

    def test_issue(self, forgejo_adapter):
        assert (
            forgejo_adapter.get_web_url("issue", 7)
            == "https://forgejo.example.com/test-owner/test-repo/issues/7"
        )

    def test_settings(self, forgejo_adapter):
        assert (
            forgejo_adapter.get_web_url("settings")
            == "https://forgejo.example.com/test-owner/test-repo/settings"
        )


class TestGogsBrowse:
    def test_repo(self, gogs_adapter):
        assert gogs_adapter.get_web_url() == "https://gogs.example.com/test-owner/test-repo"

    def test_pr(self, gogs_adapter):
        assert (
            gogs_adapter.get_web_url("pr", 42)
            == "https://gogs.example.com/test-owner/test-repo/pulls/42"
        )

    def test_issue(self, gogs_adapter):
        assert (
            gogs_adapter.get_web_url("issue", 7)
            == "https://gogs.example.com/test-owner/test-repo/issues/7"
        )

    def test_settings(self, gogs_adapter):
        assert (
            gogs_adapter.get_web_url("settings")
            == "https://gogs.example.com/test-owner/test-repo/settings"
        )


class TestGitBucketBrowse:
    def test_repo(self, gitbucket_adapter):
        assert (
            gitbucket_adapter.get_web_url() == "https://gitbucket.example.com/test-owner/test-repo"
        )

    def test_pr(self, gitbucket_adapter):
        assert (
            gitbucket_adapter.get_web_url("pr", 42)
            == "https://gitbucket.example.com/test-owner/test-repo/pulls/42"
        )

    def test_issue(self, gitbucket_adapter):
        assert (
            gitbucket_adapter.get_web_url("issue", 7)
            == "https://gitbucket.example.com/test-owner/test-repo/issues/7"
        )

    def test_settings(self, gitbucket_adapter):
        assert (
            gitbucket_adapter.get_web_url("settings")
            == "https://gitbucket.example.com/test-owner/test-repo/settings"
        )


class TestBacklogBrowse:
    def test_repo(self, backlog_adapter):
        assert backlog_adapter.get_web_url() == "https://example.backlog.com/git/TEST/test-repo"

    def test_pr(self, backlog_adapter):
        assert (
            backlog_adapter.get_web_url("pr", 42)
            == "https://example.backlog.com/git/TEST/test-repo/pullRequests/42"
        )

    def test_issue_not_supported(self, backlog_adapter):
        with pytest.raises(NotSupportedError):
            backlog_adapter.get_web_url("issue", 7)

    def test_settings_not_supported(self, backlog_adapter):
        with pytest.raises(NotSupportedError):
            backlog_adapter.get_web_url("settings")
