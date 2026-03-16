"""全アダプターの Notification テスト。"""

from __future__ import annotations

import pytest
import responses

from gfo.exceptions import AuthenticationError, NotFoundError, NotSupportedError

# --- ヘルパー ---


def _github_notification_data(**overrides):
    data = {
        "id": "1",
        "reason": "mention",
        "unread": True,
        "subject": {
            "title": "Fix bug",
            "url": "https://api.github.com/repos/owner/repo/issues/1",
            "type": "Issue",
        },
        "repository": {"full_name": "owner/repo"},
        "updated_at": "2024-01-01T00:00:00Z",
    }
    data.update(overrides)
    return data


def _gitlab_todo_data(**overrides):
    data = {
        "id": 1,
        "body": "Review MR !5",
        "target_type": "MergeRequest",
        "state": "pending",
        "project": {"path_with_namespace": "group/proj"},
        "target_url": "https://gitlab.com/group/proj/-/merge_requests/5",
        "updated_at": "2024-01-01T00:00:00Z",
    }
    data.update(overrides)
    return data


def _gitea_notification_data(**overrides):
    data = {
        "id": 1,
        "reason": "mention",
        "unread": True,
        "subject": {
            "title": "Fix issue",
            "type": "Issue",
            "html_url": "https://gitea.example.com/owner/repo/issues/1",
        },
        "repository": {"full_name": "owner/repo"},
        "updated_at": "2024-01-01T00:00:00Z",
    }
    data.update(overrides)
    return data


def _backlog_notification_data(**overrides):
    data = {
        "id": 1,
        "resourceAlreadyRead": False,
        "comment": {"content": "New comment", "issue": {"summary": "Fix bug"}},
        "created": "2024-01-01T00:00:00Z",
    }
    data.update(overrides)
    return data


# --- GitHub ---


class TestGitHubNotification:
    @responses.activate
    def test_list(self, github_adapter):
        responses.add(
            responses.GET,
            "https://api.github.com/notifications",
            json=[_github_notification_data()],
        )
        notifs = github_adapter.list_notifications()
        assert len(notifs) == 1
        assert notifs[0].id == "1"
        assert notifs[0].title == "Fix bug"
        assert notifs[0].unread is True
        assert notifs[0].repository == "owner/repo"

    @responses.activate
    def test_list_unread_only(self, github_adapter):
        responses.add(
            responses.GET,
            "https://api.github.com/notifications",
            json=[],
        )
        github_adapter.list_notifications(unread_only=True)
        assert "all" not in responses.calls[0].request.url

    @responses.activate
    def test_list_all(self, github_adapter):
        responses.add(
            responses.GET,
            "https://api.github.com/notifications",
            json=[],
        )
        github_adapter.list_notifications(unread_only=False)
        assert "all=true" in responses.calls[0].request.url

    @responses.activate
    def test_mark_read(self, github_adapter):
        responses.add(
            responses.PATCH,
            "https://api.github.com/notifications/threads/1",
            status=205,
        )
        github_adapter.mark_notification_read("1")

    @responses.activate
    def test_mark_all_read(self, github_adapter):
        responses.add(
            responses.PUT,
            "https://api.github.com/notifications",
            status=205,
        )
        github_adapter.mark_all_notifications_read()

    @responses.activate
    def test_list_empty(self, github_adapter):
        responses.add(responses.GET, "https://api.github.com/notifications", json=[])
        assert github_adapter.list_notifications() == []

    @responses.activate
    def test_list_403(self, github_adapter):
        responses.add(responses.GET, "https://api.github.com/notifications", status=403)
        with pytest.raises(AuthenticationError):
            github_adapter.list_notifications()


# --- GitLab ---


