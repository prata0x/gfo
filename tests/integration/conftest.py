"""統合テスト共通フィクスチャ・ヘルパー。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from gfo.adapter.base import GitServiceAdapter
from gfo.adapter.registry import create_http_client, get_adapter_class


# .env ファイルを読み込む（存在する場合）
_ENV_FILE = Path(__file__).parent / ".env"
if _ENV_FILE.exists():
    for line in _ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key.strip(), value)


@dataclass
class ServiceTestConfig:
    """統合テスト用のサービス設定。"""

    service_type: str
    host: str
    api_url: str
    owner: str
    repo: str
    token: str
    organization: str | None = None
    project_key: str | None = None
    # テスト用ブランチ名
    test_branch: str = "gfo-test-branch"
    # デフォルトブランチ名
    default_branch: str = "main"


# サービス種別ごとの環境変数マッピング
_TOKEN_ENV_MAP = {
    "github": "GFO_TEST_GITHUB_TOKEN",
    "gitlab": "GFO_TEST_GITLAB_TOKEN",
    "bitbucket": "GFO_TEST_BITBUCKET_APP_PASSWORD",
    "azure-devops": "GFO_TEST_AZURE_DEVOPS_PAT",
    "gitea": "GFO_TEST_GITEA_TOKEN",
    "forgejo": "GFO_TEST_FORGEJO_TOKEN",
    "gogs": "GFO_TEST_GOGS_TOKEN",
    "gitbucket": "GFO_TEST_GITBUCKET_TOKEN",
    "backlog": "GFO_TEST_BACKLOG_API_KEY",
}

# サービス種別ごとのデフォルト API URL
_DEFAULT_API_URLS = {
    "github": "https://api.github.com",
    "gitlab": "https://gitlab.com/api/v4",
    "bitbucket": "https://api.bitbucket.org/2.0",
}


def get_service_config(service_type: str) -> ServiceTestConfig | None:
    """環境変数からサービス設定を読み取る。設定不足なら None を返す。"""
    prefix = service_type.upper().replace("-", "_")

    # トークン
    token_var = _TOKEN_ENV_MAP.get(service_type, f"GFO_TEST_{prefix}_TOKEN")
    token = os.environ.get(token_var, "")
    if not token:
        return None

    # 基本情報
    owner = os.environ.get(f"GFO_TEST_{prefix}_OWNER", "")
    repo = os.environ.get(f"GFO_TEST_{prefix}_REPO", "")
    if not owner or not repo:
        return None

    # ホスト
    host = os.environ.get(f"GFO_TEST_{prefix}_HOST", "")

    # API URL
    api_url = os.environ.get(f"GFO_TEST_{prefix}_API_URL", "")
    if not api_url:
        if service_type in _DEFAULT_API_URLS:
            api_url = _DEFAULT_API_URLS[service_type]
        elif host:
            # セルフホスト向けのデフォルト構築
            if service_type in ("gitea", "forgejo", "gogs"):
                api_url = f"http://{host}/api/v1"
            elif service_type == "gitbucket":
                api_url = f"http://{host}/api/v3"
            elif service_type == "gitlab":
                api_url = f"http://{host}/api/v4"
            elif service_type == "azure-devops":
                org = os.environ.get(f"GFO_TEST_{prefix}_ORG", "")
                project = os.environ.get(f"GFO_TEST_{prefix}_PROJECT", "")
                api_url = f"https://dev.azure.com/{org}/{project}/_apis"
            elif service_type == "backlog":
                api_url = f"https://{host}/api/v2"
            else:
                api_url = f"http://{host}/api/v1"

    if not host:
        # API URL からホスト名を推定
        from urllib.parse import urlparse
        parsed = urlparse(api_url)
        host = parsed.netloc or parsed.hostname or ""

    # Azure DevOps 固有
    organization = os.environ.get(f"GFO_TEST_{prefix}_ORG")
    project_key = os.environ.get(f"GFO_TEST_{prefix}_PROJECT")
    # Backlog 固有
    if service_type == "backlog":
        project_key = os.environ.get(f"GFO_TEST_{prefix}_PROJECT_KEY")

    return ServiceTestConfig(
        service_type=service_type,
        host=host,
        api_url=api_url,
        owner=owner,
        repo=repo,
        token=token,
        organization=organization,
        project_key=project_key,
    )


def create_test_adapter(config: ServiceTestConfig) -> GitServiceAdapter:
    """ServiceTestConfig からアダプターインスタンスを生成する。"""
    client = create_http_client(config.service_type, config.api_url, config.token)
    adapter_cls = get_adapter_class(config.service_type)
    kwargs: dict = {}
    if config.organization is not None:
        kwargs["organization"] = config.organization
    if config.project_key is not None:
        kwargs["project_key"] = config.project_key
    return adapter_cls(client, config.owner, config.repo, **kwargs)
