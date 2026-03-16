"""全アダプターの SSH Key テスト。"""

from __future__ import annotations

import json

import pytest
import responses

from gfo.exceptions import NotSupportedError

# --- ヘルパー ---


def _github_ssh_key_data(**overrides):
    data = {
        "id": 1,
        "title": "my-key",
        "key": "ssh-rsa AAAA...",
        "created_at": "2024-01-01T00:00:00Z",
    }
    data.update(overrides)
    return data


def _gitlab_ssh_key_data(**overrides):
    data = {
        "id": 1,
        "title": "my-key",
        "key": "ssh-rsa AAAA...",
        "created_at": "2024-01-01T00:00:00Z",
    }
    data.update(overrides)
    return data


def _bitbucket_ssh_key_data(**overrides):
    data = {
        "uuid": "{abc-123}",
        "label": "my-key",
        "key": "ssh-rsa AAAA...",
        "created_on": "2024-01-01T00:00:00Z",
    }
    data.update(overrides)
    return data


def _gitea_ssh_key_data(**overrides):
    data = {
        "id": 1,
        "title": "my-key",
        "key": "ssh-rsa AAAA...",
        "created_at": "2024-01-01T00:00:00Z",
    }
    data.update(overrides)
    return data


# --- GitHub ---


class TestGitHubSshKey:
    @responses.activate
    def test_list(self, github_adapter):
        responses.add(
            responses.GET,
            "https://api.github.com/user/keys",
            json=[_github_ssh_key_data()],
        )
        keys = github_adapter.list_ssh_keys()
        assert len(keys) == 1
        assert keys[0].id == 1
        assert keys[0].title == "my-key"
        assert keys[0].key == "ssh-rsa AAAA..."

    @responses.activate
    def test_create(self, github_adapter):
        responses.add(
            responses.POST,
            "https://api.github.com/user/keys",
            json=_github_ssh_key_data(id=2, title="new-key"),
            status=201,
        )
        key = github_adapter.create_ssh_key(title="new-key", key="ssh-rsa BBBB...")
        assert key.id == 2
        assert key.title == "new-key"
        req_body = json.loads(responses.calls[0].request.body)
        assert req_body["title"] == "new-key"
        assert req_body["key"] == "ssh-rsa BBBB..."

    @responses.activate
    def test_delete(self, github_adapter):
        responses.add(
            responses.DELETE,
            "https://api.github.com/user/keys/1",
            status=204,
        )
        github_adapter.delete_ssh_key(key_id=1)


# --- GitLab ---


class TestGitLabSshKey:
    @responses.activate
    def test_list(self, gitlab_adapter):
        responses.add(
            responses.GET,
            "https://gitlab.com/api/v4/user/keys",
            json=[_gitlab_ssh_key_data()],
        )
        keys = gitlab_adapter.list_ssh_keys()
        assert len(keys) == 1
        assert keys[0].title == "my-key"

    @responses.activate
    def test_create(self, gitlab_adapter):
        responses.add(
            responses.POST,
            "https://gitlab.com/api/v4/user/keys",
            json=_gitlab_ssh_key_data(id=2, title="new-key"),
            status=201,
        )
        key = gitlab_adapter.create_ssh_key(title="new-key", key="ssh-rsa BBBB...")
        assert key.id == 2

    @responses.activate
    def test_delete(self, gitlab_adapter):
        responses.add(
            responses.DELETE,
            "https://gitlab.com/api/v4/user/keys/1",
            status=204,
        )
        gitlab_adapter.delete_ssh_key(key_id=1)


# --- Bitbucket ---


class TestBitbucketSshKey:
    @responses.activate
    def test_list(self, bitbucket_adapter):
        responses.add(
            responses.GET,
            "https://api.bitbucket.org/2.0/users/test-workspace/ssh-keys",
            json={"values": [_bitbucket_ssh_key_data()], "pagelen": 10},
        )
        keys = bitbucket_adapter.list_ssh_keys()
        assert len(keys) == 1
        assert keys[0].id == "abc-123"
        assert keys[0].title == "my-key"

    @responses.activate
    def test_create(self, bitbucket_adapter):
        responses.add(
            responses.POST,
            "https://api.bitbucket.org/2.0/users/test-workspace/ssh-keys",
            json=_bitbucket_ssh_key_data(uuid="{def-456}", label="new-key"),
            status=201,
        )
        key = bitbucket_adapter.create_ssh_key(title="new-key", key="ssh-rsa BBBB...")
        assert key.id == "def-456"
        assert key.title == "new-key"
        req_body = json.loads(responses.calls[0].request.body)
        assert req_body["label"] == "new-key"

    @responses.activate
    def test_delete(self, bitbucket_adapter):
        responses.add(
            responses.DELETE,
            "https://api.bitbucket.org/2.0/users/test-workspace/ssh-keys/abc-123",
            status=204,
        )
        bitbucket_adapter.delete_ssh_key(key_id="abc-123")


