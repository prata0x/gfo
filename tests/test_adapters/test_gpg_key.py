"""全アダプターの GPG Key テスト。"""

from __future__ import annotations

import json

import pytest
import responses

from gfo.exceptions import AuthenticationError, NotFoundError, NotSupportedError

# --- ヘルパー ---


def _common_gpg_key_data(**overrides):
    """GitHub / Gitea 系共通の GPG Key レスポンスデータ。"""
    data = {
        "id": 1,
        "primary_key_id": "ABC123",
        "public_key": "-----BEGIN PGP PUBLIC KEY BLOCK-----...",
        "emails": [{"email": "user@example.com"}],
        "created_at": "2024-01-01T00:00:00Z",
    }
    data.update(overrides)
    return data


def _gitlab_gpg_key_data(**overrides):
    """GitLab の GPG Key レスポンスデータ。"""
    data = {
        "id": 1,
        "primary_key_id": "ABC123",
        "key": "-----BEGIN PGP PUBLIC KEY BLOCK-----...",
        "created_at": "2024-01-01T00:00:00Z",
    }
    data.update(overrides)
    return data


def _bitbucket_gpg_key_data(**overrides):
    """Bitbucket の GPG Key レスポンスデータ。"""
    data = {
        "fingerprint": "AABBCCDD",
        "key": "-----BEGIN PGP PUBLIC KEY BLOCK-----...",
        "created_on": "2024-01-01T00:00:00Z",
    }
    data.update(overrides)
    return data


# --- GitHub ---


class TestGitHubGpgKey:
    @responses.activate
    def test_list(self, github_adapter):
        responses.add(
            responses.GET,
            "https://api.github.com/user/gpg_keys",
            json=[_common_gpg_key_data()],
        )
        keys = github_adapter.list_gpg_keys()
        assert len(keys) == 1
        assert keys[0].id == 1
        assert keys[0].primary_key_id == "ABC123"
        assert keys[0].emails == ("user@example.com",)

    @responses.activate
    def test_create(self, github_adapter):
        responses.add(
            responses.POST,
            "https://api.github.com/user/gpg_keys",
            json=_common_gpg_key_data(id=2),
            status=201,
        )
        key = github_adapter.create_gpg_key(armored_key="-----BEGIN PGP...")
        assert key.id == 2
        req_body = json.loads(responses.calls[0].request.body)
        assert req_body["armored_public_key"] == "-----BEGIN PGP..."

    @responses.activate
    def test_delete(self, github_adapter):
        responses.add(
            responses.DELETE,
            "https://api.github.com/user/gpg_keys/1",
            status=204,
        )
        github_adapter.delete_gpg_key(key_id=1)

    @responses.activate
    def test_list_empty(self, github_adapter):
        responses.add(responses.GET, "https://api.github.com/user/gpg_keys", json=[])
        assert github_adapter.list_gpg_keys() == []

    @responses.activate
    def test_list_404(self, github_adapter):
        responses.add(responses.GET, "https://api.github.com/user/gpg_keys", status=404)
        with pytest.raises(NotFoundError):
            github_adapter.list_gpg_keys()

    @responses.activate
    def test_create_403(self, github_adapter):
        responses.add(responses.POST, "https://api.github.com/user/gpg_keys", status=403)
        with pytest.raises(AuthenticationError):
            github_adapter.create_gpg_key(armored_key="k")

    @responses.activate
    def test_delete_404(self, github_adapter):
        responses.add(responses.DELETE, "https://api.github.com/user/gpg_keys/999", status=404)
        with pytest.raises(NotFoundError):
            github_adapter.delete_gpg_key(key_id=999)


# --- GitLab ---


