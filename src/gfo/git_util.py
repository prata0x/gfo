"""git コマンドの subprocess 呼び出しをラップするユーティリティ。"""

from __future__ import annotations

import subprocess

from gfo.exceptions import GitCommandError

_DEFAULT_TIMEOUT = 30


def run_git(*args: str, cwd: str | None = None) -> str:
    """git コマンドを実行し stdout を返す。失敗時は GitCommandError。"""
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=_DEFAULT_TIMEOUT,
        cwd=cwd,
        shell=False,
    )
    if result.returncode != 0:
        raise GitCommandError(result.stderr.strip())
    return result.stdout.strip()


def get_remote_url(remote: str = "origin", cwd: str | None = None) -> str:
    """リモート URL を取得する。"""
    return run_git("remote", "get-url", remote, cwd=cwd)


def get_current_branch(cwd: str | None = None) -> str:
    """現在のブランチ名を取得する。"""
    return run_git("symbolic-ref", "--short", "HEAD", cwd=cwd)


def get_last_commit_subject(cwd: str | None = None) -> str:
    """直近コミットの subject を取得する。"""
    return run_git("log", "-1", "--format=%s", cwd=cwd)


def get_default_branch(remote: str = "origin", cwd: str | None = None) -> str:
    """デフォルトブランチ名を取得する。失敗時は "main" を返す。"""
    try:
        ref = run_git("symbolic-ref", f"refs/remotes/{remote}/HEAD", cwd=cwd)
    except GitCommandError:
        return "main"
    prefix = f"refs/remotes/{remote}/"
    if ref.startswith(prefix):
        return ref[len(prefix):]
    return ref


def git_config_get(key: str, cwd: str | None = None) -> str | None:
    """git config --local の値を取得する。未設定時は None。"""
    try:
        return run_git("config", "--local", key, cwd=cwd)
    except GitCommandError:
        return None


def git_config_set(key: str, value: str, cwd: str | None = None) -> None:
    """git config --local に値を設定する。"""
    run_git("config", "--local", key, value, cwd=cwd)


def git_fetch(remote: str, refspec: str, cwd: str | None = None) -> None:
    """git fetch を実行する。"""
    run_git("fetch", remote, refspec, cwd=cwd)


def git_checkout_new_branch(
    branch: str, start: str = "FETCH_HEAD", cwd: str | None = None
) -> None:
    """新しいブランチを作成してチェックアウトする。"""
    run_git("checkout", "-b", branch, start, cwd=cwd)


def git_clone(url: str, dest: str | None = None, cwd: str | None = None) -> None:
    """git clone を実行する。timeout=None。"""
    cmd = ["git", "clone", url]
    if dest is not None:
        cmd.append(dest)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        timeout=None,
        cwd=cwd,
        shell=False,
    )
    if result.returncode != 0:
        raise GitCommandError(result.stderr.strip())
