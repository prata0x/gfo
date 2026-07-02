"""confirm_action ヘルパーと破壊的コマンドの確認ガードのテスト。"""

from __future__ import annotations

import importlib
import json
from unittest.mock import patch

import pytest

from gfo.commands import confirm_action
from gfo.exceptions import ConfigError
from tests.test_commands.conftest import make_args, patch_adapter


class TestConfirmAction:
    def test_yes_flag_skips_prompt(self):
        """--yes 指定時は input() を呼ばずに True を返す。"""
        with patch("builtins.input", side_effect=AssertionError("input must not be called")):
            assert confirm_action(make_args(yes=True), "sure? ", fmt="table") is True

    def test_missing_yes_attr_treated_as_false(self):
        """args に yes 属性がない場合も --yes なしとして扱う（非対話では ConfigError）。"""
        with pytest.raises(ConfigError, match="--yes"):
            confirm_action(make_args(), "sure? ", fmt="table")

    def test_non_interactive_without_yes_raises(self):
        """非対話環境（stdin が TTY でない）ではプロンプトを出さず ConfigError。"""
        with pytest.raises(ConfigError, match="--yes"):
            confirm_action(make_args(yes=False), "sure? ", fmt="table")

    @pytest.mark.parametrize("answer", ["y", "yes", "Y", "YES", " y "])
    def test_accepts_yes_answers(self, interactive_stdin, answer):
        with patch("builtins.input", return_value=answer):
            assert confirm_action(make_args(yes=False), "sure? ", fmt="table") is True

    @pytest.mark.parametrize("answer", ["", "n", "no", "nope"])
    def test_rejects_other_answers(self, interactive_stdin, answer, capsys):
        with patch("builtins.input", return_value=answer):
            assert confirm_action(make_args(yes=False), "sure? ", fmt="table") is False
        assert "Aborted" in capsys.readouterr().out

    def test_reject_json_format(self, interactive_stdin, capsys):
        """fmt="json" で拒否すると result="aborted" の JSON が出力される。"""
        with patch("builtins.input", return_value="n"):
            assert confirm_action(make_args(yes=False), "sure? ", fmt="json") is False
        data = json.loads(capsys.readouterr().out)
        assert data["result"] == "aborted"


# (モジュール, ハンドラ名, args, 呼ばれてはいけないアダプターメソッド)
_DESTRUCTIVE_CASES = [
    ("gfo.commands.issue", "handle_delete", {"number": 1}, "delete_issue"),
    (
        "gfo.commands.issue",
        "handle_time",
        {"time_action": "delete", "number": 1, "entry_id": "42"},
        "delete_time_entry",
    ),
    (
        "gfo.commands.comment",
        "handle_pr_comment",
        {"comment_action": "delete", "comment_id": 42},
        "delete_comment",
    ),
    (
        "gfo.commands.comment",
        "handle_issue_comment",
        {"comment_action": "delete", "comment_id": 42},
        "delete_comment",
    ),
    ("gfo.commands.release", "handle_delete", {"tag": "v1.0.0"}, "delete_release"),
    (
        "gfo.commands.release",
        "handle_asset",
        {"asset_action": "delete", "tag": "v1.0.0", "asset_id": 7},
        "delete_release_asset",
    ),
    ("gfo.commands.label", "handle_delete", {"name": "bug"}, "delete_label"),
    ("gfo.commands.milestone", "handle_delete", {"number": 3}, "delete_milestone"),
    ("gfo.commands.branch", "handle_delete", {"name": "feature/x"}, "delete_branch"),
    ("gfo.commands.tag", "handle_delete", {"name": "v1"}, "delete_tag"),
    (
        "gfo.commands.file",
        "handle_delete",
        {"path": "a.txt", "branch": None, "message": "remove"},
        "delete_file",
    ),
    ("gfo.commands.webhook", "handle_delete", {"id": 5}, "delete_webhook"),
    ("gfo.commands.deploy_key", "handle_delete", {"id": 5}, "delete_deploy_key"),
    ("gfo.commands.ssh_key", "handle_delete", {"id": 5}, "delete_ssh_key"),
    ("gfo.commands.gpg_key", "handle_delete", {"id": 5}, "delete_gpg_key"),
    ("gfo.commands.collaborator", "handle_remove", {"username": "alice"}, "remove_collaborator"),
    ("gfo.commands.ci", "handle_delete", {"id": 9}, "delete_pipeline_run"),
    ("gfo.commands.wiki", "handle_delete", {"id": "Home"}, "delete_wiki_page"),
    (
        "gfo.commands.branch_protect",
        "handle_remove",
        {"branch": "main"},
        "remove_branch_protection",
    ),
    ("gfo.commands.tag_protect", "handle_delete", {"id": 2}, "delete_tag_protection"),
    ("gfo.commands.secret", "handle_delete", {"name": "TOKEN"}, "delete_secret"),
    ("gfo.commands.variable", "handle_delete", {"name": "VAR"}, "delete_variable"),
    (
        "gfo.commands.repo",
        "handle_mirror",
        {"mirror_action": "remove", "mirror_name": "m1"},
        "delete_push_mirror",
    ),
    ("gfo.commands.repo", "handle_delete", {}, "delete_repository"),
    ("gfo.commands.repo", "handle_archive", {}, "archive_repository"),
    (
        "gfo.commands.repo",
        "handle_transfer",
        {"new_owner": "new-owner", "team_id": None},
        "transfer_repository",
    ),
    ("gfo.commands.org", "handle_delete", {"name": "my-org"}, "delete_organization"),
    (
        "gfo.commands.package",
        "handle_delete",
        {"package_type": "npm", "name": "pkg", "version": "1.0.0"},
        "delete_package",
    ),
]

_CASE_IDS = [f"{m.rsplit('.', 1)[-1]}:{h}:{meth}" for m, h, _, meth in _DESTRUCTIVE_CASES]


class TestDestructiveCommandsRequireConfirmation:
    @pytest.mark.parametrize(
        ("module", "handler", "kwargs", "method"), _DESTRUCTIVE_CASES, ids=_CASE_IDS
    )
    def test_non_interactive_without_yes_raises(self, module, handler, kwargs, method):
        """非対話環境で --yes なしの破壊的操作は ConfigError（アダプター未呼び出し）。"""
        mod = importlib.import_module(module)
        with patch_adapter(module) as adapter:
            with pytest.raises(ConfigError, match="--yes"):
                getattr(mod, handler)(make_args(**kwargs), fmt="table")
        getattr(adapter, method).assert_not_called()

    def test_prompt_accept_runs_delete(self, interactive_stdin):
        """代表例（issue delete）: プロンプトに "y" で削除が実行される。"""
        mod = importlib.import_module("gfo.commands.issue")
        with patch_adapter("gfo.commands.issue") as adapter:
            with patch("builtins.input", return_value="y"):
                mod.handle_delete(make_args(number=1, yes=False), fmt="table")
        adapter.delete_issue.assert_called_once_with(1)

    def test_prompt_reject_aborts(self, interactive_stdin, capsys):
        """代表例（issue delete）: プロンプト拒否で "Aborted." が出力され削除されない。"""
        mod = importlib.import_module("gfo.commands.issue")
        with patch_adapter("gfo.commands.issue") as adapter:
            with patch("builtins.input", return_value="n"):
                mod.handle_delete(make_args(number=1, yes=False), fmt="table")
        adapter.delete_issue.assert_not_called()
        assert "Aborted" in capsys.readouterr().out
