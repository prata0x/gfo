"""gfo.commands.release のテスト。"""

from __future__ import annotations

import contextlib
import json
from unittest.mock import MagicMock, patch

import pytest

from gfo.adapter.base import Release, ReleaseAsset
from gfo.commands import release as release_cmd
from gfo.exceptions import ConfigError, GfoError
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


class TestHandleListFilter:
    """release list の --draft / --prerelease フィルタテスト。"""

    def setup_method(self):
        self.releases = [
            Release(
                tag="v1.0.0",
                title="Stable",
                body="",
                draft=False,
                prerelease=False,
                url="https://example.com/v1.0.0",
                created_at="2024-01-01",
            ),
            Release(
                tag="v2.0.0-rc1",
                title="RC",
                body="",
                draft=False,
                prerelease=True,
                url="https://example.com/v2.0.0-rc1",
                created_at="2024-01-02",
            ),
            Release(
                tag="v3.0.0-draft",
                title="Draft",
                body="",
                draft=True,
                prerelease=False,
                url="https://example.com/v3.0.0-draft",
                created_at="2024-01-03",
            ),
        ]
        self.adapter = MagicMock()
        self.adapter.list_releases.return_value = self.releases

    def test_draft_filter(self, sample_config, capsys):
        args = make_args(limit=30, draft=True, prerelease=None)
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_list(args, fmt="json")
        data = json.loads(capsys.readouterr().out)
        assert len(data) == 1
        assert data[0]["tag"] == "v3.0.0-draft"

    def test_no_draft_filter(self, sample_config, capsys):
        args = make_args(limit=30, draft=False, prerelease=None)
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_list(args, fmt="json")
        data = json.loads(capsys.readouterr().out)
        assert len(data) == 2
        assert all(not r["draft"] for r in data)

    def test_prerelease_filter(self, sample_config, capsys):
        args = make_args(limit=30, draft=None, prerelease=True)
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_list(args, fmt="json")
        data = json.loads(capsys.readouterr().out)
        assert len(data) == 1
        assert data[0]["tag"] == "v2.0.0-rc1"

    def test_no_prerelease_filter(self, sample_config, capsys):
        args = make_args(limit=30, draft=None, prerelease=False)
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_list(args, fmt="json")
        data = json.loads(capsys.readouterr().out)
        assert len(data) == 2
        assert all(not r["prerelease"] for r in data)

    def test_combined_filter(self, sample_config, capsys):
        args = make_args(limit=30, draft=False, prerelease=False)
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_list(args, fmt="json")
        data = json.loads(capsys.readouterr().out)
        assert len(data) == 1
        assert data[0]["tag"] == "v1.0.0"

    def test_no_filter(self, sample_config, capsys):
        args = make_args(limit=30, draft=None, prerelease=None)
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_list(args, fmt="json")
        data = json.loads(capsys.readouterr().out)
        assert len(data) == 3

    def test_filter_all_excluded(self, sample_config, capsys):
        args = make_args(limit=30, draft=True, prerelease=True)
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_list(args, fmt="json")
        data = json.loads(capsys.readouterr().out)
        assert len(data) == 0

    def test_filter_then_limit(self, sample_config, capsys):
        """limit でアダプターから取得後、draft/prerelease フィルタで件数が減るケース。"""
        releases = [
            Release(
                tag="v1.0.0",
                title="Stable1",
                body="",
                draft=False,
                prerelease=False,
                url="",
                created_at="2024-01-01",
            ),
            Release(
                tag="v2.0.0",
                title="Stable2",
                body="",
                draft=False,
                prerelease=False,
                url="",
                created_at="2024-01-02",
            ),
            Release(
                tag="v3.0.0-draft",
                title="Draft",
                body="",
                draft=True,
                prerelease=False,
                url="",
                created_at="2024-01-03",
            ),
            Release(
                tag="v4.0.0-rc1",
                title="RC",
                body="",
                draft=False,
                prerelease=True,
                url="",
                created_at="2024-01-04",
            ),
        ]
        adapter = MagicMock()
        adapter.list_releases.return_value = releases
        args = make_args(limit=4, draft=False, prerelease=False)
        with _patch_all(sample_config, adapter):
            release_cmd.handle_list(args, fmt="json")
        data = json.loads(capsys.readouterr().out)
        assert len(data) == 2
        assert all(not r["draft"] and not r["prerelease"] for r in data)

    def test_prerelease_and_limit(self, sample_config, capsys):
        """prerelease=True フィルタで prerelease のみ残るケース。"""
        releases = [
            Release(
                tag="v1.0.0-rc1",
                title="RC1",
                body="",
                draft=False,
                prerelease=True,
                url="",
                created_at="2024-01-01",
            ),
            Release(
                tag="v2.0.0-rc2",
                title="RC2",
                body="",
                draft=False,
                prerelease=True,
                url="",
                created_at="2024-01-02",
            ),
            Release(
                tag="v3.0.0",
                title="Stable",
                body="",
                draft=False,
                prerelease=False,
                url="",
                created_at="2024-01-03",
            ),
        ]
        adapter = MagicMock()
        adapter.list_releases.return_value = releases
        args = make_args(limit=3, draft=None, prerelease=True)
        with _patch_all(sample_config, adapter):
            release_cmd.handle_list(args, fmt="json")
        data = json.loads(capsys.readouterr().out)
        assert len(data) == 2
        assert all(r["prerelease"] for r in data)


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
            target=None,
            generate_notes=False,
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

    def test_target_passed_to_adapter(self, sample_config):
        args = make_args(
            tag="v1.0.0", title="Release", notes="", draft=False, prerelease=False, target="main"
        )
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_create(args, fmt="table")

        call_kwargs = self.adapter.create_release.call_args.kwargs
        assert call_kwargs["target"] == "main"

    def test_target_none_by_default(self, sample_config):
        args = make_args(tag="v1.0.0", title="Release", notes="", draft=False, prerelease=False)
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_create(args, fmt="table")

        call_kwargs = self.adapter.create_release.call_args.kwargs
        assert call_kwargs["target"] is None

    def test_notes_file_overrides_notes(self, sample_config, tmp_path):
        """--notes-file が指定されたらファイル内容を notes として使用する。"""
        notes_path = tmp_path / "notes.md"
        notes_path.write_text("Notes from file")
        args = make_args(
            tag="v1.0.0",
            title="Release",
            notes="",
            draft=False,
            prerelease=False,
            notes_file=str(notes_path),
        )
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_create(args, fmt="table")

        call_kwargs = self.adapter.create_release.call_args.kwargs
        assert call_kwargs["notes"] == "Notes from file"

    def test_notes_file_none_uses_notes(self, sample_config):
        """--notes-file 未指定なら --notes の値を使用する。"""
        args = make_args(
            tag="v1.0.0",
            title="Release",
            notes="Inline notes",
            draft=False,
            prerelease=False,
            notes_file=None,
        )
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_create(args, fmt="table")

        call_kwargs = self.adapter.create_release.call_args.kwargs
        assert call_kwargs["notes"] == "Inline notes"

    def test_notes_file_not_found_raises_gfo_error(self, sample_config):
        """存在しないファイルを --notes-file に指定すると GfoError を送出する。"""
        args = make_args(
            tag="v1.0.0",
            title="Release",
            notes="",
            draft=False,
            prerelease=False,
            notes_file="nonexistent.txt",
        )
        with _patch_all(sample_config, self.adapter):
            with pytest.raises(GfoError, match="File not found"):
                release_cmd.handle_create(args, fmt="table")

    def test_generate_notes_passed_to_adapter(self, sample_config):
        """--generate-notes フラグがアダプターに渡される。"""
        args = make_args(
            tag="v1.0.0", title=None, notes="", draft=False, prerelease=False, generate_notes=True
        )
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_create(args, fmt="table")

        call_kwargs = self.adapter.create_release.call_args.kwargs
        assert call_kwargs["generate_notes"] is True

    def test_generate_notes_false_by_default(self, sample_config):
        """--generate-notes 未指定なら False が渡される。"""
        args = make_args(tag="v1.0.0", title=None, notes="", draft=False, prerelease=False)
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_create(args, fmt="table")

        call_kwargs = self.adapter.create_release.call_args.kwargs
        assert call_kwargs["generate_notes"] is False

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