class TestGitLabNotification:
    @responses.activate
    def test_list(self, gitlab_adapter):
        responses.add(
            responses.GET,
            "https://gitlab.com/api/v4/todos",
            json=[_gitlab_todo_data()],
        )
        notifs = gitlab_adapter.list_notifications()
        assert len(notifs) == 1
        assert notifs[0].title == "Review MR !5"
        assert notifs[0].reason == "MergeRequest"
        assert notifs[0].unread is True

    @responses.activate
    def test_list_unread_only(self, gitlab_adapter):
        responses.add(
            responses.GET,
            "https://gitlab.com/api/v4/todos",
            json=[],
        )
        gitlab_adapter.list_notifications(unread_only=True)
        assert "state=pending" in responses.calls[0].request.url

    @responses.activate
    def test_mark_read(self, gitlab_adapter):
        responses.add(
            responses.POST,
            "https://gitlab.com/api/v4/todos/1/mark_as_done",
            status=200,
        )
        gitlab_adapter.mark_notification_read("1")

    @responses.activate
    def test_mark_all_read(self, gitlab_adapter):
        responses.add(
            responses.POST,
            "https://gitlab.com/api/v4/todos/mark_as_done",
            status=204,
        )
        gitlab_adapter.mark_all_notifications_read()

    @responses.activate
    def test_list_unread_only_false(self, gitlab_adapter):
        """unread_only=False の場合 state パラメータなしで全件取得。"""
        responses.add(
            responses.GET,
            "https://gitlab.com/api/v4/todos",
            json=[_gitlab_todo_data(state="done")],
        )
        notifs = gitlab_adapter.list_notifications(unread_only=False)
        assert len(notifs) == 1
        # state=done なので unread=False
        assert notifs[0].unread is False
        assert "state=" not in responses.calls[0].request.url

    @responses.activate
    def test_list_empty(self, gitlab_adapter):
        responses.add(responses.GET, "https://gitlab.com/api/v4/todos", json=[])
        assert gitlab_adapter.list_notifications() == []

    @responses.activate
    def test_list_404(self, gitlab_adapter):
        responses.add(responses.GET, "https://gitlab.com/api/v4/todos", status=404)
        with pytest.raises(NotFoundError):
            gitlab_adapter.list_notifications()


# --- Gitea ---


class TestGiteaNotification:
    @responses.activate
    def test_list(self, gitea_adapter):
        responses.add(
            responses.GET,
            "https://gitea.example.com/api/v1/notifications",
            json=[_gitea_notification_data()],
        )
        notifs = gitea_adapter.list_notifications()
        assert len(notifs) == 1
        assert notifs[0].title == "Fix issue"

    @responses.activate
    def test_mark_read(self, gitea_adapter):
        responses.add(
            responses.PATCH,
            "https://gitea.example.com/api/v1/notifications/threads/1",
            status=205,
        )
        gitea_adapter.mark_notification_read("1")

    @responses.activate
    def test_mark_all_read(self, gitea_adapter):
        responses.add(
            responses.PUT,
            "https://gitea.example.com/api/v1/notifications",
            status=205,
        )
        gitea_adapter.mark_all_notifications_read()

    @responses.activate
    def test_list_empty(self, gitea_adapter):
        responses.add(
            responses.GET,
            "https://gitea.example.com/api/v1/notifications",
            json=[],
        )
        assert gitea_adapter.list_notifications() == []

    @responses.activate
    def test_list_403(self, gitea_adapter):
        responses.add(
            responses.GET,
            "https://gitea.example.com/api/v1/notifications",
            status=403,
        )
        with pytest.raises(AuthenticationError):
            gitea_adapter.list_notifications()


# --- Forgejo ---


