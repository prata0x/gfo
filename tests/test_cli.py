"""cli.py のテスト。"""

from __future__ import annotations

import argparse
from unittest.mock import MagicMock, patch

import pytest

from gfo.cli import _DISPATCH, _positive_int, create_parser, main
from gfo.exceptions import GfoError, NotSupportedError

# ── _positive_int のテスト ──


def test_positive_int_valid():
    assert _positive_int("1") == 1
    assert _positive_int("100") == 100


def test_positive_int_zero_raises():
    with pytest.raises(argparse.ArgumentTypeError, match="0 is not a positive integer"):
        _positive_int("0")


def test_positive_int_negative_raises():
    with pytest.raises(argparse.ArgumentTypeError, match="-5 is not a positive integer"):
        _positive_int("-5")


def test_positive_int_non_integer_raises():
    with pytest.raises(argparse.ArgumentTypeError, match="abc is not a positive integer"):
        _positive_int("abc")


def test_positive_int_float_string_raises():
    with pytest.raises(argparse.ArgumentTypeError, match="1.5 is not a positive integer"):
        _positive_int("1.5")


# ── create_parser のテスト ──


def test_parser_version(capsys):
    parser, _ = create_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--version"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "gfo 0.1.0" in captured.out


def test_parser_init_defaults():
    parser, _ = create_parser()
    args = parser.parse_args(["init"])
    assert args.command == "init"
    assert args.non_interactive is False
    assert args.type is None
    assert args.host is None


def test_parser_init_non_interactive():
    parser, _ = create_parser()
    args = parser.parse_args(
        ["init", "--non-interactive", "--type", "github", "--host", "github.com"]
    )
    assert args.non_interactive is True
    assert args.type == "github"
    assert args.host == "github.com"


def test_parser_auth_login():
    parser, _ = create_parser()
    args = parser.parse_args(["auth", "login", "--host", "github.com", "--token", "tok"])
    assert args.command == "auth"
    assert args.subcommand == "login"
    assert args.host == "github.com"
    assert args.token == "tok"


def test_parser_auth_status():
    parser, _ = create_parser()
    args = parser.parse_args(["auth", "status"])
    assert args.command == "auth"
    assert args.subcommand == "status"


def test_parser_pr_list_defaults():
    parser, _ = create_parser()
    args = parser.parse_args(["pr", "list"])
    assert args.command == "pr"
    assert args.subcommand == "list"
    assert args.state == "open"
    assert args.limit == 30


def test_parser_pr_create():
    parser, _ = create_parser()
    args = parser.parse_args(["pr", "create", "--title", "My PR", "--draft"])
    assert args.title == "My PR"
    assert args.draft is True


def test_parser_pr_view():
    parser, _ = create_parser()
    args = parser.parse_args(["pr", "view", "42"])
    assert args.number == 42


def test_parser_pr_merge():
    parser, _ = create_parser()
    args = parser.parse_args(["pr", "merge", "5", "--method", "squash"])
    assert args.number == 5
    assert args.method == "squash"


def test_parser_pr_close():
    parser, _ = create_parser()
    args = parser.parse_args(["pr", "close", "3"])
    assert args.number == 3


def test_parser_pr_checkout():
    parser, _ = create_parser()
    args = parser.parse_args(["pr", "checkout", "7"])
    assert args.number == 7


def test_parser_issue_list():
    parser, _ = create_parser()
    args = parser.parse_args(["issue", "list", "--state", "closed", "--assignee", "alice"])
    assert args.state == "closed"
    assert args.assignee == "alice"


def test_parser_issue_create():
    parser, _ = create_parser()
    args = parser.parse_args(["issue", "create", "--title", "Bug"])
    assert args.title == "Bug"


def test_parser_issue_view():
    parser, _ = create_parser()
    args = parser.parse_args(["issue", "view", "10"])
    assert args.number == 10


def test_parser_issue_close():
    parser, _ = create_parser()
    args = parser.parse_args(["issue", "close", "10"])
    assert args.number == 10


def test_parser_issue_delete():
    parser, _ = create_parser()
    args = parser.parse_args(["issue", "delete", "7"])
    assert args.subcommand == "delete"
    assert args.number == 7


