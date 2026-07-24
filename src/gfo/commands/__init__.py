from __future__ import annotations

import argparse
from dataclasses import dataclass

import gfo.adapter.registry
import gfo.config
from gfo.adapter.base import GitServiceAdapter
from gfo.config import ProjectConfig


def _stdin_is_interactive() -> bool:
    """stdin が対話端末かどうか（テストで差し替えるためのシーム）。"""
    import sys

    return sys.stdin.isatty()


def confirm_action(
    args: argparse.Namespace, message: str, *, fmt: str, jq: str | None = None
) -> bool:
    """破壊的操作の実行前確認ヘルパー。

    - ``--yes`` 指定時は確認せず True を返す。
    - 非対話環境（stdin が TTY でない）ではプロンプトを出さずに ConfigError を
      投げる。パイプ・自動化・AI agent からの誤操作を防ぐため、非対話実行では
      ``--yes`` による明示同意を要求する。
    - プロンプトへの回答が y/yes 以外なら "Aborted." を出力して False を返す。
    """
    from gfo.exceptions import ConfigError
    from gfo.i18n import _
    from gfo.output import output_result

    if getattr(args, "yes", False):
        return True
    if not _stdin_is_interactive():
        raise ConfigError(
            _(
                "Confirmation required. Re-run with --yes to skip the prompt in non-interactive mode."
            )
        )
    answer = input(message)
    if answer.strip().lower() not in ("y", "yes"):
        output_result(_("Aborted."), result="aborted", fmt=fmt, jq=jq)
        return False
    return True


def read_token_input(*, stdin: bool = False, file_path: str | None = None) -> str | None:
    """``--*-stdin`` / ``--*-file`` 形式のフラグからトークンを読み込む共通ヘルパー。

    stdin が優先。どちらも指定されていなければ None を返す（呼び出し側で
    argv 経由フラグ等へフォールバックする）。空トークンは ConfigError。
    file 読み込み時は POSIX で group/other readable なら警告する。
    """
    import sys

    from gfo.exceptions import ConfigError
    from gfo.i18n import _

    if stdin:
        token = sys.stdin.read().strip()
        if not token:
            raise ConfigError(_("Empty token received from stdin"))
        return token
    if file_path:
        try:
            with open(file_path, encoding="utf-8") as f:
                token = f.read().strip()
        except OSError as e:
            raise ConfigError(
                _("Cannot read token file {path}: {error}").format(path=file_path, error=e)
            ) from e
        if not token:
            raise ConfigError(_("Empty token in file {path}").format(path=file_path))
        # POSIX 系で world/group readable のファイルからトークンを読むと
        # 他ユーザに漏れうるため警告 (Windows では mode bit が同じ意味を持たないのでスキップ)
        if sys.platform != "win32":
            import os
            import warnings

            try:
                mode = os.stat(file_path).st_mode
                if mode & 0o077:
                    warnings.warn(
                        _(
                            "Token file {path} is readable by other users "
                            "(mode {mode}). Run 'chmod 600 {path}' to restrict access."
                        ).format(path=file_path, mode=oct(mode & 0o777)),
                        stacklevel=2,
                    )
            except OSError:
                # 権限取得失敗は致命傷ではないので無視
                pass
        return token
    return None


def get_adapter(*, require_repo: bool = True) -> GitServiceAdapter:
    """設定を解決してアダプターインスタンスを返す共通ヘルパー。

    `require_repo=False` は、org/user/notification 操作等 owner/repo を
    一切参照しないハンドラ向け（owner/repo が未解決でも `ConfigError` にしない）。
    """
    config = gfo.config.resolve_project_config(require_repo=require_repo)
    return gfo.adapter.registry.create_adapter(config)


def get_adapter_with_config(
    *, require_repo: bool = True
) -> tuple[GitServiceAdapter, ProjectConfig]:
    """設定を解決してアダプターインスタンスと設定オブジェクトをまとめて返す。

    service_type 等の設定値を参照しつつアダプターを使用するハンドラ向け。
    """
    config = gfo.config.resolve_project_config(require_repo=require_repo)
    return gfo.adapter.registry.create_adapter(config), config


@dataclass(frozen=True, slots=True)
class ServiceSpec:
    """サービス指定文字列をパースした結果を保持するデータクラス。"""

    service_type: str
    host: str
    owner: str
    repo: str
    organization: str | None = None
    project_key: str | None = None


