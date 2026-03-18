"""gfo.commands.issue_template のテスト。"""

from __future__ import annotations

import json

import pytest

from gfo.adapter.base import IssueTemplate
from gfo.commands import issue_template as it_cmd
from gfo.exceptions import HttpError
from tests.test_commands.conftest import make_args, patch_adapter

SAMPLE_TEMPLATE = IssueTemplate(
    name="Bug Report",
    title="[Bug]: ",
    body="## Description\n...",
    about="Report a bug",
    labels=("bug",),
)


class TestHandleList:
    def test_calls_list_issue_templates(self, capsys):
        with patch_adapter("gfo.commands.issue_template") as adapter:
            adapter.list_issue_templates.return_value = [SAMPLE_TEMPLATE]
            args = make_args()
            it_cmd.handle_list(args, fmt="table")
        adapter.list_issue_templates.assert_called_once()
        out = capsys.readouterr().out
        assert "Bug Report" in out

    def test_json_format(self, capsys):
        with patch_adapter("gfo.commands.issue_template") as adapter:
            adapter.list_issue_templates.return_value = [SAMPLE_TEMPLATE]
            args = make_args()
            it_cmd.handle_list(args, fmt="json")
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert isinstance(parsed, list)
        assert parsed[0]["name"] == "Bug Report"

    def test_error_propagation(self):
        with patch_adapter("gfo.commands.issue_template") as adapter:
            adapter.list_issue_templates.side_effect = HttpError(500, "Server error")
            args = make_args()
            with pytest.raises(HttpError):
                it_cmd.handle_list(args, fmt="table")

    def test_empty_list(self, capsys):
        with patch_adapter("gfo.commands.issue_template") as adapter:
            adapter.list_issue_templates.return_value = []
            args = make_args()
            it_cmd.handle_list(args, fmt="table")
        out = capsys.readouterr().out
        assert "Bug Report" not in out