def test_parser_repo_list():
    parser, _ = create_parser()
    args = parser.parse_args(["repo", "list", "--limit", "10"])
    assert args.limit == 10


def test_parser_repo_create():
    parser, _ = create_parser()
    args = parser.parse_args(["repo", "create", "my-repo", "--private"])
    assert args.name == "my-repo"
    assert args.private is True


def test_parser_repo_clone_dest_repo():
    parser, _ = create_parser()
    args = parser.parse_args(["repo", "clone", "owner/repo"])
    assert args.repo == "owner/repo"


def test_parser_repo_clone_project_arg():
    """--project 引数が正しく parse される。"""
    parser, _ = create_parser()
    args = parser.parse_args(["repo", "clone", "owner/repo", "--project", "myproj"])
    assert args.project == "myproj"


def test_parser_repo_clone_project_default_none():
    """--project 未指定時は None。"""
    parser, _ = create_parser()
    args = parser.parse_args(["repo", "clone", "owner/repo"])
    assert args.project is None


def test_parser_repo_view_dest_repo():
    parser, _ = create_parser()
    args = parser.parse_args(["repo", "view", "owner/repo"])
    assert args.repo == "owner/repo"


def test_parser_repo_view_optional():
    parser, _ = create_parser()
    args = parser.parse_args(["repo", "view"])
    assert args.repo is None


def test_parser_repo_delete():
    parser, _ = create_parser()
    args = parser.parse_args(["repo", "delete"])
    assert args.subcommand == "delete"
    assert args.yes is False


def test_parser_repo_delete_yes_flag():
    parser, _ = create_parser()
    args = parser.parse_args(["repo", "delete", "--yes"])
    assert args.yes is True


def test_parser_repo_delete_short_yes_flag():
    parser, _ = create_parser()
    args = parser.parse_args(["repo", "delete", "-y"])
    assert args.yes is True


def test_parser_release_list():
    parser, _ = create_parser()
    args = parser.parse_args(["release", "list"])
    assert args.limit == 30


def test_parser_release_create():
    parser, _ = create_parser()
    args = parser.parse_args(["release", "create", "v1.0.0", "--draft", "--prerelease"])
    assert args.tag == "v1.0.0"
    assert args.draft is True
    assert args.prerelease is True


def test_parser_label_list():
    parser, _ = create_parser()
    args = parser.parse_args(["label", "list"])
    assert args.subcommand == "list"


def test_parser_label_create():
    parser, _ = create_parser()
    args = parser.parse_args(["label", "create", "bug", "--color", "red"])
    assert args.name == "bug"
    assert args.color == "red"


def test_parser_milestone_list():
    parser, _ = create_parser()
    args = parser.parse_args(["milestone", "list"])
    assert args.subcommand == "list"


def test_parser_milestone_create():
    parser, _ = create_parser()
    args = parser.parse_args(["milestone", "create", "v2.0", "--due", "2026-12-31"])
    assert args.title == "v2.0"
    assert args.due == "2026-12-31"


def test_parser_release_delete():
    parser, _ = create_parser()
    args = parser.parse_args(["release", "delete", "v1.0.0"])
    assert args.subcommand == "delete"
    assert args.tag == "v1.0.0"


def test_parser_label_delete():
    parser, _ = create_parser()
    args = parser.parse_args(["label", "delete", "bug"])
    assert args.subcommand == "delete"
    assert args.name == "bug"


def test_parser_milestone_delete():
    parser, _ = create_parser()
    args = parser.parse_args(["milestone", "delete", "5"])
    assert args.subcommand == "delete"
    assert args.number == 5


def test_parser_format_option():
    parser, _ = create_parser()
    args = parser.parse_args(["--format", "json", "pr", "list"])
    assert args.format == "json"


# ── browse パーサーのテスト ──


def test_parser_browse_defaults():
    parser, _ = create_parser()
    args = parser.parse_args(["browse"])
    assert args.command == "browse"
    assert args.pr is None
    assert args.issue is None
    assert args.settings is False
    assert getattr(args, "print") is False


