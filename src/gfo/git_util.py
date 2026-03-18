"""git コマンドの subprocess 呼び出しをラップするユーティリティ。"""

from __future__ import annotations

import re
import subprocess  # nosec B404
import warnings

from gfo.exceptions import GitCommandError

_DEFAULT_TIMEOUT = 30
_CLONE_TIMEOUT = 600


def _mask_credentials(text: str) -> str:
    """URL 内の認証情報（`://user:pass@` 形式）をマスクする。"""
    return re.sub(r"://[^/\s]*@", "://***@", text)


def run_git(*args: str, cwd: str | None = None) -> str:
    """git コマンドを実行し stdout を返す。失敗時は GitCommandError。"""
    try:
        result = subprocess.run(  # nosec B603 B607 - git is a fixed system command
            ["git", *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=_DEFAULT_TIMEOUT,
            cwd=cwd,
            shell=False,
        )
    except (FileNotFoundError, PermissionError) as e:
        raise GitCommandError(f"git command not found or not executable: {e}") from e
    except subprocess.TimeoutExpired as e:
        raise GitCommandError(f"git command timed out after {_DEFAULT_TIMEOUT}s") from e
    if result.returncode != 0:
        stderr_text = result.stderr.strip()
        if "not a git repository" in stderr_text.lower():
            raise GitCommandError(
                "Not inside a git repository. Run 'git init' or change to a git directory."
            )
        raise GitCommandError(_mask_credentials(stderr_text))
    return result.stdout.strip()


def list_remotes(cwd: str | None = None) -> list[str]:
    """git remote の一覧を返す。リモートが存在しない/git リポジトリ外の場合は空リスト。"""
    try:
        output = run_git("remote", cwd=cwd)
    except GitCommandError:
        return []
    return [line for line in output.splitlines() if line]


def get_remote_url(remote: str | None = None, cwd: str | None = None) -> str:
    """リモート URL を取得する。remote 未指定時は origin → 最初のリモートの順で解決。"""
    if remote is not None:
        return run_git("remote", "get-url", remote, cwd=cwd)
    try:
        return run_git("remote", "get-url", "origin", cwd=cwd)
    except GitCommandError:
        remotes = list_remotes(cwd=cwd)
        fallback = next((r for r in remotes if r != "origin"), None)
        if fallback is not None:
            warnings.warn(
                f"Remote 'origin' not found; using '{fallback}' instead.",
                stacklevel=2,
            )
            return run_git("remote", "get-url", fallback, cwd=cwd)
        raise


def get_current_branch(cwd: str | None = None) -> str:
    """現在のブランチ名を取得する。"""
    return run_git("symbolic-ref", "--short", "HEAD", cwd=cwd)


def get_last_commit_subject(cwd: str | None = None) -> str:
    """直近コミットの subject を取得する。"""
    return run_git("log", "-1", "--format=%s", cwd=cwd)


def _resolve_symbolic_head(remote: str, cwd: str | None) -> str | None:
    """リモートの symbolic-ref HEAD を解決する。失敗時は None。"""
    try:
        ref = run_git("symbolic-ref", f"refs/remotes/{remote}/HEAD", cwd=cwd)
    except GitCommandError:
        return None
    prefix = f"refs/remotes/{remote}/"
    return ref[len(prefix) :] if ref.startswith(prefix) else ref


def get_default_branch(remote: str | None = None, cwd: str | None = None) -> str:
    """デフォルトブランチ名を取得する。失敗時は "main" を返す。"""
    if remote is None:
        result = _resolve_symbolic_head("origin", cwd)
        if result is not None:
            return result
        remotes = list_remotes(cwd=cwd)
        fallback = next((r for r in remotes if r != "origin"), None)
        if fallback is not None:
            result = _resolve_symbolic_head(fallback, cwd)
            if result is not None:
                return result
        return "main"
    return _resolve_symbolic_head(remote, cwd) or "main"


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


def git_checkout_new_branch(branch: str, start: str = "FETCH_HEAD", cwd: str | None = None) -> None:
    """新しいブランチを作成してチェックアウトする。"""
    run_git("checkout", "-b", branch, start, cwd=cwd)


def git_checkout_branch(branch: str, start: str = "FETCH_HEAD", cwd: str | None = None) -> None:
    """ブランチが存在しなければ新規作成、存在すれば既存ブランチにスイッチする。"""
    try:
        run_git("checkout", "-b", branch, start, cwd=cwd)
    except GitCommandError as e:
        if "already exists" in str(e).lower():
            run_git("checkout", branch, cwd=cwd)
        else:
            raise


def git_clone(url: str, dest: str | None = None, cwd: str | None = None) -> None:
    """git clone を実行する。timeout=600。"""
    cmd = ["git", "clone", url]
    if dest is not None:
        cmd.append(dest)
    try:
        result = subprocess.run(  # nosec B603 B607 - git is a fixed system command
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=_CLONE_TIMEOUT,
            cwd=cwd,
            shell=False,
        )
    except (FileNotFoundError, PermissionError) as e:
        raise GitCommandError(f"git command not found or not executable: {e}") from e
    except subprocess.TimeoutExpired as e:
        raise GitCommandError(f"git clone timed out after {_CLONE_TIMEOUT}s") from e
    if result.returncode != 0:
        raw = (
            result.stderr.strip()
            or result.stdout.strip()
            or f"exited with code {result.returncode}"
        )
        raise GitCommandError(_mask_credentials(raw))
