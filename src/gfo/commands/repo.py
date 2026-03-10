"""gfo repo サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.adapter.registry import create_http_client, get_adapter_class
from gfo.auth import resolve_token
from gfo.commands import get_adapter
from gfo.config import (
    build_clone_url,
    build_default_api_url,
    get_default_host,
    get_host_config,
    resolve_project_config,
)
from gfo.detect import detect_service, get_known_service_type, probe_unknown_host
from gfo.exceptions import ConfigError, DetectionError, GitCommandError
from gfo.git_util import git_clone
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo repo list のハンドラ。"""
    adapter = get_adapter()
    repos = adapter.list_repositories(
        owner=getattr(args, "owner", None),
        limit=args.limit,
    )
    output(repos, fmt=fmt, fields=["name", "full_name", "private", "description"])


def _resolve_host_without_repo(args_host: str | None) -> tuple[str, str]:
    """リポジトリ外からホストとサービス種別を解決する。

    優先順位:
    1. args_host が指定されている場合はそれを使用
    2. detect_service() でホストを検出
    3. get_default_host() のデフォルトホストを使用
    4. いずれも失敗したら ConfigError
    """
    host: str | None = None

    if args_host:
        host = args_host
    else:
        try:
            result = detect_service()
            host = result.host
        except (DetectionError, GitCommandError):
            host = get_default_host()

    if not host:
        raise ConfigError(
            "Could not resolve host. Use --host option or set defaults.host in config.toml."
        )

    # service_type を解決（優先順位: ユーザー設定 > 既知ホスト > ネットワークプローブ）
    host_cfg = get_host_config(host)
    if host_cfg and "type" in host_cfg:
        service_type = host_cfg["type"]
    else:
        service_type = get_known_service_type(host)
        if not service_type:
            service_type = probe_unknown_host(host)
        if not service_type:
            raise ConfigError(
                f"Could not determine service type for host '{host}'. "
                f'Configure it in config.toml: [hosts.{host}] type = "..."'
            )

    return host, service_type


def handle_create(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo repo create のハンドラ。"""
    host, service_type = _resolve_host_without_repo(getattr(args, "host", None))

    # Azure DevOps と Backlog は API URL 構築・アダプター生成に organization/project_key が必要。
    # 現在のプロジェクト設定から取得を試みる（git リポジトリ外では ConfigError が発生する）。
    organization: str | None = None
    project_key: str | None = None
    if service_type in ("azure-devops", "backlog"):
        try:
            cfg = resolve_project_config()
            if cfg.service_type == service_type:
                organization = cfg.organization
                project_key = cfg.project_key
        except ConfigError:
            pass

    token = resolve_token(host, service_type)
    api_url = build_default_api_url(service_type, host, organization, project_key)

    client = create_http_client(service_type, api_url, token)
    adapter_cls = get_adapter_class(service_type)

    # サービスによってはコンストラクタに追加引数が必要
    extra_kwargs: dict = {}
    if service_type == "backlog":
        if not project_key:
            raise ConfigError(
                "Backlog requires a project key. Run 'gfo init' first to configure the project."
            )
        extra_kwargs["project_key"] = project_key
    elif service_type == "azure-devops":
        if not organization or not project_key:
            raise ConfigError(
                "Azure DevOps requires an organization and a project. "
                "Run 'gfo init' first to configure."
            )
        extra_kwargs["organization"] = organization
        extra_kwargs["project_key"] = project_key

    adapter = adapter_cls(client, "", "", **extra_kwargs)
    repo = adapter.create_repository(
        name=args.name,
        private=getattr(args, "private", False),
        description=getattr(args, "description", "") or "",
    )
    output(repo, fmt=fmt)


def _parse_repo_arg(repo_arg: str) -> tuple[str, str]:
    """'owner/name' 形式の文字列をパースして (owner, name) を返す。"""
    parts = repo_arg.split("/", 1)
    if len(parts) != 2:
        raise ConfigError(
            f"Invalid repo format '{repo_arg}'. Expected 'owner/name' with non-empty owner and name."
        )
    owner, name = parts[0].strip(), parts[1].strip()
    if not owner or not name:
        raise ConfigError(
            f"Invalid repo format '{repo_arg}'. Expected 'owner/name' with non-empty owner and name."
        )
    return owner, name


def handle_clone(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo repo clone のハンドラ。"""
    host, service_type = _resolve_host_without_repo(getattr(args, "host", None))
    owner, name = _parse_repo_arg(args.repo)
    url = build_clone_url(service_type, host, owner, name)
    git_clone(url)


def handle_view(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo repo view のハンドラ。"""
    adapter = get_adapter()

    repo_arg = getattr(args, "repo", None)
    if repo_arg:
        owner, name = _parse_repo_arg(repo_arg)
    else:
        owner, name = None, None

    repo = adapter.get_repository(owner, name)
    output(repo, fmt=fmt)


def handle_delete(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo repo delete のハンドラ。"""
    adapter = get_adapter()
    repo_name = f"{adapter._owner}/{adapter._repo}"
    if not getattr(args, "yes", False):
        confirm = input(
            f"Are you sure you want to delete repository '{repo_name}'? "
            "This action cannot be undone. [y/N]: "
        )
        if confirm.lower() not in ("y", "yes"):
            print("Aborted.")
            return
    adapter.delete_repository()
    print(f"Deleted repository '{repo_name}'.")


def handle_fork(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo repo fork のハンドラ。"""
    adapter = get_adapter()
    repo = adapter.fork_repository(organization=getattr(args, "org", None))
    output(repo, fmt=fmt)
