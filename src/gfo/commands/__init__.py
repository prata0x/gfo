from gfo.adapter.base import GitServiceAdapter
from gfo.adapter.registry import create_adapter
from gfo.config import resolve_project_config


def get_adapter() -> GitServiceAdapter:
    """設定を解決してアダプターインスタンスを返す共通ヘルパー。"""
    config = resolve_project_config()
    return create_adapter(config)
