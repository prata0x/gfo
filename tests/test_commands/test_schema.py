"""gfo.commands.schema のテスト。"""

from __future__ import annotations

import json

import pytest

from gfo.adapter.base import Label, PullRequest, Webhook, WikiPage
from gfo.cli import create_parser
from gfo.commands.schema import (
    _dataclass_to_json_schema,
    _parser_to_input_schema,
    _python_type_to_json_schema,
    handle_schema,
)
from gfo.exceptions import ConfigError, GfoError
from tests.test_commands.conftest import make_args

# ---- 型変換ユニットテスト ----


class TestPythonTypeToJsonSchema:
    def test_type_str(self):
        assert _python_type_to_json_schema(str) == {"type": "string"}

    def test_type_int(self):
        assert _python_type_to_json_schema(int) == {"type": "integer"}

    def test_type_bool(self):
        assert _python_type_to_json_schema(bool) == {"type": "boolean"}

    def test_type_optional_str(self):
        schema = _python_type_to_json_schema(str | None)
        assert schema == {"type": ["string", "null"]}

    def test_type_list_str(self):
        schema = _python_type_to_json_schema(list[str])
        assert schema == {"type": "array", "items": {"type": "string"}}

    def test_type_tuple_str_ellipsis(self):
        schema = _python_type_to_json_schema(tuple[str, ...])
        assert schema == {"type": "array", "items": {"type": "string"}}

    def test_type_union_int_str(self):
        schema = _python_type_to_json_schema(int | str)
        assert schema == {"oneOf": [{"type": "integer"}, {"type": "string"}]}


# ---- データクラス → スキーマ ----


class TestDataclassToJsonSchema:
    def test_dataclass_label(self):
        schema = _dataclass_to_json_schema(Label)
        assert schema["type"] == "object"
        assert "name" in schema["properties"]
        assert "color" in schema["properties"]
        assert "description" in schema["properties"]
        assert schema["properties"]["name"] == {"type": "string"}
        assert schema["properties"]["color"] == {"type": ["string", "null"]}
        assert "name" in schema["required"]

    def test_dataclass_pull_request(self):
        schema = _dataclass_to_json_schema(PullRequest)
        assert schema["type"] == "object"
        props = schema["properties"]
        assert props["number"] == {"type": "integer"}
        assert props["body"] == {"type": ["string", "null"]}
        assert props["draft"] == {"type": "boolean"}
        # updated_at にはデフォルト値があるので required に含まれない
        assert "updated_at" not in schema["required"]
        assert "number" in schema["required"]

    def test_dataclass_webhook(self):
        schema = _dataclass_to_json_schema(Webhook)
        props = schema["properties"]
        assert props["events"] == {"type": "array", "items": {"type": "string"}}

    def test_dataclass_wiki_page_union(self):
        """WikiPage.id は int | str。"""
        schema = _dataclass_to_json_schema(WikiPage)
        props = schema["properties"]
        assert props["id"] == {"oneOf": [{"type": "integer"}, {"type": "string"}]}


# ---- argparse → 入力スキーマ ----


class TestParserToInputSchema:
    def setup_method(self):
        _, self.subparser_map = create_parser()

    def _get_subcmd_parser(self, cmd, subcmd):
        import argparse as _ap

        cmd_parser = self.subparser_map[cmd]
        for action in cmd_parser._actions:
            if isinstance(action, _ap._SubParsersAction):
                return action.choices[subcmd]
        raise KeyError(subcmd)

    def test_parser_pr_list(self):
        parser = self._get_subcmd_parser("pr", "list")
        schema = _parser_to_input_schema(parser)
        props = schema["properties"]
        assert "state" in props
        assert props["state"]["enum"] == ["open", "closed", "merged", "all"]
        assert props["state"]["default"] == "open"
        assert "limit" in props
        assert props["limit"]["type"] == "integer"
        assert props["limit"]["default"] == 30

    def test_parser_pr_create(self):
        parser = self._get_subcmd_parser("pr", "create")
        schema = _parser_to_input_schema(parser)
        props = schema["properties"]
        assert "draft" in props
        assert props["draft"]["type"] == "boolean"

    def test_parser_positional_arg(self):
        parser = self._get_subcmd_parser("pr", "view")
        schema = _parser_to_input_schema(parser)
        assert "number" in schema.get("required", [])

    def test_parser_branch_protect_set_boolean_pairs(self):
        """store_true / store_false ペアが重複せず1つにまとまる。"""
        parser = self._get_subcmd_parser("branch-protect", "set")
        schema = _parser_to_input_schema(parser)
        props = schema["properties"]
        assert props["enforce_admins"]["type"] == "boolean"

    def test_parser_append_action(self):
        """webhook create --event は append アクション。"""
        parser = self._get_subcmd_parser("webhook", "create")
        schema = _parser_to_input_schema(parser)
        props = schema["properties"]
        assert props["event"]["type"] == "array"
        assert props["event"]["items"] == {"type": "string"}

    def test_parser_nargs_plus(self):
        """branch-protect set --require-status-checks は nargs='+'。"""
        parser = self._get_subcmd_parser("branch-protect", "set")
        schema = _parser_to_input_schema(parser)
        props = schema["properties"]
        assert props["require_status_checks"]["type"] == "array"


