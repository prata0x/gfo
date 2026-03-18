"""gfo schema コマンド — コマンドの JSON Schema を出力するメタデータコマンド。"""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import types
import typing
from typing import Any, get_type_hints

from gfo.adapter.base import (
    Branch,
    BranchProtection,
    CheckRun,
    Comment,
    Commit,
    CommitStatus,
    CompareResult,
    DeployKey,
    GpgKey,
    Issue,
    IssueTemplate,
    Label,
    Milestone,
    Notification,
    Organization,
    Package,
    Pipeline,
    PullRequest,
    PullRequestCommit,
    PullRequestFile,
    PushMirror,
    Reaction,
    Release,
    ReleaseAsset,
    Repository,
    Review,
    Secret,
    SshKey,
    Tag,
    TagProtection,
    TimeEntry,
    TimelineEvent,
    Variable,
    Webhook,
    WikiPage,
    WikiRevision,
)
from gfo.exceptions import ConfigError
from gfo.output import apply_jq_filter

logger = logging.getLogger(__name__)

_OUTPUT_MAP: dict[tuple[str, str | None], type | None] = {
    ("pr", "list"): list[PullRequest],
    ("pr", "create"): PullRequest,
    ("pr", "view"): PullRequest,
    ("pr", "merge"): None,
    ("pr", "close"): None,
    ("pr", "checkout"): None,
    ("pr", "update"): PullRequest,
    ("pr", "reopen"): None,
    ("pr", "diff"): None,
    ("pr", "checks"): list[CheckRun],
    ("pr", "files"): list[PullRequestFile],
    ("pr", "commits"): list[PullRequestCommit],
    ("pr", "reviewers"): list[str],
    ("pr", "update-branch"): None,
    ("pr", "ready"): None,
    ("issue", "list"): list[Issue],
    ("issue", "create"): Issue,
    ("issue", "view"): Issue,
    ("issue", "close"): None,
    ("issue", "delete"): None,
    ("issue", "update"): Issue,
    ("issue", "reopen"): None,
    ("issue-template", "list"): list[IssueTemplate],
    ("repo", "list"): list[Repository],
    ("repo", "create"): Repository,
    ("repo", "clone"): None,
    ("repo", "view"): Repository,
    ("repo", "delete"): None,
    ("repo", "fork"): Repository,
    ("repo", "update"): Repository,
    ("repo", "archive"): None,
    ("repo", "languages"): dict,
    ("repo", "topics"): list[str],
    ("repo", "compare"): CompareResult,
    ("repo", "migrate"): Repository,
    ("release", "list"): list[Release],
    ("release", "create"): Release,
    ("release", "delete"): None,
    ("release", "view"): Release,
    ("release", "update"): Release,
    ("release", "asset"): list[ReleaseAsset],
    ("label", "list"): list[Label],
    ("label", "create"): Label,
    ("label", "delete"): None,
    ("label", "update"): Label,
    ("milestone", "list"): list[Milestone],
    ("milestone", "create"): Milestone,
    ("milestone", "delete"): None,
    ("milestone", "view"): Milestone,
    ("milestone", "update"): Milestone,
    ("milestone", "close"): None,
    ("milestone", "reopen"): None,
    ("comment", "list"): list[Comment],
    ("comment", "create"): Comment,
    ("comment", "update"): Comment,
    ("comment", "delete"): None,
    ("review", "list"): list[Review],
    ("review", "create"): Review,
    ("review", "dismiss"): None,
    ("branch", "list"): list[Branch],
    ("branch", "create"): Branch,
    ("branch", "delete"): None,
    ("tag", "list"): list[Tag],
    ("tag", "create"): Tag,
    ("tag", "delete"): None,
    ("status", "list"): list[CommitStatus],
    ("status", "create"): CommitStatus,
    ("file", "get"): dict,
    ("file", "put"): None,
    ("file", "delete"): None,
    ("webhook", "list"): list[Webhook],
    ("webhook", "create"): Webhook,
    ("webhook", "delete"): None,
    ("webhook", "test"): None,
    ("deploy-key", "list"): list[DeployKey],
    ("deploy-key", "create"): DeployKey,
    ("deploy-key", "delete"): None,
    ("collaborator", "list"): list[str],
    ("collaborator", "add"): None,
    ("collaborator", "remove"): None,
    ("ci", "list"): list[Pipeline],
    ("ci", "view"): Pipeline,
    ("ci", "cancel"): None,
    ("ci", "trigger"): Pipeline,
    ("ci", "retry"): Pipeline,
    ("ci", "logs"): None,
    ("user", "whoami"): dict,
    ("search", "repos"): list[Repository],
    ("search", "issues"): list[Issue],
    ("wiki", "list"): list[WikiPage],
    ("wiki", "view"): WikiPage,
    ("wiki", "create"): WikiPage,
    ("wiki", "update"): WikiPage,
    ("wiki", "delete"): None,
    ("issue", "reaction"): list[Reaction],
    ("issue", "depends"): list[Issue],
    ("issue", "timeline"): list[TimelineEvent],
    ("issue", "pin"): None,
    ("issue", "unpin"): None,
    ("issue", "time"): list[TimeEntry],
    ("search", "prs"): list[PullRequest],
    ("search", "commits"): list[Commit],
    ("label", "clone"): None,
    ("wiki", "revisions"): list[WikiRevision],
    ("repo", "mirror"): list[PushMirror],
    ("repo", "transfer"): None,
    ("repo", "star"): None,
    ("repo", "unstar"): None,
    ("package", "list"): list[Package],
    ("package", "view"): Package,
    ("package", "delete"): None,
    ("branch-protect", "list"): list[BranchProtection],
    ("branch-protect", "view"): BranchProtection,
    ("branch-protect", "set"): BranchProtection,
    ("branch-protect", "remove"): None,
    ("notification", "list"): list[Notification],
    ("notification", "read"): None,
    ("org", "list"): list[Organization],
    ("org", "view"): Organization,
    ("org", "members"): list[str],
    ("org", "repos"): list[Repository],
    ("org", "create"): Organization,
    ("org", "delete"): None,
    ("secret", "list"): list[Secret],
    ("secret", "set"): Secret,
    ("secret", "delete"): None,
    ("variable", "list"): list[Variable],
    ("variable", "set"): Variable,
    ("variable", "get"): Variable,
    ("variable", "delete"): None,
    ("ssh-key", "list"): list[SshKey],
    ("ssh-key", "create"): SshKey,
    ("ssh-key", "delete"): None,
    ("gpg-key", "list"): list[GpgKey],
    ("gpg-key", "create"): GpgKey,
    ("gpg-key", "delete"): None,
    ("tag-protect", "list"): list[TagProtection],
    ("tag-protect", "create"): TagProtection,
    ("tag-protect", "delete"): None,
    ("browse", None): None,
    ("api", None): dict,
    ("init", None): None,
    ("auth", "login"): None,
    ("auth", "status"): None,
    ("issue", "migrate"): list,
    ("batch", "pr"): list,
}

