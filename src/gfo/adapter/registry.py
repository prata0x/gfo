"""サービス種別文字列からアダプタークラスを解決し、インスタンスを生成する。"""

from __future__ import annotations

from typing import Type

from gfo.adapter.base import GitServiceAdapter
from gfo.config import ProjectConfig
from gfo.exceptions import ConfigError, UnsupportedServiceError

_REGISTRY: dict[str, Type[GitServiceAdapter]] = {}


def register(service_type: str):
    """デコレータ。アダプタークラスをレジストリに登録する。"""
    def decorator(cls):
        _REGISTRY[service_type] = cls
        return cls
    return decorator


def get_adapter_class(service_type: str) -> Type[GitServiceAdapter]:
    """サービス種別からアダプタークラスを返す。未登録なら UnsupportedServiceError。"""
    if service_type not in _REGISTRY:
        raise UnsupportedServiceError(service_type)
    return _REGISTRY[service_type]


def create_http_client(service_type: str, api_url: str, token: str):
    """サービス種別・API URL・トークンから HttpClient インスタンスを生成する。"""
    from gfo.http import HttpClient

    if service_type == "backlog":
        return HttpClient(api_url, auth_params={"apiKey": token})
    elif service_type == "bitbucket":
        if ":" not in token:
            raise ConfigError(
                "Bitbucket token must be in 'username:app-password' format. "
                "Run 'gfo auth login --host bitbucket.org' to reconfigure."
            )
        user, pw = token.split(":", 1)
        return HttpClient(api_url, basic_auth=(user, pw))
    elif service_type == "azure-devops":
        return HttpClient(
            api_url,
            basic_auth=("", token),
            default_params={"api-version": "7.1"},
        )
    elif service_type == "gitlab":
        return HttpClient(api_url, auth_header={"Private-Token": token})
    elif service_type == "github":
        return HttpClient(api_url, auth_header={"Authorization": f"Bearer {token}"})
    elif service_type in ("gitea", "forgejo", "gogs", "gitbucket"):
        return HttpClient(api_url, auth_header={"Authorization": f"token {token}"})
    else:
        raise UnsupportedServiceError(service_type)


def create_adapter(config: ProjectConfig) -> GitServiceAdapter:
    """ProjectConfig からアダプターインスタンスを生成する。"""
    import gfo.auth

    token = gfo.auth.resolve_token(config.host, config.service_type)
    stype = config.service_type

    kwargs: dict = {}

    if stype == "backlog":
        kwargs["project_key"] = config.project_key
    elif stype == "azure-devops":
        kwargs["organization"] = config.organization
        kwargs["project_key"] = config.project_key

    client = create_http_client(stype, config.api_url, token)
    adapter_cls = get_adapter_class(stype)
    return adapter_cls(client, config.owner, config.repo, **kwargs)