# ---- ハンドラ統合テスト ----


class TestHandleSchema:
    def test_list_commands(self, capsys):
        args = make_args(command="schema", subcommand=None, list_commands=True, target=[])
        handle_schema(args, fmt="json")
        out = json.loads(capsys.readouterr().out)
        assert isinstance(out, list)
        assert len(out) > 0
        commands = [item["command"] for item in out]
        assert "pr list" in commands
        assert "browse" in commands

    def test_schema_pr_list(self, capsys):
        args = make_args(
            command="schema", subcommand=None, list_commands=False, target=["pr", "list"]
        )
        handle_schema(args, fmt="json")
        out = json.loads(capsys.readouterr().out)
        assert out["command"] == "pr list"
        assert "input" in out
        assert "output" in out
        assert out["input"]["type"] == "object"

    def test_schema_pr_list_output_is_array(self, capsys):
        args = make_args(
            command="schema", subcommand=None, list_commands=False, target=["pr", "list"]
        )
        handle_schema(args, fmt="json")
        out = json.loads(capsys.readouterr().out)
        assert out["output"]["type"] == "array"
        assert "properties" in out["output"]["items"]

    def test_schema_void_command(self, capsys):
        args = make_args(
            command="schema", subcommand=None, list_commands=False, target=["pr", "merge"]
        )
        handle_schema(args, fmt="json")
        out = json.loads(capsys.readouterr().out)
        assert out["output"] is None

    def test_schema_command_group(self, capsys):
        args = make_args(command="schema", subcommand=None, list_commands=False, target=["pr"])
        handle_schema(args, fmt="json")
        out = json.loads(capsys.readouterr().out)
        assert isinstance(out, list)
        commands = [item["command"] for item in out]
        assert "pr list" in commands
        assert "pr create" in commands
        assert "pr merge" in commands

    def test_schema_unknown_command(self):
        args = make_args(
            command="schema", subcommand=None, list_commands=False, target=["nonexistent", "foo"]
        )
        with pytest.raises(ConfigError):
            handle_schema(args, fmt="json")

    def test_schema_unknown_group(self):
        args = make_args(
            command="schema", subcommand=None, list_commands=False, target=["nonexistent"]
        )
        with pytest.raises(ConfigError):
            handle_schema(args, fmt="json")

    def test_schema_no_args_shows_list(self, capsys):
        args = make_args(command="schema", subcommand=None, list_commands=False, target=[])
        handle_schema(args, fmt="json")
        out = json.loads(capsys.readouterr().out)
        assert isinstance(out, list)
        assert len(out) > 0

    def test_jq_filter_applied(self, capsys):
        args = make_args(
            command="schema", subcommand=None, list_commands=False, target=["pr", "list"]
        )
        try:
            handle_schema(args, fmt="json", jq=".command")
        except GfoError:
            pytest.skip("jq not available")
        out = capsys.readouterr().out.strip()
        assert out == '"pr list"'

    def test_schema_browse_single_command(self, capsys):
        """サブコマンドなしのコマンド（browse）のスキーマ。"""
        args = make_args(command="schema", subcommand=None, list_commands=False, target=["browse"])
        handle_schema(args, fmt="json")
        out = json.loads(capsys.readouterr().out)
        assert out["command"] == "browse"
        assert "input" in out

    def test_schema_file_get_special_output(self, capsys):
        """file get の特殊出力スキーマ。"""
        args = make_args(
            command="schema", subcommand=None, list_commands=False, target=["file", "get"]
        )
        handle_schema(args, fmt="json")
        out = json.loads(capsys.readouterr().out)
        assert out["output"]["type"] == "object"
        assert "content" in out["output"]["properties"]
        assert "sha" in out["output"]["properties"]

    def test_schema_collaborator_list_output(self, capsys):
        """collaborator list は list[str] を返す。"""
        args = make_args(
            command="schema", subcommand=None, list_commands=False, target=["collaborator", "list"]
        )
        handle_schema(args, fmt="json")
        out = json.loads(capsys.readouterr().out)
        assert out["output"]["type"] == "array"
        assert out["output"]["items"] == {"type": "string"}

    def test_output_map_covers_dispatch(self):
        """_OUTPUT_MAP が _DISPATCH の全キーをカバーしている。"""
        from gfo.cli import _DISPATCH
        from gfo.commands.schema import _OUTPUT_MAP

        missing = set(_DISPATCH.keys()) - set(_OUTPUT_MAP.keys()) - {("schema", None)}
        assert missing == set(), f"_OUTPUT_MAP に不足: {missing}"
