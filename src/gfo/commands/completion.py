"""gfo completion サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.exceptions import ConfigError
from gfo.i18n import _


def _get_commands_and_subcommands() -> dict[str, list[str]]:
    """_DISPATCH からコマンドとサブコマンドの構造を取得する。"""
    from gfo.cli import _DISPATCH

    commands: dict[str, list[str]] = {}
    for cmd, sub in _DISPATCH:
        if cmd not in commands:
            commands[cmd] = []
        if sub is not None and sub not in commands[cmd]:
            commands[cmd].append(sub)
    return commands


def _generate_bash(commands: dict[str, list[str]]) -> str:
    """bash 補完スクリプトを生成する。"""
    cmd_list = " ".join(sorted(commands.keys()))

    subcmd_cases = []
    for cmd in sorted(commands.keys()):
        subs = commands[cmd]
        if subs:
            sub_list = " ".join(sorted(subs))
            subcmd_cases.append(
                f"        {cmd})\n"
                f'            COMPREPLY=($(compgen -W "{sub_list}" -- "$cur"))\n'
                f"            return\n"
                f"            ;;"
            )

    subcmd_block = "\n".join(subcmd_cases)

    return (
        "# bash completion for gfo\n"
        '# Usage: eval "$(gfo completion bash)"\n'
        "\n"
        "_gfo_completion() {\n"
        "    local cur prev words cword\n"
        "    _init_completion 2>/dev/null || {\n"
        "        COMPREPLY=()\n"
        '        cur="${COMP_WORDS[COMP_CWORD]}"\n'
        '        prev="${COMP_WORDS[COMP_CWORD-1]}"\n'
        '        words=("${COMP_WORDS[@]}")\n'
        "        cword=$COMP_CWORD\n"
        "    }\n"
        "\n"
        '    local global_opts="--format --jq --version --remote --repo --account"\n'
        "\n"
        "    if [[ $cword -eq 1 ]]; then\n"
        f'        COMPREPLY=($(compgen -W "{cmd_list} $global_opts" -- "$cur"))\n'
        "        return\n"
        "    fi\n"
        "\n"
        '    local command="${words[1]}"\n'
        '    if [[ $cword -eq 2 && "$cur" != -* ]]; then\n'
        '        case "$command" in\n'
        f"{subcmd_block}\n"
        "        esac\n"
        "    fi\n"
        "\n"
        '    COMPREPLY=($(compgen -W "$global_opts" -- "$cur"))\n'
        "}\n"
        "\n"
        "complete -o default -F _gfo_completion gfo\n"
    )


def _generate_zsh(commands: dict[str, list[str]]) -> str:
    """zsh 補完スクリプトを生成する。"""
    cmd_items = []
    for cmd in sorted(commands.keys()):
        cmd_items.append(f"        '{cmd}'")
    cmd_block = "\n".join(cmd_items)

    subcmd_cases = []
    for cmd in sorted(commands.keys()):
        subs = commands[cmd]
        if subs:
            sub_list = " ".join(sorted(subs))
            subcmd_cases.append(
                f'        {cmd})\n            _values "subcommand" {sub_list}\n            ;;'
            )

    subcmd_block = "\n".join(subcmd_cases)

    return (
        "#compdef gfo\n"
        "# zsh completion for gfo\n"
        '# Usage: gfo completion zsh > "${fpath[1]}/_gfo"\n'
        "\n"
        "_gfo() {\n"
        "    local -a commands\n"
        "    commands=(\n"
        f"{cmd_block}\n"
        "    )\n"
        "\n"
        "    _arguments -C \\\n"
        "        '--format[Output format]:format:(table json plain)' \\\n"
        "        '--jq[jq expression]:expression:' \\\n"
        "        '--version[Show version]' \\\n"
        "        '--remote[Git remote]:remote:' \\\n"
        "        '--repo[Target repository]:repo:' \\\n"
        "        '--account[Account name]:account:' \\\n"
        "        '1:command:->command' \\\n"
        "        '*::arg:->args'\n"
        "\n"
        '    case "$state" in\n'
        "    command)\n"
        '        _describe -t commands "gfo command" commands\n'
        "        ;;\n"
        "    args)\n"
        '        case "$words[1]" in\n'
        f"{subcmd_block}\n"
        "        esac\n"
        "        ;;\n"
        "    esac\n"
        "}\n"
        "\n"
        '_gfo "$@"\n'
    )


def _generate_fish(commands: dict[str, list[str]]) -> str:
    """fish 補完スクリプトを生成する。"""
    lines = [
        "# fish completion for gfo",
        "# Usage: gfo completion fish > ~/.config/fish/completions/gfo.fish",
        "",
        "# Disable file completion by default",
        "complete -c gfo -f",
        "",
        "# Global options",
        'complete -c gfo -l format -x -a "table json plain" -d "Output format"',
        'complete -c gfo -l jq -x -d "jq expression"',
        'complete -c gfo -l version -d "Show version"',
        'complete -c gfo -l remote -x -d "Git remote"',
        'complete -c gfo -l repo -x -d "Target repository"',
        'complete -c gfo -l account -x -d "Account name"',
        "",
        "# Commands",
    ]

    for cmd in sorted(commands.keys()):
        lines.append(f'complete -c gfo -n "__fish_use_subcommand" -a "{cmd}"')

    lines.append("")
    lines.append("# Subcommands")

    for cmd in sorted(commands.keys()):
        subs = commands[cmd]
        if subs:
            for sub in sorted(subs):
                lines.append(f'complete -c gfo -n "__fish_seen_subcommand_from {cmd}" -a "{sub}"')

    lines.append("")
    return "\n".join(lines)


_GENERATORS = {
    "bash": _generate_bash,
    "zsh": _generate_zsh,
    "fish": _generate_fish,
}


def handle_completion(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo completion のハンドラ。"""
    target_shell = args.shell
    if target_shell not in _GENERATORS:
        msg = _("Unsupported shell: {shell}. Use bash, zsh, or fish.").format(
            **{"shell": target_shell}
        )
        raise ConfigError(msg)

    commands = _get_commands_and_subcommands()
    print(_GENERATORS[target_shell](commands))
