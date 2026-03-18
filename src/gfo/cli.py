"""argparse ベースの CLI パーサーとディスパッチ層。"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable
from typing import NoReturn

import gfo.commands.api
import gfo.commands.auth_cmd
import gfo.commands.batch
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
from gfo._context import cli_remote, cli_repo
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

    parser.add_argument(
        "--remote",
        dest="global_remote",
        default=None,
        metavar="REMOTE",
        help=_("Use specified git remote instead of origin"),
    )
    parser.add_argument(
        "--repo",
        dest="global_repo",
        default=None,
        metavar="REPO",
        help=_("Specify target repository (URL or HOST/OWNER/REPO)"),
    )

    subparsers = parser.add_subparsers(dest="command")
    subparser_map: dict[str, argparse.ArgumentParser] = {}

    # gfo init
    init_parser = subparser_map["init"] = subparsers.add_parser(
        "init", help=_("Initialize project")
    )
    init_parser.add_argument(
        "--non-interactive", action="store_true", help=_("Run in non-interactive mode")
    )
    init_parser.add_argument("--type", help=_("Service type"))
    init_parser.add_argument("--host", help=_("Host URL"))
    init_parser.add_argument("--api-url", help=_("API base URL"))
    init_parser.add_argument("--project-key", help=_("Project key"))

    # gfo auth → サブサブコマンド
    auth_parser = subparser_map["auth"] = subparsers.add_parser(
        "auth", help=_("Manage authentication")
    )
    auth_sub = auth_parser.add_subparsers(dest="subcommand")
    login_parser = auth_sub.add_parser("login", help=_("Login to service"))
    login_parser.add_argument("--host", help=_("Host URL"))
    login_parser.add_argument("--token", help=_("Authentication token"))
    auth_sub.add_parser("status", help=_("Show authentication status"))

    # gfo pr → サブサブコマンド
    pr_parser = subparser_map["pr"] = subparsers.add_parser("pr", help=_("Manage pull requests"))
    pr_sub = pr_parser.add_subparsers(dest="subcommand")
    pr_list = pr_sub.add_parser("list", help=_("List pull requests"))
    pr_list.add_argument(
        "--state",
        choices=["open", "closed", "merged", "all"],
        default="open",
        help=_("Filter by state"),
    )
    pr_list.add_argument(
        "--limit", type=_positive_int, default=30, help=_("Maximum number of results")
    )
    pr_create = pr_sub.add_parser("create", help=_("Create pull request"))
    pr_create.add_argument("--title", help=_("Title"))
    pr_create.add_argument("--body", default="", help=_("Body"))
    pr_create.add_argument("--base", help=_("Base branch"))
    pr_create.add_argument("--head", help=_("Head branch"))
    pr_create.add_argument("--draft", action="store_true", help=_("Create as draft"))
    pr_view = pr_sub.add_parser("view", help=_("View pull request details"))
    pr_view.add_argument("number", type=int, help=_("PR number"))
    pr_merge = pr_sub.add_parser("merge", help=_("Merge pull request"))
    pr_merge.add_argument("number", type=int, help=_("PR number"))
    pr_merge.add_argument(
        "--method", choices=["merge", "squash", "rebase"], default="merge", help=_("Merge method")
    )
    pr_merge.add_argument("--auto", action="store_true", help=_("Enable auto-merge"))
    pr_close = pr_sub.add_parser("close", help=_("Close pull request"))
    pr_close.add_argument("number", type=int, help=_("PR number"))
    pr_checkout = pr_sub.add_parser("checkout", help=_("Checkout pull request branch"))
    pr_checkout.add_argument("number", type=int, help=_("PR number"))
    pr_reopen = pr_sub.add_parser("reopen", help=_("Reopen pull request"))
    pr_reopen.add_argument("number", type=int, help=_("PR number"))
    pr_diff = pr_sub.add_parser("diff", help=_("Show pull request diff"))
    pr_diff.add_argument("number", type=int, help=_("PR number"))
    pr_checks = pr_sub.add_parser("checks", help=_("List pull request checks"))
    pr_checks.add_argument("number", type=int, help=_("PR number"))
    pr_files = pr_sub.add_parser("files", help=_("List pull request changed files"))
    pr_files.add_argument("number", type=int, help=_("PR number"))
    pr_commits = pr_sub.add_parser("commits", help=_("List pull request commits"))
    pr_commits.add_argument("number", type=int, help=_("PR number"))
    pr_reviewers = pr_sub.add_parser("reviewers", help=_("Manage pull request reviewers"))
    pr_reviewers_sub = pr_reviewers.add_subparsers(dest="reviewer_action")
    pr_reviewers_list = pr_reviewers_sub.add_parser("list", help=_("List reviewers"))
    pr_reviewers_list.add_argument("number", type=int, help=_("PR number"))
    pr_reviewers_add = pr_reviewers_sub.add_parser("add", help=_("Add reviewers"))
    pr_reviewers_add.add_argument("number", type=int, help=_("PR number"))
    pr_reviewers_add.add_argument("users", nargs="+", help=_("Usernames"))
    pr_reviewers_remove = pr_reviewers_sub.add_parser("remove", help=_("Remove reviewers"))
    pr_reviewers_remove.add_argument("number", type=int, help=_("PR number"))
    pr_reviewers_remove.add_argument("users", nargs="+", help=_("Usernames"))
    pr_update_branch = pr_sub.add_parser("update-branch", help=_("Update pull request branch"))
    pr_update_branch.add_argument("number", type=int, help=_("PR number"))
    pr_ready = pr_sub.add_parser("ready", help=_("Mark as ready for review"))
    pr_ready.add_argument("number", type=int, help=_("PR number"))

    # gfo issue → サブサブコマンド
    issue_parser = subparser_map["issue"] = subparsers.add_parser("issue", help=_("Manage issues"))
    issue_sub = issue_parser.add_subparsers(dest="subcommand")
    issue_list = issue_sub.add_parser("list", help=_("List issues"))
    issue_list.add_argument(
        "--state", choices=["open", "closed", "all"], default="open", help=_("Filter by state")
    )
    issue_list.add_argument("--assignee", help=_("Filter by assignee"))
    issue_list.add_argument("--label", help=_("Filter by label"))
    issue_list.add_argument(
        "--limit", type=_positive_int, default=30, help=_("Maximum number of results")
    )
    issue_create = issue_sub.add_parser("create", help=_("Create issue"))
    issue_create.add_argument("--title", required=True, help=_("Title"))
    issue_create.add_argument("--body", default="", help=_("Body"))
    issue_create.add_argument("--assignee", help=_("Assignee"))
    issue_create.add_argument("--label", help=_("Label"))
    issue_create.add_argument("--type", help=_("Issue type"))
    issue_create.add_argument("--priority", type=int, help=_("Priority"))
    issue_view = issue_sub.add_parser("view", help=_("View issue details"))
    issue_view.add_argument("number", type=int, help=_("Issue number"))
    issue_close = issue_sub.add_parser("close", help=_("Close issue"))
    issue_close.add_argument("number", type=int, help=_("Issue number"))
    issue_delete = issue_sub.add_parser("delete", help=_("Delete issue"))
    issue_delete.add_argument("number", type=int, help=_("Issue number"))
    issue_reopen = issue_sub.add_parser("reopen", help=_("Reopen issue"))
    issue_reopen.add_argument("number", type=int, help=_("Issue number"))

    issue_migrate = issue_sub.add_parser("migrate", help=_("Migrate issues between services"))
    issue_migrate.add_argument(
        "--from", dest="from_spec", required=True, help=_("Source (host/owner/repo)")
    )
    issue_migrate.add_argument(
        "--to", dest="to_spec", required=True, help=_("Destination (host/owner/repo)")
    )
    migrate_target = issue_migrate.add_mutually_exclusive_group(required=True)
    migrate_target.add_argument("--number", type=int, help=_("Issue number to migrate"))
    migrate_target.add_argument("--numbers", help=_("Comma-separated issue numbers"))
    migrate_target.add_argument(
        "--all", dest="migrate_all", action="store_true", help=_("Migrate all issues")
    )

    # gfo issue-template → サブサブコマンド
    it_parser = subparser_map["issue-template"] = subparsers.add_parser(
        "issue-template", help=_("Manage issue templates")
    )
    it_sub = it_parser.add_subparsers(dest="subcommand")
    it_sub.add_parser("list", help=_("List issue templates"))

    # gfo repo → サブサブコマンド
    repo_parser = subparser_map["repo"] = subparsers.add_parser(
        "repo", help=_("Manage repositories")
    )
    repo_sub = repo_parser.add_subparsers(dest="subcommand")
    repo_list = repo_sub.add_parser("list", help=_("List repositories"))
    repo_list.add_argument("--owner", help=_("Repository owner"))
    repo_list.add_argument(
        "--limit", type=_positive_int, default=30, help=_("Maximum number of results")
    )
    repo_create = repo_sub.add_parser("create", help=_("Create repository"))
    repo_create.add_argument("name", help=_("Repository name"))
    repo_create.add_argument("--private", action="store_true", help=_("Create as private"))
    repo_create.add_argument("--description", default="", help=_("Description"))
    repo_create.add_argument("--host", help=_("Host URL"))
    repo_clone = repo_sub.add_parser("clone", help=_("Clone repository"))
    repo_clone.add_argument(
        "repo", help=_("Repository (owner/name)")
    )  # ハンドラは args.repo を参照
    repo_clone.add_argument("--host", help=_("Host URL"))
    repo_clone.add_argument(
        "--project", help=_("Project name (Azure DevOps)")
    )  # Azure DevOps 用プロジェクト名
    repo_view = repo_sub.add_parser("view", help=_("View repository details"))
    repo_view.add_argument(
        "repo", nargs="?", help=_("Repository (owner/name)")
    )  # ハンドラは args.repo を参照
    repo_delete = repo_sub.add_parser("delete", help=_("Delete repository"))
    repo_delete.add_argument("--yes", "-y", action="store_true", help=_("Skip confirmation prompt"))

    # gfo repo update
    repo_update = repo_sub.add_parser("update", help=_("Update repository settings"))
    repo_update.add_argument("--description", help=_("Description"))
    _repo_private_group = repo_update.add_mutually_exclusive_group()
    _repo_private_group.add_argument(
        "--private", dest="private", action="store_true", default=None, help=_("Set as private")
    )
    _repo_private_group.add_argument(
        "--public", dest="private", action="store_false", help=_("Set as public")
    )
    repo_update.add_argument(
        "--default-branch", dest="default_branch", help=_("Default branch name")
    )

    # gfo repo archive
    repo_archive = repo_sub.add_parser("archive", help=_("Archive repository"))
    repo_archive.add_argument(
        "--yes", "-y", action="store_true", help=_("Skip confirmation prompt")
    )

    # gfo repo languages
    repo_sub.add_parser("languages", help=_("List repository languages"))

    # gfo repo topics → サブサブコマンド
    repo_topics = repo_sub.add_parser("topics", help=_("Manage repository topics"))
    repo_topics_sub = repo_topics.add_subparsers(dest="topics_action")
    repo_topics_sub.add_parser("list", help=_("List topics"))
    repo_topics_add = repo_topics_sub.add_parser("add", help=_("Add topic"))
    repo_topics_add.add_argument("topic", help=_("Topic name"))
    repo_topics_remove = repo_topics_sub.add_parser("remove", help=_("Remove topic"))
    repo_topics_remove.add_argument("topic", help=_("Topic name"))
    repo_topics_set = repo_topics_sub.add_parser("set", help=_("Set topics"))
    repo_topics_set.add_argument("topics", nargs="+", help=_("Topic names"))

    # gfo repo compare
    repo_compare = repo_sub.add_parser("compare", help=_("Compare branches or commits"))
    repo_compare.add_argument("spec", help=_("Comparison spec (base...head)"))

    # gfo repo migrate
    repo_migrate = repo_sub.add_parser("migrate", help=_("Migrate repository from URL"))
    repo_migrate.add_argument("clone_url", help=_("Clone URL of source repository"))
    repo_migrate.add_argument("--name", required=True, help=_("Repository name"))
    repo_migrate.add_argument("--private", action="store_true", help=_("Create as private"))
    repo_migrate.add_argument("--description", default="", help=_("Description"))
    repo_migrate.add_argument("--mirror", action="store_true", help=_("Create as mirror"))
    repo_migrate.add_argument(
        "--auth-token", dest="auth_token", help=_("Authentication token for source")
    )

    # gfo release → サブサブコマンド
    release_parser = subparser_map["release"] = subparsers.add_parser(
        "release", help=_("Manage releases")
    )
    release_sub = release_parser.add_subparsers(dest="subcommand")
    release_list = release_sub.add_parser("list", help=_("List releases"))
    release_list.add_argument(
        "--limit", type=_positive_int, default=30, help=_("Maximum number of results")
    )
    release_create = release_sub.add_parser("create", help=_("Create release"))
    release_create.add_argument("tag", help=_("Tag name"))
    release_create.add_argument("--title", default=None, help=_("Title"))
    release_create.add_argument("--notes", default="", help=_("Release notes"))
    release_create.add_argument("--draft", action="store_true", help=_("Create as draft"))
    release_create.add_argument("--prerelease", action="store_true", help=_("Mark as prerelease"))
    release_delete = release_sub.add_parser("delete", help=_("Delete release"))
    release_delete.add_argument("tag", help=_("Tag name"))
    release_view = release_sub.add_parser("view", help=_("View release details"))
    release_view.add_argument("tag", nargs="?", help=_("Tag name"))
    release_view.add_argument("--latest", action="store_true", help=_("View latest release"))
    release_update = release_sub.add_parser("update", help=_("Update release"))
    release_update.add_argument("tag", help=_("Tag name"))
    release_update.add_argument("--title", help=_("Title"))
    release_update.add_argument("--notes", help=_("Release notes"))
    release_update.add_argument(
        "--draft", action="store_true", default=None, help=_("Mark as draft")
    )
    release_update.add_argument(
        "--no-draft", dest="draft", action="store_false", help=_("Unmark as draft")
    )
    release_update.add_argument(
        "--prerelease", action="store_true", default=None, help=_("Mark as prerelease")
    )
    release_update.add_argument(
        "--no-prerelease", dest="prerelease", action="store_false", help=_("Unmark as prerelease")
    )

    # gfo release asset → サブサブコマンド
    release_asset = release_sub.add_parser("asset", help=_("Manage release assets"))
    release_asset_sub = release_asset.add_subparsers(dest="asset_action")
    asset_list = release_asset_sub.add_parser("list", help=_("List assets"))
    asset_list.add_argument("--tag", required=True, help=_("Tag name"))
    asset_upload = release_asset_sub.add_parser("upload", help=_("Upload asset"))
    asset_upload.add_argument("--tag", required=True, help=_("Tag name"))
    asset_upload.add_argument("file", help=_("File path"))
    asset_upload.add_argument("--name", help=_("Asset name"))
    asset_download = release_asset_sub.add_parser("download", help=_("Download asset"))
    asset_download.add_argument("--tag", required=True, help=_("Tag name"))
    asset_download.add_argument("--pattern", help=_("Download pattern"))
    asset_download.add_argument("--dir", default=".", help=_("Download directory"))
    asset_download.add_argument("--asset-id", dest="asset_id", help=_("Asset ID"))
    asset_delete = release_asset_sub.add_parser("delete", help=_("Delete asset"))
    asset_delete.add_argument("--tag", required=True, help=_("Tag name"))
    asset_delete.add_argument("asset_id", help=_("Asset ID"))

    # gfo label → サブサブコマンド
    label_parser = subparser_map["label"] = subparsers.add_parser("label", help=_("Manage labels"))
    label_sub = label_parser.add_subparsers(dest="subcommand")
    label_sub.add_parser("list", help=_("List labels"))
    label_create = label_sub.add_parser("create", help=_("Create label"))
    label_create.add_argument("name", help=_("Label name"))
    label_create.add_argument("--color", help=_("Color (hex)"))
    label_create.add_argument("--description", help=_("Description"))
    label_delete = label_sub.add_parser("delete", help=_("Delete label"))
    label_delete.add_argument("name", help=_("Label name"))
    label_update = label_sub.add_parser("update", help=_("Update label"))
    label_update.add_argument("name", help=_("Label name"))
    label_update.add_argument("--new-name", dest="new_name", help=_("New name"))
    label_update.add_argument("--color", help=_("Color (hex)"))
    label_update.add_argument("--description", help=_("Description"))

    # gfo milestone → サブサブコマンド
    milestone_parser = subparser_map["milestone"] = subparsers.add_parser(
        "milestone", help=_("Manage milestones")
    )
    milestone_sub = milestone_parser.add_subparsers(dest="subcommand")
    milestone_sub.add_parser("list", help=_("List milestones"))
    milestone_create = milestone_sub.add_parser("create", help=_("Create milestone"))
    milestone_create.add_argument("title", help=_("Milestone title"))
    milestone_create.add_argument("--description", help=_("Description"))
    milestone_create.add_argument("--due", help=_("Due date"))
    milestone_delete = milestone_sub.add_parser("delete", help=_("Delete milestone"))
    milestone_delete.add_argument("number", type=int, help=_("Milestone number"))
    milestone_view = milestone_sub.add_parser("view", help=_("View milestone details"))
    milestone_view.add_argument("number", type=int, help=_("Milestone number"))
    milestone_update = milestone_sub.add_parser("update", help=_("Update milestone"))
    milestone_update.add_argument("number", type=int, help=_("Milestone number"))
    milestone_update.add_argument("--title", help=_("Title"))
    milestone_update.add_argument("--description", help=_("Description"))
    milestone_update.add_argument("--due", help=_("Due date"))
    milestone_update.add_argument("--state", choices=["open", "closed"], help=_("State"))
    milestone_close = milestone_sub.add_parser("close", help=_("Close milestone"))
    milestone_close.add_argument("number", type=int, help=_("Milestone number"))
    milestone_reopen = milestone_sub.add_parser("reopen", help=_("Reopen milestone"))
    milestone_reopen.add_argument("number", type=int, help=_("Milestone number"))

    # gfo comment → サブサブコマンド
    comment_parser = subparser_map["comment"] = subparsers.add_parser(
        "comment", help=_("Manage comments")
    )
    comment_sub = comment_parser.add_subparsers(dest="subcommand")
    comment_list = comment_sub.add_parser("list", help=_("List comments"))
    comment_list.add_argument(
        "resource", choices=["pr", "issue"], help=_("Resource type (pr/issue)")
    )
    comment_list.add_argument("number", type=int, help=_("Resource number"))
    comment_list.add_argument(
        "--limit", type=_positive_int, default=30, help=_("Maximum number of results")
    )
    comment_create = comment_sub.add_parser("create", help=_("Create comment"))
    comment_create.add_argument(
        "resource", choices=["pr", "issue"], help=_("Resource type (pr/issue)")
    )
    comment_create.add_argument("number", type=int, help=_("Resource number"))
    comment_create.add_argument("--body", required=True, help=_("Body"))
    comment_update = comment_sub.add_parser("update", help=_("Update comment"))
    comment_update.add_argument("comment_id", type=int, help=_("Comment ID"))
    comment_update.add_argument("--body", required=True, help=_("Body"))
    comment_update.add_argument(
        "--on",
        dest="on",
        choices=["pr", "issue"],
        required=True,
        help=_("Resource type (pr/issue)"),
    )
    comment_delete = comment_sub.add_parser("delete", help=_("Delete comment"))
    comment_delete.add_argument("comment_id", type=int, help=_("Comment ID"))
    comment_delete.add_argument(
        "--on",
        dest="on",
        choices=["pr", "issue"],
        required=True,
        help=_("Resource type (pr/issue)"),
    )

    # gfo pr update（既存 pr に追加）
    pr_update = pr_sub.add_parser("update", help=_("Update pull request"))
    pr_update.add_argument("number", type=int, help=_("PR number"))
    pr_update.add_argument("--title", help=_("Title"))
    pr_update.add_argument("--body", help=_("Body"))
    pr_update.add_argument("--base", help=_("Base branch"))

    # gfo issue update（既存 issue に追加）
    issue_update = issue_sub.add_parser("update", help=_("Update issue"))
    issue_update.add_argument("number", type=int, help=_("Issue number"))
    issue_update.add_argument("--title", help=_("Title"))
    issue_update.add_argument("--body", help=_("Body"))
    issue_update.add_argument("--assignee", help=_("Assignee"))
    issue_update.add_argument("--label", help=_("Label"))

    # gfo repo fork（既存 repo に追加）
    repo_fork = repo_sub.add_parser("fork", help=_("Fork repository"))
    repo_fork.add_argument("--org", help=_("Organization to fork into"))

    # gfo review → サブサブコマンド
    review_parser = subparser_map["review"] = subparsers.add_parser(
        "review", help=_("Manage reviews")
    )
    review_sub = review_parser.add_subparsers(dest="subcommand")
    review_list = review_sub.add_parser("list", help=_("List reviews"))
    review_list.add_argument("number", type=int, help=_("PR number"))
    review_create = review_sub.add_parser("create", help=_("Create review"))
    review_create.add_argument("number", type=int, help=_("PR number"))
    _review_group = review_create.add_mutually_exclusive_group(required=True)
    _review_group.add_argument("--approve", action="store_true", help=_("Approve"))
    _review_group.add_argument(
        "--request-changes", dest="request_changes", action="store_true", help=_("Request changes")
    )
    _review_group.add_argument("--comment", action="store_true", help=_("Comment only"))
    review_create.add_argument("--body", default="", help=_("Body"))
    review_dismiss = review_sub.add_parser("dismiss", help=_("Dismiss review"))
    review_dismiss.add_argument("number", type=int, help=_("PR number"))
    review_dismiss.add_argument("review_id", type=int, help=_("Review ID"))
    review_dismiss.add_argument("--message", default="", help=_("Message"))

    # gfo branch → サブサブコマンド
    branch_parser = subparser_map["branch"] = subparsers.add_parser(
        "branch", help=_("Manage branches")
    )
    branch_sub = branch_parser.add_subparsers(dest="subcommand")
    branch_list = branch_sub.add_parser("list", help=_("List branches"))
    branch_list.add_argument(
        "--limit", type=_positive_int, default=30, help=_("Maximum number of results")
    )
    branch_create = branch_sub.add_parser("create", help=_("Create branch"))
    branch_create.add_argument("name", help=_("Branch name"))
    branch_create.add_argument("--ref", required=True, help=_("Source ref"))
    branch_delete = branch_sub.add_parser("delete", help=_("Delete branch"))
    branch_delete.add_argument("name", help=_("Branch name"))

    # gfo tag → サブサブコマンド
    tag_parser = subparser_map["tag"] = subparsers.add_parser("tag", help=_("Manage tags"))
    tag_sub = tag_parser.add_subparsers(dest="subcommand")
    tag_list = tag_sub.add_parser("list", help=_("List tags"))
    tag_list.add_argument(
        "--limit", type=_positive_int, default=30, help=_("Maximum number of results")
    )
    tag_create = tag_sub.add_parser("create", help=_("Create tag"))
    tag_create.add_argument("name", help=_("Tag name"))
    tag_create.add_argument("--ref", required=True, help=_("Source ref"))
    tag_create.add_argument("--message", default="", help=_("Tag message"))
    tag_delete = tag_sub.add_parser("delete", help=_("Delete tag"))
    tag_delete.add_argument("name", help=_("Tag name"))

    # gfo status → サブサブコマンド
    status_parser = subparser_map["status"] = subparsers.add_parser(
        "status", help=_("Manage commit statuses")
    )
    status_sub = status_parser.add_subparsers(dest="subcommand")
    status_list = status_sub.add_parser("list", help=_("List commit statuses"))
    status_list.add_argument("ref", help=_("Commit ref"))
    status_list.add_argument(
        "--limit", type=_positive_int, default=30, help=_("Maximum number of results")
    )
    status_create = status_sub.add_parser("create", help=_("Create commit status"))
    status_create.add_argument("ref", help=_("Commit ref"))
    status_create.add_argument(
        "--state",
        required=True,
        choices=["success", "failure", "pending", "error"],
        help=_("Status state"),
    )
    status_create.add_argument("--context", help=_("Context name"))
    status_create.add_argument("--description", help=_("Description"))
    status_create.add_argument("--url", help=_("Target URL"))

    # gfo file → サブサブコマンド
    file_parser = subparser_map["file"] = subparsers.add_parser(
        "file", help=_("Manage repository files")
    )
    file_sub = file_parser.add_subparsers(dest="subcommand")
    file_get = file_sub.add_parser("get", help=_("Get file content"))
    file_get.add_argument("path", help=_("File path"))
    file_get.add_argument("--ref", help=_("Git ref"))
    file_put = file_sub.add_parser("put", help=_("Create or update file"))
    file_put.add_argument("path", help=_("File path"))
    file_put.add_argument("--message", required=True, help=_("Commit message"))
    file_put.add_argument("--branch", help=_("Target branch"))
    file_delete = file_sub.add_parser("delete", help=_("Delete file"))
    file_delete.add_argument("path", help=_("File path"))
    file_delete.add_argument("--message", required=True, help=_("Commit message"))
    file_delete.add_argument("--branch", help=_("Target branch"))

    # gfo webhook → サブサブコマンド
    webhook_parser = subparser_map["webhook"] = subparsers.add_parser(
        "webhook", help=_("Manage webhooks")
    )
    webhook_sub = webhook_parser.add_subparsers(dest="subcommand")
    webhook_list = webhook_sub.add_parser("list", help=_("List webhooks"))
    webhook_list.add_argument(
        "--limit", type=_positive_int, default=30, help=_("Maximum number of results")
    )
    webhook_create = webhook_sub.add_parser("create", help=_("Create webhook"))
    webhook_create.add_argument("--url", required=True, help=_("Webhook URL"))
    webhook_create.add_argument("--event", action="append", required=True, help=_("Event type"))
    webhook_create.add_argument("--secret", help=_("Webhook secret"))
    webhook_delete = webhook_sub.add_parser("delete", help=_("Delete webhook"))
    webhook_delete.add_argument("id", type=int, help=_("Webhook ID"))
    webhook_test = webhook_sub.add_parser("test", help=_("Test webhook"))
    webhook_test.add_argument("id", type=int, help=_("Webhook ID"))

    # gfo deploy-key → サブサブコマンド
    deploy_key_parser = subparser_map["deploy-key"] = subparsers.add_parser(
        "deploy-key", help=_("Manage deploy keys")
    )
    deploy_key_sub = deploy_key_parser.add_subparsers(dest="subcommand")
    deploy_key_list = deploy_key_sub.add_parser("list", help=_("List deploy keys"))
    deploy_key_list.add_argument(
        "--limit", type=_positive_int, default=30, help=_("Maximum number of results")
    )
    deploy_key_create = deploy_key_sub.add_parser("create", help=_("Create deploy key"))
    deploy_key_create.add_argument("--title", required=True, help=_("Title"))
    deploy_key_create.add_argument("--key", required=True, help=_("Public key"))
    deploy_key_create.add_argument(
        "--read-write", dest="read_write", action="store_true", help=_("Allow write access")
    )
    deploy_key_delete = deploy_key_sub.add_parser("delete", help=_("Delete deploy key"))
    deploy_key_delete.add_argument("id", type=int, help=_("Deploy key ID"))

    # gfo collaborator → サブサブコマンド
    collab_parser = subparser_map["collaborator"] = subparsers.add_parser(
        "collaborator", help=_("Manage collaborators")
    )
    collab_sub = collab_parser.add_subparsers(dest="subcommand")
    collab_list = collab_sub.add_parser("list", help=_("List collaborators"))
    collab_list.add_argument(
        "--limit", type=_positive_int, default=30, help=_("Maximum number of results")
    )
    collab_add = collab_sub.add_parser("add", help=_("Add collaborator"))
    collab_add.add_argument("username", help=_("Username"))
    collab_add.add_argument(
        "--permission",
        choices=["read", "write", "admin"],
        default="write",
        help=_("Permission level"),
    )
    collab_remove = collab_sub.add_parser("remove", help=_("Remove collaborator"))
    collab_remove.add_argument("username", help=_("Username"))

    # gfo ci → サブサブコマンド
    ci_parser = subparser_map["ci"] = subparsers.add_parser("ci", help=_("Manage CI pipelines"))
    ci_sub = ci_parser.add_subparsers(dest="subcommand")
    ci_list = ci_sub.add_parser("list", help=_("List pipelines"))
    ci_list.add_argument("--ref", help=_("Git ref"))
    ci_list.add_argument(
        "--limit", type=_positive_int, default=30, help=_("Maximum number of results")
    )
    ci_view = ci_sub.add_parser("view", help=_("View pipeline details"))
    ci_view.add_argument("id", help=_("Pipeline ID"))
    ci_cancel = ci_sub.add_parser("cancel", help=_("Cancel pipeline"))
    ci_cancel.add_argument("id", help=_("Pipeline ID"))
    ci_trigger = ci_sub.add_parser("trigger", help=_("Trigger pipeline"))
    ci_trigger.add_argument("--ref", required=True, help=_("Git ref"))
    ci_trigger.add_argument("--workflow", "-w", help=_("Workflow name or file"))
    ci_trigger.add_argument("--input", "-i", action="append", help=_("Input parameter (key=value)"))
    ci_retry = ci_sub.add_parser("retry", help=_("Retry pipeline"))
    ci_retry.add_argument("id", help=_("Pipeline ID"))
    ci_logs = ci_sub.add_parser("logs", help=_("View pipeline logs"))
    ci_logs.add_argument("id", help=_("Pipeline ID"))
    ci_logs.add_argument("--job", "-j", help=_("Job name or ID"))

    # gfo user → サブサブコマンド
    user_parser = subparser_map["user"] = subparsers.add_parser("user", help=_("User commands"))
    user_sub = user_parser.add_subparsers(dest="subcommand")
    user_sub.add_parser("whoami", help=_("Show current user"))

    # gfo search → サブサブコマンド
    search_parser = subparser_map["search"] = subparsers.add_parser(
        "search", help=_("Search resources")
    )
    search_sub = search_parser.add_subparsers(dest="subcommand")
    search_repos = search_sub.add_parser("repos", help=_("Search repositories"))
    search_repos.add_argument("query", help=_("Search query"))
    search_repos.add_argument(
        "--limit", type=_positive_int, default=30, help=_("Maximum number of results")
    )
    search_issues = search_sub.add_parser("issues", help=_("Search issues"))
    search_issues.add_argument("query", help=_("Search query"))
    search_issues.add_argument(
        "--limit", type=_positive_int, default=30, help=_("Maximum number of results")
    )

    # gfo wiki → サブサブコマンド
    wiki_parser = subparser_map["wiki"] = subparsers.add_parser("wiki", help=_("Manage wiki pages"))
    wiki_sub = wiki_parser.add_subparsers(dest="subcommand")
    wiki_list = wiki_sub.add_parser("list", help=_("List wiki pages"))
    wiki_list.add_argument(
        "--limit", type=_positive_int, default=30, help=_("Maximum number of results")
    )
    wiki_view = wiki_sub.add_parser("view", help=_("View wiki page"))
    wiki_view.add_argument("id", help=_("Page ID"))
    wiki_create = wiki_sub.add_parser("create", help=_("Create wiki page"))
    wiki_create.add_argument("--title", required=True, help=_("Title"))
    wiki_create.add_argument("--content", required=True, help=_("Content"))
    wiki_update = wiki_sub.add_parser("update", help=_("Update wiki page"))
    wiki_update.add_argument("id", help=_("Page ID"))
    wiki_update.add_argument("--title", help=_("Title"))
    wiki_update.add_argument("--content", help=_("Content"))
    wiki_delete = wiki_sub.add_parser("delete", help=_("Delete wiki page"))
    wiki_delete.add_argument("id", help=_("Page ID"))

    # -- New Phase 5 parsers --

    # gfo issue reaction → サブサブコマンド
    issue_reaction = issue_sub.add_parser("reaction", help=_("Manage issue reactions"))
    issue_reaction_sub = issue_reaction.add_subparsers(dest="reaction_action")
    issue_reaction_list = issue_reaction_sub.add_parser("list", help=_("List reactions"))
    issue_reaction_list.add_argument("number", type=int, help=_("Issue number"))
    issue_reaction_add = issue_reaction_sub.add_parser("add", help=_("Add reaction"))
    issue_reaction_add.add_argument("number", type=int, help=_("Issue number"))
    issue_reaction_add.add_argument("reaction", help=_("Reaction type"))
    issue_reaction_remove = issue_reaction_sub.add_parser("remove", help=_("Remove reaction"))
    issue_reaction_remove.add_argument("number", type=int, help=_("Issue number"))
    issue_reaction_remove.add_argument("reaction", help=_("Reaction type"))

    # gfo issue depends → サブサブコマンド
    issue_depends = issue_sub.add_parser("depends", help=_("Manage issue dependencies"))
    issue_depends_sub = issue_depends.add_subparsers(dest="depends_action")
    issue_depends_list = issue_depends_sub.add_parser("list", help=_("List dependencies"))
    issue_depends_list.add_argument("number", type=int, help=_("Issue number"))
    issue_depends_add = issue_depends_sub.add_parser("add", help=_("Add dependency"))
    issue_depends_add.add_argument("number", type=int, help=_("Issue number"))
    issue_depends_add.add_argument("depends_on", type=int, help=_("Dependency issue number"))
    issue_depends_remove = issue_depends_sub.add_parser("remove", help=_("Remove dependency"))
    issue_depends_remove.add_argument("number", type=int, help=_("Issue number"))
    issue_depends_remove.add_argument("depends_on", type=int, help=_("Dependency issue number"))

    # gfo issue timeline
    issue_timeline = issue_sub.add_parser("timeline", help=_("List issue timeline events"))
    issue_timeline.add_argument("number", type=int, help=_("Issue number"))
    issue_timeline.add_argument(
        "--limit", type=_positive_int, default=30, help=_("Maximum number of results")
    )

    # gfo issue pin / unpin
    issue_pin = issue_sub.add_parser("pin", help=_("Pin issue"))
    issue_pin.add_argument("number", type=int, help=_("Issue number"))
    issue_unpin = issue_sub.add_parser("unpin", help=_("Unpin issue"))
    issue_unpin.add_argument("number", type=int, help=_("Issue number"))

    # gfo issue time → サブサブコマンド
    issue_time = issue_sub.add_parser("time", help=_("Manage time tracking"))
    issue_time_sub = issue_time.add_subparsers(dest="time_action")
    issue_time_list = issue_time_sub.add_parser("list", help=_("List time entries"))
    issue_time_list.add_argument("number", type=int, help=_("Issue number"))
    issue_time_add = issue_time_sub.add_parser("add", help=_("Add time entry"))
    issue_time_add.add_argument("number", type=int, help=_("Issue number"))
    issue_time_add.add_argument("duration", help=_("Duration (e.g. 1h30m)"))
    issue_time_delete = issue_time_sub.add_parser("delete", help=_("Delete time entry"))
    issue_time_delete.add_argument("number", type=int, help=_("Issue number"))
    issue_time_delete.add_argument("entry_id", help=_("Time entry ID"))

    # gfo search prs
    search_prs = search_sub.add_parser("prs", help=_("Search pull requests"))
    search_prs.add_argument("query", help=_("Search query"))
    search_prs.add_argument(
        "--state", choices=["open", "closed", "merged", "all"], help=_("Filter by state")
    )
    search_prs.add_argument(
        "--limit", type=_positive_int, default=30, help=_("Maximum number of results")
    )

    # gfo search commits
    search_commits = search_sub.add_parser("commits", help=_("Search commits"))
    search_commits.add_argument("query", help=_("Search query"))
    search_commits.add_argument("--author", help=_("Filter by author"))
    search_commits.add_argument("--since", help=_("Start date"))
    search_commits.add_argument("--until", help=_("End date"))
    search_commits.add_argument(
        "--limit", type=_positive_int, default=30, help=_("Maximum number of results")
    )

    # gfo label clone
    label_clone = label_sub.add_parser("clone", help=_("Clone labels from another repository"))
    label_clone.add_argument(
        "--from", dest="source", required=True, help=_("Source repository (owner/name)")
    )
    label_clone.add_argument(
        "--overwrite", action="store_true", help=_("Overwrite existing labels")
    )

    # gfo wiki revisions
    wiki_revisions = wiki_sub.add_parser("revisions", help=_("List page revisions"))
    wiki_revisions.add_argument("page_name", help=_("Page name"))

    # gfo repo mirror → サブサブコマンド
    repo_mirror = repo_sub.add_parser("mirror", help=_("Manage push mirrors"))
    repo_mirror_sub = repo_mirror.add_subparsers(dest="mirror_action")
    repo_mirror_sub.add_parser("list", help=_("List push mirrors"))
    repo_mirror_add = repo_mirror_sub.add_parser("add", help=_("Add push mirror"))
    repo_mirror_add.add_argument("remote_address", help=_("Remote address"))
    repo_mirror_add.add_argument("--interval", default="8h", help=_("Sync interval"))
    repo_mirror_add.add_argument("--auth-token", dest="auth_token", help=_("Authentication token"))
    repo_mirror_remove = repo_mirror_sub.add_parser("remove", help=_("Remove push mirror"))
    repo_mirror_remove.add_argument("mirror_name", help=_("Mirror name"))
    repo_mirror_sub.add_parser("sync", help=_("Sync push mirrors"))

    # gfo repo transfer
    repo_transfer = repo_sub.add_parser("transfer", help=_("Transfer repository ownership"))
    repo_transfer.add_argument("new_owner", help=_("New owner"))
    repo_transfer.add_argument("--team-id", dest="team_id", type=int, help=_("Team ID"))
    repo_transfer.add_argument(
        "--yes", "-y", action="store_true", help=_("Skip confirmation prompt")
    )

    # gfo repo star / unstar
    repo_sub.add_parser("star", help=_("Star repository"))
    repo_sub.add_parser("unstar", help=_("Unstar repository"))

    # gfo package → サブサブコマンド
    package_parser = subparser_map["package"] = subparsers.add_parser(
        "package", help=_("Manage packages")
    )
    package_sub = package_parser.add_subparsers(dest="subcommand")
    package_list = package_sub.add_parser("list", help=_("List packages"))
    package_list.add_argument("--type", dest="type", help=_("Package type"))
    package_list.add_argument(
        "--limit", type=_positive_int, default=30, help=_("Maximum number of results")
    )
    package_view = package_sub.add_parser("view", help=_("View package details"))
    package_view.add_argument("package_type", help=_("Package type"))
    package_view.add_argument("name", help=_("Package name"))
    package_view.add_argument("--version", help=_("Version"))
    package_delete = package_sub.add_parser("delete", help=_("Delete package"))
    package_delete.add_argument("package_type", help=_("Package type"))
    package_delete.add_argument("name", help=_("Package name"))
    package_delete.add_argument("version", help=_("Version"))
    package_delete.add_argument(
        "--yes", "-y", action="store_true", help=_("Skip confirmation prompt")
    )

    # gfo branch-protect → サブサブコマンド
    bp_parser = subparser_map["branch-protect"] = subparsers.add_parser(
        "branch-protect", help=_("Manage branch protection rules")
    )
    bp_sub = bp_parser.add_subparsers(dest="subcommand")
    bp_list = bp_sub.add_parser("list", help=_("List branch protection rules"))
    bp_list.add_argument(
        "--limit", type=_positive_int, default=30, help=_("Maximum number of results")
    )
    bp_view = bp_sub.add_parser("view", help=_("View branch protection rule"))
    bp_view.add_argument("branch", help=_("Branch name"))
    bp_set = bp_sub.add_parser("set", help=_("Set branch protection rule"))
    bp_set.add_argument("branch", help=_("Branch name"))
    bp_set.add_argument(
        "--require-reviews", type=int, dest="require_reviews", help=_("Required review count")
    )
    bp_set.add_argument(
        "--require-status-checks",
        nargs="+",
        dest="require_status_checks",
        help=_("Required status checks"),
    )
    bp_set.add_argument(
        "--enforce-admins", action="store_true", default=None, help=_("Enforce rules for admins")
    )
    bp_set.add_argument(
        "--no-enforce-admins",
        dest="enforce_admins",
        action="store_false",
        help=_("Don't enforce rules for admins"),
    )
    bp_set.add_argument(
        "--allow-force-push", action="store_true", default=None, help=_("Allow force push")
    )
    bp_set.add_argument(
        "--no-allow-force-push",
        dest="allow_force_push",
        action="store_false",
        help=_("Disallow force push"),
    )
    bp_set.add_argument(
        "--allow-deletions", action="store_true", default=None, help=_("Allow branch deletion")
    )
    bp_set.add_argument(
        "--no-allow-deletions",
        dest="allow_deletions",
        action="store_false",
        help=_("Disallow branch deletion"),
    )
    bp_remove = bp_sub.add_parser("remove", help=_("Remove branch protection rule"))
    bp_remove.add_argument("branch", help=_("Branch name"))

    # gfo tag-protect → サブサブコマンド
    tp_parser = subparser_map["tag-protect"] = subparsers.add_parser(
        "tag-protect", help=_("Manage tag protection rules")
    )
    tp_sub = tp_parser.add_subparsers(dest="subcommand")
    tp_list = tp_sub.add_parser("list", help=_("List tag protection rules"))
    tp_list.add_argument(
        "--limit", type=_positive_int, default=30, help=_("Maximum number of results")
    )
    tp_create = tp_sub.add_parser("create", help=_("Create tag protection rule"))
    tp_create.add_argument("pattern", help=_("Tag pattern"))
    tp_create.add_argument("--access-level", dest="access_level", help=_("Access level"))
    tp_delete = tp_sub.add_parser("delete", help=_("Delete tag protection rule"))
    tp_delete.add_argument("id", help=_("Rule ID"))

    # gfo notification → サブサブコマンド
    notif_parser = subparser_map["notification"] = subparsers.add_parser(
        "notification", help=_("Manage notifications")
    )
    notif_sub = notif_parser.add_subparsers(dest="subcommand")
    notif_list = notif_sub.add_parser("list", help=_("List notifications"))
    notif_list.add_argument("--unread-only", action="store_true", help=_("Show unread only"))
    notif_list.add_argument(
        "--limit", type=_positive_int, default=30, help=_("Maximum number of results")
    )
    notif_read = notif_sub.add_parser("read", help=_("Mark notifications as read"))
    notif_read.add_argument("id", nargs="?", metavar="ID", help=_("Notification ID"))
    notif_read.add_argument(
        "--all", dest="mark_all", action="store_true", help=_("Mark all notifications as read")
    )

    # gfo org → サブサブコマンド
    org_parser = subparser_map["org"] = subparsers.add_parser("org", help=_("Manage organizations"))
    org_sub = org_parser.add_subparsers(dest="subcommand")
    org_list = org_sub.add_parser("list", help=_("List organizations"))
    org_list.add_argument(
        "--limit", type=_positive_int, default=30, help=_("Maximum number of results")
    )
    org_view = org_sub.add_parser("view", help=_("View organization details"))
    org_view.add_argument("name", help=_("Organization name"))
    org_members = org_sub.add_parser("members", help=_("List members"))
    org_members.add_argument("name", help=_("Organization name"))
    org_members.add_argument(
        "--limit", type=_positive_int, default=30, help=_("Maximum number of results")
    )
    org_repos = org_sub.add_parser("repos", help=_("List repositories"))
    org_repos.add_argument("name", help=_("Organization name"))
    org_repos.add_argument(
        "--limit", type=_positive_int, default=30, help=_("Maximum number of results")
    )
    org_create = org_sub.add_parser("create", help=_("Create organization"))
    org_create.add_argument("name", help=_("Organization name"))
    org_create.add_argument("--display-name", dest="display_name", help=_("Display name"))
    org_create.add_argument("--description", help=_("Description"))
    org_delete = org_sub.add_parser("delete", help=_("Delete organization"))
    org_delete.add_argument("name", help=_("Organization name"))
    org_delete.add_argument("--yes", "-y", action="store_true", help=_("Skip confirmation prompt"))

    # gfo ssh-key → サブサブコマンド
    ssh_key_parser = subparser_map["ssh-key"] = subparsers.add_parser(
        "ssh-key", help=_("Manage SSH keys")
    )
    ssh_key_sub = ssh_key_parser.add_subparsers(dest="subcommand")
    ssh_key_list = ssh_key_sub.add_parser("list", help=_("List SSH keys"))
    ssh_key_list.add_argument(
        "--limit", type=_positive_int, default=30, help=_("Maximum number of results")
    )
    ssh_key_create = ssh_key_sub.add_parser("create", help=_("Create SSH key"))
    ssh_key_create.add_argument("--title", required=True, help=_("Title"))
    ssh_key_create.add_argument("--key", required=True, help=_("Public key"))
    ssh_key_delete = ssh_key_sub.add_parser("delete", help=_("Delete SSH key"))
    ssh_key_delete.add_argument("id", type=int, help=_("SSH key ID"))

    # gfo gpg-key → サブサブコマンド
    gpg_key_parser = subparser_map["gpg-key"] = subparsers.add_parser(
        "gpg-key", help=_("Manage GPG keys")
    )
    gpg_key_sub = gpg_key_parser.add_subparsers(dest="subcommand")
    gpg_key_list = gpg_key_sub.add_parser("list", help=_("List GPG keys"))
    gpg_key_list.add_argument(
        "--limit", type=_positive_int, default=30, help=_("Maximum number of results")
    )
    gpg_key_create = gpg_key_sub.add_parser("create", help=_("Create GPG key"))
    gpg_key_create.add_argument("--key", required=True, help=_("GPG public key"))
    gpg_key_delete = gpg_key_sub.add_parser("delete", help=_("Delete GPG key"))
    gpg_key_delete.add_argument("id", type=int, help=_("GPG key ID"))

    # gfo secret → サブサブコマンド
    secret_parser = subparser_map["secret"] = subparsers.add_parser(
        "secret", help=_("Manage secrets")
    )
    secret_sub = secret_parser.add_subparsers(dest="subcommand")
    secret_list = secret_sub.add_parser("list", help=_("List secrets"))
    secret_list.add_argument(
        "--limit", type=_positive_int, default=30, help=_("Maximum number of results")
    )
    secret_set = secret_sub.add_parser("set", help=_("Set secret"))
    secret_set.add_argument("name", help=_("Secret name"))
    _secret_value_group = secret_set.add_mutually_exclusive_group(required=True)
    _secret_value_group.add_argument("--value", help=_("Secret value"))
    _secret_value_group.add_argument(
        "--env-var", dest="env_var", help=_("Environment variable name")
    )
    _secret_value_group.add_argument("--file", help=_("File path"))
    secret_delete = secret_sub.add_parser("delete", help=_("Delete secret"))
    secret_delete.add_argument("name", help=_("Secret name"))

    # gfo variable → サブサブコマンド
    variable_parser = subparser_map["variable"] = subparsers.add_parser(
        "variable", help=_("Manage variables")
    )
    variable_sub = variable_parser.add_subparsers(dest="subcommand")
    variable_list = variable_sub.add_parser("list", help=_("List variables"))
    variable_list.add_argument(
        "--limit", type=_positive_int, default=30, help=_("Maximum number of results")
    )
    variable_set = variable_sub.add_parser("set", help=_("Set variable"))
    variable_set.add_argument("name", help=_("Variable name"))
    variable_set.add_argument("--value", required=True, help=_("Value"))
    variable_set.add_argument("--masked", action="store_true", help=_("Mask variable in logs"))
    variable_get = variable_sub.add_parser("get", help=_("Get variable"))
    variable_get.add_argument("name", help=_("Variable name"))
    variable_delete = variable_sub.add_parser("delete", help=_("Delete variable"))
    variable_delete.add_argument("name", help=_("Variable name"))

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
        help=_("HTTP method"),
    )
    api_parser.add_argument("path", help=_("API path"))
    api_parser.add_argument("--data", "-d", help=_("Request body (JSON)"))
    api_parser.add_argument("--header", "-H", action="append", help=_("Request header"))

    # gfo batch → サブコマンド
    batch_parser = subparser_map["batch"] = subparsers.add_parser(
        "batch", help=_("Batch operations")
    )
    batch_sub = batch_parser.add_subparsers(dest="subcommand")

    # gfo batch pr → サブサブコマンド
    batch_pr = batch_sub.add_parser("pr", help=_("Batch pull request operations"))
    batch_pr_sub = batch_pr.add_subparsers(dest="batch_pr_action")
    batch_pr_create = batch_pr_sub.add_parser(
        "create", help=_("Create pull requests in multiple repositories")
    )
    batch_pr_create.add_argument(
        "--repos", required=True, help=_("Target repositories (comma-separated)")
    )
    batch_pr_create.add_argument("--title", required=True, help=_("Title"))
    batch_pr_create.add_argument("--body", default="", help=_("Body"))
    batch_pr_create.add_argument("--head", required=True, help=_("Head branch"))
    batch_pr_create.add_argument("--base", default="main", help=_("Base branch"))
    batch_pr_create.add_argument("--draft", action="store_true", help=_("Create as draft"))
    batch_pr_create.add_argument(
        "--dry-run", dest="dry_run", action="store_true", help=_("Dry run")
    )

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
    ("issue", "migrate"): gfo.commands.issue.handle_migrate,
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
    ("batch", "pr"): gfo.commands.batch.handle_batch_pr,
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

    # --repo と --remote の排他検証
    repo_value = getattr(args, "global_repo", None)
    remote_value = getattr(args, "global_remote", None)
    if repo_value and remote_value:
        pre_fmt = _pre_parse_format(argv)
        excl_err = ConfigError(_("--repo and --remote are mutually exclusive."))
        if pre_fmt == "json":
            print(format_error_json(excl_err), file=sys.stderr)
        else:
            print(str(excl_err), file=sys.stderr)
        return excl_err.exit_code

    # --remote / --repo の ContextVar 設定
    remote_token = cli_remote.set(remote_value)
    repo_token = cli_repo.set(repo_value)

    try:
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
    finally:
        cli_remote.reset(remote_token)
        cli_repo.reset(repo_token)
