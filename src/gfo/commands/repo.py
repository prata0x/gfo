"""gfo repo サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.adapter.registry import create_adapter, get_adapter_class
from gfo.auth import resolve_token
from gfo.config import (
    _build_default_api_url,
    get_default_host,
    get_host_config,
    resolve_project_config,
)
from gfo.detect import detect_service, probe_unknown_host
from gfo.exceptions import ConfigError, DetectionError
from gfo.git_util import git_clone
from gfo.http import HttpClient
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo repo list のハンドラ。"""
    config = resolve_project_config()
    adapter = create_adapter(config)
    repos = adapter.list_repositories(limit=args.limit)
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
        except DetectionError:
            host = get_default_host()

    if not host:
        raise ConfigError(
            "Could not resolve host. Use --host option or set defaults.host in config.toml."
        )

    # service_type を解決
    host_cfg = get_host_config(host)
    if host_cfg and "type" in host_cfg:
        service_type = host_cfg["type"]
    else:
        service_type = probe_unknown_host(host)
        if not service_type:
            # 既知ホストテーブルから解決を試みる
            from gfo.detect import _KNOWN_HOSTS
            service_type = _KNOWN_HOSTS.get(host)
        if not service_type:
            raise ConfigError(
                f"Could not determine service type for host '{host}'. "
                "Configure it in config.toml: [hosts.{host}] type = \"...\""
            )

    return host, service_type


def handle_create(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo repo create のハンドラ。"""
    host, service_type = _resolve_host_without_repo(getattr(args, "host", None))

    token = resolve_token(host, service_type)
    api_url = _build_default_api_url(service_type, host)

    if service_type == "backlog":
        client = HttpClient(api_url, auth_params={"apiKey": token})
    elif service_type == "bitbucket":
        if ":" not in token:
            raise ConfigError(
                "Bitbucket token must be in 'username:app-password' format."
            )
        user, pw = token.split(":", 1)
        client = HttpClient(api_url, basic_auth=(user, pw))
    elif service_type == "azure-devops":
        client = HttpClient(
            api_url,
            basic_auth=("", token),
            default_params={"api-version": "7.1"},
        )
    elif service_type == "gitlab":
        client = HttpClient(api_url, auth_header={"Private-Token": token})
    elif service_type == "github":
        client = HttpClient(api_url, auth_header={"Authorization": f"Bearer {token}"})
    elif service_type in ("gitea", "forgejo", "gogs", "gitbucket"):
        client = HttpClient(api_url, auth_header={"Authorization": f"token {token}"})
    else:
        from gfo.exceptions import UnsupportedServiceError
        raise UnsupportedServiceError(service_type)

    adapter_cls = get_adapter_class(service_type)
    adapter = adapter_cls(client, "", "")
    repo = adapter.create_repository(
        name=args.name,
        private=getattr(args, "private", False),
        description=getattr(args, "description", "") or "",
    )
    output(repo, fmt=fmt)


def handle_clone(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo repo clone のハンドラ。"""
    host, service_type = _resolve_host_without_repo(getattr(args, "host", None))

    repo_arg: str = args.repo
    parts = repo_arg.split("/", 1)
    if len(parts) == 2:
        owner, name = parts
    else:
        raise ConfigError(
            f"Invalid repo format '{repo_arg}'. Expected 'owner/name'."
        )

    if service_type == "github":
        url = f"https://github.com/{owner}/{name}.git"
    elif service_type == "gitlab":
        url = f"https://{host}/{owner}/{name}.git"
    elif service_type == "bitbucket":
        url = f"https://bitbucket.org/{owner}/{name}.git"
    elif service_type == "azure-devops":
        # owner = org, name = repo (project は owner と同じと仮定)
        url = f"https://dev.azure.com/{owner}/{owner}/_git/{name}"
    elif service_type in ("gitea", "forgejo", "gogs"):
        url = f"https://{host}/{owner}/{name}.git"
    elif service_type == "gitbucket":
        url = f"https://{host}/git/{owner}/{name}.git"
    elif service_type == "backlog":
        url = f"https://{host}/git/{owner}/{name}.git"
    else:
        url = f"https://{host}/{owner}/{name}.git"

    git_clone(url)


def handle_view(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo repo view のハンドラ。"""
    config = resolve_project_config()
    adapter = create_adapter(config)

    repo_arg = getattr(args, "repo", None)
    if repo_arg:
        parts = repo_arg.split("/", 1)
        if len(parts) == 2:
            owner, name = parts
        else:
            owner, name = None, repo_arg
    else:
        owner, name = None, None

    repo = adapter.get_repository(owner, name)
    output(repo, fmt=fmt)