def parse_service_spec(spec: str) -> ServiceSpec:
    """サービス指定文字列をパースして ServiceSpec を返す。

    入力形式:
    - ``service:owner/repo`` — SaaS サービス（デフォルトホスト使用）
    - ``service:host:owner/repo`` — カスタムホスト指定
    - ``service:org/project/repo`` — Azure DevOps（デフォルトホスト）
    - ``service:host:org/project/repo`` — Azure DevOps（カスタムホスト）
    """
    from gfo.auth import _SERVICE_DEFAULT_HOSTS
    from gfo.exceptions import ConfigError
    from gfo.i18n import _

    _SELFHOSTED_SERVICES = {"gitea", "forgejo", "gogs", "gitbucket"}

    parts = spec.split(":", maxsplit=2)

    if len(parts) < 2 or not parts[0]:
        raise ConfigError(
            _(
                "Invalid service spec format: {spec}. Expected 'service:owner/repo' or 'service:host:owner/repo'."
            ).format(spec=spec)
        )

    service_type = parts[0]

    if len(parts) == 2:
        # service:owner_repo_part
        owner_repo_part = parts[1]
        if not owner_repo_part:
            raise ConfigError(
                _(
                    "Invalid service spec format: {spec}. Expected 'service:owner/repo' or 'service:host:owner/repo'."
                ).format(spec=spec)
            )
        if service_type in _SELFHOSTED_SERVICES:
            raise ConfigError(
                _(
                    "Self-hosted service '{service_type}' requires a host: '{service_type}:host:owner/repo'."
                ).format(service_type=service_type)
            )
        default_host = _SERVICE_DEFAULT_HOSTS.get(service_type)
        if not default_host:
            raise ConfigError(
                _("Unknown SaaS service type '{service_type}' with no default host.").format(
                    service_type=service_type
                )
            )
        host = default_host
    elif len(parts) == 3:
        # service:host:owner_repo_part
        host = parts[1]
        owner_repo_part = parts[2]
        if not host or not owner_repo_part:
            raise ConfigError(
                _(
                    "Invalid service spec format: {spec}. Expected 'service:host:owner/repo'."
                ).format(spec=spec)
            )
    else:
        raise ConfigError(
            _(
                "Invalid service spec format: {spec}. Expected 'service:owner/repo' or 'service:host:owner/repo'."
            ).format(spec=spec)
        )

    # owner_repo_part のパース
    if service_type == "azure-devops":
        segments = owner_repo_part.split("/")
        if len(segments) != 3:
            raise ConfigError(
                _("Azure DevOps requires 'org/project/repo' format, got: {part}").format(
                    part=owner_repo_part
                )
            )
        organization = segments[0]
        project_key = segments[1]
        repo = segments[2]
        if not organization or not project_key or not repo:
            raise ConfigError(
                _("Azure DevOps requires 'org/project/repo' format, got: {part}").format(
                    part=owner_repo_part
                )
            )
        return ServiceSpec(
            service_type=service_type,
            host=host,
            owner=organization,
            repo=repo,
            organization=organization,
            project_key=project_key,
        )
    elif service_type == "backlog":
        segments = owner_repo_part.split("/")
        if len(segments) != 2 or not segments[0] or not segments[1]:
            raise ConfigError(
                _(
                    "Invalid service spec format: {spec}. Expected 'service:host:owner/repo'."
                ).format(spec=spec)
            )
        project_key = segments[0]
        repo = segments[1]
        return ServiceSpec(
            service_type=service_type,
            host=host,
            owner=project_key,
            repo=repo,
            project_key=project_key,
        )
    else:
        segments = owner_repo_part.split("/")
        if len(segments) < 2 or not all(segments):
            raise ConfigError(
                _(
                    "Invalid service spec format: {spec}. Expected 'service:owner/repo' or 'service:host:owner/repo'."
                ).format(spec=spec)
            )
        owner = "/".join(segments[:-1])
        repo = segments[-1]
        return ServiceSpec(
            service_type=service_type,
            host=host,
            owner=owner,
            repo=repo,
        )


def create_adapter_from_spec(spec: ServiceSpec) -> GitServiceAdapter:
    """ServiceSpec からアダプターインスタンスを生成する。"""
    import gfo.adapter.registry
    import gfo.auth
    import gfo.config

    api_url = gfo.config.build_default_api_url(
        spec.service_type, spec.host, spec.organization, spec.project_key
    )
    token = gfo.auth.resolve_token(spec.host, spec.service_type)
    client = gfo.adapter.registry.create_http_client(spec.service_type, api_url, token)
    adapter_cls = gfo.adapter.registry.get_adapter_class(spec.service_type)
    kwargs: dict[str, str] = {}
    if spec.service_type == "backlog" and spec.project_key:
        kwargs["project_key"] = spec.project_key
    elif spec.service_type == "azure-devops":
        if spec.organization:
            kwargs["organization"] = spec.organization
        if spec.project_key:
            kwargs["project_key"] = spec.project_key
    return adapter_cls(client, spec.owner, spec.repo, **kwargs)


def open_in_browser(
    adapter: GitServiceAdapter, resource: str, number: int | str | None = None
) -> None:
    """`adapter.get_web_url(resource, number)` を Web ブラウザで開く共通ヘルパー。

    `--web` フラグ処理に使う。`webbrowser` のインポートと URL 解決を 1 箇所に
    集約することで、各コマンドで `import webbrowser; webbrowser.open(...)` を
    繰り返さないようにする。
    """
    import webbrowser

    if number is None:
        url = adapter.get_web_url(resource)
    else:
        url = adapter.get_web_url(resource, number)
    webbrowser.open(url)


def read_file_arg(path: str) -> str:
    """ファイルパスまたは '-'(stdin) からテキストを読み込む。"""
    import sys

    from gfo.exceptions import GfoError
    from gfo.i18n import _

    if path == "-":
        return sys.stdin.read()
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError as e:
        raise GfoError(_("File not found: {file}").format(file=path)) from e
    except PermissionError as e:
        raise GfoError(_("Permission denied: {file}").format(file=path)) from e