def test_parser_browse_pr():
    parser, _ = create_parser()
    args = parser.parse_args(["browse", "--pr", "42"])
    assert args.pr == 42
    assert args.issue is None


def test_parser_browse_issue():
    parser, _ = create_parser()
    args = parser.parse_args(["browse", "--issue", "7"])
    assert args.issue == 7
    assert args.pr is None


def test_parser_browse_settings():
    parser, _ = create_parser()
    args = parser.parse_args(["browse", "--settings"])
    assert args.settings is True


def test_parser_browse_print():
    parser, _ = create_parser()
    args = parser.parse_args(["browse", "--print"])
    assert getattr(args, "print") is True


def test_parser_browse_mutually_exclusive():
    """--pr と --issue は同時指定できない。"""
    parser, _ = create_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["browse", "--pr", "1", "--issue", "2"])


# ── ssh-key パーサーのテスト ──


def test_parser_ssh_key_list():
    parser, _ = create_parser()
    args = parser.parse_args(["ssh-key", "list"])
    assert args.command == "ssh-key"
    assert args.subcommand == "list"
    assert args.limit == 30


def test_parser_ssh_key_create():
    parser, _ = create_parser()
    args = parser.parse_args(["ssh-key", "create", "--title", "my-key", "--key", "ssh-rsa AAAA"])
    assert args.subcommand == "create"
    assert args.title == "my-key"
    assert args.key == "ssh-rsa AAAA"


def test_parser_ssh_key_delete():
    parser, _ = create_parser()
    args = parser.parse_args(["ssh-key", "delete", "123"])
    assert args.subcommand == "delete"
    assert args.id == "123"


# ── branch-protect パーサーのテスト ──


def test_parser_branch_protect_list():
    parser, _ = create_parser()
    args = parser.parse_args(["branch-protect", "list"])
    assert args.command == "branch-protect"
    assert args.subcommand == "list"
    assert args.limit == 30


def test_parser_branch_protect_view():
    parser, _ = create_parser()
    args = parser.parse_args(["branch-protect", "view", "main"])
    assert args.subcommand == "view"
    assert args.branch == "main"


def test_parser_branch_protect_set():
    parser, _ = create_parser()
    args = parser.parse_args(
        [
            "branch-protect",
            "set",
            "main",
            "--require-reviews",
            "2",
            "--enforce-admins",
            "--allow-force-push",
        ]
    )
    assert args.subcommand == "set"
    assert args.branch == "main"
    assert args.require_reviews == 2
    assert args.enforce_admins is True
    assert args.allow_force_push is True


def test_parser_branch_protect_set_negations():
    parser, _ = create_parser()
    args = parser.parse_args(
        [
            "branch-protect",
            "set",
            "main",
            "--no-enforce-admins",
            "--no-allow-force-push",
            "--no-allow-deletions",
        ]
    )
    assert args.enforce_admins is False
    assert args.allow_force_push is False
    assert args.allow_deletions is False


def test_parser_branch_protect_remove():
    parser, _ = create_parser()
    args = parser.parse_args(["branch-protect", "remove", "main"])
    assert args.subcommand == "remove"
    assert args.branch == "main"


# ── notification パーサーのテスト ──


def test_parser_notification_list():
    parser, _ = create_parser()
    args = parser.parse_args(["notification", "list"])
    assert args.command == "notification"
    assert args.subcommand == "list"
    assert args.unread_only is False
    assert args.limit == 30


def test_parser_notification_list_unread_only():
    parser, _ = create_parser()
    args = parser.parse_args(["notification", "list", "--unread-only"])
    assert args.unread_only is True


def test_parser_notification_read_by_id():
    parser, _ = create_parser()
    args = parser.parse_args(["notification", "read", "42"])
    assert args.subcommand == "read"
    assert args.id == "42"
    assert args.mark_all is False


def test_parser_notification_read_all():
    parser, _ = create_parser()
    args = parser.parse_args(["notification", "read", "--all"])
    assert args.subcommand == "read"
    assert args.id is None
    assert args.mark_all is True


# ── org パーサーのテスト ──


