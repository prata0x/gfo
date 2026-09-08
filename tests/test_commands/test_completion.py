"""gfo.commands.completion のテスト。"""

from __future__ import annotations

import pytest

from gfo.commands import completion
from gfo.exceptions import ConfigError
from tests.test_commands.conftest import make_args


class TestHandleCompletion:
    """handle_completion のテスト。"""

    def test_bash(self, capsys):
        """bash 補完スクリプトが出力される。"""
        args = make_args(shell="bash")
        completion.handle_completion(args, fmt="table")
        captured = capsys.readouterr()
        assert "_gfo_completion" in captured.out
        assert "complete" in captured.out
        assert "COMPREPLY" in captured.out

    def test_zsh(self, capsys):
        """zsh 補完スクリプトが出力される。"""
        args = make_args(shell="zsh")
        completion.handle_completion(args, fmt="table")
        captured = capsys.readouterr()
        assert "#compdef gfo" in captured.out
        assert "_gfo" in captured.out
        assert "_arguments" in captured.out

    def test_fish(self, capsys):
        """fish 補完スクリプトが出力される。"""
        args = make_args(shell="fish")
        completion.handle_completion(args, fmt="table")
        captured = capsys.readouterr()
        assert "complete -c gfo" in captured.out
        assert "__fish_use_subcommand" in captured.out

    def test_unsupported_shell(self):
        """未対応シェル → ConfigError。"""
        args = make_args(shell="powershell")
        with pytest.raises(ConfigError, match="Unsupported shell"):
            completion.handle_completion(args, fmt="table")

    def test_contains_known_commands(self, capsys):
        """生成されたスクリプトに既知のコマンドが含まれる。"""
        args = make_args(shell="bash")
        completion.handle_completion(args, fmt="table")
        captured = capsys.readouterr()
        for cmd in ("pr", "issue", "auth", "release", "repo"):
            assert cmd in captured.out

    def test_contains_subcommands(self, capsys):
        """生成されたスクリプトにサブコマンドが含まれる。"""
        args = make_args(shell="bash")
        completion.handle_completion(args, fmt="table")
        captured = capsys.readouterr()
        # pr のサブコマンド
        assert "create" in captured.out
        assert "list" in captured.out
        assert "merge" in captured.out

    def test_fish_subcommands(self, capsys):
        """fish スクリプトにサブコマンド補完が含まれる。"""
        args = make_args(shell="fish")
        completion.handle_completion(args, fmt="table")
        captured = capsys.readouterr()
        assert "__fish_seen_subcommand_from pr" in captured.out

    def test_bash_global_opts(self, capsys):
        """bash スクリプトにグローバルオプションが含まれる。"""
        args = make_args(shell="bash")
        completion.handle_completion(args, fmt="table")
        captured = capsys.readouterr()
        assert "--format" in captured.out
        assert "--jq" in captured.out
        assert "--repo" in captured.out

    def test_zsh_global_opts(self, capsys):
        """zsh スクリプトにグローバルオプションが含まれる。"""
        args = make_args(shell="zsh")
        completion.handle_completion(args, fmt="table")
        captured = capsys.readouterr()
        assert "--format" in captured.out
        assert "--repo" in captured.out


class TestGlobalFlagDrift:
    """#587: cli.py のグローバルフラグ(-R 等)が補完から漏れていないこと。"""

    def test_short_r_in_all_shells(self, capsys):
        """-R (--repo の短縮形) が 3 シェル全ての補完に出る。

        bash/zsh はリテラル '-R' を、fish は短フラグ登録 '-s R' を出力する
        (いずれも `gfo -R <TAB>` で補完される)。
        """
        for shell in ("bash", "zsh", "fish"):
            args = make_args(shell=shell)
            completion.handle_completion(args, fmt="table")
            captured = capsys.readouterr()
            if shell == "fish":
                assert "-s R" in captured.out, "fish completion missing -R (short flag)"
            else:
                assert "-R" in captured.out, f"{shell} completion missing -R"

    def test_bash_format_value_completion(self, capsys):
        """bash でも --format の値補完(table json plain)が出る。"""
        args = make_args(shell="bash")
        completion.handle_completion(args, fmt="table")
        captured = capsys.readouterr()
        assert "table json plain" in captured.out


class TestGetCommandsAndSubcommands:
    """_get_commands_and_subcommands のテスト。"""

    def test_returns_dict(self):
        """dict を返す。"""
        result = completion._get_commands_and_subcommands()
        assert isinstance(result, dict)

    def test_has_known_commands(self):
        """既知のコマンドが含まれる。"""
        result = completion._get_commands_and_subcommands()
        assert "pr" in result
        assert "issue" in result
        assert "auth" in result

    def test_pr_has_subcommands(self):
        """pr にサブコマンドがある。"""
        result = completion._get_commands_and_subcommands()
        assert "list" in result["pr"]
        assert "create" in result["pr"]

    def test_browse_has_no_subcommands(self):
        """browse にサブコマンドがない。"""
        result = completion._get_commands_and_subcommands()
        assert result["browse"] == []

    def test_auth_has_token_subcommand(self):
        """auth に token サブコマンドがある。"""
        result = completion._get_commands_and_subcommands()
        assert "token" in result["auth"]