# file get / user whoami の特殊出力スキーマ
_SPECIAL_OUTPUT: dict[tuple[str, str | None], dict] = {
    ("file", "get"): {
        "type": "object",
        "properties": {
            "content": {"type": "string"},
            "sha": {"type": "string"},
        },
        "required": ["content", "sha"],
    },
    ("user", "whoami"): {
        "type": "object",
        "properties": {
            "username": {"type": "string"},
            "name": {"type": "string"},
            "url": {"type": "string"},
        },
        "required": ["username"],
    },
    ("repo", "languages"): {
        "type": "object",
        "additionalProperties": {"type": "number"},
    },
    ("api", None): {
        "type": "object",
        "additionalProperties": True,
    },
}


def _python_type_to_json_schema(tp: Any) -> dict:
    """Python 型アノテーションを JSON Schema に変換する。"""
    origin = typing.get_origin(tp)

    # types.UnionType (Python 3.10+ の X | Y)
    if isinstance(tp, types.UnionType):
        union_args = typing.get_args(tp)
        return _union_to_schema(union_args)

    # typing.Union / Optional
    if origin is typing.Union:
        union_args = typing.get_args(tp)
        return _union_to_schema(union_args)

    # list[X]
    if origin is list:
        (item_type,) = typing.get_args(tp)
        return {"type": "array", "items": _python_type_to_json_schema(item_type)}

    # tuple[X, ...]
    if origin is tuple:
        args = typing.get_args(tp)
        if len(args) == 2 and args[1] is Ellipsis:
            return {"type": "array", "items": _python_type_to_json_schema(args[0])}
        return {"type": "array", "items": {"type": "string"}}

    # プリミティブ
    if tp is str:
        return {"type": "string"}
    if tp is int:
        return {"type": "integer"}
    if tp is bool:
        return {"type": "boolean"}

    logger.warning("Unknown type %r, falling back to string schema", tp)
    return {"type": "string"}


