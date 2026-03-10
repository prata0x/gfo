"""サービス種別文字列からアダプタークラスを解決し、インスタンスを生成する。"""

from __future__ import annotations

from gfo.adapter.base import GitServiceAdapter
from gfo.config import ProjectConfig
from gfo.exceptions import ConfigError, UnsupportedServiceError

_REGISTRY: dict[str, type[GitServiceAdapter]] = {}


def register(service_type: str):
    """デコレータ。アダプタークラスをレジストリに登録する。"""

    def decorator(cls):
        _REGISTRY[service_type] = cls
        return cls

    return decorator


def get_adapter_class(service_type: str) -> type[GitServiceAdapter]:
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
                "Bitbucket token must be in 'email:api-token' format. "
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
    """ProjectConfig からアダプターインスタンスを生成する。

    create_http_client との分岐の非対称性について:
    - create_http_client は認証方式（auth_header/auth_params/basic_auth）が
      サービスごとに異なるため全サービスを列挙する。
    - create_adapter の kwargs 分岐は追加コンストラクタ引数が必要なサービス
      （backlog: project_key、azure-devops: organization/project_key）のみ。
      新サービス追加時に追加引数が不要であれば create_adapter の変更は不要。
    """
    import gfo.auth

    token = gfo.auth.resolve_token(config.host, config.service_type)
    service_type = config.service_type

    kwargs: dict = {}

    if service_type == "backlog":
        kwargs["project_key"] = config.project_key
    elif service_type == "azure-devops":
        kwargs["organization"] = config.organization
        kwargs["project_key"] = config.project_key

    client = create_http_client(service_type, config.api_url, token)
    adapter_cls = get_adapter_class(service_type)
    return adapter_cls(client, config.owner, config.repo, **kwargs)
