"""gfo.commands.release のテスト。"""

from __future__ import annotations

import contextlib
import json
from unittest.mock import MagicMock, patch

import pytest

from gfo.adapter.base import Release, ReleaseAsset
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


def _make_asset() -> ReleaseAsset:
    return ReleaseAsset(
        id=1,
        name="app-v1.0.0.zip",
        size=1024,
        download_url="https://github.com/test-owner/test-repo/releases/download/v1.0.0/app-v1.0.0.zip",
        created_at="2024-01-01T00:00:00Z",
    )


def _make_adapter(sample_release: Release) -> MagicMock:
    adapter = MagicMock()
    adapter.list_releases.return_value = [sample_release]
    adapter.create_release.return_value = sample_release
    adapter.get_release.return_value = sample_release
    adapter.get_latest_release.return_value = sample_release
    adapter.update_release.return_value = sample_release
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
        assert isinstance(data, list)
        assert data[0]["tag"] == "v1.0.0"


class TestHandleCreate:
    def setup_method(self):
        self.release = _make_release()
        self.adapter = _make_adapter(self.release)

    def test_basic_create(self, sample_config):
        args = make_args(
            tag="v1.0.0", title="Version 1.0.0", notes="Notes", draft=False, prerelease=False
        )
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


class TestHandleDelete:
    def setup_method(self):
        self.release = _make_release()
        self.adapter = _make_adapter(self.release)

    def test_delete_calls_adapter(self, sample_config):
        args = make_args(tag="v1.0.0")
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_delete(args, fmt="table")

        self.adapter.delete_release.assert_called_once_with(tag="v1.0.0")

    def test_delete_prints_message(self, sample_config, capsys):
        args = make_args(tag="v1.0.0")
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_delete(args, fmt="table")

        out = capsys.readouterr().out
        assert "v1.0.0" in out
        assert "Deleted" in out

    def test_empty_tag_raises_config_error(self, sample_config):
        args = make_args(tag="")
        with _patch_all(sample_config, self.adapter):
            with pytest.raises(ConfigError, match="gfo release delete"):
                release_cmd.handle_delete(args, fmt="table")

    def test_whitespace_only_tag_raises_config_error(self, sample_config):
        args = make_args(tag="   ")
        with _patch_all(sample_config, self.adapter):
            with pytest.raises(ConfigError):
                release_cmd.handle_delete(args, fmt="table")


class TestHandleView:
    def setup_method(self):
        self.release = _make_release()
        self.adapter = _make_adapter(self.release)

    def test_view_calls_adapter(self, sample_config):
        args = make_args(tag="v1.0.0")
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_view(args, fmt="table")

        self.adapter.get_release.assert_called_once_with(tag="v1.0.0")

    def test_view_json_format(self, sample_config, capsys):
        args = make_args(tag="v1.0.0")
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_view(args, fmt="json")

        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, list)
        assert data[0]["tag"] == "v1.0.0"
        assert data[0]["title"] == "Version 1.0.0"

    def test_empty_tag_raises_config_error(self, sample_config):
        args = make_args(tag="")
        with _patch_all(sample_config, self.adapter):
            with pytest.raises(ConfigError):
                release_cmd.handle_view(args, fmt="table")

    def test_whitespace_only_tag_raises_config_error(self, sample_config):
        args = make_args(tag="   ")
        with _patch_all(sample_config, self.adapter):
            with pytest.raises(ConfigError):
                release_cmd.handle_view(args, fmt="table")


class TestHandleUpdate:
    def setup_method(self):
        self.release = _make_release()
        self.adapter = _make_adapter(self.release)

    def test_update_calls_adapter(self, sample_config):
        args = make_args(
            tag="v1.0.0", title="New Title", notes="New notes", draft=True, prerelease=False
        )
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_update(args, fmt="table")

        self.adapter.update_release.assert_called_once_with(
            tag="v1.0.0",
            title="New Title",
            notes="New notes",
            draft=True,
            prerelease=False,
        )

    def test_update_with_none_fields(self, sample_config):
        args = make_args(tag="v1.0.0", title=None, notes=None, draft=None, prerelease=None)
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_update(args, fmt="table")

        call_kwargs = self.adapter.update_release.call_args.kwargs
        assert call_kwargs["title"] is None
        assert call_kwargs["notes"] is None
        assert call_kwargs["draft"] is None
        assert call_kwargs["prerelease"] is None

    def test_update_json_format(self, sample_config, capsys):
        args = make_args(tag="v1.0.0", title="Updated", notes=None, draft=None, prerelease=None)
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_update(args, fmt="json")

        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, list)
        assert data[0]["tag"] == "v1.0.0"

    def test_empty_tag_raises_config_error(self, sample_config):
        args = make_args(tag="", title=None, notes=None, draft=None, prerelease=None)
        with _patch_all(sample_config, self.adapter):
            with pytest.raises(ConfigError):
                release_cmd.handle_update(args, fmt="table")


