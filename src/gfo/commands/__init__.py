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