def test_parser_org_list():
    parser, _ = create_parser()
    args = parser.parse_args(["org", "list"])
    assert args.command == "org"
    assert args.subcommand == "list"
    assert args.limit == 30


def test_parser_org_view():
    parser, _ = create_parser()
    args = parser.parse_args(["org", "view", "my-org"])
    assert args.subcommand == "view"
    assert args.name == "my-org"


def test_parser_org_members():
    parser, _ = create_parser()
    args = parser.parse_args(["org", "members", "my-org", "--limit", "10"])
    assert args.subcommand == "members"
    assert args.name == "my-org"
    assert args.limit == 10


def test_parser_org_repos():
    parser, _ = create_parser()
    args = parser.parse_args(["org", "repos", "my-org"])
    assert args.subcommand == "repos"
    assert args.name == "my-org"


# ── _DISPATCH テーブルのテスト ──


def test_dispatch_table_has_68_entries():
    assert len(_DISPATCH) == 89  # 82 + secret(3) + variable(4)


def test_dispatch_table_all_keys():
    expected_keys = {
        ("init", None),
        ("auth", "login"),
        ("auth", "status"),
        ("pr", "list"),
        ("pr", "create"),
        ("pr", "view"),
        ("pr", "merge"),
        ("pr", "close"),
        ("pr", "checkout"),
        ("pr", "update"),
        ("issue", "list"),
        ("issue", "create"),
        ("issue", "view"),
        ("issue", "close"),
        ("issue", "delete"),
        ("issue", "update"),
        ("repo", "list"),
        ("repo", "create"),
        ("repo", "clone"),
        ("repo", "view"),
        ("repo", "delete"),
        ("repo", "fork"),
        ("release", "list"),
        ("release", "create"),
        ("release", "delete"),
        ("label", "list"),
        ("label", "create"),
        ("label", "delete"),
        ("milestone", "list"),
        ("milestone", "create"),
        ("milestone", "delete"),
        ("comment", "list"),
        ("comment", "create"),
        ("comment", "update"),
        ("comment", "delete"),
        ("review", "list"),
        ("review", "create"),
        ("branch", "list"),
        ("branch", "create"),
        ("branch", "delete"),
        ("tag", "list"),
        ("tag", "create"),
        ("tag", "delete"),
        ("status", "list"),
        ("status", "create"),
        ("file", "get"),
        ("file", "put"),
        ("file", "delete"),
        ("webhook", "list"),
        ("webhook", "create"),
        ("webhook", "delete"),
        ("deploy-key", "list"),
        ("deploy-key", "create"),
        ("deploy-key", "delete"),
        ("collaborator", "list"),
        ("collaborator", "add"),
        ("collaborator", "remove"),
        ("ci", "list"),
        ("ci", "view"),
        ("ci", "cancel"),
        ("user", "whoami"),
        ("search", "repos"),
        ("search", "issues"),
        ("wiki", "list"),
        ("wiki", "view"),
        ("wiki", "create"),
        ("wiki", "update"),
        ("wiki", "delete"),
        ("branch-protect", "list"),
        ("branch-protect", "view"),
        ("branch-protect", "set"),
        ("branch-protect", "remove"),
        ("notification", "list"),
        ("notification", "read"),
        ("org", "list"),
        ("org", "view"),
        ("org", "members"),
        ("org", "repos"),
        ("secret", "list"),
        ("secret", "set"),
        ("secret", "delete"),
        ("variable", "list"),
        ("variable", "set"),
        ("variable", "get"),
        ("variable", "delete"),
        ("ssh-key", "list"),
        ("ssh-key", "create"),
        ("ssh-key", "delete"),
        ("browse", None),
    }
    assert set(_DISPATCH.keys()) == expected_keys


def test_dispatch_table_all_callable():
    for key, handler in _DISPATCH.items():
        assert callable(handler), f"Handler for {key} is not callable"


# ── main() のテスト ──


def test_main_no_args_returns_1(capsys):
    result = main([])
    assert result == 1
    captured = capsys.readouterr()
    assert "gfo" in captured.out  # help テキストに prog 名が含まれる


def test_main_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "gfo 0.1.0" in captured.out


