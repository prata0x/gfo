"""gfo.commands.label のテスト。"""

from __future__ import annotations

import contextlib
import json
from unittest.mock import MagicMock, patch

import pytest

from gfo.adapter.base import Label
from gfo.commands import label as label_cmd
from gfo.exceptions import ConfigError
from tests.test_commands.conftest import make_args


def _make_label() -> Label:
    return Label(
        name="bug",
        color="#d73a4a",
        description="Something isn't working",
    )


def _make_adapter(sample_label: Label) -> MagicMock:
    adapter = MagicMock()
    adapter.list_labels.return_value = [sample_label]
    adapter.create_label.return_value = sample_label
    return adapter


@contextlib.contextmanager
def _patch_all(config, adapter: MagicMock):
    with patch("gfo.commands.label.get_adapter", return_value=adapter):
        yield


class TestHandleList:
    def setup_method(self):
        self.label = _make_label()
        self.adapter = _make_adapter(self.label)

    def test_calls_list_labels(self, sample_config):
        args = make_args()
        with _patch_all(sample_config, self.adapter):
            label_cmd.handle_list(args, fmt="table")

        self.adapter.list_labels.assert_called_once_with()

    def test_outputs_results(self, sample_config, capsys):
        args = make_args()
        with _patch_all(sample_config, self.adapter):
            label_cmd.handle_list(args, fmt="table")

        out = capsys.readouterr().out
        assert "bug" in out

    def test_json_format(self, sample_config, capsys):
        args = make_args()
        with _patch_all(sample_config, self.adapter):
            label_cmd.handle_list(args, fmt="json")

        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, list)
        assert data[0]["name"] == "bug"

    def test_table_output_includes_color(self, sample_config, capsys):
        args = make_args()
        with _patch_all(sample_config, self.adapter):
            label_cmd.handle_list(args, fmt="table")

        out = capsys.readouterr().out
        assert "#d73a4a" in out

    def test_table_output_includes_description(self, sample_config, capsys):
        args = make_args()
        with _patch_all(sample_config, self.adapter):
            label_cmd.handle_list(args, fmt="table")

        out = capsys.readouterr().out
        assert "Something isn't working" in out

    def test_empty_list(self, sample_config, capsys):
        self.adapter.list_labels.return_value = []
        args = make_args()
        with _patch_all(sample_config, self.adapter):
            label_cmd.handle_list(args, fmt="table")

        # 空リストでも例外なく実行される
        self.adapter.list_labels.assert_called_once_with()

    def test_json_format_has_all_fields(self, sample_config, capsys):
        args = make_args()
        with _patch_all(sample_config, self.adapter):
            label_cmd.handle_list(args, fmt="json")

        out = capsys.readouterr().out
        data = json.loads(out)
        item = data[0]
        assert "name" in item
        assert "color" in item
        assert "description" in item

    def test_plain_format(self, sample_config, capsys):
        args = make_args()
        with _patch_all(sample_config, self.adapter):
            label_cmd.handle_list(args, fmt="plain")

        out = capsys.readouterr().out
        assert "\t" in out
        assert "NAME" not in out
        assert "bug" in out


