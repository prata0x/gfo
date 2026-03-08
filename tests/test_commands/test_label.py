"""gfo.commands.label のテスト。"""

from __future__ import annotations

import contextlib
import json
from unittest.mock import MagicMock, patch

from gfo.adapter.base import Label
from gfo.commands import label as label_cmd
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
    with patch("gfo.commands.label.resolve_project_config", return_value=config), \
         patch("gfo.commands.label.create_adapter", return_value=adapter):
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
        if isinstance(data, list):
            assert data[0]["name"] == "bug"
        else:
            assert data["name"] == "bug"

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
        item = data[0] if isinstance(data, list) else data
        assert "name" in item
        assert "color" in item
        assert "description" in item


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
            color="#d73a4a",
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
        assert data["name"] == "bug"

    def test_create_adapter_error_propagates(self, sample_config):
        self.adapter.create_label.side_effect = RuntimeError("API error")
        args = make_args(name="bug", color="#d73a4a", description=None)
        with _patch_all(sample_config, self.adapter):
            try:
                label_cmd.handle_create(args, fmt="table")
                assert False, "例外が伝播されるべき"
            except RuntimeError as e:
                assert "API error" in str(e)

    def test_create_name_forwarded_correctly(self, sample_config):
        args = make_args(name="wontfix", color="#ffffff", description="Will not fix")
        with _patch_all(sample_config, self.adapter):
            label_cmd.handle_create(args, fmt="table")

        call_kwargs = self.adapter.create_label.call_args.kwargs
        assert call_kwargs["name"] == "wontfix"
        assert call_kwargs["color"] == "#ffffff"
        assert call_kwargs["description"] == "Will not fix"