def test_main_subcommand_only_returns_1(capsys):
    result = main(["pr"])
    assert result == 1


def test_main_normal_dispatch():
    mock_handler = MagicMock()
    with patch.dict(_DISPATCH, {("pr", "list"): mock_handler}):
        with patch("gfo.cli.get_default_output_format", return_value="table"):
            result = main(["pr", "list"])
    assert result == 0
    mock_handler.assert_called_once()
    _, kwargs = mock_handler.call_args
    assert kwargs["fmt"] == "table"


def test_main_format_override():
    mock_handler = MagicMock()
    with patch.dict(_DISPATCH, {("pr", "list"): mock_handler}):
        result = main(["--format", "json", "pr", "list"])
    assert result == 0
    _, kwargs = mock_handler.call_args
    assert kwargs["fmt"] == "json"


def test_main_format_plain_override():
    """--format plain が fmt に正しく伝搬する。"""
    mock_handler = MagicMock()
    with patch.dict(_DISPATCH, {("pr", "list"): mock_handler}):
        result = main(["--format", "plain", "pr", "list"])
    assert result == 0
    _, kwargs = mock_handler.call_args
    assert kwargs["fmt"] == "plain"


def test_main_default_format_from_config_plain():
    """config.toml の output = "plain" が fmt に伝搬する。"""
    mock_handler = MagicMock()
    with (
        patch.dict(_DISPATCH, {("pr", "list"): mock_handler}),
        patch("gfo.cli.get_default_output_format", return_value="plain"),
    ):
        result = main(["pr", "list"])
    assert result == 0
    _, kwargs = mock_handler.call_args
    assert kwargs["fmt"] == "plain"


def test_main_jq_forces_json():
    """--jq 指定時に fmt が json に強制される。"""
    mock_handler = MagicMock()
    with patch.dict(_DISPATCH, {("pr", "list"): mock_handler}):
        result = main(["--jq", ".[].title", "pr", "list"])
    assert result == 0
    _, kwargs = mock_handler.call_args
    assert kwargs["fmt"] == "json"
    assert kwargs["jq"] == ".[].title"


def test_main_jq_overrides_format_table():
    """--jq は --format table を上書きして json にする。"""
    mock_handler = MagicMock()
    with patch.dict(_DISPATCH, {("pr", "list"): mock_handler}):
        result = main(["--format", "table", "--jq", ".", "pr", "list"])
    assert result == 0
    _, kwargs = mock_handler.call_args
    assert kwargs["fmt"] == "json"
    assert kwargs["jq"] == "."


def test_main_no_jq_passes_none():
    """--jq なしでは jq=None が渡される。"""
    mock_handler = MagicMock()
    with patch.dict(_DISPATCH, {("pr", "list"): mock_handler}):
        result = main(["pr", "list"])
    assert result == 0
    _, kwargs = mock_handler.call_args
    assert kwargs["jq"] is None


def test_main_gfo_error_returns_1(capsys):
    def raise_gfo(args, *, fmt, jq=None):
        raise GfoError("something went wrong")

    with patch.dict(_DISPATCH, {("pr", "list"): raise_gfo}):
        result = main(["pr", "list"])
    assert result == 1
    captured = capsys.readouterr()
    assert "something went wrong" in captured.err


def test_main_not_supported_error_returns_1(capsys):
    def raise_nse(args, *, fmt, jq=None):
        raise NotSupportedError("github", "delete-repo", web_url="https://github.com/settings")

    with patch.dict(_DISPATCH, {("pr", "list"): raise_nse}):
        result = main(["pr", "list"])
    assert result == 1
    captured = capsys.readouterr()
    assert "github" in captured.err
    assert "https://github.com/settings" in captured.out


def test_main_not_supported_error_no_web_url(capsys):
    def raise_nse(args, *, fmt, jq=None):
        raise NotSupportedError("gitlab", "milestones")

    with patch.dict(_DISPATCH, {("pr", "list"): raise_nse}):
        result = main(["pr", "list"])
    assert result == 1
    captured = capsys.readouterr()
    assert "gitlab" in captured.err
    assert captured.out == ""