class TestHandleCreate:
    def setup_method(self):
        self.label = _make_label()
        self.adapter = _make_adapter(self.label)

    def test_basic_create(self, sample_config):
        args = make_args(name="bug", color="#d73a4a", description="Something isn't working")
        with _patch_all(sample_config, self.adapter):
            label_cmd.handle_create(args, fmt="table")

        self.adapter.create_label.assert_called_once_with(
            name="bug",
            color="d73a4a",
            description="Something isn't working",
        )

    def test_create_without_color(self, sample_config):
        args = make_args(name="enhancement", color=None, description=None)
        with _patch_all(sample_config, self.adapter):
            label_cmd.handle_create(args, fmt="table")

        self.adapter.create_label.assert_called_once_with(
            name="enhancement",
            color=None,
            description=None,
        )

    def test_create_outputs_label_name(self, sample_config, capsys):
        args = make_args(name="bug", color="#d73a4a", description="Something isn't working")
        with _patch_all(sample_config, self.adapter):
            label_cmd.handle_create(args, fmt="table")

        out = capsys.readouterr().out
        assert "bug" in out

    def test_create_json_format(self, sample_config, capsys):
        args = make_args(name="bug", color="#d73a4a", description="Something isn't working")
        with _patch_all(sample_config, self.adapter):
            label_cmd.handle_create(args, fmt="json")

        out = capsys.readouterr().out
        data = json.loads(out)
        item = data[0]
        assert item["name"] == "bug"

    def test_create_adapter_error_propagates(self, sample_config):
        self.adapter.create_label.side_effect = RuntimeError("API error")
        args = make_args(name="bug", color="#d73a4a", description=None)
        with _patch_all(sample_config, self.adapter):
            with pytest.raises(RuntimeError, match="API error"):
                label_cmd.handle_create(args, fmt="table")

    def test_create_name_forwarded_correctly(self, sample_config):
        args = make_args(name="wontfix", color="#ffffff", description="Will not fix")
        with _patch_all(sample_config, self.adapter):
            label_cmd.handle_create(args, fmt="table")

        call_kwargs = self.adapter.create_label.call_args.kwargs
        assert call_kwargs["name"] == "wontfix"
        assert call_kwargs["color"] == "ffffff"
        assert call_kwargs["description"] == "Will not fix"

    def test_color_without_hash_accepted(self, sample_config):
        """`#` なしの有効 hex カラーはそのまま受け入れる。"""
        args = make_args(name="bug", color="ff0000", description=None)
        with _patch_all(sample_config, self.adapter):
            label_cmd.handle_create(args, fmt="table")

        call_kwargs = self.adapter.create_label.call_args.kwargs
        assert call_kwargs["color"] == "ff0000"

    def test_invalid_color_raises_config_error(self, sample_config):
        """不正なカラーコードは ConfigError を送出する。"""
        args = make_args(name="bug", color="xyz123", description=None)
        with (
            _patch_all(sample_config, self.adapter),
            pytest.raises(ConfigError, match="Invalid color"),
        ):
            label_cmd.handle_create(args, fmt="table")

    def test_double_hash_color_raises_config_error(self, sample_config):
        """複数の `#` を持つカラーは ConfigError を送出する（lstrip→removeprefix 修正の確認）。"""
        args = make_args(name="bug", color="##ff0000", description=None)
        with (
            _patch_all(sample_config, self.adapter),
            pytest.raises(ConfigError, match="Invalid color"),
        ):
            label_cmd.handle_create(args, fmt="table")

    def test_name_with_surrounding_whitespace_is_stripped(self, sample_config):
        """前後に空白を持つ name は strip されてアダプターに渡される。"""
        args = make_args(name="  bug  ", color=None, description=None)
        with _patch_all(sample_config, self.adapter):
            label_cmd.handle_create(args, fmt="table")

        call_kwargs = self.adapter.create_label.call_args.kwargs
        assert call_kwargs["name"] == "bug"

    def test_whitespace_only_name_raises_config_error(self, sample_config):
        """空白のみの name は ConfigError を送出する。"""
        args = make_args(name="   ", color=None, description=None)
        with (
            _patch_all(sample_config, self.adapter),
            pytest.raises(ConfigError, match="name must not be empty"),
        ):
            label_cmd.handle_create(args, fmt="table")


class TestHandleDelete:
    def setup_method(self):
        self.label = _make_label()
        self.adapter = _make_adapter(self.label)

    def test_delete_calls_adapter(self, sample_config):
        args = make_args(name="bug")
        with _patch_all(sample_config, self.adapter):
            label_cmd.handle_delete(args, fmt="table")

        self.adapter.delete_label.assert_called_once_with(name="bug")

    def test_delete_prints_message(self, sample_config, capsys):
        args = make_args(name="bug")
        with _patch_all(sample_config, self.adapter):
            label_cmd.handle_delete(args, fmt="table")

        out = capsys.readouterr().out
        assert "bug" in out
        assert "Deleted" in out

    def test_whitespace_only_name_raises_config_error(self, sample_config):
        args = make_args(name="   ")
        with _patch_all(sample_config, self.adapter):
            with pytest.raises(ConfigError, match="name must not be empty"):
                label_cmd.handle_delete(args, fmt="table")

    def test_name_stripped_before_call(self, sample_config):
        args = make_args(name="  bug  ")
        with _patch_all(sample_config, self.adapter):
            label_cmd.handle_delete(args, fmt="table")

        self.adapter.delete_label.assert_called_once_with(name="bug")