class TestGitLabGpgKey:
    @responses.activate
    def test_list(self, gitlab_adapter):
        responses.add(
            responses.GET,
            "https://gitlab.com/api/v4/user/gpg_keys",
            json=[_gitlab_gpg_key_data()],
        )
        keys = gitlab_adapter.list_gpg_keys()
        assert len(keys) == 1
        assert keys[0].primary_key_id == "ABC123"
        assert keys[0].public_key == "-----BEGIN PGP PUBLIC KEY BLOCK-----..."

    @responses.activate
    def test_create(self, gitlab_adapter):
        responses.add(
            responses.POST,
            "https://gitlab.com/api/v4/user/gpg_keys",
            json=_gitlab_gpg_key_data(id=2),
            status=201,
        )
        key = gitlab_adapter.create_gpg_key(armored_key="-----BEGIN PGP...")
        assert key.id == 2
        req_body = json.loads(responses.calls[0].request.body)
        assert req_body["key"] == "-----BEGIN PGP..."

    @responses.activate
    def test_delete(self, gitlab_adapter):
        responses.add(
            responses.DELETE,
            "https://gitlab.com/api/v4/user/gpg_keys/1",
            status=204,
        )
        gitlab_adapter.delete_gpg_key(key_id=1)

    @responses.activate
    def test_list_empty(self, gitlab_adapter):
        responses.add(responses.GET, "https://gitlab.com/api/v4/user/gpg_keys", json=[])
        assert gitlab_adapter.list_gpg_keys() == []

    @responses.activate
    def test_list_404(self, gitlab_adapter):
        responses.add(responses.GET, "https://gitlab.com/api/v4/user/gpg_keys", status=404)
        with pytest.raises(NotFoundError):
            gitlab_adapter.list_gpg_keys()

    @responses.activate
    def test_delete_403(self, gitlab_adapter):
        responses.add(responses.DELETE, "https://gitlab.com/api/v4/user/gpg_keys/1", status=403)
        with pytest.raises(AuthenticationError):
            gitlab_adapter.delete_gpg_key(key_id=1)


# --- Bitbucket ---


class TestBitbucketGpgKey:
    @responses.activate
    def test_list(self, bitbucket_adapter):
        responses.add(
            responses.GET,
            "https://api.bitbucket.org/2.0/users/test-workspace/gpg-keys",
            json={"values": [_bitbucket_gpg_key_data()], "pagelen": 10},
        )
        keys = bitbucket_adapter.list_gpg_keys()
        assert len(keys) == 1
        assert keys[0].id == "AABBCCDD"
        assert keys[0].primary_key_id == "AABBCCDD"

    @responses.activate
    def test_create(self, bitbucket_adapter):
        responses.add(
            responses.POST,
            "https://api.bitbucket.org/2.0/users/test-workspace/gpg-keys",
            json=_bitbucket_gpg_key_data(fingerprint="EEFF0011"),
            status=201,
        )
        key = bitbucket_adapter.create_gpg_key(armored_key="-----BEGIN PGP...")
        assert key.id == "EEFF0011"
        req_body = json.loads(responses.calls[0].request.body)
        assert req_body["key"] == "-----BEGIN PGP..."

    @responses.activate
    def test_delete(self, bitbucket_adapter):
        responses.add(
            responses.DELETE,
            "https://api.bitbucket.org/2.0/users/test-workspace/gpg-keys/AABBCCDD",
            status=204,
        )
        bitbucket_adapter.delete_gpg_key(key_id="AABBCCDD")

    @responses.activate
    def test_list_empty(self, bitbucket_adapter):
        responses.add(
            responses.GET,
            "https://api.bitbucket.org/2.0/users/test-workspace/gpg-keys",
            json={"values": [], "pagelen": 10},
        )
        assert bitbucket_adapter.list_gpg_keys() == []

    @responses.activate
    def test_list_404(self, bitbucket_adapter):
        responses.add(
            responses.GET,
            "https://api.bitbucket.org/2.0/users/test-workspace/gpg-keys",
            status=404,
        )
        with pytest.raises(NotFoundError):
            bitbucket_adapter.list_gpg_keys()

    @responses.activate
    def test_delete_403(self, bitbucket_adapter):
        responses.add(
            responses.DELETE,
            "https://api.bitbucket.org/2.0/users/test-workspace/gpg-keys/AABBCCDD",
            status=403,
        )
        with pytest.raises(AuthenticationError):
            bitbucket_adapter.delete_gpg_key(key_id="AABBCCDD")


# --- Gitea ---