class TestHandleEdit:
    def setup_method(self):
        self.release = _make_release()
        self.adapter = _make_adapter(self.release)

    def test_update_calls_adapter(self, sample_config):
        args = make_args(
            tag="v1.0.0", title="New Title", notes="New notes", draft=True, prerelease=False
        )
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_edit(args, fmt="table")

        self.adapter.update_release.assert_called_once_with(
            tag="v1.0.0",
            title="New Title",
            notes="New notes",
            draft=True,
            prerelease=False,
            new_tag=None,
            target=None,
        )

    def test_update_with_none_fields(self, sample_config):
        args = make_args(tag="v1.0.0", title=None, notes=None, draft=None, prerelease=None)
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_edit(args, fmt="table")

        call_kwargs = self.adapter.update_release.call_args.kwargs
        assert call_kwargs["title"] is None
        assert call_kwargs["notes"] is None
        assert call_kwargs["draft"] is None
        assert call_kwargs["prerelease"] is None

    def test_update_json_format(self, sample_config, capsys):
        args = make_args(tag="v1.0.0", title="Updated", notes=None, draft=None, prerelease=None)
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_edit(args, fmt="json")

        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, list)
        assert data[0]["tag"] == "v1.0.0"

    def test_notes_file_overrides_notes(self, sample_config, tmp_path):
        """--notes-file が指定されたらファイル内容を notes として使用する。"""
        notes_path = tmp_path / "notes.md"
        notes_path.write_text("Notes from file")
        args = make_args(
            tag="v1.0.0",
            title=None,
            notes=None,
            draft=None,
            prerelease=None,
            notes_file=str(notes_path),
        )
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_edit(args, fmt="table")

        call_kwargs = self.adapter.update_release.call_args.kwargs
        assert call_kwargs["notes"] == "Notes from file"

    def test_notes_file_none_uses_notes(self, sample_config):
        """--notes-file 未指定なら --notes の値を使用する。"""
        args = make_args(
            tag="v1.0.0",
            title=None,
            notes="Inline notes",
            draft=None,
            prerelease=None,
            notes_file=None,
        )
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_edit(args, fmt="table")

        call_kwargs = self.adapter.update_release.call_args.kwargs
        assert call_kwargs["notes"] == "Inline notes"

    def test_notes_file_not_found_raises_gfo_error(self, sample_config):
        """存在しないファイルを --notes-file に指定すると GfoError を送出する。"""
        args = make_args(
            tag="v1.0.0",
            title=None,
            notes=None,
            draft=None,
            prerelease=None,
            notes_file="nonexistent.txt",
        )
        with _patch_all(sample_config, self.adapter):
            with pytest.raises(GfoError, match="File not found"):
                release_cmd.handle_edit(args, fmt="table")

    def test_new_tag_passed_to_adapter(self, sample_config):
        args = make_args(
            tag="v1.0.0",
            title=None,
            notes=None,
            draft=None,
            prerelease=None,
            new_tag="v1.0.1",
            target=None,
        )
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_edit(args, fmt="table")

        call_kwargs = self.adapter.update_release.call_args.kwargs
        assert call_kwargs["new_tag"] == "v1.0.1"
        assert call_kwargs["target"] is None

    def test_target_passed_to_adapter(self, sample_config):
        args = make_args(
            tag="v1.0.0",
            title=None,
            notes=None,
            draft=None,
            prerelease=None,
            new_tag=None,
            target="main",
        )
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_edit(args, fmt="table")

        call_kwargs = self.adapter.update_release.call_args.kwargs
        assert call_kwargs["target"] == "main"

    def test_new_tag_and_target_combined(self, sample_config):
        args = make_args(
            tag="v1.0.0",
            title=None,
            notes=None,
            draft=None,
            prerelease=None,
            new_tag="v2.0.0",
            target="develop",
        )
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_edit(args, fmt="table")

        call_kwargs = self.adapter.update_release.call_args.kwargs
        assert call_kwargs["new_tag"] == "v2.0.0"
        assert call_kwargs["target"] == "develop"

    def test_empty_tag_raises_config_error(self, sample_config):
        args = make_args(tag="", title=None, notes=None, draft=None, prerelease=None)
        with _patch_all(sample_config, self.adapter):
            with pytest.raises(ConfigError):
                release_cmd.handle_edit(args, fmt="table")


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

    def test_asset_download_by_pattern(self, sample_config, capsys, tmp_path):
        self.adapter.list_release_assets.return_value = [self.asset]
        args = make_args(
            asset_action="download",
            tag="v1.0.0",
            asset_id=None,
            pattern="*.zip",
            dir=str(tmp_path),
        )
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_asset(args, fmt="table")

        # --pattern 経路ではメタ GET (download_release_asset) を呼ばず、
        # list_release_assets で得た download_url を client.download_file に渡す。
        self.adapter.download_release_asset.assert_not_called()
        self.adapter.client.download_file.assert_called_once_with(
            self.asset.download_url,
            str(tmp_path / self.asset.name),
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

    def test_asset_edit(self, sample_config, capsys):
        self.adapter.update_release_asset.return_value = self.asset
        args = make_args(asset_action="edit", tag="v1.0.0", asset_id="1", name="renamed.zip")
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_asset(args, fmt="json")

        self.adapter.update_release_asset.assert_called_once_with(
            tag="v1.0.0",
            asset_id="1",
            name="renamed.zip",
        )
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data[0]["name"] == "app-v1.0.0.zip"

    def test_asset_edit_no_name(self, sample_config):
        self.adapter.update_release_asset.return_value = self.asset
        args = make_args(asset_action="edit", tag="v1.0.0", asset_id="1", name=None)
        with _patch_all(sample_config, self.adapter):
            release_cmd.handle_asset(args, fmt="table")

        self.adapter.update_release_asset.assert_called_once_with(
            tag="v1.0.0",
            asset_id="1",
            name=None,
        )

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


class TestHandleListWeb:
    def setup_method(self):
        self.release = _make_release()
        self.adapter = _make_adapter(self.release)

    def test_opens_browser(self, sample_config):
        args = make_args(limit=30, web=True)
        with (
            _patch_all(sample_config, self.adapter),
            patch("webbrowser.open") as mock_open,
        ):
            release_cmd.handle_list(args, fmt="table")
        self.adapter.get_web_url.assert_called_once_with("release")
        mock_open.assert_called_once_with(self.adapter.get_web_url.return_value)

    def test_does_not_call_api(self, sample_config):
        args = make_args(limit=30, web=True)
        with (
            _patch_all(sample_config, self.adapter),
            patch("webbrowser.open"),
        ):
            release_cmd.handle_list(args, fmt="table")
        self.adapter.list_releases.assert_not_called()


class TestHandleCreateWeb:
    def setup_method(self):
        self.release = _make_release()
        self.adapter = _make_adapter(self.release)

    def test_opens_browser_after_create(self, sample_config):
        args = make_args(
            tag="v1.0.0",
            title="Version 1.0.0",
            notes="Release notes",
            draft=False,
            prerelease=False,
            web=True,
        )
        with (
            _patch_all(sample_config, self.adapter),
            patch("webbrowser.open") as mock_open,
        ):
            release_cmd.handle_create(args, fmt="table")
        self.adapter.create_release.assert_called_once()
        mock_open.assert_called_once_with(
            "https://github.com/test-owner/test-repo/releases/tag/v1.0.0"
        )

    def test_does_not_open_browser_without_flag(self, sample_config):
        args = make_args(
            tag="v1.0.0",
            title="Version 1.0.0",
            notes="Release notes",
            draft=False,
            prerelease=False,
        )
        with (
            _patch_all(sample_config, self.adapter),
            patch("webbrowser.open") as mock_open,
        ):
            release_cmd.handle_create(args, fmt="table")
        mock_open.assert_not_called()


class TestReleaseCreateWebArgParsing:
    def test_web_flag_parsed(self):
        from gfo.cli import create_parser

        parser, _ = create_parser()
        ns = parser.parse_args(["release", "create", "v1.0.0", "--web"])
        assert ns.web is True

    def test_web_short_flag_parsed(self):
        from gfo.cli import create_parser

        parser, _ = create_parser()
        ns = parser.parse_args(["release", "create", "v1.0.0", "-w"])
        assert ns.web is True

    def test_web_default_is_false(self):
        from gfo.cli import create_parser

        parser, _ = create_parser()
        ns = parser.parse_args(["release", "create", "v1.0.0"])
        assert ns.web is False


class TestReleaseListWebArgParsing:
    def test_web_flag_parsed(self):
        from gfo.cli import create_parser

        parser, _ = create_parser()
        ns = parser.parse_args(["release", "list", "--web"])
        assert ns.web is True

    def test_web_short_flag_parsed(self):
        from gfo.cli import create_parser

        parser, _ = create_parser()
        ns = parser.parse_args(["release", "list", "-w"])
        assert ns.web is True

    def test_web_default_is_false(self):
        from gfo.cli import create_parser

        parser, _ = create_parser()
        ns = parser.parse_args(["release", "list"])
        assert ns.web is False


class TestHandleViewWeb:
    def setup_method(self):
        self.release = _make_release()
        self.adapter = _make_adapter(self.release)

    def test_opens_browser_with_tag(self, sample_config):
        args = make_args(tag="v1.0.0", latest=False, web=True)
        with (
            _patch_all(sample_config, self.adapter),
            patch("webbrowser.open") as mock_open,
        ):
            release_cmd.handle_view(args, fmt="table")
        self.adapter.get_web_url.assert_called_once_with("release", "v1.0.0")
        mock_open.assert_called_once_with(self.adapter.get_web_url.return_value)

    def test_opens_browser_with_latest(self, sample_config):
        args = make_args(tag=None, latest=True, web=True)
        with (
            _patch_all(sample_config, self.adapter),
            patch("webbrowser.open") as mock_open,
        ):
            release_cmd.handle_view(args, fmt="table")
        self.adapter.get_latest_release.assert_called_once()
        self.adapter.get_web_url.assert_called_once_with("release", "v1.0.0")
        mock_open.assert_called_once_with(self.adapter.get_web_url.return_value)

    def test_does_not_call_get_release(self, sample_config):
        args = make_args(tag="v1.0.0", latest=False, web=True)
        with (
            _patch_all(sample_config, self.adapter),
            patch("webbrowser.open"),
        ):
            release_cmd.handle_view(args, fmt="table")
        self.adapter.get_release.assert_not_called()

    def test_empty_tag_no_latest_raises(self, sample_config):
        args = make_args(tag=None, latest=False, web=True)
        with (
            _patch_all(sample_config, self.adapter),
            patch("webbrowser.open"),
        ):
            with pytest.raises(ConfigError, match="tag must not be empty"):
                release_cmd.handle_view(args, fmt="table")