class TestHandleUpdate:
    def setup_method(self):
        self.label = _make_label()
        self.adapter = _make_adapter(self.label)

    def test_basic_update(self, sample_config):
        self.adapter.update_label.return_value = self.label
        args = make_args(name="bug", new_name=None, color=None, description=None)
        with _patch_all(sample_config, self.adapter):
            label_cmd.handle_update(args, fmt="table")
        self.adapter.update_label.assert_called_once_with(
            name="bug", new_name=None, color=None, description=None
        )

    def test_with_color(self, sample_config):
        self.adapter.update_label.return_value = self.label
        args = make_args(name="bug", new_name=None, color="ff0000", description=None)
        with _patch_all(sample_config, self.adapter):
            label_cmd.handle_update(args, fmt="table")
        self.adapter.update_label.assert_called_once_with(
            name="bug", new_name=None, color="ff0000", description=None
        )

    def test_with_color_hash_prefix(self, sample_config):
        self.adapter.update_label.return_value = self.label
        args = make_args(name="bug", new_name=None, color="#ff0000", description=None)
        with _patch_all(sample_config, self.adapter):
            label_cmd.handle_update(args, fmt="table")
        self.adapter.update_label.assert_called_once_with(
            name="bug", new_name=None, color="ff0000", description=None
        )

    def test_invalid_color(self, sample_config):
        args = make_args(name="bug", new_name=None, color="xyz", description=None)
        with _patch_all(sample_config, self.adapter):
            with pytest.raises(ConfigError):
                label_cmd.handle_update(args, fmt="table")

    def test_json_format(self, sample_config, capsys):
        self.adapter.update_label.return_value = self.label
        args = make_args(name="bug", new_name=None, color=None, description=None)
        with _patch_all(sample_config, self.adapter):
            label_cmd.handle_update(args, fmt="json")
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data[0]["name"] == "bug"

    def test_whitespace_only_name_raises_config_error(self, sample_config):
        args = make_args(name="   ", new_name=None, color=None, description=None)
        with _patch_all(sample_config, self.adapter):
            with pytest.raises(ConfigError, match="name must not be empty"):
                label_cmd.handle_update(args, fmt="table")

    def test_name_stripped_before_call(self, sample_config):
        self.adapter.update_label.return_value = self.label
        args = make_args(name="  bug  ", new_name=None, color=None, description=None)
        with _patch_all(sample_config, self.adapter):
            label_cmd.handle_update(args, fmt="table")
        self.adapter.update_label.assert_called_once_with(
            name="bug", new_name=None, color=None, description=None
        )


# --- Phase 5: label clone ---


class TestHandleClone:
    def test_clone_labels(self, sample_config, capsys):
        from gfo.config import ProjectConfig

        mock_cfg = ProjectConfig(
            service_type="github",
            host="github.com",
            api_url="https://api.github.com",
            owner="src-owner",
            repo="src-repo",
        )
        source_adapter = MagicMock()
        source_adapter.list_labels.return_value = [_make_label()]
        dest_adapter = MagicMock()
        dest_adapter.list_labels.return_value = []

        mock_adapter_cls = MagicMock(return_value=source_adapter)

        with (
            patch("gfo.commands.label.get_adapter", return_value=dest_adapter),
            patch("gfo.config.resolve_project_config", return_value=mock_cfg),
            patch("gfo.auth.resolve_token", return_value="test-token"),
            patch("gfo.config.build_default_api_url", return_value="https://api.github.com"),
            patch("gfo.adapter.registry.create_http_client"),
            patch("gfo.adapter.registry.get_adapter_class", return_value=mock_adapter_cls),
        ):
            args = make_args(source="src-owner/src-repo", overwrite=False)
            label_cmd.handle_clone(args, fmt="table")
        dest_adapter.create_label.assert_called_once()
