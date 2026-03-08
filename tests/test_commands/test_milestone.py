"""gfo.commands.milestone のテスト。"""

from __future__ import annotations

import contextlib
import json
from unittest.mock import MagicMock, patch

from gfo.adapter.base import Milestone
from gfo.commands import milestone as milestone_cmd
from tests.test_commands.conftest import make_args


def _make_milestone() -> Milestone:
    return Milestone(
        number=1,
        title="v1.0",
        description="First release",
        state="open",
        due_date="2026-04-01",
    )


def _make_adapter(sample_milestone: Milestone) -> MagicMock:
    adapter = MagicMock()
    adapter.list_milestones.return_value = [sample_milestone]
    adapter.create_milestone.return_value = sample_milestone
    return adapter


@contextlib.contextmanager
def _patch_all(config, adapter: MagicMock):
    with patch("gfo.commands.milestone.resolve_project_config", return_value=config), \
         patch("gfo.commands.milestone.create_adapter", return_value=adapter):
        yield


class TestHandleList:
    def setup_method(self):
        self.milestone = _make_milestone()
        self.adapter = _make_adapter(self.milestone)

    def test_calls_list_milestones(self, sample_config):
        args = make_args()
        with _patch_all(sample_config, self.adapter):
            milestone_cmd.handle_list(args, fmt="table")

        self.adapter.list_milestones.assert_called_once_with()

    def test_outputs_results(self, sample_config, capsys):
        args = make_args()
        with _patch_all(sample_config, self.adapter):
            milestone_cmd.handle_list(args, fmt="table")

        out = capsys.readouterr().out
        assert "v1.0" in out

    def test_json_format(self, sample_config, capsys):
        args = make_args()
        with _patch_all(sample_config, self.adapter):
            milestone_cmd.handle_list(args, fmt="json")

        out = capsys.readouterr().out
        data = json.loads(out)
        if isinstance(data, list):
            assert data[0]["title"] == "v1.0"
        else:
            assert data["title"] == "v1.0"


class TestHandleCreate:
    def setup_method(self):
        self.milestone = _make_milestone()
        self.adapter = _make_adapter(self.milestone)

    def test_basic_create(self, sample_config):
        args = make_args(title="v1.0", description="First release", due="2026-04-01")
        with _patch_all(sample_config, self.adapter):
            milestone_cmd.handle_create(args, fmt="table")

        self.adapter.create_milestone.assert_called_once_with(
            title="v1.0",
            description="First release",
            due_date="2026-04-01",
        )

    def test_create_without_optional_args(self, sample_config):
        args = make_args(title="v2.0", description=None, due=None)
        with _patch_all(sample_config, self.adapter):
            milestone_cmd.handle_create(args, fmt="table")

        self.adapter.create_milestone.assert_called_once_with(
            title="v2.0",
            description=None,
            due_date=None,
        )

    def test_due_to_due_date_mapping(self, sample_config):
        args = make_args(title="v3.0", description=None, due="2026-06-30")
        with _patch_all(sample_config, self.adapter):
            milestone_cmd.handle_create(args, fmt="table")

        call_kwargs = self.adapter.create_milestone.call_args.kwargs
        assert "due_date" in call_kwargs
        assert call_kwargs["due_date"] == "2026-06-30"
        assert "due" not in call_kwargs
