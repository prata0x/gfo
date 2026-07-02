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

    def test_too_many_arguments(self):
        """孫サブコマンドを持たないコマンドに 3 個目を渡すと ConfigError。"""
        args = make_args(
            command="schema", subcommand=None, list_commands=False, target=["pr", "list", "extra"]
        )
        with pytest.raises(ConfigError):
            handle_schema(args, fmt="json")

    def test_too_many_arguments_four_elements(self):
        """target に 4 個以上渡すと ConfigError。"""
        args = make_args(
            command="schema",
            subcommand=None,
            list_commands=False,
            target=["release", "asset", "delete", "extra"],
        )
        with pytest.raises(ConfigError):
            handle_schema(args, fmt="json")

    def test_all_commands_have_descriptions(self, capsys):
        """全コマンドの description が空でないこと。"""
        args = make_args(command="schema", subcommand=None, list_commands=True, target=[])
        handle_schema(args, fmt="json")
        out = json.loads(capsys.readouterr().out)
        empty = [item["command"] for item in out if not item["description"]]
        assert empty == [], f"Commands with empty description: {empty}"

    def test_all_arguments_have_descriptions(self, capsys):
        """全コマンドの全パラメータに description があること。"""
        args = make_args(command="schema", subcommand=None, list_commands=False, target=[])
        handle_schema(args, fmt="json")
        out = json.loads(capsys.readouterr().out)
        missing = []
        for cmd in out:
            if "input" not in cmd:
                continue
            props = cmd["input"].get("properties", {})
            for prop_name, prop_val in props.items():
                if "description" not in prop_val:
                    missing.append(f"{cmd['command']}.{prop_name}")
        assert missing == [], f"Arguments without description: {missing}"


class TestParserNargsOptional:
    """nargs='?' の位置引数が required に含まれないこと（H4）。"""

    def setup_method(self):
        _, self.subparser_map = create_parser()

    def _get_subcmd_parser(self, cmd, subcmd):
        import argparse as _ap

        cmd_parser = self.subparser_map[cmd]
        for action in cmd_parser._actions:
            if isinstance(action, _ap._SubParsersAction):
                return action.choices[subcmd]
        raise KeyError(subcmd)

    def test_repo_view_repo_not_required(self):
        """repo view の repo (nargs='?') は required に含まれない。"""
        parser = self._get_subcmd_parser("repo", "view")
        schema = _parser_to_input_schema(parser)
        assert "repo" not in schema.get("required", [])

    def test_notification_read_id_not_required(self):
        """notification read の id (nargs='?') は required に含まれない。"""
        parser = self._get_subcmd_parser("notification", "read")
        schema = _parser_to_input_schema(parser)
        assert "id" not in schema.get("required", [])


class TestOutputMapDictSync:
    """_OUTPUT_MAP で dict 型のエントリが全て _SPECIAL_OUTPUT に存在する（M2）。"""

    def test_dict_entries_in_special_output(self):
        from gfo.commands.schema import _OUTPUT_MAP, _SPECIAL_OUTPUT

        dict_keys = [k for k, v in _OUTPUT_MAP.items() if v is dict]
        for k in dict_keys:
            assert k in _SPECIAL_OUTPUT, f"{k} は _OUTPUT_MAP で dict だが _SPECIAL_OUTPUT にない"


