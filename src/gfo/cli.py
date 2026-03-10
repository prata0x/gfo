"""argparse ベースの CLI パーサーとディスパッチ層。"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable

import gfo.commands.auth_cmd
import gfo.commands.branch
import gfo.commands.ci
import gfo.commands.collaborator
import gfo.commands.comment
import gfo.commands.deploy_key
import gfo.commands.file
import gfo.commands.init
import gfo.commands.issue
import gfo.commands.label
import gfo.commands.milestone
import gfo.commands.pr
import gfo.commands.release
import gfo.commands.repo
import gfo.commands.review
import gfo.commands.search
import gfo.commands.status
import gfo.commands.tag
import gfo.commands.user
import gfo.commands.webhook
import gfo.commands.wiki
from gfo import __version__
from gfo.config import get_default_output_format
from gfo.exceptions import GfoError, NotSupportedError


def _positive_int(value: str) -> int:
    """argparse type: 正の整数のみ受け付ける。"""
    try:
        ivalue = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value} is not a positive integer")
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
    issue_create.add_argument("--priority", type=int)
    issue_view = issue_sub.add_parser("view")
    issue_view.add_argument("number", type=int)
    issue_close = issue_sub.add_parser("close")
    issue_close.add_argument("number", type=int)
    issue_delete = issue_sub.add_parser("delete")
    issue_delete.add_argument("number", type=int)

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
    repo_delete = repo_sub.add_parser("delete")
    repo_delete.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")

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
    release_delete = release_sub.add_parser("delete")
    release_delete.add_argument("tag")

    # gfo label → サブサブコマンド
    label_parser = subparser_map["label"] = subparsers.add_parser("label")
    label_sub = label_parser.add_subparsers(dest="subcommand")
    label_sub.add_parser("list")
    label_create = label_sub.add_parser("create")
    label_create.add_argument("name")
    label_create.add_argument("--color")
    label_create.add_argument("--description")
    label_delete = label_sub.add_parser("delete")
    label_delete.add_argument("name")

    # gfo milestone → サブサブコマンド
    milestone_parser = subparser_map["milestone"] = subparsers.add_parser("milestone")
    milestone_sub = milestone_parser.add_subparsers(dest="subcommand")
    milestone_sub.add_parser("list")
    milestone_create = milestone_sub.add_parser("create")
    milestone_create.add_argument("title")
    milestone_create.add_argument("--description")
    milestone_create.add_argument("--due")
    milestone_delete = milestone_sub.add_parser("delete")
    milestone_delete.add_argument("number", type=int)

    # gfo comment → サブサブコマンド
    comment_parser = subparser_map["comment"] = subparsers.add_parser("comment")
    comment_sub = comment_parser.add_subparsers(dest="subcommand")
    comment_list = comment_sub.add_parser("list")
    comment_list.add_argument("resource", choices=["pr", "issue"])
    comment_list.add_argument("number", type=int)
    comment_list.add_argument("--limit", type=_positive_int, default=30)
    comment_create = comment_sub.add_parser("create")
    comment_create.add_argument("resource", choices=["pr", "issue"])
    comment_create.add_argument("number", type=int)
    comment_create.add_argument("--body", required=True)
    comment_update = comment_sub.add_parser("update")
    comment_update.add_argument("comment_id", type=int)
    comment_update.add_argument("--body", required=True)
    comment_update.add_argument("--on", dest="on", choices=["pr", "issue"], required=True)
    comment_delete = comment_sub.add_parser("delete")
    comment_delete.add_argument("comment_id", type=int)
    comment_delete.add_argument("--on", dest="on", choices=["pr", "issue"], required=True)

    # gfo pr update（既存 pr に追加）
    pr_update = pr_sub.add_parser("update")
    pr_update.add_argument("number", type=int)
    pr_update.add_argument("--title")
    pr_update.add_argument("--body")
    pr_update.add_argument("--base")

    # gfo issue update（既存 issue に追加）
    issue_update = issue_sub.add_parser("update")
    issue_update.add_argument("number", type=int)
    issue_update.add_argument("--title")
    issue_update.add_argument("--body")
    issue_update.add_argument("--assignee")
    issue_update.add_argument("--label")

    # gfo repo fork（既存 repo に追加）
    repo_fork = repo_sub.add_parser("fork")
    repo_fork.add_argument("--org")

    # gfo review → サブサブコマンド
    review_parser = subparser_map["review"] = subparsers.add_parser("review")
    review_sub = review_parser.add_subparsers(dest="subcommand")
    review_list = review_sub.add_parser("list")
    review_list.add_argument("number", type=int)
    review_create = review_sub.add_parser("create")
    review_create.add_argument("number", type=int)
    _review_group = review_create.add_mutually_exclusive_group(required=True)
    _review_group.add_argument("--approve", action="store_true")
    _review_group.add_argument("--request-changes", dest="request_changes", action="store_true")
    _review_group.add_argument("--comment", action="store_true")
    review_create.add_argument("--body", default="")

    # gfo branch → サブサブコマンド
    branch_parser = subparser_map["branch"] = subparsers.add_parser("branch")
    branch_sub = branch_parser.add_subparsers(dest="subcommand")
    branch_list = branch_sub.add_parser("list")
    branch_list.add_argument("--limit", type=_positive_int, default=30)
    branch_create = branch_sub.add_parser("create")
    branch_create.add_argument("name")
    branch_create.add_argument("--ref", required=True)
    branch_delete = branch_sub.add_parser("delete")
    branch_delete.add_argument("name")

    # gfo tag → サブサブコマンド
    tag_parser = subparser_map["tag"] = subparsers.add_parser("tag")
    tag_sub = tag_parser.add_subparsers(dest="subcommand")
    tag_list = tag_sub.add_parser("list")
    tag_list.add_argument("--limit", type=_positive_int, default=30)
    tag_create = tag_sub.add_parser("create")
    tag_create.add_argument("name")
    tag_create.add_argument("--ref", required=True)
    tag_create.add_argument("--message", default="")
    tag_delete = tag_sub.add_parser("delete")
    tag_delete.add_argument("name")

    # gfo status → サブサブコマンド
    status_parser = subparser_map["status"] = subparsers.add_parser("status")
    status_sub = status_parser.add_subparsers(dest="subcommand")
    status_list = status_sub.add_parser("list")
    status_list.add_argument("ref")
    status_list.add_argument("--limit", type=_positive_int, default=30)
    status_create = status_sub.add_parser("create")
    status_create.add_argument("ref")
    status_create.add_argument(
        "--state", required=True, choices=["success", "failure", "pending", "error"]
    )
    status_create.add_argument("--context")
    status_create.add_argument("--description")
    status_create.add_argument("--url")

    # gfo file → サブサブコマンド
    file_parser = subparser_map["file"] = subparsers.add_parser("file")
    file_sub = file_parser.add_subparsers(dest="subcommand")
    file_get = file_sub.add_parser("get")
    file_get.add_argument("path")
    file_get.add_argument("--ref")
    file_put = file_sub.add_parser("put")
    file_put.add_argument("path")
    file_put.add_argument("--message", required=True)
    file_put.add_argument("--branch")
    file_delete = file_sub.add_parser("delete")
    file_delete.add_argument("path")
    file_delete.add_argument("--message", required=True)
    file_delete.add_argument("--branch")

    # gfo webhook → サブサブコマンド
    webhook_parser = subparser_map["webhook"] = subparsers.add_parser("webhook")
    webhook_sub = webhook_parser.add_subparsers(dest="subcommand")
    webhook_list = webhook_sub.add_parser("list")
    webhook_list.add_argument("--limit", type=_positive_int, default=30)
    webhook_create = webhook_sub.add_parser("create")
    webhook_create.add_argument("--url", required=True)
    webhook_create.add_argument("--event", action="append", required=True)
    webhook_create.add_argument("--secret")
    webhook_delete = webhook_sub.add_parser("delete")
    webhook_delete.add_argument("id", type=int)

    # gfo deploy-key → サブサブコマンド
    deploy_key_parser = subparser_map["deploy-key"] = subparsers.add_parser("deploy-key")
    deploy_key_sub = deploy_key_parser.add_subparsers(dest="subcommand")
    deploy_key_list = deploy_key_sub.add_parser("list")
    deploy_key_list.add_argument("--limit", type=_positive_int, default=30)
    deploy_key_create = deploy_key_sub.add_parser("create")
    deploy_key_create.add_argument("--title", required=True)
    deploy_key_create.add_argument("--key", required=True)
    deploy_key_create.add_argument("--read-write", dest="read_write", action="store_true")
    deploy_key_delete = deploy_key_sub.add_parser("delete")
    deploy_key_delete.add_argument("id", type=int)

    # gfo collaborator → サブサブコマンド
    collab_parser = subparser_map["collaborator"] = subparsers.add_parser("collaborator")
    collab_sub = collab_parser.add_subparsers(dest="subcommand")
    collab_list = collab_sub.add_parser("list")
    collab_list.add_argument("--limit", type=_positive_int, default=30)
    collab_add = collab_sub.add_parser("add")
    collab_add.add_argument("username")
    collab_add.add_argument("--permission", choices=["read", "write", "admin"], default="write")
    collab_remove = collab_sub.add_parser("remove")
    collab_remove.add_argument("username")

    # gfo ci → サブサブコマンド
    ci_parser = subparser_map["ci"] = subparsers.add_parser("ci")
    ci_sub = ci_parser.add_subparsers(dest="subcommand")
    ci_list = ci_sub.add_parser("list")
    ci_list.add_argument("--ref")
    ci_list.add_argument("--limit", type=_positive_int, default=30)
    ci_view = ci_sub.add_parser("view")
    ci_view.add_argument("id")
    ci_cancel = ci_sub.add_parser("cancel")
    ci_cancel.add_argument("id")

    # gfo user → サブサブコマンド
    user_parser = subparser_map["user"] = subparsers.add_parser("user")
    user_sub = user_parser.add_subparsers(dest="subcommand")
    user_sub.add_parser("whoami")

    # gfo search → サブサブコマンド
    search_parser = subparser_map["search"] = subparsers.add_parser("search")
    search_sub = search_parser.add_subparsers(dest="subcommand")
    search_repos = search_sub.add_parser("repos")
    search_repos.add_argument("query")
    search_repos.add_argument("--limit", type=_positive_int, default=30)
    search_issues = search_sub.add_parser("issues")
    search_issues.add_argument("query")
    search_issues.add_argument("--limit", type=_positive_int, default=30)

    # gfo wiki → サブサブコマンド
    wiki_parser = subparser_map["wiki"] = subparsers.add_parser("wiki")
    wiki_sub = wiki_parser.add_subparsers(dest="subcommand")
    wiki_list = wiki_sub.add_parser("list")
    wiki_list.add_argument("--limit", type=_positive_int, default=30)
    wiki_view = wiki_sub.add_parser("view")
    wiki_view.add_argument("id")
    wiki_create = wiki_sub.add_parser("create")
    wiki_create.add_argument("--title", required=True)
    wiki_create.add_argument("--content", required=True)
    wiki_update = wiki_sub.add_parser("update")
    wiki_update.add_argument("id")
    wiki_update.add_argument("--title")
    wiki_update.add_argument("--content")
    wiki_delete = wiki_sub.add_parser("delete")
    wiki_delete.add_argument("id")

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
    ("pr", "update"): gfo.commands.pr.handle_update,
    ("issue", "list"): gfo.commands.issue.handle_list,
    ("issue", "create"): gfo.commands.issue.handle_create,
    ("issue", "view"): gfo.commands.issue.handle_view,
    ("issue", "close"): gfo.commands.issue.handle_close,
    ("issue", "delete"): gfo.commands.issue.handle_delete,
    ("issue", "update"): gfo.commands.issue.handle_update,
    ("repo", "list"): gfo.commands.repo.handle_list,
    ("repo", "create"): gfo.commands.repo.handle_create,
    ("repo", "clone"): gfo.commands.repo.handle_clone,
    ("repo", "view"): gfo.commands.repo.handle_view,
    ("repo", "delete"): gfo.commands.repo.handle_delete,
    ("repo", "fork"): gfo.commands.repo.handle_fork,
    ("release", "list"): gfo.commands.release.handle_list,
    ("release", "create"): gfo.commands.release.handle_create,
    ("release", "delete"): gfo.commands.release.handle_delete,
    ("label", "list"): gfo.commands.label.handle_list,
    ("label", "create"): gfo.commands.label.handle_create,
    ("label", "delete"): gfo.commands.label.handle_delete,
    ("milestone", "list"): gfo.commands.milestone.handle_list,
    ("milestone", "create"): gfo.commands.milestone.handle_create,
    ("milestone", "delete"): gfo.commands.milestone.handle_delete,
    ("comment", "list"): gfo.commands.comment.handle_list,
    ("comment", "create"): gfo.commands.comment.handle_create,
    ("comment", "update"): gfo.commands.comment.handle_update,
    ("comment", "delete"): gfo.commands.comment.handle_delete,
    ("review", "list"): gfo.commands.review.handle_list,
    ("review", "create"): gfo.commands.review.handle_create,
    ("branch", "list"): gfo.commands.branch.handle_list,
    ("branch", "create"): gfo.commands.branch.handle_create,
    ("branch", "delete"): gfo.commands.branch.handle_delete,
    ("tag", "list"): gfo.commands.tag.handle_list,
    ("tag", "create"): gfo.commands.tag.handle_create,
    ("tag", "delete"): gfo.commands.tag.handle_delete,
    ("status", "list"): gfo.commands.status.handle_list,
    ("status", "create"): gfo.commands.status.handle_create,
    ("file", "get"): gfo.commands.file.handle_get,
    ("file", "put"): gfo.commands.file.handle_put,
    ("file", "delete"): gfo.commands.file.handle_delete,
    ("webhook", "list"): gfo.commands.webhook.handle_list,
    ("webhook", "create"): gfo.commands.webhook.handle_create,
    ("webhook", "delete"): gfo.commands.webhook.handle_delete,
    ("deploy-key", "list"): gfo.commands.deploy_key.handle_list,
    ("deploy-key", "create"): gfo.commands.deploy_key.handle_create,
    ("deploy-key", "delete"): gfo.commands.deploy_key.handle_delete,
    ("collaborator", "list"): gfo.commands.collaborator.handle_list,
    ("collaborator", "add"): gfo.commands.collaborator.handle_add,
    ("collaborator", "remove"): gfo.commands.collaborator.handle_remove,
    ("ci", "list"): gfo.commands.ci.handle_list,
    ("ci", "view"): gfo.commands.ci.handle_view,
    ("ci", "cancel"): gfo.commands.ci.handle_cancel,
    ("user", "whoami"): gfo.commands.user.handle_whoami,
    ("search", "repos"): gfo.commands.search.handle_repos,
    ("search", "issues"): gfo.commands.search.handle_issues,
    ("wiki", "list"): gfo.commands.wiki.handle_list,
    ("wiki", "view"): gfo.commands.wiki.handle_view,
    ("wiki", "create"): gfo.commands.wiki.handle_create,
    ("wiki", "update"): gfo.commands.wiki.handle_update,
    ("wiki", "delete"): gfo.commands.wiki.handle_delete,
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
    except Exception as err:  # pragma: no cover
        print(f"Unexpected error: {err}", file=sys.stderr)
        return 1