# --- Gitea ---


class TestGiteaSshKey:
    @responses.activate
    def test_list(self, gitea_adapter):
        responses.add(
            responses.GET,
            "https://gitea.example.com/api/v1/user/keys",
            json=[_gitea_ssh_key_data()],
        )
        keys = gitea_adapter.list_ssh_keys()
        assert len(keys) == 1
        assert keys[0].title == "my-key"

    @responses.activate
    def test_create(self, gitea_adapter):
        responses.add(
            responses.POST,
            "https://gitea.example.com/api/v1/user/keys",
            json=_gitea_ssh_key_data(id=2, title="new-key"),
            status=201,
        )
        key = gitea_adapter.create_ssh_key(title="new-key", key="ssh-rsa BBBB...")
        assert key.id == 2

    @responses.activate
    def test_delete(self, gitea_adapter):
        responses.add(
            responses.DELETE,
            "https://gitea.example.com/api/v1/user/keys/1",
            status=204,
        )
        gitea_adapter.delete_ssh_key(key_id=1)


# --- Forgejo (inherits Gitea) ---


class TestForgejoSshKey:
    @responses.activate
    def test_list(self, forgejo_adapter):
        responses.add(
            responses.GET,
            "https://forgejo.example.com/api/v1/user/keys",
            json=[_gitea_ssh_key_data()],
        )
        keys = forgejo_adapter.list_ssh_keys()
        assert len(keys) == 1

    @responses.activate
    def test_create(self, forgejo_adapter):
        responses.add(
            responses.POST,
            "https://forgejo.example.com/api/v1/user/keys",
            json=_gitea_ssh_key_data(id=2),
            status=201,
        )
        key = forgejo_adapter.create_ssh_key(title="k", key="ssh-rsa X")
        assert key.id == 2

    @responses.activate
    def test_delete(self, forgejo_adapter):
        responses.add(
            responses.DELETE,
            "https://forgejo.example.com/api/v1/user/keys/1",
            status=204,
        )
        forgejo_adapter.delete_ssh_key(key_id=1)


# --- Gogs (inherits Gitea) ---


class TestGogsSshKey:
    @responses.activate
    def test_list(self, gogs_adapter):
        responses.add(
            responses.GET,
            "https://gogs.example.com/api/v1/user/keys",
            json=[_gitea_ssh_key_data()],
        )
        keys = gogs_adapter.list_ssh_keys()
        assert len(keys) == 1

    @responses.activate
    def test_create(self, gogs_adapter):
        responses.add(
            responses.POST,
            "https://gogs.example.com/api/v1/user/keys",
            json=_gitea_ssh_key_data(id=3),
            status=201,
        )
        key = gogs_adapter.create_ssh_key(title="k", key="ssh-rsa X")
        assert key.id == 3

    @responses.activate
    def test_delete(self, gogs_adapter):
        responses.add(
            responses.DELETE,
            "https://gogs.example.com/api/v1/user/keys/1",
            status=204,
        )
        gogs_adapter.delete_ssh_key(key_id=1)


# --- NotSupported ---


class TestSshKeyNotSupported:
    def test_azure_devops_list(self, azure_devops_adapter):
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.list_ssh_keys()

    def test_azure_devops_create(self, azure_devops_adapter):
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.create_ssh_key(title="t", key="k")

    def test_azure_devops_delete(self, azure_devops_adapter):
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.delete_ssh_key(key_id=1)

    def test_gitbucket_list(self, gitbucket_adapter):
        with pytest.raises(NotSupportedError):
            gitbucket_adapter.list_ssh_keys()

    def test_gitbucket_create(self, gitbucket_adapter):
        with pytest.raises(NotSupportedError):
            gitbucket_adapter.create_ssh_key(title="t", key="k")

    def test_gitbucket_delete(self, gitbucket_adapter):
        with pytest.raises(NotSupportedError):
            gitbucket_adapter.delete_ssh_key(key_id=1)

    def test_backlog_list(self, backlog_adapter):
        with pytest.raises(NotSupportedError):
            backlog_adapter.list_ssh_keys()

    def test_backlog_create(self, backlog_adapter):
        with pytest.raises(NotSupportedError):
            backlog_adapter.create_ssh_key(title="t", key="k")

    def test_backlog_delete(self, backlog_adapter):
        with pytest.raises(NotSupportedError):
            backlog_adapter.delete_ssh_key(key_id=1)