class TestSchemaAlwaysEnglish:
    """schema 出力はロケールに関係なく常に英語であること。"""

    def test_parameter_descriptions_english(self, capsys):
        """翻訳関数が有効でも schema の description は英語 msgid のまま。"""
        import gfo.cli

        original = gfo.cli._
        gfo.cli._ = lambda s: f"[翻訳]{s}"
        try:
            args = make_args(
                command="schema", subcommand=None, list_commands=False, target=["pr", "list"]
            )
            handle_schema(args, fmt="json")
        finally:
            gfo.cli._ = original
        out = json.loads(capsys.readouterr().out)
        props = out["input"]["properties"]
        # description に翻訳マーカーが混入していないこと
        for name, prop in props.items():
            desc = prop.get("description", "")
            assert "[翻訳]" not in desc, f"{name} の description に翻訳が混入: {desc}"

    def test_command_descriptions_english(self, capsys):
        """翻訳関数が有効でも schema --list の description は英語。"""
        import gfo.cli

        original = gfo.cli._
        gfo.cli._ = lambda s: f"[翻訳]{s}"
        try:
            args = make_args(command="schema", subcommand=None, list_commands=True, target=[])
            handle_schema(args, fmt="json")
        finally:
            gfo.cli._ = original
        out = json.loads(capsys.readouterr().out)
        for item in out:
            desc = item.get("description", "")
            assert "[翻訳]" not in desc, f"{item['command']} の description に翻訳が混入: {desc}"


# ---- 孫サブコマンド（#58） ----


def _discover_grandchild_triples():
    """create_parser() から (command, subcommand, action) の全組を動的に発見する。"""
    import argparse as _ap

    from gfo.cli import create_parser

    _, subparser_map = create_parser()
    triples = []
    for command, cmd_parser in subparser_map.items():
        for cmd_action in cmd_parser._actions:
            if not isinstance(cmd_action, _ap._SubParsersAction):
                continue
            for subcommand, sub_parser in cmd_action.choices.items():
                for sub_action in sub_parser._actions:
                    if not isinstance(sub_action, _ap._SubParsersAction):
                        continue
                    for action in sub_action.choices:
                        triples.append((command, subcommand, action))
    return triples


class TestGrandchildSchema:
    """孫サブコマンド（release asset delete 等）の schema 取得（#58）。"""

    def test_grandchild_single_command(self, capsys):
        args = make_args(
            command="schema",
            subcommand=None,
            list_commands=False,
            target=["release", "asset", "delete"],
        )
        handle_schema(args, fmt="json")
        out = json.loads(capsys.readouterr().out)
        assert out["command"] == "release asset delete"
        assert "asset_id" in out["input"]["properties"]
        assert out["output"] is None

    def test_grandchild_output_dataclass(self, capsys):
        """release asset upload は単一オブジェクトを返す。"""
        args = make_args(
            command="schema",
            subcommand=None,
            list_commands=False,
            target=["release", "asset", "upload"],
        )
        handle_schema(args, fmt="json")
        out = json.loads(capsys.readouterr().out)
        assert out["output"]["type"] == "object"
        assert "download_url" in out["output"]["properties"]

    def test_grandchild_list_str_output(self, capsys):
        """repo topics add は list[str] を返す。"""
        args = make_args(
            command="schema",
            subcommand=None,
            list_commands=False,
            target=["repo", "topics", "add"],
        )
        handle_schema(args, fmt="json")
        out = json.loads(capsys.readouterr().out)
        assert out["output"] == {"type": "array", "items": {"type": "string"}}

    def test_grandchild_group_returns_array(self, capsys):
        """2 要素指定が孫グループの場合は action 別スキーマの配列を返す。"""
        args = make_args(
            command="schema", subcommand=None, list_commands=False, target=["release", "asset"]
        )
        handle_schema(args, fmt="json")
        out = json.loads(capsys.readouterr().out)
        assert isinstance(out, list)
        commands = [item["command"] for item in out]
        assert commands == [
            "release asset list",
            "release asset upload",
            "release asset download",
            "release asset edit",
            "release asset delete",
        ]

    def test_grandchild_unknown_action(self):
        args = make_args(
            command="schema",
            subcommand=None,
            list_commands=False,
            target=["release", "asset", "nonexistent"],
        )
        with pytest.raises(ConfigError):
            handle_schema(args, fmt="json")

    def test_grandchild_on_non_grandchild_subcommand(self):
        """孫を持たないコマンドに 3 要素目を渡すと ConfigError。"""
        args = make_args(
            command="schema", subcommand=None, list_commands=False, target=["pr", "list", "extra"]
        )
        with pytest.raises(ConfigError):
            handle_schema(args, fmt="json")

    def test_grandchild_unknown_command_subcommand(self):
        args = make_args(
            command="schema",
            subcommand=None,
            list_commands=False,
            target=["nonexistent", "asset", "delete"],
        )
        with pytest.raises(ConfigError):
            handle_schema(args, fmt="json")

    def test_list_commands_includes_grandchildren(self, capsys):
        """schema --list に孫サブコマンドも含まれる。"""
        args = make_args(command="schema", subcommand=None, list_commands=True, target=[])
        handle_schema(args, fmt="json")
        out = json.loads(capsys.readouterr().out)
        commands = [item["command"] for item in out]
        assert "release asset delete" in commands
        assert "issue time add" in commands
        assert "batch pr create" in commands

    def test_grandchild_output_map_covers_all_actions(self):
        """_GRANDCHILD_OUTPUT_MAP が実際の argparse 構造の全 (command, subcommand, action) をカバーしている。"""
        from gfo.commands.schema import _GRANDCHILD_OUTPUT_MAP

        triples = set(_discover_grandchild_triples())
        missing = triples - set(_GRANDCHILD_OUTPUT_MAP.keys())
        assert missing == set(), f"_GRANDCHILD_OUTPUT_MAP に不足: {missing}"
        extra = set(_GRANDCHILD_OUTPUT_MAP.keys()) - triples
        assert extra == set(), f"_GRANDCHILD_OUTPUT_MAP に存在しない孫コマンド: {extra}"


