"""cli.py のテスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gfo.cli import _DISPATCH, create_parser, main
from gfo.exceptions import GfoError, NotSupportedError


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
    args = parser.parse_args(["init", "--non-interactive", "--type", "github", "--host", "github.com"])
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


def test_parser_repo_view_dest_repo():
    parser, _ = create_parser()
    args = parser.parse_args(["repo", "view", "owner/repo"])
    assert args.repo == "owner/repo"


def test_parser_repo_view_optional():
    parser, _ = create_parser()
    args = parser.parse_args(["repo", "view"])
    assert args.repo is None


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


def test_parser_format_option():
    parser, _ = create_parser()
    args = parser.parse_args(["--format", "json", "pr", "list"])
    assert args.format == "json"


# ── _DISPATCH テーブルのテスト ──


def test_dispatch_table_has_22_entries():
    assert len(_DISPATCH) == 23  # init(None) + 22 subcommands


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
        ("issue", "list"),
        ("issue", "create"),
        ("issue", "view"),
        ("issue", "close"),
        ("repo", "list"),
        ("repo", "create"),
        ("repo", "clone"),
        ("repo", "view"),
        ("release", "list"),
        ("release", "create"),
        ("label", "list"),
        ("label", "create"),
        ("milestone", "list"),
        ("milestone", "create"),
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
    with patch.dict(_DISPATCH, {("pr", "list"): mock_handler}), \
         patch("gfo.cli.get_default_output_format", return_value="plain"):
        result = main(["pr", "list"])
    assert result == 0
    _, kwargs = mock_handler.call_args
    assert kwargs["fmt"] == "plain"


def test_main_gfo_error_returns_1(capsys):
    def raise_gfo(args, *, fmt):
        raise GfoError("something went wrong")

    with patch.dict(_DISPATCH, {("pr", "list"): raise_gfo}):
        result = main(["pr", "list"])
    assert result == 1
    captured = capsys.readouterr()
    assert "something went wrong" in captured.err


def test_main_not_supported_error_returns_1(capsys):
    def raise_nse(args, *, fmt):
        raise NotSupportedError("github", "delete-repo", web_url="https://github.com/settings")

    with patch.dict(_DISPATCH, {("pr", "list"): raise_nse}):
        result = main(["pr", "list"])
    assert result == 1
    captured = capsys.readouterr()
    assert "github" in captured.err
    assert "https://github.com/settings" in captured.out


def test_main_not_supported_error_no_web_url(capsys):
    def raise_nse(args, *, fmt):
        raise NotSupportedError("gitlab", "milestones")

    with patch.dict(_DISPATCH, {("pr", "list"): raise_nse}):
        result = main(["pr", "list"])
    assert result == 1
    captured = capsys.readouterr()
    assert "gitlab" in captured.err
    assert captured.out == ""
