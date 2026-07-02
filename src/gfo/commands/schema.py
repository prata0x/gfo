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
    Artifact,
    Branch,
    BranchProtection,
    CheckRun,
    CodeSearchResult,
    Comment,
    Commit,
    CommitStatus,
    CompareResult,
    Contributor,
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
    Workflow,
)
from gfo.commands.batch import BatchPrResult
from gfo.exceptions import ConfigError
from gfo.i18n import _
from gfo.output import apply_jq_filter

logger = logging.getLogger(__name__)

_OUTPUT_MAP: dict[tuple[str, str | None], type | None] = {
    ("pr", "list"): list[PullRequest],
    ("pr", "create"): PullRequest,
    ("pr", "view"): PullRequest,
    ("pr", "merge"): None,
    ("pr", "close"): None,
    ("pr", "checkout"): None,
    ("pr", "edit"): PullRequest,
    ("pr", "reopen"): None,
    ("pr", "lock"): None,
    ("pr", "unlock"): None,
    ("pr", "diff"): None,
    ("pr", "checks"): list[CheckRun],
    ("pr", "files"): list[PullRequestFile],
    ("pr", "commits"): list[PullRequestCommit],
    ("pr", "reviewers"): list[str],
    ("pr", "update-branch"): None,
    ("pr", "ready"): None,
    ("pr", "status"): None,
    ("pr", "subscribe"): None,
    ("pr", "unsubscribe"): None,
    ("issue", "list"): list[Issue],
    ("issue", "create"): Issue,
    ("issue", "view"): Issue,
    ("issue", "close"): None,
    ("issue", "delete"): None,
    ("issue", "edit"): Issue,
    ("issue", "reopen"): None,
    ("issue", "lock"): None,
    ("issue", "unlock"): None,
    ("issue-template", "list"): list[IssueTemplate],
    ("repo", "list"): list[Repository],
    ("repo", "create"): Repository,
    ("repo", "clone"): None,
    ("repo", "view"): Repository,
    ("repo", "delete"): None,
    ("repo", "fork"): Repository,
    ("repo", "sync"): None,
    ("repo", "edit"): Repository,
    ("repo", "archive"): None,
    ("repo", "unarchive"): None,
    ("repo", "languages"): dict,
    ("repo", "topics"): list[str],
    ("repo", "compare"): CompareResult,
    ("repo", "contributors"): list[Contributor],
    ("repo", "migrate"): Repository,
    ("release", "list"): list[Release],
    ("release", "create"): Release,
    ("release", "delete"): None,
    ("release", "view"): Release,
    ("release", "edit"): Release,
    ("release", "asset"): list[ReleaseAsset],
    ("label", "list"): list[Label],
    ("label", "create"): Label,
    ("label", "delete"): None,
    ("label", "edit"): Label,
    ("milestone", "list"): list[Milestone],
    ("milestone", "create"): Milestone,
    ("milestone", "delete"): None,
    ("milestone", "view"): Milestone,
    ("milestone", "edit"): Milestone,
    ("milestone", "close"): None,
    ("milestone", "reopen"): None,
    ("pr", "comment"): list[Comment],
    ("issue", "comment"): list[Comment],
    ("pr", "review"): list[Review],
    ("branch", "view"): Branch,
    ("branch", "list"): list[Branch],
    ("branch", "create"): Branch,
    ("branch", "delete"): None,
    ("tag", "view"): Tag,
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
    ("webhook", "edit"): Webhook,
    ("deploy-key", "view"): DeployKey,
    ("deploy-key", "list"): list[DeployKey],
    ("deploy-key", "create"): DeployKey,
    ("deploy-key", "delete"): None,
    ("collaborator", "list"): list[str],
    ("collaborator", "add"): None,
    ("collaborator", "remove"): None,
    ("ci", "list"): list[Pipeline],
    ("ci", "view"): Pipeline,
    ("ci", "cancel"): None,
    ("ci", "delete"): None,
    ("ci", "trigger"): Pipeline,
    ("ci", "retry"): Pipeline,
    ("ci", "logs"): None,
    ("ci", "watch"): Pipeline,
    ("ci", "download"): None,
    ("ci", "workflow"): list[Workflow],
    ("ci", "artifact"): list[Artifact],
    ("user", "whoami"): dict,
    ("search", "repos"): list[Repository],
    ("search", "issues"): list[Issue],
    ("wiki", "list"): list[WikiPage],
    ("wiki", "view"): WikiPage,
    ("wiki", "create"): WikiPage,
    ("wiki", "edit"): WikiPage,
    ("wiki", "delete"): None,
    ("issue", "reaction"): list[Reaction],
    ("issue", "depends"): list[Issue],
    ("issue", "timeline"): list[TimelineEvent],
    ("issue", "subscribe"): None,
    ("issue", "unsubscribe"): None,
    ("issue", "pin"): None,
    ("issue", "unpin"): None,
    ("issue", "time"): list[TimeEntry],
    ("issue", "status"): None,
    ("issue", "develop"): Branch,
    ("search", "prs"): list[PullRequest],
    ("search", "commits"): list[Commit],
    ("search", "code"): list[CodeSearchResult],
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
    ("org", "edit"): Organization,
    ("org", "delete"): None,
    ("secret", "list"): list[Secret],
    ("secret", "set"): Secret,
    ("secret", "delete"): None,
    ("variable", "list"): list[Variable],
    ("variable", "set"): Variable,
    ("variable", "get"): Variable,
    ("variable", "delete"): None,
    ("ssh-key", "view"): SshKey,
    ("ssh-key", "list"): list[SshKey],
    ("ssh-key", "create"): SshKey,
    ("ssh-key", "delete"): None,
    ("gpg-key", "view"): GpgKey,
    ("gpg-key", "list"): list[GpgKey],
    ("gpg-key", "create"): GpgKey,
    ("gpg-key", "delete"): None,
    ("tag-protect", "list"): list[TagProtection],
    ("tag-protect", "create"): TagProtection,
    ("tag-protect", "edit"): TagProtection,
    ("tag-protect", "delete"): None,
    ("browse", None): None,
    ("api", None): dict,
    ("init", None): None,
    ("auth", "login"): None,
    ("auth", "status"): None,
    ("auth", "switch"): None,
    ("auth", "token"): None,
    ("auth", "logout"): None,
    ("completion", None): None,
    ("config", "get"): None,
    ("config", "set"): None,
    ("config", "list"): None,
    ("config", "unset"): None,
    ("config", "path"): None,
    ("issue", "migrate"): list,
    ("batch", "pr"): list,
}

