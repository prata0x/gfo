"""gfo.commands.release のテスト。"""

from __future__ import annotations

import contextlib
import json
from unittest.mock import MagicMock, patch

import pytest

from gfo.adapter.base import Release
from gfo.commands import release as release_cmd
from gfo.exceptions import ConfigError
from tests.test_commands.conftest import make_args


def _make_release() -> Release:
    return Release(
        tag="v1.0.0",
        title="Version 1.0.0",
        body="Release notes",
        draft=False,
        prerelease=False,
        url="https://github.com/test-owner/test-repo/releases/tag/v1.0.0",
        created_at="2024-01-01T00:00:00Z",
    )


def _make_adapter(sample_release: Release) -> MagicMock:
    adapter = MagicMock()
    adapter.list_releases.return_value = [sample_release]
    adapter.create_release.return_value = sample_release
    return adapter


@contextlib.contextmanager
def _patch_all(config, adapter: MagicMock):
    with patch("gfo.commands.release.get_adapter", return_value=adapter):
        yield


class TestHandleList:
    def setup_method(self):
        self.release = _make_release()
        self.adapter = _make_adapter(self.release)

    def test_calls_list_releases(self, sample_config):
        args = make_args(limit=30)
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_list(args, fmt="table")

        self.adapter.list_releases.assert_called_once_with(limit=30)

    def test_outputs_results(self, sample_config, capsys):
        args = make_args(limit=30)
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_list(args, fmt="table")

        out = capsys.readouterr().out
        assert "v1.0.0" in out
        assert "Version 1.0.0" in out

    def test_plain_format(self, sample_config, capsys):
        args = make_args(limit=30)
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_list(args, fmt="plain")

        out = capsys.readouterr().out
        assert "\t" in out
        assert "TAG" not in out
        assert "v1.0.0" in out

    def test_json_format(self, sample_config, capsys):
        args = make_args(limit=10)
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_list(args, fmt="json")

        out = capsys.readouterr().out
        data = json.loads(out)
        if isinstance(data, list):
            assert data[0]["tag"] == "v1.0.0"
        else:
            assert data["tag"] == "v1.0.0"


class TestHandleCreate:
    def setup_method(self):
        self.release = _make_release()
        self.adapter = _make_adapter(self.release)

    def test_basic_create(self, sample_config):
        args = make_args(tag="v1.0.0", title="Version 1.0.0", notes="Notes", draft=False, prerelease=False)
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_create(args, fmt="table")

        self.adapter.create_release.assert_called_once_with(
            tag="v1.0.0",
            title="Version 1.0.0",
            notes="Notes",
            draft=False,
            prerelease=False,
        )

    def test_title_defaults_to_tag(self, sample_config):
        args = make_args(tag="v2.0.0", title=None, notes="", draft=False, prerelease=False)
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_create(args, fmt="table")

        call_kwargs = self.adapter.create_release.call_args.kwargs
        assert call_kwargs["title"] == "v2.0.0"

    def test_draft_flag(self, sample_config):
        args = make_args(tag="v1.0.0-draft", title=None, notes="", draft=True, prerelease=False)
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_create(args, fmt="table")

        call_kwargs = self.adapter.create_release.call_args.kwargs
        assert call_kwargs["draft"] is True
        assert call_kwargs["prerelease"] is False

    def test_prerelease_flag(self, sample_config):
        args = make_args(tag="v1.0.0-rc1", title=None, notes="", draft=False, prerelease=True)
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_create(args, fmt="table")

        call_kwargs = self.adapter.create_release.call_args.kwargs
        assert call_kwargs["prerelease"] is True
        assert call_kwargs["draft"] is False

    def test_notes_defaults_to_empty_string(self, sample_config):
        args = make_args(tag="v1.0.0", title="Release", notes=None, draft=False, prerelease=False)
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_create(args, fmt="table")

        call_kwargs = self.adapter.create_release.call_args.kwargs
        assert call_kwargs["notes"] == ""

    def test_whitespace_only_title_falls_back_to_tag(self, sample_config):
        args = make_args(tag="v1.0.0", title="   ", notes="", draft=False, prerelease=False)
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_create(args, fmt="table")

        call_kwargs = self.adapter.create_release.call_args.kwargs
        assert call_kwargs["title"] == "v1.0.0"

    def test_empty_tag_raises_config_error_with_correct_message(self, sample_config):
        """空文字 tag では正しいエラーメッセージが表示される（R39-02）。"""
        args = make_args(tag="", title=None, notes="", draft=False, prerelease=False)
        with _patch_all(sample_config, self.adapter):
            with pytest.raises(ConfigError, match="gfo release create"):
                release_cmd.handle_create(args, fmt="table")