def _union_to_schema(args: tuple) -> dict:
    """Union 型引数を JSON Schema に変換する。"""
    non_none = [a for a in args if a is not type(None)]
    has_none = len(non_none) < len(args)

    if len(non_none) == 1:
        schema = _python_type_to_json_schema(non_none[0])
        if has_none:
            if "type" in schema and isinstance(schema["type"], str):
                schema = {**schema, "type": [schema["type"], "null"]}
            else:
                schema = {"oneOf": [schema, {"type": "null"}]}
        return schema

    schemas = [_python_type_to_json_schema(a) for a in non_none]
    if has_none:
        schemas.append({"type": "null"})
    return {"oneOf": schemas}


def _dataclass_to_json_schema(cls: type) -> dict:
    """データクラスを JSON Schema に変換する。"""
    hints = get_type_hints(cls)
    fields = dataclasses.fields(cls)
    properties: dict[str, dict] = {}
    required: list[str] = []

    for f in fields:
        properties[f.name] = _python_type_to_json_schema(hints[f.name])
        if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING:
            required.append(f.name)

    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _parser_to_input_schema(parser: argparse.ArgumentParser) -> dict:
    """argparse パーサーから入力スキーマを生成する。

    NOTE: argparse の非公開 API を使用している:
      - parser._actions: 登録済みアクションリストへのアクセス
      - _HelpAction, _SubParsersAction, _StoreTrueAction, _StoreFalseAction, _AppendAction:
        アクション種別の判定に使用
    argparse の内部実装変更により動作しなくなる可能性がある。
    """
    properties: dict[str, dict] = {}
    required: list[str] = []
    seen_dests: set[str] = set()

    for action in parser._actions:
        if isinstance(action, argparse._HelpAction):
            continue
        if isinstance(action, argparse._SubParsersAction):
            continue

        dest = action.dest
        if dest in seen_dests:
            continue
        seen_dests.add(dest)

        prop: dict[str, Any] = {}

        if isinstance(action, (argparse._StoreTrueAction, argparse._StoreFalseAction)):
            prop["type"] = "boolean"
        elif isinstance(action, argparse._AppendAction):
            prop["type"] = "array"
            prop["items"] = {"type": "string"}
        elif action.type is int or (
            callable(action.type)
            and action.type is not None
            and "int" in getattr(action.type, "__name__", "")
        ):
            if action.nargs in ("+", "*"):
                prop["type"] = "array"
                prop["items"] = {"type": "integer"}
            else:
                prop["type"] = "integer"
        elif action.nargs in ("+", "*"):
            prop["type"] = "array"
            prop["items"] = {"type": "string"}
        else:
            prop["type"] = "string"

        if action.choices is not None:
            prop["enum"] = list(action.choices)

        if action.default is not None and action.default is not argparse.SUPPRESS:
            prop["default"] = action.default

        if action.help and action.help is not argparse.SUPPRESS:
            prop["description"] = action.help

        # 位置引数 or required
        if not action.option_strings:
            # nargs="?" (0個or1個) や nargs="*" (0個以上) は省略可能
            if action.nargs not in ("?", "*"):
                required.append(dest)
        elif action.required:
            required.append(dest)

        properties[dest] = prop

    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _get_subcommand_parser(
    subparser_map: dict[str, argparse.ArgumentParser],
    command: str,
    subcommand: str,
) -> argparse.ArgumentParser:
    """サブコマンドパーサーを取得する。

    NOTE: argparse の非公開 API を使用:
      - cmd_parser._actions, _SubParsersAction: サブパーサーの探索に使用
    """
    cmd_parser = subparser_map[command]
    for action in cmd_parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            if subcommand in action.choices:
                parser: argparse.ArgumentParser = action.choices[subcommand]
                return parser
    raise ConfigError(f"Unknown subcommand: {command} {subcommand}")


