"""T-20: adapter/__init__.py — 全アダプター登録のテスト"""

import pytest

import gfo.adapter  # noqa: F401 — 全アダプターを登録
from gfo.adapter.registry import _REGISTRY, get_adapter_class
from gfo.exceptions import UnsupportedServiceError

EXPECTED_SERVICES = [
    "github",
    "gitlab",
    "bitbucket",
    "azure-devops",
    "gitea",
    "forgejo",
    "gogs",
    "gitbucket",
    "backlog",
]


def test_all_adapters_registered():
    for stype in EXPECTED_SERVICES:
        assert stype in _REGISTRY, f"{stype} がレジストリに登録されていない"


def test_get_adapter_class_returns_class():
    for stype in EXPECTED_SERVICES:
        cls = get_adapter_class(stype)
        assert cls is not None


def test_unsupported_service_raises():
    with pytest.raises(UnsupportedServiceError):
        get_adapter_class("unknown-service")
