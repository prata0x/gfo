from __future__ import annotations

from dataclasses import dataclass

from gfo.adapter.base import GitServiceAdapter
from gfo.adapter.registry import create_adapter
from gfo.config import ProjectConfig, resolve_project_config


def get_adapter() -> GitServiceAdapter:
    """設定を解決してアダプターインスタンスを返す共通ヘルパー。"""
    config = resolve_project_config()
    return create_adapter(config)


def get_adapter_with_config() -> tuple[GitServiceAdapter, ProjectConfig]:
    """設定を解決してアダプターインスタンスと設定オブジェクトをまとめて返す。

    service_type 等の設定値を参照しつつアダプターを使用するハンドラ向け。
    """
    config = resolve_project_config()
    return create_adapter(config), config


@dataclass(frozen=True)
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
        if len(segments) != 2 or not segments[0] or not segments[1]:
            raise ConfigError(
                _(
                    "Invalid service spec format: {spec}. Expected 'service:owner/repo' or 'service:host:owner/repo'."
                ).format(spec=spec)
            )
        owner = segments[0]
        repo = segments[1]
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
    kwargs: dict = {}
    if spec.service_type == "backlog" and spec.project_key:
        kwargs["project_key"] = spec.project_key
    elif spec.service_type == "azure-devops":
        if spec.organization:
            kwargs["organization"] = spec.organization
        if spec.project_key:
            kwargs["project_key"] = spec.project_key
    return adapter_cls(client, spec.owner, spec.repo, **kwargs)
