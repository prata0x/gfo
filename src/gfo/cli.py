"""argparse ベースの CLI パーサーとディスパッチ層。"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable
from typing import NoReturn

import gfo.commands.api
import gfo.commands.auth_cmd
import gfo.commands.branch
import gfo.commands.branch_protect
import gfo.commands.browse
import gfo.commands.ci
import gfo.commands.collaborator
import gfo.commands.comment
import gfo.commands.deploy_key
import gfo.commands.file
import gfo.commands.gpg_key
import gfo.commands.init
import gfo.commands.issue
import gfo.commands.issue_template
import gfo.commands.label
import gfo.commands.milestone
import gfo.commands.notification
import gfo.commands.org
import gfo.commands.package
import gfo.commands.pr
import gfo.commands.release
import gfo.commands.repo
import gfo.commands.review
import gfo.commands.schema
import gfo.commands.search
import gfo.commands.secret
import gfo.commands.ssh_key
import gfo.commands.status
import gfo.commands.tag
import gfo.commands.tag_protect
import gfo.commands.user
import gfo.commands.variable
import gfo.commands.webhook
import gfo.commands.wiki
from gfo import __version__
from gfo.config import get_configured_output_format
from gfo.exceptions import ConfigError, GfoError, NotSupportedError
from gfo.i18n import _
from gfo.output import format_error_json


def _positive_int(value: str) -> int:
    """argparse type: 正の整数のみ受け付ける。"""
    try:
        ivalue = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(_("{value} is not a positive integer").format(value=value))
    if ivalue <= 0:
        raise argparse.ArgumentTypeError(_("{value} is not a positive integer").format(value=value))
    return ivalue


class _GfoArgumentParser(argparse.ArgumentParser):
    """argparse のエラーを ConfigError に変換するサブクラス。"""

    def error(self, message: str) -> NoReturn:
        raise ConfigError(message)


def create_parser() -> tuple[argparse.ArgumentParser, dict[str, argparse.ArgumentParser]]:
    """メインパーサーと全サブコマンドパーサーを構築して返す。

    Returns:
        (parser, subparser_map): メインパーサーと {コマンド名: サブパーサー} の辞書。
    """

    parser = _GfoArgumentParser(prog="gfo", description=_("Git Forge Operator"))
    parser.add_argument("--format", choices=["table", "json", "plain"], default=None)
    parser.add_argument(
        "--jq",
        metavar="EXPRESSION",
        default=None,
        help=_("Apply jq expression to JSON output (implicitly enables --format json)"),
    )
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
    pr_merge.add_argument("--auto", action="store_true")
    pr_close = pr_sub.add_parser("close")
    pr_close.add_argument("number", type=int)
    pr_checkout = pr_sub.add_parser("checkout")
    pr_checkout.add_argument("number", type=int)
    pr_reopen = pr_sub.add_parser("reopen")
    pr_reopen.add_argument("number", type=int)
    pr_diff = pr_sub.add_parser("diff")
    pr_diff.add_argument("number", type=int)
    pr_checks = pr_sub.add_parser("checks")
    pr_checks.add_argument("number", type=int)
    pr_files = pr_sub.add_parser("files")
    pr_files.add_argument("number", type=int)
    pr_commits = pr_sub.add_parser("commits")
    pr_commits.add_argument("number", type=int)
    pr_reviewers = pr_sub.add_parser("reviewers")
    pr_reviewers_sub = pr_reviewers.add_subparsers(dest="reviewer_action")
    pr_reviewers_list = pr_reviewers_sub.add_parser("list")
    pr_reviewers_list.add_argument("number", type=int)
    pr_reviewers_add = pr_reviewers_sub.add_parser("add")
    pr_reviewers_add.add_argument("number", type=int)
    pr_reviewers_add.add_argument("users", nargs="+")
    pr_reviewers_remove = pr_reviewers_sub.add_parser("remove")
    pr_reviewers_remove.add_argument("number", type=int)
    pr_reviewers_remove.add_argument("users", nargs="+")
    pr_update_branch = pr_sub.add_parser("update-branch")
    pr_update_branch.add_argument("number", type=int)
    pr_ready = pr_sub.add_parser("ready")
    pr_ready.add_argument("number", type=int)

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
    issue_reopen = issue_sub.add_parser("reopen")
    issue_reopen.add_argument("number", type=int)

    # gfo issue-template → サブサブコマンド
    it_parser = subparser_map["issue-template"] = subparsers.add_parser(
        "issue-template", help=_("Manage issue templates")
    )
    it_sub = it_parser.add_subparsers(dest="subcommand")
    it_sub.add_parser("list")

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
    repo_clone.add_argument("--project")  # Azure DevOps 用プロジェクト名
    repo_view = repo_sub.add_parser("view")
    repo_view.add_argument("repo", nargs="?")  # ハンドラは args.repo を参照
    repo_delete = repo_sub.add_parser("delete")
    repo_delete.add_argument("--yes", "-y", action="store_true", help=_("Skip confirmation prompt"))

    # gfo repo update
    repo_update = repo_sub.add_parser("update")
    repo_update.add_argument("--description")
    _repo_private_group = repo_update.add_mutually_exclusive_group()
    _repo_private_group.add_argument("--private", dest="private", action="store_true", default=None)
    _repo_private_group.add_argument("--public", dest="private", action="store_false")
    repo_update.add_argument("--default-branch", dest="default_branch")

    # gfo repo archive
    repo_archive = repo_sub.add_parser("archive")
    repo_archive.add_argument(
        "--yes", "-y", action="store_true", help=_("Skip confirmation prompt")
    )

    # gfo repo languages
    repo_sub.add_parser("languages")

    # gfo repo topics → サブサブコマンド
    repo_topics = repo_sub.add_parser("topics")
    repo_topics_sub = repo_topics.add_subparsers(dest="topics_action")
    repo_topics_sub.add_parser("list")
    repo_topics_add = repo_topics_sub.add_parser("add")
    repo_topics_add.add_argument("topic")
    repo_topics_remove = repo_topics_sub.add_parser("remove")
    repo_topics_remove.add_argument("topic")
    repo_topics_set = repo_topics_sub.add_parser("set")
    repo_topics_set.add_argument("topics", nargs="+")

    # gfo repo compare
    repo_compare = repo_sub.add_parser("compare")
    repo_compare.add_argument("spec")

    # gfo repo migrate
    repo_migrate = repo_sub.add_parser("migrate")
    repo_migrate.add_argument("clone_url")
    repo_migrate.add_argument("--name", required=True)
    repo_migrate.add_argument("--private", action="store_true")
    repo_migrate.add_argument("--description", default="")
    repo_migrate.add_argument("--mirror", action="store_true")
    repo_migrate.add_argument("--auth-token", dest="auth_token")

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
    release_view = release_sub.add_parser("view")
    release_view.add_argument("tag", nargs="?")
    release_view.add_argument("--latest", action="store_true")
    release_update = release_sub.add_parser("update")
    release_update.add_argument("tag")
    release_update.add_argument("--title")
    release_update.add_argument("--notes")
    release_update.add_argument("--draft", action="store_true", default=None)
    release_update.add_argument("--no-draft", dest="draft", action="store_false")
    release_update.add_argument("--prerelease", action="store_true", default=None)
    release_update.add_argument("--no-prerelease", dest="prerelease", action="store_false")

    # gfo release asset → サブサブコマンド
    release_asset = release_sub.add_parser("asset")
    release_asset_sub = release_asset.add_subparsers(dest="asset_action")
    asset_list = release_asset_sub.add_parser("list")
    asset_list.add_argument("--tag", required=True)
    asset_upload = release_asset_sub.add_parser("upload")
    asset_upload.add_argument("--tag", required=True)
    asset_upload.add_argument("file")
    asset_upload.add_argument("--name")
    asset_download = release_asset_sub.add_parser("download")
    asset_download.add_argument("--tag", required=True)
    asset_download.add_argument("--pattern")
    asset_download.add_argument("--dir", default=".")
    asset_download.add_argument("--asset-id", dest="asset_id")
    asset_delete = release_asset_sub.add_parser("delete")
    asset_delete.add_argument("--tag", required=True)
    asset_delete.add_argument("asset_id")

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
    label_update = label_sub.add_parser("update")
    label_update.add_argument("name")
    label_update.add_argument("--new-name", dest="new_name")
    label_update.add_argument("--color")
    label_update.add_argument("--description")

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
    milestone_view = milestone_sub.add_parser("view")
    milestone_view.add_argument("number", type=int)
    milestone_update = milestone_sub.add_parser("update")
    milestone_update.add_argument("number", type=int)
    milestone_update.add_argument("--title")
    milestone_update.add_argument("--description")
    milestone_update.add_argument("--due")
    milestone_update.add_argument("--state", choices=["open", "closed"])
    milestone_close = milestone_sub.add_parser("close")
    milestone_close.add_argument("number", type=int)
    milestone_reopen = milestone_sub.add_parser("reopen")
    milestone_reopen.add_argument("number", type=int)

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
    review_dismiss = review_sub.add_parser("dismiss")
    review_dismiss.add_argument("number", type=int)
    review_dismiss.add_argument("review_id", type=int)
    review_dismiss.add_argument("--message", default="")

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
    webhook_test = webhook_sub.add_parser("test")
    webhook_test.add_argument("id", type=int)

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
    ci_trigger = ci_sub.add_parser("trigger")
    ci_trigger.add_argument("--ref", required=True)
    ci_trigger.add_argument("--workflow", "-w")
    ci_trigger.add_argument("--input", "-i", action="append")
    ci_retry = ci_sub.add_parser("retry")
    ci_retry.add_argument("id")
    ci_logs = ci_sub.add_parser("logs")
    ci_logs.add_argument("id")
    ci_logs.add_argument("--job", "-j")

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

    # -- New Phase 5 parsers --

    # gfo issue reaction → サブサブコマンド
    issue_reaction = issue_sub.add_parser("reaction")
    issue_reaction_sub = issue_reaction.add_subparsers(dest="reaction_action")
    issue_reaction_list = issue_reaction_sub.add_parser("list")
    issue_reaction_list.add_argument("number", type=int)
    issue_reaction_add = issue_reaction_sub.add_parser("add")
    issue_reaction_add.add_argument("number", type=int)
    issue_reaction_add.add_argument("reaction")
    issue_reaction_remove = issue_reaction_sub.add_parser("remove")
    issue_reaction_remove.add_argument("number", type=int)
    issue_reaction_remove.add_argument("reaction")

    # gfo issue depends → サブサブコマンド
    issue_depends = issue_sub.add_parser("depends")
    issue_depends_sub = issue_depends.add_subparsers(dest="depends_action")
    issue_depends_list = issue_depends_sub.add_parser("list")
    issue_depends_list.add_argument("number", type=int)
    issue_depends_add = issue_depends_sub.add_parser("add")
    issue_depends_add.add_argument("number", type=int)
    issue_depends_add.add_argument("depends_on", type=int)
    issue_depends_remove = issue_depends_sub.add_parser("remove")
    issue_depends_remove.add_argument("number", type=int)
    issue_depends_remove.add_argument("depends_on", type=int)

    # gfo issue timeline
    issue_timeline = issue_sub.add_parser("timeline")
    issue_timeline.add_argument("number", type=int)
    issue_timeline.add_argument("--limit", type=_positive_int, default=30)

    # gfo issue pin / unpin
    issue_pin = issue_sub.add_parser("pin")
    issue_pin.add_argument("number", type=int)
    issue_unpin = issue_sub.add_parser("unpin")
    issue_unpin.add_argument("number", type=int)

    # gfo issue time → サブサブコマンド
    issue_time = issue_sub.add_parser("time")
    issue_time_sub = issue_time.add_subparsers(dest="time_action")
    issue_time_list = issue_time_sub.add_parser("list")
    issue_time_list.add_argument("number", type=int)
    issue_time_add = issue_time_sub.add_parser("add")
    issue_time_add.add_argument("number", type=int)
    issue_time_add.add_argument("duration")
    issue_time_delete = issue_time_sub.add_parser("delete")
    issue_time_delete.add_argument("number", type=int)
    issue_time_delete.add_argument("entry_id")

    # gfo search prs
    search_prs = search_sub.add_parser("prs")
    search_prs.add_argument("query")
    search_prs.add_argument("--state", choices=["open", "closed", "merged", "all"])
    search_prs.add_argument("--limit", type=_positive_int, default=30)

    # gfo search commits
    search_commits = search_sub.add_parser("commits")
    search_commits.add_argument("query")
    search_commits.add_argument("--author")
    search_commits.add_argument("--since")
    search_commits.add_argument("--until")
    search_commits.add_argument("--limit", type=_positive_int, default=30)

    # gfo label clone
    label_clone = label_sub.add_parser("clone")
    label_clone.add_argument("--from", dest="source", required=True)
    label_clone.add_argument("--overwrite", action="store_true")

    # gfo wiki revisions
    wiki_revisions = wiki_sub.add_parser("revisions")
    wiki_revisions.add_argument("page_name")

    # gfo repo mirror → サブサブコマンド
    repo_mirror = repo_sub.add_parser("mirror")
    repo_mirror_sub = repo_mirror.add_subparsers(dest="mirror_action")
    repo_mirror_sub.add_parser("list")
    repo_mirror_add = repo_mirror_sub.add_parser("add")
    repo_mirror_add.add_argument("remote_address")
    repo_mirror_add.add_argument("--interval", default="8h")
    repo_mirror_add.add_argument("--auth-token", dest="auth_token")
    repo_mirror_remove = repo_mirror_sub.add_parser("remove")
    repo_mirror_remove.add_argument("mirror_name")
    repo_mirror_sub.add_parser("sync")

    # gfo repo transfer
    repo_transfer = repo_sub.add_parser("transfer")
    repo_transfer.add_argument("new_owner")
    repo_transfer.add_argument("--team-id", dest="team_id", type=int)
    repo_transfer.add_argument("--yes", "-y", action="store_true")

    # gfo repo star / unstar
    repo_sub.add_parser("star")
    repo_sub.add_parser("unstar")

    # gfo package → サブサブコマンド
    package_parser = subparser_map["package"] = subparsers.add_parser("package")
    package_sub = package_parser.add_subparsers(dest="subcommand")
    package_list = package_sub.add_parser("list")
    package_list.add_argument("--type", dest="type")
    package_list.add_argument("--limit", type=_positive_int, default=30)
    package_view = package_sub.add_parser("view")
    package_view.add_argument("package_type")
    package_view.add_argument("name")
    package_view.add_argument("--version")
    package_delete = package_sub.add_parser("delete")
    package_delete.add_argument("package_type")
    package_delete.add_argument("name")
    package_delete.add_argument("version")
    package_delete.add_argument("--yes", "-y", action="store_true")

    # gfo branch-protect → サブサブコマンド
    bp_parser = subparser_map["branch-protect"] = subparsers.add_parser(
        "branch-protect", help=_("Manage branch protection rules")
    )
    bp_sub = bp_parser.add_subparsers(dest="subcommand")
    bp_list = bp_sub.add_parser("list")
    bp_list.add_argument("--limit", type=_positive_int, default=30)
    bp_view = bp_sub.add_parser("view")
    bp_view.add_argument("branch")
    bp_set = bp_sub.add_parser("set")
    bp_set.add_argument("branch")
    bp_set.add_argument("--require-reviews", type=int, dest="require_reviews")
    bp_set.add_argument("--require-status-checks", nargs="+", dest="require_status_checks")
    bp_set.add_argument("--enforce-admins", action="store_true", default=None)
    bp_set.add_argument("--no-enforce-admins", dest="enforce_admins", action="store_false")
    bp_set.add_argument("--allow-force-push", action="store_true", default=None)
    bp_set.add_argument("--no-allow-force-push", dest="allow_force_push", action="store_false")
    bp_set.add_argument("--allow-deletions", action="store_true", default=None)
    bp_set.add_argument("--no-allow-deletions", dest="allow_deletions", action="store_false")
    bp_remove = bp_sub.add_parser("remove")
    bp_remove.add_argument("branch")

    # gfo tag-protect → サブサブコマンド
    tp_parser = subparser_map["tag-protect"] = subparsers.add_parser(
        "tag-protect", help=_("Manage tag protection rules")
    )
    tp_sub = tp_parser.add_subparsers(dest="subcommand")
    tp_list = tp_sub.add_parser("list")
    tp_list.add_argument("--limit", type=_positive_int, default=30)
    tp_create = tp_sub.add_parser("create")
    tp_create.add_argument("pattern")
    tp_create.add_argument("--access-level", dest="access_level")
    tp_delete = tp_sub.add_parser("delete")
    tp_delete.add_argument("id")

    # gfo notification → サブサブコマンド
    notif_parser = subparser_map["notification"] = subparsers.add_parser(
        "notification", help=_("Manage notifications")
    )
    notif_sub = notif_parser.add_subparsers(dest="subcommand")
    notif_list = notif_sub.add_parser("list", help=_("List notifications"))
    notif_list.add_argument("--unread-only", action="store_true")
    notif_list.add_argument("--limit", type=_positive_int, default=30)
    notif_read = notif_sub.add_parser("read", help=_("Mark notifications as read"))
    notif_read.add_argument("id", nargs="?", metavar="ID", help=_("Notification ID"))
    notif_read.add_argument(
        "--all", dest="mark_all", action="store_true", help=_("Mark all notifications as read")
    )

    # gfo org → サブサブコマンド
    org_parser = subparser_map["org"] = subparsers.add_parser("org", help=_("Manage organizations"))
    org_sub = org_parser.add_subparsers(dest="subcommand")
    org_list = org_sub.add_parser("list", help=_("List organizations"))
    org_list.add_argument("--limit", type=_positive_int, default=30)
    org_view = org_sub.add_parser("view", help=_("View organization details"))
    org_view.add_argument("name", help=_("Organization name"))
    org_members = org_sub.add_parser("members", help=_("List members"))
    org_members.add_argument("name", help=_("Organization name"))
    org_members.add_argument("--limit", type=_positive_int, default=30)
    org_repos = org_sub.add_parser("repos", help=_("List repositories"))
    org_repos.add_argument("name", help=_("Organization name"))
    org_repos.add_argument("--limit", type=_positive_int, default=30)
    org_create = org_sub.add_parser("create", help=_("Create organization"))
    org_create.add_argument("name", help=_("Organization name"))
    org_create.add_argument("--display-name", dest="display_name")
    org_create.add_argument("--description")
    org_delete = org_sub.add_parser("delete", help=_("Delete organization"))
    org_delete.add_argument("name", help=_("Organization name"))
    org_delete.add_argument("--yes", "-y", action="store_true", help=_("Skip confirmation prompt"))

    # gfo ssh-key → サブサブコマンド
    ssh_key_parser = subparser_map["ssh-key"] = subparsers.add_parser(
        "ssh-key", help=_("Manage SSH keys")
    )
    ssh_key_sub = ssh_key_parser.add_subparsers(dest="subcommand")
    ssh_key_list = ssh_key_sub.add_parser("list")
    ssh_key_list.add_argument("--limit", type=_positive_int, default=30)
    ssh_key_create = ssh_key_sub.add_parser("create")
    ssh_key_create.add_argument("--title", required=True)
    ssh_key_create.add_argument("--key", required=True)
    ssh_key_delete = ssh_key_sub.add_parser("delete")
    ssh_key_delete.add_argument("id")

    # gfo gpg-key → サブサブコマンド
    gpg_key_parser = subparser_map["gpg-key"] = subparsers.add_parser(
        "gpg-key", help=_("Manage GPG keys")
    )
    gpg_key_sub = gpg_key_parser.add_subparsers(dest="subcommand")
    gpg_key_list = gpg_key_sub.add_parser("list")
    gpg_key_list.add_argument("--limit", type=_positive_int, default=30)
    gpg_key_create = gpg_key_sub.add_parser("create")
    gpg_key_create.add_argument("--key", required=True)
    gpg_key_delete = gpg_key_sub.add_parser("delete")
    gpg_key_delete.add_argument("id")

    # gfo secret → サブサブコマンド
    secret_parser = subparser_map["secret"] = subparsers.add_parser(
        "secret", help=_("Manage secrets")
    )
    secret_sub = secret_parser.add_subparsers(dest="subcommand")
    secret_list = secret_sub.add_parser("list")
    secret_list.add_argument("--limit", type=_positive_int, default=30)
    secret_set = secret_sub.add_parser("set")
    secret_set.add_argument("name")
    _secret_value_group = secret_set.add_mutually_exclusive_group(required=True)
    _secret_value_group.add_argument("--value")
    _secret_value_group.add_argument("--env-var", dest="env_var")
    _secret_value_group.add_argument("--file")
    secret_delete = secret_sub.add_parser("delete")
    secret_delete.add_argument("name")

    # gfo variable → サブサブコマンド
    variable_parser = subparser_map["variable"] = subparsers.add_parser(
        "variable", help=_("Manage variables")
    )
    variable_sub = variable_parser.add_subparsers(dest="subcommand")
    variable_list = variable_sub.add_parser("list")
    variable_list.add_argument("--limit", type=_positive_int, default=30)
    variable_set = variable_sub.add_parser("set")
    variable_set.add_argument("name")
    variable_set.add_argument("--value", required=True)
    variable_set.add_argument("--masked", action="store_true")
    variable_get = variable_sub.add_parser("get")
    variable_get.add_argument("name")
    variable_delete = variable_sub.add_parser("delete")
    variable_delete.add_argument("name")

    # gfo browse（サブコマンドなし）
    browse_parser = subparser_map["browse"] = subparsers.add_parser(
        "browse", help=_("Open repository in browser")
    )
    _browse_group = browse_parser.add_mutually_exclusive_group()
    _browse_group.add_argument("--pr", type=int, metavar="N", help=_("PR number"))
    _browse_group.add_argument("--issue", type=int, metavar="N", help=_("Issue number"))
    _browse_group.add_argument("--settings", action="store_true", help=_("Open settings page"))
    browse_parser.add_argument("--print", action="store_true", help=_("Print URL only"))

    # gfo api（サブコマンドなし）
    api_parser = subparser_map["api"] = subparsers.add_parser("api", help=_("Send raw API request"))
    api_parser.add_argument(
        "method",
        choices=["GET", "POST", "PUT", "PATCH", "DELETE", "get", "post", "put", "patch", "delete"],
    )
    api_parser.add_argument("path")
    api_parser.add_argument("--data", "-d")
    api_parser.add_argument("--header", "-H", action="append")

    # gfo schema（サブコマンドなし、browse と同じパターン）
    schema_parser = subparser_map["schema"] = subparsers.add_parser(
        "schema", help=_("Show command JSON Schema")
    )
    schema_parser.add_argument("--list", dest="list_commands", action="store_true")
    schema_parser.add_argument("target", nargs="*", default=[])

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
    ("pr", "reopen"): gfo.commands.pr.handle_reopen,
    ("pr", "diff"): gfo.commands.pr.handle_diff,
    ("pr", "checks"): gfo.commands.pr.handle_checks,
    ("pr", "files"): gfo.commands.pr.handle_files,
    ("pr", "commits"): gfo.commands.pr.handle_commits,
    ("pr", "reviewers"): gfo.commands.pr.handle_reviewers,
    ("pr", "update-branch"): gfo.commands.pr.handle_update_branch,
    ("pr", "ready"): gfo.commands.pr.handle_ready,
    ("issue", "list"): gfo.commands.issue.handle_list,
    ("issue", "create"): gfo.commands.issue.handle_create,
    ("issue", "view"): gfo.commands.issue.handle_view,
    ("issue", "close"): gfo.commands.issue.handle_close,
    ("issue", "delete"): gfo.commands.issue.handle_delete,
    ("issue", "update"): gfo.commands.issue.handle_update,
    ("issue", "reopen"): gfo.commands.issue.handle_reopen,
    ("issue-template", "list"): gfo.commands.issue_template.handle_list,
    ("repo", "list"): gfo.commands.repo.handle_list,
    ("repo", "create"): gfo.commands.repo.handle_create,
    ("repo", "clone"): gfo.commands.repo.handle_clone,
    ("repo", "view"): gfo.commands.repo.handle_view,
    ("repo", "delete"): gfo.commands.repo.handle_delete,
    ("repo", "fork"): gfo.commands.repo.handle_fork,
    ("repo", "update"): gfo.commands.repo.handle_update,
    ("repo", "archive"): gfo.commands.repo.handle_archive,
    ("repo", "languages"): gfo.commands.repo.handle_languages,
    ("repo", "topics"): gfo.commands.repo.handle_topics,
    ("repo", "compare"): gfo.commands.repo.handle_compare,
    ("repo", "migrate"): gfo.commands.repo.handle_migrate,
    ("release", "list"): gfo.commands.release.handle_list,
    ("release", "create"): gfo.commands.release.handle_create,
    ("release", "delete"): gfo.commands.release.handle_delete,
    ("release", "view"): gfo.commands.release.handle_view,
    ("release", "update"): gfo.commands.release.handle_update,
    ("release", "asset"): gfo.commands.release.handle_asset,
    ("label", "list"): gfo.commands.label.handle_list,
    ("label", "create"): gfo.commands.label.handle_create,
    ("label", "delete"): gfo.commands.label.handle_delete,
    ("label", "update"): gfo.commands.label.handle_update,
    ("milestone", "list"): gfo.commands.milestone.handle_list,
    ("milestone", "create"): gfo.commands.milestone.handle_create,
    ("milestone", "delete"): gfo.commands.milestone.handle_delete,
    ("milestone", "view"): gfo.commands.milestone.handle_view,
    ("milestone", "update"): gfo.commands.milestone.handle_update,
    ("milestone", "close"): gfo.commands.milestone.handle_close,
    ("milestone", "reopen"): gfo.commands.milestone.handle_reopen,
    ("comment", "list"): gfo.commands.comment.handle_list,
    ("comment", "create"): gfo.commands.comment.handle_create,
    ("comment", "update"): gfo.commands.comment.handle_update,
    ("comment", "delete"): gfo.commands.comment.handle_delete,
    ("review", "list"): gfo.commands.review.handle_list,
    ("review", "create"): gfo.commands.review.handle_create,
    ("review", "dismiss"): gfo.commands.review.handle_dismiss,
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
    ("webhook", "test"): gfo.commands.webhook.handle_test,
    ("deploy-key", "list"): gfo.commands.deploy_key.handle_list,
    ("deploy-key", "create"): gfo.commands.deploy_key.handle_create,
    ("deploy-key", "delete"): gfo.commands.deploy_key.handle_delete,
    ("collaborator", "list"): gfo.commands.collaborator.handle_list,
    ("collaborator", "add"): gfo.commands.collaborator.handle_add,
    ("collaborator", "remove"): gfo.commands.collaborator.handle_remove,
    ("ci", "list"): gfo.commands.ci.handle_list,
    ("ci", "view"): gfo.commands.ci.handle_view,
    ("ci", "cancel"): gfo.commands.ci.handle_cancel,
    ("ci", "trigger"): gfo.commands.ci.handle_trigger,
    ("ci", "retry"): gfo.commands.ci.handle_retry,
    ("ci", "logs"): gfo.commands.ci.handle_logs,
    ("user", "whoami"): gfo.commands.user.handle_whoami,
    ("search", "repos"): gfo.commands.search.handle_repos,
    ("search", "issues"): gfo.commands.search.handle_issues,
    ("wiki", "list"): gfo.commands.wiki.handle_list,
    ("wiki", "view"): gfo.commands.wiki.handle_view,
    ("wiki", "create"): gfo.commands.wiki.handle_create,
    ("wiki", "update"): gfo.commands.wiki.handle_update,
    ("wiki", "delete"): gfo.commands.wiki.handle_delete,
    ("issue", "reaction"): gfo.commands.issue.handle_reaction,
    ("issue", "depends"): gfo.commands.issue.handle_depends,
    ("issue", "timeline"): gfo.commands.issue.handle_timeline,
    ("issue", "pin"): gfo.commands.issue.handle_pin,
    ("issue", "unpin"): gfo.commands.issue.handle_unpin,
    ("issue", "time"): gfo.commands.issue.handle_time,
    ("search", "prs"): gfo.commands.search.handle_prs,
    ("search", "commits"): gfo.commands.search.handle_commits,
    ("label", "clone"): gfo.commands.label.handle_clone,
    ("wiki", "revisions"): gfo.commands.wiki.handle_revisions,
    ("repo", "mirror"): gfo.commands.repo.handle_mirror,
    ("repo", "transfer"): gfo.commands.repo.handle_transfer,
    ("repo", "star"): gfo.commands.repo.handle_star,
    ("repo", "unstar"): gfo.commands.repo.handle_unstar,
    ("package", "list"): gfo.commands.package.handle_list,
    ("package", "view"): gfo.commands.package.handle_view,
    ("package", "delete"): gfo.commands.package.handle_delete,
    ("branch-protect", "list"): gfo.commands.branch_protect.handle_list,
    ("branch-protect", "view"): gfo.commands.branch_protect.handle_view,
    ("branch-protect", "set"): gfo.commands.branch_protect.handle_set,
    ("branch-protect", "remove"): gfo.commands.branch_protect.handle_remove,
    ("tag-protect", "list"): gfo.commands.tag_protect.handle_list,
    ("tag-protect", "create"): gfo.commands.tag_protect.handle_create,
    ("tag-protect", "delete"): gfo.commands.tag_protect.handle_delete,
    ("notification", "list"): gfo.commands.notification.handle_list,
    ("notification", "read"): gfo.commands.notification.handle_read,
    ("org", "list"): gfo.commands.org.handle_list,
    ("org", "view"): gfo.commands.org.handle_view,
    ("org", "members"): gfo.commands.org.handle_members,
    ("org", "repos"): gfo.commands.org.handle_repos,
    ("org", "create"): gfo.commands.org.handle_create,
    ("org", "delete"): gfo.commands.org.handle_delete,
    ("secret", "list"): gfo.commands.secret.handle_list,
    ("secret", "set"): gfo.commands.secret.handle_set,
    ("secret", "delete"): gfo.commands.secret.handle_delete,
    ("variable", "list"): gfo.commands.variable.handle_list,
    ("variable", "set"): gfo.commands.variable.handle_set,
    ("variable", "get"): gfo.commands.variable.handle_get,
    ("variable", "delete"): gfo.commands.variable.handle_delete,
    ("ssh-key", "list"): gfo.commands.ssh_key.handle_list,
    ("ssh-key", "create"): gfo.commands.ssh_key.handle_create,
    ("ssh-key", "delete"): gfo.commands.ssh_key.handle_delete,
    ("gpg-key", "list"): gfo.commands.gpg_key.handle_list,
    ("gpg-key", "create"): gfo.commands.gpg_key.handle_create,
    ("gpg-key", "delete"): gfo.commands.gpg_key.handle_delete,
    ("browse", None): gfo.commands.browse.handle_browse,
    ("api", None): gfo.commands.api.handle_api,
    ("schema", None): gfo.commands.schema.handle_schema,
}


def _ensure_utf8_stdio() -> None:
    """Windows で stdout/stderr を UTF-8 に切り替える。

    cp932 では一部の Unicode 文字（絵文字等）を出力できず UnicodeEncodeError や
    文字化けが発生するため、CLI 起動時に UTF-8 へ reconfigure する。
    """
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name)
        if hasattr(stream, "reconfigure") and getattr(stream, "encoding", "").lower() != "utf-8":
            stream.reconfigure(encoding="utf-8")


def _resolve_format(args_format: str | None, jq_expr: str | None) -> str:
    """出力フォーマットを解決する。優先順位: --jq > --format > config > TTY 検出。"""
    if jq_expr is not None:
        return "json"
    if args_format:
        return args_format
    cfg_fmt = get_configured_output_format()
    if cfg_fmt is not None:
        return cfg_fmt
    if not sys.stdout.isatty() and not os.environ.get("GFO_NO_AUTO_JSON"):
        return "json"
    return "table"


def _pre_parse_format(argv: list[str] | None) -> str | None:
    """parse_args 前に --format を簡易判定する（argparse エラーの JSON 構造化用）。"""
    args = argv if argv is not None else sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--format" and i + 1 < len(args):
            return args[i + 1]
        if arg.startswith("--format="):
            return arg.split("=", 1)[1]
        if arg == "--jq":
            return "json"
    return None


def main(argv: list[str] | None = None) -> int:
    """CLI エントリポイント。"""
    _ensure_utf8_stdio()
    parser, subparser_map = create_parser()

    try:
        args = parser.parse_args(argv)
    except ConfigError as err:
        pre_fmt = _pre_parse_format(argv)
        if pre_fmt == "json":
            print(format_error_json(err), file=sys.stderr)
        else:
            print(str(err), file=sys.stderr)
        return err.exit_code

    if args.command is None:
        parser.print_help()
        return 1

    jq_expr = args.jq
    if jq_expr is not None and not jq_expr:
        print(_("Error: --jq expression must not be empty."), file=sys.stderr)
        return 1
    resolved_fmt = _resolve_format(args.format, jq_expr)

    key = (args.command, getattr(args, "subcommand", None))

    if key not in _DISPATCH:
        # サブコマンド未指定の場合、該当コマンドの help を表示
        subparser_map[args.command].print_help()
        return 1

    handler = _DISPATCH[key]

    try:
        handler(args, fmt=resolved_fmt, jq=jq_expr)
        return 0
    except GfoError as err:
        if resolved_fmt == "json":
            print(format_error_json(err), file=sys.stderr)
        else:
            print(str(err), file=sys.stderr)
            if isinstance(err, NotSupportedError) and err.web_url:
                print(err.web_url)
        return err.exit_code
    except Exception as err:  # pragma: no cover
        print(_("Unexpected error: {err}").format(err=err), file=sys.stderr)
        return 1