class TestForgejoNotification:
    @responses.activate
    def test_list(self, forgejo_adapter):
        responses.add(
            responses.GET,
            "https://forgejo.example.com/api/v1/notifications",
            json=[_gitea_notification_data()],
        )
        notifs = forgejo_adapter.list_notifications()
        assert len(notifs) == 1

    @responses.activate
    def test_mark_read(self, forgejo_adapter):
        responses.add(
            responses.PATCH,
            "https://forgejo.example.com/api/v1/notifications/threads/1",
            status=205,
        )
        forgejo_adapter.mark_notification_read("1")

    @responses.activate
    def test_mark_all_read(self, forgejo_adapter):
        responses.add(
            responses.PUT,
            "https://forgejo.example.com/api/v1/notifications",
            status=205,
        )
        forgejo_adapter.mark_all_notifications_read()

    @responses.activate
    def test_list_empty(self, forgejo_adapter):
        responses.add(
            responses.GET,
            "https://forgejo.example.com/api/v1/notifications",
            json=[],
        )
        assert forgejo_adapter.list_notifications() == []


# --- Backlog ---


class TestBacklogNotification:
    @responses.activate
    def test_list(self, backlog_adapter):
        responses.add(
            responses.GET,
            "https://example.backlog.com/api/v2/notifications",
            json=[_backlog_notification_data()],
        )
        notifs = backlog_adapter.list_notifications()
        assert len(notifs) == 1
        assert notifs[0].title == "Fix bug"
        assert notifs[0].unread is True

    @responses.activate
    def test_mark_read(self, backlog_adapter):
        responses.add(
            responses.POST,
            "https://example.backlog.com/api/v2/notifications/1/markAsRead",
            status=200,
        )
        backlog_adapter.mark_notification_read("1")

    @responses.activate
    def test_mark_all_read(self, backlog_adapter):
        responses.add(
            responses.POST,
            "https://example.backlog.com/api/v2/notifications/markAsRead",
            status=200,
        )
        backlog_adapter.mark_all_notifications_read()

    @responses.activate
    def test_list_empty(self, backlog_adapter):
        responses.add(
            responses.GET,
            "https://example.backlog.com/api/v2/notifications",
            json=[],
        )
        assert backlog_adapter.list_notifications() == []

    @responses.activate
    def test_list_403(self, backlog_adapter):
        responses.add(
            responses.GET,
            "https://example.backlog.com/api/v2/notifications",
            status=403,
        )
        with pytest.raises(AuthenticationError):
            backlog_adapter.list_notifications()


# --- NotSupported ---


class TestNotificationNotSupported:
    def test_azure_devops(self, azure_devops_adapter):
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.list_notifications()

    def test_azure_devops_mark_read(self, azure_devops_adapter):
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.mark_notification_read("1")

    def test_azure_devops_mark_all_read(self, azure_devops_adapter):
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.mark_all_notifications_read()

    def test_bitbucket(self, bitbucket_adapter):
        with pytest.raises(NotSupportedError):
            bitbucket_adapter.list_notifications()

    def test_bitbucket_mark_read(self, bitbucket_adapter):
        with pytest.raises(NotSupportedError):
            bitbucket_adapter.mark_notification_read("1")

    def test_bitbucket_mark_all_read(self, bitbucket_adapter):
        with pytest.raises(NotSupportedError):
            bitbucket_adapter.mark_all_notifications_read()

    def test_gogs(self, gogs_adapter):
        with pytest.raises(NotSupportedError):
            gogs_adapter.list_notifications()

    def test_gitbucket(self, gitbucket_adapter):
        with pytest.raises(NotSupportedError):
            gitbucket_adapter.list_notifications()

    def test_gogs_mark_read(self, gogs_adapter):
        with pytest.raises(NotSupportedError):
            gogs_adapter.mark_notification_read("1")

    def test_gitbucket_mark_read(self, gitbucket_adapter):
        with pytest.raises(NotSupportedError):
            gitbucket_adapter.mark_notification_read("1")

    def test_gogs_mark_all_read(self, gogs_adapter):
        with pytest.raises(NotSupportedError):
            gogs_adapter.mark_all_notifications_read()

    def test_gitbucket_mark_all_read(self, gitbucket_adapter):
        with pytest.raises(NotSupportedError):
            gitbucket_adapter.mark_all_notifications_read()
