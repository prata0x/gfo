"""argparse ベースの CLI パーサーとディスパッチ層。"""

from __future__ import annotations

import argparse
import sys
from typing import Callable

import gfo.commands.auth_cmd
import gfo.commands.init
import gfo.commands.issue
import gfo.commands.label
import gfo.commands.milestone
import gfo.commands.pr
import gfo.commands.release
import gfo.commands.repo
from gfo import __version__
from gfo.config import get_default_output_format
from gfo.exceptions import GfoError, NotSupportedError


def _positive_int(value: str) -> int:
    """argparse type: 正の整数のみ受け付ける。"""
    ivalue = int(value)
    if ivalue <= 0:
        raise argparse.ArgumentTypeError(f"{value} is not a positive integer")
    return ivalue


def create_parser() -> tuple[argparse.ArgumentParser, dict[str, argparse.ArgumentParser]]:
    """メインパーサーと全サブコマンドパーサーを構築して返す。

    Returns:
        (parser, subparser_map): メインパーサーと {コマンド名: サブパーサー} の辞書。
    """

    parser = argparse.ArgumentParser(prog="gfo", description="統合 Git Forge CLI")
    parser.add_argument("--format", choices=["table", "json", "plain"], default=None)
    parser.add_argument("--version", action="version", version=f"gfo {__version__}")

    subparsers = parser.add_subparsers(dest="command")
    subparser_map: dict[str, argparse.ArgumentParser] = {}

    # gfo init
    init_parser = subparser_map["init"] = subparsers.add_parser("init")
    init_parser.add_argument("--non-interactive", action="store_true")
    init_parser.add_argument("--type")
    init_parser.add_argument("--host")
    init_parser.add_argument("--api-url")
    init_parser.add_argument("--project-key")

    # gfo auth → サブサブコマンド
    auth_parser = subparser_map["auth"] = subparsers.add_parser("auth")
    auth_sub = auth_parser.add_subparsers(dest="subcommand")
    login_parser = auth_sub.add_parser("login")
    login_parser.add_argument("--host")
    login_parser.add_argument("--token")
    auth_sub.add_parser("status")

    # gfo pr → サブサブコマンド
    pr_parser = subparser_map["pr"] = subparsers.add_parser("pr")
    pr_sub = pr_parser.add_subparsers(dest="subcommand")
    pr_list = pr_sub.add_parser("list")
    pr_list.add_argument("--state", choices=["open", "closed", "merged", "all"], default="open")
    pr_list.add_argument("--limit", type=_positive_int, default=30)
    pr_create = pr_sub.add_parser("create")
    pr_create.add_argument("--title")
    pr_create.add_argument("--body", default="")
    pr_create.add_argument("--base")
    pr_create.add_argument("--head")
    pr_create.add_argument("--draft", action="store_true")
    pr_view = pr_sub.add_parser("view")
    pr_view.add_argument("number", type=int)
    pr_merge = pr_sub.add_parser("merge")
    pr_merge.add_argument("number", type=int)
    pr_merge.add_argument("--method", choices=["merge", "squash", "rebase"], default="merge")
    pr_close = pr_sub.add_parser("close")
    pr_close.add_argument("number", type=int)
    pr_checkout = pr_sub.add_parser("checkout")
    pr_checkout.add_argument("number", type=int)

    # gfo issue → サブサブコマンド
    issue_parser = subparser_map["issue"] = subparsers.add_parser("issue")
    issue_sub = issue_parser.add_subparsers(dest="subcommand")
    issue_list = issue_sub.add_parser("list")
    issue_list.add_argument("--state", choices=["open", "closed", "all"], default="open")
    issue_list.add_argument("--assignee")
    issue_list.add_argument("--label")
    issue_list.add_argument("--limit", type=_positive_int, default=30)
    issue_create = issue_sub.add_parser("create")
    issue_create.add_argument("--title", required=True)
    issue_create.add_argument("--body", default="")
    issue_create.add_argument("--assignee")
    issue_create.add_argument("--label")
    issue_create.add_argument("--type")
    issue_create.add_argument("--priority")
    issue_view = issue_sub.add_parser("view")
    issue_view.add_argument("number", type=int)
    issue_close = issue_sub.add_parser("close")
    issue_close.add_argument("number", type=int)

    # gfo repo → サブサブコマンド
    repo_parser = subparser_map["repo"] = subparsers.add_parser("repo")
    repo_sub = repo_parser.add_subparsers(dest="subcommand")
    repo_list = repo_sub.add_parser("list")
    repo_list.add_argument("--owner")
    repo_list.add_argument("--limit", type=_positive_int, default=30)
    repo_create = repo_sub.add_parser("create")
    repo_create.add_argument("name")
    repo_create.add_argument("--private", action="store_true")
    repo_create.add_argument("--description", default="")
    repo_create.add_argument("--host")
    repo_clone = repo_sub.add_parser("clone")
    repo_clone.add_argument("repo")  # ハンドラは args.repo を参照
    repo_clone.add_argument("--host")
    repo_view = repo_sub.add_parser("view")
    repo_view.add_argument("repo", nargs="?")  # ハンドラは args.repo を参照

    # gfo release → サブサブコマンド
    release_parser = subparser_map["release"] = subparsers.add_parser("release")
    release_sub = release_parser.add_subparsers(dest="subcommand")
    release_list = release_sub.add_parser("list")
    release_list.add_argument("--limit", type=_positive_int, default=30)
    release_create = release_sub.add_parser("create")
    release_create.add_argument("tag")
    release_create.add_argument("--title", default=None)
    release_create.add_argument("--notes", default="")
    release_create.add_argument("--draft", action="store_true")
    release_create.add_argument("--prerelease", action="store_true")

    # gfo label → サブサブコマンド
    label_parser = subparser_map["label"] = subparsers.add_parser("label")
    label_sub = label_parser.add_subparsers(dest="subcommand")
    label_sub.add_parser("list")
    label_create = label_sub.add_parser("create")
    label_create.add_argument("name")
    label_create.add_argument("--color")
    label_create.add_argument("--description")

    # gfo milestone → サブサブコマンド
    milestone_parser = subparser_map["milestone"] = subparsers.add_parser("milestone")
    milestone_sub = milestone_parser.add_subparsers(dest="subcommand")
    milestone_sub.add_parser("list")
    milestone_create = milestone_sub.add_parser("create")
    milestone_create.add_argument("title")
    milestone_create.add_argument("--description")
    milestone_create.add_argument("--due")

    return parser, subparser_map