class TestGiteaGpgKey:
    @responses.activate
    def test_list(self, gitea_adapter):
        responses.add(
            responses.GET,
            "https://gitea.example.com/api/v1/user/gpg_keys",
            json=[_common_gpg_key_data()],
        )
        keys = gitea_adapter.list_gpg_keys()
        assert len(keys) == 1
        assert keys[0].primary_key_id == "ABC123"

    @responses.activate
    def test_create(self, gitea_adapter):
        responses.add(
            responses.POST,
            "https://gitea.example.com/api/v1/user/gpg_keys",
            json=_common_gpg_key_data(id=2),
            status=201,
        )
        key = gitea_adapter.create_gpg_key(armored_key="-----BEGIN PGP...")
        assert key.id == 2

    @responses.activate
    def test_delete(self, gitea_adapter):
        responses.add(
            responses.DELETE,
            "https://gitea.example.com/api/v1/user/gpg_keys/1",
            status=204,
        )
        gitea_adapter.delete_gpg_key(key_id=1)

    @responses.activate
    def test_list_empty(self, gitea_adapter):
        responses.add(
            responses.GET,
            "https://gitea.example.com/api/v1/user/gpg_keys",
            json=[],
        )
        assert gitea_adapter.list_gpg_keys() == []

    @responses.activate
    def test_delete_404(self, gitea_adapter):
        responses.add(
            responses.DELETE,
            "https://gitea.example.com/api/v1/user/gpg_keys/999",
            status=404,
        )
        with pytest.raises(NotFoundError):
            gitea_adapter.delete_gpg_key(key_id=999)


# --- Forgejo (inherits Gitea) ---


class TestForgejoGpgKey:
    @responses.activate
    def test_list(self, forgejo_adapter):
        responses.add(
            responses.GET,
            "https://forgejo.example.com/api/v1/user/gpg_keys",
            json=[_common_gpg_key_data()],
        )
        keys = forgejo_adapter.list_gpg_keys()
        assert len(keys) == 1

    @responses.activate
    def test_create(self, forgejo_adapter):
        responses.add(
            responses.POST,
            "https://forgejo.example.com/api/v1/user/gpg_keys",
            json=_common_gpg_key_data(id=2),
            status=201,
        )
        key = forgejo_adapter.create_gpg_key(armored_key="-----BEGIN PGP...")
        assert key.id == 2

    @responses.activate
    def test_delete(self, forgejo_adapter):
        responses.add(
            responses.DELETE,
            "https://forgejo.example.com/api/v1/user/gpg_keys/1",
            status=204,
        )
        forgejo_adapter.delete_gpg_key(key_id=1)


# --- NotSupported ---


class TestGpgKeyNotSupported:
    def test_azure_devops_list(self, azure_devops_adapter):
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.list_gpg_keys()

    def test_azure_devops_create(self, azure_devops_adapter):
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.create_gpg_key(armored_key="k")

    def test_azure_devops_delete(self, azure_devops_adapter):
        with pytest.raises(NotSupportedError):
            azure_devops_adapter.delete_gpg_key(key_id=1)

    def test_gitbucket_list(self, gitbucket_adapter):
        with pytest.raises(NotSupportedError):
            gitbucket_adapter.list_gpg_keys()

    def test_gitbucket_create(self, gitbucket_adapter):
        with pytest.raises(NotSupportedError):
            gitbucket_adapter.create_gpg_key(armored_key="k")

    def test_gitbucket_delete(self, gitbucket_adapter):
        with pytest.raises(NotSupportedError):
            gitbucket_adapter.delete_gpg_key(key_id=1)

    def test_backlog_list(self, backlog_adapter):
        with pytest.raises(NotSupportedError):
            backlog_adapter.list_gpg_keys()

    def test_backlog_create(self, backlog_adapter):
        with pytest.raises(NotSupportedError):
            backlog_adapter.create_gpg_key(armored_key="k")

    def test_backlog_delete(self, backlog_adapter):
        with pytest.raises(NotSupportedError):
            backlog_adapter.delete_gpg_key(key_id=1)

    def test_gogs_list(self, gogs_adapter):
        with pytest.raises(NotSupportedError):
            gogs_adapter.list_gpg_keys()

    def test_gogs_create(self, gogs_adapter):
        with pytest.raises(NotSupportedError):
            gogs_adapter.create_gpg_key(armored_key="k")

    def test_gogs_delete(self, gogs_adapter):
        with pytest.raises(NotSupportedError):
            gogs_adapter.delete_gpg_key(key_id=1)