def _build_output_schema(key: tuple[str, str | None]) -> Any:
    """コマンドキーから出力スキーマを生成する。"""
    if key in _SPECIAL_OUTPUT:
        return _SPECIAL_OUTPUT[key]

    output_type = _OUTPUT_MAP.get(key)
    if output_type is None:
        return None

    origin = typing.get_origin(output_type)
    if origin is list:
        (item_type,) = typing.get_args(output_type)
        if item_type is str:
            return {"type": "array", "items": {"type": "string"}}
        if dataclasses.is_dataclass(item_type) and isinstance(item_type, type):
            return {"type": "array", "items": _dataclass_to_json_schema(item_type)}
        return {"type": "array"}

    if dataclasses.is_dataclass(output_type) and isinstance(output_type, type):
        return _dataclass_to_json_schema(output_type)

    return None


def _build_command_schema(
    key: tuple[str, str | None],
    subparser_map: dict[str, argparse.ArgumentParser],
) -> dict:
    """単一コマンドのスキーマを構築する。"""
    command, subcommand = key

    if subcommand is not None:
        parser = _get_subcommand_parser(subparser_map, command, subcommand)
        cmd_label = f"{command} {subcommand}"
    else:
        parser = subparser_map[command]
        cmd_label = command

    result: dict[str, Any] = {
        "command": cmd_label,
        "input": _parser_to_input_schema(parser),
        "output": _build_output_schema(key),
    }
    return result


def _print_json(json_str: str, jq: str | None) -> None:
    """JSON 文字列を出力する。jq 式があれば適用する。"""
    if jq:
        print(apply_jq_filter(json_str, jq))
    else:
        print(json_str)


def handle_schema(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    from gfo.cli import _DISPATCH, create_parser

    main_parser, subparser_map = create_parser()

    target: list[str] = args.target
    list_commands: bool = args.list_commands

    if list_commands or not target:
        # コマンド一覧
        result: list[dict] = []
        for key in _DISPATCH:
            command, subcommand = key
            cmd_label = f"{command} {subcommand}" if subcommand else command
            # description はサブパーサーの help から取得
            if subcommand is not None:
                try:
                    p = _get_subcommand_parser(subparser_map, command, subcommand)
                    desc = p.description or ""
                    # p.description が空の場合、add_parser() の help= を参照する
                    # NOTE: _choices_actions は argparse 非公開 API
                    if not desc:
                        cmd_parser = subparser_map[command]
                        for act in cmd_parser._actions:
                            if isinstance(act, argparse._SubParsersAction):
                                for ca in act._choices_actions:
                                    if ca.dest == subcommand and ca.help:
                                        desc = ca.help
                                        break
                                break
                except (ConfigError, KeyError):
                    logger.warning("Failed to get parser for %s %s", command, subcommand)
                    desc = ""
            else:
                desc = subparser_map.get(command, argparse.ArgumentParser()).description or ""
                # description が空の場合、add_parser() の help= を参照する
                # NOTE: _choices_actions は argparse 非公開 API
                if not desc:
                    for act in main_parser._actions:
                        if isinstance(act, argparse._SubParsersAction):
                            for ca in act._choices_actions:
                                if ca.dest == command and ca.help:
                                    desc = ca.help
                                    break
                            break
            result.append({"command": cmd_label, "description": desc})
        json_str = json.dumps(result, indent=2, ensure_ascii=False)
        _print_json(json_str, jq)
        return

    if len(target) > 2:
        raise ConfigError(f"Too many arguments: {' '.join(target)}")

    command = target[0]
    subcommand = target[1] if len(target) > 1 else None

    if subcommand is not None:
        # 単一コマンドスキーマ
        key = (command, subcommand)
        if key not in _DISPATCH:
            raise ConfigError(f"Unknown command: {command} {subcommand}")
        schema = _build_command_schema(key, subparser_map)
        json_str = json.dumps(schema, indent=2, ensure_ascii=False)
        _print_json(json_str, jq)
    else:
        # コマンドグループ — 該当 command 配下の全サブコマンド
        if command not in subparser_map:
            raise ConfigError(f"Unknown command: {command}")
        group_keys = [k for k in _DISPATCH if k[0] == command]
        if not group_keys:
            raise ConfigError(f"Unknown command: {command}")
        # サブコマンドなしのコマンド（browse 等）
        if len(group_keys) == 1 and group_keys[0][1] is None:
            schema = _build_command_schema(group_keys[0], subparser_map)
            json_str = json.dumps(schema, indent=2, ensure_ascii=False)
        else:
            schemas = [_build_command_schema(k, subparser_map) for k in group_keys]
            json_str = json.dumps(schemas, indent=2, ensure_ascii=False)
        _print_json(json_str, jq)