_DISPATCH: dict[tuple[str, str | None], Callable] = {
    ("init", None): gfo.commands.init.handle,
    ("auth", "login"): gfo.commands.auth_cmd.handle_login,
    ("auth", "status"): gfo.commands.auth_cmd.handle_status,
    ("pr", "list"): gfo.commands.pr.handle_list,
    ("pr", "create"): gfo.commands.pr.handle_create,
    ("pr", "view"): gfo.commands.pr.handle_view,
    ("pr", "merge"): gfo.commands.pr.handle_merge,
    ("pr", "close"): gfo.commands.pr.handle_close,
    ("pr", "checkout"): gfo.commands.pr.handle_checkout,
    ("issue", "list"): gfo.commands.issue.handle_list,
    ("issue", "create"): gfo.commands.issue.handle_create,
    ("issue", "view"): gfo.commands.issue.handle_view,
    ("issue", "close"): gfo.commands.issue.handle_close,
    ("repo", "list"): gfo.commands.repo.handle_list,
    ("repo", "create"): gfo.commands.repo.handle_create,
    ("repo", "clone"): gfo.commands.repo.handle_clone,
    ("repo", "view"): gfo.commands.repo.handle_view,
    ("release", "list"): gfo.commands.release.handle_list,
    ("release", "create"): gfo.commands.release.handle_create,
    ("label", "list"): gfo.commands.label.handle_list,
    ("label", "create"): gfo.commands.label.handle_create,
    ("milestone", "list"): gfo.commands.milestone.handle_list,
    ("milestone", "create"): gfo.commands.milestone.handle_create,
}


def main(argv: list[str] | None = None) -> int:
    """CLI エントリポイント。"""
    parser, subparser_map = create_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 1

    resolved_fmt = args.format or get_default_output_format()

    key = (args.command, getattr(args, "subcommand", None))

    if key not in _DISPATCH:
        # サブコマンド未指定の場合、該当コマンドの help を表示
        subparser_map[args.command].print_help()
        return 1

    handler = _DISPATCH[key]

    try:
        handler(args, fmt=resolved_fmt)
        return 0
    except NotSupportedError as err:
        print(str(err), file=sys.stderr)
        if err.web_url:
            print(err.web_url)
        return 1
    except GfoError as err:
        print(str(err), file=sys.stderr)
        return 1
