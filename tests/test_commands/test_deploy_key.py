"""gfo.commands.deploy_key のテスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from gfo.adapter.base import DeployKey
from gfo.commands import deploy_key as deploy_key_cmd
from tests.test_commands.conftest import make_args

SAMPLE_KEY = DeployKey(id=1, title="CI Key", key="ssh-rsa AAAA...", read_only=True)


def _patch(adapter):
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        with patch("gfo.commands.deploy_key.get_adapter", return_value=adapter):
            yield

    return _ctx()


class TestHandleList:
    def test_calls_list_deploy_keys(self, capsys):
        adapter = MagicMock()
        adapter.list_deploy_keys.return_value = [SAMPLE_KEY]
        args = make_args(limit=30)
        with _patch(adapter):
            deploy_key_cmd.handle_list(args, fmt="table")
        adapter.list_deploy_keys.assert_called_once_with(limit=30)


class TestHandleCreate:
    def test_creates_read_only_by_default(self):
        adapter = MagicMock()
        adapter.create_deploy_key.return_value = SAMPLE_KEY
        args = make_args(title="Deploy", key="ssh-rsa AAAA...", read_write=False)
        with _patch(adapter):
            deploy_key_cmd.handle_create(args, fmt="table")
        adapter.create_deploy_key.assert_called_once_with(
            title="Deploy", key="ssh-rsa AAAA...", read_only=True
        )

    def test_creates_read_write(self):
        adapter = MagicMock()
        adapter.create_deploy_key.return_value = SAMPLE_KEY
        args = make_args(title="Deploy", key="ssh-rsa AAAA...", read_write=True)
        with _patch(adapter):
            deploy_key_cmd.handle_create(args, fmt="table")
        adapter.create_deploy_key.assert_called_once_with(
            title="Deploy", key="ssh-rsa AAAA...", read_only=False
        )


class TestHandleDelete:
    def test_calls_delete_deploy_key(self):
        adapter = MagicMock()
        args = make_args(id=1)
        with _patch(adapter):
            deploy_key_cmd.handle_delete(args, fmt="table")
        adapter.delete_deploy_key.assert_called_once_with(key_id=1)
