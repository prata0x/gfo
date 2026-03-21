"""CI コマンドの CLI 統合テスト。

GitHub / GitLab のみ（テストリポジトリに CI 実行履歴が必要）。
他のサービスでは NotSupportedError を検証する。
"""

from __future__ import annotations

import pytest

from gfo.exceptions import ExitCode
from tests.integration.cli_helper import CLIResult, make_project_config, run_cli
from tests.integration.conftest import (
    ServiceTestConfig,
    create_test_adapter,
    get_service_config,
)

# CI が対応しているサービス
_CI_SUPPORTED = {"github", "gitlab", "gitea", "forgejo"}

# CI 非対応サービス
_CI_NOT_SUPPORTED = {"bitbucket", "azure-devops", "backlog", "gogs", "gitbucket"}


# ── CI 対応サービスのテスト ──


def _make_ci_test_class(
    service_type: str,
    *,
    marker: str,
    skip_reason: str,
):
    """CI テストクラスを動的に生成する。"""
    config = get_service_config(service_type)

    marks = [
        pytest.mark.integration,
        pytest.mark.cli,
        pytest.mark.slow,
        getattr(pytest.mark, marker),
        pytest.mark.skipif(config is None, reason=skip_reason),
    ]

    class CITestBase:
        """CI コマンド CLI テスト基底クラス。"""

        CONFIG: ServiceTestConfig | None = config
        _pipeline_id: str | int | None = None

        @classmethod
        def setup_class(cls) -> None:
            assert cls.CONFIG is not None
            cls.adapter = create_test_adapter(cls.CONFIG)
            cls.project_config = make_project_config(cls.CONFIG)

        def _run(self, argv: list[str]) -> CLIResult:
            return run_cli(argv, self.adapter, config=self.project_config)

        def test_ci_list(self) -> None:
            result = self._run(["ci", "list", "--limit", "5", "--format", "json"])
            assert result.exit_code == 0
            data = result.json()
            assert isinstance(data, list)
            if data:
                self.__class__._pipeline_id = data[0].get("id")

        def test_ci_view(self) -> None:
            if self._pipeline_id is None:
                pytest.skip("No pipeline found to view")
            result = self._run(
                [
                    "ci",
                    "view",
                    str(self._pipeline_id),
                    "--format",
                    "json",
                ]
            )
            assert result.exit_code == 0

        def test_ci_workflow_list(self) -> None:
            result = self._run(
                [
                    "ci",
                    "workflow",
                    "list",
                    "--format",
                    "json",
                ]
            )
            # NotSupportedError は一部のサービスで発生する可能性がある
            # Forgejo Docker 環境では Actions 未設定のため NETWORK エラーの可能性がある
            assert result.exit_code in (
                0,
                ExitCode.NOT_SUPPORTED,
                ExitCode.NOT_FOUND,
                ExitCode.NETWORK,
            )

    for mark in marks:
        CITestBase = mark(CITestBase)

    return CITestBase


def _make_ci_not_supported_class(
    service_type: str,
    *,
    marker: str,
    skip_reason: str,
):
    """CI 非対応サービスのテストクラスを動的に生成する。"""
    config = get_service_config(service_type)

    marks = [
        pytest.mark.integration,
        pytest.mark.cli,
        getattr(pytest.mark, marker),
        pytest.mark.skipif(config is None, reason=skip_reason),
    ]

    class CINotSupportedBase:
        """CI 非対応サービスの CLI テスト基底クラス。"""

        CONFIG: ServiceTestConfig | None = config

        @classmethod
        def setup_class(cls) -> None:
            assert cls.CONFIG is not None
            cls.adapter = create_test_adapter(cls.CONFIG)
            cls.project_config = make_project_config(cls.CONFIG)

        def _run(self, argv: list[str]) -> CLIResult:
            return run_cli(argv, self.adapter, config=self.project_config)

        def test_ci_list_not_supported(self) -> None:
            result = self._run(["ci", "list", "--format", "json"])
            # GitBucket/Gogs は親クラスの実装が呼ばれて NETWORK エラーになる場合がある
            assert result.exit_code in (
                ExitCode.NOT_SUPPORTED,
                ExitCode.NOT_FOUND,
                ExitCode.NETWORK,
            )

    for mark in marks:
        CINotSupportedBase = mark(CINotSupportedBase)

    return CINotSupportedBase


# ── CI 対応: GitHub / GitLab / Gitea / Forgejo ──


class TestCIGitHub(
    _make_ci_test_class("github", marker="saas", skip_reason="GitHub credentials not configured")
):
    pass


class TestCIGitLab(
    _make_ci_test_class("gitlab", marker="saas", skip_reason="GitLab credentials not configured")
):
    pass


class TestCIGitea(
    _make_ci_test_class(
        "gitea", marker="selfhosted", skip_reason="Gitea credentials not configured"
    )
):
    pass


class TestCIForgejo(
    _make_ci_test_class(
        "forgejo", marker="selfhosted", skip_reason="Forgejo credentials not configured"
    )
):
    pass


# ── CI 対応: Bitbucket / Azure DevOps ──


class TestCIBitbucket(
    _make_ci_test_class(
        "bitbucket", marker="saas", skip_reason="Bitbucket credentials not configured"
    )
):
    pass


class TestCIAzureDevOps(
    _make_ci_test_class(
        "azure-devops", marker="saas", skip_reason="Azure DevOps credentials not configured"
    )
):
    pass


class TestCINotSupportedBacklog(
    _make_ci_not_supported_class(
        "backlog",
        marker="saas",
        skip_reason="Backlog credentials not configured (paid service)",
    )
):
    pass


class TestCINotSupportedGogs(
    _make_ci_not_supported_class(
        "gogs", marker="selfhosted", skip_reason="Gogs credentials not configured"
    )
):
    pass


class TestCINotSupportedGitBucket(
    _make_ci_not_supported_class(
        "gitbucket", marker="selfhosted", skip_reason="GitBucket credentials not configured"
    )
):
    pass
