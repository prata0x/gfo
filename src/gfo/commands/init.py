"""gfo init サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.config import (
    ProjectConfig,
    build_default_api_url,
    get_host_config,
    save_project_config,
)
from gfo.detect import DetectResult, detect_from_url, detect_service
from gfo.exceptions import ConfigError, DetectionError, GitCommandError
from gfo.git_util import get_remote_url

_VALID_SERVICE_TYPES = frozenset({
    "github", "gitlab", "bitbucket", "azure-devops",
    "gitea", "forgejo", "gogs", "gitbucket", "backlog",
})


def handle(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo init のハンドラ。"""
    if getattr(args, "non_interactive", False):
        _handle_non_interactive(args)
    else:
        _handle_interactive(args)


def _handle_non_interactive(args: argparse.Namespace) -> None:
    """--non-interactive モードの処理。"""
    service_type = getattr(args, "type", None)
    host = getattr(args, "host", None)

    if not service_type:
        raise ConfigError("--type is required in non-interactive mode.")
    if service_type not in _VALID_SERVICE_TYPES:
        valid = ", ".join(sorted(_VALID_SERVICE_TYPES))
        raise ConfigError(
            f"Unknown service type '{service_type}'. Valid values: {valid}"
        )
    if not host:
        raise ConfigError("--host is required in non-interactive mode.")

    # owner/repo/organization は detect_from_url() で取得
    try:
        remote_url = get_remote_url()
        detect_result = detect_from_url(remote_url)
    except (GitCommandError, DetectionError) as e:
        raise ConfigError(
            f"Could not detect repository from remote URL: {e} "
            "Please ensure you're in a git repository with an origin remote configured."
        ) from e

    # api_url の解決: args.api_url → get_host_config → build_default_api_url
    api_url = getattr(args, "api_url", None)
    if not api_url:
        host_cfg = get_host_config(host)
        if host_cfg and "api_url" in host_cfg:
            api_url = host_cfg["api_url"]
    if not api_url:
        project_key = getattr(args, "project_key", None)
        api_url = build_default_api_url(service_type, host, organization=detect_result.organization, project=project_key)

    project_key = getattr(args, "project_key", None) or detect_result.project

    config = ProjectConfig(
        service_type=service_type,
        host=host,
        api_url=api_url,
        owner=detect_result.owner,
        repo=detect_result.repo,
        organization=detect_result.organization,
        project_key=project_key,
    )
    save_project_config(config)
    print(f"Initialized: {service_type} at {host}")


def _handle_interactive(args: argparse.Namespace) -> None:
    """対話モードの処理。"""
    detect_result: DetectResult | None = None

    try:
        detect_result = detect_service()
        print(f"Detected: {detect_result.service_type} at {detect_result.host}")
        answer = input("Is this correct? [Y/n]: ").strip().lower()
        if answer in ("n", "no"):
            detect_result = None
    except DetectionError:
        print("Could not auto-detect service. Please enter manually.")

    if detect_result is not None:
        # 検出結果を使用
        service_type = detect_result.service_type
        # detect_service() は service_type が None のまま返さないが型注釈上は str | None のため絞り込む
        if service_type is None:
            service_type = input("Service type (github/gitlab/bitbucket/...): ").strip()
        host = detect_result.host
        owner = detect_result.owner
        repo = detect_result.repo
        organization = detect_result.organization
        project_key = detect_result.project

        try:
            api_url = build_default_api_url(service_type, host, organization, project_key)
        except ConfigError:
            # organization / project_key が未解決の場合（Azure DevOps 等）に手動入力へフォールバック
            print(
                "Could not build API URL automatically "
                "(organization or project key may be missing)."
            )
            if organization is None:
                organization = input("Organization: ").strip() or None
            if project_key is None:
                project_key = input("Project key: ").strip() or None
            try:
                api_url = build_default_api_url(service_type, host, organization, project_key)
            except ConfigError as e:
                raise ConfigError(
                    f"Could not build API URL for {service_type}: {e}. "
                    "Use --api-url to specify the URL manually."
                ) from e
    else:
        # 手動入力
        service_type = input("Service type (github/gitlab/bitbucket/...): ").strip()
        if not service_type:
            raise ConfigError("service_type cannot be empty.")
        if service_type not in _VALID_SERVICE_TYPES:
            valid = ", ".join(sorted(_VALID_SERVICE_TYPES))
            raise ConfigError(f"Unknown service type {service_type!r}. Valid: {valid}")
        host = input("Host: ").strip()
        if not host:
            raise ConfigError("host cannot be empty.")
        api_url_input = input("API URL (leave blank for default): ").strip()
        project_key = input("Project key (leave blank if none): ").strip() or None

        # owner/repo は remote URL から取得を試みる
        try:
            remote_url = get_remote_url()
            from_url = detect_from_url(remote_url)
            owner = from_url.owner
            repo = from_url.repo
            organization = from_url.organization
        except (DetectionError, GitCommandError, ValueError, OSError):
            owner = ""
            repo = ""
            organization = None

        if api_url_input:
            api_url = api_url_input
        else:
            api_url = build_default_api_url(service_type, host, organization, project_key)

    config = ProjectConfig(
        service_type=service_type,
        host=host,
        api_url=api_url,
        owner=owner,
        repo=repo,
        organization=organization,
        project_key=project_key,
    )
    save_project_config(config)
    print(f"Initialized: {service_type} at {host}")