# ---- 安全性メタデータ（#57） ----


def _has_yes_flag(parser):
    for action in parser._actions:
        if "--yes" in action.option_strings:
            return True
    return False


class TestSafetyMetadata:
    """schema の safety フィールド（#57）。"""

    def test_safety_present_in_single_command_schema(self, capsys):
        args = make_args(
            command="schema", subcommand=None, list_commands=False, target=["pr", "list"]
        )
        handle_schema(args, fmt="json")
        out = json.loads(capsys.readouterr().out)
        assert out["safety"] == {
            "destructive": False,
            "requires_confirmation": False,
            "prints_secret": False,
            "network_write": False,
            "local_git_write": False,
        }

    def test_safety_destructive_delete_command(self, capsys):
        args = make_args(
            command="schema", subcommand=None, list_commands=False, target=["issue", "delete"]
        )
        handle_schema(args, fmt="json")
        out = json.loads(capsys.readouterr().out)
        assert out["safety"]["destructive"] is True
        assert out["safety"]["requires_confirmation"] is True

    def test_safety_grandchild_destructive(self, capsys):
        args = make_args(
            command="schema",
            subcommand=None,
            list_commands=False,
            target=["release", "asset", "delete"],
        )
        handle_schema(args, fmt="json")
        out = json.loads(capsys.readouterr().out)
        assert out["safety"]["destructive"] is True
        assert out["safety"]["requires_confirmation"] is True

    def test_safety_grandchild_non_destructive(self, capsys):
        args = make_args(
            command="schema",
            subcommand=None,
            list_commands=False,
            target=["release", "asset", "list"],
        )
        handle_schema(args, fmt="json")
        out = json.loads(capsys.readouterr().out)
        assert out["safety"]["destructive"] is False

    def test_safety_prints_secret_auth_token(self, capsys):
        args = make_args(
            command="schema", subcommand=None, list_commands=False, target=["auth", "token"]
        )
        handle_schema(args, fmt="json")
        out = json.loads(capsys.readouterr().out)
        assert out["safety"]["prints_secret"] is True

    def test_safety_api_worst_case(self, capsys):
        """gfo api は method 次第で危険度が変わるため worst-case 固定値。"""
        args = make_args(command="schema", subcommand=None, list_commands=False, target=["api"])
        handle_schema(args, fmt="json")
        out = json.loads(capsys.readouterr().out)
        assert out["safety"]["destructive"] is True
        assert out["safety"]["network_write"] is True
        assert out["safety"]["requires_confirmation"] is False

    def test_safety_local_git_write_repo_clone(self, capsys):
        args = make_args(
            command="schema", subcommand=None, list_commands=False, target=["repo", "clone"]
        )
        handle_schema(args, fmt="json")
        out = json.loads(capsys.readouterr().out)
        assert out["safety"]["local_git_write"] is True
        assert out["safety"]["network_write"] is False

    def test_safety_map_covers_dispatch(self):
        """_SAFETY_MAP が _DISPATCH の全キーをカバーしている。"""
        from gfo.cli import _DISPATCH
        from gfo.commands.schema import _SAFETY_MAP

        missing = set(_DISPATCH.keys()) - set(_SAFETY_MAP.keys()) - {("schema", None)}
        assert missing == set(), f"_SAFETY_MAP に不足: {missing}"

    def test_grandchild_safety_map_covers_all_actions(self):
        """_GRANDCHILD_SAFETY_MAP が実際の argparse 構造の全 (command, subcommand, action) をカバーしている。"""
        from gfo.commands.schema import _GRANDCHILD_SAFETY_MAP

        triples = set(_discover_grandchild_triples())
        missing = triples - set(_GRANDCHILD_SAFETY_MAP.keys())
        assert missing == set(), f"_GRANDCHILD_SAFETY_MAP に不足: {missing}"
        extra = set(_GRANDCHILD_SAFETY_MAP.keys()) - triples
        assert extra == set(), f"_GRANDCHILD_SAFETY_MAP に存在しない孫コマンド: {extra}"

    def test_yes_flag_matches_requires_confirmation_top_level(self):
        """パーサーに --yes があるコマンドは requires_confirmation: True、無いコマンドは False。

        孫グループを持つキー（例: release asset）自体には --yes は付かないため対象外。
        """
        from gfo.cli import _DISPATCH, create_parser
        from gfo.commands.schema import (
            _SAFETY_MAP,
            _get_nested_subparsers_action,
            _get_subcommand_parser,
        )

        _, subparser_map = create_parser()
        mismatches = []
        for key in _DISPATCH:
            if key == ("schema", None):
                continue
            command, subcommand = key
            if subcommand is None:
                parser = subparser_map[command]
            else:
                parser = _get_subcommand_parser(subparser_map, command, subcommand)
                if _get_nested_subparsers_action(parser) is not None:
                    continue
            has_yes = _has_yes_flag(parser)
            requires_confirmation = _SAFETY_MAP[key][1]
            if has_yes != requires_confirmation:
                mismatches.append((key, has_yes, requires_confirmation))
        assert mismatches == [], f"--yes フラグと requires_confirmation の不一致: {mismatches}"

    def test_yes_flag_matches_requires_confirmation_grandchild(self):
        """孫サブコマンドについても --yes ⇔ requires_confirmation が一致している。"""
        from gfo.cli import create_parser
        from gfo.commands.schema import (
            _GRANDCHILD_SAFETY_MAP,
            _get_grandchild_parser,
        )

        _, subparser_map = create_parser()
        mismatches = []
        for command, subcommand, action in _discover_grandchild_triples():
            parser = _get_grandchild_parser(subparser_map, command, subcommand, action)
            has_yes = _has_yes_flag(parser)
            requires_confirmation = _GRANDCHILD_SAFETY_MAP[(command, subcommand, action)][1]
            if has_yes != requires_confirmation:
                mismatches.append(((command, subcommand, action), has_yes, requires_confirmation))
        assert mismatches == [], f"--yes フラグと requires_confirmation の不一致: {mismatches}"

    def test_destructive_equals_requires_confirmation_except_api(self):
        """現状は api を除き destructive == requires_confirmation（issue #57 の判定方針）。"""
        from gfo.commands.schema import _GRANDCHILD_SAFETY_MAP, _SAFETY_MAP

        mismatches = [
            key
            for key, values in _SAFETY_MAP.items()
            if key != ("api", None) and values[0] != values[1]
        ]
        mismatches += [
            key for key, values in _GRANDCHILD_SAFETY_MAP.items() if values[0] != values[1]
        ]
        assert mismatches == [], f"destructive と requires_confirmation の不一致: {mismatches}"