# file get / user whoami の特殊出力スキーマ
_SPECIAL_OUTPUT: dict[tuple[str, str | None], dict[str, Any]] = {
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

# 孫サブコマンド（例: release asset delete）の出力スキーマ。
# キーは (command, subcommand, action)。
_GRANDCHILD_OUTPUT_MAP: dict[tuple[str, str, str], type | None] = {
    ("pr", "reviewers", "list"): list[str],
    ("pr", "reviewers", "add"): None,
    ("pr", "reviewers", "remove"): None,
    ("pr", "review", "list"): list[Review],
    ("pr", "review", "create"): Review,
    ("pr", "review", "dismiss"): None,
    ("pr", "comment", "list"): list[Comment],
    ("pr", "comment", "create"): Comment,
    ("pr", "comment", "edit"): Comment,
    ("pr", "comment", "delete"): None,
    ("issue", "comment", "list"): list[Comment],
    ("issue", "comment", "create"): Comment,
    ("issue", "comment", "edit"): Comment,
    ("issue", "comment", "delete"): None,
    ("issue", "reaction", "list"): list[Reaction],
    ("issue", "reaction", "add"): Reaction,
    ("issue", "reaction", "remove"): None,
    ("issue", "depends", "list"): list[Issue],
    ("issue", "depends", "add"): None,
    ("issue", "depends", "remove"): None,
    ("issue", "time", "list"): list[TimeEntry],
    ("issue", "time", "add"): TimeEntry,
    ("issue", "time", "delete"): None,
    ("repo", "topics", "list"): list[str],
    ("repo", "topics", "add"): list[str],
    ("repo", "topics", "remove"): list[str],
    ("repo", "topics", "set"): list[str],
    ("repo", "mirror", "list"): list[PushMirror],
    ("repo", "mirror", "add"): PushMirror,
    ("repo", "mirror", "remove"): None,
    ("repo", "mirror", "sync"): None,
    ("release", "asset", "list"): list[ReleaseAsset],
    ("release", "asset", "upload"): ReleaseAsset,
    ("release", "asset", "download"): None,
    ("release", "asset", "edit"): ReleaseAsset,
    ("release", "asset", "delete"): None,
    ("ci", "workflow", "list"): list[Workflow],
    ("ci", "workflow", "enable"): None,
    ("ci", "workflow", "disable"): None,
    ("ci", "artifact", "list"): list[Artifact],
    ("ci", "artifact", "download"): None,
    ("batch", "pr", "create"): list[BatchPrResult],
}


def _python_type_to_json_schema(tp: Any) -> dict[str, Any]:
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


def _union_to_schema(args: tuple[Any, ...]) -> dict[str, Any]:
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


def _dataclass_to_json_schema(cls: type) -> dict[str, Any]:
    """データクラスを JSON Schema に変換する。"""
    hints = get_type_hints(cls)
    fields = dataclasses.fields(cls)
    properties: dict[str, dict[str, Any]] = {}
    required: list[str] = []

    for f in fields:
        properties[f.name] = _python_type_to_json_schema(hints[f.name])
        if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING:
            required.append(f.name)

    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _parser_to_input_schema(parser: argparse.ArgumentParser) -> dict[str, Any]:
    """argparse パーサーから入力スキーマを生成する。

    NOTE: argparse の非公開 API を使用している:
      - parser._actions: 登録済みアクションリストへのアクセス
      - _HelpAction, _SubParsersAction, _StoreTrueAction, _StoreFalseAction, _AppendAction:
        アクション種別の判定に使用
    argparse の内部実装変更により動作しなくなる可能性がある。
    """
    properties: dict[str, dict[str, Any]] = {}
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
    raise ConfigError(
        _("Unknown subcommand: {command} {subcommand}").format(
            command=command, subcommand=subcommand
        )
    )


def _get_nested_subparsers_action(
    parser: argparse.ArgumentParser,
) -> argparse._SubParsersAction[argparse.ArgumentParser] | None:
    """パーサー直下の _SubParsersAction を返す（孫サブコマンドが無ければ None）。

    NOTE: argparse の非公開 API を使用: parser._actions, _SubParsersAction。
    """
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    return None


def _get_grandchild_parser(
    subparser_map: dict[str, argparse.ArgumentParser],
    command: str,
    subcommand: str,
    action: str,
) -> argparse.ArgumentParser:
    """孫サブコマンドパーサーを取得する。"""
    parser = _get_subcommand_parser(subparser_map, command, subcommand)
    sub_action = _get_nested_subparsers_action(parser)
    if sub_action is not None and action in sub_action.choices:
        result: argparse.ArgumentParser = sub_action.choices[action]
        return result
    raise ConfigError(
        _("Unknown command: {command} {subcommand} {action}").format(
            command=command, subcommand=subcommand, action=action
        )
    )


def _get_choice_description(parent_parser: argparse.ArgumentParser, choice: str) -> str:
    """親パーサー直下の _SubParsersAction から choice の help テキストを取得する。

    NOTE: action._choices_actions は argparse 非公開 API。
    """
    action = _get_nested_subparsers_action(parent_parser)
    if action is None or choice not in action.choices:
        return ""
    desc = action.choices[choice].description or ""
    if not desc:
        for ca in action._choices_actions:
            if ca.dest == choice and ca.help:
                return ca.help
    return desc


def _output_type_to_schema(output_type: Any) -> Any:
    """Python 型（dataclass / list[dataclass] 等）を出力 JSON Schema に変換する。"""
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


def _build_output_schema(key: tuple[str, str | None]) -> Any:
    """コマンドキーから出力スキーマを生成する。"""
    if key in _SPECIAL_OUTPUT:
        return _SPECIAL_OUTPUT[key]
    return _output_type_to_schema(_OUTPUT_MAP.get(key))


def _build_grandchild_output_schema(key: tuple[str, str, str]) -> Any:
    """孫サブコマンドキーから出力スキーマを生成する。"""
    return _output_type_to_schema(_GRANDCHILD_OUTPUT_MAP.get(key))


def _build_command_schema(
    key: tuple[str, str | None],
    subparser_map: dict[str, argparse.ArgumentParser],
) -> dict[str, Any]:
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


def _build_grandchild_command_schema(
    command: str,
    subcommand: str,
    action: str,
    subparser_map: dict[str, argparse.ArgumentParser],
) -> dict[str, Any]:
    """孫サブコマンド（例: release asset delete）のスキーマを構築する。"""
    parser = _get_grandchild_parser(subparser_map, command, subcommand, action)
    key = (command, subcommand, action)
    return {
        "command": f"{command} {subcommand} {action}",
        "input": _parser_to_input_schema(parser),
        "output": _build_grandchild_output_schema(key),
    }


def _print_json(json_str: str, jq: str | None) -> None:
    """JSON 文字列を出力する。jq 式があれば適用する。"""
    if jq is not None:
        print(apply_jq_filter(json_str, jq))
    else:
        print(json_str)


def handle_schema(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    import gfo.cli
    from gfo.cli import _DISPATCH, create_parser

    # schema 出力は常に英語: _() を恒等関数に差し替えて翻訳をバイパスする
    _original_gettext = gfo.cli._
    gfo.cli._ = lambda s: s  # type: ignore[assignment]
    try:
        main_parser, subparser_map = create_parser()
    finally:
        gfo.cli._ = _original_gettext

    target: list[str] = args.target
    list_commands: bool = args.list_commands

    if list_commands or not target:
        # コマンド一覧
        result: list[dict[str, Any]] = []
        for key in _DISPATCH:
            command, subcommand = key
            cmd_label = f"{command} {subcommand}" if subcommand else command
            # description はサブパーサーの help から取得
            if subcommand is not None:
                try:
                    desc = _get_choice_description(subparser_map[command], subcommand)
                except KeyError:
                    logger.warning("Failed to get parser for %s %s", command, subcommand)
                    desc = ""
            else:
                desc = _get_choice_description(main_parser, command)
            result.append({"command": cmd_label, "description": desc})

            # 孫サブコマンド（例: release asset delete）があれば併せて列挙する
            if subcommand is not None:
                try:
                    parser = _get_subcommand_parser(subparser_map, command, subcommand)
                except (ConfigError, KeyError):
                    continue
                grandchild_action = _get_nested_subparsers_action(parser)
                if grandchild_action is not None:
                    for action_name in grandchild_action.choices:
                        result.append(
                            {
                                "command": f"{cmd_label} {action_name}",
                                "description": _get_choice_description(parser, action_name),
                            }
                        )
        json_str = json.dumps(result, indent=2, ensure_ascii=False)
        _print_json(json_str, jq)
        return

    if len(target) > 3:
        raise ConfigError(_("Too many arguments: {args}").format(args=" ".join(target)))

    command = target[0]
    subcommand = target[1] if len(target) > 1 else None
    action = target[2] if len(target) > 2 else None

    if action is not None:
        # 孫サブコマンドスキーマ（例: release asset delete）
        subcommand = target[1]
        key2 = (command, subcommand)
        if key2 not in _DISPATCH:
            raise ConfigError(
                _("Unknown command: {command} {subcommand}").format(
                    command=command, subcommand=subcommand
                )
            )
        schema = _build_grandchild_command_schema(command, subcommand, action, subparser_map)
        json_str = json.dumps(schema, indent=2, ensure_ascii=False)
        _print_json(json_str, jq)
    elif subcommand is not None:
        # 単一コマンドスキーマ、または孫サブコマンドを持つグループ
        key = (command, subcommand)
        if key not in _DISPATCH:
            raise ConfigError(
                _("Unknown command: {command} {subcommand}").format(
                    command=command, subcommand=subcommand
                )
            )
        parser = _get_subcommand_parser(subparser_map, command, subcommand)
        grandchild_action = _get_nested_subparsers_action(parser)
        if grandchild_action is not None:
            # 孫グループ — action 別スキーマの一覧
            schemas = [
                _build_grandchild_command_schema(command, subcommand, act, subparser_map)
                for act in grandchild_action.choices
            ]
            json_str = json.dumps(schemas, indent=2, ensure_ascii=False)
        else:
            schema = _build_command_schema(key, subparser_map)
            json_str = json.dumps(schema, indent=2, ensure_ascii=False)
        _print_json(json_str, jq)
    else:
        # コマンドグループ — 該当 command 配下の全サブコマンド
        if command not in subparser_map:
            raise ConfigError(_("Unknown command: {command}").format(command=command))
        group_keys = [k for k in _DISPATCH if k[0] == command]
        if not group_keys:
            raise ConfigError(_("Unknown command: {command}").format(command=command))
        # サブコマンドなしのコマンド（browse 等）
        if len(group_keys) == 1 and group_keys[0][1] is None:
            schema = _build_command_schema(group_keys[0], subparser_map)
            json_str = json.dumps(schema, indent=2, ensure_ascii=False)
        else:
            schemas = [_build_command_schema(k, subparser_map) for k in group_keys]
            json_str = json.dumps(schemas, indent=2, ensure_ascii=False)
        _print_json(json_str, jq)