class TestHandleViewLatest:
    def setup_method(self):
        self.release = _make_release()
        self.adapter = _make_adapter(self.release)

    def test_latest_flag_calls_get_latest_release(self, sample_config):
        args = make_args(tag=None, latest=True)
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_view(args, fmt="table")

        self.adapter.get_latest_release.assert_called_once()
        self.adapter.get_release.assert_not_called()

    def test_tag_still_works(self, sample_config):
        args = make_args(tag="v1.0.0", latest=False)
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_view(args, fmt="table")

        self.adapter.get_release.assert_called_once_with(tag="v1.0.0")

    def test_no_tag_no_latest_raises(self, sample_config):
        args = make_args(tag=None, latest=False)
        with _patch_all(sample_config, self.adapter):
            with pytest.raises(ConfigError, match="tag must not be empty"):
                release_cmd.handle_view(args, fmt="table")


class TestHandleAsset:
    def setup_method(self):
        self.release = _make_release()
        self.adapter = _make_adapter(self.release)
        self.asset = _make_asset()

    def test_asset_list(self, sample_config, capsys):
        self.adapter.list_release_assets.return_value = [self.asset]
        args = make_args(asset_action="list", tag="v1.0.0")
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_asset(args, fmt="json")

        self.adapter.list_release_assets.assert_called_once_with(tag="v1.0.0")
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data[0]["name"] == "app-v1.0.0.zip"

    def test_asset_upload(self, sample_config, capsys):
        self.adapter.upload_release_asset.return_value = self.asset
        args = make_args(asset_action="upload", tag="v1.0.0", file="app.zip", name=None)
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_asset(args, fmt="json")

        self.adapter.upload_release_asset.assert_called_once_with(
            tag="v1.0.0",
            file_path="app.zip",
            name=None,
        )

    def test_asset_download_by_id(self, sample_config, capsys):
        self.adapter.download_release_asset.return_value = "/tmp/app.zip"
        args = make_args(
            asset_action="download",
            tag="v1.0.0",
            asset_id="1",
            pattern=None,
            dir=".",
        )
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_asset(args, fmt="table")

        self.adapter.download_release_asset.assert_called_once_with(
            tag="v1.0.0",
            asset_id="1",
            output_dir=".",
        )

    def test_asset_download_by_pattern(self, sample_config, capsys):
        self.adapter.list_release_assets.return_value = [self.asset]
        self.adapter.download_release_asset.return_value = "/tmp/app-v1.0.0.zip"
        args = make_args(
            asset_action="download",
            tag="v1.0.0",
            asset_id=None,
            pattern="*.zip",
            dir="/tmp",
        )
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_asset(args, fmt="table")

        self.adapter.download_release_asset.assert_called_once_with(
            tag="v1.0.0",
            asset_id=1,
            output_dir="/tmp",
        )

    def test_asset_download_no_match_raises(self, sample_config):
        self.adapter.list_release_assets.return_value = [self.asset]
        args = make_args(
            asset_action="download",
            tag="v1.0.0",
            asset_id=None,
            pattern="*.tar.gz",
            dir=".",
        )
        with _patch_all(sample_config, self.adapter):
            with pytest.raises(ConfigError, match="No assets match"):
                release_cmd.handle_asset(args, fmt="table")

    def test_asset_download_no_id_no_pattern_raises(self, sample_config):
        args = make_args(
            asset_action="download",
            tag="v1.0.0",
            asset_id=None,
            pattern=None,
            dir=".",
        )
        with _patch_all(sample_config, self.adapter):
            with pytest.raises(ConfigError, match="--asset-id or --pattern"):
                release_cmd.handle_asset(args, fmt="table")

    def test_asset_delete(self, sample_config, capsys):
        args = make_args(asset_action="delete", tag="v1.0.0", asset_id="1")
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_asset(args, fmt="table")

        self.adapter.delete_release_asset.assert_called_once_with(tag="v1.0.0", asset_id="1")

    def test_no_action_raises(self, sample_config):
        args = make_args(asset_action=None)
        with _patch_all(sample_config, self.adapter):
            with pytest.raises(ConfigError):
                release_cmd.handle_asset(args, fmt="table")
